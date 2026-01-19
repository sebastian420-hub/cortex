"""
Delegation-enabled Cortex agent with model-aware planning.

This module extends EnhancedCortex to add model delegation capabilities
to the planning system. It enables automatic delegation to specialist
models based on step requirements and validation rules.
"""

import logging
from typing import Optional, Dict, Any, Callable, Union
from pathlib import Path

from .agent_enhanced import EnhancedCortex
from .models import PermissionMode
from .config import AgentConfig
from .output import OutputFormat
from .hooks import HookManager
from .core.planning_enhanced import ModelAwarePlanStep, convert_plan_to_modelaware
from .core.delegation_planning_engine import DelegationPlanningEngine
from .core.delegation_rules import DelegationRules
from .core.prompts.delegation_guidance import get_delegation_guidance, get_quick_reference
from .core.model_capabilities import PromptStyle

logger = logging.getLogger(__name__)


class PlanningDelegationCortex(EnhancedCortex):
    """
    Enhanced Cortex agent with model delegation planning.
    
    Extends EnhancedCortex to:
    1. Use DelegationPlanningEngine instead of PlanningEngine
    2. Add delegation guidance to system prompts
    3. Provide model-aware plan creation helpers
    4. Track delegation statistics and quota
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
        max_delegations: int = 5,
        current_model: str = "haiku-4.5",
    ):
        """
        Initialize delegation-enabled Cortex agent.
        
        Args:
            model: Model name to use (coordinator model)
            project_dir: Project directory to work in
            permission_mode: Permission mode (NORMAL, AUTO_APPROVE, PLAN)
            config: Agent configuration
            hook_manager: Hook manager for event handling
            output_format: Output format (TEXT, JSON, etc.)
            on_max_iterations_reached: Callback for max iterations
            enable_planning: Enable planning system
            enable_layered_memory: Enable layered memory system
            max_delegations: Maximum allowed delegations per request
            current_model: The model name representing this coordinator
        """
        # Store delegation settings
        self.max_delegations = max_delegations
        self.current_model = current_model
        
        # Initialize parent (EnhancedCortex) with planning disabled
        # We'll create our own delegation planning engine
        super().__init__(
            model=model,
            project_dir=project_dir,
            permission_mode=permission_mode,
            config=config,
            hook_manager=hook_manager,
            output_format=output_format,
            on_max_iterations_reached=on_max_iterations_reached,
            enable_planning=False,  # We'll create our own engine
            enable_layered_memory=enable_layered_memory,
        )
        
        # Now create delegation planning engine if enabled
        if enable_planning:
            self.planning_engine = DelegationPlanningEngine(
                project_dir=self.project_dir,
                skill_loader=self._load_skill,
                tool_executor=self._execute_tool_for_planning,
                reflection_callback=self._on_plan_reflection,
                current_model=self.current_model,
                max_delegations=self.max_delegations,
            )
            logger.debug(f"DelegationPlanningEngine initialized with {self.max_delegations} max delegations")
        else:
            self.planning_engine = None
        
        # Re-enable planning flag for our agent
        self.enable_planning = enable_planning
        
        # Update system prompt with delegation guidance
        self._update_system_prompt()
        
        logger.info(f"PlanningDelegationCortex initialized for model: {current_model}")
        logger.info(f"Maximum delegations: {max_delegations}")
    
    def _update_system_prompt(self) -> None:
        """
        Update system prompt with delegation guidance.
        
        Overrides parent to add model delegation framework guidance
        while keeping all existing enhanced guidance.
        """
        # Get base enhanced prompt from parent
        base_prompt = super()._get_system_prompt()
        
        # Get model profile for adaptive guidance
        from .core.model_capabilities import get_model_profile, get_adapter_info
        from .core.prompts import adapt_prompt_for_model
        
        profile = get_model_profile(self.model)
        adapter_info = get_adapter_info(self.model)
        
        logger.debug(f"PlanningDelegationCortex using model profile: {profile.name}, style: {profile.prompt_style.value}")
        
        # Get enhanced planning guidance (from parent)
        enhanced_guidance = self._get_planning_guidance(profile.prompt_style)
        
        # Get delegation guidance based on remaining quota
        delegation_guidance = self._get_delegation_guidance(profile.prompt_style)
        
        # Combine all guidance
        full_prompt = base_prompt + enhanced_guidance + delegation_guidance
        
        # Apply model-specific adaptations
        full_prompt = adapt_prompt_for_model(full_prompt, self.model)
        
        # Update conversation manager's system prompt
        self.conversation.history[0]["content"] = full_prompt
        
        logger.debug("System prompt updated with delegation guidance")
    
    def _get_delegation_guidance(self, style: PromptStyle) -> str:
        """
        Get delegation guidance appropriate for model capability level.
        
        Args:
            style: Prompt style based on model capability
            
        Returns:
            Delegation guidance string
        """
        # Get remaining delegations from engine if available
        remaining_delegations = self.max_delegations
        if self.enable_planning and self.planning_engine:
            remaining_delegations = self.planning_engine.delegation_tracker.get_remaining()
        
        if style == PromptStyle.EXPLICIT:
            # Short, explicit guidance for smaller models
            return f"""

# MODEL DELEGATION (SIMPLIFIED)

You can delegate tasks to specialist models:

1. **Security** → dolphin-24b (REQUIRED for security tasks)
2. **Complex** → deepseek-reasoner (recommended)
3. **Code Review** → gpt-5.1-codex-mini
4. **Implementation** → grok-code-fast-1

**Delegations Remaining:** {remaining_delegations}/{self.max_delegations}

