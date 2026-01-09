"""Main Cortex class"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .models import PermissionMode
from .config import AgentConfig
from .core.conversation import ConversationManager
from .core.streaming import stream_model_response, display_streaming_response
from .core.providers import ProviderFactory, ProviderError
from .core.security import SecurityError
from .core.loop_guards import LoopGuard
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

        # Initialize conversation manager
        system_prompt = self._get_system_prompt()
        warn_on_truncation = self.config.session_retention.get("warn_on_truncation", True)
        self.conversation = ConversationManager(
            system_prompt=system_prompt,
            max_tokens=self.config.max_tokens,
            keep_recent=self.config.keep_recent_messages,
            model=self.model,
            warn_on_truncation=warn_on_truncation,
            on_truncation=self._on_context_truncation
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
            recovery_manager=recovery_manager
        )

        # Initialize timeout configuration
        self._timeout_config = self.config.get_timeout_config()

        # Initialize model provider
        provider_override = getattr(self.config, 'provider', None)
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
            provider_override = provider_override or getattr(self.config, 'provider', None)
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
        """Generate system prompt for the agent"""
        mode_instructions = {
            PermissionMode.NORMAL: "Ask for user approval before making changes.",
            PermissionMode.AUTO_APPROVE: "You can make changes without asking. Be careful!",
            PermissionMode.PLAN: "You are in PLAN MODE - read-only. Do not write files or execute commands. Only analyze and create plans."
        }
        
        return f"""You are a helpful coding assistant working in the directory: {self.project_dir}

Permission Mode: {self.permission_mode.upper()}
{mode_instructions[self.permission_mode]}

Project Context:
{self.project_context if self.project_context else "No project context file found."}

## Your Role and Decision-Making

You are an intelligent assistant that understands user intent and responds appropriately. You must reason about what the user wants before deciding whether to use tools or respond conversationally.

### Understanding User Intent

Before using any tools, ask yourself:
1. What is the user actually asking for?
2. Is this a conversational interaction (greeting, question, clarification)?
3. Does this require an action (reading files, running commands, modifying code)?
4. Can I answer this from context, or do I need to use tools?

### Decision Framework

**Respond conversationally (NO TOOLS) when:**
- User greets you: "hey", "hi", "hello"
- User asks general questions: "what can you do?", "how are you?"
- User acknowledges or clarifies: "thanks", "got it", "what do you mean?"
- User asks questions you can answer from context or general knowledge
- The request is ambiguous and needs clarification

**Use tools when:**
- User explicitly requests file operations: "read file.py", "show me the code in X"
- User requests commands: "install dependencies", "run tests", "git status"
- User requests code changes: "add a function", "fix this bug", "refactor X"
- User requests searches: "find where X is used", "list Python files"
- You need to read code to answer a question about the codebase

### Examples of Correct Behavior

**Example 1: Greeting**
User: "hey"
Your reasoning: This is a greeting. I should respond conversationally and ask how I can help. No tools needed.
Your response: "Hello! How can I help you with your coding project today?"
→ NO TOOLS

**Example 2: Simple Question**
User: "what can you do?"
Your reasoning: This is a general question about my capabilities. I can answer from my knowledge. No tools needed.
Your response: "I can help you read and write files, run commands, search code, manage git, and run tests. What would you like to do?"
→ NO TOOLS

**Example 3: Action Request**
User: "read the README file"
Your reasoning: User explicitly wants to read a file. I need to use the read_file tool.
Your action: Call read_file tool with path="README.md"
→ USE TOOL

**Example 4: Ambiguous Request**
User: "what's in the project?"
Your reasoning: This could mean many things. I should ask for clarification rather than guessing.
Your response: "I can help you explore the project. Would you like me to read the README, list files, or search for something specific?"
→ NO TOOLS (ask for clarification first)

**Example 5: Clear Action**
User: "install the dependencies"
Your reasoning: User explicitly wants to run a command. I need to use execute_command tool.
Your action: Call execute_command tool with command="pip install -r requirements.txt" and reason="User requested to install dependencies"
→ USE TOOL

**Example 6: Question Requiring Code Reading**
User: "what does the main function do?"
Your reasoning: To answer this, I need to read the code. I should use read_file to find and read the main function.
Your action: First search_files to find where main is defined, then read_file to read it
→ USE TOOLS

### Guidelines for Tool Usage

1. **Think before acting**: Always reason about user intent before using tools
2. **Be conversational**: For greetings, simple questions, and casual conversation, respond naturally without tools
3. **Read before writing**: ALWAYS read relevant files before making changes
4. **Explain your plan**: Before executing multiple steps, explain what you'll do
5. **Ask when unclear**: If user intent is ambiguous, ask for clarification rather than guessing
6. **Complete tasks fully**: When the task is complete, give a final summary without calling more tools
7. **Use search wisely**: Use search_files to find relevant code when you don't know the file structure
8. **NEVER use tools for greetings or simple conversational exchanges**

