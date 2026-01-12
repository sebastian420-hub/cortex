# Phase 3: Code Refactoring Specifications

## Overview

This document contains specifications for refactoring the Cortex codebase to improve maintainability, type safety, and code organization.

---

## 3.1 Extract System Prompt Builder

### Purpose

Move the 130+ line system prompt generation from `agent.py` to a dedicated module, making it configurable and easier to maintain.

### Current State

```python
# In agent.py - _get_system_prompt() is 130+ lines
def _get_system_prompt(self) -> str:
    """Generate system prompt for the agent"""
    mode_instructions = {...}
    return f"""You are a helpful coding assistant...
    # 130+ lines of prompt template
    """
```

### Target Architecture

```
cortex/core/
├── system_prompt.py      # New: SystemPromptBuilder
├── prompt_templates/     # New: Template files (optional)
│   ├── base.txt
│   ├── tools.txt
│   └── examples.txt
```

### System Prompt Builder

```python
# cortex/core/system_prompt.py

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
from enum import Enum


class PromptSection(Enum):
    """Sections of the system prompt"""
    IDENTITY = "identity"
    PERMISSION_MODE = "permission_mode"
    PROJECT_CONTEXT = "project_context"
    DECISION_FRAMEWORK = "decision_framework"
    TOOL_USAGE = "tool_usage"
    ERROR_HANDLING = "error_handling"
    TASK_COMPLETION = "task_completion"
    AVAILABLE_TOOLS = "available_tools"
    CUSTOM = "custom"


@dataclass
class PromptConfig:
    """Configuration for prompt generation"""
    include_examples: bool = True
    include_tool_list: bool = True
    include_error_handling: bool = True
    max_project_context_chars: int = 2000
    custom_instructions: Optional[str] = None


class SystemPromptBuilder:
    """
    Builds system prompts for the agent.

    Features:
    - Modular prompt sections
    - Configurable content
    - Template support
    - Context injection
    """

    def __init__(
        self,
        project_dir: Path,
        permission_mode: str,
        project_context: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        config: Optional[PromptConfig] = None
    ):
        self.project_dir = project_dir
        self.permission_mode = permission_mode
        self.project_context = project_context
        self.tools = tools or []
        self.config = config or PromptConfig()

        # Section builders
        self._section_builders = {
            PromptSection.IDENTITY: self._build_identity,
            PromptSection.PERMISSION_MODE: self._build_permission_mode,
            PromptSection.PROJECT_CONTEXT: self._build_project_context,
            PromptSection.DECISION_FRAMEWORK: self._build_decision_framework,
            PromptSection.TOOL_USAGE: self._build_tool_usage,
            PromptSection.ERROR_HANDLING: self._build_error_handling,
            PromptSection.TASK_COMPLETION: self._build_task_completion,
            PromptSection.AVAILABLE_TOOLS: self._build_available_tools,
        }

    def build(
        self,
        sections: Optional[List[PromptSection]] = None,
        exclude: Optional[List[PromptSection]] = None
    ) -> str:
        """
        Build the complete system prompt.

        Args:
            sections: Specific sections to include (default: all)
            exclude: Sections to exclude

        Returns:
            Complete system prompt string
        """
        if sections is None:
            sections = list(PromptSection)

        if exclude:
            sections = [s for s in sections if s not in exclude]

        parts = []
        for section in sections:
            if section == PromptSection.CUSTOM:
                if self.config.custom_instructions:
                    parts.append(self.config.custom_instructions)
            elif section in self._section_builders:
                content = self._section_builders[section]()
                if content:
                    parts.append(content)

        return "\n\n".join(parts)

    def _build_identity(self) -> str:
        """Build identity section"""
        return f"""You are a helpful coding assistant working in the directory: {self.project_dir}"""

    def _build_permission_mode(self) -> str:
        """Build permission mode section"""
        mode_instructions = {
            "normal": "Ask for user approval before making changes.",
            "auto_approve": "You can make changes without asking. Be careful!",
            "plan": "You are in PLAN MODE - read-only. Do not write files or execute commands. Only analyze and create plans."
        }

        instruction = mode_instructions.get(
            self.permission_mode.lower(),
            mode_instructions["normal"]
        )

        return f"""Permission Mode: {self.permission_mode.upper()}
{instruction}"""

    def _build_project_context(self) -> str:
        """Build project context section"""
        if not self.project_context:
            return "Project Context:\nNo project context file found."

        truncated = self.project_context[:self.config.max_project_context_chars]
        if len(self.project_context) > self.config.max_project_context_chars:
            truncated += "\n... (truncated)"

        return f"""Project Context:
{truncated}"""

    def _build_decision_framework(self) -> str:
        """Build decision framework section"""
        return """## Your Role and Decision-Making

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
- You need to read code to answer a question about the codebase"""

    def _build_tool_usage(self) -> str:
        """Build tool usage guidelines"""
        if not self.config.include_examples:
            return """### Guidelines for Tool Usage

1. **Think before acting**: Always reason about user intent before using tools
2. **Be conversational**: For greetings and simple questions, respond naturally without tools
3. **Read before writing**: ALWAYS read relevant files before making changes
4. **Explain your plan**: Before executing multiple steps, explain what you'll do
5. **Ask when unclear**: If user intent is ambiguous, ask for clarification
6. **Complete tasks fully**: When done, give a final summary without calling more tools
7. **NEVER use tools for greetings or simple conversational exchanges**"""

        return """### Examples of Correct Behavior

**Example 1: Greeting**
User: "hey"
Your reasoning: This is a greeting. I should respond conversationally and ask how I can help. No tools needed.
Your response: "Hello! How can I help you with your coding project today?"
→ NO TOOLS

**Example 2: Simple Question**
User: "what can you do?"
Your reasoning: This is a general question about my capabilities. I can answer from my knowledge. No tools needed.
Your response: "I can help you read and write files, run commands, search code, manage git, and run tests."
→ NO TOOLS

**Example 3: Action Request**
User: "read the README file"
Your reasoning: User explicitly wants to read a file. I need to use the read_file tool.
Your action: Call read_file tool with path="README.md"
→ USE TOOL

**Example 4: Ambiguous Request**
User: "what's in the project?"
Your reasoning: This could mean many things. I should ask for clarification.
Your response: "I can help you explore the project. Would you like me to read the README, list files, or search for something specific?"
→ NO TOOLS (ask for clarification first)

### Guidelines for Tool Usage

1. **Think before acting**: Always reason about user intent before using tools
2. **Be conversational**: For greetings and simple questions, respond naturally without tools
3. **Read before writing**: ALWAYS read relevant files before making changes
4. **Explain your plan**: Before executing multiple steps, explain what you'll do
5. **Ask when unclear**: If user intent is ambiguous, ask for clarification
6. **Complete tasks fully**: When done, give a final summary without calling more tools
7. **NEVER use tools for greetings or simple conversational exchanges**"""

    def _build_error_handling(self) -> str:
        """Build error handling section"""
        if not self.config.include_error_handling:
            return ""

        return """### Error Handling

Tool results have a "success" field (true/false):
- If "success" is false, check "error_type" and "retryable" fields:
  * "permission" (retryable: false): Permission denied - do NOT retry, inform user
  * "not_found" (retryable: false): Resource not found - try alternative approach
  * "validation" (retryable: true): Invalid input - retry with corrected input
  * "execution" or "timeout" (retryable: true): Operation failed - may retry once
  * "security" (retryable: false): Security violation - do NOT retry
- If "retryable" is true and error occurred once, you may retry with modifications
- If same error occurs 3 times, stop and explain the issue to the user
- If "permission_denied" is true, this is a permission issue, not an error"""

    def _build_task_completion(self) -> str:
        """Build task completion section"""
        return """### Task Completion

When you have completed the user's request:
1. Provide a clear summary of what was accomplished
2. Do NOT call additional tools unless the user requests more changes
3. Use a completion signal in your response (e.g., "Task completed", "Done", "Finished")

If the user's request is ambiguous or incomplete:
1. Ask for clarification
2. Propose a plan before executing
3. Wait for confirmation before proceeding"""

    def _build_available_tools(self) -> str:
        """Build available tools section"""
        if not self.config.include_tool_list or not self.tools:
            return ""

        tool_descriptions = []
        for tool in self.tools:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "No description")
            tool_descriptions.append(f"- {name}: {desc}")

        tools_list = "\n".join(tool_descriptions)

        return f"""### Available Tools

You have access to these tools:
{tools_list}

Remember: Use tools only when necessary. For conversational interactions, respond naturally without tools."""

    def add_custom_section(self, content: str) -> 'SystemPromptBuilder':
        """Add custom instructions"""
        if self.config.custom_instructions:
            self.config.custom_instructions += f"\n\n{content}"
        else:
            self.config.custom_instructions = content
        return self

    def with_todo_instructions(self) -> 'SystemPromptBuilder':
        """Add todo tracking instructions"""
        todo_instructions = """## Task Management

Use the todo_write tool to track progress on multi-step tasks:
- Create todos when starting complex tasks (3+ steps)
- Mark tasks as in_progress BEFORE starting work
- Mark tasks as completed IMMEDIATELY after finishing
- Only ONE task should be in_progress at a time"""

        return self.add_custom_section(todo_instructions)

    def with_plan_mode_instructions(self) -> 'SystemPromptBuilder':
        """Add plan mode instructions"""
        plan_instructions = """## Plan Mode

You are currently in PLAN MODE. This means:
- You can ONLY read files and explore the codebase
- You CANNOT write files or execute commands
- Your goal is to create an implementation plan
- When your plan is ready, call exit_plan_mode tool"""

        return self.add_custom_section(plan_instructions)


# Factory function for easy creation
def create_system_prompt(
    project_dir: Path,
    permission_mode: str,
    project_context: str = "",
    tools: Optional[List[Dict]] = None,
    include_examples: bool = True,
    custom_instructions: Optional[str] = None
) -> str:
    """
    Create a system prompt with default settings.

    This is a convenience function for common use cases.
    """
    config = PromptConfig(
        include_examples=include_examples,
        custom_instructions=custom_instructions
    )

    builder = SystemPromptBuilder(
        project_dir=project_dir,
        permission_mode=permission_mode,
        project_context=project_context,
        tools=tools,
        config=config
    )

    return builder.build()
```