**IMPORTANT RULES:**
- Security tasks MUST use dolphin-24b
- Don't delegate simple tasks
- Track your delegation count
"""
        
        elif style == PromptStyle.CONCISE:
            # Medium-length guidance
            return f"""

# MODEL DELEGATION FRAMEWORK

You coordinate a team of specialist models. Delegate strategically.

## SPECIALIST MODELS

| Model | Specialty | When to Use |
|-------|-----------|-------------|
| **dolphin-24b** | Security | Security audits, authentication, vulnerabilities |
| **deepseek-reasoner** | Reasoning | Complex architecture, critical decisions |
| **gpt-5.1-codex-mini** | Code Review | Quality checks, best practices |
| **grok-code-fast-1** | Implementation | Coding, debugging, refactoring |

## DELEGATION STATUS
**Remaining:** {remaining_delegations}/{self.max_delegations}

## KEY RULES
1. **MANDATORY**: Security tasks → dolphin-24b
2. **RECOMMENDED**: Complex tasks → deepseek-reasoner
3. **OPTIONAL**: Code reviews → gpt-5.1-codex-mini
4. **PROHIBITED**: Don't delegate simple tasks
"""
        
        else:  # DETAILED - full guidance for capable models
            # Get full delegation guidance
            full_guidance = get_delegation_guidance(remaining_delegations)
            
            # Add quick reference at the end
            full_guidance += "\n\n" + get_quick_reference()
            
            return full_guidance
    
    def get_delegation_stats(self) -> Dict[str, Any]:
        """
        Get delegation statistics.
        
        Returns:
            Dictionary with delegation statistics and execution stats
        """
        if not self.enable_planning or not self.planning_engine:
            return {
                "delegation_enabled": False,
                "message": "Planning not enabled"
            }
        
        # Get stats from delegation planning engine
        stats = self.planning_engine.get_execution_stats()
        
        # Add agent-level info
        stats.update({
            "agent_model": self.model,
            "coordinator_model": self.current_model,
            "max_delegations": self.max_delegations,
            "delegation_enabled": True,
            "planning_enabled": self.enable_planning,
        })
        
        return stats
    
    def create_model_aware_plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        constraints: Optional[list] = None,
        assumptions: Optional[list] = None,
        skill_hints: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Create a plan and convert it to model-aware format.
        
        This is a convenience method that creates a plan and automatically
        converts it to use ModelAwarePlanStep for all steps.
        
        Args:
            goal: The goal to achieve
            context: Additional context (optional)
            constraints: List of constraints (optional)
            assumptions: List of assumptions (optional)
            skill_hints: Suggested skills to apply (optional)
            
        Returns:
            Plan creation result with delegation metadata
        """
        # Create plan using parent method
        result = self.tool_executor("create_plan", {
            "goal": goal,
            "constraints": constraints or [],
            "assumptions": assumptions or [],
            "skill_hints": skill_hints or [],
            "context": context or {},
        })
        
        # Convert plan to model-aware format
        if result.get("success") and self.enable_planning and self.planning_engine:
            plan_id = result.get("plan_id")
            if plan_id:
                plan = self.planning_engine.get_plan(plan_id)
                if plan:
                    # Convert to model-aware
                    converted_plan = convert_plan_to_modelaware(plan)
                    # Replace in engine
                    self.planning_engine.plans[plan_id] = converted_plan
                    
                    # Add delegation metadata to result
                    result["delegation_metadata"] = {
                        "model_aware": True,
                        "step_count": len(converted_plan.steps),
                        "max_delegations": self.max_delegations,
                    }
        
        return result
    
    def add_model_aware_step(
        self,
        plan_id: str,
        description: str,
        required_model: Optional[str] = None,
        model_assignment_reason: Optional[str] = None,
        risk_level: str = "medium",
        security_related: bool = False,
        review_required: bool = False,
        review_model: Optional[str] = None,
        **step_kwargs,
    ) -> Dict[str, Any]:
        """
        Add a model-aware step to a plan.
        
        This is a convenience method for adding steps with delegation metadata.
        
        Args:
            plan_id: ID of the plan to update
            description: Step description
            required_model: Model that must execute this step
            model_assignment_reason: Reason for model assignment
            risk_level: Risk level (low, medium, high, critical)
            security_related: Whether step involves security
            review_required: Whether step requires review
            review_model: Model to perform review
            **step_kwargs: Additional step parameters
            
        Returns:
            Update plan result
        """
        # Build step data with delegation fields
        step_data = {
            "description": description,
            "required_model": required_model,
            "model_assignment_reason": model_assignment_reason,
            "risk_level": risk_level,
            "security_related": security_related,
            "review_required": review_required,
            "review_model": review_model,
            **step_kwargs,
        }
        
        # Remove None values
        step_data = {k: v for k, v in step_data.items() if v is not None}
        
        # Use update_plan tool
        return self.tool_executor("update_plan", {
            "plan_id": plan_id,
            "action": "add_step",
            "step_data": step_data,
        })
    
    def get_delegation_summary(self) -> str:
        """
        Get human-readable delegation summary.
        
        Returns:
            String summary of delegation activity
        """
        if not self.enable_planning or not self.planning_engine:
            return "Delegation planning not enabled"
        
        return self.planning_engine.get_delegation_summary()
    
    def reset_delegation_stats(self) -> Dict[str, Any]:
        """
        Reset delegation statistics.
        
        Returns:
            Result of reset operation
        """
        if not self.enable_planning or not self.planning_engine:
            return {
                "success": False,
                "error": "Planning not enabled"
            }
        
        self.planning_engine.reset_execution_stats()
        
        return {
            "success": True,
            "message": "Delegation statistics reset"
        }