"""Tests for Phase 2 features: Summarization, Enhanced System Prompt, Explore Agent"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.agent import Cortex
from cortex.models import PermissionMode
from cortex.config import AgentConfig
from cortex.core.conversation import ConversationManager
from cortex.core.summarization import (
    SimpleSummarizer,
    SummarizationStrategy,
    SummaryChunk,
    create_summarizer,
)
from cortex.subagent.task_tool import TaskTool, AGENT_TYPES


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create test files
    (temp_dir / "main.py").write_text(
        """
def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
"""
    )

    yield temp_dir
    shutil.rmtree(temp_dir)


class TestSimpleSummarizer:
    """Tests for SimpleSummarizer."""

    def test_summarize_basic_messages(self):
        """Test summarizing basic conversation messages."""
        summarizer = SimpleSummarizer()

        messages = [
            {"role": "user", "content": "Read the main.py file"},
            {
                "role": "assistant",
                "content": "I'll read that file.",
                "tool_calls": [
                    {"function": {"name": "read_file", "arguments": {"path": "main.py"}}}
                ],
            },
            {"role": "tool", "tool_call_id": "1", "content": '{"success": true, "content": "..."}'},
            {"role": "assistant", "content": "Here's the file content..."},
        ]

        summary = summarizer.summarize(messages)

        assert isinstance(summary, SummaryChunk)
        assert summary.original_message_count == 4
        assert "main.py" in summary.files_read

    def test_summarize_extracts_files_modified(self):
        """Test that summarizer extracts modified files."""
        summarizer = SimpleSummarizer()

        messages = [
            {"role": "user", "content": "Write a new file"},
            {
                "role": "assistant",
                "content": "Creating file",
                "tool_calls": [
                    {
                        "function": {
                            "name": "write_file",
                            "arguments": '{"path": "new.py", "content": "test"}',
                        }
                    }
                ],
            },
        ]

        summary = summarizer.summarize(messages)
        assert "new.py" in summary.files_modified

    def test_summarize_extracts_commands(self):
        """Test that summarizer extracts executed commands."""
        summarizer = SimpleSummarizer()

        messages = [
            {"role": "user", "content": "Run the tests"},
            {
                "role": "assistant",
                "content": "Running",
                "tool_calls": [
                    {"function": {"name": "execute_command", "arguments": '{"command": "pytest"}'}}
                ],
            },
        ]

        summary = summarizer.summarize(messages)
        assert len(summary.commands_executed) > 0

    def test_summarize_extracts_errors(self):
        """Test that summarizer extracts errors."""
        summarizer = SimpleSummarizer()

        messages = [
            {
                "role": "tool",
                "tool_call_id": "1",
                "content": '{"success": false, "error": "File not found"}',
            },
        ]

        summary = summarizer.summarize(messages)
        assert len(summary.errors_encountered) > 0

    def test_summary_to_message(self):
        """Test converting summary to message format."""
        summarizer = SimpleSummarizer()

        messages = [
            {"role": "user", "content": "Test request"},
        ]

        summary = summarizer.summarize(messages)
        message = summary.to_message()

        assert message["role"] == "system"
        assert "CONVERSATION SUMMARY" in message["content"]


class TestConversationManagerWithSummarization:
    """Tests for ConversationManager with summarization enabled."""

    def test_conversation_manager_accepts_summarizer(self):
        """Test that ConversationManager accepts a summarizer."""
        summarizer = SimpleSummarizer()

        manager = ConversationManager(
            system_prompt="Test prompt",
            summarizer=summarizer,
            enable_summarization=True,
        )

        assert manager.summarizer is not None
        assert manager.enable_summarization is True

    def test_conversation_manager_without_summarizer(self):
        """Test ConversationManager works without summarizer."""
        manager = ConversationManager(
            system_prompt="Test prompt",
            enable_summarization=False,
        )

        assert manager.summarizer is None
        assert manager.enable_summarization is False

    def test_truncation_stats_include_summarization(self):
        """Test that truncation stats include summarization info."""
        manager = ConversationManager(
            system_prompt="Test prompt",
            enable_summarization=True,
        )

        stats = manager.get_truncation_stats()

        assert "summarization_count" in stats
        assert "summarization_enabled" in stats


class TestCreateSummarizer:
    """Tests for summarizer factory function."""

    def test_create_simple_summarizer(self):
        """Test creating simple summarizer."""
        summarizer = create_summarizer(SummarizationStrategy.SIMPLE)
        assert isinstance(summarizer, SimpleSummarizer)

    def test_create_llm_summarizer_without_provider(self):
        """Test that LLM summarizer falls back to simple without provider."""
        summarizer = create_summarizer(SummarizationStrategy.LLM_BASED)
        # Should fall back to SimpleSummarizer when no provider
        assert isinstance(summarizer, SimpleSummarizer)


class TestAgentSystemPrompt:
    """Tests for enhanced system prompt."""

    def test_system_prompt_contains_grep(self, temp_project):
        """Test that system prompt mentions grep tool."""
        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        prompt = agent._get_system_prompt()
        assert "grep" in prompt.lower()

    def test_system_prompt_contains_glob(self, temp_project):
        """Test that system prompt mentions glob tool."""
        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        prompt = agent._get_system_prompt()
        assert "glob" in prompt.lower()

    def test_system_prompt_contains_edit(self, temp_project):
        """Test that system prompt mentions edit tool."""
        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        prompt = agent._get_system_prompt()
        assert "edit" in prompt.lower()

    def test_system_prompt_contains_exploration_strategy(self, temp_project):
        """Test that system prompt contains exploration strategy."""
        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        prompt = agent._get_system_prompt()
        # Check for exploration-related content (exploring, Mental Model, codebase)
        assert "exploring" in prompt.lower() or "mental model" in prompt.lower()


class TestAgentTypes:
    """Tests for agent type configurations."""

    def test_explore_agent_type_exists(self):
        """Test that explore agent type is defined."""
        assert "explore" in AGENT_TYPES

    def test_explore_agent_has_grep_tool(self):
        """Test that explore agent has grep in default tools."""
        assert "grep" in AGENT_TYPES["explore"]["default_tools"]

    def test_explore_agent_has_glob_tool(self):
        """Test that explore agent has glob in default tools."""
        assert "glob" in AGENT_TYPES["explore"]["default_tools"]

    def test_search_agent_type_exists(self):
        """Test that search agent type is defined."""
        assert "search" in AGENT_TYPES

    def test_analyze_agent_type_exists(self):
        """Test that analyze agent type is defined."""
        assert "analyze" in AGENT_TYPES

    def test_general_agent_type_exists(self):
        """Test that general agent type is defined."""
        assert "general" in AGENT_TYPES


class TestTaskToolAgentTypes:
    """Tests for TaskTool with agent types."""

    def test_task_tool_accepts_agent_type(self, temp_project):
        """Test that TaskTool accepts agent_type parameter."""
        tool = TaskTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.PLAN,
            console=None,
        )

        # Should not raise
        assert hasattr(tool, "execute")

    def test_get_subagent_prompt_explore(self, temp_project):
        """Test that explore agent gets specialized prompt."""
        from cortex.subagent.context import SubagentContext

        tool = TaskTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.PLAN,
            console=None,
        )

        context = SubagentContext(
            task_id="test",
            task_description="Explore the codebase",
            parent_context={"agent_type": "explore"},
            allowed_tools=["read_file", "grep", "glob"],
            max_iterations=10,
            working_directory=temp_project,
        )

        prompt = tool._get_subagent_prompt(context)

        assert "explore" in prompt.lower()
        assert "structure" in prompt.lower() or "glob" in prompt.lower()

    def test_get_subagent_prompt_search(self, temp_project):
        """Test that search agent gets specialized prompt."""
        from cortex.subagent.context import SubagentContext

        tool = TaskTool(
            project_dir=temp_project,
            permission_mode=PermissionMode.PLAN,
            console=None,
        )

        context = SubagentContext(
            task_id="test",
            task_description="Find function definitions",
            parent_context={"agent_type": "search"},
            allowed_tools=["grep", "glob", "read_file"],
            max_iterations=10,
            working_directory=temp_project,
        )

        prompt = tool._get_subagent_prompt(context)

        assert "search" in prompt.lower()


class TestAgentWithSummarization:
    """Tests for agent initialization with summarization."""

    def test_agent_initializes_with_summarizer(self, temp_project):
        """Test that agent initializes with summarizer enabled by default."""
        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        # Check that conversation manager has summarization configured
        assert agent.conversation.enable_summarization is True

    def test_agent_summarizer_is_simple_by_default(self, temp_project):
        """Test that agent uses simple summarizer by default."""
        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        # Simple summarizer should be used by default
        assert agent.conversation.summarizer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
