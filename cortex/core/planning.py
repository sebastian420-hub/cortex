"""Planning engine for structured task planning and execution."""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Union, Callable
from pathlib import Path

from ..utils.errors import create_error_response, create_success_response, ErrorType
from ..ui.console import console
from ..ui.plan_progress import PlanProgressDisplay

logger = logging.getLogger(__name__)


class PlanStepStatus(str, Enum):
    """Status of a plan step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStepType(str, Enum):
    """Type of plan step."""

    TOOL_CALL = "tool_call"
    SUBTASK = "subtask"
    DECISION = "decision"
    CHECKPOINT = "checkpoint"
    REFLECTION = "reflection"
    SKILL_APPLICATION = "skill_application"


@dataclass
class PlanStep:
    """A single step in a plan."""

    id: str
    description: str
    step_type: PlanStepType = PlanStepType.TOOL_CALL
    status: PlanStepStatus = PlanStepStatus.PENDING
    dependencies: List[str] = field(default_factory=list)  # IDs of steps that must complete first
    expected_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    tool_name: Optional[str] = None  # For TOOL_CALL steps
    tool_arguments: Optional[Dict[str, Any]] = None  # For TOOL_CALL steps
    skill_name: Optional[str] = None  # For SKILL_APPLICATION steps
    skill_params: Optional[Dict[str, Any]] = None  # For SKILL_APPLICATION steps
    subtask_description: Optional[str] = None  # For SUBTASK steps
    decision_point: Optional[str] = None  # For DECISION steps
    checkpoint_name: Optional[str] = None  # For CHECKPOINT steps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "description": self.description,
            "step_type": self.step_type.value,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "tool_name": self.tool_name,
            "tool_arguments": self.tool_arguments,
            "skill_name": self.skill_name,
            "skill_params": self.skill_params,
            "subtask_description": self.subtask_description,
            "decision_point": self.decision_point,
            "checkpoint_name": self.checkpoint_name,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            step_type=PlanStepType(data["step_type"]),
            status=PlanStepStatus(data["status"]),
            dependencies=data.get("dependencies", []),
            expected_outcome=data.get("expected_outcome"),
            actual_outcome=data.get("actual_outcome"),
            tool_name=data.get("tool_name"),
            tool_arguments=data.get("tool_arguments"),
            skill_name=data.get("skill_name"),
            skill_params=data.get("skill_params"),
            subtask_description=data.get("subtask_description"),
            decision_point=data.get("decision_point"),
            checkpoint_name=data.get("checkpoint_name"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )

    def mark_started(self) -> None:
        """Mark step as started."""
        self.status = PlanStepStatus.IN_PROGRESS
        self.started_at = datetime.now().isoformat()

    def mark_completed(self, actual_outcome: Optional[str] = None) -> None:
        """Mark step as completed."""
        self.status = PlanStepStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        if actual_outcome is not None:
            self.actual_outcome = actual_outcome

    def mark_failed(self, error: str) -> None:
        """Mark step as failed."""
        self.status = PlanStepStatus.FAILED
        self.completed_at = datetime.now().isoformat()
        self.error = error

    def mark_skipped(self, reason: Optional[str] = None) -> None:
        """Mark step as skipped."""
        self.status = PlanStepStatus.SKIPPED
        self.completed_at = datetime.now().isoformat()
        if reason:
            self.actual_outcome = f"Skipped: {reason}"


@dataclass
class Plan:
    """A complete plan for achieving a goal."""

    id: str
    goal: str
    description: Optional[str] = None
    steps: List[PlanStep] = field(default_factory=list)
    status: PlanStepStatus = PlanStepStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    success_criteria: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    priority: int = 1  # 1=low, 5=critical
    estimated_duration_minutes: Optional[int] = None
    actual_duration_minutes: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self):
        return len(self.steps)

    def __getitem__(self, index):
        return self.steps[index]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "goal": self.goal,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "success_criteria": self.success_criteria,
            "constraints": self.constraints,
            "assumptions": self.assumptions,
            "priority": self.priority,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "actual_duration_minutes": self.actual_duration_minutes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            goal=data["goal"],
            description=data.get("description"),
            steps=[PlanStep.from_dict(step) for step in data.get("steps", [])],
            status=PlanStepStatus(data["status"]),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            success_criteria=data.get("success_criteria", []),
            constraints=data.get("constraints", []),
            assumptions=data.get("assumptions", []),
            priority=data.get("priority", 1),
            estimated_duration_minutes=data.get("estimated_duration_minutes"),
            actual_duration_minutes=data.get("actual_duration_minutes"),
            metadata=data.get("metadata", {}),
        )

    def add_step(self, step: PlanStep) -> None:
        """Add a step to the plan."""
        self.steps.append(step)

    def get_step_by_id(self, step_id: str) -> Optional[PlanStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_ready_steps(self) -> List[PlanStep]:
        """Get steps that are pending and have all dependencies satisfied."""
        ready_steps = []

        for step in self.steps:
            if step.status != PlanStepStatus.PENDING:
                continue

            # Check if all dependencies are completed
            all_deps_completed = True
            for dep_id in step.dependencies:
                dep_step = self.get_step_by_id(dep_id)
                if not dep_step or dep_step.status != PlanStepStatus.COMPLETED:
                    all_deps_completed = False
                    break

            if all_deps_completed:
                ready_steps.append(step)

        return ready_steps

    def mark_started(self) -> None:
        """Mark plan as started."""
        self.status = PlanStepStatus.IN_PROGRESS
        self.started_at = datetime.now().isoformat()

    def mark_completed(self) -> None:
        """Mark plan as completed."""
        self.status = PlanStepStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        if self.started_at:
            start_dt = datetime.fromisoformat(self.started_at)
            end_dt = datetime.fromisoformat(self.completed_at)
            self.actual_duration_minutes = (end_dt - start_dt).total_seconds() / 60

    def mark_failed(self) -> None:
        """Mark plan as failed."""
        self.status = PlanStepStatus.FAILED
        self.completed_at = datetime.now().isoformat()

    def get_progress(self) -> Dict[str, Any]:
        """Get plan progress statistics."""
        total = len(self.steps)
        completed = sum(1 for step in self.steps if step.status == PlanStepStatus.COMPLETED)
        in_progress = sum(1 for step in self.steps if step.status == PlanStepStatus.IN_PROGRESS)
        pending = sum(1 for step in self.steps if step.status == PlanStepStatus.PENDING)
        failed = sum(1 for step in self.steps if step.status == PlanStepStatus.FAILED)

        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "failed": failed,
            "completion_percentage": (completed / total * 100) if total > 0 else 0,
        }


class PlanningEngine:
    """
    Engine for generating, executing, and monitoring plans.

    The planning engine:
    1. Generates structured plans from goals
    2. Executes plan steps in dependency order
    3. Monitors progress and adapts as needed
    4. Reflects on outcomes to improve future planning
    """

    def __init__(
        self,
        project_dir: Union[str, Path] = ".",
        skill_loader: Optional[Callable[[str], Dict[str, Any]]] = None,
        tool_executor: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        reflection_callback: Optional[Callable[[Plan, str], None]] = None,
        max_plan_steps: int = 100,
    ):
        """
        Initialize planning engine.

        Args:
            project_dir: Project directory for context
            skill_loader: Function to load skills by name
            tool_executor: Function to execute tools by name and arguments
            reflection_callback: Callback for reflection events
            max_plan_steps: Maximum number of steps in a plan
        """
        self.project_dir = Path(project_dir).resolve()
        self.skill_loader = skill_loader
        self.tool_executor = tool_executor
        self.reflection_callback = reflection_callback
        self.max_plan_steps = max_plan_steps
        self.active_plan: Optional[Plan] = None
        self.plans: Dict[str, Plan] = {}
        self.progress_display = PlanProgressDisplay()

    def create_plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        constraints: Optional[List[str]] = None,
        assumptions: Optional[List[str]] = None,
        skill_hints: Optional[List[str]] = None,
    ) -> Plan:
        """
        Generate a plan for achieving a goal.

        Args:
            goal: The goal to achieve
            context: Additional context for planning
            constraints: Constraints to consider
            assumptions: Assumptions to document
            skill_hints: Suggested skills to apply

        Returns:
            A Plan object with steps to achieve the goal
        """
        # Generate a unique ID for the plan
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(goal) % 10000:04d}"

        plan = Plan(
            id=plan_id,
            goal=goal,
            description=f"Plan to achieve: {goal}",
            constraints=constraints or [],
            assumptions=assumptions or [],
        )

        # Add an initial analysis step
        analysis_step = PlanStep(
            id=f"{plan_id}_step_1",
            description=f"Analyze requirements for: {goal}",
            step_type=PlanStepType.SUBTASK,
            expected_outcome="Clear understanding of requirements and approach",
        )
        plan.add_step(analysis_step)

        # If skill hints provided, add skill application steps
        if skill_hints:
            for i, skill in enumerate(skill_hints[:3]):  # Limit to 3 skills
                skill_step = PlanStep(
                    id=f"{plan_id}_skill_{i+2}",
                    description=f"Apply {skill} skill to achieve goal",
                    step_type=PlanStepType.SKILL_APPLICATION,
                    skill_name=skill,
                    dependencies=[analysis_step.id],
                )
                plan.add_step(skill_step)

        self.active_plan = plan
        self.plans[plan.id] = plan

        logger.info(f"Generated plan {plan.id} for goal: {goal} with {len(plan.steps)} steps")
        return plan

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID."""
        return self.plans.get(plan_id)

    def add_step(
        self,
        plan_id: str,
        description: str,
        step_type: PlanStepType = PlanStepType.TOOL_CALL,
        tool_name: Optional[str] = None,
        tool_arguments: Optional[Dict[str, Any]] = None,
    ) -> Optional[PlanStep]:
        """Add a step to a plan."""
        plan = self.get_plan(plan_id)
        if plan is None:
            return None

        step_id = f"{plan_id}_step_{len(plan.steps) + 1}"
        step = PlanStep(
            id=step_id,
            description=description,
            step_type=step_type,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
        )
        plan.add_step(step)
        return step

    def update_step_status(
        self, plan_id: str, step_id: str, status: PlanStepStatus, error: Optional[str] = None
    ) -> bool:
        """Update the status of a step."""
        plan = self.get_plan(plan_id)
        if plan is None:
            return False

        step = plan.get_step_by_id(step_id)
        if step is None:
            return False

        step.status = status
        if status == PlanStepStatus.IN_PROGRESS:
            step.mark_started()
        elif status == PlanStepStatus.COMPLETED:
            step.mark_completed()
        elif status == PlanStepStatus.FAILED:
            step.mark_failed(error or "Unknown error")
        elif status == PlanStepStatus.SKIPPED:
            step.mark_skipped()

        return True

    def execute_step(self, plan_id: str, step_id: str) -> Dict[str, Any]:
        """Execute a single plan step by ID."""
        plan = self.get_plan(plan_id)
        if plan is None:
            return create_error_response(f"Plan not found: {plan_id}", ErrorType.NOT_FOUND)

        step = plan.get_step_by_id(step_id)
        if step is None:
            return create_error_response(f"Step not found: {step_id}", ErrorType.NOT_FOUND)

        step.mark_started()

        try:
            result = self._execute_step(step, plan)

            if result["success"]:
                step.mark_completed(result.get("content"))
                logger.info(f"Step {step.id} completed: {step.description}")
            else:
                step.mark_failed(result.get("error", "Unknown error"))
                logger.error(f"Step {step.id} failed: {result.get('error')}")

            return result
        except Exception as e:
            step.mark_failed(str(e))
            logger.exception(f"Exception executing step {step.id}")
            return create_error_response(
                f"Exception executing step {step.id}: {str(e)}", ErrorType.EXECUTION
            )

    def execute_plan(
        self,
        plan: Optional[Plan] = None,
        max_steps: Optional[int] = None,
        stop_on_failure: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a plan step by step.

        Args:
            plan: Plan to execute (uses active plan if None)
            max_steps: Maximum number of steps to execute
            stop_on_failure: Stop execution if a step fails

        Returns:
            Dictionary with execution results
        """
        if plan is None:
            plan = self.active_plan

        if plan is None:
            return create_error_response("No plan to execute", ErrorType.VALIDATION)

        plan.mark_started()
        steps_executed = 0
        step_results = []

        # Show plan overview using progress display
        self.progress_display.show_plan_overview(plan)
        self.progress_display.start_progress_bar(len(plan.steps), f"Executing: {plan.goal[:40]}...")

        while True:
            # Check if we've reached max steps
            if max_steps is not None and steps_executed >= max_steps:
                logger.info(f"Reached maximum steps ({max_steps}), stopping execution")
                break

            # Get ready steps
            ready_steps = plan.get_ready_steps()

            # If no ready steps, check if plan is complete
            if not ready_steps:
                # Check if all steps are completed
                all_completed = all(
                    step.status
                    in [PlanStepStatus.COMPLETED, PlanStepStatus.SKIPPED, PlanStepStatus.FAILED]
                    for step in plan.steps
                )
                if all_completed:
                    plan.mark_completed()
                    # Show plan completion summary
                    self.progress_display.stop_progress_bar()
                    self.progress_display.show_plan_complete(plan)
                    self.progress_display.show_execution_summary(plan, step_results)

                    return create_success_response(
                        {
                            "message": "Plan execution completed",
                            "plan_id": plan.id,
                            "progress": plan.get_progress(),
                            "step_results": step_results,
                        }
                    )
                else:
                    # Some steps are still pending but dependencies not met
                    # This shouldn't happen if dependency graph is correct
                    logger.warning(f"Plan {plan.id} has pending steps but none are ready")
                    return create_error_response(
                        "Plan stuck: pending steps but dependencies not satisfied",
                        ErrorType.EXECUTION,
                        context={
                            "plan_id": plan.id,
                            "progress": plan.get_progress(),
                        },
                    )

            # Execute the first ready step
            step = ready_steps[0]
            step.mark_started()

            # Show step start
            step_number = steps_executed + 1
            self.progress_display.show_step_start(step, step_number, len(plan.steps))

            try:
                result = self._execute_step(step, plan)

                if result["success"]:
                    step.mark_completed(result.get("content"))
                    logger.info(f"Step {step.id} completed: {step.description}")
                    outcome = result.get("content") or result.get("outcome") or "Completed"
                    self.progress_display.show_step_complete(step, outcome)
                    self.progress_display.update_progress(1)
                else:
                    step.mark_failed(result.get("error", "Unknown error"))
                    logger.error(f"Step {step.id} failed: {result.get('error')}")
                    error_msg = result.get("error", "Unknown error")
                    self.progress_display.show_step_failed(step, error_msg)

                    if stop_on_failure:
                        plan.mark_failed()
                        self.progress_display.stop_progress_bar()
                        self.progress_display.show_plan_failed(plan, error_msg)
                        return create_error_response(
                            f"Step {step.id} failed: {result.get('error')}",
                            ErrorType.EXECUTION,
                            context={
                                "plan_id": plan.id,
                                "failed_step": step.id,
                                "progress": plan.get_progress(),
                            },
                        )

            except Exception as e:
                step.mark_failed(str(e))
                logger.exception(f"Exception executing step {step.id}")
                self.progress_display.show_step_failed(step, f"Exception: {str(e)}")

                if stop_on_failure:
                    plan.mark_failed()
                    self.progress_display.stop_progress_bar()
                    self.progress_display.show_plan_failed(plan, str(e))
                    return create_error_response(
                        f"Exception executing step {step.id}: {str(e)}",
                        ErrorType.EXECUTION,
                        context={
                            "plan_id": plan.id,
                            "failed_step": step.id,
                            "progress": plan.get_progress(),
                        },
                    )

            step_results.append(result)
            steps_executed += 1

        # Plan execution paused (max_steps reached)
        self.progress_display.stop_progress_bar()
        return create_success_response(
            {
                "message": f"Plan execution paused after {steps_executed} steps",
                "plan_id": plan.id,
                "progress": plan.get_progress(),
            }
        )

    def _execute_step(self, step: PlanStep, plan: Plan) -> Dict[str, Any]:
        """Execute a single plan step."""

        if step.step_type == PlanStepType.TOOL_CALL and step.tool_name and self.tool_executor:
            # Execute tool call
            return self.tool_executor(step.tool_name, step.tool_arguments or {})

        elif (
            step.step_type == PlanStepType.SKILL_APPLICATION
            and step.skill_name
            and self.skill_loader
        ):
            # Apply a skill
            skill = self.skill_loader(step.skill_name)
            if not skill:
                return create_error_response(
                    f"Skill not found: {step.skill_name}", ErrorType.NOT_FOUND
                )

            # For now, just return success
            # In a real implementation, this would execute the skill workflow
            return create_success_response(
                {
                    "outcome": f"Applied skill: {step.skill_name}",
                    "skill": step.skill_name,
                }
            )

        elif step.step_type == PlanStepType.SUBTASK:
            # For subtask steps, we need to generate a sub-plan
            # This is a placeholder for now
            return create_success_response(
                {
                    "outcome": f"Analyzed: {step.description}",
                    "subtask": step.description,
                }
            )

        elif step.step_type == PlanStepType.CHECKPOINT:
            # Checkpoint steps verify progress
            return create_success_response(
                {
                    "outcome": f"Checkpoint '{step.checkpoint_name}' reached",
                    "checkpoint": step.checkpoint_name,
                }
            )

        elif step.step_type == PlanStepType.DECISION:
            # Decision points require user input or rule-based decision
            # This is a placeholder
            return create_success_response(
                {
                    "outcome": f"Decision made at: {step.decision_point}",
                    "decision": step.decision_point,
                }
            )

        elif step.step_type == PlanStepType.REFLECTION:
            # Trigger reflection
            if self.reflection_callback:
                self.reflection_callback(plan, step.description)
            return create_success_response(
                {
                    "outcome": "Reflection completed",
                    "reflection": step.description,
                }
            )

        else:
            # Unknown step type or missing executor
            return create_error_response(
                f"Cannot execute step type: {step.step_type}",
                ErrorType.EXECUTION,
            )

    def reflect_on_plan(
        self,
        plan: Optional[Plan] = None,
        focus_areas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Reflect on plan progress and suggest improvements.

        Args:
            plan: Plan to reflect on (uses active plan if None)
            focus_areas: Specific areas to focus reflection on

        Returns:
            Dictionary with reflection insights and suggestions
        """
        if plan is None:
            plan = self.active_plan

        if plan is None:
            return create_error_response("No plan to reflect on", ErrorType.VALIDATION)

        progress = plan.get_progress()

        # Simple reflection logic
        insights = []
        suggestions = []

        # Analyze failed steps
        failed_steps = [step for step in plan.steps if step.status == PlanStepStatus.FAILED]
        if failed_steps:
            insights.append(f"{len(failed_steps)} steps failed")
            suggestions.append("Review failed steps and adjust approach")

        # Check for stuck plan
        if progress["completion_percentage"] < 50 and plan.started_at:
            # Plan started but not making progress
            start_dt = datetime.fromisoformat(plan.started_at)
            age_minutes = (datetime.now() - start_dt).total_seconds() / 60

            if age_minutes > 30:  # 30 minutes without progress
                insights.append("Plan appears stuck (little progress in 30+ minutes)")
                suggestions.append("Consider breaking goal into smaller sub-goals")

        # Check for skill gaps
        skill_steps = [
            step for step in plan.steps if step.step_type == PlanStepType.SKILL_APPLICATION
        ]
        if skill_steps:
            insights.append(f"{len(skill_steps)} skill application steps in plan")

        # Generate reflection result
        reflection_id = f"reflect_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if self.reflection_callback:
            reflection_message = f"Plan {plan.id} Reflection: Insights: {', '.join(insights)}. Suggestions: {', '.join(suggestions)}."
            self.reflection_callback(plan, reflection_message)

        result = create_success_response(
            {
                "reflection_id": reflection_id,
                "plan_id": plan.id,
                "progress_summary": progress,
                "insights": insights,
                "suggestions": suggestions,
                "focus_areas": focus_areas or [],
                "timestamp": datetime.now().isoformat(),
            }
        )

        logger.info(f"Reflection {reflection_id} completed for plan {plan.id}")
        return result

    def save_plan(self, plan: Plan, filepath: Union[str, Path]) -> bool:
        """Save plan to file."""
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, "w") as f:
                json.dump(plan.to_dict(), f, indent=2)

            logger.info(f"Plan {plan.id} saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save plan: {e}")
            return False

    def load_plan(self, filepath: Union[str, Path]) -> Optional[Plan]:
        """Load plan from file."""
        try:
            filepath = Path(filepath)

            with open(filepath, "r") as f:
                data = json.load(f)

            plan = Plan.from_dict(data)
            logger.info(f"Plan {plan.id} loaded from {filepath}")
            return plan
        except Exception as e:
            logger.error(f"Failed to load plan: {e}")
            return None

    def get_plan_summary(self, plan: Optional[Plan] = None) -> str:
        """Get a human-readable summary of a plan."""
        if plan is None:
            plan = self.active_plan

        if plan is None:
            return "No active plan"

        progress = plan.get_progress()

        summary_lines = [
            f"# Plan: {plan.id}",
            f"Goal: {plan.goal}",
            f"Status: {plan.status.value}",
            f"Progress: {progress['completed']}/{progress['total']} steps ({progress['completion_percentage']:.1f}%)",
            "",
            "## Steps:",
        ]

        for step in plan.steps:
            status_icon = {
                PlanStepStatus.PENDING: "[ ]",
                PlanStepStatus.IN_PROGRESS: "[>]",
                PlanStepStatus.COMPLETED: "[V]",
                PlanStepStatus.FAILED: "[X]",
                PlanStepStatus.SKIPPED: "[S]",
            }.get(step.status, "[?]")

            summary_lines.append(f"{status_icon} [{step.step_type.value}] {step.description}")

        return "\n".join(summary_lines)
