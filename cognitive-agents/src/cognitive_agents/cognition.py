from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DriveType(str, Enum):
    SURVIVAL = "survival"
    SAFETY = "safety"
    SOCIAL = "social"
    ESTEEM = "esteem"
    PURPOSE = "purpose"
    CODE_QUALITY = "code_quality"
    TASK_COMPLETION = "task_completion"
    EXPLORATION = "exploration"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass
class Drive:
    drive_type: DriveType
    urgency: float = 0.0  # 0.0 - 1.0, computed from game state

    def to_dict(self) -> dict:
        return {"drive_type": self.drive_type.value, "urgency": round(self.urgency, 3)}

    @staticmethod
    def from_dict(d: dict) -> Drive:
        return Drive(drive_type=DriveType(d["drive_type"]), urgency=d.get("urgency", 0.0))


@dataclass
class Goal:
    description: str
    priority: float = 0.5  # 0.0 - 1.0
    source_drive: DriveType = DriveType.PURPOSE
    status: GoalStatus = GoalStatus.ACTIVE
    created_tick: int = 0
    progress_tick: int = 0  # last tick when progress was made

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "priority": round(self.priority, 3),
            "source_drive": self.source_drive.value,
            "status": self.status.value,
            "created_tick": self.created_tick,
            "progress_tick": self.progress_tick,
        }

    @staticmethod
    def from_dict(d: dict) -> Goal:
        return Goal(
            description=d["description"],
            priority=d.get("priority", 0.5),
            source_drive=DriveType(d.get("source_drive", "purpose")),
            status=GoalStatus(d.get("status", "active")),
            created_tick=d.get("created_tick", 0),
            progress_tick=d.get("progress_tick", 0),
        )


@dataclass
class Milestone:
    """Concrete, measurable goal with progress tracking."""
    description: str
    target: int  # Target value (e.g., 100 food, 25% map coverage)
    current: int = 0  # Current progress state (e.g., inventory amount)
    total_achieved: int = 0 # Cumulative progress (never decreases)
    completed: bool = False
    metric_type: str = "count"  # "count", "percentage", "boolean"

    def update_progress(self, value: int) -> bool:
        """Update progress with a cumulative value, return True if milestone just completed."""
        was_completed = self.completed
        self.total_achieved = value

        if self.total_achieved >= self.target:
            self.completed = True
        return not was_completed and self.completed

    def progress_percentage(self) -> int:
        """Return progress as percentage (0-100)."""
        if self.target == 0:
            return 100 if self.completed else 0
        # Base percentage on cumulative progress
        return min(100, int((self.total_achieved / self.target) * 100))

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "target": self.target,
            "current": self.current,
            "total_achieved": self.total_achieved,
            "completed": self.completed,
            "metric_type": self.metric_type,
        }

    @staticmethod
    def from_dict(d: dict) -> "Milestone":
        return Milestone(
            description=d["description"],
            target=d["target"],
            current=d.get("current", 0),
            total_achieved=d.get("total_achieved", 0),
            completed=d.get("completed", False),
            metric_type=d.get("metric_type", "count"),
        )


@dataclass
class Task:
    """Concrete actionable task with dependencies and progress tracking."""
    description: str
    status: str = "pending"  # "pending", "in_progress", "completed", "blocked"
    priority: int = 3  # 1-5, higher = more urgent
    progress: int = 0  # 0-100%
    target: int = 0  # Target value (e.g., gather 10 wood)
    current: int = 0  # Current progress toward target
    total_achieved: int = 0  # Cumulative progress (never decreases, tracks work done)
    prerequisite_task: str | None = None  # Description of task that must complete first
    created_tick: int = 0

    def update_progress(self, current_value: int) -> bool:
        """Update progress, return True if task just completed.
        Progress is based on total_achieved (cumulative) not current (inventory).
        This prevents progress regression when resources are consumed."""
        was_completed = self.status == "completed"
        self.current = current_value

        # Track highest value ever achieved (cumulative, never decreases)
        if current_value > self.total_achieved:
            self.total_achieved = current_value

        if self.target > 0:
            # Calculate progress from total_achieved, not current
            self.progress = min(100, int((self.total_achieved / self.target) * 100))
            if self.total_achieved >= self.target:
                self.status = "completed"

        return not was_completed and self.status == "completed"

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "progress": self.progress,
            "target": self.target,
            "current": self.current,
            "total_achieved": self.total_achieved,
            "prerequisite_task": self.prerequisite_task,
            "created_tick": self.created_tick,
        }

    @staticmethod
    def from_dict(d: dict) -> "Task":
        return Task(
            description=d["description"],
            status=d.get("status", "pending"),
            priority=d.get("priority", 3),
            progress=d.get("progress", 0),
            target=d.get("target", 0),
            current=d.get("current", 0),
            total_achieved=d.get("total_achieved", 0),
            prerequisite_task=d.get("prerequisite_task"),
            created_tick=d.get("created_tick", 0),
        )


