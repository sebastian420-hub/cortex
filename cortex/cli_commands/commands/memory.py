"""Memory and context commands"""

from typing import Optional
from pathlib import Path
from rich.panel import Panel

from .base import Command, CommandContext
from ...ui.console import console
from ...core.memory import MemorySource


class MemoryCommand(Command):
    """Show memory bank contents and search semantic memory"""

    @property
    def name(self) -> str:
        return "memory"

    @property
    def description(self) -> str:
        return "Show memory contents or search semantic memory (/memory search <query>)"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the memory command"""
        if args and args.strip().startswith("search "):
            query = args.strip()[7:].strip()
            self._handle_search(ctx, query)
            return

        # Default display
        if ctx.agent.memory_bank and ctx.agent.memory_bank.items:
            console.print(
                Panel(
                    ctx.agent.memory_bank.get_full_display(),
                    title="[bold]Memory Bank[/bold]",
                    border_style="yellow",
                )
            )
        else:
            console.print("[dim]Memory bank is empty.[/dim]")
        
        # Show semantic memory status if available
        if hasattr(ctx.agent.memory_bank, "semantic_manager") and ctx.agent.memory_bank.semantic_manager:
            sm = ctx.agent.memory_bank.semantic_manager
            count = sm.count()
            console.print(f"[dim]Semantic Memory (Vector DB): {count} documents indexed[/dim]")

    def _handle_search(self, ctx: CommandContext, query: str) -> None:
        """Handle semantic search subcommand"""
        if not hasattr(ctx.agent.memory_bank, "retrieve_semantic_context"):
            console.print("[red]Semantic memory is not enabled.[/red]")
            return

        if not query:
            console.print("[red]Usage: /memory search <query>[/red]")
            return

        console.print(f"[cyan]Searching semantic memory for:[/cyan] '{query}'...")
        results = ctx.agent.memory_bank.retrieve_semantic_context(query, top_k=5)

        if not results:
            console.print("[yellow]No semantically similar memories found.[/yellow]")
            return

        from rich.table import Table
        table = Table(title=f"🔍 Semantic Search Results for '{query}'")
        table.add_column("Similarity", justify="right", style="dim")
        table.add_column("Content", style="white")
        table.add_column("Type", style="cyan")

        for res in results:
            # Distance: lower is better in Chroma
            score = f"{1.0 - res.get('distance', 0):.2f}"
            content = res.get("document", "")
            if len(content) > 150:
                content = content[:147] + "..."
            
            metadata = res.get("metadata", {})
            m_type = metadata.get("type", "unknown")
            
            table.add_row(score, content, m_type)

        console.print(table)


class FocusCommand(Command):
    """Focus on a specific directory"""

    @property
    def name(self) -> str:
        return "focus"

    @property
    def description(self) -> str:
        return "Focus on a specific directory"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the focus command"""
        if args:
            focus_path = Path(args.strip()).resolve()
            if focus_path.exists() and focus_path.is_dir():
                # Add to memory as a fact
                ctx.agent.memory_bank.add_fact(
                    f"User focused on directory: {focus_path}", source=MemorySource.USER
                )
                console.print(f"[green]✓[/green] Focus set to: {focus_path}")
                console.print("[dim]Future searches will prioritize this directory[/dim]")
            else:
                console.print(f"[red]Directory not found: {args.strip()}[/red]")
        else:
            console.print("[dim]Usage: /focus <directory_path>[/dim]")


class ThinkingCommand(Command):
    """Toggle thinking display"""

    @property
    def name(self) -> str:
        return "thinking"

    @property
    def description(self) -> str:
        return "Toggle thinking display on/off"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the thinking command"""
        if args:
            toggle = args.strip().lower()
            if toggle == "on":
                ctx.agent.show_thinking = True
                console.print("[green]✓[/green] Thinking display enabled")
            elif toggle == "off":
                ctx.agent.show_thinking = False
                console.print("[green]✓[/green] Thinking display disabled")
            else:
                console.print("[red]Usage: /thinking [on|off][/red]")
        else:
            ctx.agent.show_thinking = not ctx.agent.show_thinking
            status = "enabled" if ctx.agent.show_thinking else "disabled"
            console.print(f"[green]✓[/green] Thinking display {status}")


class SummaryCommand(Command):
    """Show conversation summary"""

    @property
    def name(self) -> str:
        return "summary"

    @property
    def description(self) -> str:
        return "Show conversation summary"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the summary command"""
        from ...core.summarization import SimpleSummarizer

        summarizer = SimpleSummarizer()
        history = ctx.agent.get_conversation_history()
        if len(history) > 1:  # More than just system prompt
            summary = summarizer.summarize(history[1:])  # Skip system prompt
            summary_msg = summary.to_message()
            console.print(
                Panel(
                    summary_msg.get("content", "No summary available"),
                    title="[bold]Conversation Summary[/bold]",
                    border_style="cyan",
                )
            )
        else:
            console.print("[dim]No conversation to summarize yet.[/dim]")
