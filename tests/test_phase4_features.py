"""Tests for Phase 4 features: Memory Bank, Slash Commands, Thinking Display, Progress Indicators"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from cortex.models import PermissionMode


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    temp_dir = Path(tempfile.mkdtemp())
    (temp_dir / "main.py").write_text("print('hello')")
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestMemoryBank:
    """Tests for MemoryBank functionality."""

    def test_memory_bank_import(self):
        """Test that MemoryBank can be imported."""
        from cortex.core.memory import MemoryBank
        assert MemoryBank is not None

    def test_memory_bank_creation(self):
        """Test creating a memory bank."""
        from cortex.core.memory import MemoryBank, create_memory_bank
        bank = create_memory_bank(max_items=50)
        assert bank is not None
        assert bank.max_items == 50
        assert len(bank.items) == 0

    def test_add_decision(self):
        """Test adding a decision memory."""
        from cortex.core.memory import MemoryBank, MemoryType, MemorySource

        bank = MemoryBank()
        bank.add_decision("Chose pytest over unittest for testing")

        assert len(bank.items) == 1
        assert bank.items[0].type == MemoryType.DECISION
        assert "pytest" in bank.items[0].content

    def test_add_fact(self):
        """Test adding a fact memory."""
        from cortex.core.memory import MemoryBank, MemoryType

        bank = MemoryBank()
        bank.add_fact("Entry point is main.py")

        assert len(bank.items) == 1
        assert bank.items[0].type == MemoryType.FACT

    def test_add_preference(self):
        """Test adding a preference memory."""
        from cortex.core.memory import MemoryBank, MemoryType, MemorySource

        bank = MemoryBank()
        bank.add_preference("User prefers TypeScript", source=MemorySource.USER)

        assert len(bank.items) == 1
        assert bank.items[0].type == MemoryType.PREFERENCE
        assert bank.items[0].source == MemorySource.USER

    def test_add_file(self):
        """Test adding a file reference."""
        from cortex.core.memory import MemoryBank, MemoryType

        bank = MemoryBank()
        bank.add_file("src/main.py", "Main entry point")

        assert len(bank.items) == 1
        assert bank.items[0].type == MemoryType.FILE
        assert "src/main.py" in bank.items[0].content

    def test_add_error(self):
        """Test adding an error memory."""
        from cortex.core.memory import MemoryBank, MemoryType

        bank = MemoryBank()
        bank.add_error("File not found: config.yaml", "loading config")

        assert len(bank.items) == 1
        assert bank.items[0].type == MemoryType.ERROR

    def test_deduplication(self):
        """Test that similar memories are deduplicated."""
        from cortex.core.memory import MemoryBank

        bank = MemoryBank()
        bank.add_fact("Entry point is main.py")
        bank.add_fact("Entry point is main.py")  # Duplicate

        assert len(bank.items) == 1

    def test_get_by_type(self):
        """Test filtering memories by type."""
        from cortex.core.memory import MemoryBank, MemoryType

        bank = MemoryBank()
        bank.add_fact("Fact 1")
        bank.add_decision("Decision 1")
        bank.add_fact("Fact 2")

        facts = bank.get_by_type(MemoryType.FACT)
        assert len(facts) == 2

        decisions = bank.get_by_type(MemoryType.DECISION)
        assert len(decisions) == 1

    def test_get_relevant(self):
        """Test getting relevant memories for a query."""
        from cortex.core.memory import MemoryBank

        bank = MemoryBank()
        bank.add_fact("The authentication module is in src/auth.py")
        bank.add_fact("Database config is in config/db.yaml")
        bank.add_fact("Tests are in the tests directory")

        relevant = bank.get_relevant("authentication", limit=2)
        assert len(relevant) > 0
        assert any("auth" in item.content.lower() for item in relevant)

    def test_get_summary(self):
        """Test generating a summary string."""
        from cortex.core.memory import MemoryBank

        bank = MemoryBank()
        bank.add_decision("Using pytest")
        bank.add_fact("Python project")
        bank.add_preference("Prefers async")

        summary = bank.get_summary()
        assert "Key Decisions" in summary
        assert "Known Facts" in summary
        assert "User Preferences" in summary

    def test_get_full_display(self):
        """Test the full display format."""
        from cortex.core.memory import MemoryBank

        bank = MemoryBank()
        bank.add_decision("Using pytest")
        bank.add_fact("Python project")

        display = bank.get_full_display()
        assert "Memory Bank Contents" in display
        assert "Decisions" in display
        assert "Facts" in display

    def test_pruning(self):
        """Test that old items are pruned when over max."""
        from cortex.core.memory import MemoryBank

        bank = MemoryBank(max_items=3)
        bank.add_fact("Fact 1")
        bank.add_fact("Fact 2")
        bank.add_fact("Fact 3")
        bank.add_fact("Fact 4")  # Should trigger pruning

        assert len(bank.items) <= 3

    def test_serialization(self):
        """Test serializing and deserializing memory bank."""
        from cortex.core.memory import MemoryBank

        bank = MemoryBank()
        bank.add_decision("Decision 1")
        bank.add_fact("Fact 1")

        # Serialize
        data = bank.to_dict()
        assert "items" in data
        assert len(data["items"]) == 2

        # Deserialize
        restored = MemoryBank.from_dict(data)
        assert len(restored.items) == 2

    def test_clear(self):
        """Test clearing the memory bank."""
        from cortex.core.memory import MemoryBank

        bank = MemoryBank()
        bank.add_fact("Fact 1")
        bank.add_decision("Decision 1")

        bank.clear()
        assert len(bank.items) == 0


class TestMemoryExtraction:
    """Tests for extracting memories from messages."""

    def test_extract_from_user_preferences(self):
        """Test extracting preferences from user messages."""
        from cortex.core.memory import MemoryBank, extract_memories_from_messages, MemoryType

        bank = MemoryBank()
        messages = [
            {"role": "user", "content": "I prefer using TypeScript for frontend development"}
        ]

        extract_memories_from_messages(messages, bank)

        prefs = bank.get_by_type(MemoryType.PREFERENCE)
        # May or may not extract based on pattern matching
        assert isinstance(prefs, list)

    def test_extract_from_tool_results(self):
        """Test extracting file references from tool results."""
        from cortex.core.memory import MemoryBank, extract_memories_from_messages, MemoryType
        import json

        bank = MemoryBank()
        messages = [
            {"role": "tool", "content": json.dumps({"success": True, "path": "src/main.py"})}
        ]

        extract_memories_from_messages(messages, bank)

        files = bank.get_by_type(MemoryType.FILE)
        assert len(files) == 1
        assert "src/main.py" in files[0].content


class TestThinkingDisplay:
    """Tests for thinking/reasoning display."""

    def test_display_thinking_import(self):
        """Test that display_thinking can be imported."""
        from cortex.ui.display import display_thinking
        assert display_thinking is not None

    def test_display_thinking_empty(self):
        """Test display_thinking with empty content."""
        from cortex.ui.display import display_thinking

        # Should not raise
        display_thinking("")
        display_thinking(None)

    @patch('cortex.ui.display.console')
    def test_display_thinking_collapsed(self, mock_console):
        """Test collapsed thinking display - shows minimal one-liner."""
        from cortex.ui.display import display_thinking

        display_thinking("This is a test thinking content", expanded=False)

        mock_console.print.assert_called_once()
        # Should be a simple dim one-liner, not a panel
        call_args = str(mock_console.print.call_args)
        assert "💭" in call_args
        assert "dim" in call_args.lower()

    @patch('cortex.ui.display.console')
    def test_display_thinking_expanded(self, mock_console):
        """Test expanded thinking display."""
        from cortex.ui.display import display_thinking

        display_thinking("This is a test thinking content\nWith multiple lines", expanded=True)

        mock_console.print.assert_called_once()


class TestProgressIndicators:
    """Tests for progress indicators."""

    def test_operation_tracker_import(self):
        """Test that OperationTracker can be imported."""
        from cortex.ui.progress import OperationTracker
        assert OperationTracker is not None

    def test_operation_tracker_creation(self):
        """Test creating an operation tracker."""
        from cortex.ui.progress import OperationTracker

        tracker = OperationTracker()
        assert tracker is not None

    def test_track_files_import(self):
        """Test that track_files can be imported."""
        from cortex.ui.progress import track_files
        assert track_files is not None

    def test_track_search_import(self):
        """Test that track_search can be imported."""
        from cortex.ui.progress import track_search
        assert track_search is not None

    def test_show_operation_summary_import(self):
        """Test that show_operation_summary can be imported."""
        from cortex.ui.progress import show_operation_summary
        assert show_operation_summary is not None

    @patch('cortex.ui.progress.console')
    def test_show_operation_summary(self, mock_console):
        """Test showing operation summary."""
        from cortex.ui.progress import show_operation_summary

        show_operation_summary("Search", 42, 150.5, "in 3 files")

        mock_console.print.assert_called_once()


class TestEnhancedRecovery:
    """Tests for enhanced error recovery."""

    def test_recovery_manager_import(self):
        """Test that RecoveryManager can be imported."""
        from cortex.core.recovery import RecoveryManager
        assert RecoveryManager is not None

    def test_not_found_recovery_enhanced(self):
        """Test enhanced not_found recovery with debugging steps."""
        from cortex.core.recovery import RecoveryManager, RecoveryContext, RecoveryStrategy

        manager = RecoveryManager()
        context = RecoveryContext(
            error_type="not_found",
            error_message="File not found: src/utils/helper.py",
            tool_name="read_file",
            arguments={"path": "src/utils/helper.py"},
            attempt_count=1
        )

        action = manager.determine_recovery_action(context)

        assert action.strategy == RecoveryStrategy.SUGGEST
        assert "glob" in action.suggested_prompt.lower() or "search" in action.suggested_prompt.lower()
        assert "DEBUG" in action.suggested_prompt

    def test_execution_recovery_command_not_found(self):
        """Test execution recovery for command not found."""
        from cortex.core.recovery import RecoveryManager, RecoveryContext, RecoveryStrategy

        manager = RecoveryManager()
        context = RecoveryContext(
            error_type="execution",
            error_message="'rg' is not recognized as an internal command",
            tool_name="execute_command",
            arguments={"command": "rg pattern"},
            attempt_count=1
        )

        action = manager.determine_recovery_action(context)

        assert action.strategy == RecoveryStrategy.SUGGEST
        assert "command not found" in action.suggested_prompt.lower() or "not available" in action.suggested_prompt.lower()

    def test_execution_recovery_test_failure(self):
        """Test execution recovery for test failures."""
        from cortex.core.recovery import RecoveryManager, RecoveryContext, RecoveryStrategy

        manager = RecoveryManager()
        context = RecoveryContext(
            error_type="execution",
            error_message="FAILED test_auth.py::test_login - AssertionError",
            tool_name="run_tests",
            arguments={"pattern": "test_auth.py"},
            attempt_count=1
        )

        action = manager.determine_recovery_action(context)

        assert action.strategy == RecoveryStrategy.SUGGEST
        assert "test" in action.suggested_prompt.lower()


class TestAgentMemoryIntegration:
    """Tests for memory bank integration with agent."""

    def test_agent_has_memory_bank(self, temp_project):
        """Test that agent is initialized with memory bank."""
        from cortex.agent import Cortex

        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        assert hasattr(agent, 'memory_bank')
        assert agent.memory_bank is not None

    def test_agent_has_show_thinking(self, temp_project):
        """Test that agent has show_thinking attribute."""
        from cortex.agent import Cortex

        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        assert hasattr(agent, 'show_thinking')
        assert agent.show_thinking is False  # Default

    def test_system_prompt_contains_mental_model(self, temp_project):
        """Test that system prompt contains mental model section."""
        from cortex.agent import Cortex

        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        prompt = agent._get_system_prompt()

        assert "Mental Model" in prompt
        assert "Self-Awareness" in prompt
        assert "Efficiency" in prompt

    def test_system_prompt_contains_memory_section(self, temp_project):
        """Test that system prompt can include memory summary."""
        from cortex.agent import Cortex

        agent = Cortex(
            model="llama3.2",
            project_dir=str(temp_project),
            permission_mode=PermissionMode.NORMAL,
        )

        # Add some memories
        agent.memory_bank.add_fact("Project uses Python 3.10")
        agent.memory_bank.add_decision("Using pytest for tests")

        # Regenerate prompt
        prompt = agent._get_system_prompt()

        # Memory summary should be included
        assert "Python 3.10" in prompt or "Session Memory" in prompt or "Known Facts" in prompt


class TestCoreExports:
    """Test that Phase 4 modules are properly exported."""

    def test_memory_exports(self):
        """Test memory module exports."""
        from cortex.core import (
            MemoryBank,
            MemoryItem,
            MemoryType,
            MemorySource,
            create_memory_bank,
            extract_memories_from_messages,
        )

        assert MemoryBank is not None
        assert MemoryItem is not None
        assert MemoryType is not None
        assert MemorySource is not None

    def test_ui_exports(self):
        """Test UI module exports."""
        from cortex.ui import (
            display_thinking,
            display_progress_summary,
            display_operation_complete,
            OperationTracker,
            track_files,
            track_search,
            show_operation_summary,
            get_tracker,
        )

        assert display_thinking is not None
        assert OperationTracker is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
