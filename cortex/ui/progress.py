"""Progress indicators for long-running operations."""

import time
from contextlib import contextmanager
from typing import Optional, Generator, Callable, Any
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)

console = Console()


class OperationTracker:
    """
    Track and display progress for long-running operations.

    Supports both determinate (with total) and indeterminate (spinner) progress.
    """

    def __init__(self, console_instance: Optional[Console] = None):
        """
        Initialize the tracker.

        Args:
            console_instance: Optional Rich console to use
        """
        self.console = console_instance or console
        self._current_progress: Optional[Progress] = None
        self._current_task_id: Optional[int] = None
        self._start_time: Optional[float] = None

    @contextmanager
    def track_operation(
        self, description: str, total: Optional[int] = None, show_speed: bool = False
    ) -> Generator["ProgressUpdater", None, None]:
        """
        Context manager for tracking an operation.

        Args:
            description: Description of the operation
            total: Total items (if known, shows progress bar)
            show_speed: Show items/second (for determinate operations)

        Yields:
            ProgressUpdater instance for updating progress
        """
        self._start_time = time.time()

        if total is not None and total > 0:
            # Determinate progress (progress bar)
            columns = [
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ]
            if show_speed:
                columns.append(TextColumn("[dim]{task.speed} it/s[/dim]"))
            columns.append(TimeElapsedColumn())

            with Progress(*columns, console=self.console) as progress:
                task_id = progress.add_task(description, total=total)
                updater = ProgressUpdater(progress, task_id, self._start_time)
                yield updater
        else:
            # Indeterminate progress (spinner)
            with self.console.status(f"[cyan]{description}...[/cyan]", spinner="dots") as status:
                updater = SpinnerUpdater(status, description, self._start_time)
                yield updater

    def simple_status(self, message: str):
        """
        Show a simple status message (non-blocking).

        Args:
            message: Status message to display
        """
        self.console.print(f"[dim]{message}[/dim]")

    def operation_complete(
        self,
        description: str,
        success: bool = True,
        summary: str = "",
        duration: Optional[float] = None,
    ) -> None:
        """
        Display operation completion.

        Args:
            description: What completed
            success: Whether it succeeded
            summary: Brief result summary
            duration: Duration in seconds (auto-calculated if not provided)
        """
        if duration is None and self._start_time:
            duration = time.time() - self._start_time

        icon = "[green]✓[/green]" if success else "[red]✗[/red]"
        parts = [icon, description]

        if summary:
            parts.append(f"- {summary}")

        if duration is not None:
            if duration < 1:
                parts.append(f"[dim]({duration*1000:.0f}ms)[/dim]")
            else:
                parts.append(f"[dim]({duration:.1f}s)[/dim]")

        self.console.print(" ".join(parts))


class ProgressUpdater:
    """Helper for updating determinate progress."""

    def __init__(self, progress: Progress, task_id: int, start_time: float):
        self.progress = progress
        self.task_id = task_id
        self.start_time = start_time
        self._completed = 0

    def update(self, advance: int = 1, description: str = None) -> None:
        """Update progress by advance amount."""
        self.progress.update(self.task_id, advance=advance)
        self._completed += advance
        if description:
            self.progress.update(self.task_id, description=description)

    def set_completed(self, completed: int) -> None:
        """Set absolute completion value."""
        advance = completed - self._completed
        if advance > 0:
            self.progress.update(self.task_id, advance=advance)
            self._completed = completed

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time


class SpinnerUpdater:
    """Helper for updating indeterminate progress (spinner)."""

    def __init__(self, status, description: str, start_time: float):
        self.status = status
        self.description = description
        self.start_time = start_time

    def update(self, message: str = None) -> None:
        """Update the spinner message."""
        if message:
            self.status.update(f"[cyan]{message}...[/cyan]")

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time


@contextmanager
def track_files(
    description: str = "Processing files", total: Optional[int] = None
) -> Generator[ProgressUpdater, None, None]:
    """
    Convenience context manager for file operations.

    Args:
        description: Operation description
        total: Total files (if known)

    Yields:
        Progress updater
    """
    tracker = OperationTracker()
    with tracker.track_operation(description, total) as updater:
        yield updater


@contextmanager
def track_search(
    query: str, total_files: Optional[int] = None
) -> Generator[ProgressUpdater, None, None]:
    """
    Convenience context manager for search operations.

    Args:
        query: Search query/pattern
        total_files: Total files to search (if known)

    Yields:
        Progress updater
    """
    desc = f"Searching: {query[:30]}{'...' if len(query) > 30 else ''}"
    tracker = OperationTracker()
    with tracker.track_operation(desc, total_files) as updater:
        yield updater


def show_operation_summary(
    operation: str, results_count: int, duration_ms: float, details: str = ""
) -> None:
    """
    Display a summary of a completed operation.

    Args:
        operation: Name of operation
        results_count: Number of results
        duration_ms: Duration in milliseconds
        details: Additional details
    """
    parts = [f"[cyan]{operation}:[/cyan]", f"{results_count} results"]

    if details:
        parts.append(f"({details})")

    if duration_ms < 1000:
        parts.append(f"[dim]in {duration_ms:.0f}ms[/dim]")
    else:
        parts.append(f"[dim]in {duration_ms/1000:.1f}s[/dim]")

    console.print(" ".join(parts))


# Global tracker instance for convenience
_global_tracker = OperationTracker()


def get_tracker() -> OperationTracker:
    """Get the global operation tracker."""
    return _global_tracker
