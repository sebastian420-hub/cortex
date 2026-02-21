"""Context summarization for intelligent history management."""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from .context import count_message_tokens, estimate_tokens

if TYPE_CHECKING:
    from .providers import ModelProvider

logger = logging.getLogger(__name__)


class SummarizationStrategy(Enum):
    """Strategy for summarization."""

    SIMPLE = "simple"  # Basic extraction of key points
    LLM_BASED = "llm_based"  # Use LLM to summarize
    HYBRID = "hybrid"  # Combine both approaches


@dataclass
class SummaryChunk:
    """A summarized chunk of conversation."""

    original_message_count: int
    original_token_count: int
    summary_token_count: int
    summary_content: str
    key_decisions: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_read: List[str] = field(default_factory=list)
    commands_executed: List[str] = field(default_factory=list)
    errors_encountered: List[str] = field(default_factory=list)
    timestamp_start: str = ""
    timestamp_end: str = ""

    def to_message(self) -> Dict[str, Any]:
        """Convert summary to a message format for injection into conversation."""
        sections = [f"[CONVERSATION SUMMARY - {self.original_message_count} messages summarized]"]
        sections.append(self.summary_content)

        if self.files_modified:
            sections.append(f"\nFiles modified: {', '.join(self.files_modified[:10])}")
        if self.files_read:
            sections.append(f"Files read: {', '.join(self.files_read[:10])}")
        if self.commands_executed:
            sections.append(f"Commands executed: {len(self.commands_executed)}")
        if self.errors_encountered:
            sections.append(f"Errors encountered: {len(self.errors_encountered)}")
        if self.key_decisions:
            sections.append("\nKey decisions: " + "; ".join(self.key_decisions[:5]))

        return {"role": "system", "content": "\n".join(sections)}


@dataclass
class SummarizationConfig:
    """Configuration for summarization."""

    enabled: bool = True
    strategy: SummarizationStrategy = SummarizationStrategy.SIMPLE
    trigger_threshold: float = 0.8  # Summarize at 80% token capacity
    max_summary_tokens: int = 500
    preserve_tool_results: bool = True
    preserve_errors: bool = True
    min_messages_to_summarize: int = 5


class ConversationSummarizer(ABC):
    """Base class for conversation summarization."""

    @abstractmethod
    def summarize(
        self, messages: List[Dict[str, Any]], max_summary_tokens: int = 500
    ) -> SummaryChunk:
        """
        Summarize a list of messages.

        Args:
            messages: Messages to summarize
            max_summary_tokens: Maximum tokens for the summary

        Returns:
            SummaryChunk with the summarized content
        """
        pass

    def should_summarize(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: int,
        max_tokens: int,
        threshold: float = 0.8,
    ) -> bool:
        """
        Determine if summarization should occur.

        Args:
            messages: Current conversation history
            current_tokens: Current token count
            max_tokens: Maximum allowed tokens
            threshold: Percentage of max_tokens to trigger summarization

        Returns:
            True if summarization should occur
        """
        return current_tokens > (max_tokens * threshold)


