"""
Transparency Layer for Routing Decisions.

This module provides transparency into routing decisions, showing users
which model was selected and why. It includes logging, display formatting,
and cost tracking for Phase 1.
"""

import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import logging
from enum import Enum

from .task_analysis import TaskAnalysis, TaskType
from .factory import ProviderType

logger = logging.getLogger(__name__)


class DecisionSource(Enum):
    """Source of routing decision."""

    RULE_BASED = "rule_based"
    TASK_ANALYSIS = "task_analysis"
    USER_OVERRIDE = "user_override"
    FALLBACK = "fallback"
    MANUAL = "manual"


class DisplayFormat(Enum):
    """Format for displaying routing decisions."""

    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"
    MINIMAL = "minimal"
    VERBOSE = "verbose"


@dataclass
class RoutingReasoning:
    """Reasoning behind a routing decision."""

    primary_reason: str
    secondary_reasons: List[str] = field(default_factory=list)
    task_type: Optional[TaskType] = None
    complexity_score: Optional[int] = None
    confidence: Optional[float] = None
    cost_consideration: Optional[str] = None
    performance_consideration: Optional[str] = None
    provider_availability: Optional[str] = None


@dataclass
class RoutingDecision:
    """Complete routing decision with all metadata."""

    model_name: str
    provider_type: ProviderType
    provider_name: str
    reasoning: RoutingReasoning
    task_analysis: Optional[TaskAnalysis] = None
    decision_source: DecisionSource = DecisionSource.RULE_BASED
    timestamp: float = field(default_factory=time.time)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    confidence_score: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


