"""Clear command - clears conversation history"""

from typing import Optional
from .base import Command, CommandContext
from ...ui.console import console


class ClearCommand(Command):
    """Clear conversation history"""

    @property
    def name(self) -> str:
        return "clear"

    @property
    def description(self) -> str:
        return "Clear conversation history"

    @property
    def aliases(self) -> list:
        return []

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the clear command"""
        ctx.agent.clear_conversation()
        console.print("[green]✓[/green] Conversation cleared")


class ResetContextCommand(Command):
    """Clear conversation but preserve memory bank"""

    @property
    def name(self) -> str:
        return "reset-context"

    @property
    def description(self) -> str:
        return "Clear conversation but preserve memory"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the reset-context command"""
        # Clear conversation but preserve memory bank
        if hasattr(ctx.agent, "memory_bank") and ctx.agent.memory_bank:
            memory_class = type(ctx.agent.memory_bank)
            memory_backup = ctx.agent.memory_bank.to_dict()
            ctx.agent.clear_conversation()
            ctx.agent.memory_bank = memory_class.from_dict(memory_backup)
            # Re-inject memory into system prompt
            ctx.agent.conversation.history[0]["content"] = ctx.agent._get_system_prompt()
        else:
            ctx.agent.clear_conversation()

        console.print("[green]✓[/green] Context cleared. Memory preserved.")
        console.print(
            f"[dim]Memory items: {len(ctx.agent.memory_bank.items) if ctx.agent.memory_bank else 0}[/dim]"  # noqa: E501
        )