@dataclass
class Belief:
    content: str
    confidence: float = 0.7  # 0.0 - 1.0
    source: str = "observation"
    created_tick: int = 0
    last_confirmed_tick: int = 0
    failed_attempts: int = 0  # Phase 3: Track how many times this belief led to failure
    last_failed_tick: int = 0  # Phase 3: When it last failed

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "created_tick": self.created_tick,
            "last_confirmed_tick": self.last_confirmed_tick,
            "failed_attempts": self.failed_attempts,
            "last_failed_tick": self.last_failed_tick,
        }

    @staticmethod
    def from_dict(d: dict) -> Belief:
        return Belief(
            content=d["content"],
            confidence=d.get("confidence", 0.7),
            source=d.get("source", "observation"),
            created_tick=d.get("created_tick", 0),
            last_confirmed_tick=d.get("last_confirmed_tick", 0),
        )


@dataclass
class AgentModel:
    """Theory of Mind: what this agent believes about another agent."""
    agent_name: str
    perceived_role: str = ""
    perceived_goals: list[str] = field(default_factory=list)
    perceived_traits: list[str] = field(default_factory=list)
    interaction_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "perceived_role": self.perceived_role,
            "perceived_goals": list(self.perceived_goals),
            "perceived_traits": list(self.perceived_traits),
            "interaction_summary": self.interaction_summary,
        }

    @staticmethod
    def from_dict(d: dict) -> AgentModel:
        return AgentModel(
            agent_name=d["agent_name"],
            perceived_role=d.get("perceived_role", ""),
            perceived_goals=d.get("perceived_goals", []),
            perceived_traits=d.get("perceived_traits", []),
            interaction_summary=d.get("interaction_summary", ""),
        )


# --- Role-specific starting goals ---
ROLE_STARTING_GOALS: dict[str, tuple[str, DriveType]] = {
    "explorer": ("Discover new areas and map the world", DriveType.PURPOSE),
    "builder": ("Gather materials and build useful structures", DriveType.ESTEEM),
    "gatherer": ("Stockpile food and resources for the community", DriveType.SURVIVAL),
    "scholar": ("Study the world and share knowledge with others", DriveType.PURPOSE),
}

# --- Role-specific self-concepts ---
ROLE_SELF_CONCEPTS: dict[str, str] = {
    "explorer": "I am an adventurer who thrives on discovery and mapping the unknown.",
    "builder": "I am a craftsperson dedicated to creating structures and tools.",
    "gatherer": "I am a provider who ensures resources are available for survival.",
    "scholar": "I am a seeker of knowledge who values learning and teaching.",
}

# --- Drive-to-goal templates for generating goals from drives ---
DRIVE_GOAL_TEMPLATES: dict[DriveType, list[str]] = {
    DriveType.SURVIVAL: [
        "Find and gather food to avoid starvation",
        "Ensure I have enough food to survive",
    ],
    DriveType.SAFETY: [
        "Build up reserves of food and materials",
        "Find a safe area with reliable resources",
    ],
    DriveType.SOCIAL: [
        "Build trust with nearby agents through conversation",
        "Find allies and cooperate on gathering",
    ],
    DriveType.ESTEEM: [
        "Excel at my role and become recognized for my skills",
        "Complete a challenging task to prove my abilities",
    ],
    DriveType.PURPOSE: [
        "Find deeper meaning in my daily activities",
        "Contribute something lasting to the community",
    ],
}

# --- Keyword sets for inferring traits/goals from conversation ---
_GOAL_KEYWORDS = {
    "food": ["food", "hungry", "eat", "starving", "gather", "forage"],
    "building": ["build", "construct", "craft", "structure", "materials"],
    "exploring": ["explore", "discover", "map", "travel", "journey"],
    "knowledge": ["learn", "study", "teach", "knowledge", "understand"],
    "trading": ["trade", "exchange", "deal", "offer", "negotiate"],
    "socializing": ["friend", "ally", "trust", "help", "cooperate"],
}