class DecisionLogger:
    """Logs routing decisions for later analysis and debugging."""

    def __init__(self, log_file: Optional[str] = None, max_entries: int = 1000):
        """
        Initialize the decision logger.

        Args:
            log_file: Optional file path to persist logs
            max_entries: Maximum number of entries to keep in memory
        """
        self.log_file = log_file
        self.max_entries = max_entries
        self.decisions: List[RoutingDecision] = []

        # Load existing logs if file exists
        if log_file:
            try:
                self._load_logs()
            except Exception as e:
                logger.warning(f"Failed to load decision logs: {e}")

    def log_decision(self, decision: RoutingDecision) -> None:
        """
        Log a routing decision.

        Args:
            decision: Routing decision to log
        """
        self.decisions.append(decision)

        # Trim old entries if needed
        if len(self.decisions) > self.max_entries:
            self.decisions = self.decisions[-self.max_entries :]

        # Log to file if configured
        if self.log_file:
            self._persist_decision(decision)

        # Log to application logger
        self._log_to_logger(decision)

    def _persist_decision(self, decision: RoutingDecision) -> None:
        """Persist decision to log file."""
        try:
            # Convert decision to dict
            decision_dict = self._decision_to_dict(decision)

            with open(self.log_file, "a", encoding="utf-8") as f:
                json_line = json.dumps(decision_dict, ensure_ascii=False, default=str)
                f.write(json_line + "\n")
        except Exception as e:
            logger.error(f"Failed to persist decision: {e}")

    def _load_logs(self) -> None:
        """Load decisions from log file."""
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        decision_dict = json.loads(line.strip())
                        decision = self._dict_to_decision(decision_dict)
                        self.decisions.append(decision)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass  # File doesn't exist yet, that's fine

    def _decision_to_dict(self, decision: RoutingDecision) -> Dict[str, Any]:
        """Convert decision to serializable dict."""
        decision_dict = asdict(decision)

        # Convert enums to strings
        decision_dict["provider_type"] = decision.provider_type.value
        decision_dict["decision_source"] = decision.decision_source.value

        if decision.task_analysis:
            decision_dict["task_analysis"] = asdict(decision.task_analysis)
            decision_dict["task_analysis"]["task_type"] = decision.task_analysis.task_type.value

        decision_dict["reasoning"] = asdict(decision.reasoning)
        if decision.reasoning.task_type:
            decision_dict["reasoning"]["task_type"] = decision.reasoning.task_type.value

        return decision_dict

    def _dict_to_decision(self, decision_dict: Dict[str, Any]) -> RoutingDecision:
        """Convert dict back to RoutingDecision."""
        # Convert string enums back to enum values
        decision_dict["provider_type"] = ProviderType(decision_dict["provider_type"])
        decision_dict["decision_source"] = DecisionSource(decision_dict["decision_source"])

        # Handle task analysis
        if "task_analysis" in decision_dict and decision_dict["task_analysis"]:
            ta_dict = decision_dict["task_analysis"]
            ta_dict["task_type"] = TaskType(ta_dict["task_type"])
            decision_dict["task_analysis"] = TaskAnalysis(**ta_dict)

        # Handle reasoning
        reason_dict = decision_dict["reasoning"]
        if "task_type" in reason_dict and reason_dict["task_type"]:
            reason_dict["task_type"] = TaskType(reason_dict["task_type"])
        decision_dict["reasoning"] = RoutingReasoning(**reason_dict)

        return RoutingDecision(**decision_dict)

    def _log_to_logger(self, decision: RoutingDecision) -> None:
        """Log decision to application logger."""
        log_message = (
            f"Routing decision: model={decision.model_name}, "
            f"provider={decision.provider_name}, "
            f"reason={decision.reasoning.primary_reason}, "
            f"confidence={decision.confidence_score:.2f}"
        )

        if decision.estimated_cost_usd:
            log_message += f", cost=${decision.estimated_cost_usd:.4f}"

        logger.info(log_message)

    def get_recent_decisions(self, limit: int = 10) -> List[RoutingDecision]:
        """
        Get recent routing decisions.

        Args:
            limit: Maximum number of decisions to return

        Returns:
            List of recent decisions
        """
        return self.decisions[-limit:] if self.decisions else []

    def get_decisions_by_model(self, model_name: str) -> List[RoutingDecision]:
        """
        Get all decisions for a specific model.

        Args:
            model_name: Model name to filter by

        Returns:
            List of decisions for the model
        """
        return [d for d in self.decisions if d.model_name == model_name]

    def get_decisions_by_task_type(self, task_type: TaskType) -> List[RoutingDecision]:
        """
        Get all decisions for a specific task type.

        Args:
            task_type: Task type to filter by

        Returns:
            List of decisions for the task type
        """
        return [
            d for d in self.decisions if d.task_analysis and d.task_analysis.task_type == task_type
        ]

    def get_decision_stats(self) -> Dict[str, Any]:
        """
        Get statistics about routing decisions.

        Returns:
            Dictionary of statistics
        """
        if not self.decisions:
            return {}

        total = len(self.decisions)

        # Count by model
        model_counts: Dict[str, int] = {}
        provider_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {}

        for decision in self.decisions:
            model_counts[decision.model_name] = model_counts.get(decision.model_name, 0) + 1
            provider_counts[decision.provider_name] = (
                provider_counts.get(decision.provider_name, 0) + 1
            )
            source_counts[decision.decision_source.value] = (
                source_counts.get(decision.decision_source.value, 0) + 1
            )

        # Calculate average confidence
        avg_confidence = sum(d.confidence_score for d in self.decisions) / total

        # Calculate average cost if available
        costs = [d.estimated_cost_usd for d in self.decisions if d.estimated_cost_usd]
        avg_cost = sum(costs) / len(costs) if costs else 0

        return {
            "total_decisions": total,
            "model_distribution": model_counts,
            "provider_distribution": provider_counts,
            "source_distribution": source_counts,
            "average_confidence": avg_confidence,
            "average_cost_usd": avg_cost,
            "first_decision": self.decisions[0].timestamp if self.decisions else None,
            "last_decision": self.decisions[-1].timestamp if self.decisions else None,
        }