### Integration with Agent

```python
# In cortex/agent.py (refactored)

from .core.system_prompt import SystemPromptBuilder, PromptConfig

class Cortex:
    def __init__(self, ...):
        # ... existing init ...

        # Build system prompt using builder
        self._prompt_builder = self._create_prompt_builder()
        system_prompt = self._prompt_builder.build()

        # Initialize conversation manager
        self.conversation = ConversationManager(
            system_prompt=system_prompt,
            # ... other params ...
        )

    def _create_prompt_builder(self) -> SystemPromptBuilder:
        """Create the system prompt builder"""
        from .tools import TOOLS

        config = PromptConfig(
            include_examples=self.config.get("include_examples", True),
            include_tool_list=True,
            max_project_context_chars=2000
        )

        builder = SystemPromptBuilder(
            project_dir=self.project_dir,
            permission_mode=self.permission_mode,
            project_context=self.project_context,
            tools=TOOLS,
            config=config
        )

        # Add optional sections based on config
        if self.config.get("enable_todo_tracking", True):
            builder.with_todo_instructions()

        return builder

    def _get_system_prompt(self) -> str:
        """Get current system prompt (for refresh)"""
        return self._prompt_builder.build()
```

---

## 3.2 Split agent.py

### Purpose

Split the 772-line `agent.py` into smaller, focused modules with clear responsibilities.

