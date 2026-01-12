"""Main Cortex class"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

logger = logging.getLogger(__name__)

from .models import PermissionMode
from .config import AgentConfig
from .core.conversation import ConversationManager
from .core.parallel import ParallelToolExecutor, ToolCall
from .core.streaming import stream_model_response, display_streaming_response
from .core.providers import ProviderFactory, ProviderError
from .core.security import SecurityError
from .core.loop_guards import LoopGuard
from .core.summarization import (
    create_summarizer,
    SummarizationStrategy,
    SimpleSummarizer,
)
from .core.memory import (
    MemoryBank,
    create_memory_bank,
    extract_memories_from_messages,
)
from .tools import TOOLS, create_tool_instance
from .ui.console import console
from .utils.errors import retry_with_backoff, ModelError, create_error_response, ErrorType

# Hook system imports
from .hooks import (
    HookManager,
    HookAction,
    PreToolUseEvent,
    PostToolUseEvent,
    StopEvent,
    UserPromptSubmitEvent,
    SessionStartEvent,
    SessionEndEvent,
)
from .output import OutputFormat, create_formatter

try:
    from .core.streaming import stream_model_response, display_streaming_response
except ImportError:
    # Fallback if streaming not available
    stream_model_response = None
    display_streaming_response = None


class Cortex:
    """Main Cortex class - handles conversation loop and tool execution"""

    def __init__(
        self,
        model: str = "llama3.2",
        project_dir: str = ".",
        permission_mode: str = PermissionMode.NORMAL,
        config: Optional[AgentConfig] = None,
        hook_manager: Optional[HookManager] = None,
        output_format: OutputFormat = OutputFormat.TEXT,
        on_max_iterations_reached: Optional[Callable[[int, int], Optional[int]]] = None,
    ):
        self.model = model
        self.project_dir = Path(project_dir).resolve()
        self.permission_mode = permission_mode
        self.config = config or AgentConfig()
        self.session_start = datetime.now()

        # Initialize hook manager
        self.hook_manager = hook_manager or HookManager()

        # Initialize output formatter
        self.output_format = output_format
        self.formatter = create_formatter(output_format, console=console)

        # Initialize history directory
        self.history_dir = Path.home() / ".cortex" / "sessions"
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Load project context (must be before _get_system_prompt)
        self.project_context = self._load_project_context()

        # Initialize memory bank for tracking decisions and facts
        self.memory_bank = create_memory_bank(max_items=50)

        # Initialize conversation manager with summarization support
        system_prompt = self._get_system_prompt()
        warn_on_truncation = self.config.session_retention.get("warn_on_truncation", True)

        # Create summarizer for intelligent context management
        # Use simple summarization by default (no extra API calls)
        # Can be upgraded to LLM-based or hybrid via config
        summarization_config = getattr(self.config, "summarization", {})
        enable_summarization = summarization_config.get("enabled", True)
        strategy_name = summarization_config.get("strategy", "simple")

        if strategy_name == "llm":
            strategy = SummarizationStrategy.LLM_BASED
        elif strategy_name == "hybrid":
            strategy = SummarizationStrategy.HYBRID
        else:
            strategy = SummarizationStrategy.SIMPLE

        summarizer = create_summarizer(strategy) if enable_summarization else None

        self.conversation = ConversationManager(
            system_prompt=system_prompt,
            max_tokens=self.config.max_tokens,
            keep_recent=self.config.keep_recent_messages,
            model=self.model,
            warn_on_truncation=warn_on_truncation,
            on_truncation=self._on_context_truncation,
            summarizer=summarizer,
            enable_summarization=enable_summarization,
            summarization_threshold=summarization_config.get("threshold", 0.8),
        )

        # Initialize loop guard with recovery manager if enabled
        recovery_manager = None
        if self.config.error_recovery.get("enable_smart_recovery", False):
            from .core.recovery import create_recovery_manager_from_config

            recovery_manager = create_recovery_manager_from_config(self.config.error_recovery)

        self.loop_guard = LoopGuard(
            max_repeats=self.config.error_recovery.get("max_repeats", 3),
            stuck_threshold=self.config.error_recovery.get("stuck_threshold", 5),
            buffer_size=self.config.error_recovery.get("buffer_size", 10),
            recovery_manager=recovery_manager,
        )

        # Initialize parallel tool executor
        parallel_config = self.config.get_parallel_execution_config()
        self.parallel_executor = ParallelToolExecutor(
            execute_fn=self.execute_tool,
            max_workers=parallel_config.get("max_workers", 4),
            enabled=parallel_config.get("enabled", True),
        )

        # Initialize timeout configuration
        self._timeout_config = self.config.get_timeout_config()

        # Initialize model provider
        provider_override = getattr(self.config, "provider", None)
        try:
            self.provider = ProviderFactory.get_provider(self.model, provider_override)
            # Validate API key for cloud providers
            if not self.provider.validate_api_key():
                raise ProviderError(
                    f"API key not set for {ProviderFactory.get_provider_name(self.model)} provider. "
                    f"Please set the required environment variable."
                )
        except ProviderError as e:
            raise ProviderError(f"Failed to initialize provider: {e}") from e

        # Track tools used in session (for metrics)
        self._tools_used: List[str] = []

        # Shutdown flag for graceful termination
        self._shutdown_requested = False
        self._session_dirty = False  # Track if session needs saving

        # Display settings
        self.show_thinking = False  # Toggle for reasoning display

        # Set default callback if configured
        if on_max_iterations_reached is None and self.config.max_iterations_continue_default:

            def default_callback(current: int, max_iter: int) -> Optional[int]:
                # Auto-continue with configured amount
                return self.config.max_iterations_continue_amount

            self._on_max_iterations_reached = default_callback
        else:
            self._on_max_iterations_reached = on_max_iterations_reached

        # Dispatch session start event
        self._dispatch_session_start()

    def _on_context_truncation(self, messages_removed: int, remaining: int) -> None:
        """Callback when context is truncated."""
        if self._is_text_output():
            console.print(
                f"[yellow]Context truncated:[/yellow] Removed {messages_removed} old messages "
                f"({remaining} remaining)"
            )

    def switch_model(self, new_model: str, provider_override: Optional[str] = None) -> None:
        """
        Switch to a different model while maintaining conversation history.

        Reinitializes the provider and updates conversation manager's model reference.
        This allows switching between models (e.g., local to cloud) while keeping
        the same conversation context.

        Args:
            new_model: New model name to use
            provider_override: Optional provider override

        Raises:
            ProviderError: If provider initialization fails or API key is missing
        """
        # Skip if same model
        if new_model == self.model:
            return

        old_model = self.model
        old_provider_name = ProviderFactory.get_provider_name(self.model)

        try:
            # Reinitialize provider for new model
            provider_override = provider_override or getattr(self.config, "provider", None)
            new_provider = ProviderFactory.get_provider(new_model, provider_override)

            # Validate API key for cloud providers
            if not new_provider.validate_api_key():
                provider_name = ProviderFactory.get_provider_name(new_model)
                raise ProviderError(
                    f"API key not set for {provider_name} provider. "
                    f"Please set the required environment variable."
                )

            # Update model and provider
            self.model = new_model
            self.provider = new_provider

            # Update conversation manager's model reference for token counting
            self.conversation.update_model(new_model)

            # Notify user of model switch
            new_provider_name = ProviderFactory.get_provider_name(new_model)
            if old_provider_name != new_provider_name:
                console.print(
                    f"[cyan]🔄 Switched model:[/cyan] {old_model} ({old_provider_name}) → "
                    f"{new_model} ({new_provider_name})"
                )
            else:
                console.print(f"[cyan]🔄 Switched model:[/cyan] {old_model} → {new_model}")

        except ProviderError as e:
            # Keep old model on error
            console.print(f"[red]Failed to switch model:[/red] {e}")
            raise ProviderError(f"Failed to switch model: {e}") from e

    def _load_project_context(self) -> str:
        """Load AGENT.md or README.md for project context"""
        context_files = ["AGENT.md", "CLAUDE.md", "README.md"]

        for filename in context_files:
            filepath = self.project_dir / filename
            if filepath.exists():
                try:
                    content = filepath.read_text()
                    console.print(f"[dim]📋 Loaded project context from {filename}[/dim]")
                    return content[:2000]  # Limit context size
                except:
                    pass
        return ""

    def _get_system_prompt(self) -> str:
        """Generate comprehensive system prompt for the agent"""
        mode_instructions = {
            PermissionMode.NORMAL: "Ask for user approval before making changes.",
            PermissionMode.AUTO_APPROVE: "You can make changes without asking. Be careful!",
            PermissionMode.PLAN: "You are in PLAN MODE - read-only. Do not write files or execute commands. Only analyze and create plans.",
        }

        # Get memory summary if available
        memory_summary = ""
        if hasattr(self, "memory_bank") and self.memory_bank:
            memory_summary = self.memory_bank.get_summary()

        return f"""You are Cortex, a powerful AI coding assistant working in: {self.project_dir}

