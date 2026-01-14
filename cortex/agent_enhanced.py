"""Enhanced Cortex agent with planning and layered memory systems.

This module extends the base Cortex agent with:
1. Goal-oriented planning system
2. Layered memory architecture (working, session, state)
3. Enhanced reasoning with plan execution and verification
4. Better context management and state tracking
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Union
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .agent import Cortex
from .models import PermissionMode
from .config import AgentConfig
from .core.conversation import ConversationManager
from .core.parallel import ParallelToolExecutor, ToolCall
from .core.streaming import stream_model_response, display_streaming_response
from .core.providers import ProviderFactory, ProviderError
from .core.security import SecurityError
from .core.loop_guards import LoopGuard
from .core.summarization import create_summarizer, SummarizationStrategy
from .core.planning import PlanningEngine, Plan, PlanStep, PlanStepStatus, PlanStepType
from .core.memory_layers import (
    StateManager,
    AgentState,
    AgentFocus,
    WorkingMemory,
    EnhancedMemoryBank,
)
from .tools import TOOLS, create_tool_instance
from .ui.console import console
from .utils.errors import (
    retry_with_backoff,
    ModelError,
    create_error_response,
    create_success_response,
    ErrorType,
)
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

logger = logging.getLogger(__name__)


class EnhancedCortex(Cortex):
    """
    Enhanced Cortex agent with planning and layered memory.
    
    Extends the base Cortex agent with:
    - Goal decomposition and planning
    - Layered memory architecture
    - State management across execution cycles
    - Plan execution with verification
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
        enable_planning: bool = True,
        enable_layered_memory: bool = True,
    ):
        """
        Initialize enhanced Cortex agent.
        
        Args:
            model: Model name to use
            project_dir: Project directory to work in
            permission_mode: Permission mode (NORMAL, AUTO_APPROVE, PLAN)
            config: Agent configuration
            hook_manager: Hook manager for event handling
            output_format: Output format (TEXT, JSON, etc.)
            on_max_iterations_reached: Callback for max iterations
            enable_planning: Enable planning system
            enable_layered_memory: Enable layered memory system
        """
        # Initialize base Cortex
        super().__init__(
            model=model,
            project_dir=project_dir,
            permission_mode=permission_mode,
            config=config,
            hook_manager=hook_manager,
            output_format=output_format,
            on_max_iterations_reached=on_max_iterations_reached,
        )
        
        # Planning and memory configuration
        self.enable_planning = enable_planning
        self.enable_layered_memory = enable_layered_memory
        
        # Replace base memory bank with enhanced one if enabled
        if enable_layered_memory:
            self.memory_bank = EnhancedMemoryBank(max_items=100)
        
        # Initialize state manager
        self.state_manager = StateManager(project_dir=Path(project_dir).resolve())
        
        # Initialize planning engine if enabled
        if enable_planning:
            self.planning_engine = PlanningEngine(
                project_dir=project_dir,
                skill_loader=self._load_skill,
                tool_executor=self._execute_tool_for_planning,
                reflection_callback=self._on_plan_reflection,
            )
        else:
            self.planning_engine = None
        
        # Track enhanced metrics
        self.plans_generated = 0
        self.plans_executed = 0
        self.plans_completed = 0
        
        # Update system prompt with enhanced guidance
        self._update_system_prompt()
    
    def _update_system_prompt(self) -> None:
        """Update system prompt with planning and memory guidance."""
        # Get base system prompt
        base_prompt = super()._get_system_prompt()
        
        # Enhanced guidance to append
        enhanced_guidance = """

# ENHANCED PLANNING AND MEMORY CAPABILITIES

You now have access to enhanced planning and memory systems:

## Planning System
- **Goal Decomposition**: Break complex tasks into sub-goals
- **Plan Generation**: Create step-by-step execution plans
- **Plan Execution**: Execute plans with verification
- **Adaptation**: Adjust plans based on results

## Memory Layers
- **Working Memory**: Current task context, files being examined, tool chain
- **Session Memory**: What you've learned this session (patterns, failures, insights)
- **State Tracking**: Your current focus and progress towards goals

## Enhanced Workflow
1. **Understand**: Analyze the user's request and context
2. **Explore**: Discover relevant files and structure if needed
3. **Plan**: Create or select an execution strategy
4. **Execute**: Run tools with clear purpose and expected outcomes
5. **Verify**: Check if results match expectations
6. **Learn**: Extract insights and update memory
7. **Adapt**: Adjust approach if needed

## Key Principles
- Use state awareness to inform decisions
- Maintain context in working memory
- Learn from both successes and failures
- Adapt plans when encountering obstacles
- Track progress against goals

Your enhanced capabilities are enabled. Use them to work more effectively.
"""
        
        # Append enhanced guidance to the base prompt
        enhanced_prompt = base_prompt + enhanced_guidance
        
        # Update conversation manager's system prompt
        self.conversation.history[0]["content"] = enhanced_prompt
    
    def _load_skill(self, skill_name: str) -> Dict[str, Any]:
        """Load a skill by name (for planning engine)."""
        # This would integrate with the skill system
        # For now, return empty dict
        return {}
    
    def _execute_tool_for_planning(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool (for planning engine)."""
        # Use the existing execute_tool method
        return self.execute_tool(tool_name, arguments)
    
    def _on_plan_reflection(self, plan: Plan, reflection: str) -> None:
        """Callback for plan reflection events."""
        logger.info(f"Plan reflection: {reflection}")
        
        # Add to session memory
        if self.enable_layered_memory:
            self.state_manager.record_insight(f"Plan reflection: {reflection}")
    
    def process_with_planning(self, user_message: str, use_streaming: bool = False):
        """
        Process a user message with enhanced planning.
        
        This method overrides the base _process_message to incorporate
        planning and layered memory.
        """
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
            user_message = prompt_result.modified_data.get("prompt", user_message)
        
        # Set primary goal in state manager
        self.state_manager.set_primary_goal(user_message)
        self.state_manager.set_focus(AgentFocus.EXPLORING)
        
        # Add enhanced context to conversation
        enhanced_context = self._get_enhanced_context()
        user_message_with_context = f"{enhanced_context}\\n\\nUser request: {user_message}"
        
        # Add to conversation
        self.conversation.add_user_message(user_message_with_context)
        self._session_dirty = True
        
        # Set processing flag
        self._is_processing = True
        
        # Main enhanced processing loop
        max_iterations = self.config.max_iterations
        iteration = 0
        
        try:
            while True:
                iteration += 1
                self.state_manager.increment_iteration()
                
                # Check for shutdown request
                if self._shutdown_requested:
                    self._output_warning("Shutdown requested. Cleaning up...")
                    self._cleanup()
                    self._is_processing = False
                    return
                
                # Check max iterations
                if iteration > max_iterations:
                    if self._on_max_iterations_reached:
                        additional = self._on_max_iterations_reached(iteration, max_iterations)
                        if additional is not None and additional > 0:
                            max_iterations += additional
                            console.print(
                                f"[cyan]Extended iterations:[/cyan] +{additional} more (total: {max_iterations})"
                            )
                            continue
                        else:
                            self._output_warning("Reached maximum iterations")
                            self._is_processing = False
                            return
                    else:
                        self._output_warning("Reached maximum iterations")
                        self._is_processing = False
                        return
                
                self.loop_guard.increment_iteration()
                console.print(f"[dim]{'-' * 60}[/dim]")
                
                try:
                    # Get conversation history
                    messages = self.conversation.get_history()
                    
                    # Show thinking indicator
                    with console.status("[cyan]Thinking...[/cyan]", spinner="dots"):
                        if (
                            use_streaming
                            and stream_model_response
                            and self.provider.supports_streaming()
                        ):
                            normalized_model = self.provider.normalize_model_name(self.model)
                            stream = stream_model_response(
                                self.provider, normalized_model, messages, TOOLS
                            )
                            response_message = display_streaming_response(stream)
                        else:
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
                        # Execute tools in batch
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
                        
                        # Execute tools
                        batch_result = self.parallel_executor.execute_batch(tool_calls_to_run)
                        
                        # Process results
                        for tool_result in batch_result.results:
                            if self._shutdown_requested:
                                self._output_warning("Shutdown requested. Stopping tool execution...")
                                self._cleanup()
                                return
                            
                            tool_name = tool_result.name
                            arguments = next(
                                (tc.arguments for tc in tool_calls_to_run if tc.id == tool_result.id),
                                {},
                            )
                            result = tool_result.result
                            
                            # Output tool result
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
                            
                            # Update state manager with tool execution
                            self.state_manager.record_tool_execution(tool_name, arguments, result)
                            
                            # Extract learnings if layered memory is enabled
                            if self.enable_layered_memory:
                                self.memory_bank.extract_learnings_from_tool_results([result])
                            
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
                            
                            # Extract insights from final response
                            if self.enable_layered_memory:
                                self._extract_insights_from_response(final_text)
                            
                            return
                        elif reasoning:
                            # Model had reasoning but no content
                            return
                        else:
                            self._output_warning("Model returned empty response. Exiting.")
                            return
                
                except KeyboardInterrupt:
                    self._output_warning("Interrupted by user")
                    return
                except (ModelError, ProviderError) as e:
                    import traceback
                    self._output_error(str(e), "model_error", {"traceback": traceback.format_exc()})
                    return
                except Exception as e:
                    import traceback
                    self._output_error(str(e), "error", {"traceback": traceback.format_exc()})
                    return
        
        finally:
            self._is_processing = False
    
    def _get_enhanced_context(self) -> str:
        """Get enhanced context including state and memory."""
        context_parts = []
        
        # State manager context
        if self.enable_layered_memory:
            state_context = self.state_manager.get_llm_context()
            if state_context:
                context_parts.append("## CURRENT STATE AND CONTEXT")
                context_parts.append(state_context)
        
        # Memory bank summary
        if hasattr(self, 'memory_bank') and self.memory_bank:
            memory_summary = self.memory_bank.get_summary()
            if memory_summary:
                context_parts.append("## SESSION MEMORY")
                context_parts.append(memory_summary)
        
        # Project context
        if self.project_context:
            context_parts.append("## PROJECT CONTEXT")
            context_parts.append(self.project_context[:1000])  # Limit length
        
        return "\\n\\n".join(context_parts)
    
    def _extract_insights_from_response(self, response: str) -> None:
        """Extract insights from final response text."""
        # Simple insight extraction - could be enhanced
        if not self.enable_layered_memory:
            return
        
        # Look for patterns indicating insights
        insight_indicators = [
            "insight:",
            "learned that",
            "key finding:",
            "important:",
            "note that",
            "discovered that",
        ]
        
        lines = response.split('\\n')
        for line in lines:
            line_lower = line.lower()
            for indicator in insight_indicators:
                if indicator in line_lower:
                    # Extract the insight part
                    idx = line_lower.find(indicator)
                    insight_text = line[idx + len(indicator):].strip()
                    if insight_text and len(insight_text) > 10:  # Meaningful length
                        self.state_manager.record_insight(insight_text)
                        break
    
    def generate_and_execute_plan(self, goal: str) -> Dict[str, Any]:
        """
        Generate and execute a plan for a goal.
        
        Args:
            goal: Goal description
            
        Returns:
            Execution results
        """
        if not self.enable_planning or not self.planning_engine:
            return {"success": False, "error": "Planning not enabled"}
        
        try:
            # Generate plan
            plan = self.planning_engine.generate_plan(goal)
            self.plans_generated += 1
            
            # Set active plan in state manager
            self.state_manager.set_active_plan(plan)
            self.state_manager.set_focus(AgentFocus.EXECUTING)
            
            # Execute plan
            execution_result = self.planning_engine.execute_plan(plan)
            self.plans_executed += 1
            
            if execution_result.get("success", False):
                self.plans_completed += 1
                self.state_manager.set_focus(AgentFocus.REFLECTING)
                
                # Record successful pattern
                if self.enable_layered_memory:
                    self.state_manager.record_pattern(
                        pattern=f"Plan execution for: {goal[:50]}...",
                        context="Plan-based execution",
                        effectiveness=1.0,
                    )
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Plan execution failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def get_enhanced_metrics(self) -> Dict[str, Any]:
        """Get enhanced metrics including planning and memory stats."""
        base_metrics = {
            "model": self.model,
            "permission_mode": self.permission_mode,
            "tools_used": list(set(self._tools_used)),
            "tool_count": len(self._tools_used),
        }
        
        enhanced_metrics = {
            **base_metrics,
            "enable_planning": self.enable_planning,
            "enable_layered_memory": self.enable_layered_memory,
            "plans_generated": self.plans_generated,
            "plans_executed": self.plans_executed,
            "plans_completed": self.plans_completed,
        }
        
        if self.enable_layered_memory:
            state = self.state_manager.state
            enhanced_metrics.update({
                "iterations": state.iteration_count,
                "successful_tools": state.successful_tools,
                "failed_tools": state.failed_tools,
                "insights_generated": state.insights_generated,
                "patterns_recognized": state.patterns_recognized,
                "adaptations_made": state.adaptations_made,
            })
        
        return enhanced_metrics
    
    def clear_enhanced_state(self) -> None:
        """Clear enhanced state while keeping base conversation."""
        if self.enable_layered_memory:
            self.state_manager.clear()
        
        if hasattr(self, 'memory_bank'):
            self.memory_bank.clear()
        
        self.plans_generated = 0
        self.plans_executed = 0
        self.plans_completed = 0