"""Tests for the interactive help system."""

import pytest
import tempfile
from pathlib import Path
from io import StringIO
from rich.console import Console

from cortex.help import (
    HelpEntry,
    HelpCategory,
    HELP_ENTRIES,
    get_help_entries_by_category,
    get_beginner_entries,
    get_entry_by_command,
    search_entries,
    search_by_keyword,
    suggest_commands,
    get_related_entries,
    HelpSystem,
)


class TestHelpContent:
    """Tests for help content module."""

    def test_help_entries_exist(self):
        """Test that help entries are defined."""
        assert len(HELP_ENTRIES) > 0

    def test_all_entries_have_required_fields(self):
        """Test that all entries have required fields."""
        for entry in HELP_ENTRIES:
            assert entry.command, f"Entry missing command"
            assert entry.short_desc, f"Entry {entry.command} missing short_desc"
            assert entry.long_desc, f"Entry {entry.command} missing long_desc"
            assert entry.category is not None, f"Entry {entry.command} missing category"

    def test_get_entries_by_category(self):
        """Test filtering entries by category."""
        session_entries = get_help_entries_by_category(HelpCategory.SESSION)
        assert len(session_entries) > 0
        for entry in session_entries:
            assert entry.category == HelpCategory.SESSION

    def test_get_beginner_entries(self):
        """Test getting beginner-friendly entries."""
        beginner = get_beginner_entries()
        assert len(beginner) > 0
        for entry in beginner:
            assert entry.beginner_friendly is True

    def test_get_entry_by_command_with_slash(self):
        """Test getting entry by command with leading slash."""
        entry = get_entry_by_command("/help")
        assert entry is not None
        assert entry.command == "/help"

    def test_get_entry_by_command_without_slash(self):
        """Test getting entry by command without leading slash."""
        entry = get_entry_by_command("help")
        assert entry is not None
        assert entry.command == "/help"

    def test_get_entry_by_command_not_found(self):
        """Test getting entry by unknown command."""
        entry = get_entry_by_command("nonexistent")
        assert entry is None


class TestHelpSearch:
    """Tests for help search module."""

    def test_search_exact_match(self):
        """Test searching with exact match."""
        results = search_entries("help")
        assert len(results) > 0
        # First result should be the /help command
        assert results[0].entry.command == "/help"

    def test_search_partial_match(self):
        """Test searching with partial match."""
        results = search_entries("git")
        assert len(results) > 0
        # Should find git-related commands
        git_commands = [r.entry.command for r in results]
        assert any("git" in cmd.lower() for cmd in git_commands)

    def test_search_by_keyword(self):
        """Test searching by keyword."""
        results = search_entries("commit")
        assert len(results) > 0

    def test_search_with_category_filter(self):
        """Test searching with category filter."""
        results = search_entries("", category=HelpCategory.GIT)
        assert len(results) > 0
        for result in results:
            assert result.entry.category == HelpCategory.GIT

    def test_search_min_score(self):
        """Test that results respect min_score."""
        # Search for something that might have low matches
        results = search_entries("xyz123", min_score=0.5)
        for result in results:
            assert result.score >= 0.5

    def test_search_max_results(self):
        """Test that results respect max_results."""
        results = search_entries("command", max_results=3)
        assert len(results) <= 3

    def test_search_by_keyword_function(self):
        """Test search_by_keyword function."""
        entries = search_by_keyword("git")
        assert len(entries) > 0
        for entry in entries:
            assert "git" in [k.lower() for k in entry.keywords]

    def test_suggest_commands(self):
        """Test command suggestions."""
        suggestions = suggest_commands("hel")
        assert "/help" in suggestions

    def test_suggest_commands_with_slash(self):
        """Test command suggestions with leading slash."""
        suggestions = suggest_commands("/clea")
        assert "/clear" in suggestions

    def test_get_related_entries(self):
        """Test getting related entries."""
        save_entry = get_entry_by_command("/save")
        assert save_entry is not None

        related = get_related_entries(save_entry)
        # /save should be related to /load and /sessions
        related_commands = [r.command for r in related]
        assert "/load" in related_commands or "load" in [r.command.lstrip("/") for r in related]


