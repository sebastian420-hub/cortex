"""Conversation history management"""

import logging
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
from datetime import datetime
from .context import truncate_history, get_conversation_tokens
from ..utils.encoding import sanitize_object

if TYPE_CHECKING:
    from .summarization import ConversationSummarizer, SummaryChunk

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation history and context"""

    def __init__(
        self,
        system_prompt: str,
        max_tokens: int = 100000,
        keep_recent: int = 20,
        model: str = "gpt-4",
        warn_on_truncation: bool = True,
        on_truncation: Optional[Callable[[int, int], None]] = None,
        summarizer: Optional["ConversationSummarizer"] = None,
        enable_summarization: bool = True,
        summarization_threshold: float = 0.75,
    ):
        """
        Initialize conversation manager.

        Args:
            system_prompt: Initial system prompt
            max_tokens: Maximum tokens in context
            keep_recent: Minimum messages to keep on truncation
            model: Model name for token counting
            warn_on_truncation: Whether to log warnings on truncation
            on_truncation: Optional callback(messages_removed, new_count) on truncation
            summarizer: Optional summarizer for intelligent context management
            enable_summarization: Whether to use summarization (vs pure truncation)
            summarization_threshold: Token threshold (0-1) to trigger summarization
        """
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent
        self.model = model
        self.warn_on_truncation = warn_on_truncation
        self._on_truncation = on_truncation
        self.summarizer = summarizer
        self.enable_summarization = enable_summarization
        self.summarization_threshold = summarization_threshold
        self.history: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        self.created_at = datetime.now()
        self.truncation_count = 0
        self.total_messages_removed = 0
        self.summaries: List["SummaryChunk"] = []  # Track all summaries created

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation"""
        self.history.append({"role": "user", "content": content})
        self._optimize()

    def add_assistant_message(
        self,
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        reasoning_content: Optional[str] = None,
    ) -> None:
        """Add an assistant message to the conversation"""
        # Validate that assistant messages have at least content or tool_calls
        # This prevents "Invalid assistant message" API errors
        if not content and not tool_calls:
            logger.warning("Attempted to add invalid assistant message (no content or tool_calls). "
                          "Converting reasoning_content to content if available.")
            # If we have reasoning_content, convert it to content
            if reasoning_content:
                content = f"[Reasoning: {reasoning_content[:200]}{'...' if len(reasoning_content) > 200 else ''}]"
            else:
                # Fallback: create minimal content to prevent API errors
                content = "[Empty assistant response]"

        msg: Dict[str, Any] = {"role": "assistant"}
        if content:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        self.history.append(msg)
        self._optimize()

        # Trigger checkpoint creation if available (called from agent)
        # This is a hook for the agent to create checkpoints after assistant messages

    def add_tool_result(self, tool_call_id: str, result: Dict[str, Any]) -> None:
        """Add a tool result to the conversation"""
        import json

        # Ensure result has standard format before stringifying
        # This ensures consistent structure even if tools don't use helper functions
        if "success" not in result:
            result["success"] = "error" not in result

        self.history.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(sanitize_object(result), ensure_ascii=False),  # Keep JSON but ensure format
            }
        )
        self._optimize()

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the current conversation history"""
        return self.history.copy()

    def clear(self, keep_system: bool = True) -> None:
        """Clear conversation history"""
        if keep_system and self.history and self.history[0].get("role") == "system":
            self.history = [self.history[0]]
        else:
            self.history = []

    def update_system_prompt(self, new_prompt: str) -> None:
        """
        Update the system prompt in the conversation history.

        Args:
            new_prompt: The new system prompt content
        """
        if self.history and self.history[0].get("role") == "system":
            self.history[0]["content"] = new_prompt
        else:
            # Insert system prompt at the beginning
            self.history.insert(0, {"role": "system", "content": new_prompt})

    def _optimize(self) -> None:
        """Optimize conversation history if it exceeds token limit."""
        current_tokens = get_conversation_tokens(self.history, self.model)

        # Calculate utilization and issue progressive warnings
        utilization = current_tokens / self.max_tokens if self.max_tokens > 0 else 0

        # Progressive warnings at 70%, 80%, 90%
        if utilization >= 0.9 and not getattr(self, '_warned_90', False):
            logger.warning(f"⚠️ Context window at {utilization*100:.1f}% capacity!")
            self._warned_90 = True
        elif utilization >= 0.8 and not getattr(self, '_warned_80', False):
            logger.warning(f"Context window at {utilization*100:.1f}% capacity")
            self._warned_80 = True
        elif utilization >= 0.7 and not getattr(self, '_warned_70', False):
            logger.info(f"Context window at {utilization*100:.1f}% capacity")
            self._warned_70 = True

        # Check if we need to optimize
        if current_tokens <= self.max_tokens:
            return

        old_count = len(self.history)

        # Try summarization first if enabled and we have a summarizer
        if self.enable_summarization and self.summarizer:
            if self.summarizer.should_summarize(
                self.history, current_tokens, self.max_tokens, self.summarization_threshold
            ):
                # Get messages to summarize (skip system, keep recent)
                # We need at least 5 messages to make summarization worthwhile
                messages_to_summarize = self.history[1 : -self.keep_recent]

                if len(messages_to_summarize) >= 5:
                    try:
                        summary = self.summarizer.summarize(
                            messages_to_summarize, max_summary_tokens=500
                        )
                        self.summaries.append(summary)

                        # Create summary message
                        summary_message = summary.to_message()

                        # Rebuild history: system + summary + recent
                        self.history = [
                            self.history[0],  # System prompt
                            summary_message,
                            *self.history[-self.keep_recent :],  # Recent messages
                        ]

                        new_count = len(self.history)
                        messages_removed = old_count - new_count

                        if self.warn_on_truncation:
                            logger.info(
                                f"Context summarized: {messages_removed} messages -> summary "
                                f"(summarization #{len(self.summaries)}, {new_count} messages remaining)"
                            )

                        # Call callback
                        if self._on_truncation:
                            try:
                                self._on_truncation(messages_removed, new_count)
                            except Exception as e:
                                logger.error(f"Truncation callback error: {e}")

                        return  # Done with summarization

                    except Exception as e:
                        logger.warning(f"Summarization failed, falling back to truncation: {e}")

        # Fallback to simple truncation
        self.history = truncate_history(
            self.history,
            max_tokens=self.max_tokens,
            keep_system=True,
            keep_recent=self.keep_recent,
            model=self.model,
        )
        new_count = len(self.history)

        # Track and report truncation
        if old_count != new_count:
            messages_removed = old_count - new_count
            self.truncation_count += 1
            self.total_messages_removed += messages_removed

            if self.warn_on_truncation:
                logger.warning(
                    f"Context truncated: removed {messages_removed} old messages "
                    f"(truncation #{self.truncation_count}, {new_count} messages remaining)"
                )

            # Call optional callback
            if self._on_truncation:
                try:
                    self._on_truncation(messages_removed, new_count)
                except Exception as e:
                    logger.error(f"Truncation callback error: {e}")

    def get_token_count(self) -> int:
        """Get current token count"""
        return get_conversation_tokens(self.history, self.model)

    def update_model(self, new_model: str) -> None:
        """
        Update the model reference for token counting.

        This is used when switching models while maintaining conversation history.

        Args:
            new_model: New model name to use for token counting
        """
        self.model = new_model

    def get_truncation_stats(self) -> Dict[str, Any]:
        """
        Get truncation and summarization statistics with token details.

        Returns:
            Dict with truncation and summarization metrics
        """
        current_tokens = self.get_token_count()
        current_messages = len(self.history)

        return {
            "truncation_count": self.truncation_count,
            "total_messages_removed": self.total_messages_removed,
            "summarization_count": len(self.summaries),
            "current_message_count": current_messages,
            "current_token_count": current_tokens,
            "max_tokens": self.max_tokens,
            "token_utilization": (current_tokens / self.max_tokens) * 100 if self.max_tokens > 0 else 0,
            "tokens_remaining": self.max_tokens - current_tokens if self.max_tokens > current_tokens else 0,
            "avg_tokens_per_message": current_tokens / max(1, current_messages),
            "keep_recent": self.keep_recent,
            "summarization_enabled": self.enable_summarization,
        }

    def get_summaries(self) -> List["SummaryChunk"]:
        """Get all summaries created during this conversation."""
        return self.summaries.copy()

    def validate_history(self) -> Dict[str, Any]:
        """
        Validate the entire conversation history for API compliance.

        Returns:
            Dict with validation results including any issues found.
        """
        issues = []

        for i, msg in enumerate(self.history):
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")

            # Validate assistant messages
            if role == "assistant":
                if not content and not tool_calls:
                    issues.append({
                        "index": i,
                        "type": "invalid_assistant_message",
                        "message": f"Assistant message at index {i} has no content or tool_calls",
                        "severity": "critical"  # Will cause API errors
                    })

            # Validate tool results
            elif role == "tool":
                if not isinstance(msg.get("content", ""), str):
                    issues.append({
                        "index": i,
                        "type": "invalid_tool_result",
                        "message": f"Tool result at index {i} has non-string content",
                        "severity": "warning"
                    })

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "message_count": len(self.history),
            "severity_levels": {
                "critical": len([i for i in issues if i["severity"] == "critical"]),
                "warning": len([i for i in issues if i["severity"] == "warning"])
            }
        }