### Error Handling

Tool results have a "success" field (true/false):
- If "success" is false, check "error_type" and "retryable" fields:
  * "permission" (retryable: false): Permission denied - do NOT retry, inform user
  * "not_found" (retryable: false): Resource not found - try alternative approach
  * "validation" (retryable: true): Invalid input - retry with corrected input
  * "execution" or "timeout" (retryable: true): Operation failed - may retry once
  * "security" (retryable: false): Security violation - do NOT retry
- If "retryable" is true and error occurred once, you may retry with modifications
- If same error occurs 3 times, stop and explain the issue to the user
- If "permission_denied" is true, this is a permission issue, not an error
- If tool result doesn't have expected structure, ask for clarification

### Task Completion

When you have completed the user's request:
1. Provide a clear summary of what was accomplished
2. Do NOT call additional tools unless the user requests more changes
3. Use a completion signal in your response (e.g., "Task completed", "Done", "Finished")

If the user's request is ambiguous or incomplete:
1. Ask for clarification
2. Propose a plan before executing
3. Wait for confirmation before proceeding

### Available Tools

You have access to these tools:
- read_file: Read file contents
- write_file: Write or overwrite files
- execute_command: Run shell commands
- list_files: List files in directories
- search_files: Search for text across files
- git_status, git_diff, git_commit, git_log: Git operations
- run_tests: Execute test suites