class TestHelpSystem:
    """Tests for HelpSystem class."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def help_system(self, temp_project_dir):
        """Create a HelpSystem instance."""
        console = Console(file=StringIO(), force_terminal=True)
        return HelpSystem(project_dir=temp_project_dir, console=console)

    def test_detect_python_project(self, temp_project_dir):
        """Test detecting Python project."""
        (temp_project_dir / "pyproject.toml").write_text("[project]")
        console = Console(file=StringIO())
        hs = HelpSystem(project_dir=temp_project_dir, console=console)
        assert hs.project_type == "python"

    def test_detect_node_project(self, temp_project_dir):
        """Test detecting Node project."""
        (temp_project_dir / "package.json").write_text("{}")
        console = Console(file=StringIO())
        hs = HelpSystem(project_dir=temp_project_dir, console=console)
        assert hs.project_type == "node"

    def test_detect_rust_project(self, temp_project_dir):
        """Test detecting Rust project."""
        (temp_project_dir / "Cargo.toml").write_text("[package]")
        console = Console(file=StringIO())
        hs = HelpSystem(project_dir=temp_project_dir, console=console)
        assert hs.project_type == "rust"

    def test_detect_generic_project(self, temp_project_dir):
        """Test detecting generic project (no indicators)."""
        console = Console(file=StringIO())
        hs = HelpSystem(project_dir=temp_project_dir, console=console)
        assert hs.project_type == "generic"

    def test_show_quick_help(self, help_system):
        """Test show_quick_help doesn't raise."""
        # Just ensure it doesn't raise
        help_system.show_quick_help()

    def test_show_topic_help_category(self, help_system):
        """Test show_topic_help with category."""
        help_system.show_topic_help("session")

    def test_show_topic_help_command(self, help_system):
        """Test show_topic_help with command."""
        help_system.show_topic_help("help")

    def test_show_topic_help_unknown(self, help_system):
        """Test show_topic_help with unknown topic."""
        help_system.show_topic_help("nonexistent_command")

    def test_show_search_results(self, help_system):
        """Test show_search_results."""
        help_system.show_search_results("git commit")

    def test_show_search_no_results(self, help_system):
        """Test show_search_results with no matches."""
        help_system.show_search_results("xyz123nonexistent")

    def test_show_categories(self, help_system):
        """Test show_categories."""
        help_system.show_categories()

    def test_handle_help_command_no_args(self, help_system):
        """Test handle_help_command with no arguments."""
        help_system.handle_help_command("")

    def test_handle_help_command_search(self, help_system):
        """Test handle_help_command with search subcommand."""
        help_system.handle_help_command("search git")

    def test_handle_help_command_categories(self, help_system):
        """Test handle_help_command with categories subcommand."""
        help_system.handle_help_command("categories")

    def test_handle_help_command_topic(self, help_system):
        """Test handle_help_command with topic."""
        help_system.handle_help_command("git")


class TestHelpEntry:
    """Tests for HelpEntry dataclass."""

    def test_help_entry_creation(self):
        """Test creating a HelpEntry."""
        entry = HelpEntry(
            command="/test",
            short_desc="Test command",
            long_desc="A test command for testing",
            category=HelpCategory.SESSION,
            examples=["/test arg"],
            keywords=["test", "testing"],
        )
        assert entry.command == "/test"
        assert entry.short_desc == "Test command"
        assert entry.category == HelpCategory.SESSION
        assert len(entry.examples) == 1
        assert entry.beginner_friendly is True  # Default

    def test_help_entry_project_types(self):
        """Test HelpEntry with project types."""
        entry = HelpEntry(
            command="/pytest",
            short_desc="Run pytest",
            long_desc="Run pytest tests",
            category=HelpCategory.TEST,
            project_types=["python"],
        )
        assert "python" in entry.project_types
