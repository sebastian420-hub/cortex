"""Gym command for autonomous practice sessions"""

from typing import Optional
from .base import Command, CommandContext
from ...core.gym.manager import GymManager
from ...ui.console import console

class GymCommand(Command):
    """
    Command to start an autonomous practice session in the Cognitive Gym.
    Usage: /gym --task "Fix Bug" --goal "Find and fix the circular import in models.py"
    """

    @property
    def name(self) -> str:
        return "gym"

    @property
    def description(self) -> str:
        return "Start an autonomous practice session in the Cognitive Gym"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        if not args:
            console.print("[yellow]Usage: /gym --task <task_name> --goal <practice_goal>[/yellow]")
            return

        # Simple parsing for --task and --goal
        task_name = "practice"
        practice_goal = ""
        
        parts = args.split("--")
        for part in parts:
            if part.startswith("task "):
                task_name = part[5:].strip().strip('"')
            elif part.startswith("goal "):
                practice_goal = part[5:].strip().strip('"')

        if not practice_goal:
            console.print("[red]Error: --goal is required for a practice session.[/red]")
            return

        console.print(f"[cyan]Entering Cognitive Gym...[/cyan]")
        console.print(f"[dim]Task: {task_name}[/dim]")
        console.print(f"[dim]Goal: {practice_goal}[/dim]")
        
        try:
            manager = GymManager(ctx.agent)
            result = manager.run_practice_session(task_name, practice_goal)
            
            if result.get("success"):
                console.print(f"[green]Practice session '{task_name}' completed successfully.[/green]")
                console.print(f"[dim]Learnings have been recorded to Semantic Memory.[/dim]")
            else:
                console.print(f"[red]Practice session failed: {result.get('error')}[/red]")
                
        except Exception as e:
            console.print(f"[red]Error during gym execution: {e}[/red]")
