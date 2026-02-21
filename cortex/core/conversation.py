"""Conversation history management"""

import logging
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
from datetime import datetime
from .context import truncate_history, get_conversation_tokens
from ..utils.encoding import sanitize_object
from .model_context_limits import auto_configure_context, get_model_context_info

if TYPE_CHECKING:
    from .summarization import ConversationSummarizer, SummaryChunk

logger = logging.getLogger(__name__)

# Minimum tokens to reserve for the model's response to prevent cut-offs
RESPONSE_RESERVE_TOKENS = 4000


class ConversationManager:
    """Manages conversation history and context"""

    def __init__(
        self,
        system_prompt: str,
        max_tokens: Optional[int] = None,
        keep_recent: int = 20,
        model: str = "gpt-4",
        warn_on_truncation: bool = True,
        on_truncation: Optional[Callable[[int, int], None]] = None,
        on_summarization: Optional[Callable[[int, int], None]] = None,
        summarizer: Optional["ConversationSummarizer"] = None,
        enable_summarization: bool = True,
        summarization_threshold: float = 0.75,
    ):
        """
        Initialize conversation manager.

        Args:
            system_prompt: Initial system prompt
            max_tokens: Maximum tokens in context (None = auto-detect from model)
            keep_recent: Minimum messages to keep on truncation
            model: Model name for token counting
            warn_on_truncation: Whether to log warnings on truncation
            on_truncation: Optional callback(messages_removed, new_count) on truncation
            on_summarization: Optional callback(messages_removed, new_count) on summarization
            summarizer: Optional summarizer for intelligent context management
            enable_summarization: Whether to use summarization (vs pure truncation)
            summarization_threshold: Token threshold (0-1) to trigger summarization
        """
        self.system_prompt = system_prompt
        self.model = model

        # Auto-configure max_tokens based on model if not specified
        if max_tokens is None:
            self.max_tokens = auto_configure_context(model)
        else:
            # User-specified max_tokens - validate against model limits
            self.max_tokens = auto_configure_context(model, max_tokens)

        # Ensure we reserve room for the response
        self.max_tokens = max(2000, self.max_tokens - RESPONSE_RESERVE_TOKENS)

        context_info = get_model_context_info(model)
        logger.info(
            f"Initialized ConversationManager for {model}: {self.max_tokens:,} "
            f"history tokens (reserved {RESPONSE_RESERVE_TOKENS} for response, "
            f"model limit: {context_info['full_context_limit']:,})"
        )

        self.keep_recent = keep_recent
        self.warn_on_truncation = warn_on_truncation
        self._on_truncation = on_truncation
        self._on_summarization = on_summarization
        self.summarizer = summarizer
        self.enable_summarization = enable_summarization
        self.summarization_threshold = summarization_threshold
        self.history: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        self.created_at = datetime.now()
        self.truncation_count = 0
        self.total_messages_removed = 0
        self.summaries: List["SummaryChunk"] = []  # Track all summaries created

    def _get_max_tool_result_length(self) -> int:
        """Calculate maximum tool result length based on current context window."""
        # Aim for tool results to take at most 1/4 of the history window
        # Conversion: ~4 chars per token
        return (self.max_tokens // 4) * 4  # Keep it simple for now, but scaled

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
            # Check if this is reasoning-only response or truly invalid
            if reasoning_content:
                # Check if reasoning contains tool syntax (indicates model confusion)
                tool_syntax_patterns = [
                    "<tool_call>",
                    "</tool_call>",
                    "function_call",
                    "tool_use",
                    "<function_call>",
                ]
                has_tool_syntax = any(
                    pattern in reasoning_content.lower() for pattern in tool_syntax_patterns
                )

                if has_tool_syntax:
                    # Only log at debug level - don't warn users about this anymore
                    # The streaming layer should have already tried to extract tool calls
                    logger.debug(
                        "Model returned reasoning with tool syntax but no actual tool_calls. "
                        "Converting to content. "
                        f"Reasoning preview: {reasoning_content[:150]}..."
                    )
                else:
                    # Normal reasoning-only response - silent, no need to warn
                    logger.debug(
                        "Reasoning-only assistant message (no content or tool_calls). "
                        "Converting reasoning_content to content."
                    )

                # Convert reasoning to content for valid message structure
                content = (
                    f"[Reasoning: {reasoning_content[:200]}"
                    f"{'...' if len(reasoning_content) > 200 else ''}]"
                )
            else:
                # Truly empty response - this shouldn't happen but handle gracefully
                # Log at debug level instead of warning to reduce noise
                logger.debug(
                    "Adding placeholder content for empty assistant message to prevent API errors."
                )
                content = "[Empty assistant response]"

        msg: Dict[str, Any] = {"role": "assistant"}
        # ALWAYS include content key for assistant messages.
        # Some providers (like Arcee AI on OpenRouter) strictly require it even with tool_calls.
        msg["content"] = content if content is not None else ""

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

        # Convert result to JSON string
        result_json = json.dumps(sanitize_object(result), ensure_ascii=False)

        # Proactive truncation: limit tool result size before adding to history
        original_length = len(result_json)
        max_length = self._get_max_tool_result_length()
        if original_length > max_length:
            # Truncate the result content
            truncated_result = result.copy()
            truncated_result["data"] = {"truncated": True, "original_size": original_length}
            truncated_result["truncation_reason"] = (
                f"Tool result truncated from {original_length} to {max_length} chars "
                "to prevent context overflow"
            )
            result_json = json.dumps(sanitize_object(truncated_result), ensure_ascii=False)
            logger.warning(
                f"Proactively truncated tool result: {original_length} -> {len(result_json)} chars "
                f"(~{original_length // 4} -> ~{len(result_json) // 4} tokens)"
            )

        self.history.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result_json,  # Keep JSON but ensure format
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
        if utilization >= 0.9 and not getattr(self, "_warned_90", False):
            logger.warning(f"⚠️ Context window at {utilization*100:.1f}% capacity!")
            self._warned_90 = True
        elif utilization >= 0.8 and not getattr(self, "_warned_80", False):
            logger.warning(f"Context window at {utilization*100:.1f}% capacity")
            self._warned_80 = True
        elif utilization >= 0.7 and not getattr(self, "_warned_70", False):
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
                            logger.warning(
                                f"Context summarized: {messages_removed} messages -> summary "
                                f"(summarization #{len(self.summaries)}, "
                                f"{new_count} messages remaining)"
                            )

                        # Call callback
                        if self._on_summarization:
                            try:
                                self._on_summarization(messages_removed, new_count)
                            except Exception as e:
                                logger.error(f"Summarization callback error: {e}")

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
        Also updates max_tokens based on new model's context limits.

        Args:
            new_model: New model name to use for token counting
        """
        old_model = self.model
        self.model = new_model

        # Update max_tokens to match new model's capabilities
        old_max_tokens = self.max_tokens
        self.max_tokens = auto_configure_context(new_model)

        # Ensure we reserve room for the response
        self.max_tokens = max(2000, self.max_tokens - RESPONSE_RESERVE_TOKENS)

        if old_max_tokens != self.max_tokens:
            context_info = get_model_context_info(new_model)
            logger.info(
                f"Model switch: {old_model} -> {new_model}. "
                f"Context window adjusted: {old_max_tokens:,} -> {self.max_tokens:,} tokens "
                f"(model limit: {context_info['full_context_limit']:,})"
            )

            # If new model has smaller context, might need immediate optimization
            current_tokens = self.get_token_count()
            if current_tokens > self.max_tokens:
                logger.warning(
                    f"Current conversation ({current_tokens:,} tokens) exceeds new model's limit "
                    f"({self.max_tokens:,} tokens). Triggering optimization..."
                )
                self._optimize()

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
            "token_utilization": (
                (current_tokens / self.max_tokens) * 100 if self.max_tokens > 0 else 0
            ),
            "tokens_remaining": (
                self.max_tokens - current_tokens if self.max_tokens > current_tokens else 0
            ),
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
                # Check for missing content key entirely
                if "content" not in msg:
                    issues.append(
                        {
                            "index": i,
                            "type": "missing_content_key",
                            "message": (
                                f"Assistant message at index {i} is missing 'content' key "
                                f"(strictly required by some providers)"
                            ),
                            "severity": "critical",
                        }
                    )
                # Check for both empty content and empty tool calls
                elif not content and not tool_calls:
                    issues.append(
                        {
                            "index": i,
                            "type": "invalid_assistant_message",
                            "message": (
                                f"Assistant message at index {i} has no content or tool_calls"
                            ),
                            "severity": "critical",  # Will cause API errors
                        }
                    )

            # Validate tool results
            elif role == "tool":
                if not isinstance(msg.get("content", ""), str):
                    issues.append(
                        {
                            "index": i,
                            "type": "invalid_tool_result",
                            "message": f"Tool result at index {i} has non-string content",
                            "severity": "warning",
                        }
                    )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "message_count": len(self.history),
            "severity_levels": {
                "critical": len([i for i in issues if i["severity"] == "critical"]),
                "warning": len([i for i in issues if i["severity"] == "warning"]),
            },
        }