### Current Structure

```
agent.py (772 lines)
├── __init__() - 100 lines
├── _get_system_prompt() - 130 lines (extracted to system_prompt.py)
├── _process_message() - 190 lines
├── execute_tool() - 100 lines
├── Helper methods - 150 lines
└── Output methods - 100 lines
```

### Target Structure

```
cortex/
├── agent.py              # ~200 lines - Main orchestration only
├── core/
│   ├── system_prompt.py  # ~200 lines - Prompt generation
│   ├── tool_executor.py  # ~150 lines - Tool execution logic
│   └── message_processor.py  # ~250 lines - Message processing loop
```

### Tool Executor

```python
# cortex/core/tool_executor.py

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json
import time
import logging

from .security import SecurityError
from ..tools import create_tool_instance
from ..hooks import HookManager, HookAction, PreToolUseEvent, PostToolUseEvent
from ..utils.errors import create_error_response, ErrorType

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    """Result of tool execution"""
    tool_name: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]
    success: bool
    duration_ms: float
    skipped: bool = False
    blocked_by_hook: bool = False


class ToolExecutor:
    """
    Handles tool execution with hook support.

    Responsibilities:
    - Parse and validate tool arguments
    - Execute pre-tool hooks
    - Create and execute tool instances
    - Execute post-tool hooks
    - Track tool usage metrics
    """

    def __init__(
        self,
        project_dir: str,
        permission_mode: str,
        console,
        hook_manager: Optional[HookManager] = None,
        timeout_config: Optional[Dict[str, int]] = None,
        parent_agent: Optional['Cortex'] = None
    ):
        self.project_dir = project_dir
        self.permission_mode = permission_mode
        self.console = console
        self.hook_manager = hook_manager or HookManager()
        self.timeout_config = timeout_config or {}
        self.parent_agent = parent_agent

        # Metrics
        self.tools_executed: List[str] = []
        self.total_execution_time_ms: float = 0

    def execute(
        self,
        tool_name: str,
        arguments: Any
    ) -> ToolExecutionResult:
        """
        Execute a tool with full hook support.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments (can be dict or JSON string)

        Returns:
            ToolExecutionResult with execution details
        """
        # Parse arguments
        parsed_args = self._parse_arguments(arguments)
        if parsed_args is None:
            return ToolExecutionResult(
                tool_name=tool_name,
                arguments={},
                result=create_error_response(
                    f"Invalid JSON in tool arguments: {arguments}",
                    ErrorType.VALIDATION,
                    {"tool_name": tool_name}
                ),
                success=False,
                duration_ms=0
            )

        # Execute pre-tool hook
        hook_result = self._execute_pre_hook(tool_name, parsed_args)

        if hook_result.get("abort"):
            return ToolExecutionResult(
                tool_name=tool_name,
                arguments=parsed_args,
                result=create_error_response(
                    hook_result.get("message", "Blocked by hook"),
                    ErrorType.PERMISSION,
                    {"tool_name": tool_name, "blocked_by": "hook"}
                ),
                success=False,
                duration_ms=0,
                blocked_by_hook=True
            )

        if hook_result.get("skip"):
            return ToolExecutionResult(
                tool_name=tool_name,
                arguments=parsed_args,
                result={
                    "success": True,
                    "skipped": True,
                    "reason": hook_result.get("message", "Skipped by hook")
                },
                success=True,
                duration_ms=0,
                skipped=True
            )

        # Apply hook modifications
        if hook_result.get("modified_args"):
            parsed_args = hook_result["modified_args"]
        if hook_result.get("modified_name"):
            tool_name = hook_result["modified_name"]

        # Execute tool
        start_time = time.time()
        result = self._execute_tool(tool_name, parsed_args)
        duration_ms = (time.time() - start_time) * 1000

        success = result.get("success", False)

        # Track metrics
        self.tools_executed.append(tool_name)
        self.total_execution_time_ms += duration_ms

        # Execute post-tool hook
        post_result = self._execute_post_hook(
            tool_name, parsed_args, result, success, duration_ms
        )

        # Apply post-hook modifications
        if post_result.get("modified_result"):
            result = post_result["modified_result"]

        return ToolExecutionResult(
            tool_name=tool_name,
            arguments=parsed_args,
            result=result,
            success=success,
            duration_ms=duration_ms
        )

    def _parse_arguments(self, arguments: Any) -> Optional[Dict[str, Any]]:
        """Parse arguments to dict"""
        if isinstance(arguments, dict):
            return arguments

        if isinstance(arguments, str):
            try:
                return json.loads(arguments)
            except json.JSONDecodeError:
                return None

        return None

    def _execute_pre_hook(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute pre-tool hook"""
        event = PreToolUseEvent(
            tool_name=tool_name,
            arguments=arguments,
            permission_mode=self.permission_mode
        )

        result = self.hook_manager.dispatch(event)

        response = {}

        if result.action == HookAction.ABORT:
            response["abort"] = True
            response["message"] = result.message
        elif result.action == HookAction.SKIP:
            response["skip"] = True
            response["message"] = result.message
        elif result.action == HookAction.MODIFY and result.modified_data:
            response["modified_args"] = result.modified_data.get("arguments")
            response["modified_name"] = result.modified_data.get("tool_name")

        return response

    def _execute_post_hook(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        success: bool,
        duration_ms: float
    ) -> Dict[str, Any]:
        """Execute post-tool hook"""
        event = PostToolUseEvent(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            duration_ms=duration_ms
        )

        hook_result = self.hook_manager.dispatch(event)

        response = {}

        if hook_result.action == HookAction.MODIFY and hook_result.modified_data:
            if "result" in hook_result.modified_data:
                response["modified_result"] = hook_result.modified_data["result"]

        return response

    def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the actual tool"""
        try:
            tool = create_tool_instance(
                tool_name,
                self.project_dir,
                self.permission_mode,
                self.console,
                parent_agent=self.parent_agent,
                timeout_config=self.timeout_config
            )

            return tool.execute(**arguments)

        except ValueError as e:
            return create_error_response(
                f"Unknown tool: {tool_name}",
                ErrorType.VALIDATION,
                {"tool_name": tool_name}
            )
        except SecurityError as e:
            return create_error_response(
                str(e),
                ErrorType.SECURITY,
                {"tool_name": tool_name}
            )
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return create_error_response(
                str(e),
                ErrorType.EXECUTION,
                {"tool_name": tool_name}
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics"""
        return {
            "tools_executed": len(self.tools_executed),
            "unique_tools": len(set(self.tools_executed)),
            "total_execution_time_ms": self.total_execution_time_ms,
            "tool_usage": dict(
                (tool, self.tools_executed.count(tool))
                for tool in set(self.tools_executed)
            )
        }
```

