"""
Delegation Planning Engine.

Extends the standard PlanningEngine to support model-aware plan execution
with automatic delegation to specialist models based on step requirements.
"""

import logging
from typing import Dict, Any, Optional, Union, Callable
from pathlib import Path
from datetime import datetime

from .planning import PlanningEngine, Plan, PlanStep, PlanStepStatus
from .planning_enhanced import ModelAwarePlanStep, convert_planstep_to_modelaware
from .delegation_rules import DelegationRules, ValidationResult, RuleSeverity
from ..core.orchestration import DelegationTracker, DelegationContext, MAX_DELEGATIONS_PER_REQUEST
from ..utils.errors import create_error_response, create_success_response, ErrorType

logger = logging.getLogger(__name__)


class DelegationPlanningEngine(PlanningEngine):
    """
    Enhanced planning engine with model delegation capabilities.
    
    This engine:
    1. Validates model assignments against delegation rules
    2. Executes steps with appropriate model delegation
    3. Tracks delegation quota and prevents infinite loops
    4. Automatically reviews high-risk steps
    5. Maintains backward compatibility with existing plans
    """
    
    def __init__(
        self,
        project_dir: Union[str, Path] = ".",
        skill_loader: Optional[Callable[[str], Dict[str, Any]]] = None,
        tool_executor: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        reflection_callback: Optional[Callable[[Plan, str], None]] = None,
        max_plan_steps: int = 100,
        current_model: str = "haiku-4.5",
        max_delegations: int = MAX_DELEGATIONS_PER_REQUEST,
    ):
        """
        Initialize delegation planning engine.
        
        Args:
            project_dir: Project directory for context
            skill_loader: Function to load skills by name
            tool_executor: Function to execute tools by name and arguments
            reflection_callback: Callback for reflection events
            max_plan_steps: Maximum number of steps in a plan
            current_model: The model currently executing (coordinator)
            max_delegations: Maximum allowed delegations per request
        """
        super().__init__(
            project_dir=project_dir,
            skill_loader=skill_loader,
            tool_executor=tool_executor,
            reflection_callback=reflection_callback,
            max_plan_steps=max_plan_steps,
        )
        
        self.current_model = current_model
        self.delegation_rules = DelegationRules()
        self.delegation_tracker = DelegationTracker(max_delegations=max_delegations)
        self.execution_stats = {
            "steps_executed": 0,
            "steps_delegated": 0,
            "delegation_violations": 0,
            "auto_reviews_performed": 0,
            "total_cost_estimated": 0.0,
        }
        
        logger.info(f"DelegationPlanningEngine initialized for model: {current_model}")
        logger.info(f"Maximum delegations: {max_delegations}")
    
    def execute_step(self, plan_id: str, step_id: str) -> Dict[str, Any]:
        """
        Execute a single plan step with model delegation support.
        
        Overrides parent method to:
        1. Convert step to ModelAwarePlanStep if needed
        2. Validate model assignment against rules
        3. Execute with delegation if required
        4. Perform auto-review if configured
        
        Args:
            plan_id: ID of the plan containing the step
            step_id: ID of the step to execute
            
        Returns:
            Execution result with delegation metadata
        """
        # Get plan and step
        plan = self.get_plan(plan_id)
        if plan is None:
            return create_error_response(f"Plan not found: {plan_id}", ErrorType.NOT_FOUND)
        
        step = plan.get_step_by_id(step_id)
        if step is None:
            return create_error_response(f"Step not found: {step_id}", ErrorType.NOT_FOUND)
        
        # Convert to ModelAwarePlanStep if needed
        if not isinstance(step, ModelAwarePlanStep):
            step = convert_planstep_to_modelaware(step)
            # Update plan with converted step
            # (We need to find and replace the step in the plan)
            for i, s in enumerate(plan.steps):
                if s.id == step_id:
                    plan.steps[i] = step
                    break
        
        # Mark step as started
        step.mark_started()
        
        try:
            # Execute the step
            result = self._execute_step_with_delegation(step, plan)
            
            # Update step status based on result
            if result["success"]:
                step.mark_completed(result.get("content"))
                logger.info(f"Step {step.id} completed: {step.description}")
                
                # Add delegation metadata to result
                if step.delegated_to:
                    result["delegation"] = {
                        "from_model": self.current_model,
                        "to_model": step.delegated_to,
                        "reason": step.model_assignment_reason,
                    }
                
                # Track execution stats
                self.execution_stats["steps_executed"] += 1
                if step.delegated_to:
                    self.execution_stats["steps_delegated"] += 1
            else:
                step.mark_failed(result.get("error", "Unknown error"))
                logger.error(f"Step {step.id} failed: {result.get('error')}")
            
            return result
            
        except Exception as e:
            step.mark_failed(str(e))
            logger.exception(f"Exception executing step {step.id}")
            return create_error_response(
                f"Exception executing step {step.id}: {str(e)}",
                ErrorType.EXECUTION,
            )
    
    def _execute_step_with_delegation(self, step: ModelAwarePlanStep, plan: Plan) -> Dict[str, Any]:
        """
        Execute a step with model delegation logic.
        
        Args:
            step: The step to execute
            plan: The containing plan
            
        Returns:
            Execution result
        """
        # Step 1: Validate model assignment
        validation = self.delegation_rules.validate_step(step, self.current_model)
        
        # Log violations
        if validation.violations:
            self.execution_stats["delegation_violations"] += 1
            for violation in validation.violations:
                if violation.severity == RuleSeverity.CRITICAL:
                    logger.error(f"Critical delegation violation: {violation}")
                else:
                    logger.warning(f"Delegation violation: {violation}")
        
        # Step 2: Determine execution model
        execution_model = self._determine_execution_model(step, validation)
        
        # Step 3: Check delegation quota
        if execution_model != self.current_model:
            if not self.delegation_tracker.can_delegate():
                return create_error_response(
                    "Delegation quota exhausted",
                    ErrorType.VALIDATION,
                    {
                        "step": step.description,
                        "remaining_delegations": 0,
                        "max_delegations": self.delegation_tracker.max_delegations,
                    }
                )
        
        # Step 4: Execute with appropriate model
        if execution_model != self.current_model:
            # Delegate to another model
            return self._execute_with_delegation(step, plan, execution_model)
        else:
            # Execute locally
            return self._execute_step_locally(step, plan)
    
    def _determine_execution_model(self, step: ModelAwarePlanStep, validation: ValidationResult) -> str:
        """
        Determine which model should execute this step.
        
        Priority:
        1. Step's required_model (if valid)
        2. Validation suggested_model (if critical violations)
        3. Current model (fallback)
        
        Args:
            step: The step to execute
            validation: Validation result
            
        Returns:
            Model to execute the step
        """
        # If step has critical violations, use suggested model
        if validation.has_critical_violations() and validation.suggested_model:
            logger.info(f"Using suggested model due to critical violations: {validation.suggested_model}")
            return validation.suggested_model
        
        # If step has required_model, use it (assuming it passed validation)
        if step.required_model:
            return step.required_model
        
        # Default to current model
        return self.current_model
    
    def _execute_with_delegation(self, step: ModelAwarePlanStep, plan: Plan, target_model: str) -> Dict[str, Any]:
        """
        Execute a step by delegating to another model.
        
        Args:
            step: The step to execute
            plan: The containing plan
            target_model: Model to delegate to
            
        Returns:
            Execution result from delegated model
        """
        logger.info(f"Delegating step to {target_model}: {step.description}")
        
        # Build delegation context
        context = self._build_delegation_context(step, plan, target_model)
        
        # Record delegation
        delegation_record = self.delegation_tracker.record_delegation(
            from_model=self.current_model,
            to_model=target_model,
            reason=step.model_assignment_reason or f"Step: {step.description}"
        )
        
        # Mark step as delegated
        step.mark_delegated(target_model)
        
        # Execute via delegate_to_model tool
        result = self.tool_executor("delegate_to_model", {
            "model": target_model,
            "task": step.description,
            "handoff_notes": context.to_system_context(),
        })
        
        # Check if delegation was successful
        if not result.get("success", False):
            logger.error(f"Delegation to {target_model} failed: {result.get('error')}")
            return result
        
        # Step 5: Apply auto-review if required
        if step.review_required and step.auto_review:
            review_result = self._perform_auto_review(step, result)
            result["review"] = review_result
            self.execution_stats["auto_reviews_performed"] += 1
            
            # Store review result in step
            step.add_review_result(review_result)
        
        # Add delegation metadata to result
        result["delegation_metadata"] = {
            "from_model": self.current_model,
            "to_model": target_model,
            "delegation_number": delegation_record.delegation_number,
            "remaining_delegations": self.delegation_tracker.get_remaining(),
            "timestamp": delegation_record.timestamp.isoformat(),
        }
        
        return result
    
    def _execute_step_locally(self, step: ModelAwarePlanStep, plan: Plan) -> Dict[str, Any]:
        """
        Execute a step locally (without delegation).
        
        Args:
            step: The step to execute
            plan: The containing plan
            
        Returns:
            Execution result
        """
        logger.info(f"Executing step locally: {step.description}")
        
        # Use parent class execution logic
        if step.step_type == PlanStepType.TOOL_CALL and step.tool_name and self.tool_executor:
            return self.tool_executor(step.tool_name, step.tool_arguments or {})
        
        # Handle other step types (inherit from parent)
        return super()._execute_step(step, plan)
    
    def _build_delegation_context(self, step: ModelAwarePlanStep, plan: Plan, target_model: str) -> DelegationContext:
        """
        Build delegation context for handoff.
        
        Args:
            step: The step being delegated
            plan: The containing plan
            target_model: Model receiving the delegation
            
        Returns:
            DelegationContext object
        """
        # Build state summary
        state_summary = {
            "plan_id": plan.id,
            "plan_goal": plan.goal,
            "step_id": step.id,
            "step_description": step.description,
            "step_type": step.step_type.value,
            "risk_level": step.risk_level.value,
            "security_related": step.security_related,
            "remaining_delegations": self.delegation_tracker.get_remaining(),
            "execution_stats": self.execution_stats.copy(),
        }
        
        # Add plan progress
        progress = plan.get_progress()
        state_summary["plan_progress"] = {
            "total_steps": progress["total"],
            "completed_steps": progress["completed"],
            "completion_percentage": progress["completion_percentage"],
        }
        
        # Create delegation context
        context = DelegationContext(
            from_model=self.current_model,
            to_model=target_model,
            task=step.description,
            handoff_notes=step.model_assignment_reason or f"Execute: {step.description}",
            state_summary=state_summary,
            delegation_tracker=self.delegation_tracker,
        )
        
        return context
    
    def _perform_auto_review(self, step: ModelAwarePlanStep, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Automatically review step execution results.
        
        Args:
            step: The step that was executed
            execution_result: Result from step execution
            
        Returns:
            Review result
        """
        logger.info(f"Performing auto-review for step: {step.description}")
        
        # Determine review model
        review_model = step.review_model or "gpt-5.1-codex-mini"
        if step.security_related:
            review_model = "dolphin-24b"  # Security reviews need security model
        
        # Build review task
        review_task = f"""
REVIEW TASK: {step.description}

EXECUTION RESULT TO REVIEW:
{execution_result.get('summary', 'No summary provided')}

REVIEW INSTRUCTIONS:
1. Check for correctness and completeness
2. Identify any issues or bugs
3. Verify security considerations
4. Suggest improvements if needed
5. Provide overall assessment
"""
        
        # Delegate review to review model
        review_result = self.tool_executor("delegate_to_model", {
            "model": review_model,
            "task": review_task,
            "handoff_notes": f"Auto-review of: {step.description}",
        })
        
        # Add review metadata
        if review_result.get("success", False):
            review_result["review_metadata"] = {
                "review_model": review_model,
                "reviewed_step": step.id,
                "review_timestamp": datetime.now().isoformat(),
            }
        
        return review_result
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics.
        
        Returns:
            Dictionary with execution statistics
        """
        stats = self.execution_stats.copy()
        stats.update({
            "current_model": self.current_model,
            "delegation_tracker": self.delegation_tracker.to_dict(),
            "remaining_delegations": self.delegation_tracker.get_remaining(),
            "total_delegations": self.delegation_tracker.delegation_count,
        })
        return stats
    
    def reset_execution_stats(self) -> None:
        """Reset execution statistics."""
        self.execution_stats = {
            "steps_executed": 0,
            "steps_delegated": 0,
            "delegation_violations": 0,
            "auto_reviews_performed": 0,
            "total_cost_estimated": 0.0,
        }
        logger.info("Execution statistics reset")
    
    def get_delegation_summary(self) -> str:
        """
        Get human-readable delegation summary.
        
        Returns:
            String summary of delegation activity
        """
        stats = self.get_execution_stats()
        tracker = self.delegation_tracker
        
        lines = [
            "## Delegation Summary",
            "",
            f"Current Model: {self.current_model}",
            f"Steps Executed: {stats['steps_executed']}",
            f"Steps Delegated: {stats['steps_delegated']}",
            f"Delegation Violations: {stats['delegation_violations']}",
            f"Auto Reviews: {stats['auto_reviews_performed']}",
            "",
            f"Delegations: {tracker.delegation_count}/{tracker.max_delegations}",
            f"Remaining: {tracker.get_remaining()}",
            "",
        ]
        
        if tracker.delegation_history:
            lines.append("Delegation History:")
            for record in tracker.delegation_history:
                lines.append(f"  {record.delegation_number}. {record.from_model} → {record.to_model}")
                lines.append(f"     Reason: {record.reason[:60]}...")
                lines.append("")
        
        return "\n".join(lines)