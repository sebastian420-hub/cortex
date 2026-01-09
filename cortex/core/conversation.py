"""Conversation history management"""

import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from .context import truncate_history, get_conversation_tokens

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
        on_truncation: Optional[Callable[[int, int], None]] = None
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
        """
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent
        self.model = model
        self.warn_on_truncation = warn_on_truncation
        self._on_truncation = on_truncation
        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        self.created_at = datetime.now()
        self.truncation_count = 0
        self.total_messages_removed = 0
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation"""
        self.history.append({
            "role": "user",
            "content": content
        })
        self._optimize()
    
    def add_assistant_message(
        self,
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        reasoning_content: Optional[str] = None
    ) -> None:
        """Add an assistant message to the conversation"""
        msg: Dict[str, Any] = {"role": "assistant"}
        if content:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        self.history.append(msg)
        self._optimize()
    
    def add_tool_result(self, tool_call_id: str, result: Dict[str, Any]) -> None:
        """Add a tool result to the conversation"""
        import json
        # Ensure result has standard format before stringifying
        # This ensures consistent structure even if tools don't use helper functions
        if "success" not in result:
            result["success"] = "error" not in result
        
        self.history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False)  # Keep JSON but ensure format
        })
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
    
    def _optimize(self) -> None:
        """Optimize conversation history if it exceeds token limit"""
        current_tokens = get_conversation_tokens(self.history, self.model)
        if current_tokens > self.max_tokens:
            old_count = len(self.history)
            self.history = truncate_history(
                self.history,
                max_tokens=self.max_tokens,
                keep_system=True,
                keep_recent=self.keep_recent,
                model=self.model
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
        Get truncation statistics.

        Returns:
            Dict with truncation metrics
        """
        return {
            "truncation_count": self.truncation_count,
            "total_messages_removed": self.total_messages_removed,
            "current_message_count": len(self.history),
            "current_token_count": self.get_token_count(),
            "max_tokens": self.max_tokens,
            "keep_recent": self.keep_recent,
        }