### Message Processor

```python
# cortex/core/message_processor.py

from typing import Dict, Any, Optional, List, Generator, Callable
from dataclasses import dataclass
import json
import logging

from .tool_executor import ToolExecutor, ToolExecutionResult
from .loop_guards import LoopGuard
from .recovery import RecoveryManager, RecoveryStrategy
from .providers import ModelProvider, ProviderError
from .conversation import ConversationManager
from ..utils.errors import ModelError, create_error_response, ErrorType

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of message processing"""
    success: bool
    final_response: Optional[str] = None
    iterations: int = 0
    tool_calls: int = 0
    stopped_reason: Optional[str] = None
    error: Optional[str] = None


class MessageProcessor:
    """
    Processes user messages through the agent loop.

    Responsibilities:
    - Run the main agent loop
    - Handle model calls
    - Route tool executions
    - Apply loop guards
    - Handle error recovery
    """

    def __init__(
        self,
        provider: ModelProvider,
        model: str,
        conversation: ConversationManager,
        tool_executor: ToolExecutor,
        loop_guard: LoopGuard,
        tools: List[Dict[str, Any]],
        config: Dict[str, Any],
        on_output: Optional[Callable[[str, str], None]] = None,
        on_tool_result: Optional[Callable[[str, Dict], None]] = None
    ):
        self.provider = provider
        self.model = model
        self.conversation = conversation
        self.tool_executor = tool_executor
        self.loop_guard = loop_guard
        self.tools = tools
        self.config = config
        self.on_output = on_output
        self.on_tool_result = on_tool_result

        self.max_iterations = config.get("max_iterations", 20)
        self._shutdown_requested = False

    def request_shutdown(self) -> None:
        """Request graceful shutdown"""
        self._shutdown_requested = True

    def process(
        self,
        user_message: str,
        use_streaming: bool = False,
        on_max_iterations: Optional[Callable[[int, int], Optional[int]]] = None
    ) -> ProcessingResult:
        """
        Process a user message through the agent loop.

        Args:
            user_message: The user's message
            use_streaming: Whether to use streaming responses
            on_max_iterations: Callback when max iterations reached

        Returns:
            ProcessingResult with outcome details
        """
        # Add user message to conversation
        self.conversation.add_user_message(user_message)

        max_iterations = self.max_iterations
        iteration = 0
        tool_calls = 0

        while True:
            iteration += 1

            # Check shutdown
            if self._shutdown_requested:
                return ProcessingResult(
                    success=False,
                    iterations=iteration,
                    tool_calls=tool_calls,
                    stopped_reason="shutdown_requested"
                )

            # Check iteration limit
            if iteration > max_iterations:
                if on_max_iterations:
                    additional = on_max_iterations(iteration, max_iterations)
                    if additional and additional > 0:
                        max_iterations += additional
                        continue

                return ProcessingResult(
                    success=False,
                    iterations=iteration,
                    tool_calls=tool_calls,
                    stopped_reason="max_iterations"
                )

            # Update loop guard
            self.loop_guard.increment_iteration()

            try:
                # Call model
                response = self._call_model(use_streaming)

                if response is None:
                    return ProcessingResult(
                        success=False,
                        iterations=iteration,
                        tool_calls=tool_calls,
                        stopped_reason="model_error",
                        error="Failed to get model response"
                    )

                # Add assistant message
                self.conversation.add_assistant_message(
                    content=response.get("content", ""),
                    tool_calls=response.get("tool_calls"),
                    reasoning_content=response.get("reasoning_content")
                )

                # Process tool calls
                if response.get("tool_calls"):
                    for tool_call in response["tool_calls"]:
                        if self._shutdown_requested:
                            return ProcessingResult(
                                success=False,
                                iterations=iteration,
                                tool_calls=tool_calls,
                                stopped_reason="shutdown_requested"
                            )

                        result = self._process_tool_call(tool_call, iteration)
                        tool_calls += 1

                        # Check for loop guard violations
                        if result.get("stop"):
                            return ProcessingResult(
                                success=False,
                                iterations=iteration,
                                tool_calls=tool_calls,
                                stopped_reason=result.get("reason", "loop_guard")
                            )

                else:
                    # No tool calls - final response
                    final_text = response.get("content", "")

                    if final_text:
                        if self.on_output:
                            self.on_output("response", final_text)

                        return ProcessingResult(
                            success=True,
                            final_response=final_text,
                            iterations=iteration,
                            tool_calls=tool_calls
                        )
                    else:
                        return ProcessingResult(
                            success=False,
                            iterations=iteration,
                            tool_calls=tool_calls,
                            stopped_reason="empty_response"
                        )

            except (ModelError, ProviderError) as e:
                logger.error(f"Model error: {e}")
                return ProcessingResult(
                    success=False,
                    iterations=iteration,
                    tool_calls=tool_calls,
                    stopped_reason="model_error",
                    error=str(e)
                )
            except Exception as e:
                logger.error(f"Processing error: {e}", exc_info=True)
                return ProcessingResult(
                    success=False,
                    iterations=iteration,
                    tool_calls=tool_calls,
                    stopped_reason="error",
                    error=str(e)
                )

    def _call_model(self, use_streaming: bool) -> Optional[Dict[str, Any]]:
        """Call the model and return response message"""
        try:
            messages = self.conversation.get_history()
            normalized_model = self.provider.normalize_model_name(self.model)

            if use_streaming and self.provider.supports_streaming():
                # Streaming implementation
                from .streaming import stream_model_response, display_streaming_response
                stream = stream_model_response(
                    self.provider,
                    normalized_model,
                    messages,
                    self.tools
                )
                return display_streaming_response(stream)
            else:
                response = self.provider.chat(
                    model=normalized_model,
                    messages=messages,
                    tools=self.tools
                )
                return response.get("message")

        except Exception as e:
            logger.error(f"Model call failed: {e}")
            return None

    def _process_tool_call(
        self,
        tool_call: Dict[str, Any],
        iteration: int
    ) -> Dict[str, Any]:
        """
        Process a single tool call.

        Returns dict with 'stop' key if loop should stop.
        """
        tool_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]

        # Parse arguments for loop guards
        parsed_args = arguments
        if isinstance(arguments, str):
            try:
                parsed_args = json.loads(arguments)
            except json.JSONDecodeError:
                parsed_args = {}

        # Execute tool
        exec_result = self.tool_executor.execute(tool_name, arguments)

        # Notify callback
        if self.on_tool_result:
            self.on_tool_result(tool_name, exec_result.result)

        # Add to conversation
        tool_call_id = tool_call.get("id", f"call_{iteration}")
        self.conversation.add_tool_result(tool_call_id, exec_result.result)

        # Check loop guards
        if not exec_result.success:
            self.loop_guard.record_error(exec_result.result)

            if self.loop_guard.check_repeated_error(exec_result.result):
                # Try recovery
                recovery_action = self.loop_guard.get_recovery_action(
                    exec_result.result, tool_name, parsed_args
                )

                if recovery_action:
                    if recovery_action.strategy != RecoveryStrategy.ESCALATE:
                        if recovery_action.suggested_prompt:
                            self.conversation.add_user_message(
                                f"[Recovery Guidance] {recovery_action.suggested_prompt}"
                            )
                        return {}  # Continue with recovery

                return {"stop": True, "reason": "repeated_error"}

        # Record for loop detection
        self.loop_guard.record_tool_call(tool_name, parsed_args)
        self.loop_guard.record_operation(tool_name, parsed_args)

        if self.loop_guard.check_stuck_state():
            return {"stop": True, "reason": "stuck_state"}

        if self.loop_guard.check_repeated_tool_call(tool_name, parsed_args):
            return {"stop": True, "reason": "repeated_tool_call"}

        return {}
```