_TRAIT_KEYWORDS = {
    "friendly": ["hello", "nice", "glad", "happy", "friend", "help", "welcome"],
    "cautious": ["careful", "watch", "danger", "risk", "wary", "suspicious"],
    "ambitious": ["goal", "plan", "achieve", "succeed", "best", "great"],
    "generous": ["share", "give", "offer", "help", "free"],
    "resourceful": ["found", "gathered", "stockpile", "reserve", "plenty"],
}


@dataclass
class CognitiveState:
    """The agent's persistent mind between ticks."""
    drives: dict[str, Drive] = field(default_factory=dict)
    goals: list[Goal] = field(default_factory=list)
    current_intention: str = ""
    beliefs: list[Belief] = field(default_factory=list)
    agent_models: dict[str, AgentModel] = field(default_factory=dict)
    self_concept: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    last_inner_thought: str = ""
    conversation_cooldowns: dict[str, int] = field(default_factory=dict)
    action_streak: dict[str, int] = field(default_factory=dict)
    action_history: dict[str, int] = field(default_factory=dict)  # lifetime action counts
    milestones: list[Milestone] = field(default_factory=list)  # Role-specific measurable goals
    tasks: list[Task] = field(default_factory=list)  # Concrete actionable tasks
    current_task: Task | None = None  # Task being actively worked on
    visited_terrain_types: set[str] = field(default_factory=set)
    visited_coordinates: set[tuple[int, int]] = field(default_factory=set)
    cumulative_resources_gathered: dict[str, int] = field(default_factory=dict)

    def initialize(self, role: str, personality_traits: dict) -> None:
        """Set up initial cognitive state from role and personality."""
        # Initialize drives
        for dt in DriveType:
            self.drives[dt.value] = Drive(drive_type=dt, urgency=0.3)

        # Set role-appropriate self-concept
        self.self_concept = ROLE_SELF_CONCEPTS.get(role, "I am finding my place in this world.")

        # Seed one starting goal
        goal_desc, source_drive = ROLE_STARTING_GOALS.get(
            role, ("Survive and find my purpose", DriveType.PURPOSE)
        )
        self.goals.append(Goal(
            description=goal_desc,
            priority=0.7,
            source_drive=source_drive,
            status=GoalStatus.ACTIVE,
            created_tick=0,
            progress_tick=0,
        ))

        # Initialize role-specific milestones
        self.milestones = self._init_milestones_for_role(role)

        # Derive initial strengths from high personality traits
        if personality_traits.get("curiosity", 5) >= 7:
            self.strengths.append("naturally curious")
        if personality_traits.get("conscientiousness", 5) >= 7:
            self.strengths.append("diligent and focused")
        if personality_traits.get("extraversion", 5) >= 7:
            self.strengths.append("socially confident")
        if personality_traits.get("agreeableness", 5) >= 7:
            self.strengths.append("cooperative")
        if personality_traits.get("risk_tolerance", 5) >= 7:
            self.strengths.append("bold risk-taker")

        # Derive initial weaknesses from low personality traits
        if personality_traits.get("conscientiousness", 5) <= 3:
            self.weaknesses.append("easily distracted")
        if personality_traits.get("extraversion", 5) <= 3:
            self.weaknesses.append("socially reserved")
        if personality_traits.get("neuroticism", 5) >= 7:
            self.weaknesses.append("prone to anxiety")
        if personality_traits.get("risk_tolerance", 5) <= 3:
            self.weaknesses.append("overly cautious")

        self.current_intention = goal_desc

    # --- Drive computation (pure game state, NO LLM) ---

    def compute_drives(
        self,
        food: int,
        energy: int,
        materials: int,
        relationships: list[dict],
        role: str,
        tick: int,
        inventory: dict[str, int],
    ) -> None:
        """Recompute all drive urgencies from game state. Called every tick."""
        # SURVIVAL: based on food and energy
        food_urgency = max(0.0, 1.0 - food / 8.0)
        energy_urgency = max(0.0, 1.0 - energy / 80.0)
        self.drives[DriveType.SURVIVAL.value].urgency = _clamp(
            max(food_urgency, energy_urgency)
        )

        # SAFETY: reserves check (dampened to 60%)
        food_safe = min(1.0, food / 12.0)
        materials_safe = min(1.0, materials / 6.0)
        safety_met = (food_safe + materials_safe) / 2.0
        self.drives[DriveType.SAFETY.value].urgency = _clamp(
            (1.0 - safety_met) * 0.6
        )

        # SOCIAL: based on trust and relationship breadth
        if relationships:
            avg_trust = sum(r.get("trust", 5.0) for r in relationships) / len(relationships)
            breadth = min(1.0, len(relationships) / 5.0)
            # Corrected formula: remove division by 2
            social_met = avg_trust / 10.0 + breadth
            social_urgency = 1.0 - social_met
        else:
            # When alone, social drive is a stable, moderate value.
            social_urgency = 0.5
        self.drives[DriveType.SOCIAL.value].urgency = _clamp(social_urgency)

        # ESTEEM: role-specific mastery metric
        if role == "explorer":
            # Based on exploration coverage (using tick as proxy)
            esteem_met = min(1.0, tick / 200.0)
        elif role == "builder":
            tools = inventory.get("tools", 0)
            esteem_met = min(1.0, tools / 5.0)
        elif role == "gatherer":
            total = food + materials
            esteem_met = min(1.0, total / 20.0)
        elif role == "scholar":
            knowledge = inventory.get("knowledge", 0)
            esteem_met = min(1.0, knowledge / 10.0)
        else:
            esteem_met = 0.3
        self.drives[DriveType.ESTEEM.value].urgency = _clamp(
            (1.0 - esteem_met) * 0.5
        )

        # PURPOSE: grows over time, dampened
        purpose_base = min(1.0, tick / 100.0)
        active_goals = sum(1 for g in self.goals if g.status == GoalStatus.ACTIVE)
        purpose_met = min(1.0, active_goals / 3.0) * 0.5 + purpose_base * 0.5
        self.drives[DriveType.PURPOSE.value].urgency = _clamp(
            (1.0 - purpose_met) * 0.4
        )

    def compute_drives_from_fs(self, perception: "Perception") -> None:
        """Recompute all drive urgencies from filesystem state. Called every tick."""
        # CODE_QUALITY
        # Simplistic implementation: urgency increases with the number of uncommitted changes.
        git_status = perception.data.get("git_status", "")
        num_uncommitted_changes = len(git_status.splitlines())
        code_quality_urgency = 1.0 - (1.0 / (1.0 + num_uncommitted_changes * 0.2))
        self.drives[DriveType.CODE_QUALITY.value].urgency = _clamp(code_quality_urgency)

        # TASK_COMPLETION
        # Urgency is high if there are active goals
        active_goals = [g for g in self.goals if g.status == GoalStatus.ACTIVE]
        task_completion_urgency = 0.9 if active_goals else 0.1
        self.drives[DriveType.TASK_COMPLETION.value].urgency = _clamp(task_completion_urgency)

        # EXPLORATION
        # Urgency is high if the agent has not visited many files
        num_visited_files = len(self.visited_coordinates) # Using visited_coordinates as a proxy for visited files
        total_files = len(perception.data.get("files", []))
        exploration_urgency = 1.0 - (num_visited_files / (total_files + 1e-5))
        self.drives[DriveType.EXPLORATION.value].urgency = _clamp(exploration_urgency)

    def dominant_drive(self) -> tuple[str, float]:
        """Return the most urgent drive name and its urgency."""
        if not self.drives:
            return "survival", 0.5
        best = max(self.drives.values(), key=lambda d: d.urgency)
        return best.drive_type.value, best.urgency

    def drives_text(self) -> str:
        """Format drives for prompt injection."""
        parts = []
        for dt in DriveType:
            d = self.drives.get(dt.value)
            if d is None:
                continue
            urgency = d.urgency
            if urgency > 0.7:
                label = "URGENT"
            elif urgency > 0.4:
                label = "moderate"
            else:
                label = "satisfied"
            parts.append(f"- {dt.value.upper()}: {label} ({urgency:.2f})")
        return "\n".join(parts)

    def goals_text(self) -> str:
        """Format active goals for prompt injection."""
        active = [g for g in self.goals if g.status == GoalStatus.ACTIVE]
        if not active:
            return "- No specific goals right now"
        active.sort(key=lambda g: g.priority, reverse=True)
        return "\n".join(
            f"- [{g.priority:.1f}] {g.description}" for g in active[:5]
        )

    def beliefs_text(self) -> str:
        """Format beliefs for prompt injection."""
        if not self.beliefs:
            return "- Still learning about the world"
        # Show most confident beliefs first
        sorted_beliefs = sorted(self.beliefs, key=lambda b: b.confidence, reverse=True)
        return "\n".join(
            f"- {b.content} (confidence: {b.confidence:.1f})" for b in sorted_beliefs[:5]
        )

    def agent_models_text(self, nearby_names: list[str]) -> str:
        """Format mental models of nearby agents for prompt injection."""
        parts = []
        for name in nearby_names:
            model = self.agent_models.get(name)
            if model is None:
                continue
            desc = f"- {model.agent_name}"
            if model.perceived_role:
                desc += f" ({model.perceived_role})"
            if model.perceived_goals:
                desc += f": seems focused on {', '.join(model.perceived_goals[:2])}"
            if model.perceived_traits:
                desc += f" [traits: {', '.join(model.perceived_traits[:2])}]"
            parts.append(desc)
        return "\n".join(parts) if parts else ""

    # --- Phase 2: Theory of Mind and Belief Updating ---

    def update_beliefs_from_observation(
        self, perception: dict, tick: int
    ) -> None:
        """Create/update beliefs from what the agent perceives. No LLM call."""
        MAX_BELIEFS = 20

        # Resources visible -> beliefs about resource locations
        for res in perception.get("reachable_resources", []) + perception.get("aware_resources", []):
            content = f"{res['type']} available near ({res.get('x', '?')}, {res.get('y', '?')})"

            # Phase 3: Check if this belief recently failed before recreating
            existing_belief = self._find_belief(content)
            if existing_belief and existing_belief.failed_attempts > 0:
                # Don't recreate or boost confidence if it recently failed
                ticks_since_failure = tick - existing_belief.last_failed_tick
                if ticks_since_failure < 20:  # Cooldown period: 20 ticks
                    continue  # Skip this resource, it's on cooldown

            # Only confirm beliefs about resources with amount > 0
            if res.get("amount", 0) > 0:
                self._upsert_belief(content, source="observation", tick=tick, confidence=0.9)
            else:
                # If we see a depleted resource, invalidate the belief
                self.invalidate_belief(content)

        # Agents visible -> beliefs about agent locations
        for agent in perception.get("reachable_agents", []) + perception.get("aware_agents", []):
            content = f"{agent['name']} is a {agent.get('role', 'agent')} near ({agent.get('x', '?')}, {agent.get('y', '?')})"
            self._upsert_belief(content, source="observation", tick=tick, confidence=0.8)

        # Enforce cap
        if len(self.beliefs) > MAX_BELIEFS:
            self.beliefs.sort(key=lambda b: b.last_confirmed_tick)
            self.beliefs = self.beliefs[-MAX_BELIEFS:]

    def _upsert_belief(
        self, content: str, source: str, tick: int, confidence: float = 0.7
    ) -> None:
        """Add or update an existing belief."""
        # Check for similar existing belief (simple substring match)
        for b in self.beliefs:
            # Match on the key entity/location part
            if _beliefs_match(b.content, content):
                b.confidence = min(1.0, b.confidence + 0.05)
                b.last_confirmed_tick = tick
                return
        # New belief
        self.beliefs.append(Belief(
            content=content,
            confidence=confidence,
            source=source,
            created_tick=tick,
            last_confirmed_tick=tick,
        ))

    def update_agent_model_from_observation(
        self, agent_name: str, agent_role: str
    ) -> None:
        """Create/update a model of another agent from seeing them. No LLM."""
        if agent_name not in self.agent_models:
            self.agent_models[agent_name] = AgentModel(
                agent_name=agent_name,
                perceived_role=agent_role,
            )
        else:
            self.agent_models[agent_name].perceived_role = agent_role

    def update_agent_model_from_conversation(
        self, agent_name: str, conversation_text: str
    ) -> None:
        """Infer goals and traits from conversation text. No LLM call."""
        if agent_name not in self.agent_models:
            self.agent_models[agent_name] = AgentModel(agent_name=agent_name)
        model = self.agent_models[agent_name]

        text_lower = conversation_text.lower()

        # Infer goals from keywords
        for goal_label, keywords in _GOAL_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                if goal_label not in model.perceived_goals:
                    model.perceived_goals.append(goal_label)
                    # Cap perceived goals
                    if len(model.perceived_goals) > 5:
                        model.perceived_goals = model.perceived_goals[-5:]

        # Infer traits from keywords
        for trait_label, keywords in _TRAIT_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                if trait_label not in model.perceived_traits:
                    model.perceived_traits.append(trait_label)
                    if len(model.perceived_traits) > 5:
                        model.perceived_traits = model.perceived_traits[-5:]

        # Update interaction summary
        snippet = conversation_text[:100].replace("\n", " ")
        model.interaction_summary = f"Last talked about: {snippet}"

    # --- Phase 3: Self-Model Evolution and Goal Lifecycle ---

    def evolve_self_concept(self, tick: int) -> None:
        """Analyze action history to update self-concept, strengths, weaknesses.
        Called every 50 ticks. No LLM call."""
        if not self.action_history:
            return

        total_actions = sum(self.action_history.values())
        if total_actions < 10:
            return

        # Identify dominant action patterns
        sorted_actions = sorted(
            self.action_history.items(), key=lambda x: x[1], reverse=True
        )
        top_action, top_count = sorted_actions[0]
        top_ratio = top_count / total_actions

        # Update strengths based on what agent does most
        new_strengths = list(self.strengths)
        action_strength_map = {
            "gather": "resourceful provider",
            "explore": "tireless explorer",
            "build": "skilled builder",
            "craft": "crafty artisan",
            "talk": "social connector",
            "trade": "shrewd trader",
            "learn": "dedicated scholar",
            "teach": "patient teacher",
        }
        if top_ratio > 0.3 and top_action in action_strength_map:
            strength = action_strength_map[top_action]
            if strength not in new_strengths:
                new_strengths.append(strength)
                if len(new_strengths) > 5:
                    new_strengths = new_strengths[-5:]

        # Identify weaknesses from underperformed areas
        new_weaknesses = list(self.weaknesses)
        social_count = self.action_history.get("talk", 0) + self.action_history.get("trade", 0)
        if social_count / max(total_actions, 1) < 0.05 and total_actions > 20:
            if "socially isolated" not in new_weaknesses:
                new_weaknesses.append("socially isolated")
        gather_count = self.action_history.get("gather", 0)
        if gather_count / max(total_actions, 1) < 0.05 and total_actions > 20:
            if "neglects resource gathering" not in new_weaknesses:
                new_weaknesses.append("neglects resource gathering")
        if len(new_weaknesses) > 5:
            new_weaknesses = new_weaknesses[-5:]

        self.strengths = new_strengths
        self.weaknesses = new_weaknesses

        # Evolve self-concept text based on dominant behavior
        if top_ratio > 0.4:
            behavior_concepts = {
                "gather": "I have become a resourceful provider, focused on keeping supplies stocked.",
                "explore": "I am a restless explorer, always seeking what lies beyond the horizon.",
                "build": "I am a dedicated builder, creating lasting structures for the community.",
                "talk": "I am a social connector, building relationships and sharing stories.",
                "trade": "I am a shrewd negotiator, always looking for mutually beneficial exchanges.",
                "learn": "I am a devoted scholar, endlessly pursuing knowledge and understanding.",
            }
            if top_action in behavior_concepts:
                self.self_concept = behavior_concepts[top_action]

    def manage_goal_lifecycle(self, tick: int) -> None:
        """Abandon stale goals, ensure minimum goals. Called every 20 ticks. No LLM."""
        # Abandon stale goals (100+ ticks with no progress)
        for goal in self.goals:
            if goal.status != GoalStatus.ACTIVE:
                continue
            ticks_since_progress = tick - goal.progress_tick
            ticks_since_created = tick - goal.created_tick
            if ticks_since_progress > 100 and ticks_since_created > 100:
                goal.status = GoalStatus.ABANDONED

        # Ensure at least 1 active goal
        active_goals = [g for g in self.goals if g.status == GoalStatus.ACTIVE]
        if not active_goals:
            drive_name, _ = self.dominant_drive()
            drive_type = DriveType(drive_name)
            templates = DRIVE_GOAL_TEMPLATES.get(drive_type, DRIVE_GOAL_TEMPLATES[DriveType.PURPOSE])
            import random
            desc = random.choice(templates)
            self.goals.append(Goal(
                description=desc,
                priority=0.6,
                source_drive=drive_type,
                status=GoalStatus.ACTIVE,
                created_tick=tick,
                progress_tick=tick,
            ))

        # Cap total goals (keep most recent active ones + completed/abandoned for history)
        active = [g for g in self.goals if g.status == GoalStatus.ACTIVE]
        inactive = [g for g in self.goals if g.status != GoalStatus.ACTIVE]
        if len(active) > 5:
            active.sort(key=lambda g: g.priority, reverse=True)
            for g in active[5:]:
                g.status = GoalStatus.ABANDONED
        # Keep only recent inactive goals for history
        if len(inactive) > 10:
            inactive.sort(key=lambda g: g.created_tick)
            inactive = inactive[-10:]
        self.goals = [g for g in self.goals if g.status == GoalStatus.ACTIVE] + inactive[-10:]

    def invalidate_belief(self, content: str) -> None:
        """Find and remove a belief by its content."""
        self.beliefs = [b for b in self.beliefs if b.content.lower() != content.lower()]

    def mark_belief_failed(self, content: str, tick: int) -> None:
        """Mark that acting on this belief failed. Reduce confidence sharply.
        Phase 3: Track failure history to prevent repeated attempts at failed locations."""
        for b in self.beliefs:
            if _beliefs_match(b.content, content):
                b.failed_attempts += 1
                b.last_failed_tick = tick
                b.confidence = max(0.1, b.confidence - 0.3)  # Sharp penalty (-0.3)
                logger.debug(f"Belief failed: '{content}' (attempts: {b.failed_attempts}, confidence: {b.confidence:.2f})")
                return

    def get_belief_failure_count(self, content: str) -> int:
        """Get how many times this belief has led to failure."""
        for b in self.beliefs:
            if _beliefs_match(b.content, content):
                return b.failed_attempts
        return 0

    def _find_belief(self, content: str) -> Belief | None:
        """Find a belief by content (case-insensitive match)."""
        for b in self.beliefs:
            if _beliefs_match(b.content, content):
                return b
        return None

    def decay_beliefs(self, tick: int) -> None:
        """Decay confidence of old beliefs. Called periodically (every 10 ticks).
        Beliefs lose 0.05 confidence per 10 ticks, removed when confidence < 0.2."""
        for b in self.beliefs:
            ticks_since_confirmed = tick - b.last_confirmed_tick
            if ticks_since_confirmed > 10:
                # Decay 0.05 confidence per 10 ticks
                decay_amount = 0.05 * (ticks_since_confirmed // 10)
                b.confidence = max(0.0, b.confidence - decay_amount)
        # Remove low-confidence beliefs
        self.beliefs = [b for b in self.beliefs if b.confidence >= 0.2]

    # --- Conversation cooldown ---

    def is_conversation_on_cooldown(self, other_agent_id: str, current_tick: int) -> bool:
        """Check if conversation with a specific agent is on cooldown."""
        expires = self.conversation_cooldowns.get(other_agent_id, 0)
        return current_tick < expires

    def set_conversation_cooldown(self, other_agent_id: str, current_tick: int, duration: int = 5) -> None:
        """Set cooldown for conversation with a specific agent."""
        self.conversation_cooldowns[other_agent_id] = current_tick + duration

    # --- Action streak ---

    def update_action_streak(self, action_type: str) -> int:
        """Track consecutive actions of the same type. Returns current streak count."""
        # Increment this action's streak
        current = self.action_streak.get(action_type, 0) + 1
        # Reset all other streaks
        self.action_streak = {action_type: current}
        # Update lifetime history
        self.action_history[action_type] = self.action_history.get(action_type, 0) + 1
        return current

    # --- Conversation purpose (no LLM) ---

    def determine_conversation_purpose(self) -> str:
        """Derive a conversation purpose from the dominant drive."""
        drive_name, urgency = self.dominant_drive()
        purpose_map = {
            "survival": "Ask about food locations or offer to trade for food",
            "safety": "Discuss resource locations and safe areas",
            "social": "Build rapport and learn about each other",
            "esteem": "Share accomplishments or seek collaboration",
            "purpose": "Discuss goals and plans for the future",
        }
        purpose = purpose_map.get(drive_name, "Have a meaningful conversation")
        if urgency > 0.7:
            purpose = f"URGENT: {purpose}"
        return purpose

    def _init_milestones_for_role(self, role: str) -> list[Milestone]:
        """Initialize role-specific measurable milestones."""
        if role == "gatherer":
            return [
                Milestone("Stockpile 50 food", target=50, metric_type="count"),
                Milestone("Stockpile 100 total resources", target=100, metric_type="count"),
                Milestone("Stockpile 200 total resources", target=200, metric_type="count"),
            ]
        elif role == "builder":
            return [
                Milestone("Gather 20 materials", target=20, metric_type="count"),
                Milestone("Craft 1 tool", target=1, metric_type="count"),
                Milestone("Build 1 structure", target=1, metric_type="count"),
            ]
        elif role == "scholar":
            return [
                Milestone("Study 5 terrain types", target=5, metric_type="count"),
                Milestone("Document 10 resource locations", target=10, metric_type="count"),
                Milestone("Teach 1 other agent", target=1, metric_type="count"),
            ]
        elif role == "explorer":
            return [
                Milestone("Discover 10% of the map", target=10, metric_type="percentage"),
                Milestone("Map all resource-rich areas", target=10, metric_type="count"),
                Milestone("Discover 50% of the map", target=50, metric_type="percentage"),
            ]
        else:
            # Default milestones for unknown roles
            return [
                Milestone("Survive 100 ticks", target=100, metric_type="count"),
                Milestone("Form 2 relationships", target=2, metric_type="count"),
            ]

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {
            "drives": {k: v.to_dict() for k, v in self.drives.items()},
            "goals": [g.to_dict() for g in self.goals],
            "current_intention": self.current_intention,
            "beliefs": [b.to_dict() for b in self.beliefs],
            "agent_models": {k: v.to_dict() for k, v in self.agent_models.items()},
            "self_concept": self.self_concept,
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "last_inner_thought": self.last_inner_thought,
            "conversation_cooldowns": dict(self.conversation_cooldowns),
            "action_streak": dict(self.action_streak),
            "action_history": dict(self.action_history),
            "milestones": [m.to_dict() for m in self.milestones],
            "tasks": [t.to_dict() for t in self.tasks],
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "visited_terrain_types": list(self.visited_terrain_types),
            "visited_coordinates": [list(c) for c in self.visited_coordinates],
            "cumulative_resources_gathered": dict(self.cumulative_resources_gathered),
        }

    @staticmethod
    def from_dict(d: dict) -> CognitiveState:
        cs = CognitiveState()
        cs.drives = {
            k: Drive.from_dict(v) for k, v in d.get("drives", {}).items()
        }
        cs.goals = [Goal.from_dict(g) for g in d.get("goals", [])]
        cs.current_intention = d.get("current_intention", "")
        cs.beliefs = [Belief.from_dict(b) for b in d.get("beliefs", [])]
        cs.agent_models = {
            k: AgentModel.from_dict(v) for k, v in d.get("agent_models", {}).items()
        }
        cs.self_concept = d.get("self_concept", "")
        cs.strengths = d.get("strengths", [])
        cs.weaknesses = d.get("weaknesses", [])
        cs.last_inner_thought = d.get("last_inner_thought", "")
        cs.conversation_cooldowns = d.get("conversation_cooldowns", {})
        cs.action_streak = d.get("action_streak", {})
        cs.action_history = d.get("action_history", {})
        cs.milestones = [Milestone.from_dict(m) for m in d.get("milestones", [])]
        cs.tasks = [Task.from_dict(t) for t in d.get("tasks", [])]
        current_task_data = d.get("current_task")
        cs.current_task = Task.from_dict(current_task_data) if current_task_data else None
        cs.visited_terrain_types = set(d.get("visited_terrain_types", []))
        cs.visited_coordinates = {tuple(c) for c in d.get("visited_coordinates", [])}
        cs.cumulative_resources_gathered = d.get("cumulative_resources_gathered", {})
        return cs


# --- Helpers ---

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _beliefs_match(existing: str, new: str) -> bool:
    """Check if two beliefs refer to the same entity/location."""
    # Extract location tuples
    existing_loc = re.search(r"\((\d+),\s*(\d+)\)", existing)
    new_loc = re.search(r"\((\d+),\s*(\d+)\)", new)
    if existing_loc and new_loc:
        # Same location and same resource/agent type prefix
        if existing_loc.group() == new_loc.group():
            # Check if they share the key noun (first word before "available" or "is")
            e_prefix = existing.split(" available")[0].split(" is")[0].split(" near")[0]
            n_prefix = new.split(" available")[0].split(" is")[0].split(" near")[0]
            return e_prefix.strip().lower() == n_prefix.strip().lower()
    return False