Permission Mode: {self.permission_mode.upper()}
{mode_instructions[self.permission_mode]}

{f"Project Context:{chr(10)}{self.project_context}" if self.project_context else ""}
{f"Session Memory:{chr(10)}{memory_summary}" if memory_summary else ""}

# Mental Model for Codebase Understanding

When exploring a new codebase, build understanding systematically:

## Phase 1: Structure Discovery (1-2 tool calls)
```
glob(pattern="**/*.py")  # Map all source files
```
From this, identify:
- Entry points (main.py, cli.py, app.py, __main__.py)
- Core packages (src/, lib/, cortex/)
- Tests location (tests/, test_*)
- Config files (*.yaml, *.json, *.toml)

## Phase 2: Architecture Understanding (2-3 tool calls)
```
grep(pattern="^class ", file_type="py")           # Find all classes
grep(pattern="^def |^async def ", file_type="py") # Find top-level functions
```
Build a mental map:
- Entry points → Core logic → Utilities → Data models

## Phase 3: Targeted Deep Dives
Only read files when you have a specific reason. Track what you've read to avoid re-reading.

**Efficiency Rule**: Always use `files_with_matches` mode first for breadth, then `content` mode only when narrowing down.

# Self-Awareness

## Your Capabilities
- **Search**: glob for files, grep for content - these are your eyes
- **Read**: Deep understanding of specific files
- **Edit**: Surgical changes with exact string replacement
- **Write**: Create new files or replace content entirely
- **Execute**: Run commands, tests, git operations

