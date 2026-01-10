"""REPL interface for Cortex"""

from typing import Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from ..models import PermissionMode

console = Console()


class REPL:
    """Interactive REPL for Cortex"""
    
    def __init__(self, history_file: str):
        self.history_file = history_file
        self.session = PromptSession(history=FileHistory(history_file))
        self._setup_key_bindings()
    
    def _setup_key_bindings(self):
        """Set up keyboard shortcuts"""
        bindings = KeyBindings()
        
        @bindings.add(Keys.ControlD)
        def exit_handler(event):
            """Ctrl+D to exit"""
            event.app.exit()
        
        @bindings.add(Keys.ControlL)
        def clear_handler(event):
            """Ctrl+L to clear screen"""
            console.clear()
        
        self.key_bindings = bindings
    
    def prompt(self, message: str = "> ") -> str:
        """Get user input with history and shortcuts"""
        return self.session.prompt(
            message,
            key_bindings=self.key_bindings,
            multiline=False
        )
    
    def show_banner(
        self,
        project_name: str,
        model: str,
        permission_mode: str
    ) -> None:
        """Show welcome banner"""
        banner = Panel(
            f"[bold cyan]Cortex[/bold cyan] - Unified Agent for Coding, Cybersecurity, and Personal Assistance\n\n"
            f"📂 Project: [cyan]{project_name}[/cyan]\n"
            f"🤖 Model: [cyan]{model}[/cyan]\n"
            f"🔒 Mode: [cyan]{permission_mode}[/cyan]\n\n"
            f"[dim]Type your requests in natural language or /help for commands[/dim]\n"
            f"[dim]Press Ctrl+D to exit, Ctrl+L to clear screen[/dim]",
            title="🚀 Ready",
            border_style="cyan"
        )
        console.print(banner)
    
    def show_help(self) -> None:
        """Show help message"""
        help_text = """
[bold cyan]Session Commands:[/bold cyan]
  /help              Show this help
  /clear             Clear conversation history
  /mode [normal|auto|plan]  Change permission mode
  /project           Show project info
  /save [name]       Save current session
  /load [name]       Load a saved session
  /sessions          List saved sessions
  /exit              Exit Cortex

[bold cyan]Context Commands:[/bold cyan]
  /summary           Show conversation summary
  /plan              Enter read-only planning mode
  /reset-context     Clear history but keep memory
  /focus <path>      Focus on a directory
  /memory            Show memory bank contents
  /stats             Show session statistics

[bold cyan]Display Commands:[/bold cyan]
  /thinking [on|off] Toggle thinking/reasoning display
  /storage           Show storage statistics
  /cleanup           Run session cleanup

[bold cyan]Tips:[/bold cyan]
  - Be specific about what you want
  - Agent will read files before editing
  - Use plan mode to explore without changes
  - Press Ctrl+C to interrupt
  - Press Ctrl+D to exit
  - Press Ctrl+L to clear screen
"""
        console.print(Panel(help_text, title="Help"))

