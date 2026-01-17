"""Tests for prompt builder and adapter modules."""

import pytest
from pathlib import Path

from cortex.core.prompts import PromptBuilder, ToolFormatter
from cortex.core.prompt_adapter import (
    get_model_adaptation_notes,
    should_simplify_tools,
    get_tool_priority_list,
    get_context_budget,
    adapt_system_prompt,
    get_profile_info,
)
from cortex.core.model_capabilities import PromptStyle, CapabilityLevel


class TestToolFormatter:
    """Tests for ToolFormatter class."""

    @pytest.fixture
    def sample_tools(self):
        """Sample tool definitions for testing."""
        return [
            {
                "name": "read_file",
                "description": "Read contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file"},
                        "encoding": {"type": "string", "description": "File encoding"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "edit_file",
                "description": "Edit a file by replacing text",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file"},
                        "old_text": {"type": "string", "description": "Text to replace"},
                        "new_text": {"type": "string", "description": "Replacement text"},
                    },
                    "required": ["path", "old_text", "new_text"],
                },
            },
        ]

    def test_format_tools_detailed(self, sample_tools):
        """Test detailed tool formatting for capable models."""
        builder = PromptBuilder("claude-3-5-sonnet")
        formatted = builder.tool_formatter.format_tools(sample_tools)

        assert "# Available Tools" in formatted
        assert "read_file" in formatted
        assert "edit_file" in formatted
        assert "**Parameters:**" in formatted
        assert "**Example:**" in formatted

    def test_format_tools_concise(self, sample_tools):
        """Test concise tool formatting for medium models."""
        builder = PromptBuilder("llama3.2")
        formatted = builder.tool_formatter.format_tools(sample_tools)

        assert "# Tools" in formatted
        assert "read_file" in formatted
        # Concise format should be shorter
        assert "**Parameters:**" not in formatted

    def test_format_tools_explicit(self, sample_tools):
        """Test explicit tool formatting for smaller models."""
        builder = PromptBuilder("mistral")
        formatted = builder.tool_formatter.format_tools(sample_tools)

        assert "TOOLS" in formatted
        assert "WHAT IT DOES" in formatted
        assert "REQUIRED PARAMETERS" in formatted


class TestPromptBuilder:
    """Tests for PromptBuilder class."""

    @pytest.fixture
    def sample_tools(self):
        """Sample tools for testing."""
        return [
            {"name": "read_file", "description": "Read a file", "parameters": {}},
            {"name": "write_file", "description": "Write a file", "parameters": {}},
        ]

    def test_builder_initialization(self):
        """Test PromptBuilder initialization."""
        builder = PromptBuilder("llama3.2")

        assert builder.model_name == "llama3.2"
        assert builder.profile is not None
        assert builder.tool_formatter is not None

    def test_build_system_prompt_basic(self, sample_tools):
        """Test basic system prompt building."""
        builder = PromptBuilder("llama3.2")
        prompt = builder.build_system_prompt(tools=sample_tools)

        assert "Cortex" in prompt
        assert "read_file" in prompt

    def test_build_system_prompt_with_planning(self, sample_tools):
        """Test system prompt with planning enabled."""
        builder = PromptBuilder("claude-3-5-sonnet")
        prompt = builder.build_system_prompt(
            tools=sample_tools,
            enable_planning=True,
        )

        assert "Planning" in prompt or "plan" in prompt.lower()

    def test_build_system_prompt_with_memory(self, sample_tools):
        """Test system prompt with memory enabled."""
        builder = PromptBuilder("claude-3-5-sonnet")
        prompt = builder.build_system_prompt(
            tools=sample_tools,
            enable_memory=True,
        )

        assert "Memory" in prompt or "memory" in prompt.lower()

    def test_build_system_prompt_with_state_context(self, sample_tools):
        """Test system prompt with state context."""
        builder = PromptBuilder("llama3.2")
        prompt = builder.build_system_prompt(
            tools=sample_tools,
            state_context="Current task: Fix bug in main.py",
        )

        assert "Current State" in prompt
        assert "Fix bug" in prompt

    def test_get_profile_summary(self):
        """Test get_profile_summary method."""
        builder = PromptBuilder("claude-3-5-sonnet")
        summary = builder.get_profile_summary()

        assert summary["model"] == "claude-3-5-sonnet"
        assert summary["prompt_style"] == "detailed"
        assert "context_window" in summary


class TestPromptAdapter:
    """Tests for prompt adapter functions."""

    def test_get_model_adaptation_notes_capable_model(self):
        """Test that capable models get minimal adaptations."""
        notes = get_model_adaptation_notes("claude-3-5-sonnet")
        # Capable models should have empty or minimal notes
        assert notes == "" or len(notes) < 200

    def test_get_model_adaptation_notes_smaller_model(self):
        """Test that smaller models get more guidance."""
        notes = get_model_adaptation_notes("mistral")
        # Smaller models should get explicit guidance
        assert len(notes) > 0
        assert "Tool" in notes or "step" in notes.lower()

    def test_should_simplify_tools(self):
        """Test should_simplify_tools function."""
        # Large tool count for small model
        assert should_simplify_tools("mistral", 50) is True
        # Small tool count for large model
        assert should_simplify_tools("claude-3-5-sonnet", 10) is False

    def test_get_tool_priority_list(self):
        """Test get_tool_priority_list function."""
        priority = get_tool_priority_list("claude-3-5-sonnet")
        # Core tools should always be first
        assert "read_file" in priority
        assert "edit_file" in priority

        # Smaller models get shorter list
        small_priority = get_tool_priority_list("mistral")
        assert len(small_priority) <= len(priority)

    def test_get_context_budget(self):
        """Test get_context_budget function."""
        budget = get_context_budget("claude-3-5-sonnet")

        assert "system_prompt" in budget
        assert "tools" in budget
        assert "conversation" in budget
        assert "reserve" in budget
        # Total should roughly equal context window
        total = sum(budget.values())
        assert total > 100000  # Claude has large context

    def test_adapt_system_prompt(self):
        """Test adapt_system_prompt function."""
        base = "You are a helpful assistant."
        adapted = adapt_system_prompt(base, "mistral")

        # Should include adaptations for smaller model
        assert len(adapted) >= len(base)

    def test_adapt_system_prompt_disabled(self):
        """Test adapt_system_prompt with adaptations disabled."""
        base = "You are a helpful assistant."
        adapted = adapt_system_prompt(base, "mistral", include_adaptations=False)

        # Should return unchanged
        assert adapted == base

    def test_get_profile_info(self):
        """Test get_profile_info function."""
        info = get_profile_info("llama3.2")

        assert info["model"] == "llama3.2"
        assert "profile_name" in info
        assert "prompt_style" in info
        assert "context_window" in info
        assert "tool_following" in info