### Refactored Agent

```python
# cortex/agent.py (refactored - ~200 lines)

"""Main Cortex agent class"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

from .models import PermissionMode
from .config import AgentConfig
from .core.conversation import ConversationManager
from .core.system_prompt import SystemPromptBuilder, PromptConfig
from .core.tool_executor import ToolExecutor
from .core.message_processor import MessageProcessor, ProcessingResult
from .core.providers import ProviderFactory, ProviderError
from .core.loop_guards import LoopGuard
from .tools import TOOLS
from .hooks import HookManager, SessionStartEvent, SessionEndEvent
from .output import OutputFormat, create_formatter
from .ui.console import console

logger = logging.getLogger(__name__)


class Cortex:
    """
    Main Cortex agent class.

    Orchestrates conversation flow, tool execution, and session management.
    """

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

        # Initialize components
        self.hook_manager = hook_manager or HookManager()
        self.output_format = output_format
        self.formatter = create_formatter(output_format, console=console)

        # Load project context
        self.project_context = self._load_project_context()

        # Initialize provider
        self.provider = self._init_provider()

        # Build system prompt
        self._prompt_builder = self._create_prompt_builder()

        # Initialize conversation
        self.conversation = ConversationManager(
            system_prompt=self._prompt_builder.build(),
            max_tokens=self.config.max_tokens,
            keep_recent=self.config.keep_recent_messages,
            model=self.model
        )

        # Initialize tool executor
        self.tool_executor = ToolExecutor(
            project_dir=str(self.project_dir),
            permission_mode=permission_mode,
            console=console,
            hook_manager=self.hook_manager,
            timeout_config=self.config.get_timeout_config(),
            parent_agent=self
        )

        # Initialize loop guard
        self.loop_guard = self._create_loop_guard()

        # Initialize message processor
        self.message_processor = MessageProcessor(
            provider=self.provider,
            model=self.model,
            conversation=self.conversation,
            tool_executor=self.tool_executor,
            loop_guard=self.loop_guard,
            tools=TOOLS,
            config={"max_iterations": self.config.max_iterations},
            on_output=self._handle_output,
            on_tool_result=self._handle_tool_result
        )

        self._on_max_iterations_reached = on_max_iterations_reached
        self._shutdown_requested = False

        # Dispatch session start
        self._dispatch_session_start()

    def _init_provider(self):
        """Initialize model provider"""
        provider_override = getattr(self.config, 'provider', None)
        try:
            provider = ProviderFactory.get_provider(self.model, provider_override)
            if not provider.validate_api_key():
                raise ProviderError(
                    f"API key not set for {ProviderFactory.get_provider_name(self.model)}"
                )
            return provider
        except ProviderError as e:
            raise ProviderError(f"Failed to initialize provider: {e}") from e

    def _create_prompt_builder(self) -> SystemPromptBuilder:
        """Create system prompt builder"""
        config = PromptConfig(
            include_examples=True,
            include_tool_list=True
        )
        return SystemPromptBuilder(
            project_dir=self.project_dir,
            permission_mode=self.permission_mode,
            project_context=self.project_context,
            tools=TOOLS,
            config=config
        )

    def _create_loop_guard(self) -> LoopGuard:
        """Create loop guard with recovery if enabled"""
        recovery_manager = None
        if self.config.error_recovery.get("enable_smart_recovery", False):
            from .core.recovery import create_recovery_manager_from_config
            recovery_manager = create_recovery_manager_from_config(
                self.config.error_recovery
            )

        return LoopGuard(
            max_repeats=self.config.error_recovery.get("max_repeats", 3),
            stuck_threshold=self.config.error_recovery.get("stuck_threshold", 5),
            recovery_manager=recovery_manager
        )

    def _load_project_context(self) -> str:
        """Load project context from AGENT.md, CLAUDE.md, or README.md"""
        for filename in ["AGENT.md", "CLAUDE.md", "README.md"]:
            filepath = self.project_dir / filename
            if filepath.exists():
                try:
                    content = filepath.read_text()
                    console.print(f"[dim]Loaded context from {filename}[/dim]")
                    return content[:2000]
                except Exception:
                    pass
        return ""

    def process_message(self, user_message: str, use_streaming: bool = False) -> None:
        """Process a user message"""
        result = self.message_processor.process(
            user_message,
            use_streaming=use_streaming,
            on_max_iterations=self._on_max_iterations_reached
        )

        if not result.success:
            self._handle_processing_failure(result)

    def _handle_output(self, output_type: str, content: str) -> None:
        """Handle output from message processor"""
        if self.output_format == OutputFormat.TEXT:
            from rich.markdown import Markdown
            console.print(Markdown(content))
        else:
            formatted = self.formatter.format_response({"content": content})
            self.formatter.write(formatted)

    def _handle_tool_result(self, tool_name: str, result: Dict[str, Any]) -> None:
        """Handle tool result from message processor"""
        if self.output_format != OutputFormat.TEXT:
            formatted = self.formatter.format_tool_result(tool_name, result)
            self.formatter.write(formatted)

    def _handle_processing_failure(self, result: ProcessingResult) -> None:
        """Handle processing failure"""
        if result.stopped_reason == "max_iterations":
            console.print("[yellow]Reached maximum iterations[/yellow]")
        elif result.stopped_reason == "shutdown_requested":
            console.print("[yellow]Shutdown requested[/yellow]")
        elif result.error:
            console.print(f"[red]Error:[/red] {result.error}")

    def switch_model(self, new_model: str, provider_override: Optional[str] = None) -> None:
        """Switch to a different model"""
        if new_model == self.model:
            return

        try:
            new_provider = ProviderFactory.get_provider(
                new_model,
                provider_override or getattr(self.config, 'provider', None)
            )
            if not new_provider.validate_api_key():
                raise ProviderError(f"API key not set")

            old_model = self.model
            self.model = new_model
            self.provider = new_provider
            self.conversation.update_model(new_model)
            self.message_processor.model = new_model
            self.message_processor.provider = new_provider

            console.print(f"[cyan]Switched model:[/cyan] {old_model} → {new_model}")

        except ProviderError as e:
            console.print(f"[red]Failed to switch model:[/red] {e}")
            raise

    def request_shutdown(self) -> None:
        """Request graceful shutdown"""
        self._shutdown_requested = True
        self.message_processor.request_shutdown()

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.conversation.get_history()

    def clear_conversation(self) -> None:
        """Clear conversation history"""
        self.conversation.clear(keep_system=True)
        self.conversation.history[0]["content"] = self._prompt_builder.build()

    def _dispatch_session_start(self) -> None:
        """Dispatch session start event"""
        event = SessionStartEvent(
            model=self.model,
            project_dir=str(self.project_dir),
            permission_mode=self.permission_mode,
            config={"max_iterations": self.config.max_iterations}
        )
        self.hook_manager.dispatch(event)

    def _dispatch_session_end(self) -> None:
        """Dispatch session end event"""
        event = SessionEndEvent(
            model=self.model,
            project_dir=str(self.project_dir),
            messages_count=len(self.conversation.get_history()),
            tools_used=list(set(self.tool_executor.tools_executed))
        )
        self.hook_manager.dispatch(event)
```