class TransparencyDisplay:
    """Formats and displays routing decisions to users."""

    def __init__(self, format: DisplayFormat = DisplayFormat.TEXT):
        """
        Initialize the transparency display.

        Args:
            format: Display format to use
        """
        self.format = format

        # Color/icon mappings for different providers
        self.provider_display = {
            ProviderType.OLLAMA: {"name": "Ollama", "icon": "🖥️", "color": "blue"},
            ProviderType.DEEPSEEK: {"name": "DeepSeek", "icon": "🔍", "color": "green"},
            ProviderType.ANTHROPIC: {"name": "Claude", "icon": "🤖", "color": "purple"},
            ProviderType.OPENROUTER: {"name": "OpenRouter", "icon": "🔄", "color": "orange"},
            ProviderType.OPENAI: {"name": "OpenAI", "icon": "⚡", "color": "cyan"},
        }

        # Task type descriptions
        self.task_type_display = {
            TaskType.PLANNING: "📋 Planning",
            TaskType.SECURITY: "🔒 Security",
            TaskType.CODING: "💻 Coding",
            TaskType.DEBUGGING: "🐛 Debugging",
            TaskType.REFACTORING: "♻️ Refactoring",
            TaskType.DOCUMENTATION: "📝 Documentation",
            TaskType.TESTING: "🧪 Testing",
            TaskType.ANALYSIS: "🔍 Analysis",
            TaskType.GENERAL: "💬 General",
            TaskType.UNKNOWN: "❓ Unknown",
        }

    def display_decision(self, decision: RoutingDecision) -> str:
        """
        Format and return decision display string.

        Args:
            decision: Routing decision to display

        Returns:
            Formatted display string
        """
        if self.format == DisplayFormat.JSON:
            return self._format_json(decision)
        elif self.format == DisplayFormat.MARKDOWN:
            return self._format_markdown(decision)
        elif self.format == DisplayFormat.MINIMAL:
            return self._format_minimal(decision)
        elif self.format == DisplayFormat.VERBOSE:
            return self._format_verbose(decision)
        else:  # TEXT (default)
            return self._format_text(decision)

    def _format_text(self, decision: RoutingDecision) -> str:
        """Format decision as plain text."""
        provider_info = self.provider_display.get(
            decision.provider_type, {"name": decision.provider_name, "icon": "🤖", "color": "white"}
        )

        lines = [
            "🧭 **Model Selection**",
            f"  Model: {decision.model_name}",
            f"  Provider: {provider_info['icon']} {provider_info['name']}",
            f"  Reason: {decision.reasoning.primary_reason}",
        ]

        # Add secondary reasons if present
        if decision.reasoning.secondary_reasons:
            for reason in decision.reasoning.secondary_reasons:
                lines.append(f"    • {reason}")

        # Add task analysis if available
        if decision.task_analysis:
            task_display = self.task_type_display.get(
                decision.task_analysis.task_type, decision.task_analysis.task_type.value
            )
            lines.append(f"  Task Type: {task_display}")
            lines.append(f"  Complexity: {decision.task_analysis.complexity.score}/10")
            lines.append(f"  Confidence: {decision.confidence_score:.0%}")

        # Add cost if available
        if decision.estimated_cost_usd:
            lines.append(f"  Estimated Cost: ${decision.estimated_cost_usd:.4f}")

        return "\n".join(lines)

    def _format_markdown(self, decision: RoutingDecision) -> str:
        """Format decision as markdown."""
        provider_info = self.provider_display.get(
            decision.provider_type, {"name": decision.provider_name, "icon": "🤖", "color": "white"}
        )

        lines = [
            "## 🧭 Model Selection",
            "",
            f"**Model:** `{decision.model_name}`",
            f"**Provider:** {provider_info['icon']} {provider_info['name']}",
            f"**Reason:** {decision.reasoning.primary_reason}",
            "",
        ]

        # Add secondary reasons if present
        if decision.reasoning.secondary_reasons:
            lines.append("**Additional Considerations:**")
            for reason in decision.reasoning.secondary_reasons:
                lines.append(f"  - {reason}")
            lines.append("")

        # Add task analysis if available
        if decision.task_analysis:
            task_display = self.task_type_display.get(
                decision.task_analysis.task_type, decision.task_analysis.task_type.value
            )
            lines.append("**Task Analysis:**")
            lines.append(f"- **Type:** {task_display}")
            lines.append(f"- **Complexity:** {decision.task_analysis.complexity.score}/10")
            lines.append(f"- **Confidence:** {decision.confidence_score:.0%}")
            lines.append("")

        # Add cost if available
        if decision.estimated_cost_usd:
            lines.append(f"**Estimated Cost:** ${decision.estimated_cost_usd:.4f}")

        return "\n".join(lines)

    def _format_json(self, decision: RoutingDecision) -> str:
        """Format decision as JSON."""
        import json

        return json.dumps(self._decision_to_dict(decision), indent=2, default=str)

    def _format_minimal(self, decision: RoutingDecision) -> str:
        """Format decision as minimal text."""
        provider_info = self.provider_display.get(
            decision.provider_type, {"name": decision.provider_name, "icon": "🤖", "color": "white"}
        )

        if decision.estimated_cost_usd:
            return (
                f"{provider_info['icon']} Using {decision.model_name} "
                f"({provider_info['name']}) - {decision.reasoning.primary_reason} "
                f"[${decision.estimated_cost_usd:.4f}]"
            )
        else:
            return (
                f"{provider_info['icon']} Using {decision.model_name} "
                f"({provider_info['name']}) - {decision.reasoning.primary_reason}"
            )

    def _format_verbose(self, decision: RoutingDecision) -> str:
        """Format decision as verbose text with all details."""
        provider_info = self.provider_display.get(
            decision.provider_type, {"name": decision.provider_name, "icon": "🤖", "color": "white"}
        )

        lines = [
            "=" * 60,
            "ROUTING DECISION DETAILS",
            "=" * 60,
            f"Timestamp: {datetime.fromtimestamp(decision.timestamp).isoformat()}",
            f"Session ID: {decision.session_id or 'N/A'}",
            f"User ID: {decision.user_id or 'N/A'}",
            "-" * 60,
            f"MODEL: {decision.model_name}",
            f"PROVIDER: {provider_info['icon']} {provider_info['name']} ({decision.provider_type.value})",  # noqa: E501
            f"SOURCE: {decision.decision_source.value}",
            f"CONFIDENCE: {decision.confidence_score:.2f}",
            "",
            "REASONING:",
            f"  Primary: {decision.reasoning.primary_reason}",
        ]

        if decision.reasoning.secondary_reasons:
            lines.append("  Secondary:")
            for reason in decision.reasoning.secondary_reasons:
                lines.append(f"    • {reason}")

        if decision.reasoning.cost_consideration:
            lines.append(f"  Cost: {decision.reasoning.cost_consideration}")

        if decision.reasoning.performance_consideration:
            lines.append(f"  Performance: {decision.reasoning.performance_consideration}")

        if decision.reasoning.provider_availability:
            lines.append(f"  Provider: {decision.reasoning.provider_availability}")

        lines.append("")

        # Task analysis details
        if decision.task_analysis:
            lines.append("TASK ANALYSIS:")
            lines.append(f"  Type: {decision.task_analysis.task_type.value}")
            lines.append(f"  Complexity: {decision.task_analysis.complexity.score}/10")
            lines.append(f"    {decision.task_analysis.complexity.reasoning}")
            lines.append(f"  Keywords: {', '.join(decision.task_analysis.keywords)}")
            lines.append(f"  Confidence: {decision.task_analysis.confidence:.2f}")

            # Metadata
            if decision.task_analysis.metadata:
                lines.append("  Metadata:")
                for key, value in decision.task_analysis.metadata.items():
                    lines.append(f"    • {key}: {value}")

        # Cost details
        if decision.estimated_cost_usd:
            lines.append("")
            lines.append(f"COST: ${decision.estimated_cost_usd:.6f}")

        # Additional metadata
        if decision.metadata:
            lines.append("")
            lines.append("ADDITIONAL METADATA:")
            for key, value in decision.metadata.items():
                lines.append(f"  {key}: {value}")

        lines.append("=" * 60)

        return "\n".join(lines)

    def _decision_to_dict(self, decision: RoutingDecision) -> Dict[str, Any]:
        """Convert decision to dict for JSON formatting."""
        from .transparency import DecisionLogger

        logger_obj = DecisionLogger()
        return logger_obj._decision_to_dict(decision)

    def set_format(self, format: DisplayFormat) -> None:
        """
        Change the display format.

        Args:
            format: New display format
        """
        self.format = format


