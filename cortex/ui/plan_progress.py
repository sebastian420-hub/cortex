"""Rich-based progress display for plan execution.

This module provides specialized UI components for displaying plan execution
progress, including tree views, progress bars, and step status updates.
"""

import time
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table
from rich.live import Live
from rich.text import Text

from .console import console


class PlanProgressDisplay:
    """Rich-based progress display for plan execution.

    Provides visual feedback during plan execution including:
    - Plan overview tree
    - Step-by-step progress bar
    - Status updates with icons
    - Completion summary
    """

    # Status icons and colors
    STATUS_STYLES = {
        "pending": ("○", "dim"),
        "in_progress": ("◐", "yellow"),
        "completed": ("●", "green"),
        "failed": ("✗", "red"),
        "skipped": ("⊘", "dim cyan"),
    }

    def __init__(self, console_instance: Optional[Console] = None):
        """Initialize the plan progress display.

        Args:
            console_instance: Optional Rich console to use
        """
        self.console = console_instance or console
        self._start_time: Optional[float] = None
        self._progress: Optional[Progress] = None
        self._task_id: Optional[int] = None

    def show_plan_overview(self, plan: Any) -> None:
        """Display a tree view of the plan before execution.

        Args:
            plan: The Plan object to display
        """
        # Create a tree view of the plan
        tree = Tree(
            f"[bold cyan]📋 Plan: {plan.goal[:60]}{'...' if len(plan.goal) > 60 else ''}[/bold cyan]"
        )

        # Add metadata branch
        meta = tree.add("[dim]Metadata[/dim]")
        meta.add(f"[dim]ID:[/dim] {plan.id}")
        meta.add(
            f"[dim]Created:[/dim] {plan.created_at[:19] if hasattr(plan, 'created_at') else 'N/A'}"
        )
        if hasattr(plan, "constraints") and plan.constraints:
            meta.add(f"[dim]Constraints:[/dim] {len(plan.constraints)}")

        # Add steps branch
        steps_branch = tree.add(f"[bold]Steps ({len(plan.steps)})[/bold]")
        for i, step in enumerate(plan.steps, 1):
            icon, color = self.STATUS_STYLES.get(step.status.value, ("?", "white"))
            step_text = f"[{color}]{icon}[/{color}] {i}. {step.description[:50]}{'...' if len(step.description) > 50 else ''}"  # noqa: E501
            step_node = steps_branch.add(step_text)

            # Add step details if present
            if hasattr(step, "tool_name") and step.tool_name:
                step_node.add(f"[dim]Tool: {step.tool_name}[/dim]")
            if hasattr(step, "dependencies") and step.dependencies:
                step_node.add(f"[dim]Depends on: {', '.join(step.dependencies)}[/dim]")

        # Display the tree in a panel
        self.console.print(Panel(tree, border_style="blue"))

    def show_step_start(self, step: Any, step_number: int, total_steps: int) -> None:
        """Display step start notification.

        Args:
            step: The PlanStep being started
            step_number: Current step number (1-indexed)
            total_steps: Total number of steps
        """
        self.console.print()
        self.console.print(f"[cyan]▶ Step {step_number}/{total_steps}:[/cyan] {step.description}")

        if hasattr(step, "tool_name") and step.tool_name:
            self.console.print(f"   [dim]Tool: {step.tool_name}[/dim]")
        if hasattr(step, "expected_outcome") and step.expected_outcome:
            self.console.print(f"   [dim]Expected: {step.expected_outcome}[/dim]")

    def show_step_complete(self, step: Any, result: Optional[str] = None) -> None:
        """Display step completion notification.

        Args:
            step: The completed PlanStep
            result: Optional result message
        """
        outcome = result or "Completed successfully"
        if len(outcome) > 100:
            outcome = outcome[:97] + "..."
        self.console.print(f"   [green]✓ Success:[/green] {outcome}")

    def show_step_failed(self, step: Any, error: str) -> None:
        """Display step failure notification.

        Args:
            step: The failed PlanStep
            error: Error message
        """
        self.console.print(f"   [red]✗ Failed:[/red] {error}")

    def show_step_skipped(self, step: Any, reason: str = "Dependencies not met") -> None:
        """Display step skipped notification.

        Args:
            step: The skipped PlanStep
            reason: Reason for skipping
        """
        self.console.print(f"   [dim cyan]⊘ Skipped:[/dim cyan] {reason}")

    def start_progress_bar(self, total_steps: int, description: str = "Executing plan") -> None:
        """Start a progress bar for plan execution.

        Args:
            total_steps: Total number of steps
            description: Description for the progress bar
        """
        self._start_time = time.time()
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
        )
        self._progress.start()
        self._task_id = self._progress.add_task(description, total=total_steps)

    def update_progress(self, advance: int = 1, description: Optional[str] = None) -> None:
        """Update the progress bar.

        Args:
            advance: Number of steps to advance
            description: Optional new description
        """
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, advance=advance)
            if description:
                self._progress.update(self._task_id, description=description)

    def stop_progress_bar(self) -> None:
        """Stop the progress bar."""
        if self._progress:
            self._progress.stop()
            self._progress = None
            self._task_id = None

    def show_execution_summary(self, plan: Any, step_results: List[Dict[str, Any]]) -> None:
        """Display a summary of plan execution.

        Args:
            plan: The executed Plan
            step_results: List of step execution results
        """
        duration = time.time() - self._start_time if self._start_time else 0
        progress = plan.get_progress() if hasattr(plan, "get_progress") else {}

        # Create summary table
        table = Table(title="Execution Summary", show_header=False, border_style="green")
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")

        table.add_row("Plan ID", plan.id)
        table.add_row("Goal", plan.goal[:50] + "..." if len(plan.goal) > 50 else plan.goal)
        table.add_row("Total Steps", str(progress.get("total", len(plan.steps))))
        table.add_row("Completed", f"[green]{progress.get('completed', 0)}[/green]")
        table.add_row("Failed", f"[red]{progress.get('failed', 0)}[/red]")
        table.add_row("Skipped", f"[dim]{progress.get('skipped', 0)}[/dim]")

        if duration > 0:
            if duration < 60:
                duration_str = f"{duration:.1f}s"
            else:
                minutes = int(duration // 60)
                seconds = duration % 60
                duration_str = f"{minutes}m {seconds:.1f}s"
            table.add_row("Duration", duration_str)

        # Calculate success rate
        total = progress.get("total", 1)
        completed = progress.get("completed", 0)
        success_rate = (completed / total * 100) if total > 0 else 0
        table.add_row("Success Rate", f"{success_rate:.1f}%")

        self.console.print()
        self.console.print(table)

    def show_plan_complete(self, plan: Any) -> None:
        """Display plan completion message.

        Args:
            plan: The completed Plan
        """
        self.console.print()
        self.console.print("[bold green]✅ Plan Execution Complete[/bold green]")

    def show_plan_failed(self, plan: Any, error: str) -> None:
        """Display plan failure message.

        Args:
            plan: The failed Plan
            error: Error message
        """
        self.console.print()
        self.console.print(f"[bold red]❌ Plan Execution Failed:[/bold red] {error}")


def create_plan_display(console_instance: Optional[Console] = None) -> PlanProgressDisplay:
    """Factory function to create a PlanProgressDisplay.

    Args:
        console_instance: Optional Rich console to use

    Returns:
        Configured PlanProgressDisplay instance
    """
    return PlanProgressDisplay(console_instance)


# Convenience function for quick status updates
def show_step_status(
    step_number: int,
    total_steps: int,
    description: str,
    status: str = "in_progress",
    result: Optional[str] = None,
) -> None:
    """Show a quick step status update.

    Args:
        step_number: Current step number
        total_steps: Total steps in plan
        description: Step description
        status: Step status (pending, in_progress, completed, failed, skipped)
        result: Optional result or error message
    """
    icon, color = PlanProgressDisplay.STATUS_STYLES.get(status, ("?", "white"))

    if status == "in_progress":
        console.print(f"[cyan]▶ Step {step_number}/{total_steps}:[/cyan] {description}")
    elif status == "completed":
        msg = result or "Done"
        console.print(f"   [{color}]{icon}[/{color}] {msg}")
    elif status == "failed":
        msg = result or "Failed"
        console.print(f"   [{color}]{icon}[/{color}] {msg}")
    else:
        console.print(f"   [{color}]{icon}[/{color}] {description}")