---

## 3.3 TypedDict Types

### Purpose

Replace generic `Dict[str, Any]` types with specific TypedDict classes for better type safety and IDE support.

### Type Definitions

```python
# cortex/types.py

from typing import TypedDict, List, Optional, Any, Literal
from typing_extensions import NotRequired


# ============ Tool Types ============

class ToolResult(TypedDict):
    """Standard tool result format"""
    success: bool
    error: NotRequired[str]
    error_type: NotRequired[Literal[
        "permission", "not_found", "validation",
        "execution", "timeout", "security"
    ]]
    retryable: NotRequired[bool]
    permission_denied: NotRequired[bool]
    data: NotRequired[dict]


class ToolCallFunction(TypedDict):
    """Tool call function specification"""
    name: str
    arguments: str  # JSON string


class ToolCall(TypedDict):
    """Tool call from model response"""
    id: str
    type: Literal["function"]
    function: ToolCallFunction


class ToolDefinition(TypedDict):
    """Tool definition for model"""
    type: Literal["function"]
    function: 'FunctionDefinition'


class FunctionDefinition(TypedDict):
    """Function definition in tool"""
    name: str
    description: str
    parameters: dict


# ============ Message Types ============

class SystemMessage(TypedDict):
    """System message"""
    role: Literal["system"]
    content: str


class UserMessage(TypedDict):
    """User message"""
    role: Literal["user"]
    content: str


class AssistantMessage(TypedDict):
    """Assistant message"""
    role: Literal["assistant"]
    content: NotRequired[str]
    tool_calls: NotRequired[List[ToolCall]]
    reasoning_content: NotRequired[str]


class ToolMessage(TypedDict):
    """Tool result message"""
    role: Literal["tool"]
    tool_call_id: str
    content: str


Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage


# ============ Model Response Types ============

class ModelResponseMessage(TypedDict):
    """Message in model response"""
    content: NotRequired[str]
    tool_calls: NotRequired[List[ToolCall]]
    reasoning_content: NotRequired[str]


class ModelResponse(TypedDict):
    """Response from model provider"""
    message: ModelResponseMessage
    done: NotRequired[bool]
    model: NotRequired[str]


# ============ Hook Types ============

class HookResultData(TypedDict):
    """Modified data from hook"""
    tool_name: NotRequired[str]
    arguments: NotRequired[dict]
    prompt: NotRequired[str]
    result: NotRequired[dict]


class HookResult(TypedDict):
    """Result from hook execution"""
    action: Literal["continue", "skip", "modify", "abort"]
    message: NotRequired[str]
    modified_data: NotRequired[HookResultData]


# ============ Session Types ============

class SessionData(TypedDict):
    """Session persistence data"""
    conversation_history: List[Message]
    model: str
    permission_mode: str
    project_dir: str
    timestamp: str
    metadata: NotRequired[dict]


class SessionMetadata(TypedDict):
    """Session metadata"""
    session_id: str
    created_at: str
    updated_at: str
    message_count: int
    tools_used: List[str]


# ============ Config Types ============

class TimeoutConfig(TypedDict):
    """Timeout configuration"""
    default: int
    git: NotRequired[int]
    test: NotRequired[int]
    command: NotRequired[int]


class ErrorRecoveryConfig(TypedDict):
    """Error recovery configuration"""
    enable_smart_recovery: bool
    max_repeats: int
    stuck_threshold: NotRequired[int]
    buffer_size: NotRequired[int]
    recovery_strategy: NotRequired[Literal["suggest", "escalate", "continue"]]


class SessionRetentionConfig(TypedDict):
    """Session retention configuration"""
    max_age_days: int
    max_count: int
    max_total_size_mb: NotRequired[int]
    cleanup_on_startup: NotRequired[bool]
    warn_on_truncation: NotRequired[bool]


# ============ Progress Types ============

class TodoItem(TypedDict):
    """Todo item"""
    content: str
    status: Literal["pending", "in_progress", "completed"]
    activeForm: str


class TodoProgress(TypedDict):
    """Todo progress statistics"""
    total: int
    pending: int
    in_progress: int
    completed: int


# ============ Question Types ============

class QuestionOption(TypedDict):
    """Option for a question"""
    label: str
    description: str


class Question(TypedDict):
    """Structured question"""
    question: str
    header: str
    options: List[QuestionOption]
    multiSelect: NotRequired[bool]


class QuestionAnswer(TypedDict):
    """Answer to a question"""
    header: str
    selected: List[str]
    custom_input: NotRequired[str]
```

