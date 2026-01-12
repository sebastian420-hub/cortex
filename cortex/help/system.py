"""Interactive help system for Cortex."""

from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown

from .content import (
    HelpEntry,
    HelpCategory,
    HELP_ENTRIES,
    get_help_entries_by_category,
    get_beginner_entries,
    get_entry_by_command,
)
from .search import search_entries, suggest_commands, get_related_entries, SearchResult


class HelpSystem:
    """
    Interactive, context-aware help system.

    Features:
    - Project type detection for relevant help
    - Fuzzy search across all help content
    - Category-based help browsing
    - Related command suggestions
    """

    def __init__(self, project_dir: Optional[Path] = None, console: Optional[Console] = None):
        """
        Initialize HelpSystem.

        Args:
            project_dir: Project directory for type detection
            console: Rich console for output
        """
        self.project_dir = project_dir or Path.cwd()
        self.console = console or Console()
        self.project_type = self._detect_project_type()

    def _detect_project_type(self) -> str:
        """
        Detect the project type from files.

        Returns:
            Project type string (python, node, rust, go, java, generic)
        """
        indicators = {
            "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
            "node": ["package.json", "yarn.lock", "package-lock.json"],
            "rust": ["Cargo.toml"],
            "go": ["go.mod", "go.sum"],
            "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
        }

        for project_type, files in indicators.items():
            for f in files:
                if (self.project_dir / f).exists():
                    return project_type

        return "generic"

    def show_quick_help(self) -> None:
        """Show a quick reference table of commands."""
        table = Table(title="Cortex Commands", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("Category", style="dim")

        # Show beginner-friendly commands first
        entries = get_beginner_entries()

        for entry in entries:
            if entry.command.startswith("/"):
                table.add_row(entry.command, entry.short_desc, entry.category.value)

        self.console.print(table)
        self.console.print()
        self.console.print(
            "[dim]Use /help <topic> for more info, or /help search <query> to search[/dim]"
        )

    def show_topic_help(self, topic: str) -> None:
        """
        Show detailed help for a topic.

        Args:
            topic: Topic to show help for (category or command)
        """
        topic = topic.lower().strip()

        # Check if it's a category
        for cat in HelpCategory:
            if cat.value == topic or cat.name.lower() == topic:
                self._show_category_help(cat)
                return

        # Check if it's a command
        entry = get_entry_by_command(topic)
        if entry:
            self._show_command_help(entry)
            return

        # Try fuzzy search
        results = search_entries(topic, max_results=5)
        if results:
            self.console.print(f"[yellow]No exact match for '{topic}'. Did you mean:[/yellow]")
            for result in results:
                self.console.print(
                    f"  - [cyan]{result.entry.command}[/cyan]: {result.entry.short_desc}"
                )
        else:
            self.console.print(f"[red]No help found for '{topic}'[/red]")
            self.console.print("[dim]Try /help search <query> to search all help content[/dim]")

    def show_search_results(self, query: str) -> None:
        """
        Search help content and show results.

        Args:
            query: Search query
        """
        results = search_entries(query, max_results=10)

        if not results:
            self.console.print(f"[yellow]No results found for '{query}'[/yellow]")
            suggestions = suggest_commands(query)
            if suggestions:
                self.console.print("[dim]Try one of these commands:[/dim]")
                for s in suggestions:
                    self.console.print(f"  - [cyan]{s}[/cyan]")
            return

        table = Table(title=f"Search Results for '{query}'", show_header=True)
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("Relevance", style="green")

        for result in results:
            relevance = f"{result.score:.0%}"
            table.add_row(result.entry.command, result.entry.short_desc, relevance)

        self.console.print(table)
        self.console.print()
        self.console.print("[dim]Use /help <command> for detailed help on a specific command[/dim]")

    def _show_category_help(self, category: HelpCategory) -> None:
        """Show help for a category."""
        entries = get_help_entries_by_category(category)

        category_titles = {
            HelpCategory.SESSION: "Session Management",
            HelpCategory.FILE: "File Operations",
            HelpCategory.SEARCH: "Search & Navigation",
            HelpCategory.GIT: "Git Operations",
            HelpCategory.TEST: "Testing",
            HelpCategory.WEB: "Web & Documentation",
            HelpCategory.CONTEXT: "Context & Memory",
            HelpCategory.ADVANCED: "Advanced Features",
        }

        title = category_titles.get(category, category.value.title())

        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")

        for entry in entries:
            table.add_row(entry.command, entry.short_desc)

        self.console.print(table)
        self.console.print()
        self.console.print("[dim]Use /help <command> for detailed help on a specific command[/dim]")

    def _show_command_help(self, entry: HelpEntry) -> None:
        """Show detailed help for a command."""
        content = []

        # Command name
        content.append(f"[bold cyan]{entry.command}[/bold cyan]")
        content.append("")

        # Description
        content.append(f"[bold]Description:[/bold]")
        content.append(entry.long_desc)
        content.append("")

        # Examples
        if entry.examples:
            content.append("[bold]Examples:[/bold]")
            for example in entry.examples:
                content.append(f"  [green]{example}[/green]")
            content.append("")

        # Related commands
        if entry.related:
            related_entries = get_related_entries(entry)
            if related_entries:
                content.append("[bold]Related Commands:[/bold]")
                for r in related_entries:
                    content.append(f"  [cyan]{r.command}[/cyan] - {r.short_desc}")
                content.append("")

        # Keywords
        if entry.keywords:
            content.append(f"[dim]Keywords: {', '.join(entry.keywords)}[/dim]")

        self.console.print(
            Panel("\n".join(content), title=f"Help: {entry.command}", border_style="cyan")
        )

    def show_categories(self) -> None:
        """Show all help categories."""
        table = Table(title="Help Categories", show_header=True, header_style="bold cyan")
        table.add_column("Category", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Commands", style="dim")

        category_descriptions = {
            HelpCategory.SESSION: "Manage sessions, save/load, exit",
            HelpCategory.FILE: "Read, write, and edit files",
            HelpCategory.SEARCH: "Find files and search code",
            HelpCategory.GIT: "Git operations and version control",
            HelpCategory.TEST: "Run tests and check code",
            HelpCategory.WEB: "Fetch web content and search online",
            HelpCategory.CONTEXT: "Manage context, memory, summaries",
            HelpCategory.ADVANCED: "Advanced features and settings",
        }

        for cat in HelpCategory:
            count = len(get_help_entries_by_category(cat))
            table.add_row(cat.value, category_descriptions.get(cat, ""), str(count))

        self.console.print(table)
        self.console.print()
        self.console.print("[dim]Use /help <category> to see commands in a category[/dim]")

    def handle_help_command(self, args: str = "") -> None:
        """
        Handle /help command with arguments.

        Args:
            args: Arguments after /help (e.g., "git", "search commit")
        """
        args = args.strip()

        if not args:
            self.show_quick_help()
            return

        parts = args.split(maxsplit=1)
        first = parts[0].lower()

        # Check for search subcommand
        if first == "search" and len(parts) > 1:
            self.show_search_results(parts[1])
            return

        # Check for categories subcommand
        if first == "categories":
            self.show_categories()
            return

        # Otherwise, show topic help
        self.show_topic_help(args)
