"""Planning tools for Cortex agent.

This module provides tools for monitoring and updating plans
using the PlanningEngine. These tools enable the LLM to work with structured
plans for complex multi-step tasks.
"""

import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import logging

from .base import Tool
from ..models import PermissionMode
from ..utils.errors import create_error_response, create_success_response, ErrorType
from ..core.planning import PlanningEngine, Plan, PlanStep, PlanStepStatus, PlanStepType

logger = logging.getLogger(__name__)


class MonitorPlanTool(Tool):
    """Tool for monitoring plan progress and status."""

    def __init__(
        self,
        project_dir,
        permission_mode="normal",
        console=None,
        timeout_config=None,
        transaction_manager=None,
        parent_agent=None,
    ):
        super().__init__(project_dir, permission_mode, console, timeout_config, transaction_manager)
        self.parent_agent = parent_agent

    def execute(
        self,
        plan_id: str,
        detail_level: str = "summary",  # "summary", "steps", "detailed"
    ) -> Dict[str, Any]:
        """
        Monitor a plan's progress and status.

        Args:
            plan_id: ID of the plan to monitor
            detail_level: Level of detail ("summary", "steps", "detailed")

        Returns:
            Dictionary with plan status and progress
        """
        if self.console:
            self.console.print(f"[cyan]Monitoring plan:[/cyan] {plan_id}")

        # Check if we have access to planning engine through parent agent
        if not hasattr(self, "parent_agent") or not self.parent_agent:
            return create_error_response(
                "Planning tools require enhanced agent with planning enabled",
                ErrorType.CONFIGURATION,
                {"hint": "Use --enhanced flag when starting Cortex"},
            )

        # Check if planning engine is available
        if (
            not hasattr(self, "parent_agent")
            or not self.parent_agent
            or not getattr(self.parent_agent, "planning_engine", None)
        ):  # noqa: E501
            return create_error_response(
                "Planning engine not available. Please restart with --enhanced flag.",
                ErrorType.CONFIGURATION,
                {"hint": "Use --enhanced flag when starting Cortex"},
            )

        try:
            planning_engine = self.parent_agent.planning_engine

            # Get plan by ID
            plan = planning_engine.get_plan(plan_id)
            if not plan:
                return create_error_response(
                    f"Plan not found: {plan_id}", ErrorType.NOT_FOUND, {"plan_id": plan_id}
                )

            # Get basic plan info
            progress = plan.get_progress()
            plan_summary = planning_engine.get_plan_summary(plan)

            result = {
                "plan_id": plan_id,
                "goal": plan.goal,
                "status": plan.status.value,
                "progress": progress,
                "summary": plan_summary,
                "step_count": len(plan.steps),
                "created_at": plan.created_at,
            }

            # Add started/completed times if available
            if plan.started_at:
                result["started_at"] = plan.started_at
            if plan.completed_at:
                result["completed_at"] = plan.completed_at

            # Add step details based on detail level
            if detail_level in ["steps", "detailed"]:
                steps_data = []
                for step in plan.steps:
                    step_info = {
                        "id": step.id,
                        "description": step.description,
                        "step_type": step.step_type.value,
                        "status": step.status.value,
                        "dependencies": step.dependencies,
                    }

                    if detail_level == "detailed":
                        step_info.update(
                            {
                                "expected_outcome": step.expected_outcome,
                                "actual_outcome": step.actual_outcome,
                                "tool_name": step.tool_name,
                                "skill_name": step.skill_name,
                                "started_at": step.started_at,
                                "completed_at": step.completed_at,
                                "error": step.error,
                            }
                        )

                    steps_data.append(step_info)

                result["steps"] = steps_data

            if self.console:
                completion_pct = progress.get("completion_percentage", 0)
                status_color = (
                    "green"
                    if plan.status == PlanStepStatus.COMPLETED
                    else "yellow"
                    if plan.status == PlanStepStatus.IN_PROGRESS
                    else "dim"
                )
                self.console.print(
                    f"[{status_color}]Plan status: {plan.status.value} ({completion_pct:.1f}%)[/{status_color}]"
                )  # noqa: E501

            return create_success_response(result)

        except Exception as e:
            logger.error(f"Failed to monitor plan: {e}", exc_info=True)
            return create_error_response(
                f"Failed to monitor plan: {str(e)}", ErrorType.EXECUTION, {"plan_id": plan_id}
            )