Remember: Use tools only when necessary. For conversational interactions, respond naturally without tools."""

    def _dispatch_session_start(self) -> None:
        """Dispatch session start event to hooks."""
        event = SessionStartEvent(
            model=self.model,
            project_dir=str(self.project_dir),
            permission_mode=self.permission_mode,
            config={
                "max_iterations": self.config.max_iterations,
                "max_tokens": self.config.max_tokens,
            }
        )
        self.hook_manager.dispatch(event)

    def _dispatch_session_end(self) -> None:
        """Dispatch session end event to hooks."""
        event = SessionEndEvent(
            model=self.model,
            project_dir=str(self.project_dir),
            messages_count=len(self.conversation.get_history()),
            tools_used=list(set(self._tools_used))
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

    def _output_error(self, error: str, error_type: str = "error", context: Optional[Dict[str, Any]] = None) -> None:
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
    def _call_model(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call model via provider with retry logic"""
        try:
            # Normalize model name for provider
            normalized_model = self.provider.normalize_model_name(self.model)
            return self.provider.chat(
                model=normalized_model,
                messages=messages,
                tools=tools
            )
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
                    {"tool_name": tool_name}
                )

        # Dispatch PreToolUse hook
        pre_event = PreToolUseEvent(
            tool_name=tool_name,
            arguments=arguments,
            permission_mode=self.permission_mode
        )
        pre_result = self.hook_manager.dispatch(pre_event)

        # Handle hook actions
        if pre_result.action == HookAction.ABORT:
            return create_error_response(
                pre_result.message or "Blocked by hook",
                ErrorType.PERMISSION,
                {"tool_name": tool_name, "blocked_by": "hook"}
            )
        elif pre_result.action == HookAction.SKIP:
            return {
                "success": True,
                "skipped": True,
                "reason": pre_result.message or "Skipped by hook"
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
                timeout_config=self._timeout_config
            )

            # Execute tool
            result = tool.execute(**arguments)
            success = result.get("success", False)

        except ValueError as e:
            result = create_error_response(
                f"Unknown tool: {tool_name}",
                ErrorType.VALIDATION,
                {"tool_name": tool_name}
            )
        except SecurityError as e:
            result = create_error_response(
                str(e),
                ErrorType.SECURITY,
                {"tool_name": tool_name}
            )
        except Exception as e:
            result = create_error_response(
                str(e),
                ErrorType.EXECUTION,
                {"tool_name": tool_name}
            )

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Dispatch PostToolUse hook
        post_event = PostToolUseEvent(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            duration_ms=duration_ms
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
            
            # Note: Session saving is handled by CLI layer if needed
            # This cleanup focuses on internal state
            
        except Exception as e:
            # Don't raise exceptions during cleanup
            logger = logging.getLogger(__name__)
            logger.warning(f"Error during cleanup: {e}")
    
    def _process_message(self, user_message: str, use_streaming: bool = False):
        """Process a user message through the agent loop with hook support."""

        # Check for shutdown request
        if self._shutdown_requested:
            return

        # Dispatch UserPromptSubmit hook
        prompt_event = UserPromptSubmitEvent(
            prompt=user_message,
            conversation_length=len(self.conversation.get_history())
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

        # Agent loop
        max_iterations = self.config.max_iterations

        for iteration in range(max_iterations):
            # Check for shutdown request
            if self._shutdown_requested:
                self._output_warning("Shutdown requested. Cleaning up...")
                self._cleanup()
                return
            
            self.loop_guard.increment_iteration()
            console.print(f"[dim]{'─' * 60}[/dim]")
            
            try:
                # Get conversation history
                messages = self.conversation.get_history()
                
                # Show thinking indicator
                with console.status("[cyan]🤔 Thinking...[/cyan]", spinner="dots"):
                    if use_streaming and stream_model_response and self.provider.supports_streaming():
                        # Streaming mode
                        normalized_model = self.provider.normalize_model_name(self.model)
                        stream = stream_model_response(
                            self.provider,
                            normalized_model,
                            messages,
                            TOOLS
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
                    reasoning_content=response_message.get("reasoning_content")
                )
                
                # Check if using tools
                if response_message.get("tool_calls"):
                    # Don't display content here if tools are present - wait for final response
                    # Execute tools
                    for tool_call in response_message["tool_calls"]:
                        # Check for shutdown request before each tool
                        if self._shutdown_requested:
                            self._output_warning("Shutdown requested. Stopping tool execution...")
                            self._cleanup()
                            return
                        
                        tool_name = tool_call["function"]["name"]
                        arguments = tool_call["function"]["arguments"]
                        
                        # Parse arguments to dict if it's a JSON string (for loop guards)
                        parsed_arguments = arguments
                        if isinstance(arguments, str):
                            try:
                                parsed_arguments = json.loads(arguments)
                            except json.JSONDecodeError:
                                parsed_arguments = {}  # Fallback to empty dict if parsing fails
                        
                        # Execute (execute_tool handles string parsing internally)
                        result = self.execute_tool(tool_name, arguments)
                        
                        # Output tool result (for JSON modes)
                        self._output_tool_result(tool_name, result)

                        # Validate result
                        if not self._validate_tool_result(tool_name, result):
                            self._output_warning(f"Invalid tool result format from {tool_name}")
                            result = create_error_response(
                                "Tool returned invalid result format",
                                ErrorType.EXECUTION,
                                {"tool_name": tool_name}
                            )
                        
                        # Add result to conversation first (before recovery handling)
                        tool_call_id = tool_call.get("id", f"call_{iteration}")
                        self.conversation.add_tool_result(tool_call_id, result)
                        
                        # Check loop guards
                        if not self._is_tool_result_success(result):
                            self.loop_guard.record_error(result)
                            if self.loop_guard.check_repeated_error(result):
                                # Try recovery if enabled
                                recovery_action = self.loop_guard.get_recovery_action(
                                    result, tool_name, parsed_arguments
                                )
                                if recovery_action:
                                    from .core.recovery import RecoveryStrategy
                                    if recovery_action.strategy != RecoveryStrategy.ESCALATE:
                                        # Inject recovery suggestion and continue
                                        self._output_warning(
                                            f"Recovery triggered: {recovery_action.message}"
                                        )
                                        if recovery_action.suggested_prompt:
                                            # Add recovery guidance as additional context
                                            # The original tool result was already added above
                                            self.conversation.add_user_message(
                                                f"[Recovery Guidance] {recovery_action.suggested_prompt}"
                                            )
                                        continue  # Continue loop to let model try recovery
                                # No recovery or escalate - stop
                                self._output_error("Repeated error detected. Stopping to prevent infinite loop.", "loop_guard")
                                return

                        # Use parsed_arguments for loop guards (must be dict)
                        self.loop_guard.record_tool_call(tool_name, parsed_arguments)
                        self.loop_guard.record_operation(tool_name, parsed_arguments)

                        # Check stuck state
                        if self.loop_guard.check_stuck_state():
                            self._output_error("Agent appears stuck. Stopping to prevent infinite loop.", "loop_guard")
                            return

                        if self.loop_guard.check_repeated_tool_call(tool_name, parsed_arguments):
                            self._output_error("Same tool called repeatedly. Stopping to prevent infinite loop.", "loop_guard")
                            return
                        
                        # Note: Tool result is already added to conversation above (before recovery handling)
                else:
                    # No more tools - final response
                    final_text = response_message.get("content", "")

                    if final_text:
                        self._output_response({"content": final_text}, is_final=True)
                        return
                    else:
                        # Empty response - this shouldn't happen, but handle gracefully
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

        self._output_warning("Reached maximum iterations")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get current conversation history"""
        return self.conversation.get_history()
    
    def clear_conversation(self) -> None:
        """Clear conversation history"""
        self.conversation.clear(keep_system=True)
        # Update system prompt
        self.conversation.history[0]["content"] = self._get_system_prompt()

