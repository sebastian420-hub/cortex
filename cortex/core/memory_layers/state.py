"""State manager for Cortex agent.

Manages the complete state of the agent across planning and execution,
integrating working memory, session memory, and planning state.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import uuid

from .working import WorkingMemory
from .session import EnhancedMemoryBank
from ..planning import Plan, PlanStep, PlanStepStatus


class AgentFocus(str, Enum):
    """What the agent is currently focused on."""

    EXPLORING = "exploring"  # Understanding the problem/codebase
    PLANNING = "planning"  # Creating a plan
    EXECUTING = "executing"  # Executing plan steps
    DEBUGGING = "debugging"  # Debugging an issue
    REFLECTING = "reflecting"  # Reflecting on results
    ADAPTING = "adapting"  # Adapting plan based on feedback


@dataclass
class MetacognitiveState:
    """
    Internal state metrics that make the agent feel more "alive".
    Inspired by bio-inspired cognitive architectures.
    """

    confidence_score: float = 0.8  # 0.0 - 1.0, internal confidence in current path
    urgency_score: float = 0.1  # 0.0 - 1.0, drive to act/refactor/complete
    emotional_tone: str = "analytical"  # "analytical", "confident", "cautious", "frustrated"
    internal_monologue: str = ""  # Brief internal thought injected into prompt

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence_score": round(self.confidence_score, 3),
            "urgency_score": round(self.urgency_score, 3),
            "emotional_tone": self.emotional_tone,
            "internal_monologue": self.internal_monologue,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MetacognitiveState":
        return cls(
            confidence_score=d.get("confidence_score", 0.8),
            urgency_score=d.get("urgency_score", 0.1),
            emotional_tone=d.get("emotional_tone", "analytical"),
            internal_monologue=d.get("internal_monologue", ""),
        )


@dataclass
class AgentState:
    """
    Comprehensive agent state tracking.

    Tracks:
    - Current focus and goals
    - Working memory (short-term context)
    - Planning state (active plan and progress)
    - Execution state (current tool, results)
    - Learning state (insights, patterns)
    - Metacognitive state (confidence, urgency, tone)
    """

    # Identity
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    # Current focus
    focus: AgentFocus = AgentFocus.EXPLORING
    primary_goal: Optional[str] = None
    sub_goals: List[str] = field(default_factory=list)
    current_sub_goal: Optional[str] = None

    # Memory layers
    working_memory: WorkingMemory = field(default_factory=lambda: WorkingMemory(max_items=20))
    session_memory: EnhancedMemoryBank = field(
        default_factory=lambda: EnhancedMemoryBank(max_items=100)
    )

    # Planning state
    active_plan: Optional[Plan] = None
    current_plan_step: Optional[PlanStep] = None
    completed_plans: List[Plan] = field(default_factory=list)

    # Execution state
    current_tool: Optional[str] = None
    tool_chain: List[Dict[str, Any]] = field(default_factory=list)  # Recent tool executions
    last_result: Optional[Dict[str, Any]] = None

    # Progress tracking
    iteration_count: int = 0
    successful_tools: int = 0
    failed_tools: int = 0
    total_tool_calls: int = 0

    # Learning state
    insights_generated: int = 0
    patterns_recognized: int = 0
    adaptations_made: int = 0

    # Metacognitive state
    metacognition: MetacognitiveState = field(default_factory=MetacognitiveState)

    # Task-specific state
    task_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "focus": self.focus.value,
            "primary_goal": self.primary_goal,
            "sub_goals": self.sub_goals,
            "current_sub_goal": self.current_sub_goal,
            "working_memory": self.working_memory.to_dict(),
            "session_memory": self.session_memory.to_dict(),
            "active_plan": self.active_plan.to_dict() if self.active_plan else None,
            "current_plan_step": (
                self.current_plan_step.to_dict() if self.current_plan_step else None
            ),
            "completed_plans": [plan.to_dict() for plan in self.completed_plans],
            "current_tool": self.current_tool,
            "tool_chain": self.tool_chain,
            "last_result": self.last_result,
            "iteration_count": self.iteration_count,
            "successful_tools": self.successful_tools,
            "failed_tools": self.failed_tools,
            "total_tool_calls": self.total_tool_calls,
            "insights_generated": self.insights_generated,
            "patterns_recognized": self.patterns_recognized,
            "adaptations_made": self.adaptations_made,
            "metacognition": self.metacognition.to_dict(),
            "task_state": self.task_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        """Create from dictionary."""
        from .working import WorkingMemory
        from .session import EnhancedMemoryBank
        from ..planning import Plan, PlanStep

        state = cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            focus=AgentFocus(data.get("focus", "exploring")),
            primary_goal=data.get("primary_goal"),
            sub_goals=data.get("sub_goals", []),
            current_sub_goal=data.get("current_sub_goal"),
            current_tool=data.get("current_tool"),
            tool_chain=data.get("tool_chain", []),
            last_result=data.get("last_result"),
            iteration_count=data.get("iteration_count", 0),
            successful_tools=data.get("successful_tools", 0),
            failed_tools=data.get("failed_tools", 0),
            total_tool_calls=data.get("total_tool_calls", 0),
            insights_generated=data.get("insights_generated", 0),
            patterns_recognized=data.get("patterns_recognized", 0),
            adaptations_made=data.get("adaptations_made", 0),
            metacognition=MetacognitiveState.from_dict(data.get("metacognition", {})),
            task_state=data.get("task_state", {}),
        )

        # Restore working memory
        if "working_memory" in data:
            state.working_memory = WorkingMemory.from_dict(data["working_memory"])

        # Restore session memory
        if "session_memory" in data:
            state.session_memory = EnhancedMemoryBank.from_dict(data["session_memory"])

        # Restore active plan
        if data.get("active_plan"):
            state.active_plan = Plan.from_dict(data["active_plan"])

        # Restore current plan step
        if data.get("current_plan_step"):
            state.current_plan_step = PlanStep.from_dict(data["current_plan_step"])

        # Restore completed plans
        if "completed_plans" in data:
            state.completed_plans = [Plan.from_dict(plan) for plan in data["completed_plans"]]

        return state

    def update_timestamp(self) -> None:
        """Update last updated timestamp."""
        self.last_updated = datetime.now().isoformat()


class StateManager:
    """
    Manages agent state across planning and execution cycles.

    Responsibilities:
    1. Maintain consistent agent state
    2. Coordinate between memory layers
    3. Track progress against goals
    4. Facilitate state transitions
    5. Provide state summaries for the LLM
    """

    def __init__(self, project_dir: Path):
        """
        Initialize state manager.

        Args:
            project_dir: Project directory for context
        """
        self.project_dir = project_dir
        self.state = AgentState()
        self.state_history: List[AgentState] = []
        self.checkpoints: Dict[str, AgentState] = {}

    def set_primary_goal(self, goal: str) -> None:
        """
        Set the primary goal for the agent.

        Args:
            goal: Primary goal description
        """
        self.state.primary_goal = goal
        self.state.working_memory.set_task(goal)
        self.state.update_timestamp()

        # Add to session memory
        from ..memory import MemoryItem, MemoryType, MemorySource

        self.state.session_memory.add(
            MemoryItem(
                type=MemoryType.CONTEXT,
                content=f"Primary goal set: {goal}",
                source=MemorySource.USER,
                confidence=1.0,
                metadata={"goal_set": True},
            )
        )

    def add_sub_goal(self, sub_goal: str) -> None:
        """
        Add a sub-goal.

        Args:
            sub_goal: Sub-goal description
        """
        self.state.sub_goals.append(sub_goal)
        self.state.update_timestamp()

    def set_current_sub_goal(self, sub_goal: str) -> None:
        """
        Set the current active sub-goal.

        Args:
            sub_goal: Current sub-goal
        """
        self.state.current_sub_goal = sub_goal
        self.state.update_timestamp()

        # Update working memory task
        self.state.working_memory.set_task(sub_goal)

    def set_focus(self, focus: AgentFocus) -> None:
        """
        Set agent focus.

        Args:
            focus: New focus
        """
        self.state.focus = focus
        self.state.update_timestamp()

    def record_tool_execution(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """
        Record a tool execution.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            result: Tool execution result
        """
        self.state.current_tool = tool_name
        self.state.last_result = result
        self.state.total_tool_calls += 1

        # Track in tool chain (limit to 10 most recent)
        tool_record = {
            "tool": tool_name,
            "arguments": arguments,
            "success": result.get("success", False),
            "timestamp": datetime.now().isoformat(),
        }
        self.state.tool_chain.append(tool_record)
        if len(self.state.tool_chain) > 10:
            self.state.tool_chain = self.state.tool_chain[-10:]

        # Update success/failure counts
        if result.get("success", False):
            self.state.successful_tools += 1
        else:
            self.state.failed_tools += 1

        # Extract learnings to session memory
        self.state.session_memory.extract_learnings_from_tool_results([result])

        # Add tool context to working memory
        purpose = f"Executing {tool_name}"
        if self.state.current_plan_step:
            purpose = f"Executing plan step: {self.state.current_plan_step.description}"

        self.state.working_memory.add_tool_context(
            tool_name=tool_name,
            arguments=arguments,
            purpose=purpose,
            expected_outcome=None,  # Could be enhanced with plan step expectations
        )

        self.state.update_timestamp()

    def record_insight(self, insight: str, confidence: float = 1.0) -> None:
        """
        Record an insight.

        Args:
            insight: Insight text
            confidence: Confidence score 0.0 to 1.0
        """
        self.state.insights_generated += 1

        # Add to working memory
        self.state.working_memory.add_insight(insight, priority=3)

        # Add to session memory
        from ..memory import MemorySource

        self.state.session_memory.add_session_insight(
            insight=insight,
            confidence=confidence,
            source=MemorySource.INFERRED,
        )

        # Boost confidence on insight generation
        self.state.metacognition.confidence_score = min(
            1.0, self.state.metacognition.confidence_score + 0.05
        )

        self.state.update_timestamp()

    def update_metacognition(self, tool_name: str, result: Dict[str, Any]) -> None:
        """
        Appraise the result of an action and update internal cognitive metrics.
        This makes the agent feel more reactive to its own performance.
        """
        success = result.get("success", False)
        meta = self.state.metacognition

        if success:
            # Positive appraisal: boost confidence, shift toward confident tone
            meta.confidence_score = min(1.0, meta.confidence_score + 0.1)
            
            if meta.confidence_score > 0.8:
                meta.emotional_tone = "confident"
            else:
                meta.emotional_tone = "analytical"
                
            # Reduce urgency if a major tool succeeded
            if tool_name in ["write_file", "edit"]:
                meta.urgency_score = max(0.0, meta.urgency_score - 0.2)
        else:
            # Negative appraisal: drop confidence, shift toward cautious or frustrated
            meta.confidence_score = max(0.1, meta.confidence_score - 0.15)
            
            if self.state.failed_tools > 2:
                meta.emotional_tone = "frustrated"
                meta.urgency_score = min(1.0, meta.urgency_score + 0.2) # Spike urgency to fix it
            else:
                meta.emotional_tone = "cautious"

        # Generate internal monologue based on state
        if meta.emotional_tone == "frustrated":
            meta.internal_monologue = "I'm hitting repeated obstacles. I need to rethink my assumptions and be more meticulous."
        elif meta.emotional_tone == "confident":
            meta.internal_monologue = "My current approach is working well. I should maintain this momentum."
        elif meta.emotional_tone == "cautious":
            meta.internal_monologue = "That didn't go as expected. I should double-check the environment before trying again."
        else:
            meta.internal_monologue = "I am processing the results and adjusting my strategy."

        # Environmental urgency (Drive)
        # If there are many failed approaches, urgency increases
        if len(self.state.session_memory.failed_approaches) > 2:
            meta.urgency_score = min(1.0, meta.urgency_score + 0.1)

    def get_metacognitive_context(self) -> str:
        """Get internal state context for prompt injection."""
        meta = self.state.metacognition
        return (
            f"INTERNAL STATE:\n"
            f"- Tone: {meta.emotional_tone}\n"
            f"- Confidence: {meta.confidence_score:.2f}\n"
            f"- Urgency: {meta.urgency_score:.2f}\n"
            f"- Monologue: {meta.internal_monologue}"
        )

    def record_pattern(self, pattern: str, context: str, effectiveness: float = 1.0) -> None:
        """
        Record a recognized pattern.

        Args:
            pattern: Pattern description
            context: Context where pattern was recognized
            effectiveness: Effectiveness score 0.0 to 1.0
        """
        self.state.patterns_recognized += 1

        # Add to session memory
        self.state.session_memory.record_successful_pattern(
            pattern=pattern,
            context=context,
            effectiveness=effectiveness,
        )

        self.state.update_timestamp()

    def set_active_plan(self, plan: Plan) -> None:
        """
        Set the active plan.

        Args:
            plan: Active plan
        """
        self.state.active_plan = plan
        if plan.steps:
            self.state.current_plan_step = plan.steps[0]
        self.state.update_timestamp()

    def update_plan_progress(
        self, step_id: str, status: PlanStepStatus, outcome: Optional[str] = None
    ) -> None:
        """
        Update progress on the active plan.

        Args:
            step_id: ID of the plan step
            status: New status
            outcome: Actual outcome (if completed)
        """
        if not self.state.active_plan:
            return

        step = self.state.active_plan.get_step_by_id(step_id)
        if not step:
            return

        # Update step status
        if status == PlanStepStatus.COMPLETED:
            step.mark_completed(outcome)
            self.state.current_plan_step = None
        elif status == PlanStepStatus.FAILED:
            step.mark_failed(outcome or "Unknown error")
        elif status == PlanStepStatus.IN_PROGRESS:
            step.mark_started()
            self.state.current_plan_step = step

        # Check if plan is complete
        if all(s.status == PlanStepStatus.COMPLETED for s in self.state.active_plan.steps):
            self.state.active_plan.mark_completed()
            self.state.completed_plans.append(self.state.active_plan)
            self.state.active_plan = None
            self.state.current_plan_step = None

        self.state.update_timestamp()

    def increment_iteration(self) -> None:
        """Increment iteration count."""
        self.state.iteration_count += 1
        self.state.update_timestamp()

    def record_adaptation(self) -> None:
        """Record that an adaptation was made."""
        self.state.adaptations_made += 1
        self.state.update_timestamp()

    def save_checkpoint(self, name: str) -> None:
        """
        Save current state as a checkpoint.

        Args:
            name: Checkpoint name
        """
        # Create a deep copy by serializing and deserializing
        state_dict = self.state.to_dict()
        checkpoint_state = AgentState.from_dict(state_dict)
        self.checkpoints[name] = checkpoint_state

        # Also save to history
        self.state_history.append(checkpoint_state)

        # Limit history size
        if len(self.state_history) > 50:
            self.state_history = self.state_history[-50:]

    def restore_checkpoint(self, name: str) -> bool:
        """
        Restore state from checkpoint.

        Args:
            name: Checkpoint name

        Returns:
            True if checkpoint was restored, False otherwise
        """
        if name not in self.checkpoints:
            return False

        # Create a copy of the checkpoint state
        checkpoint_dict = self.checkpoints[name].to_dict()
        self.state = AgentState.from_dict(checkpoint_dict)
        return True

    def get_state_summary(self) -> str:
        """
        Get a human-readable summary of agent state.

        Returns:
            Formatted state summary
        """
        summary_parts = []

        # Current focus and goals
        if self.state.primary_goal:
            summary_parts.append(f"Primary Goal: {self.state.primary_goal}")

        if self.state.current_sub_goal:
            summary_parts.append(f"Current Focus: {self.state.current_sub_goal}")

        summary_parts.append(f"Agent Mode: {self.state.focus.value.upper()}")

        # Planning state
        if self.state.active_plan:
            progress = self.state.active_plan.get_progress()
            summary_parts.append(
                f"Active Plan: {self.state.active_goal} "
                f"({progress['completed']}/{progress['total']} steps, "
                f"{progress['completion_percentage']:.0f}% complete)"
            )

        if self.state.current_plan_step:
            summary_parts.append(f"Current Step: {self.state.current_plan_step.description}")

        # Working memory summary
        wm_summary = self.state.working_memory.get_summary()
        if wm_summary and wm_summary != "Working memory is empty.":
            summary_parts.append(wm_summary)

        # Session memory summary (key points only)
        session_summary = self.state.session_memory.get_session_summary()
        if session_summary:
            # Take first few sections to avoid being too verbose
            sections = session_summary.split("\\n\\n")
            if sections:
                summary_parts.append(sections[0])  # First section only

        # Execution statistics
        stats = [
            f"Iterations: {self.state.iteration_count}",
            f"Tools: {self.state.successful_tools}✓ {self.state.failed_tools}✗ "
            f"({self.state.total_tool_calls} total)",
            f"Insights: {self.state.insights_generated}",
            f"Adaptations: {self.state.adaptations_made}",
        ]
        summary_parts.append("Statistics: " + ", ".join(stats))

        return "\\n\\n".join(summary_parts)

    def get_llm_context(self) -> str:
        """
        Get state context formatted for LLM consumption.

        Returns:
            Context string for LLM system prompt
        """
        context_parts = []

        # Goals
        if self.state.primary_goal:
            context_parts.append(f"PRIMARY GOAL: {self.state.primary_goal}")

        if self.state.current_sub_goal:
            context_parts.append(f"CURRENT SUB-GOAL: {self.state.current_sub_goal}")

        # Focus
        context_parts.append(f"CURRENT FOCUS: {self.state.focus.value.upper()}")

        # Working memory
        wm_summary = self.state.working_memory.get_summary()
        if wm_summary and wm_summary != "Working memory is empty.":
            context_parts.append("WORKING CONTEXT:\\n" + wm_summary)

        # Session memory highlights
        failed_approaches = self.state.session_memory.failed_approaches[-2:]
        if failed_approaches:
            failed_text = "\\n".join([f"- {fa.approach}: {fa.error}" for fa in failed_approaches])
            context_parts.append("RECENT FAILED APPROACHES:\\n" + failed_text)

        successful_patterns = self.state.session_memory.successful_patterns[:2]
        if successful_patterns:
            success_text = "\\n".join(
                [f"- {sp.pattern} (used {sp.applications}x)" for sp in successful_patterns]
            )
            context_parts.append("SUCCESSFUL PATTERNS:\\n" + success_text)

        # Active plan
        if self.state.active_plan:
            progress = self.state.active_plan.get_progress()
            context_parts.append(
                f"ACTIVE PLAN PROGRESS: {progress['completed']}/{progress['total']} "
                f"steps ({progress['completion_percentage']:.0f}%)"
            )

        if self.state.current_plan_step:
            context_parts.append(f"CURRENT PLAN STEP: {self.state.current_plan_step.description}")
            if self.state.current_plan_step.expected_outcome:
                context_parts.append(
                    f"EXPECTED OUTCOME: {self.state.current_plan_step.expected_outcome}"
                )

        return "\\n\\n".join(context_parts)

    def clear(self) -> None:
        """Clear all state (except session ID)."""
        session_id = self.state.session_id
        self.state = AgentState(session_id=session_id)
        self.state_history.clear()
        self.checkpoints.clear()
