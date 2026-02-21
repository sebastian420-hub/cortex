"""Agent output mixin — output, validation, session lifecycle, cleanup."""

import json
import logging
from typing import Dict, Any, List, Optional

from rich.markdown import Markdown

from ..output import OutputFormat
from ..ui.console import console

logger = logging.getLogger(__name__)


class AgentOutputMixin:
    """Mixin providing output, validation, session lifecycle, and cleanup methods."""

    # Output helper methods for format-aware display
    def _is_text_output(self) -> bool:
        """Check if we're in text output mode (vs JSON modes)."""
        return self.output_format == OutputFormat.TEXT

    def _output_response(self, response: Dict[str, Any], is_final: bool = False) -> None:
        """Output a response using the appropriate formatter."""
        content = response.get("content", "")
        if not content:
            return

        if self._is_text_output():
            from ..utils.output_processing import process_model_output
            processed_content = process_model_output(content)
            # Always use simple markdown output (no Panel boxes)
            console.print(Markdown(processed_content))
        else:
            formatted = self.formatter.format_response(response)
            self.formatter.write(formatted)

    def _output_tool_result(
        self, tool_name: str, result: Dict[str, Any], arguments: Optional[Dict[str, Any]] = None
    ) -> None:
        """Output a tool result using the appropriate formatter."""
        if not self._is_text_output():
            formatted = self.formatter.format_tool_result(tool_name, result)
            self.formatter.write(formatted)
        # In text mode, tool results are shown by the tools themselves

    def _output_error(
        self, error: str, error_type: str = "error", context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Output an error using the appropriate formatter."""
        if self._is_text_output():
            console.print(f"[red]{error_type.upper()}:[/red] {error}")
        else:
            formatted = self.formatter.format_error(error, error_type, context)
            self.formatter.write(formatted)

    def _output_warning(self, message: str) -> None:
        """Output a warning message."""
        if self._is_text_output():
            console.print(f"[yellow]{message}[/yellow]")
        else:
            formatted = self.formatter.format_error(message, "warning")
            self.formatter.write(formatted)

    # Session lifecycle
    def _dispatch_session_start(self) -> None:
        """Dispatch session start event to hooks."""
        from ..hooks import SessionStartEvent

        event = SessionStartEvent(
            model=self.model,
            project_dir=str(self.project_dir),
            permission_mode=self.permission_mode,
            config={
                "max_iterations": self.config.max_iterations,
                "max_tokens": self.config.max_tokens,
            },
        )
        self.hook_manager.dispatch(event)

    def _dispatch_session_end(self) -> None:
        """Dispatch session end event to hooks."""
        from ..hooks import SessionEndEvent

        event = SessionEndEvent(
            model=self.model,
            project_dir=str(self.project_dir),
            messages_count=len(self.conversation.get_history()),
            tools_used=list(set(self._tools_used)),
        )
        self.hook_manager.dispatch(event)

    # Validation
    def _validate_messages_for_api(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate messages for API compliance to prevent "Invalid assistant message" errors.

        Returns:
            Dict with validation results and issues found.
        """
        issues = []

        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            content = msg.get("content")
            tool_calls = msg.get("tool_calls")

            # Validate assistant messages
            if role == "assistant":
                # Check for missing content key entirely
                if "content" not in msg:
                    issues.append(
                        {
                            "index": i,
                            "type": "missing_content_key",
                            "message": f"Assistant message at index {i} is missing 'content' key (strictly required by some providers)",
                            "severity": "critical",
                        }
                    )
                # Check for both empty content and empty tool calls
                elif not content and not tool_calls:
                    issues.append(
                        {
                            "index": i,
                            "type": "invalid_assistant_message",
                            "message": f"Assistant message at index {i} has no content or tool_calls",
                            "severity": "critical",  # Will cause API errors
                        }
                    )

            # Validate tool messages - content must be string
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
            "message_count": len(messages),
            "severity_levels": {
                "critical": len([i for i in issues if i["severity"] == "critical"]),
                "warning": len([i for i in issues if i["severity"] == "warning"]),
            },
        }

    def _repair_messages_for_api(
        self, messages: List[Dict[str, Any]], issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Attempt to automatically repair critical message validation issues.

        Args:
            messages: Original message list
            issues: List of validation issues (only critical ones should be passed)

        Returns:
            Repaired message list
        """
        repaired_messages = messages.copy()

        for issue in issues:
            idx = issue["index"]
            msg = repaired_messages[idx]

            if issue["type"] == "missing_content_key":
                repaired_messages[idx]["content"] = ""
            elif issue["type"] == "invalid_assistant_message":
                # Try to fix by converting reasoning_content to content
                if msg.get("reasoning_content"):
                    content = f"[Reasoning: {msg['reasoning_content'][:200]}{'...' if len(msg['reasoning_content']) > 200 else ''}]"
                    repaired_messages[idx]["content"] = content
                    logger.debug(
                        f"Repaired assistant message at index {idx} by converting reasoning to content"
                    )
                else:
                    # Fallback: add minimal content
                    repaired_messages[idx]["content"] = "[Repaired empty assistant response]"
                    logger.debug(
                        f"Repaired assistant message at index {idx} by adding minimal content"
                    )

        return repaired_messages

    def validate_session_health(self) -> Dict[str, Any]:
        """
        Validate the current session health and provide recovery recommendations.

        Returns:
            Dict with session health status and recommendations.
        """
        # Use conversation manager's validation
        history_validation = self.conversation.validate_history()

        # Additional checks
        issues = history_validation["issues"].copy()
        recommendations = []

        # Check for excessive message count
        if history_validation["message_count"] > 100:
            issues.append(
                {
                    "type": "high_message_count",
                    "message": f"Session has {history_validation['message_count']} messages, which may impact performance",
                    "severity": "warning",
                }
            )
            recommendations.append("Consider clearing old messages or starting a new session")

        # Check for repeated errors in recent history
        recent_messages = self.conversation.get_history()[-20:]  # Last 20 messages
        error_count = 0
        for msg in recent_messages:
            if msg.get("role") == "tool":
                try:
                    result = json.loads(msg.get("content", "{}"))
                    if not result.get("success", True):
                        error_count += 1
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse tool result JSON: {e}")
                    pass

        if error_count > 5:
            issues.append(
                {
                    "type": "frequent_errors",
                    "message": f"{error_count} errors in recent messages, indicating potential issues",
                    "severity": "warning",
                }
            )
            recommendations.append("Review recent tool executions for patterns")

        # Generate recovery recommendations based on issues
        if history_validation["severity_levels"]["critical"] > 0:
            recommendations.insert(
                0, "CRITICAL: Session has corrupted messages. Use '/clear' to start fresh"
            )
        elif history_validation["severity_levels"]["warning"] > 0:
            recommendations.insert(0, "Session has warnings. Monitor for issues")

        return {
            "healthy": len([i for i in issues if i["severity"] == "critical"]) == 0,
            "issues": issues,
            "recommendations": recommendations,
            "validation": history_validation,
        }

    # Token estimation
    def _estimate_api_call_tokens(
        self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> int:
        """
        Estimate token count for API call for rate limiting.

        Uses simple approximation: ~4 characters per token for English text.
        For code, this may underestimate, but it's conservative for rate limiting.

        Args:
            messages: List of message dictionaries
            tools: List of tool definitions

        Returns:
            Estimated token count
        """
        # Count characters in messages
        char_count = 0
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, str):
                    char_count += len(content)
                # Also count in tool calls/results
                if "tool_calls" in msg:
                    for call in msg.get("tool_calls", []):
                        if isinstance(call, dict):
                            char_count += len(str(call))
                if "tool_result" in msg:
                    char_count += len(str(msg.get("tool_result", "")))

        # Count characters in tool definitions
        for tool in tools or []:
            char_count += len(str(tool))

        # Approximate: 4 characters per token (conservative for rate limiting)
        tokens = max(1, int(char_count / 4))

        logger.debug(f"Estimated {tokens} tokens for API call ({char_count} chars)")
        return tokens

    # Conversation management
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get current conversation history"""
        return self.conversation.get_history()

    def clear_conversation(self) -> None:
        """Clear conversation history"""
        self.conversation.clear(keep_system=True)
        # Update system prompt
        self.conversation.history[0]["content"] = self._get_system_prompt()

    # Shutdown and cleanup
    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        self._shutdown_requested = True

    def _cleanup(self) -> None:
        """
        Cleanup resources on shutdown.
        Saves session state if dirty and dispatches session end event.
        """
        try:
            # Dispatch session end event
            self._dispatch_session_end()

            # Shutdown parallel executor
            if self.parallel_executor:
                self.parallel_executor.shutdown()

            # Note: Session saving is handled by CLI layer if needed
            # This cleanup focuses on internal state

        except Exception as e:
            # Log with traceback for debugging, but don't raise
            logger.warning(f"Error during cleanup: {e}", exc_info=True)

    # Context truncation callback
    def _on_context_truncation(self, messages_removed: int, remaining: int) -> None:
        """Callback when context is truncated."""
        if self._is_text_output():
            console.print(
                f"[yellow]Context truncated:[/yellow] Removed {messages_removed} old messages "
                f"({remaining} remaining)"
            )

    def _on_context_summarization(self, messages_removed: int, remaining: int) -> None:
        """Callback when context is summarized."""
        if self._is_text_output():
            console.print(
                f"[green]Context summarized:[/green] Compressed {messages_removed} old messages into a summary "
                f"({remaining} remaining)"
            )