class TransparencyLayer:
    """
    Main transparency layer that combines logging and display.

    This is the main interface for the transparency system in Phase 1.
    """

    def __init__(
        self,
        log_file: Optional[str] = None,
        display_format: DisplayFormat = DisplayFormat.TEXT,
        enabled: bool = True,
    ):
        """
        Initialize the transparency layer.

        Args:
            log_file: Optional file to persist decision logs
            display_format: Format for displaying decisions to users
            enabled: Whether transparency is enabled
        """
        self.enabled = enabled
        self.logger = DecisionLogger(log_file)
        self.display = TransparencyDisplay(display_format)

        # Statistics
        self.decision_count = 0
        self.last_decision_time: Optional[float] = None

    def show_decision(self, decision: RoutingDecision) -> str:
        """
        Show routing decision to user and log it.

        Args:
            decision: Routing decision to show

        Returns:
            Formatted display string
        """
        if not self.enabled:
            return ""

        # Log the decision
        self.logger.log_decision(decision)

        # Update statistics
        self.decision_count += 1
        self.last_decision_time = time.time()

        # Return formatted display
        return self.display.display_decision(decision)

    def log_only(self, decision: RoutingDecision) -> None:
        """
        Log decision without displaying it.

        Args:
            decision: Routing decision to log
        """
        if not self.enabled:
            return

        self.logger.log_decision(decision)
        self.decision_count += 1
        self.last_decision_time = time.time()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get transparency layer statistics.

        Returns:
            Dictionary of statistics
        """
        stats = {
            "enabled": self.enabled,
            "total_decisions": self.decision_count,
            "last_decision_time": self.last_decision_time,
            "display_format": self.display.format.value,
        }

        # Add decision logger stats
        stats.update(self.logger.get_decision_stats())

        return stats

    def get_recent_decisions(self, limit: int = 5) -> List[Tuple[RoutingDecision, str]]:
        """
        Get recent decisions with their display strings.

        Args:
            limit: Maximum number of decisions to return

        Returns:
            List of (decision, display_string) tuples
        """
        recent = self.logger.get_recent_decisions(limit)
        return [(d, self.display.display_decision(d)) for d in recent]

    def enable(self) -> None:
        """Enable transparency layer."""
        self.enabled = True

    def disable(self) -> None:
        """Disable transparency layer."""
        self.enabled = False

    def set_display_format(self, format: DisplayFormat) -> None:
        """
        Change display format.

        Args:
            format: New display format
        """
        self.display.set_format(format)


# Global instance for convenience
_default_transparency: Optional[TransparencyLayer] = None


def get_transparency_layer(
    log_file: Optional[str] = None,
    display_format: DisplayFormat = DisplayFormat.TEXT,
    enabled: bool = True,
) -> TransparencyLayer:
    """
    Get or create the global transparency layer instance.

    Args:
        log_file: Optional file to persist decision logs
        display_format: Format for displaying decisions
        enabled: Whether transparency is enabled

    Returns:
        TransparencyLayer instance
    """
    global _default_transparency
    if _default_transparency is None:
        _default_transparency = TransparencyLayer(log_file, display_format, enabled)
    return _default_transparency


def show_decision(decision: RoutingDecision) -> str:
    """
    Convenience function to show a routing decision.

    Args:
        decision: Routing decision to show

    Returns:
        Formatted display string
    """
    layer = get_transparency_layer()
    return layer.show_decision(decision)
