"""Advanced session health monitoring for corruption detection."""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


@dataclass
class HealthReport:
    """Comprehensive health report for a conversation session."""

    overall_score: float  # 0-1, where 1 is perfect health
    structural_score: float  # Message format compliance
    api_score: float  # API interaction health
    performance_score: float  # Efficiency metrics
    content_score: float  # Conversation coherence

    issues: List[Dict[str, Any]]  # List of detected issues
    metrics: Dict[str, Any]  # Detailed metrics
    recommendations: List[str]  # Actionable recommendations

    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def is_healthy(self) -> bool:
        """Check if session is in good health."""
        return self.overall_score >= 0.8

    @property
    def needs_attention(self) -> bool:
        """Check if session needs attention."""
        return self.overall_score < 0.9

    @property
    def is_critical(self) -> bool:
        """Check if session has critical issues."""
        return self.overall_score < 0.6

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "overall_score": self.overall_score,
            "structural_score": self.structural_score,
            "api_score": self.api_score,
            "performance_score": self.performance_score,
            "content_score": self.content_score,
            "issues": self.issues,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
        }


class SessionHealthMonitor:
    """
    Advanced health monitoring for conversation sessions.

    Detects corruption patterns, performance issues, and provides
    actionable recommendations for session recovery.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_health(
        self,
        conversation_history: List[Dict[str, Any]],
        recent_errors: Optional[List[Dict[str, Any]]] = None,
    ) -> HealthReport:
        """
        Perform comprehensive health analysis of a conversation session.

        Args:
            conversation_history: Full conversation history
            recent_errors: List of recent error events

        Returns:
            Detailed health report
        """
        recent_errors = recent_errors or []

        # Perform individual health checks
        structural_health = self._analyze_structural_health(conversation_history)
        api_health = self._analyze_api_health(conversation_history, recent_errors)
        performance_health = self._analyze_performance_health(conversation_history)
        content_health = self._analyze_content_health(conversation_history)

        # Calculate overall score (weighted average)
        overall_score = (
            structural_health[0] * 0.4  # Structural issues are most critical
            + api_health[0] * 0.3  # API issues indicate immediate problems
            + performance_health[0] * 0.2  # Performance affects usability
            + content_health[0] * 0.1  # Content issues are least critical
        )

        # Combine all issues
        all_issues = []
        all_issues.extend(structural_health[1])
        all_issues.extend(api_health[1])
        all_issues.extend(performance_health[1])
        all_issues.extend(content_health[1])

        # Combine metrics
        metrics = {}
        metrics.update(structural_health[2])
        metrics.update(api_health[2])
        metrics.update(performance_health[2])
        metrics.update(content_health[2])

        # Generate recommendations
        recommendations = self._generate_recommendations(all_issues, overall_score)

        return HealthReport(
            overall_score=overall_score,
            structural_score=structural_health[0],
            api_score=api_health[0],
            performance_score=performance_health[0],
            content_score=content_health[0],
            issues=all_issues,
            metrics=metrics,
            recommendations=recommendations,
        )

    def _analyze_structural_health(
        self, conversation_history: List[Dict[str, Any]]
    ) -> Tuple[float, List[Dict], Dict]:
        """
        Analyze structural health of conversation.

        Returns:
            Tuple of (score, issues_list, metrics_dict)
        """
        issues = []
        metrics = {
            "total_messages": len(conversation_history),
            "message_types": Counter(),
            "format_errors": 0,
        }

        score = 1.0
        penalty_per_issue = 0.1  # Each issue reduces score by 10%

        for i, msg in enumerate(conversation_history):
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")

            metrics["message_types"][role] += 1

            # Check for required fields
            if role not in ["system", "user", "assistant", "tool"]:
                issues.append(
                    {
                        "type": "invalid_role",
                        "index": i,
                        "message": f"Invalid role '{role}' at message {i}",
                        "severity": "high",
                    }
                )
                score = max(0, score - penalty_per_issue)
                metrics["format_errors"] += 1

            # Assistant message validation
            if role == "assistant":
                if not content and not tool_calls:
                    issues.append(
                        {
                            "type": "invalid_assistant_message",
                            "index": i,
                            "message": f"Assistant message {i} has no content or tool_calls",
                            "severity": "critical",
                        }
                    )
                    score = max(0, score - penalty_per_issue * 2)  # Critical issues penalize more
                    metrics["format_errors"] += 1

            # Tool message validation
            elif role == "tool":
                if not isinstance(content, str):
                    issues.append(
                        {
                            "type": "invalid_tool_result",
                            "index": i,
                            "message": f"Tool result {i} has non-string content",
                            "severity": "high",
                        }
                    )
                    score = max(0, score - penalty_per_issue)
                    metrics["format_errors"] += 1

        # Check for conversation flow issues
        flow_issues = self._analyze_conversation_flow(conversation_history)
        issues.extend(flow_issues)
        score = max(0, score - len(flow_issues) * penalty_per_issue)

        return score, issues, metrics

    def _analyze_api_health(
        self, conversation_history: List[Dict[str, Any]], recent_errors: List[Dict[str, Any]]
    ) -> Tuple[float, List[Dict], Dict]:
        """
        Analyze API interaction health.

        Returns:
            Tuple of (score, issues_list, metrics_dict)
        """
        issues = []
        metrics = {
            "error_count": len(recent_errors),
            "error_types": Counter(),
            "tool_call_count": 0,
            "tool_success_rate": 1.0,
        }

        score = 1.0
        penalty_per_error = 0.05

        # Analyze recent errors
        for error in recent_errors:
            error_type = error.get("type", "unknown")
            metrics["error_types"][error_type] += 1

            if "invalid_assistant_message" in error.get("message", "").lower():
                issues.append(
                    {
                        "type": "api_corruption_error",
                        "message": "Recent API error indicates message corruption",
                        "severity": "critical",
                    }
                )
                score = max(0, score - penalty_per_error * 4)  # Major penalty
            elif "rate_limit" in error.get("message", "").lower():
                issues.append(
                    {
                        "type": "rate_limit_issue",
                        "message": "Rate limiting detected - may indicate overuse",
                        "severity": "medium",
                    }
                )
                score = max(0, score - penalty_per_error * 2)

        # Analyze tool call patterns
        tool_calls = []
        tool_results = []

        for msg in conversation_history:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                tool_calls.extend(msg["tool_calls"])
            elif msg.get("role") == "tool":
                tool_results.append(msg)

        metrics["tool_call_count"] = len(tool_calls)

        if tool_calls:
            # Check for tool call/response mismatches
            tool_call_ids = {tc.get("id") for tc in tool_calls if tc.get("id")}
            tool_result_ids = {
                msg.get("tool_call_id") for msg in tool_results if msg.get("tool_call_id")
            }

            unmatched_calls = tool_call_ids - tool_result_ids
            _unmatched_results = tool_result_ids - tool_call_ids

            if unmatched_calls:
                issues.append(
                    {
                        "type": "unmatched_tool_calls",
                        "message": f"{len(unmatched_calls)} tool calls without matching results",
                        "severity": "high",
                    }
                )
                score = max(0, score - penalty_per_error * len(unmatched_calls))

            # Calculate tool success rate
            successful_results = sum(1 for msg in tool_results if self._is_tool_result_success(msg))
            metrics["tool_success_rate"] = (
                successful_results / len(tool_results) if tool_results else 1.0
            )

            if metrics["tool_success_rate"] < 0.8:
                issues.append(
                    {
                        "type": "low_tool_success_rate",
                        "message": f"Tool success rate is {metrics['tool_success_rate']:.1%}",
                        "severity": "medium",
                    }
                )
                score = max(0, score - penalty_per_error * 2)

        return score, issues, metrics

    def _analyze_performance_health(
        self, conversation_history: List[Dict[str, Any]]
    ) -> Tuple[float, List[Dict], Dict]:
        """
        Analyze performance and efficiency metrics.

        Returns:
            Tuple of (score, issues_list, metrics_dict)
        """
        issues = []
        metrics = {
            "message_count": len(conversation_history),
            "average_content_length": 0,
            "token_efficiency": 1.0,
            "conversation_depth": 0,
        }

        score = 1.0
        penalty_per_issue = 0.02

        # Calculate content statistics
        total_content_length = 0
        message_count = 0

        for msg in conversation_history:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_content_length += len(content)
                message_count += 1

        if message_count > 0:
            metrics["average_content_length"] = total_content_length / message_count

        # Check for excessive conversation length
        if len(conversation_history) > 200:
            issues.append(
                {
                    "type": "excessive_length",
                    "message": f"Conversation has {len(conversation_history)} messages - may impact performance",
                    "severity": "medium",
                }
            )
            score = max(0, score - penalty_per_issue * 2)

        # Check for very long messages (potential abuse)
        long_messages = sum(
            1
            for msg in conversation_history
            if isinstance(msg.get("content"), str) and len(msg["content"]) > 10000
        )

        if long_messages > 0:
            issues.append(
                {
                    "type": "long_messages",
                    "message": f"{long_messages} messages exceed 10k characters",
                    "severity": "low",
                }
            )
            score = max(0, score - penalty_per_issue * long_messages)

        # Calculate conversation depth (back-and-forth exchanges)
        user_messages = sum(1 for msg in conversation_history if msg.get("role") == "user")
        assistant_messages = sum(
            1 for msg in conversation_history if msg.get("role") == "assistant"
        )
        metrics["conversation_depth"] = min(user_messages, assistant_messages)

        return score, issues, metrics

    def _analyze_content_health(
        self, conversation_history: List[Dict[str, Any]]
    ) -> Tuple[float, List[Dict], Dict]:
        """
        Analyze content quality and coherence.

        Returns:
            Tuple of (score, issues_list, metrics_dict)
        """
        issues = []
        metrics = {
            "duplicate_messages": 0,
            "empty_responses": 0,
            "repetitive_patterns": 0,
        }

        score = 1.0
        penalty_per_issue = 0.01

        # Check for duplicate messages
        message_contents = []
        for msg in conversation_history:
            content = msg.get("content", "")
            if isinstance(content, str) and len(content.strip()) > 10:  # Ignore very short messages
                message_contents.append(content.strip())

        # Count duplicates (simple exact matching)
        content_counts = Counter(message_contents)
        duplicates = sum(count - 1 for count in content_counts.values() if count > 1)
        metrics["duplicate_messages"] = duplicates

        if duplicates > 3:
            issues.append(
                {
                    "type": "duplicate_content",
                    "message": f"{duplicates} duplicate messages detected",
                    "severity": "low",
                }
            )
            score = max(0, score - penalty_per_issue * duplicates)

        # Check for empty assistant responses
        empty_assistant = sum(
            1
            for msg in conversation_history
            if msg.get("role") == "assistant"
            and not msg.get("content", "").strip()
            and not msg.get("tool_calls")
        )

        metrics["empty_responses"] = empty_assistant

        if empty_assistant > 2:
            issues.append(
                {
                    "type": "empty_responses",
                    "message": f"{empty_assistant} empty assistant responses",
                    "severity": "medium",
                }
            )
            score = max(0, score - penalty_per_issue * empty_assistant)

        return score, issues, metrics

    def _analyze_conversation_flow(self, conversation_history: List[Dict[str, Any]]) -> List[Dict]:
        """Analyze conversation flow for structural issues."""
        issues = []

        # Check for proper alternation (but allow for tool calls)
        expected_roles = []
        for msg in conversation_history:
            role = msg.get("role")
            if role in ["system", "user", "assistant"]:
                expected_roles.append(role)

        # Simple check: no three consecutive messages from same role (ignoring tools)
        for i in range(len(expected_roles) - 2):
            if expected_roles[i] == expected_roles[i + 1] == expected_roles[
                i + 2
            ] and expected_roles[i] in ["user", "assistant"]:
                issues.append(
                    {
                        "type": "conversation_flow_issue",
                        "index": i,
                        "message": f"Unusual conversation flow at messages {i}-{i+2}",
                        "severity": "low",
                    }
                )
                break  # Only report first occurrence

        return issues

    def _is_tool_result_success(self, tool_message: Dict[str, Any]) -> bool:
        """Check if a tool result indicates success."""
        try:
            content = tool_message.get("content", "")
            if isinstance(content, str):
                result = json.loads(content)
                return result.get("success", False)
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
        return False

    def _generate_recommendations(
        self, issues: List[Dict[str, Any]], overall_score: float
    ) -> List[str]:
        """Generate actionable recommendations based on issues and score."""
        recommendations = []

        # Group issues by type
        issue_types = Counter(issue["type"] for issue in issues)

        # Critical issues get priority recommendations
        critical_issues = [i for i in issues if i.get("severity") == "critical"]
        if critical_issues:
            recommendations.append(
                "CRITICAL: Session has corrupted messages. Use '/session repair' to fix."
            )

        # High severity issues
        high_issues = [i for i in issues if i.get("severity") == "high"]
        if high_issues:
            recommendations.append("HIGH PRIORITY: Address structural issues before continuing.")

        # Specific recommendations based on issue types
        if issue_types.get("duplicate_content", 0) > 3:
            recommendations.append("Consider clearing repetitive conversation history.")

        if issue_types.get("excessive_length", 0) > 0:
            recommendations.append(
                "Session is very long. Consider creating a checkpoint and starting fresh."
            )

        if issue_types.get("low_tool_success_rate", 0) > 0:
            recommendations.append("Tool execution issues detected. Review recent tool calls.")

        if overall_score < 0.6:
            recommendations.append(
                "Session health is poor. Recommend checkpoint rollback or repair."
            )
        elif overall_score < 0.8:
            recommendations.append("Session needs attention. Monitor for further issues.")

        # General recommendations
        if not recommendations:
            recommendations.append("Session health is good. Continue normally.")

        return recommendations