class SimpleSummarizer(ConversationSummarizer):
    """
    Extract key information without using LLM.

    Extracts:
    - User requests (key phrases)
    - Files read/written
    - Commands executed
    - Errors encountered
    - Decisions made
    """

    def summarize(
        self, messages: List[Dict[str, Any]], max_summary_tokens: int = 500
    ) -> SummaryChunk:
        """Extract key information from messages."""
        from .context import estimate_tokens

        files_modified = set()
        files_read = set()
        commands_executed = []
        errors_encountered = []
        key_decisions = []
        user_requests = []

        original_token_count = 0

        for msg in messages:
            # Use accurate message token counting
            original_token_count += count_message_tokens(msg, model="gpt-4")

            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                # Extract user requests
                if content and len(content) < 200:
                    user_requests.append(content)
                elif content:
                    # Truncate long requests
                    user_requests.append(content[:100] + "...")

            elif role == "assistant":
                # Extract tool calls
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args = func.get("arguments", {})

                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}

                    # Track files
                    if name == "read_file":
                        path = args.get("path", "")
                        if path:
                            files_read.add(path)
                    elif name == "write_file":
                        path = args.get("path", "")
                        if path:
                            files_modified.add(path)
                    elif name == "execute_command":
                        cmd = args.get("command", "")
                        if cmd:
                            commands_executed.append(cmd[:50])

                # Look for decisions in content
                if content:
                    decisions = self._extract_decisions(content)
                    key_decisions.extend(decisions)

            elif role == "tool":
                # Check for errors in tool results
                try:
                    result = json.loads(content) if isinstance(content, str) else content
                    if isinstance(result, dict):
                        if not result.get("success", True):
                            error = result.get("error", "Unknown error")
                            errors_encountered.append(error[:100])
                except (json.JSONDecodeError, TypeError):
                    pass

        # Build summary content
        summary_parts = []

        if user_requests:
            # Deduplicate and limit requests
            unique_requests = list(dict.fromkeys(user_requests))[:5]
            summary_parts.append("User asked: " + "; ".join(unique_requests))

        if files_modified:
            summary_parts.append(f"Modified {len(files_modified)} files")

        if commands_executed:
            summary_parts.append(f"Executed {len(commands_executed)} commands")

        if errors_encountered:
            summary_parts.append(f"Encountered {len(errors_encountered)} errors")

        summary_content = ". ".join(summary_parts) if summary_parts else "General conversation"

        summary_token_count = estimate_tokens(summary_content)

        return SummaryChunk(
            original_message_count=len(messages),
            original_token_count=original_token_count,
            summary_token_count=summary_token_count,
            summary_content=summary_content,
            key_decisions=key_decisions[:5],
            files_modified=list(files_modified),
            files_read=list(files_read),
            commands_executed=commands_executed[:10],
            errors_encountered=errors_encountered[:5],
            timestamp_start=datetime.now().isoformat(),
            timestamp_end=datetime.now().isoformat(),
        )

    def _extract_decisions(self, content: str) -> List[str]:
        """Extract decision-like statements from content."""
        decisions = []

        # Look for decision patterns
        patterns = [
            r"I(?:'ll| will) ([^.!?]{10,100})[.!?]",
            r"Let(?:'s| me) ([^.!?]{10,100})[.!?]",
            r"I decided to ([^.!?]{10,100})[.!?]",
            r"The solution is to ([^.!?]{10,100})[.!?]",
            r"Found that ([^.!?]{10,100})[.!?]",
            r"The code shows ([^.!?]{10,100})[.!?]",
            r"Verified that ([^.!?]{10,100})[.!?]",
            r"Discovered ([^.!?]{10,100})[.!?]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches[:2]:  # Max 2 per pattern
                decisions.append(match.strip())

        return decisions[:5]  # Max 5 total


class LLMSummarizer(ConversationSummarizer):
    """
    Use LLM to create intelligent summaries.

    This provides higher quality summaries but requires API calls.
    """

    def __init__(self, provider: "ModelProvider", model: str):
        self.provider = provider
        self.model = model

    def summarize(
        self, messages: List[Dict[str, Any]], max_summary_tokens: int = 500
    ) -> SummaryChunk:
        """Use LLM to summarize messages."""
        from .context import estimate_tokens

        # Calculate original tokens using accurate message counting
        original_token_count = sum(count_message_tokens(msg, model="gpt-4") for msg in messages)

        # Prepare messages for summarization
        messages_text = self._format_messages_for_summary(messages)

        # Create summarization prompt
        prompt = f"""Summarize this conversation excerpt concisely. Focus on:
1. What the user asked for
2. What actions were taken (files read/written, commands run)
3. Any errors or issues encountered
4. Key decisions made

Keep the summary under {max_summary_tokens} tokens.

Conversation:
{messages_text}

Summary:"""

        try:
            response = self.provider.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates concise conversation summaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=[],
            )

            summary_content = response["message"].get("content", "")
            summary_token_count = estimate_tokens(summary_content)

            # Also extract structured info using simple method
            simple = SimpleSummarizer()
            simple_summary = simple.summarize(messages, max_summary_tokens)

            return SummaryChunk(
                original_message_count=len(messages),
                original_token_count=original_token_count,
                summary_token_count=summary_token_count,
                summary_content=summary_content,
                key_decisions=simple_summary.key_decisions,
                files_modified=simple_summary.files_modified,
                files_read=simple_summary.files_read,
                commands_executed=simple_summary.commands_executed,
                errors_encountered=simple_summary.errors_encountered,
                timestamp_start=datetime.now().isoformat(),
                timestamp_end=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.warning(f"LLM summarization failed, falling back to simple: {e}")
            # Fallback to simple summarization
            simple = SimpleSummarizer()
            return simple.summarize(messages, max_summary_tokens)

    def _format_messages_for_summary(
        self, messages: List[Dict[str, Any]], max_chars: int = 5000
    ) -> str:
        """Format messages for the summarization prompt."""
        parts = []

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "tool":
                # Abbreviate tool results
                try:
                    result = json.loads(content) if isinstance(content, str) else content
                    if isinstance(result, dict):
                        success = result.get("success", True)
                        content = f"[Tool result: {'success' if success else 'error'}]"
                except (json.JSONDecodeError, TypeError, KeyError):
                    content = "[Tool result]"

            line = f"{role.upper()}: {content}"
            parts.append(line)

        full_text = "\n".join(parts)
        if len(full_text) > max_chars:
            return full_text[: max_chars - 3] + "..."
        return full_text


class HybridSummarizer(ConversationSummarizer):
    """
    Combine simple extraction with LLM refinement.

    Uses simple extraction first, then optionally refines with LLM
    if provider is available.
    """

    def __init__(self, provider: Optional["ModelProvider"] = None, model: str = ""):
        self.simple = SimpleSummarizer()
        self.llm = LLMSummarizer(provider, model) if provider else None

    def summarize(
        self, messages: List[Dict[str, Any]], max_summary_tokens: int = 500
    ) -> SummaryChunk:
        """Combine simple and LLM summarization."""
        # Always do simple extraction first
        simple_summary = self.simple.summarize(messages, max_summary_tokens)

        # If LLM available and messages are substantial, enhance with LLM
        if self.llm and len(messages) > 10:
            try:
                llm_summary = self.llm.summarize(messages, max_summary_tokens)
                # Merge: use LLM content but keep simple's structured data
                return SummaryChunk(
                    original_message_count=simple_summary.original_message_count,
                    original_token_count=simple_summary.original_token_count,
                    summary_token_count=llm_summary.summary_token_count,
                    summary_content=llm_summary.summary_content,
                    key_decisions=simple_summary.key_decisions,
                    files_modified=simple_summary.files_modified,
                    files_read=simple_summary.files_read,
                    commands_executed=simple_summary.commands_executed,
                    errors_encountered=simple_summary.errors_encountered,
                    timestamp_start=simple_summary.timestamp_start,
                    timestamp_end=simple_summary.timestamp_end,
                )
            except Exception as e:
                logger.warning(f"LLM enhancement failed: {e}")

        return simple_summary


def create_summarizer(
    strategy: SummarizationStrategy, provider: Optional["ModelProvider"] = None, model: str = ""
) -> ConversationSummarizer:
    """
    Factory function to create a summarizer based on strategy.

    Args:
        strategy: Summarization strategy to use
        provider: Model provider (required for LLM-based strategies)
        model: Model name (required for LLM-based strategies)

    Returns:
        ConversationSummarizer instance
    """
    if strategy == SummarizationStrategy.SIMPLE:
        return SimpleSummarizer()
    elif strategy == SummarizationStrategy.LLM_BASED:
        if not provider:
            logger.warning("LLM summarization requested but no provider, falling back to simple")
            return SimpleSummarizer()
        return LLMSummarizer(provider, model)
    elif strategy == SummarizationStrategy.HYBRID:
        return HybridSummarizer(provider, model)
    else:
        return SimpleSummarizer()