## Your Limitations
- Cannot see file changes until you re-read them
- Cannot run interactive commands (vi, less, etc.)
- Cannot access external URLs without web tools
- Token-limited: be efficient, avoid reading entire codebases

## Decision Making
- **Confident action**: When you know exactly what to do, do it
- **Ask first**: When requirements are ambiguous or risky
- **Investigate first**: When you need more context before deciding

# Efficiency Patterns

## Minimize Tool Calls
BAD: Read every file to find a function
GOOD: grep(pattern="def target_function") → read only the matching file

BAD: Multiple greps for related things
GOOD: Single grep with OR pattern: "class.*Service|def.*service"

## Optimal Search Strategy
1. **File discovery**: glob("**/*.ext") - understand what exists
2. **Content search**: grep with files_with_matches mode - find where
3. **Targeted read**: read_file only files you need

## Edit vs Write
- **edit**: Changes < 20 lines, or multiple small changes in a file
- **write_file**: New files, or changes > 50% of file content

# Proactive Behavior

## When to Act Without Asking
- Obvious bug fixes (typos, missing imports)
- Direct requests with clear requirements
- Following established patterns in the codebase

## When to Ask First
- Architectural decisions
- Multiple valid approaches exist
- Destructive operations (delete, overwrite)
- Changes affecting multiple files

## When to Investigate First
- "Fix the bug" (need to find and understand it)
- "Improve performance" (need to profile first)
- "Add feature X" (need to understand existing patterns)

# Tool Reference

## File Discovery
| Tool | Use Case | Example |
|------|----------|---------|
| glob | Find files by pattern | `glob(pattern="**/*.py")` |
| list_files | Browse directory | `list_files(path="src")` |

## Content Search (grep)
| Mode | Use Case | Example |
|------|----------|---------|
| files_with_matches | Find which files | `grep(pattern="class.*Tool")` |
| content | See matching lines | `grep(pattern="def main", output_mode="content")` |
| count | Frequency analysis | `grep(pattern="TODO", output_mode="count")` |

