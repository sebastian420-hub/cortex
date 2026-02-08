"""Main Cortex class"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Union
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

logger = logging.getLogger(__name__)

# Platform-specific spinner (Windows cp1252 can't handle Unicode Braille)
SPINNER_TYPE = "line" if sys.platform == "win32" else "dots"

from .models import PermissionMode
from .config import AgentConfig
from .core.conversation import ConversationManager
from .core.parallel import ParallelToolExecutor, ToolCall
from .core.streaming import stream_model_response, display_streaming_response
from .core.providers import ProviderFactory, ProviderError
from .core.rate_limiter import get_rate_limiter, RateLimitConfig
from .cache.file_cache import get_file_cache

# Import routing system (optional, gracefully handle if not available)
try:
    from .core.routing import (
        RoutingOrchestrator,
        RoutingConfig,
        RoutingContext,
        RoutingDecision,
        get_orchestrator,
    )
    ROUTING_AVAILABLE = True
except ImportError:
    ROUTING_AVAILABLE = False
    RoutingOrchestrator = None
    RoutingConfig = None
    RoutingContext = None
    RoutingDecision = None
from .core.security import SecurityError
from .core.loop_guards import LoopGuard
from .core.orchestration import (
    OrchestrationManager,
    DelegationTracker,
    DelegationContext,
    get_orchestration_manager,
)
from .core.models import get_model_registry, ModelRegistry
from .core.prompts import get_prompt_profile, get_delegation_instructions
from .core.recovery import (
    CheckpointManager,
    SessionHealthMonitor,
    RecoveryOrchestrator,
)
# New modular components
from .core.agent_init import AgentInitializer
from .core.agent_prompts import PromptGenerator
from .core.agent_permissions import PermissionManager
from .core.agent_tools import ToolExecutor
from .core.agent_messaging import MessageProcessor
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
from .core.memory_layers import StateManager, AgentFocus
from .core.prompt_adapter import get_profile_info
from .core.prompts import adapt_prompt_for_model
from .tools import TOOLS, create_tool_instance, get_registry
from .ui.console import console
from .ui.consolidated_display import get_consolidated_display, create_consolidated_console, OperationStatus
from .utils.errors import retry_with_backoff, ModelError, create_error_response, create_success_response, ErrorType

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
from .utils.result_truncation import truncate_tool_result, should_truncate_proactively

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
        """Initialize Cortex agent with all components."""
        # Basic setup
        self.model = model
        self.project_dir = Path(project_dir).resolve()
        self.permission_mode = permission_mode
        self.config = config or AgentConfig()
        self.session_start = datetime.now()
        self.hook_manager = hook_manager or HookManager()
        self.output_format = output_format

        # Use AgentInitializer to handle complex initialization
        initializer = AgentInitializer(
            model=model,
            project_dir=self.project_dir,
            permission_mode=permission_mode,
            config=self.config,
            hook_manager=self.hook_manager,
            output_format=output_format,
        )

        # Copy initialized components from initializer
        self.history_dir = initializer.history_dir
        self.memory_bank = initializer.memory_bank
        self.state_manager = initializer.state_manager
        self.conversation = initializer.conversation
        self.checkpoint_manager = initializer.checkpoint_manager
        self.health_monitor = initializer.health_monitor
        self.recovery_orchestrator = initializer.recovery_orchestrator
        self.loop_guard = initializer.loop_guard
        self.rate_limiter = initializer.rate_limiter
        self.rate_limiter_enabled = initializer.is_rate_limiting_enabled()
        self._timeout_config = initializer.timeout_config
        self.file_cache = initializer.file_cache
        self.provider = initializer.provider
        self.router = initializer.router
        self._routing_enabled = initializer.is_routing_enabled()
        self.tool_registry = initializer.tool_registry
        self.formatter = initializer.formatter

        # Orchestration system
        self._orchestration_enabled = initializer.orchestration_enabled
        self._model_registry = initializer.model_registry
        self._delegation_tracker = initializer.delegation_tracker
        self._delegation_context = initializer.delegation_context
        self._orchestration = initializer.orchestration

        # Initialize parallel executor (needs self.execute_tool, so done after initializer)
        parallel_config = self.config.get_parallel_execution_config()
        max_workers = parallel_config.get("max_workers", 0)
        if max_workers == 0 or max_workers == "auto":
            import os
            max_workers = min(4, os.cpu_count() or 2)
        self.parallel_executor = ParallelToolExecutor(
            execute_fn=self.execute_tool,
            max_workers=max_workers,
            enabled=parallel_config.get("enabled", True),
            batch_size=parallel_config.get("batch_size", 10),
        )

        # Initialize new modular components
        self.prompt_generator = PromptGenerator(self)
        self.permission_manager = PermissionManager(self)
        self.tool_executor = ToolExecutor(self)
        self.message_processor = MessageProcessor(self)

        # Update conversation system prompt now that PromptGenerator is ready
        self.project_context = self.prompt_generator.load_project_context()
        system_prompt = self.prompt_generator.generate()
        self.conversation.system_prompt = system_prompt
        self.conversation.on_truncation = self._on_context_truncation

        # Track tools used in session (for metrics)
        self._tools_used: List[str] = []

        # Shutdown flag for graceful termination
        self._shutdown_requested = False
        self._session_dirty = False

        # Interrupt handling
        self._is_processing = False
        self._interrupt_requested = False

        # Display settings
        self.show_thinking = False

        # Set default callback if configured
        if on_max_iterations_reached is None and self.config.max_iterations_continue_default:
            def default_callback(current: int, max_iter: int) -> Optional[int]:
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

    # Note: _init_orchestration() and _get_orchestration_prompt() have been
    # moved to AgentInitializer and PromptGenerator respectively

    def _handle_delegation_action(self, result: Dict[str, Any]) -> bool:
        """
        Handle a delegation action from a tool result.

        Args:
            result: Tool result containing delegation action

        Returns:
            True if delegation was handled and model switched, False otherwise
        """
        action = result.get("action")

        if action == "delegate":
            target_model = result.get("target_model")
            task = result.get("task", "")
            handoff_notes = result.get("handoff_notes", "")

            if not target_model:
                logger.warning("Delegation action missing target_model")
                return False

            # Prepare delegation context
            if self._orchestration:
                self._delegation_context = self._orchestration.prepare_delegation(
                    to_model=target_model,
                    task=task,
                    handoff_notes=handoff_notes,
                    conversation_history=self.conversation.get_history(),
                    state_summary=self._get_state_summary(),
                )

            # Switch to target model
            try:
                target_config = self._model_registry.get_model(target_model) if self._model_registry else None
                provider_override = target_config.provider if target_config else None
                # Use full API model name if available
                api_model_name = target_config.api_model_name if target_config and target_config.api_model_name else target_model

                self.switch_model(api_model_name, provider_override=provider_override, silent=True)

                # Update system prompt with new model's profile
                new_prompt = self._get_system_prompt()
                self.conversation.update_system_prompt(new_prompt)

                if self._is_text_output():
                    console.print(
                        f"[cyan]Delegated:[/cyan] {result.get('from_model')} -> {target_model}\n"
                        f"[dim]Task: {task[:80]}...[/dim]"
                    )

                return True

            except ProviderError as e:
                logger.error(f"Failed to switch model for delegation: {e}")
                if self._is_text_output():
                    console.print(f"[red]Delegation failed:[/red] {e}")
                return False

        elif action == "return_to_coordinator":
            coordinator = result.get("target_model", "mimo-v2-flash")
            summary = result.get("summary", "")

            # Clear delegation context
            self._delegation_context = None

            # Switch back to coordinator
            try:
                coordinator_config = self._model_registry.get_model(coordinator) if self._model_registry else None
                provider_override = coordinator_config.provider if coordinator_config else None
                # Use full API model name if available
                api_model_name = coordinator_config.api_model_name if coordinator_config and coordinator_config.api_model_name else coordinator

                self.switch_model(api_model_name, provider_override=provider_override, silent=True)

                # Update system prompt
                new_prompt = self._get_system_prompt()
                self.conversation.update_system_prompt(new_prompt)

                if self._is_text_output():
                    console.print(
                        f"[cyan]Returned to coordinator:[/cyan] {coordinator}\n"
                        f"[dim]Summary: {summary[:80]}...[/dim]"
                    )

                return True

            except ProviderError as e:
                logger.error(f"Failed to return to coordinator: {e}")
                return False

        return False

    def _get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of current agent state for delegation context."""
        return {
            "files_read": list(set(self._tools_used))[:20],  # Recent tool usage as proxy for files
            "decisions": [],  # Could be enhanced with memory bank
            "current_model": self.model,
        }

    def switch_model(self, new_model: str, provider_override: Optional[str] = None, silent: bool = False) -> None:
        """
        Switch to a different model while maintaining conversation history.

        Reinitializes the provider and updates conversation manager's model reference.
        This allows switching between models (e.g., local to cloud) while keeping
        the same conversation context.

        Args:
            new_model: New model name to use
            provider_override: Optional provider override
            silent: If True, suppress the UI output (useful for orchestrated switches)

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

            # Notify user of model switch (unless silent mode)
            if not silent:
                new_provider_name = ProviderFactory.get_provider_name(new_model)
                if old_provider_name != new_provider_name:
                    console.print(
                        f"[cyan]Switched model:[/cyan] {old_model} ({old_provider_name}) -> "
                        f"{new_model} ({new_provider_name})"
                    )
                else:
                    console.print(f"[cyan]Switched model:[/cyan] {old_model} -> {new_model}")

        except ProviderError as e:
            # Keep old model on error
            if not silent:
                console.print(f"[red]Failed to switch model:[/red] {e}")
            raise ProviderError(f"Failed to switch model: {e}") from e

    def route_request(self, user_request: str) -> Optional["RoutingDecision"]:
        """
        Route a user request using the intelligent routing system.

        This analyzes the request and determines the optimal model/provider.
        If routing is not enabled, returns None and uses the default model.

        Args:
            user_request: The user's natural language request

        Returns:
            RoutingDecision if routing is enabled, None otherwise
        """
        if not self._routing_enabled or not self.router:
            return None

        try:
            # Create routing context from current session
            context = RoutingContext(
                session_id=str(id(self)),
                conversation_history=self.conversation.get_history(),
            )

            # Get routing decision
            decision = self.router.route_request(
                user_request,
                context=context,
                force_model=self.model if self.config.provider else None,
            )

            # Display routing decision if in text mode
            if self._is_text_output() and decision:
                self._display_routing_decision(decision)

            return decision

        except Exception as e:
            logger.warning(f"Routing failed, using default model: {e}")
            return None

    def _display_routing_decision(self, decision: "RoutingDecision") -> None:
        """Display routing decision to user."""
        if not self._is_text_output():
            return

        # Compact display
        task_info = ""
        if decision.task_analysis:
            task_info = f" ({decision.task_analysis.task_type.value})"

        cost_info = ""
        if decision.estimated_cost_usd is not None:
            if decision.estimated_cost_usd == 0:
                cost_info = " [free]"
            else:
                cost_info = f" [~${decision.estimated_cost_usd:.4f}]"

        console.print(
            f"[dim]Router:[/dim] {decision.model_name} via {decision.provider_name}"
            f"{task_info}{cost_info}"
        )

    def get_routing_statistics(self) -> Optional[Dict[str, Any]]:
        """
        Get routing system statistics.

        Returns:
            Dictionary of routing statistics, or None if routing is disabled
        """
        if not self._routing_enabled or not self.router:
            return None

        return self.router.get_statistics()

    def _load_project_context(self) -> str:
        """Load AGENT.md or README.md for project context (delegates to PromptGenerator)"""
        return self.prompt_generator.load_project_context()

    def _get_system_prompt(self) -> str:
        """Generate comprehensive system prompt (delegates to PromptGenerator)"""
        return self.prompt_generator.generate()

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

    def _output_tool_result(self, tool_name: str, result: Dict[str, Any], arguments: Optional[Dict[str, Any]] = None) -> None:
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

    def _estimate_api_call_tokens(
        self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> int:
        """
        Estimate token count for API call for rate limiting.
        
        Uses simple approximation: ~4 characters per token for English text.
        For code, this may underestimate, but it's conservative for rate limiting.
        
        Args:
            messages: List of message dictionaries
            tools: List of tool definitions
            
        Returns:
            Estimated token count
        """
        # Count characters in messages
        char_count = 0
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, str):
                    char_count += len(content)
                # Also count in tool calls/results
                if "tool_calls" in msg:
                    for call in msg.get("tool_calls", []):
                        if isinstance(call, dict):
                            char_count += len(str(call))
                if "tool_result" in msg:
                    char_count += len(str(msg.get("tool_result", "")))
        
        # Count characters in tool definitions
        for tool in tools or []:
            char_count += len(str(tool))
        
        # Approximate: 4 characters per token (conservative for rate limiting)
        tokens = max(1, int(char_count / 4))
        
        logger.debug(f"Estimated {tokens} tokens for API call ({char_count} chars)")
        return tokens

    def _call_model(
        self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Call model via provider with context overflow recovery"""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # Pre-flight validation: Check message structure to prevent API errors
                validation = self._validate_messages_for_api(messages)
                if not validation["valid"]:
                    critical_issues = [i for i in validation["issues"] if i["severity"] == "critical"]
                    if critical_issues:
                        # Try to repair critical issues automatically
                        messages = self._repair_messages_for_api(messages, critical_issues)
                        logger.warning(f"Repaired {len(critical_issues)} critical message validation issues before API call")

                # Apply rate limiting if enabled
                if self.rate_limiter:
                    # Estimate tokens for rate limiting
                    token_count = self._estimate_api_call_tokens(messages, tools)
                    if not self.rate_limiter.acquire(token_count=token_count, blocking=True):
                        logger.warning("Rate limiter blocked API call (should not happen with blocking=True)")

                # Normalize model name for provider
                normalized_model = self.provider.normalize_model_name(self.model)
                return self.provider.chat(model=normalized_model, messages=messages, tools=tools)

            except ProviderError as e:
                error_str = str(e).lower()
                # Detect context overflow errors
                if "context length" in error_str or "maximum context" in error_str or "too many tokens" in error_str or "tokens (" in error_str:
                    logger.warning(f"Context overflow detected on attempt {attempt + 1}/{max_retries}: {e}")

                    if attempt < max_retries - 1:
                        # Trigger aggressive conversation truncation
                        old_count = len(self.conversation.history)
                        current_tokens = self.conversation.get_token_count()

                        # Reduce conversation to ~30% of max to leave room for response
                        target_tokens = int(self.conversation.max_tokens * 0.3)

                        # Aggressively truncate by keeping only system + last 5 messages
                        self.conversation.history = [
                            self.conversation.history[0],  # System prompt
                            *self.conversation.history[-5:]  # Last 5 messages
                        ]

                        new_count = len(self.conversation.history)
                        new_tokens = self.conversation.get_token_count()

                        logger.warning(
                            f"Auto-recovery from context overflow: truncated conversation "
                            f"{old_count} -> {new_count} messages (~{current_tokens} -> ~{new_tokens} tokens). "
                            f"Retrying..."
                        )

                        if self._is_text_output():
                            console.print(
                                f"[yellow]⚠ Context overflow - automatically reduced conversation history. "
                                f"Retrying...[/yellow]"
                            )

                        # Update messages for retry
                        messages = self.conversation.get_history()
                        continue
                    else:
                        # Last attempt failed
                        raise ModelError(
                            f"Context overflow persists after aggressive truncation. "
                            f"Please start a new conversation or reduce the scope of your request. "
                            f"Original error: {e}"
                        ) from e
                else:
                    # Other provider error - raise immediately
                    raise ModelError(f"Provider error: {e}") from e

            except Exception as e:
                raise ModelError(f"Failed to call model: {e}") from e

        # Should not reach here
        raise ModelError("Unexpected error in model call retry logic")

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
            return create_success_response({
                "skipped": True,
                "reason": pre_result.message or "Skipped by hook",
            })
        elif pre_result.action == HookAction.MODIFY and pre_result.modified_data:
            # Use modified arguments from hook
            tool_name = pre_result.modified_data.get("tool_name", tool_name)
            arguments = pre_result.modified_data.get("arguments", arguments)

        # Permission check (delegates to PermissionManager)
        if not self.permission_manager.check(tool_name, arguments):
            return create_error_response(
                "Operation not permitted",
                ErrorType.PERMISSION,
                {"tool_name": tool_name, "permission_mode": self.permission_mode},
            )

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

        # Add duration to result for display
        if isinstance(result, dict):
            result["duration_ms"] = duration_ms

        return result

    def _get_agent_description(self, tool_calls: List[ToolCall]) -> str:
        """Get a descriptive agent message for the operation."""
        if not tool_calls:
            return "Processing"
        
        # Count operations by type
        operation_counts = {}
        for tool_call in tool_calls:
            tool_name = tool_call.name.lower()
            if "read" in tool_name:
                operation_counts["read"] = operation_counts.get("read", 0) + 1
            elif "write" in tool_name or "edit" in tool_name:
                operation_counts["write"] = operation_counts.get("write", 0) + 1
            elif "search" in tool_name or "grep" in tool_name:
                operation_counts["search"] = operation_counts.get("search", 0) + 1
            elif "execute" in tool_name:
                operation_counts["execute"] = operation_counts.get("execute", 0) + 1
            else:
                operation_counts["other"] = operation_counts.get("other", 0) + 1
        
        # Create descriptive message
        if len(operation_counts) == 1:
            op_type = list(operation_counts.keys())[0]
            count = list(operation_counts.values())[0]
            if op_type == "read":
                return f"Reading {count} file{'s' if count > 1 else ''}"
            elif op_type == "write":
                return f"Writing {count} file{'s' if count > 1 else ''}"
            elif op_type == "search":
                return f"Searching for {count} pattern{'s' if count > 1 else ''}"
            elif op_type == "execute":
                return f"Executing {count} command{'s' if count > 1 else ''}"
            else:
                return f"Processing {count} operation{'s' if count > 1 else ''}"
        else:
            total = sum(operation_counts.values())
            return f"Processing {total} operations"

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

        # ========== ROUTING INTEGRATION ==========
        # Route request to optimal model if routing is enabled
        if self._routing_enabled and self.router:
            try:
                routing_decision = self.route_request(user_message)

                if routing_decision and routing_decision.model_name != self.model:
                    # Display routing decision
                    console.print(f"\n[cyan]🔀 Routing Decision[/cyan]")
                    console.print(f"   Model: [bold]{routing_decision.model_name}[/bold]")
                    console.print(f"   Reason: {routing_decision.reasoning.primary_reason}")
                    if routing_decision.task_analysis:
                        task_type = routing_decision.task_analysis.task_type.value
                        complexity = routing_decision.task_analysis.complexity.score
                        console.print(f"   Task: {task_type} (complexity: {complexity}/10)")
                    if routing_decision.estimated_cost_usd is not None:
                        console.print(f"   Est. Cost: ${routing_decision.estimated_cost_usd:.4f}")
                    console.print()

                    # Switch to routed model
                    self.switch_model(
                        routing_decision.model_name,
                        reason=f"Routed: {routing_decision.reasoning.primary_reason}"
                    )
            except Exception as e:
                logger.warning(f"Routing failed, continuing with current model: {e}")
        # ========== END ROUTING ==========

        # Initialize delegation tracker for this request (model orchestration)
        if self._orchestration_enabled and self._orchestration:
            self._delegation_tracker = self._orchestration.start_request(self.model)

        # Set processing flag
        self._is_processing = True
        # Set agent focus to EXECUTING mode
        self.state_manager.set_focus(AgentFocus.EXECUTING)
        
        # Agent loop - use while True with explicit break for dynamic iteration extension
        max_iterations = self.config.max_iterations
        iteration = 0

        try:
            while True:
                iteration += 1
                # Track iteration in state manager
                self.state_manager.increment_iteration()

                # Check for shutdown request
                if self._shutdown_requested:
                    self._output_warning("Shutdown requested. Cleaning up...")
                    self._cleanup()
                    self._is_processing = False
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
                            self._is_processing = False
                            return
                    else:
                        # No callback - default behavior (stop)
                        self._output_warning("Reached maximum iterations")
                        self._is_processing = False
                        return

                self.loop_guard.increment_iteration()
                console.print(f"[dim]{'-' * 60}[/dim]")
    
                try:
                    # Get conversation history
                    messages = self.conversation.get_history()
    
                    # Show thinking indicator
                    # Get tools from registry (includes delegation tools)
                    tools = get_registry().get_all_schemas()

                    with console.status("[cyan]Thinking...[/cyan]", spinner=SPINNER_TYPE):
                        if (
                            use_streaming
                            and stream_model_response
                            and self.provider.supports_streaming()
                        ):
                            # Streaming mode
                            normalized_model = self.provider.normalize_model_name(self.model)
                            stream = stream_model_response(
                                self.provider, normalized_model, messages, tools
                            )
                            response_message = display_streaming_response(stream)
                        else:
                            # Non-streaming mode
                            response = self._call_model(messages, tools)
                            response_message = response["message"]
    
                    # Add assistant response
                    self.conversation.add_assistant_message(
                        content=response_message.get("content", ""),
                        tool_calls=response_message.get("tool_calls"),
                        reasoning_content=response_message.get("reasoning_content"),
                    )

                    # Create automatic checkpoint if needed
                    session_id = f"session_{self.session_start.strftime('%Y%m%d_%H%M%S')}"
                    if self.checkpoint_manager.should_checkpoint(session_id, len(self.conversation.get_history())):
                        health_report = self.health_monitor.analyze_health(self.conversation.get_history())
                        self.checkpoint_manager.create_checkpoint(
                            session_id,
                            self.conversation.get_history(),
                            health_score=health_report.overall_score
                        )
    
                    # Display thinking/reasoning if enabled and present
                    reasoning_content = response_message.get("reasoning_content")
                    if reasoning_content and self._is_text_output():
                        from .ui.display import display_thinking
    
                        display_thinking(reasoning_content, expanded=self.show_thinking)
    
                    # Display MiMo reasoning details (OpenRouter format)
                    reasoning_details = response_message.get("reasoning_details")
                    if reasoning_details and self._is_text_output():
                        from .ui.display import display_reasoning_details

                        display_reasoning_details(reasoning_details, expanded=self.show_thinking)

                    # Check if using tools
                    if response_message.get("tool_calls"):
                        # Don't display content here if tools are present - wait for final response
                        # Create ToolCall objects for batch execution
                        tool_calls_to_run = []
                        for i, tool_call_data in enumerate(response_message["tool_calls"]):
                            # Parse arguments from JSON string to dict
                            try:
                                parsed_arguments = json.loads(tool_call_data["function"]["arguments"])
                            except (json.JSONDecodeError, KeyError, TypeError):
                                # Fallback to empty dict if parsing fails
                                parsed_arguments = {}

                            # Ensure ID is always a string (defensive, in case provider validation missed something)
                            raw_id = tool_call_data.get("id", f"call_{iteration}_{i}")
                            tool_call_id = str(raw_id) if raw_id is not None else f"call_{iteration}_{i}"

                            tool_calls_to_run.append(
                                ToolCall(
                                    id=tool_call_id,
                                    name=tool_call_data["function"]["name"],
                                    arguments=parsed_arguments,
                                    index=i,
                                )
                            )

                        # Execute tools in batch with consolidated display
                        consolidated_display = get_consolidated_display()
                        agent_description = self._get_agent_description(tool_calls_to_run)

                        # Update context stats for footer display
                        context_stats = self.conversation.get_truncation_stats()
                        consolidated_display.update_context_stats(context_stats)

                        with consolidated_display.track_operations(tool_calls_to_run, agent_description):
                            batch_result = self.parallel_executor.execute_batch(tool_calls_to_run)
                            
                            # Update operation status as tools complete
                            for tool_result in batch_result.results:
                                operation_id = f"op_{tool_result.index}_{tool_result.name}"
                                status = OperationStatus.COMPLETED if tool_result.success else OperationStatus.FAILED
                                result_text = tool_result.result.get("content", "") if tool_result.success else tool_result.result.get("error", "")
                                
                                consolidated_display.update_operation_status(
                                    operation_id, status, result=result_text, error=tool_result.error
                                )
    
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
                            
                            # Track tool execution in state manager
                            self.state_manager.record_tool_execution(tool_name, arguments, result)

                            # Check for delegation actions (model orchestration)
                            if tool_name in ("delegate_to_model", "return_to_coordinator"):
                                if self._handle_delegation_action(result):
                                    # Model was switched - add result and continue with new model
                                    result = truncate_tool_result(tool_name, result)
                                    self.conversation.add_tool_result(tool_result.id, result)
                                    # Don't return - let the loop continue with the new model
                                    continue

                            # Validate result
                            if not self._validate_tool_result(tool_name, result):
                                self._output_warning(f"Invalid tool result format from {tool_name}")
                                result = create_error_response(
                                    "Tool returned invalid result format",
                                    ErrorType.EXECUTION,
                                    {"tool_name": tool_name},
                                )

                            # Truncate large results to prevent context overflow
                            result = truncate_tool_result(tool_name, result)

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
                                        from .core.recovery_strategies import RecoveryStrategy
    
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
                            # Model had reasoning but no content - check if it's confused about tools
                            tool_syntax_patterns = ['<tool_call>', '</tool_call>', 'function_call', 'tool_use']
                            has_tool_syntax = any(pattern in reasoning.lower() for pattern in tool_syntax_patterns)

                            if has_tool_syntax:
                                self._output_warning(
                                    "Model attempted to use tools in reasoning but didn't properly format tool calls. "
                                    "This may be a provider issue or model incompatibility."
                                )
                            else:
                                # Normal reasoning-only response (thinking was already displayed)
                                logger.debug("Reasoning-only response received, exiting cleanly")
                            return
                        else:
                            # Truly empty response - this shouldn't happen
                            self._output_warning("Model returned empty response. Exiting.")
                            return
    
                except KeyboardInterrupt:
                    # User interrupted the current operation
                    self._output_warning("Interrupted by user")
                    return
                except (ModelError, ProviderError) as e:
                    import traceback

                    error_msg = str(e)
                    error_context = {"traceback": traceback.format_exc()}

                    # Check for specific error types and provide recovery hints
                    if "Invalid assistant message" in error_msg:
                        # This is the specific error we're trying to prevent
                        error_msg += "\n\n[Recovery Hint] This error indicates corrupted conversation history. " \
                                   "Try clearing the session with '/clear' or starting a new session."
                        error_context["recovery_suggestion"] = "clear_session"
                    elif "rate limit" in error_msg.lower():
                        error_msg += "\n\n[Recovery Hint] Rate limit exceeded. Wait a moment and try again."
                        error_context["recovery_suggestion"] = "wait_and_retry"
                    elif "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                        error_msg += "\n\n[Recovery Hint] Check your API key configuration."
                        error_context["recovery_suggestion"] = "check_api_key"

                    self._output_error(error_msg, "model_error", error_context)
                    return
                except Exception as e:
                    import traceback
    
                    self._output_error(str(e), "error", {"traceback": traceback.format_exc()})
                    return
        finally:
            self._is_processing = False
            # Reset agent focus to EXPLORING when done
            self.state_manager.set_focus(AgentFocus.EXPLORING)

    async def _process_message_async(
        self, user_message: str, use_streaming: bool = False
    ) -> None:
        """Process a user message asynchronously through the agent loop with hook support.
        
        This is the async version of _process_message. It provides non-blocking execution
        while maintaining all the same functionality including:
        - Hook support
        - Routing integration
        - Tool execution (parallel and async-compatible)
        - Loop guards
        - Error handling
        - Rate limiting
        
        Args:
            user_message: The user's message to process
            use_streaming: Whether to use streaming responses
        """
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

        # ========== ROUTING INTEGRATION ==========
        # Route request to optimal model if routing is enabled
        if self._routing_enabled and self.router:
            try:
                routing_decision = self.route_request(user_message)

                if routing_decision and routing_decision.model_name != self.model:
                    # Display routing decision
                    console.print(f"\n[cyan]🔀 Routing Decision[/cyan]")
                    console.print(f"   Model: [bold]{routing_decision.model_name}[/bold]")
                    console.print(f"   Reason: {routing_decision.reasoning.primary_reason}")
                    if routing_decision.task_analysis:
                        task_type = routing_decision.task_analysis.task_type.value
                        complexity = routing_decision.task_analysis.complexity.score
                        console.print(f"   Task: {task_type} (complexity: {complexity}/10)")
                    if routing_decision.estimated_cost_usd is not None:
                        console.print(f"   Est. Cost: ${routing_decision.estimated_cost_usd:.4f}")
                    console.print()

                    # Switch to routed model
                    self.switch_model(
                        routing_decision.model_name,
                        reason=f"Routed: {routing_decision.reasoning.primary_reason}"
                    )
            except Exception as e:
                logger.warning(f"Routing failed, continuing with current model: {e}")
        # ========== END ROUTING ==========

        # Initialize delegation tracker for this request (model orchestration)
        if self._orchestration_enabled and self._orchestration:
            self._delegation_tracker = self._orchestration.start_request(self.model)

        # Set processing flag
        self._is_processing = True
        # Set agent focus to EXECUTING mode
        self.state_manager.set_focus(AgentFocus.EXECUTING)
        
        # Agent loop - use while True with explicit break for dynamic iteration extension
        max_iterations = self.config.max_iterations
        iteration = 0

        try:
            while True:
                iteration += 1
                # Track iteration in state manager
                self.state_manager.increment_iteration()

                # Check for shutdown request
                if self._shutdown_requested:
                    self._output_warning("Shutdown requested. Cleaning up...")
                    await asyncio.to_thread(self._cleanup)
                    self._is_processing = False
                    return

                # Check if we've exceeded max iterations (before processing)
                if iteration > max_iterations:
                    # Check if callback is set
                    if self._on_max_iterations_reached:
                        additional = await asyncio.to_thread(
                            self._on_max_iterations_reached, iteration, max_iterations
                        )
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
                            self._is_processing = False
                            return
                    else:
                        # No callback - default behavior (stop)
                        self._output_warning("Reached maximum iterations")
                        self._is_processing = False
                        return

                self.loop_guard.increment_iteration()
                console.print(f"[dim]{'-' * 60}[/dim]")

                try:
                    # Get conversation history
                    messages = self.conversation.get_history()

                    # Get tools from registry (includes delegation tools)
                    tools = await asyncio.to_thread(get_registry().get_all_schemas)

                    # Show thinking indicator
                    with console.status("[cyan]Thinking...[/cyan]", spinner=SPINNER_TYPE):
                        if (
                            use_streaming
                            and stream_model_response
                            and self.provider.supports_streaming()
                        ):
                            # Streaming mode - async
                            normalized_model = self.provider.normalize_model_name(self.model)
                            stream = await asyncio.to_thread(
                                stream_model_response,
                                self.provider,
                                normalized_model,
                                messages,
                                tools,
                            )
                            response_message = await asyncio.to_thread(
                                display_streaming_response, stream
                            )
                        else:
                            # Non-streaming mode - call async model if available
                            response = await self._call_model_async(messages, tools)
                            response_message = response["message"]

                    # Add assistant response
                    self.conversation.add_assistant_message(
                        content=response_message.get("content", ""),
                        tool_calls=response_message.get("tool_calls"),
                        reasoning_content=response_message.get("reasoning_content"),
                    )

                    # Create automatic checkpoint if needed
                    session_id = f"session_{self.session_start.strftime('%Y%m%d_%H%M%S')}"
                    if self.checkpoint_manager.should_checkpoint(
                        session_id, len(self.conversation.get_history())
                    ):
                        health_report = await asyncio.to_thread(
                            self.health_monitor.analyze_health, self.conversation.get_history()
                        )
                        await asyncio.to_thread(
                            self.checkpoint_manager.create_checkpoint,
                            session_id,
                            self.conversation.get_history(),
                            health_score=health_report.overall_score,
                        )

                    # Display thinking/reasoning if enabled and present
                    reasoning_content = response_message.get("reasoning_content")
                    if reasoning_content and self._is_text_output():
                        from .ui.display import display_thinking

                        await asyncio.to_thread(
                            display_thinking, reasoning_content, expanded=self.show_thinking
                        )

                    # Display MiMo reasoning details (OpenRouter format)
                    reasoning_details = response_message.get("reasoning_details")
                    if reasoning_details and self._is_text_output():
                        from .ui.display import display_reasoning_details

                        await asyncio.to_thread(
                            display_reasoning_details, reasoning_details, expanded=self.show_thinking
                        )

                    # Check if using tools
                    if response_message.get("tool_calls"):
                        # Create ToolCall objects for batch execution
                        tool_calls_to_run = []
                        for i, tool_call_data in enumerate(response_message["tool_calls"]):
                            # Parse arguments from JSON string to dict
                            try:
                                parsed_arguments = json.loads(tool_call_data["function"]["arguments"])
                            except (json.JSONDecodeError, KeyError, TypeError):
                                # Fallback to empty dict if parsing fails
                                parsed_arguments = {}

                            # Ensure ID is always a string (defensive, in case provider validation missed something)
                            raw_id = tool_call_data.get("id", f"call_{iteration}_{i}")
                            tool_call_id = str(raw_id) if raw_id is not None else f"call_{iteration}_{i}"

                            tool_calls_to_run.append(
                                ToolCall(
                                    id=tool_call_id,
                                    name=tool_call_data["function"]["name"],
                                    arguments=parsed_arguments,
                                    index=i,
                                )
                            )

                        # Execute tools in batch (async-compatible)
                        batch_result = await self._execute_tools_async(tool_calls_to_run)

                        # Process results
                        for tool_result in batch_result.results:
                            # Check for shutdown request before each tool
                            if self._shutdown_requested:
                                self._output_warning("Shutdown requested. Stopping tool execution...")
                                await asyncio.to_thread(self._cleanup)
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
                            
                            # Track tool execution in state manager
                            self.state_manager.record_tool_execution(tool_name, arguments, result)

                            # Check for delegation actions (model orchestration)
                            if tool_name in ("delegate_to_model", "return_to_coordinator"):
                                if await asyncio.to_thread(self._handle_delegation_action, result):
                                    # Model was switched - add result and continue with new model
                                    result = truncate_tool_result(tool_name, result)
                                    self.conversation.add_tool_result(tool_result.id, result)
                                    # Don't return - let the loop continue with the new model
                                    continue

                            # Validate result
                            if not await asyncio.to_thread(self._validate_tool_result, tool_name, result):
                                self._output_warning(f"Invalid tool result format from {tool_name}")
                                result = await asyncio.to_thread(
                                    create_error_response,
                                    "Tool returned invalid result format",
                                    ErrorType.EXECUTION,
                                    {"tool_name": tool_name},
                                )

                            # Truncate large results to prevent context overflow
                            result = truncate_tool_result(tool_name, result)

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
                                        from .core.recovery_strategies import RecoveryStrategy

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
                            # Model had reasoning but no content - check if it's confused about tools
                            tool_syntax_patterns = ['<tool_call>', '</tool_call>', 'function_call', 'tool_use']
                            has_tool_syntax = any(pattern in reasoning.lower() for pattern in tool_syntax_patterns)

                            if has_tool_syntax:
                                self._output_warning(
                                    "Model attempted to use tools in reasoning but didn't properly format tool calls. "
                                    "This may be a provider issue or model incompatibility."
                                )
                            else:
                                # Normal reasoning-only response (thinking was already displayed)
                                logger.debug("Reasoning-only response received, exiting cleanly")
                            return
                        else:
                            # Truly empty response - this shouldn't happen
                            self._output_warning("Model returned empty response. Exiting.")
                            return

                except KeyboardInterrupt:
                    # User interrupted the current operation
                    self._output_warning("Interrupted by user")
                    return
                except (ModelError, ProviderError) as e:
                    import traceback

                    error_msg = str(e)
                    error_context = {"traceback": traceback.format_exc()}

                    # Check for specific error types and provide recovery hints
                    if "Invalid assistant message" in error_msg:
                        # This is the specific error we're trying to prevent
                        error_msg += "\n\n[Recovery Hint] This error indicates corrupted conversation history. " \
                                   "Try clearing the session with '/clear' or starting a new session."
                        error_context["recovery_suggestion"] = "clear_session"
                    elif "rate limit" in error_msg.lower():
                        error_msg += "\n\n[Recovery Hint] Rate limit exceeded. Wait a moment and try again."
                        error_context["recovery_suggestion"] = "wait_and_retry"
                    elif "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                        error_msg += "\n\n[Recovery Hint] Check your API key configuration."
                        error_context["recovery_suggestion"] = "check_api_key"

                    self._output_error(error_msg, "model_error", error_context)
                    return
                except Exception as e:
                    import traceback

                    self._output_error(str(e), "error", {"traceback": traceback.format_exc()})
                    return
        finally:
            self._is_processing = False
            # Reset agent focus to EXPLORING when done
            self.state_manager.set_focus(AgentFocus.EXPLORING)

    async def _call_model_async(
        self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Call model asynchronously via provider with retry logic.
        
        This async version uses asyncio.to_thread for CPU-bound operations
        and maintains the same retry logic as the sync version.
        """
        try:
            # Apply rate limiting if enabled (async version)
            if self.rate_limiter:
                # Estimate tokens for rate limiting
                token_count = self._estimate_api_call_tokens(messages, tools)
                if not self.rate_limiter.acquire(token_count=token_count, blocking=True):
                    logger.warning("Rate limiter blocked API call (should not happen with blocking=True)")

            # Normalize model name for provider
            normalized_model = self.provider.normalize_model_name(self.model)
            
            # Call provider asynchronously
            # Most provider calls are I/O-bound, so we can use to_thread
            return await asyncio.to_thread(
                self.provider.chat,
                model=normalized_model,
                messages=messages,
                tools=tools,
            )
        except Exception as e:
            logger.error(f"Error in async model call: {e}")
            raise

    async def _execute_tools_async(
        self, tool_calls_to_run: List[ToolCall]
    ) -> Any:
        """Execute tools asynchronously.
        
        This method maintains compatibility with the sync version while
        allowing async execution of tools where possible.
        """
        # Check if we should run tools in parallel
        execution_mode = self.parallel_executor._get_execution_mode(tool_calls_to_run)
        
        if execution_mode.value == "parallel":
            # For parallel execution, we use the existing parallel executor
            # which is already optimized for concurrent execution
            return await asyncio.to_thread(
                self.parallel_executor.execute_batch,
                tool_calls_to_run,
            )
        else:
            # For serialized execution, also use to_thread
            return await asyncio.to_thread(
                self.parallel_executor.execute_batch,
                tool_calls_to_run,
            )

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get current conversation history"""
        return self.conversation.get_history()

    def clear_conversation(self) -> None:
        """Clear conversation history"""
        self.conversation.clear(keep_system=True)
        # Update system prompt
        self.conversation.history[0]["content"] = self._get_system_prompt()

    def _validate_messages_for_api(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate messages for API compliance to prevent "Invalid assistant message" errors.

        Returns:
            Dict with validation results and issues found.
        """
        issues = []

        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")

            # Validate assistant messages - must have content or tool_calls
            if role == "assistant":
                if not content and not tool_calls:
                    issues.append({
                        "index": i,
                        "type": "invalid_assistant_message",
                        "message": f"Assistant message at index {i} has no content or tool_calls",
                        "severity": "critical"  # Will cause API errors
                    })

            # Validate tool messages - content must be string
            elif role == "tool":
                if not isinstance(msg.get("content", ""), str):
                    issues.append({
                        "index": i,
                        "type": "invalid_tool_result",
                        "message": f"Tool result at index {i} has non-string content",
                        "severity": "warning"
                    })

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "message_count": len(messages),
            "severity_levels": {
                "critical": len([i for i in issues if i["severity"] == "critical"]),
                "warning": len([i for i in issues if i["severity"] == "warning"])
            }
        }

    def _repair_messages_for_api(self, messages: List[Dict[str, Any]], issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Attempt to automatically repair critical message validation issues.

        Args:
            messages: Original message list
            issues: List of validation issues (only critical ones should be passed)

        Returns:
            Repaired message list
        """
        repaired_messages = messages.copy()

        for issue in issues:
            if issue["type"] == "invalid_assistant_message":
                idx = issue["index"]
                msg = repaired_messages[idx]

                # Try to fix by converting reasoning_content to content
                if msg.get("reasoning_content"):
                    content = f"[Reasoning: {msg['reasoning_content'][:200]}{'...' if len(msg['reasoning_content']) > 200 else ''}]"
                    repaired_messages[idx]["content"] = content
                    logger.debug(f"Repaired assistant message at index {idx} by converting reasoning to content")
                else:
                    # Fallback: add minimal content
                    repaired_messages[idx]["content"] = "[Repaired empty assistant response]"
                    logger.debug(f"Repaired assistant message at index {idx} by adding minimal content")

        return repaired_messages

    def validate_session_health(self) -> Dict[str, Any]:
        """
        Validate the current session health and provide recovery recommendations.

        Returns:
            Dict with session health status and recommendations.
        """
        # Use conversation manager's validation
        history_validation = self.conversation.validate_history()

        # Additional checks
        issues = history_validation["issues"].copy()
        recommendations = []

        # Check for excessive message count
        if history_validation["message_count"] > 100:
            issues.append({
                "type": "high_message_count",
                "message": f"Session has {history_validation['message_count']} messages, which may impact performance",
                "severity": "warning"
            })
            recommendations.append("Consider clearing old messages or starting a new session")

        # Check for repeated errors in recent history
        recent_messages = self.conversation.get_history()[-20:]  # Last 20 messages
        error_count = 0
        for msg in recent_messages:
            if msg.get("role") == "tool":
                try:
                    result = json.loads(msg.get("content", "{}"))
                    if not result.get("success", True):
                        error_count += 1
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse tool result JSON: {e}")
                    pass

        if error_count > 5:
            issues.append({
                "type": "frequent_errors",
                "message": f"{error_count} errors in recent messages, indicating potential issues",
                "severity": "warning"
            })
            recommendations.append("Review recent tool executions for patterns")

        # Generate recovery recommendations based on issues
        if history_validation["severity_levels"]["critical"] > 0:
            recommendations.insert(0, "CRITICAL: Session has corrupted messages. Use '/clear' to start fresh")
        elif history_validation["severity_levels"]["warning"] > 0:
            recommendations.insert(0, "Session has warnings. Monitor for issues")

        return {
            "healthy": len([i for i in issues if i["severity"] == "critical"]) == 0,
            "issues": issues,
            "recommendations": recommendations,
            "validation": history_validation
        }