### Usage Examples

```python
# Before
def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    ...

# After
from .types import ToolResult

def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
    ...


# Before
def get_history(self) -> List[Dict[str, Any]]:
    ...

# After
from .types import Message

def get_history(self) -> List[Message]:
    ...


# Before
def dispatch(self, event) -> Dict[str, Any]:
    ...

# After
from .types import HookResult

def dispatch(self, event) -> HookResult:
    ...
```

### Benefits

1. **IDE Support**: Better autocomplete and inline documentation
2. **Type Checking**: Catch errors at development time with mypy
3. **Documentation**: Types serve as documentation
4. **Refactoring Safety**: Easier to refactor with type hints

### Migration Strategy

1. Add `types.py` with all TypedDict definitions
2. Update return types in base classes first
3. Run mypy to find type mismatches
4. Update implementations to match types
5. Add type hints to remaining functions

---

## Implementation Checklist

### 3.1 System Prompt Builder
- [ ] Create `cortex/core/system_prompt.py`
- [ ] Implement `SystemPromptBuilder` class
- [ ] Implement all section builders
- [ ] Add `create_system_prompt()` factory function
- [ ] Update `agent.py` to use builder
- [ ] Add unit tests
- [ ] Update documentation

### 3.2 Split agent.py
- [ ] Create `cortex/core/tool_executor.py`
- [ ] Create `cortex/core/message_processor.py`
- [ ] Refactor `agent.py` to use new modules
- [ ] Verify all tests pass
- [ ] Update imports throughout codebase
- [ ] Add integration tests