## File Operations
| Tool | Use Case | Example |
|------|----------|---------|
| read_file | Understand code | `read_file(path="main.py")` |
| edit | Surgical changes | `edit(file_path="x.py", old_string="a", new_string="b")` |
| write_file | New/full rewrite | `write_file(path="new.py", content="...")` |

## Execution
| Tool | Use Case | Example |
|------|----------|---------|
| execute_command | Shell commands | `execute_command(command="pip install x")` |
| run_tests | Run test suite | `run_tests(pattern="test_auth.py")` |
| git_add | Stage changes | `git_add(files=["a.py", "b.py"])` or `git_add(add_all=True)` |
| git_branch | Manage branches | `git_branch(action="create", branch_name="feat/new-thing")` |
| git_checkout | Switch branches | `git_checkout(branch="feat/new-thing")` |
| git_commit | Commit changes | `git_commit(message="Initial commit")` |
| git_diff | Show changes | `git_diff(path="a.py")` |
| git_fetch | Fetch from remote| `git_fetch(remote="origin")` |
| git_log | Show commit history| `git_log(limit=10)` |
| git_pull | Pull from remote | `git_pull(remote="origin", branch="main")` |
| git_push | Push to remote | `git_push(remote="origin", branch="main")` |
| git_remote | List remotes | `git_remote(verbose=True)` |
| git_reset | Unstage files | `git_reset(files=["a.py", "b.py"])` |
| git_show | Show object details| `git_show(ref="HEAD")` |
| git_status | See repo status | `git_status()` |

# Error Recovery

When tools fail, don't give up immediately:

## File Not Found
1. Check exact spelling and case
2. Search for similar: `glob(pattern="**/*partial_name*")`
3. List parent directory to verify path

## Command Failed
1. Read the exact error message
2. Check if dependencies are installed
3. Try a simpler version of the command
4. Consider platform differences (Windows vs Unix)

## Edit Failed (string not unique)
1. Include more context in old_string
2. Use replace_all=True if appropriate
3. Fall back to write_file for complex changes

# Response Style

- **Be direct**: Get to the point, avoid filler phrases
- **Be specific**: Use file:line format (e.g., `main.py:42`)
- **Be helpful**: Explain what you're doing and why
- **Be honest**: Say "I don't know" rather than guess
- **Be efficient**: Minimize unnecessary tool calls

# Quick Reference

**NO TOOLS for**: Greetings, general questions, knowledge from training
**USE TOOLS for**: File ops, code search, commands, git

**CLI Commands**:
- `/model <model_name>`: Switch the active LLM model (e.g., `/model deepseek-coder`)
- `/clear`: Clear conversation history
- `/mode [normal|auto|plan]`: Change agent's permission mode
- `/project`: Show project info and agent settings
- `/save <name>`: Save current session
- `/load <name>`: Load a saved session
- `/sessions`: List all saved sessions
- `/storage`: Show storage stats
- `/cleanup`: Run manual session cleanup
- `/rollback`: Rollback last transaction (if active)
- `/transactions`: Show transaction stats
- `/summary`: Show conversation summary
- `/plan`: Enter planning (read-only) mode
- `/reset-context`: Clear conversation but keep memory
- `/focus <path>`: Set focus directory for searches
- `/thinking [on|off]`: Toggle thinking process display
- `/memory`: Show memory bank contents
- `/stats`: Show agent statistics
- `/exit`: Exit Cortex
- `/help`: Display help information

**Read before modifying** | **Search before creating** | **Test after changing**

