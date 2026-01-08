"""Conversation history management"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from .context import truncate_history, get_conversation_tokens


class ConversationManager:
    """Manages conversation history and context"""
    
    def __init__(
        self,
        system_prompt: str,
        max_tokens: int = 100000,
        keep_recent: int = 20
    ):
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent
        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        self.created_at = datetime.now()
    
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
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add an assistant message to the conversation"""
        msg: Dict[str, Any] = {"role": "assistant"}
        if content:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.history.append(msg)
        self._optimize()
    
    def add_tool_result(self, tool_call_id: str, result: Dict[str, Any]) -> None:
        """Add a tool result to the conversation"""
        import json
        self.history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(result)
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
        current_tokens = get_conversation_tokens(self.history)
        if current_tokens > self.max_tokens:
            self.history = truncate_history(
                self.history,
                max_tokens=self.max_tokens,
                keep_system=True,
                keep_recent=self.keep_recent
            )
    
    def get_token_count(self) -> int:
        """Get current token count"""
        return get_conversation_tokens(self.history)

