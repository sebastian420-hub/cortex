"""Gym command for autonomous practice sessions"""

from typing import Optional
from .base import Command, CommandContext
from ...core.gym.manager import GymManager
from ...ui.console import console

class GymCommand(Command):
    """
    Command to start an autonomous practice session in the Cognitive Gym.
    Usage: /gym --task "Fix Bug" --goal "Find and fix the circular import in models.py"
           /gym --bench bug-sum-to-off-by-one   (a verified session on a benchmark task)
    """

    @property
    def name(self) -> str:
        return "gym"

    @property
    def description(self) -> str:
        return "Start an autonomous practice session in the Cognitive Gym"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        if not args:
            console.print(
                "[yellow]Usage: /gym --task <task_name> --goal <practice_goal>[/yellow]\n"
                "[yellow]       /gym --bench <task_id>   (or: /gym --bench list)[/yellow]"
            )
            return

        # Simple parsing for --task, --goal and --bench
        task_name = "practice"
        practice_goal = ""
        bench_id = ""

        parts = args.split("--")
        for part in parts:
            if part.startswith("task "):
                task_name = part[5:].strip().strip('"')
            elif part.startswith("goal "):
                practice_goal = part[5:].strip().strip('"')
            elif part.startswith("bench"):
                bench_id = part[5:].strip().strip('"')

        if bench_id == "list" or (args.strip() == "--bench"):
            self._list_benchmark(ctx)
            return

        if not bench_id and not practice_goal:
            console.print("[red]Error: --goal is required for a practice session.[/red]")
            return

        console.print("[cyan]Entering Cognitive Gym...[/cyan]")
        console.print(f"[dim]Task: {bench_id or task_name}[/dim]")
        if practice_goal:
            console.print(f"[dim]Goal: {practice_goal}[/dim]")

        try:
            manager = GymManager(ctx.agent)
            if bench_id:
                result = manager.run_benchmark_task(bench_id)
            else:
                result = manager.run_practice_session(task_name, practice_goal)
            self._report(ctx, result, bench_id or task_name)
        except Exception as e:
            console.print(f"[red]Error during gym execution: {e}[/red]")

    def _list_benchmark(self, ctx: CommandContext) -> None:
        try:
            from bench.suite import TASKS
        except ImportError:
            console.print("[yellow]The benchmark tasks are only available in a source checkout.[/yellow]")
            return
        for task in TASKS:
            console.print(f"  {task.id}  [dim]{task.kind}: {task.title}[/dim]")

    def _report(self, ctx: CommandContext, result: dict, name: str) -> None:
        """Say what happened: what the verifier found, or that nothing checked the work."""
        if result.get("verified"):
            if result.get("success"):
                console.print(f"[green]Practice session '{name}' passed its verifier.[/green]")
            else:
                console.print(
                    f"[red]Practice session '{name}' failed its verifier:[/red] {result.get('error')}"
                )
        elif result.get("success") is None:
            console.print(
                f"[yellow]Practice session '{name}' finished, but nothing checked the result, so "
                f"it is neither a success nor a failure.[/yellow] "
                f"[dim](use /gym --bench <task_id> for a session that is verified)[/dim]"
            )
        else:
            console.print(f"[red]Practice session failed: {result.get('error')}[/red]")

        if result.get("reflected"):
            has_long_term = getattr(ctx.agent.memory_bank, "semantic_manager", None) is not None
            console.print(
                "[dim]Learnings have been recorded to long-term memory.[/dim]"
                if has_long_term
                else "[dim]Learnings were recorded for this session only (long-term memory is off).[/dim]"
            )
        else:
            console.print(
                "[yellow]The session ended without saving learnings: the model did not "
                "call metacognitive_reflect.[/yellow]"
            )