Remember: You are a skilled developer's assistant. Think systematically, act precisely, communicate clearly."""

    def _dispatch_session_start(self) -> None:
        """Dispatch session start event to hooks."""
        event = SessionStartEvent(
            model=self.model,
            project_dir=str(self.project_dir),
            permission_mode=self.permission_mode,
            config={
                "max_iterations": self.config.max_iterations,
                "max_tokens": self.config.max_tokens,
            },
        )
        self.hook_manager.dispatch(event)

    def _dispatch_session_end(self) -> None:
        """Dispatch session end event to hooks."""
        event = SessionEndEvent(
            model=self.model,
            project_dir=str(self.project_dir),
            messages_count=len(self.conversation.get_history()),
            tools_used=list(set(self._tools_used)),
        )
        self.hook_manager.dispatch(event)

    # Output helper methods for format-aware display
    def _is_text_output(self) -> bool:
        """Check if we're in text output mode (vs JSON modes)."""
        return self.output_format == OutputFormat.TEXT

    def _output_response(self, response: Dict[str, Any], is_final: bool = False) -> None:
        """Output a response using the appropriate formatter."""
        content = response.get("content", "")
        if not content:
            return

        if self._is_text_output():
            # Always use simple markdown output (no Panel boxes)
            console.print(Markdown(content))
        else:
            formatted = self.formatter.format_response(response)
            self.formatter.write(formatted)

    def _output_tool_result(self, tool_name: str, result: Dict[str, Any]) -> None:
        """Output a tool result using the appropriate formatter."""
        if not self._is_text_output():
            formatted = self.formatter.format_tool_result(tool_name, result)
            self.formatter.write(formatted)
        # In text mode, tool results are shown by the tools themselves

    def _output_error(
        self, error: str, error_type: str = "error", context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Output an error using the appropriate formatter."""
        if self._is_text_output():
            console.print(f"[red]{error_type.upper()}:[/red] {error}")
        else:
            formatted = self.formatter.format_error(error, error_type, context)
            self.formatter.write(formatted)

    def _output_warning(self, message: str) -> None:
        """Output a warning message."""
        if self._is_text_output():
            console.print(f"[yellow]{message}[/yellow]")
        else:
            formatted = self.formatter.format_error(message, "warning")
            self.formatter.write(formatted)

    @retry_with_backoff(max_retries=3, exceptions=(Exception,))
    def _call_model(
        self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Call model via provider with retry logic"""
        try:
            # Normalize model name for provider
            normalized_model = self.provider.normalize_model_name(self.model)
            return self.provider.chat(model=normalized_model, messages=messages, tools=tools)
        except ProviderError as e:
            raise ModelError(f"Provider error: {e}") from e
        except Exception as e:
            raise ModelError(f"Failed to call model: {e}") from e

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return result with hook support."""

        # Fix: Handle string arguments (JSON)
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return create_error_response(
                    f"Invalid JSON in tool arguments: {arguments}",
                    ErrorType.VALIDATION,
                    {"tool_name": tool_name},
                )

        # Dispatch PreToolUse hook
        pre_event = PreToolUseEvent(
            tool_name=tool_name, arguments=arguments, permission_mode=self.permission_mode
        )
        pre_result = self.hook_manager.dispatch(pre_event)

        # Handle hook actions
        if pre_result.action == HookAction.ABORT:
            return create_error_response(
                pre_result.message or "Blocked by hook",
                ErrorType.PERMISSION,
                {"tool_name": tool_name, "blocked_by": "hook"},
            )
        elif pre_result.action == HookAction.SKIP:
            return {
                "success": True,
                "skipped": True,
                "reason": pre_result.message or "Skipped by hook",
            }
        elif pre_result.action == HookAction.MODIFY and pre_result.modified_data:
            # Use modified arguments from hook
            tool_name = pre_result.modified_data.get("tool_name", tool_name)
            arguments = pre_result.modified_data.get("arguments", arguments)

        # Track tool usage
        self._tools_used.append(tool_name)

        # Execute tool with timing
        start_time = time.time()
        result = None
        success = False

        try:
            # Create tool instance (pass self for task tool which needs parent_agent)
            tool = create_tool_instance(
                tool_name,
                self.project_dir,
                self.permission_mode,
                console,
                parent_agent=self,
                timeout_config=self._timeout_config,
            )

            # Execute tool
            result = tool.execute(**arguments)
            success = result.get("success", False)

        except ValueError as e:
            result = create_error_response(
                f"Unknown tool: {tool_name}", ErrorType.VALIDATION, {"tool_name": tool_name}
            )
        except SecurityError as e:
            result = create_error_response(str(e), ErrorType.SECURITY, {"tool_name": tool_name})
        except Exception as e:
            result = create_error_response(str(e), ErrorType.EXECUTION, {"tool_name": tool_name})

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Dispatch PostToolUse hook
        post_event = PostToolUseEvent(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            duration_ms=duration_ms,
        )
        post_result = self.hook_manager.dispatch(post_event)

        # Allow hooks to modify the result
        if post_result.action == HookAction.MODIFY and post_result.modified_data:
            if "result" in post_result.modified_data:
                result = post_result.modified_data["result"]

        return result

    def _is_tool_result_success(self, result: Dict[str, Any]) -> bool:
        """Check if tool result indicates success"""
        return result.get("success", False) and "error" not in result

    def _validate_tool_result(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """Validate tool result has expected structure"""
        # Must have success field
        if "success" not in result:
            return False

        # If error, must have error field or error_type
        if not result["success"]:
            if "error" not in result and "error_type" not in result:
                return False

        return True

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        self._shutdown_requested = True

    def _cleanup(self) -> None:
        """
        Cleanup resources on shutdown.
        Saves session state if dirty and dispatches session end event.
        """
        try:
            # Dispatch session end event
            self._dispatch_session_end()

            # Shutdown parallel executor
            if self.parallel_executor:
                self.parallel_executor.shutdown()

            # Note: Session saving is handled by CLI layer if needed
            # This cleanup focuses on internal state

        except Exception as e:
            # Log with traceback for debugging, but don't raise
            logger.warning(f"Error during cleanup: {e}", exc_info=True)

    def _process_message(self, user_message: str, use_streaming: bool = False):
        """Process a user message through the agent loop with hook support."""

        # Check for shutdown request
        if self._shutdown_requested:
            return

        # Dispatch UserPromptSubmit hook
        prompt_event = UserPromptSubmitEvent(
            prompt=user_message, conversation_length=len(self.conversation.get_history())
        )
        prompt_result = self.hook_manager.dispatch(prompt_event)

        # Handle hook actions
        if prompt_result.action == HookAction.ABORT:
            self._output_error(prompt_result.message or "Blocked by hook", "prompt_blocked")
            return
        elif prompt_result.action == HookAction.MODIFY and prompt_result.modified_data:
            # Use modified prompt from hook
            user_message = prompt_result.modified_data.get("prompt", user_message)

        # Add user message
        self.conversation.add_user_message(user_message)
        self._session_dirty = True

        # Agent loop - use while True with explicit break for dynamic iteration extension
        max_iterations = self.config.max_iterations
        iteration = 0

        while True:
            iteration += 1

            # Check for shutdown request
            if self._shutdown_requested:
                self._output_warning("Shutdown requested. Cleaning up...")
                self._cleanup()
                return

            # Check if we've exceeded max iterations (before processing)
            if iteration > max_iterations:
                # Check if callback is set
                if self._on_max_iterations_reached:
                    additional = self._on_max_iterations_reached(iteration, max_iterations)
                    if additional is not None and additional > 0:
                        # Extend max_iterations and continue
                        max_iterations += additional
                        console.print(
                            f"[cyan]Extended iterations:[/cyan] +{additional} more (total: {max_iterations})"
                        )
                        continue  # Continue the loop with extended limit
                    else:
                        # Callback returned 0 or None - stop
                        self._output_warning("Reached maximum iterations")
                        return
                else:
                    # No callback - default behavior (stop)
                    self._output_warning("Reached maximum iterations")
                    return

            self.loop_guard.increment_iteration()
            console.print(f"[dim]{'─' * 60}[/dim]")

            try:
                # Get conversation history
                messages = self.conversation.get_history()

                # Show thinking indicator
                with console.status("[cyan]🤔 Thinking...[/cyan]", spinner="dots"):
                    if (
                        use_streaming
                        and stream_model_response
                        and self.provider.supports_streaming()
                    ):
                        # Streaming mode
                        normalized_model = self.provider.normalize_model_name(self.model)
                        stream = stream_model_response(
                            self.provider, normalized_model, messages, TOOLS
                        )
                        response_message = display_streaming_response(stream)
                    else:
                        # Non-streaming mode
                        response = self._call_model(messages, TOOLS)
                        response_message = response["message"]

                # Add assistant response
                self.conversation.add_assistant_message(
                    content=response_message.get("content", ""),
                    tool_calls=response_message.get("tool_calls"),
                    reasoning_content=response_message.get("reasoning_content"),
                )

                # Display thinking/reasoning if enabled and present
                reasoning_content = response_message.get("reasoning_content")
                if reasoning_content and self._is_text_output():
                    from .ui.display import display_thinking

                    display_thinking(reasoning_content, expanded=self.show_thinking)

                # Check if using tools
                if response_message.get("tool_calls"):
                    # Don't display content here if tools are present - wait for final response
                    # Create ToolCall objects for batch execution
                    tool_calls_to_run = []
                    for i, tool_call_data in enumerate(response_message["tool_calls"]):
                        tool_calls_to_run.append(
                            ToolCall(
                                id=tool_call_data.get("id", f"call_{iteration}_{i}"),
                                name=tool_call_data["function"]["name"],
                                arguments=tool_call_data["function"]["arguments"],
                                index=i,
                            )
                        )

                    # Execute tools in batch
                    batch_result = self.parallel_executor.execute_batch(tool_calls_to_run)

                    # Process results
                    for tool_result in batch_result.results:
                        # Check for shutdown request before each tool
                        if self._shutdown_requested:
                            self._output_warning("Shutdown requested. Stopping tool execution...")
                            self._cleanup()
                            return

                        tool_name = tool_result.name
                        arguments = next(
                            (
                                tc.arguments
                                for tc in tool_calls_to_run
                                if tc.id == tool_result.id
                            ),
                            {},
                        )
                        result = tool_result.result

                        # Output tool result (for JSON modes)
                        self._output_tool_result(tool_name, result)

                        # Validate result
                        if not self._validate_tool_result(tool_name, result):
                            self._output_warning(f"Invalid tool result format from {tool_name}")
                            result = create_error_response(
                                "Tool returned invalid result format",
                                ErrorType.EXECUTION,
                                {"tool_name": tool_name},
                            )

                        # Add result to conversation
                        self.conversation.add_tool_result(tool_result.id, result)

                        # Parse arguments for loop guards
                        parsed_arguments = arguments
                        if isinstance(arguments, str):
                            try:
                                parsed_arguments = json.loads(arguments)
                            except json.JSONDecodeError:
                                parsed_arguments = {}

                        # Check loop guards
                        if not self._is_tool_result_success(result):
                            self.loop_guard.record_error(result)
                            if self.loop_guard.check_repeated_error(result):
                                recovery_action = self.loop_guard.get_recovery_action(
                                    result, tool_name, parsed_arguments
                                )
                                if recovery_action:
                                    from .core.recovery import RecoveryStrategy

                                    if recovery_action.strategy != RecoveryStrategy.ESCALATE:
                                        self._output_warning(
                                            f"Recovery triggered: {recovery_action.message}"
                                        )
                                        if recovery_action.suggested_prompt:
                                            self.conversation.add_user_message(
                                                f"[Recovery Guidance] {recovery_action.suggested_prompt}"
                                            )
                                        continue
                                self._output_error(
                                    "Repeated error detected. Stopping to prevent infinite loop.",
                                    "loop_guard",
                                )
                                return

                        self.loop_guard.record_tool_call(tool_name, parsed_arguments)
                        self.loop_guard.record_operation(tool_name, parsed_arguments)

                        if self.loop_guard.check_stuck_state():
                            self._output_error(
                                "Agent appears stuck. Stopping to prevent infinite loop.",
                                "loop_guard",
                            )
                            return

                        if self.loop_guard.check_repeated_tool_call(tool_name, parsed_arguments):
                            self._output_error(
                                "Same tool called repeatedly. Stopping to prevent infinite loop.",
                                "loop_guard",
                            )
                            return

                else:
                    # No more tools - final response
                    final_text = response_message.get("content", "")
                    reasoning = response_message.get("reasoning_content", "")

                    if final_text:
                        self._output_response({"content": final_text}, is_final=True)
                        return
                    elif reasoning:
                        # Model had reasoning but no content - this can happen with some models
                        # The thinking was already displayed above, so just exit cleanly
                        return
                    else:
                        # Truly empty response - this shouldn't happen
                        self._output_warning("Model returned empty response. Exiting.")
                        return

            except (ModelError, ProviderError) as e:
                import traceback

                self._output_error(str(e), "model_error", {"traceback": traceback.format_exc()})
                return
            except Exception as e:
                import traceback

                self._output_error(str(e), "error", {"traceback": traceback.format_exc()})
                return

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get current conversation history"""
        return self.conversation.get_history()

    def clear_conversation(self) -> None:
        """Clear conversation history"""
        self.conversation.clear(keep_system=True)
        # Update system prompt
        self.conversation.history[0]["content"] = self._get_system_prompt()
