"""Main Cortex class - Unified Agent Orchestrator"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rich.markdown import Markdown

from .config import AgentConfig
from .core.agent_init import AgentInitializer
from .core.agent_messaging import MessageProcessor
from .core.agent_permissions import PermissionManager
from .core.agent_prompts import PromptGenerator
from .core.agent_tools import ToolExecutor
from .core.memory_layers import AgentFocus, EnhancedMemoryBank
from .core.parallel import ParallelToolExecutor, ToolCall
from .core.planning import Plan, PlanStep, PlanStepType
from .core.prompts.builder import PromptBuilder
from .core.providers import ProviderError, ProviderFactory
from .core.security import SecurityError
from .core.streaming import display_streaming_response, stream_model_response
from .hooks import (
    HookAction,
    HookManager,
    PostToolUseEvent,
    PreToolUseEvent,
    SessionEndEvent,
    SessionStartEvent,
    UserPromptSubmitEvent,
)
from .models import PermissionMode
from .output import OutputFormat
from .tools import create_tool_instance, get_registry
from .ui.console import console
from .ui.consolidated_display import get_consolidated_display
from .utils.errors import (
    ErrorType,
    ModelError,
    create_error_response,
    create_permission_denial,
    create_success_response,
)
from .utils.output_processing import process_model_output
from .utils.result_truncation import truncate_tool_result

# Import routing system (optional, gracefully handle if not available)
try:
    from .core.routing import (
        RoutingConfig,
        RoutingContext,
        RoutingDecision,
        RoutingOrchestrator,
    )

    ROUTING_AVAILABLE = True
except ImportError:
    ROUTING_AVAILABLE = False
    RoutingOrchestrator = None
    RoutingConfig = None
    RoutingContext = None
    RoutingDecision = None

logger = logging.getLogger(__name__)

# Platform-specific spinner (Windows cp1252 can't handle Unicode Braille)
SPINNER_TYPE = "line" if sys.platform == "win32" else "dots"


class Cortex:
    """
    Main Cortex class - handles conversation loop, tool execution,
    planning, and layered memory.
    """

    def __init__(
        self,
        model: str = "moonshotai/kimi-k2.5",
        project_dir: str = ".",
        permission_mode: str = PermissionMode.NORMAL,
        config: Optional[AgentConfig] = None,
        hook_manager: Optional[HookManager] = None,
        output_format: OutputFormat = OutputFormat.TEXT,
        on_max_iterations_reached: Optional[Callable[[int, int], Optional[int]]] = None,
        enable_planning: bool = True,
        enable_layered_memory: bool = True,
    ):
        """
        Initialize Cortex agent with all components.

        Args:
            model: LLM model to use
            project_dir: Project directory path
            permission_mode: Permission mode (NORMAL, AUTO_APPROVE, PLAN)
            config: Agent configuration
            hook_manager: Hook manager for event handling
            output_format: Output format (TEXT, JSON, etc.)
            on_max_iterations_reached: Callback for max iterations
            enable_planning: Whether to enable the planning engine
            enable_layered_memory: Whether to use enhanced layered memory
        """
        # Basic setup
        self.model = model
        self.project_dir = Path(project_dir).resolve()
        self.permission_mode = permission_mode
        self.config = config or AgentConfig()
        self.session_start = datetime.now()
        self.hook_manager = hook_manager or HookManager()
        self.output_format = output_format

        # Enhanced features configuration
        self.enable_planning = enable_planning
        self.enable_layered_memory = enable_layered_memory

        # Use AgentInitializer to handle complex initialization
        initializer = AgentInitializer(
            model=model,
            project_dir=self.project_dir,
            permission_mode=permission_mode,
            config=self.config,
            hook_manager=self.hook_manager,
            output_format=output_format,
            enable_planning=enable_planning,
            enable_layered_memory=enable_layered_memory,
            planning_callbacks={
                "skill_loader": self._load_skill,
                "tool_executor": self._execute_tool_for_planning,
                "reflection_callback": self._on_plan_reflection,
                "step_callback": self._on_plan_step,
            },
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
        self.planning_engine = initializer.planning_engine

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
        self.prompt_builder = PromptBuilder(self.model, project_dir=self.project_dir)
        self.permission_manager = PermissionManager(self)
        self.tool_executor = ToolExecutor(self)
        self.message_processor = MessageProcessor(self)

        # Enhanced metrics
        self.plans_generated = 0
        self.plans_executed = 0
        self.plans_completed = 0

        # Initial context loading
        self.project_context = self.prompt_generator.load_project_context()

        # Initialize conversation system prompt correctly from the start
        system_prompt = self._get_system_prompt()
        self.conversation.system_prompt = system_prompt
        if not self.conversation.history:
            self.conversation.add_system_message(system_prompt)
        else:
            self.conversation.history[0]["content"] = system_prompt

        self.conversation._on_truncation = self._on_context_truncation
        if hasattr(self.conversation, "_on_summarization"):
            self.conversation._on_summarization = self._on_context_summarization

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

    def _on_context_summarization(self, messages_removed: int, remaining: int) -> None:
        """Callback when context is summarized."""
        if self._is_text_output():
            console.print(
                f"[green]Context summarized:[/green] Compressed {messages_removed} "
                f"old messages into a summary ({remaining} remaining)"
            )

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
                target_config = (
                    self._model_registry.get_model(target_model) if self._model_registry else None
                )
                provider_override = target_config.provider if target_config else None
                # Use full API model name if available
                api_model_name = (
                    target_config.api_model_name
                    if target_config and target_config.api_model_name
                    else target_model
                )

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
                coordinator_config = (
                    self._model_registry.get_model(coordinator) if self._model_registry else None
                )
                provider_override = coordinator_config.provider if coordinator_config else None
                # Use full API model name if available
                api_model_name = (
                    coordinator_config.api_model_name
                    if coordinator_config and coordinator_config.api_model_name
                    else coordinator
                )

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

    def switch_model(
        self,
        new_model: str,
        provider_override: Optional[str] = None,
        silent: bool = False,
        reason: Optional[str] = None,
    ) -> None:
        """
        Switch to a different model while maintaining conversation history.

        Reinitializes the provider and updates conversation manager's model reference.
        This allows switching between models (e.g., local to cloud) while keeping
        the same conversation context.

        Args:
            new_model: New model name to use
            provider_override: Optional provider override
            silent: If True, suppress the UI output
            reason: Optional reason for the switch
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

            # Update prompt builder for new model
            self.prompt_builder = PromptBuilder(self.model, project_dir=self.project_dir)

            # Update conversation manager's model reference for token counting
            self.conversation.update_model(new_model)

            # Notify user of model switch (unless silent mode)
            if not silent:
                new_provider_name = ProviderFactory.get_provider_name(new_model)
                reason_str = f" [dim]({reason})[/dim]" if reason else ""
                if old_provider_name != new_provider_name:
                    console.print(
                        f"[cyan]Switched model:[/cyan] {old_model} ({old_provider_name}) -> "
                        f"{new_model} ({new_provider_name}){reason_str}"
                    )
                else:
                    console.print(
                        f"[cyan]Switched model:[/cyan] {old_model} -> {new_model}{reason_str}"
                    )

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

    def load_project_context(self) -> str:
        """Public method to load project context for backward compatibility."""
        return self._load_project_context()

    def _get_system_prompt(self) -> str:
        """Generate comprehensive system prompt using PromptBuilder"""
        # Get dynamic context
        state_context = (
            self.state_manager.get_llm_context() if hasattr(self, "state_manager") else None
        )
        memory_bank_context = (
            self.memory_bank.get_summary() if hasattr(self, "memory_bank") else None
        )
        metacognitive_context = (
            self.state_manager.get_metacognitive_context()
            if hasattr(self, "state_manager")
            else None
        )

        # Get semantic context if enabled
        semantic_context = None
        if self.enable_layered_memory and hasattr(self.memory_bank, "retrieve_semantic_context"):
            # Use last user message as query for semantic retrieval
            last_user_msg = self.conversation.get_last_user_message()
            if last_user_msg:
                # Get relevant items from current session
                session_results = self.memory_bank.retrieve_semantic_context(
                    last_user_msg, top_k=2, global_search=False
                )
                
                # Get one highly relevant item from past sessions
                global_results = self.memory_bank.retrieve_semantic_context(
                    last_user_msg, top_k=1, global_search=True
                )
                
                context_items = []
                if session_results:
                    context_items.append("From current session:")
                    context_items.extend([f"- {r['document']}" for r in session_results])
                
                if global_results:
                    # Filter out if it's the same as a session result
                    session_docs = [r["document"] for r in session_results]
                    for r in global_results:
                        if r["document"] not in session_docs:
                            context_items.append("From past sessions:")
                            context_items.append(f"- {r['document']}")
                
                if context_items:
                    semantic_context = "\n".join(context_items)

        # Get all tool schemas (includes base + orchestration tools)
        exclude = []
        if not self.enable_planning:
            exclude = [
                "create_plan",
                "execute_plan",
                "monitor_plan",
                "update_plan",
                "create_and_execute_plan",
                "metacognitive_reflect",
            ]
        else:
            exclude = ["metacognitive_reflect"]

        tool_schemas = get_registry().get_all_schemas(exclude_names=exclude)

        # Build using PromptBuilder
        return self.prompt_builder.build_system_prompt(
            tools=tool_schemas,
            enable_planning=self.enable_planning,
            enable_memory=self.enable_layered_memory,
            state_context=state_context,
            project_context=self.project_context,
            memory_bank_context=memory_bank_context,
            semantic_context=semantic_context,  # New parameter
            metacognitive_context=metacognitive_context,
            permission_mode=self.permission_mode,
        )

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
            processed_content = process_model_output(content)
            # Always use simple markdown output (no Panel boxes)
            console.print(Markdown(processed_content))
        else:
            formatted = self.formatter.format_response(response)
            self.formatter.write(formatted)

    def _output_tool_result(
        self, tool_name: str, result: Dict[str, Any], arguments: Optional[Dict[str, Any]] = None
    ) -> None:
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
                # Pre-flight validation
                validation = self._validate_messages_for_api(messages)
                if not validation["valid"]:
                    critical_issues = [
                        i for i in validation["issues"] if i["severity"] == "critical"
                    ]
                    if critical_issues:
                        messages = self._repair_messages_for_api(messages, critical_issues)
                        logger.warning(
                            f"Repaired {len(critical_issues)} critical issues before API call"
                        )

                # Apply rate limiting
                if self.rate_limiter:
                    token_count = self._estimate_api_call_tokens(messages, tools)
                    if not self.rate_limiter.acquire(token_count=token_count, blocking=True):
                        logger.warning("Rate limiter blocked API call")

                # Normalize model name for provider
                normalized_model = self.provider.normalize_model_name(self.model)
                return self.provider.chat(model=normalized_model, messages=messages, tools=tools)

            except ProviderError as e:
                error_str = str(e).lower()
                if any(
                    x in error_str
                    for x in ["context length", "maximum context", "too many tokens", "tokens ("]
                ):
                    logger.warning(
                        f"Context overflow detected on attempt {attempt + 1}/{max_retries}"
                    )

                    if attempt < max_retries - 1:
                        # Aggressive truncation
                        self.conversation.history = [
                            self.conversation.history[0],  # System prompt
                            *self.conversation.history[-5:],  # Last 5 messages
                        ]

                        # Truncate remaining tool results
                        max_tool_content_length = self.conversation._get_max_tool_result_length()
                        for msg in self.conversation.history:
                            if msg.get("role") == "tool":
                                content = msg.get("content", "")
                                if (
                                    isinstance(content, str)
                                    and len(content) > max_tool_content_length
                                ):
                                    msg["content"] = (
                                        content[:max_tool_content_length] + "... [truncated]"
                                    )

                        if self._is_text_output():
                            console.print(
                                "[yellow]Context overflow - aggressively "
                                "reduced conversation history.[/yellow]"
                            )

                        messages = self.conversation.get_history()
                        continue
                    else:
                        raise ModelError(f"Context overflow persists after truncation: {e}") from e
                else:
                    raise ModelError(f"Provider error: {e}") from e

            except Exception as e:
                raise ModelError(f"Failed to call model: {e}") from e

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
            return create_success_response(
                {
                    "skipped": True,
                    "reason": pre_result.message or "Skipped by hook",
                }
            )
        elif pre_result.action == HookAction.MODIFY and pre_result.modified_data:
            tool_name = pre_result.modified_data.get("tool_name", tool_name)
            arguments = pre_result.modified_data.get("arguments", arguments)

        # Permission check
        if not self.permission_manager.check(tool_name, arguments):
            return create_permission_denial(
                reason="Operation not permitted",
                action=tool_name,
                context={"tool_name": tool_name, "permission_mode": self.permission_mode},
            )

        # Track tool usage
        self._tools_used.append(tool_name)

        # Execute tool with timing
        start_time = time.time()
        result = None
        success = False

        try:
            # Create tool instance
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

            # --- Metacognitive Appraisal ---
            if hasattr(self, "state_manager"):
                self.state_manager.update_metacognition(tool_name, result)
            
            # Bio-inspired belief reinforcement
            if self.enable_layered_memory and hasattr(self.memory_bank, "verify_memory"):
                # Use a heuristic: if we were looking for a file and found it, verify that memory
                if "path" in arguments:
                    self.memory_bank.verify_memory(arguments["path"], success)
                elif "filepath" in arguments:
                    self.memory_bank.verify_memory(arguments["filepath"], success)
            # -------------------------------

        except ValueError:
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

        if post_result.action == HookAction.MODIFY and post_result.modified_data:
            if "result" in post_result.modified_data:
                result = post_result.modified_data["result"]

        if isinstance(result, dict):
            result["duration_ms"] = duration_ms

        return result

    def _get_agent_description(self, tool_calls: List[ToolCall]) -> str:
        """Get a descriptive agent message for the operation."""
        if not tool_calls:
            return "Processing"

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
        if "success" not in result:
            return False
        if not result["success"]:
            if "error" not in result and "error_type" not in result:
                return False
        return True

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        self._shutdown_requested = True

    def _cleanup(self) -> None:
        """Cleanup resources on shutdown."""
        try:
            self._dispatch_session_end()
            if self.parallel_executor:
                self.parallel_executor.shutdown()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}", exc_info=True)

    def _process_message(self, user_message: str, use_streaming: bool = False):
        """Unified message processing loop supporting planning and memory."""

        if self._shutdown_requested:
            return

        # Dispatch UserPromptSubmit hook
        prompt_event = UserPromptSubmitEvent(
            prompt=user_message, conversation_length=len(self.conversation.get_history())
        )
        prompt_result = self.hook_manager.dispatch(prompt_event)

        if prompt_result.action == HookAction.ABORT:
            self._output_error(prompt_result.message or "Blocked by hook", "prompt_blocked")
            return
        elif prompt_result.action == HookAction.MODIFY and prompt_result.modified_data:
            user_message = prompt_result.modified_data.get("prompt", user_message)

        # Set goals if using state management
        if hasattr(self, "state_manager"):
            self.state_manager.set_primary_goal(user_message)
            self.state_manager.set_focus(AgentFocus.EXPLORING)

        # Add user message
        self.conversation.add_user_message(user_message)
        self._session_dirty = True

        # Routing integration
        if self._routing_enabled and self.router:
            try:
                routing_decision = self.route_request(user_message)
                if routing_decision and routing_decision.model_name != self.model:
                    self.switch_model(
                        routing_decision.model_name,
                        reason=routing_decision.reasoning.primary_reason,
                    )
            except Exception as e:
                logger.warning(f"Routing failed: {e}")

        # Delegation tracking
        if self._orchestration_enabled and self._orchestration:
            self._delegation_tracker = self._orchestration.start_request(self.model)

        self._is_processing = True

        # Agent loop
        max_iterations = self.config.max_iterations
        iteration = 0

        try:
            while True:
                iteration += 1
                self.state_manager.increment_iteration()

                if self._shutdown_requested:
                    self._output_warning("Shutdown requested. Cleaning up...")
                    self._cleanup()
                    return

                if iteration > max_iterations:
                    if self._on_max_iterations_reached:
                        additional = self._on_max_iterations_reached(iteration, max_iterations)
                        if additional is not None and additional > 0:
                            max_iterations += additional
                            continue
                    self._output_warning("Reached maximum iterations")
                    return

                self.loop_guard.increment_iteration()
                console.print(f"[dim]{'-' * 60}[/dim]")

                try:
                    # Refresh system prompt with latest state/memory
                    new_system_prompt = self._get_system_prompt()
                    self.conversation.update_system_prompt(new_system_prompt)
                    messages = self.conversation.get_history()

                    exclude = []
                    if not self.enable_planning:
                        exclude = [
                            "create_plan",
                            "execute_plan",
                            "monitor_plan",
                            "update_plan",
                            "create_and_execute_plan",
                            "metacognitive_reflect",
                        ]
                    else:
                        # Even if planning is enabled, we keep reflection for specific training/session end
                        exclude = ["metacognitive_reflect"]
                    tools = get_registry().get_all_schemas(exclude_names=exclude)

                    with console.status("[cyan]Thinking...[/cyan]", spinner=SPINNER_TYPE):
                        if (
                            use_streaming
                            and stream_model_response
                            and self.provider.supports_streaming()
                        ):
                            normalized_model = self.provider.normalize_model_name(self.model)
                            stream = stream_model_response(
                                self.provider, normalized_model, messages, tools
                            )
                            response_message = display_streaming_response(stream)
                        else:
                            response = self._call_model(messages, tools)
                            response_message = response["message"]

                    # Add assistant response
                    self.conversation.add_assistant_message(
                        content=response_message.get("content", ""),
                        tool_calls=response_message.get("tool_calls"),
                        reasoning_content=response_message.get("reasoning_content"),
                    )

                    # Handle thinking/reasoning
                    reasoning_content = response_message.get("reasoning_content")
                    if reasoning_content and self._is_text_output():
                        from .ui.display import display_thinking

                        display_thinking(reasoning_content, expanded=self.show_thinking)

                    # Process Tool Calls
                    if response_message.get("tool_calls"):
                        tool_calls_to_run = []
                        for i, tool_call_data in enumerate(response_message["tool_calls"]):
                            try:
                                parsed_arguments = json.loads(
                                    tool_call_data["function"]["arguments"]
                                )
                            except Exception:
                                parsed_arguments = {}

                            raw_id = tool_call_data.get("id", f"call_{iteration}_{i}")
                            tool_calls_to_run.append(
                                ToolCall(
                                    id=(
                                        str(raw_id)
                                        if raw_id is not None
                                        else f"call_{iteration}_{i}"
                                    ),
                                    name=tool_call_data["function"]["name"],
                                    arguments=parsed_arguments,
                                    index=i,
                                )
                            )

                        # Batch execute
                        consolidated_display = get_consolidated_display()
                        agent_description = self._get_agent_description(tool_calls_to_run)

                        with consolidated_display.track_operations(
                            tool_calls_to_run, agent_description
                        ):
                            batch_result = self.parallel_executor.execute_batch(tool_calls_to_run)

                        # Process results
                        for tool_result in batch_result.results:
                            if self._shutdown_requested:
                                return

                            tool_name = tool_result.name
                            result = tool_result.result
                            arguments = next(
                                (
                                    tc.arguments
                                    for tc in tool_calls_to_run
                                    if tc.id == tool_result.id
                                ),
                                {},
                            )

                            self._output_tool_result(tool_name, result)

                            # Update state and memory
                            self.state_manager.record_tool_execution(tool_name, arguments, result)
                            if self.enable_layered_memory and isinstance(
                                self.memory_bank, EnhancedMemoryBank
                            ):
                                self.memory_bank.extract_learnings_from_tool_results([result])

                            # Delegation
                            if tool_name in ("delegate_to_model", "return_to_coordinator"):
                                if self._handle_delegation_action(result):
                                    result = truncate_tool_result(
                                        tool_name,
                                        result,
                                        max_length=self.conversation._get_max_tool_result_length(),
                                    )
                                    self.conversation.add_tool_result(tool_result.id, result)
                                    continue

                            # Truncate and add to conversation
                            result = truncate_tool_result(
                                tool_name,
                                result,
                                max_length=self.conversation._get_max_tool_result_length(),
                            )
                            self.conversation.add_tool_result(tool_result.id, result)

                            # Loop guard checks
                            if not self._is_tool_result_success(result):
                                if self.loop_guard.check_repeated_error(result):
                                    recovery_action = self.loop_guard.get_recovery_action(
                                        result, tool_name, arguments
                                    )
                                    if recovery_action and recovery_action.strategy != "ESCALATE":
                                        if recovery_action.suggested_prompt:
                                            self.conversation.add_user_message(
                                                f"[Recovery Guidance] "
                                                f"{recovery_action.suggested_prompt}"
                                            )
                                        continue
                                    return

                    else:
                        # Final response
                        final_text = response_message.get("content", "")
                        if final_text:
                            self._output_response({"content": final_text}, is_final=True)
                            if self.enable_layered_memory:
                                self._extract_insights_from_response(final_text)
                            return
                        return

                except Exception as e:
                    import traceback

                    self._output_error(str(e), "error", {"traceback": traceback.format_exc()})
                    return
        finally:
            self._is_processing = False
            self.state_manager.set_focus(AgentFocus.EXPLORING)

    # Async version of the loop
    async def _process_message_async(self, user_message: str, use_streaming: bool = False) -> None:
        """Async version of message processing."""
        await asyncio.to_thread(self._process_message, user_message, use_streaming)

    def _extract_insights_from_response(self, response: str) -> None:
        """Extract insights from final response text for layered memory."""
        if not self.enable_layered_memory:
            return
        insight_indicators = ["insight:", "learned that", "key finding:", "discovered that"]
        for line in response.split("\n"):
            for indicator in insight_indicators:
                if indicator in line.lower():
                    idx = line.lower().find(indicator)
                    insight_text = line[idx + len(indicator) :].strip()
                    if len(insight_text) > 10:
                        self.state_manager.record_insight(insight_text)
                        break

    def generate_and_execute_plan(self, goal: str) -> Dict[str, Any]:
        """Generate and execute a structured plan."""
        if not self.enable_planning or not self.planning_engine:
            return {"success": False, "error": "Planning not enabled"}
        try:
            plan = self.planning_engine.create_plan(goal)
            self.plans_generated += 1
            self.state_manager.set_active_plan(plan)
            self.state_manager.set_focus(AgentFocus.EXECUTING)
            execution_result = self.planning_engine.execute_plan(plan)
            self.plans_executed += 1
            if execution_result.get("success", False):
                self.plans_completed += 1
            return execution_result
        except Exception as e:
            logger.error(f"Plan execution failed: {e}")
            return {"success": False, "error": str(e)}

    def _load_skill(self, skill_name: str) -> Dict[str, Any]:
        return {}

    def _execute_tool_for_planning(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self.execute_tool(tool_name, arguments)

    def _on_plan_reflection(self, plan: Plan, reflection: str) -> None:
        if self.enable_layered_memory:
            self.state_manager.record_insight(f"Plan reflection: {reflection}")

    def _on_plan_step(self, step: PlanStep, result: Dict[str, Any]) -> None:
        """
        Callback triggered when a plan step completes.

        This records the step execution in history and memory so the agent
        stays informed of what happened during planning execution.
        """
        if self.enable_layered_memory and isinstance(self.memory_bank, EnhancedMemoryBank):
            self.memory_bank.extract_learnings_from_tool_results([result])

        # Record the tool execution in conversation history if it was a tool call
        if step.step_type == PlanStepType.TOOL_CALL and step.tool_name:
            # We don't have the original tool_call_id from the model here,
            # so we use the step ID as a reference.
            tool_call_id = f"plan_{step.id}"

            # Add a synthetic assistant message showing the tool call that was executed
            # This helps the model maintain context of the conversation flow
            self.conversation.add_assistant_message(
                content=f"Executing plan step: {step.description}",
                tool_calls=[
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": step.tool_name,
                            "arguments": json.dumps(step.tool_arguments or {}),
                        },
                    }
                ],
            )

            # Add the result
            truncated_result = truncate_tool_result(
                step.tool_name, result, max_length=self.conversation._get_max_tool_result_length()
            )
            self.conversation.add_tool_result(tool_call_id, truncated_result)

            if self._is_text_output():
                status = "success" if result.get("success", False) else "failed"
                console.print(f"[dim]Plan Step {step.id}: {step.tool_name} -> {status}[/dim]")

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return self.conversation.get_history()

    def clear_conversation(self) -> None:
        self.conversation.clear(keep_system=True)
        self.conversation.history[0]["content"] = self._get_system_prompt()

    def _validate_messages_for_api(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate messages for API compliance, checking for missing content keys."""
        issues = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "assistant":
                # Check for missing content key entirely
                if "content" not in msg:
                    issues.append(
                        {"index": i, "type": "missing_content_key", "severity": "critical"}
                    )
                # Check for both empty content and empty tool calls
                elif not msg.get("content") and not msg.get("tool_calls"):
                    issues.append(
                        {"index": i, "type": "invalid_assistant_message", "severity": "critical"}
                    )
        return {"valid": len(issues) == 0, "issues": issues}

    def _repair_messages_for_api(
        self, messages: List[Dict[str, Any]], issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Attempt to repair critical message validation issues."""
        repaired = messages.copy()
        for issue in issues:
            idx = issue["index"]
            if issue["type"] == "missing_content_key":
                repaired[idx]["content"] = ""
            elif issue["type"] == "invalid_assistant_message":
                if repaired[idx].get("reasoning_content"):
                    repaired[idx][
                        "content"
                    ] = f"[Reasoning: {repaired[idx]['reasoning_content'][:200]}]"
                else:
                    repaired[idx]["content"] = "[Repaired empty response]"
        return repaired
