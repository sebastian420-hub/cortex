"""
Simple Tool Implementations

This module contains example tools demonstrating the Cortex plugin pattern.
"""

import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from collections import Counter

# Import the base class from cortex
from cortex.tools.base import Tool


class UUIDTool(Tool):
    """
    Generate UUIDs (Universally Unique Identifiers).

    This is a simple, stateless tool that demonstrates basic tool structure.
    """

    def execute(
        self,
        version: int = 4,
        count: int = 1,
        uppercase: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate one or more UUIDs.

        Args:
            version: UUID version (1 or 4). Version 4 is random, version 1 is time-based.
            count: Number of UUIDs to generate (max 100)
            uppercase: Return UUIDs in uppercase

        Returns:
            Success response with list of UUIDs
        """
        # Validate version
        if version not in [1, 4]:
            return self._create_error(
                f"Invalid UUID version: {version}. Must be 1 or 4.",
                "validation",
                provided_version=version,
                valid_versions=[1, 4],
            )

        # Validate count
        if count < 1:
            return self._create_error(
                "Count must be at least 1",
                "validation",
                provided_count=count,
            )

        # Limit to prevent abuse
        count = min(count, 100)

        # Generate UUIDs
        uuids = []
        for _ in range(count):
            if version == 1:
                new_uuid = str(uuid.uuid1())
            else:
                new_uuid = str(uuid.uuid4())

            if uppercase:
                new_uuid = new_uuid.upper()
            uuids.append(new_uuid)

        # Display in console if available
        if self.console:
            self.console.print(f"[green]Generated {len(uuids)} UUID(s)[/green]")
            for u in uuids[:5]:  # Show first 5
                self.console.print(f"  {u}")
            if len(uuids) > 5:
                self.console.print(f"  ... and {len(uuids) - 5} more")

        return self._create_success(
            uuids=uuids,
            count=len(uuids),
            version=version,
        )


class TextStatsTool(Tool):
    """
    Analyze text and return statistics.

    This tool demonstrates working with text input and returning structured data.
    """

    def execute(
        self,
        text: str,
        include_frequency: bool = False,
    ) -> Dict[str, Any]:
        """
        Analyze text and return statistics.

        Args:
            text: The text to analyze
            include_frequency: Include character frequency analysis

        Returns:
            Success response with text statistics
        """
        # Validate input
        if not text:
            return self._create_error(
                "Text is required",
                "validation",
                hint="Provide some text to analyze",
            )

        # Calculate statistics
        lines = text.split("\n")
        words = text.split()
        chars = len(text)
        chars_no_space = len(text.replace(" ", "").replace("\n", ""))

        stats = {
            "characters": chars,
            "characters_no_whitespace": chars_no_space,
            "words": len(words),
            "lines": len(lines),
            "average_word_length": round(chars_no_space / len(words), 2) if words else 0,
            "average_line_length": round(chars / len(lines), 2) if lines else 0,
        }

        # Optional frequency analysis
        if include_frequency:
            # Character frequency (top 10)
            char_counts = Counter(text.lower())
            # Remove whitespace from frequency
            char_counts.pop(" ", None)
            char_counts.pop("\n", None)
            char_counts.pop("\t", None)

            stats["top_characters"] = dict(char_counts.most_common(10))

            # Word frequency (top 10)
            word_counts = Counter(word.lower().strip(".,!?;:") for word in words)
            stats["top_words"] = dict(word_counts.most_common(10))

        # Display in console
        if self.console:
            from rich.table import Table

            table = Table(title="Text Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Characters", str(stats["characters"]))
            table.add_row("Characters (no whitespace)", str(stats["characters_no_whitespace"]))
            table.add_row("Words", str(stats["words"]))
            table.add_row("Lines", str(stats["lines"]))
            table.add_row("Avg Word Length", str(stats["average_word_length"]))

            self.console.print(table)

        return self._create_success(**stats)


# ============================================
# PLUGIN EXPORT - Required for registry loading
# ============================================

# Schema for UUID tool
UUID_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_uuid",
        "description": "Generate UUIDs (Universally Unique Identifiers). "
        "Supports UUID version 1 (time-based) and version 4 (random). "
        "Useful for generating unique identifiers for database records, files, or any other purpose.",
        "parameters": {
            "type": "object",
            "properties": {
                "version": {
                    "type": "integer",
                    "enum": [1, 4],
                    "description": "UUID version. 4 = random (default), 1 = time-based",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of UUIDs to generate (default: 1, max: 100)",
                },
                "uppercase": {
                    "type": "boolean",
                    "description": "Return UUIDs in uppercase (default: false)",
                },
            },
            "required": [],
        },
    },
}

# Schema for text stats tool
TEXT_STATS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "text_stats",
        "description": "Analyze text and return statistics including character count, word count, "
        "line count, and average lengths. Optionally includes character and word frequency analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to analyze",
                },
                "include_frequency": {
                    "type": "boolean",
                    "description": "Include top 10 character and word frequency (default: false)",
                },
            },
            "required": ["text"],
        },
    },
}

# Export list - this is what the registry looks for
PLUGIN_TOOLS = [
    {
        "name": "generate_uuid",
        "class": UUIDTool,
        "schema": UUID_TOOL_SCHEMA,
        "namespace": "examples",  # Tools will be namespaced as "examples:generate_uuid"
        "enabled": True,
    },
    {
        "name": "text_stats",
        "class": TextStatsTool,
        "schema": TEXT_STATS_SCHEMA,
        "namespace": "examples",
        "enabled": True,
    },
]