### 3.3 TypedDict Types
- [ ] Create `cortex/types.py`
- [ ] Define all TypedDict classes
- [ ] Update tool return types
- [ ] Update message types
- [ ] Update hook types
- [ ] Run mypy and fix issues
- [ ] Update documentation

---

## Testing Requirements

```python
# tests/test_system_prompt.py

def test_system_prompt_builder_creates_valid_prompt():
    """Test that builder creates a valid prompt"""
    builder = SystemPromptBuilder(
        project_dir=Path("/test"),
        permission_mode="normal",
        project_context="Test context"
    )
    prompt = builder.build()
    assert "coding assistant" in prompt
    assert "Permission Mode: NORMAL" in prompt


def test_system_prompt_sections_can_be_excluded():
    """Test that sections can be excluded"""
    builder = SystemPromptBuilder(...)
    prompt = builder.build(exclude=[PromptSection.EXAMPLES])
    assert "Example 1:" not in prompt


def test_custom_instructions_are_included():
    """Test that custom instructions are added"""
    builder = SystemPromptBuilder(...)
    builder.add_custom_section("Custom instruction")
    prompt = builder.build()
    assert "Custom instruction" in prompt


# tests/test_tool_executor.py

def test_tool_executor_handles_json_string_args():
    """Test that JSON string arguments are parsed"""
    executor = ToolExecutor(...)
    result = executor.execute("read_file", '{"path": "test.txt"}')
    assert result.arguments == {"path": "test.txt"}


def test_tool_executor_tracks_metrics():
    """Test that metrics are tracked"""
    executor = ToolExecutor(...)
    executor.execute("read_file", {"path": "test.txt"})
    metrics = executor.get_metrics()
    assert metrics["tools_executed"] == 1


# tests/test_types.py

def test_tool_result_type_validates():
    """Test that ToolResult validates correctly"""
    from cortex.types import ToolResult

    # Valid result
    result: ToolResult = {
        "success": True,
        "data": {"content": "test"}
    }

    # This should fail type checking
    # result: ToolResult = {"invalid": "field"}
```

---

## Summary

Phase 3 refactoring provides:

1. **SystemPromptBuilder**: Modular, configurable prompt generation
2. **Split agent.py**: Better separation of concerns
3. **TypedDict types**: Improved type safety and IDE support

These changes make the codebase more maintainable and easier to extend.
