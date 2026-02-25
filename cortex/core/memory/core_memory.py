"""Memory Bank for tracking key decisions, facts, and preferences during sessions."""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


class MemoryType(str, Enum):
    """Types of memory items."""

    DECISION = "decision"  # A choice made (e.g., "chose pytest over unittest")
    FACT = "fact"  # Learned information (e.g., "entry point is main.py")
    PREFERENCE = "preference"  # User preference (e.g., "prefers TypeScript")
    FILE = "file"  # Important file reference
    ERROR = "error"  # Notable error encountered
    CONTEXT = "context"  # General context information


class MemorySource(str, Enum):
    """Source of memory item."""

    USER = "user"  # Explicitly stated by user
    INFERRED = "inferred"  # Inferred from context/actions
    TOOL_RESULT = "tool_result"  # Learned from tool execution


@dataclass
class MemoryItem:
    """A single memory item."""

    type: MemoryType
    content: str
    source: MemorySource
    confidence: float = 1.0  # 0.0 to 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    last_verified: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "content": self.content,
            "source": self.source.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "last_verified": self.last_verified,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """Create from dictionary."""
        return cls(
            type=MemoryType(data["type"]),
            content=data["content"],
            source=MemorySource(data["source"]),
            confidence=data.get("confidence", 1.0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            last_verified=data.get("last_verified", data.get("timestamp", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
        )


class MemoryBank:
    """
    Tracks key decisions, facts, and preferences during a session.

    Memory is extracted from:
    - User messages (explicit preferences, requirements)
    - Assistant decisions (approach choices, tool selections)
    - Tool results (file contents, command outputs)

    Memory persists with session and injects into system prompt.
    """

    def __init__(self, max_items: int = 50):
        """
        Initialize memory bank.

        Args:
            max_items: Maximum items to retain (oldest pruned first)
        """
        self.items: List[MemoryItem] = []
        self.max_items = max_items
        self._files_read: set = set()  # Track files read (for dedup)

    def add(self, item: MemoryItem) -> None:
        """
        Add a memory item.

        Deduplicates similar content and prunes if over max.
        """
        # Check for duplicates (same type and similar content)
        for existing in self.items:
            if existing.type == item.type and self._is_similar(existing.content, item.content):
                # Update existing with higher confidence
                if item.confidence > existing.confidence:
                    existing.content = item.content
                    existing.confidence = item.confidence
                    existing.timestamp = item.timestamp
                return

        self.items.append(item)
        self._prune()

    def add_decision(
        self, decision: str, source: MemorySource = MemorySource.INFERRED, confidence: float = 0.8
    ) -> None:
        """Add a decision memory."""
        self.add(
            MemoryItem(
                type=MemoryType.DECISION, content=decision, source=source, confidence=confidence
            )
        )

    def add_fact(
        self, fact: str, source: MemorySource = MemorySource.TOOL_RESULT, confidence: float = 1.0
    ) -> None:
        """Add a fact memory."""
        self.add(
            MemoryItem(type=MemoryType.FACT, content=fact, source=source, confidence=confidence)
        )

    def add_preference(
        self, preference: str, source: MemorySource = MemorySource.USER, confidence: float = 0.9
    ) -> None:
        """Add a user preference."""
        self.add(
            MemoryItem(
                type=MemoryType.PREFERENCE, content=preference, source=source, confidence=confidence
            )
        )

    def add_file(
        self, filepath: str, description: str = "", source: MemorySource = MemorySource.TOOL_RESULT
    ) -> None:
        """Add an important file reference."""
        if filepath in self._files_read:
            return  # Already tracked

        self._files_read.add(filepath)
        content = f"{filepath}"
        if description:
            content += f" - {description}"

        self.add(
            MemoryItem(
                type=MemoryType.FILE,
                content=content,
                source=source,
                confidence=1.0,
                metadata={"filepath": filepath},
            )
        )

    def add_error(
        self, error: str, context: str = "", source: MemorySource = MemorySource.TOOL_RESULT
    ) -> None:
        """Add a notable error for future reference."""
        content = error
        if context:
            content = f"{error} (context: {context})"

        self.add(MemoryItem(type=MemoryType.ERROR, content=content, source=source, confidence=1.0))

    def get_by_type(self, memory_type: MemoryType) -> List[MemoryItem]:
        """Get all items of a specific type."""
        return [item for item in self.items if item.type == memory_type]

    def get_relevant(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """
        Get memories relevant to a query.

        Uses simple keyword matching for relevance scoring.
        """
        if not query or not self.items:
            return []

        query_words = set(query.lower().split())
        scored = []

        for item in self.items:
            content_words = set(item.content.lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                score = overlap * item.confidence
                scored.append((score, item))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def get_summary(self) -> str:
        """
        Get a formatted summary for system prompt injection.

        Returns a concise string summarizing key memories.
        """
        if not self.items:
            return ""

        sections = []

        # Key decisions
        decisions = self.get_by_type(MemoryType.DECISION)
        if decisions:
            decision_list = [f"- {d.content}" for d in decisions[:3]]
            sections.append("Key Decisions:\n" + "\n".join(decision_list))

        # Important facts
        facts = self.get_by_type(MemoryType.FACT)
        if facts:
            fact_list = [f"- {f.content}" for f in facts[:3]]
            sections.append("Known Facts:\n" + "\n".join(fact_list))

        # User preferences
        prefs = self.get_by_type(MemoryType.PREFERENCE)
        if prefs:
            pref_list = [f"- {p.content}" for p in prefs[:3]]
            sections.append("User Preferences:\n" + "\n".join(pref_list))

        # Files of interest (just count if many)
        files = self.get_by_type(MemoryType.FILE)
        if files:
            if len(files) <= 5:
                file_list = [f"- {f.content}" for f in files]
                sections.append("Files Referenced:\n" + "\n".join(file_list))
            else:
                sections.append(f"Files Referenced: {len(files)} files tracked")

        # Recent errors (limit to 2)
        errors = self.get_by_type(MemoryType.ERROR)
        if errors:
            error_list = [f"- {e.content}" for e in errors[-2:]]
            sections.append("Recent Errors:\n" + "\n".join(error_list))

        return "\n\n".join(sections)

    def get_full_display(self) -> str:
        """Get a detailed display of all memories for /memory command."""
        if not self.items:
            return "Memory bank is empty."

        lines = ["# Memory Bank Contents", ""]

        type_groups = {}
        for item in self.items:
            if item.type not in type_groups:
                type_groups[item.type] = []
            type_groups[item.type].append(item)

        type_names = {
            MemoryType.DECISION: "Decisions",
            MemoryType.FACT: "Facts",
            MemoryType.PREFERENCE: "Preferences",
            MemoryType.FILE: "Files",
            MemoryType.ERROR: "Errors",
            MemoryType.CONTEXT: "Context",
        }

        for mem_type, items in type_groups.items():
            lines.append(f"## {type_names.get(mem_type, mem_type.value)}")
            for item in items:
                conf = f"({item.confidence:.0%})" if item.confidence < 1.0 else ""
                lines.append(f"- {item.content} {conf}")
            lines.append("")

        lines.append(f"Total: {len(self.items)} memories")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all memories."""
        self.items.clear()
        self._files_read.clear()

    def _prune(self) -> None:
        """Prune old items if over max."""
        if len(self.items) > self.max_items:
            # Sort by confidence, then by timestamp
            # Keep highest confidence and most recent
            self.items.sort(key=lambda x: (x.confidence, x.timestamp), reverse=True)
            self.items = self.items[: self.max_items]

    def _is_similar(self, a: str, b: str, threshold: float = 0.7) -> bool:
        """Check if two strings are similar (simple word overlap)."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return a.lower() == b.lower()

        overlap = len(words_a & words_b)
        union = len(words_a | words_b)
        return (overlap / union) >= threshold if union > 0 else False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "items": [item.to_dict() for item in self.items],
            "max_items": self.max_items,
            "files_read": list(self._files_read),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryBank":
        """Deserialize from dictionary."""
        bank = cls(max_items=data.get("max_items", 50))
        bank.items = [MemoryItem.from_dict(item) for item in data.get("items", [])]
        bank._files_read = set(data.get("files_read", []))
        return bank


def extract_memories_from_messages(messages: List[Dict[str, Any]], memory_bank: MemoryBank) -> None:
    """
    Extract memories from conversation messages.

    Looks for:
    - User preferences ("I prefer...", "always use...", "don't...")
    - Decisions ("I'll use...", "chose...", "decided...")
    - File references from tool results
    - Errors from tool results
    """
    decision_patterns = [
        r"(?:I'll|Let me|I will|Going to|Decided to|Chose to)\s+(.+?)(?:\.|$)",
        r"(?:using|chose|selected|picked)\s+(\w+)\s+(?:for|because|since)",
    ]

    preference_patterns = [
        r"(?:I prefer|always use|don't use|never use|please use)\s+(.+?)(?:\.|$)",
        r"(?:should be|must be|needs to be)\s+(.+?)(?:\.|$)",
    ]

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if not content or not isinstance(content, str):
            continue

        # Extract from user messages
        if role == "user":
            for pattern in preference_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if len(match) > 5 and len(match) < 100:  # Reasonable length
                        memory_bank.add_preference(match.strip(), MemorySource.USER)

        # Extract from assistant messages
        elif role == "assistant":
            for pattern in decision_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if len(match) > 10 and len(match) < 150:
                        memory_bank.add_decision(match.strip(), MemorySource.INFERRED, 0.7)

        # Extract from tool results
        elif role == "tool":
            try:
                result = json.loads(content) if isinstance(content, str) else content
                if isinstance(result, dict):
                    # Track file reads
                    if result.get("success") and "path" in result:
                        memory_bank.add_file(result["path"])

                    # Track errors
                    if not result.get("success") and result.get("error"):
                        error_msg = result["error"]
                        if len(error_msg) < 200:
                            memory_bank.add_error(error_msg[:100])
            except (json.JSONDecodeError, TypeError):
                pass


def create_memory_bank(max_items: int = 50) -> MemoryBank:
    """Factory function to create a memory bank."""
    return MemoryBank(max_items=max_items)