class UpdatePlanTool(Tool):
    """Tool for updating existing plans."""

    def __init__(
        self,
        project_dir,
        permission_mode="normal",
        console=None,
        timeout_config=None,
        transaction_manager=None,
        parent_agent=None,
    ):
        super().__init__(project_dir, permission_mode, console, timeout_config, transaction_manager)
        self.parent_agent = parent_agent

    def execute(
        self,
        plan_id: str,
        action: str,  # "add_step", "update_step", "remove_step", "reorder_steps"
        step_data: Optional[Dict[str, Any]] = None,
        step_id: Optional[str] = None,
        new_order: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing plan.

        Args:
            plan_id: ID of the plan to update
            action: Action to perform ("add_step", "update_step", "remove_step", "reorder_steps")
            step_data: Step data for add/update actions
            step_id: Step ID for update/remove actions
            new_order: New step order for reorder_steps action

        Returns:
            Dictionary with update results
        """
        if self.console:
            self.console.print(f"[cyan]Updating plan:[/cyan] {plan_id}")

        # Check if we have access to planning engine through parent agent
        if not hasattr(self, "parent_agent") or not self.parent_agent:
            return create_error_response(
                "Planning tools require enhanced agent with planning enabled",
                ErrorType.CONFIGURATION,
                {"hint": "Use --enhanced flag when starting Cortex"},
            )

        # Check if planning engine is available
        if (
            not hasattr(self, "parent_agent")
            or not self.parent_agent
            or not getattr(self.parent_agent, "planning_engine", None)
        ):  # noqa: E501
            return create_error_response(
                "Planning engine not available. Please restart with --enhanced flag.",
                ErrorType.CONFIGURATION,
                {"hint": "Use --enhanced flag when starting Cortex"},
            )

        try:
            planning_engine = self.parent_agent.planning_engine

            # Get plan by ID
            plan = planning_engine.get_plan(plan_id)
            if not plan:
                return create_error_response(
                    f"Plan not found: {plan_id}", ErrorType.NOT_FOUND, {"plan_id": plan_id}
                )

            # Perform requested action
            if action == "add_step" and step_data:
                # Add a new step to the plan
                description = step_data.get("description", "New step")
                step_type = PlanStepType(step_data.get("step_type", "tool_call"))
                tool_name = step_data.get("tool_name")
                tool_arguments = step_data.get("tool_arguments")

                step = planning_engine.add_step(
                    plan_id=plan_id,
                    description=description,
                    step_type=step_type,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments,
                )

                if not step:
                    return create_error_response(
                        "Failed to add step to plan", ErrorType.EXECUTION, {"plan_id": plan_id}
                    )

                result = {
                    "action": "add_step",
                    "plan_id": plan_id,
                    "step_id": step.id,
                    "new_step_count": len(plan.steps),
                }

            elif action == "update_step" and step_id and step_data:
                # Update an existing step
                # For now, we can only update step status through planning engine
                # More comprehensive step updates would require additional methods
                if "status" in step_data:
                    status = PlanStepStatus(step_data["status"])
                    error = step_data.get("error")

                    success = planning_engine.update_step_status(
                        plan_id=plan_id,
                        step_id=step_id,
                        status=status,
                        error=error,
                    )

                    if not success:
                        return create_error_response(
                            f"Failed to update step {step_id}",
                            ErrorType.EXECUTION,
                            {"plan_id": plan_id, "step_id": step_id},
                        )

                    result = {
                        "action": "update_step",
                        "plan_id": plan_id,
                        "step_id": step_id,
                        "status_updated": True,
                    }
                else:
                    return create_error_response(
                        "Only status updates are currently supported",
                        ErrorType.VALIDATION,
                        {"supported_updates": ["status"]},
                    )

            elif action == "remove_step" and step_id:
                # Remove a step from the plan
                # This would require additional functionality in PlanningEngine
                # For now, return not implemented
                return create_error_response(
                    "Step removal not yet implemented",
                    ErrorType.NOT_IMPLEMENTED,
                    {"plan_id": plan_id, "step_id": step_id},
                )

            elif action == "reorder_steps" and new_order:
                # Reorder steps in the plan
                # This would require additional functionality in PlanningEngine
                # For now, return not implemented
                return create_error_response(
                    "Step reordering not yet implemented",
                    ErrorType.NOT_IMPLEMENTED,
                    {"plan_id": plan_id},
                )

            else:
                return create_error_response(
                    f"Invalid action or missing parameters: {action}",
                    ErrorType.VALIDATION,
                    {
                        "valid_actions": [
                            "add_step",
                            "update_step",
                            "remove_step",
                            "reorder_steps",
                        ]
                    },
                )

            if self.console:
                self.console.print(f"[green]Plan updated successfully[/green]")

            return create_success_response(result)

        except Exception as e:
            logger.error(f"Failed to update plan: {e}", exc_info=True)
            return create_error_response(
                f"Failed to update plan: {str(e)}",
                ErrorType.EXECUTION,
                {"plan_id": plan_id, "action": action},
            )


class CreateAndExecutePlanTool(Tool):
    """Tool for creating and immediately executing a structured plan."""

    def __init__(
        self,
        project_dir,
        permission_mode="normal",
        console=None,
        timeout_config=None,
        transaction_manager=None,
        parent_agent=None,
    ):
        super().__init__(project_dir, permission_mode, console, timeout_config, transaction_manager)
        self.parent_agent = parent_agent

    def execute(
        self,
        goal: str,
        constraints: Optional[List[str]] = None,
        assumptions: Optional[List[str]] = None,
        skill_hints: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        max_steps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create and immediately execute a structured plan.

        Args:
            goal: The goal to achieve
            constraints: Constraints to consider
            assumptions: Assumptions to document
            skill_hints: Suggested skills to apply
            context: Additional context for planning
            steps: Concrete steps for the plan
            max_steps: Maximum number of steps to execute in this turn

        Returns:
            Dictionary with creation and execution results
        """
        if self.console:
            self.console.print(f"[cyan]🚀 Creating and executing plan for goal:[/cyan] {goal}")

        # Check if we have access to planning engine
        if (
            not hasattr(self, "parent_agent")
            or not self.parent_agent
            or not getattr(self.parent_agent, "planning_engine", None)
        ):  # noqa: E501
            return create_error_response(
                "Planning engine not available. Please restart with --enhanced flag.",
                ErrorType.CONFIGURATION,
                {"hint": "Use --enhanced flag to enable planning features"},
            )

        try:
            planning_engine = self.parent_agent.planning_engine

            # 1. Create the plan
            plan = planning_engine.create_plan(
                goal=goal,
                context=context,
                constraints=constraints,
                assumptions=assumptions,
                skill_hints=skill_hints,
                steps=steps,
            )

            # 2. Execute the plan
            execution_result = planning_engine.execute_plan(
                plan=plan,
                max_steps=max_steps,
                stop_on_failure=True,
            )

            # Get plan summary
            plan_summary = planning_engine.get_plan_summary(plan)

            result_data = {
                "plan_id": plan.id,
                "goal": plan.goal,
                "status": plan.status.value,
                "plan_summary": plan_summary,
                "execution_success": execution_result.get("success", False),
                "message": execution_result.get("message", ""),
                "steps_executed": len(execution_result.get("step_results", [])),
            }

            if "progress" in execution_result:
                result_data["progress"] = execution_result["progress"]

            return create_success_response(result_data)

        except Exception as e:
            logger.error(f"Failed to create and execute plan: {e}", exc_info=True)
            return create_error_response(
                f"Failed to create and execute plan: {str(e)}", ErrorType.EXECUTION
            )


CREATE_AND_EXECUTE_PLAN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_and_execute_plan",
        "description": (
            "The MOST POWERFUL planning tool. Atomic: Creates a plan AND starts execution immediately. "  # noqa: E501
            "Use this for complex tasks (4+ steps) to maintain autonomy and ensure all results are reported back. "  # noqa: E501
            "Provide a concrete list of `steps` for maximum effectiveness."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The goal to achieve",
                },
                "steps": {
                    "type": "array",
                    "description": "Concrete steps for the plan",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Clear action (e.g., 'Read agent.py')",
                            },
                            "tool_name": {
                                "type": "string",
                                "description": "The tool to use (e.g., 'read_file')",
                            },
                            "tool_arguments": {
                                "type": "object",
                                "description": "Arguments for the tool",
                                "additionalProperties": True,
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Step IDs that must finish first",
                            },
                            "id": {
                                "type": "string",
                                "description": "ID for this step (e.g., 'step_1')",
                            },
                        },
                        "required": ["description"],
                    },
                },
                "max_steps": {
                    "type": "integer",
                    "description": "Maximum steps to run in this turn",
                },
                "constraints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Constraints to consider",
                },
            },
            "required": ["goal", "steps"],
        },
    },
}

MONITOR_PLAN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "monitor_plan",
        "description": (
            "Monitor plan progress and status. Check completion percentage, "
            "step statuses, and execution details. Use to track progress of "
            "long-running plans or debug plan execution issues."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "ID of the plan to monitor",
                },
                "detail_level": {
                    "type": "string",
                    "enum": ["summary", "steps", "detailed"],
                    "description": "Level of detail in response (default: summary)",
                },
            },
            "required": ["plan_id"],
        },
    },
}

UPDATE_PLAN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "update_plan",
        "description": (
            "Update an existing plan. Add new steps, update step status, "
            "or modify plan structure. Use to adapt plans based on execution "
            "results or changing requirements."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "ID of the plan to update",
                },
                "action": {
                    "type": "string",
                    "enum": ["add_step", "update_step", "remove_step", "reorder_steps"],
                    "description": "Action to perform on the plan",
                },
                "step_data": {
                    "type": "object",
                    "description": "Step data for add/update actions",
                    "additionalProperties": True,
                },
                "step_id": {
                    "type": "string",
                    "description": "Step ID for update/remove actions",
                },
                "new_order": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New step order for reorder_steps action",
                },
            },
            "required": ["plan_id", "action"],
        },
    },
}
