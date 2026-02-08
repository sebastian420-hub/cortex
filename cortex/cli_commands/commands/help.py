"""Help command"""

from typing import Optional

from .base import Command, CommandContext
from ...ui.console import console


class HelpCommand(Command):
    """Show help information"""

    @property
    def name(self) -> str:
        return "help"

    @property
    def description(self) -> str:
        return "Show help information"

    @property
    def requires_agent(self) -> bool:
        """Help doesn't require an initialized agent"""
        return False

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the help command"""
        from ...help import HelpSystem

        help_system = HelpSystem(project_dir=ctx.agent.project_dir, console=console)
        help_system.handle_help_command(args or "")


class ExitCommand(Command):
    """Exit the REPL"""

    @property
    def name(self) -> str:
        return "exit"

    @property
    def description(self) -> str:
        return "Exit the REPL"

    @property
    def aliases(self) -> list:
        return ["quit", "q"]

    @property
    def requires_agent(self) -> bool:
        """Exit doesn't require an initialized agent"""
        return False

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the exit command"""
        raise KeyboardInterrupt
