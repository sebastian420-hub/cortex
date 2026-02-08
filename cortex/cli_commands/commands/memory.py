"""Memory and context commands"""

from typing import Optional
from pathlib import Path
from rich.panel import Panel

from .base import Command, CommandContext
from ...ui.console import console
from ...core.memory import MemorySource


class MemoryCommand(Command):
    """Show memory bank contents"""

    @property
    def name(self) -> str:
        return "memory"

    @property
    def description(self) -> str:
        return "Show memory bank contents"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the memory command"""
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
