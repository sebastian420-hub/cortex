"""Mode commands - permission and UI mode management"""

from typing import Optional
from .base import Command, CommandContext
from ...models import PermissionMode
from ...ui.console import console
from ...ui.modes import UIMode, set_ui_mode, get_ui_mode


class PermissionModeCommand(Command):
    """Change permission mode (normal/auto/plan)"""

    @property
    def name(self) -> str:
        return "mode"

    @property
    def description(self) -> str:
        return "Change permission mode (normal/auto/plan)"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the mode command"""
        if args:
            mode = args.strip()
            if mode in [PermissionMode.NORMAL, PermissionMode.AUTO_APPROVE, PermissionMode.PLAN]:
                ctx.agent.permission_mode = mode
                # Update system prompt
                ctx.agent.conversation.history[0]["content"] = ctx.agent._get_system_prompt()
                console.print(f"[green]✓[/green] Mode changed to: {mode}")
            else:
                console.print("[red]Invalid mode. Use: normal, auto, or plan[/red]")
        else:
            console.print(f"Current mode: {ctx.agent.permission_mode}")


class UIModeCommand(Command):
    """Change UI mode (minimal/normal/debug)"""

    @property
    def name(self) -> str:
        return "ui"

    @property
    def description(self) -> str:
        return "Change UI mode (minimal/normal/debug)"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the ui command"""
        if args:
            mode_str = args.strip()
            try:
                mode = UIMode(mode_str)
                set_ui_mode(mode)
                console.print(f"[green]✓[/green] UI mode changed to: {mode.value}")
            except ValueError:
                console.print("[red]Invalid UI mode. Use: minimal, normal, or debug[/red]")
        else:
            current_mode = get_ui_mode()
            console.print(f"Current UI mode: {current_mode.value}")
            console.print("[dim]Usage: /ui <minimal|normal|debug>[/dim]")
            console.print("[dim]  minimal: Claude Code style (clean, no panels)[/dim]")
            console.print("[dim]  normal: Rich panels and detailed displays[/dim]")
            console.print("[dim]  debug: Development details and timing[/dim]")


class PlanCommand(Command):
    """Enter planning mode (read-only)"""

    @property
    def name(self) -> str:
        return "plan"

    @property
    def description(self) -> str:
        return "Enter planning mode (read-only)"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the plan command"""
        ctx.agent.permission_mode = PermissionMode.PLAN
        ctx.agent.conversation.history[0]["content"] = ctx.agent._get_system_prompt()
        console.print("[cyan]📋 Entered PLAN mode (read-only)[/cyan]")
        console.print("[dim]Use /mode normal to return to normal mode[/dim]")
