"""Consolidated display system for live progress tracking.

This module provides a consolidated display system that groups related operations
and shows live progress updates, creating a cleaner UI similar to Claude Code.

Key features:
- Groups related operations by time window and context
- Shows live progress with status indicators (⏳, ✓, ✗)
- Integrates with existing progress tracking systems
- Mode-aware display (minimal/normal/debug)
- Real-time status updates during parallel execution
"""

import time
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner

from .console import console
from .modes import get_ui_mode, UIMode
from .progress import OperationTracker, ProgressUpdater
from .plan_progress import PlanProgressDisplay


class OperationStatus(str, Enum):
    """Status of an operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class OperationType(str, Enum):
    """Type of operation for grouping."""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    SEARCH = "search"
    EXECUTION = "execution"
    ANALYSIS = "analysis"
    UNKNOWN = "unknown"


@dataclass
class Operation:
    """Represents a single operation."""
    id: str
    name: str
    description: str
    operation_type: OperationType
    arguments: Dict[str, Any] = field(default_factory=dict)
    status: OperationStatus = OperationStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class OperationGrouper:
    """Groups related operations for consolidated display."""
    
    def __init__(self, consolidation_window_ms: int = 1000):
        """
        Initialize operation grouper.
        
        Args:
            consolidation_window_ms: Time window for grouping operations (default: 1000ms)
        """
        self.consolidation_window_ms = consolidation_window_ms
    
    def classify_operation(self, tool_name: str, arguments: Dict[str, Any]) -> OperationType:
        """Classify an operation based on tool name and arguments."""
        tool_name_lower = tool_name.lower()
        
        if tool_name_lower in ["read_file", "read_file_chunked"]:
            return OperationType.FILE_READ
        elif tool_name_lower in ["write_file"]:
            return OperationType.FILE_WRITE
        elif tool_name_lower in ["edit", "replace_in_file"]:
            return OperationType.FILE_EDIT
        elif tool_name_lower in ["grep", "search_files", "glob"]:
            return OperationType.SEARCH
        elif tool_name_lower in ["execute_command", "run_tests"]:
            return OperationType.EXECUTION
        elif tool_name_lower in ["ast_search", "ast_extract", "ast_analyze"]:
            return OperationType.ANALYSIS
        else:
            return OperationType.UNKNOWN
    
    def group_operations(self, operations: List[Operation]) -> Dict[str, List[Operation]]:
        """Group operations by type and time proximity."""
        if not operations:
            return {}
        
        # Sort by start time
        sorted_ops = sorted(operations, key=lambda op: op.start_time or 0)
        
        groups = {}
        current_group = []
        current_type = None
        
        for op in sorted_ops:
            if current_type is None:
                current_type = op.operation_type
                current_group = [op]
            elif (op.operation_type == current_type and 
                  (not current_group[-1].start_time or 
                   not op.start_time or 
                   (op.start_time - current_group[-1].start_time) * 1000 < self.consolidation_window_ms)):
                # Same type and within time window
                current_group.append(op)
            else:
                # Different type or outside time window - finalize current group
                if current_group:
                    group_key = f"{current_type.value}_{len(current_group)}"
                    groups[group_key] = current_group
                current_type = op.operation_type
                current_group = [op]
        
        # Add final group
        if current_group:
            group_key = f"{current_type.value}_{len(current_group)}"
            groups[group_key] = current_group
        
        return groups


class ConsolidatedConsole:
    """Proxy console that intercepts output for consolidated display."""
    
    def __init__(self, original_console: Console, display_manager: 'ConsolidatedDisplay'):
        self.original_console = original_console
        self.display_manager = display_manager
    
    def print(self, *args, **kwargs):
        """Intercept print calls and route to display manager."""
        if self.display_manager.is_tracking():
            # Route to consolidated display
            self.display_manager.handle_output(*args, **kwargs)
        else:
            # Pass through to original console
            self.original_console.print(*args, **kwargs)
    
    def __getattr__(self, name):
        """Pass through all other attributes to original console."""
        return getattr(self.original_console, name)


class ConsolidatedDisplay:
    """Main consolidated display system."""
    
    def __init__(self, console_instance: Optional[Console] = None):
        """
        Initialize consolidated display.
        
        Args:
            console_instance: Optional Rich console to use
        """
        self.console = console_instance or console

        # Operation tracking
        self._operations: Dict[str, Operation] = {}
        self._operation_groups: Dict[str, List[Operation]] = {}
        self._grouper = OperationGrouper()
        
        # Display state
        self._is_tracking = False
        self._live_display = None
        self._current_task = None
        self._start_time = None
        
        # Progress integration
        self._progress_tracker = OperationTracker(self.console)
        self._plan_display = PlanProgressDisplay(self.console)
        
        # Threading - use RLock to prevent deadlock when update_operation_status is called from within track_operations
        self._lock = threading.RLock()

        # Context stats for footer
        self._context_stats: Optional[Dict[str, Any]] = None

    def update_context_stats(self, stats: Dict[str, Any]) -> None:
        """Update context statistics for footer display."""
        self._context_stats = stats

    @contextmanager
    def track_operations(self, tool_calls: List[Any], agent_description: str = "Processing"):
        """
        Context manager for tracking operations.

        Args:
            tool_calls: List of tool calls being executed
            agent_description: Description of what the agent is doing
        """
        # Lock only for critical section (setup)
        with self._lock:
            self._is_tracking = True
            self._start_time = time.time()

            # Create operations from tool calls
            self._create_operations(tool_calls)

            # Group operations
            self._operation_groups = self._grouper.group_operations(list(self._operations.values()))

        # Start live display outside lock to avoid blocking
        self._start_live_display(agent_description)

        try:
            yield self
        finally:
            # Stop display and cleanup
            self._stop_live_display()

            # Lock only for cleanup
            with self._lock:
                self._is_tracking = False
    
    def is_tracking(self) -> bool:
        """Check if currently tracking operations."""
        return self._is_tracking
    
    def handle_output(self, *args, **kwargs):
        """
        Handle intercepted console output.
        
        This method is called when tools try to print during tracking.
        """
        # For now, suppress individual tool outputs during tracking
        # They will be shown in the consolidated display
        pass
    
    def update_operation_status(
        self, 
        operation_id: str, 
        status: OperationStatus, 
        result: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        Update the status of an operation.
        
        Args:
            operation_id: ID of the operation
            status: New status
            result: Optional result message
            error: Optional error message
        """
        with self._lock:
            if operation_id not in self._operations:
                return
            
            operation = self._operations[operation_id]
            operation.status = status
            
            if status == OperationStatus.IN_PROGRESS and operation.start_time is None:
                operation.start_time = time.time()
            elif status in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
                operation.end_time = time.time()
                if operation.start_time:
                    operation.duration_ms = (operation.end_time - operation.start_time) * 1000
            
            if result:
                operation.result = result
            if error:
                operation.error = error
            
            # Update live display
            self._update_live_display()
    
    def _create_operations(self, tool_calls: List[Any]):
        """Create operation objects from tool calls."""
        for i, tool_call in enumerate(tool_calls):
            tool_name = getattr(tool_call, 'name', str(tool_call))
            arguments = getattr(tool_call, 'arguments', {})
            
            operation_type = self._grouper.classify_operation(tool_name, arguments)
            
            # Create descriptive name
            description = self._create_operation_description(tool_name, arguments)
            
            operation = Operation(
                id=f"op_{i}_{tool_name}",
                name=tool_name,
                description=description,
                operation_type=operation_type,
            )
            
            self._operations[operation.id] = operation
    
    def _create_operation_description(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Create a human-readable description of an operation."""
        tool_name_lower = tool_name.lower()
        
        if tool_name_lower == "read_file":
            path = arguments.get("path", "unknown file")
            offset = arguments.get("offset", 0)
            limit = arguments.get("limit", 0)
            if offset > 0 or limit > 0:
                return f"Reading {path} (lines {offset + 1}-{offset + (limit or 'end')})"
            return f"Reading {path}"
        
        elif tool_name_lower == "write_file":
            path = arguments.get("path", "unknown file")
            return f"Writing to {path}"
        
        elif tool_name_lower == "edit":
            path = arguments.get("path", "unknown file")
            return f"Editing {path}"
        
        elif tool_name_lower in ["grep", "search_files"]:
            pattern = arguments.get("pattern", "unknown pattern")
            return f"Searching for '{pattern}'"
        
        elif tool_name_lower == "execute_command":
            command = arguments.get("command", "unknown command")
            return f"Executing: {command[:50]}{'...' if len(str(command)) > 50 else ''}"
        
        else:
            return f"{tool_name} operation"
    
    def _start_live_display(self, agent_description: str):
        """Start the live display."""
        ui_mode = get_ui_mode()  # Get current UI mode dynamically
        if ui_mode == UIMode.MINIMAL:
            # Minimal mode: simple status line
            self.console.print(f"[cyan]🔍 {agent_description}...[/cyan]")
        elif ui_mode == UIMode.NORMAL:
            # Normal mode: detailed progress display
            self._create_detailed_display(agent_description)
        elif ui_mode == UIMode.DEBUG:
            # Debug mode: detailed display with extra information
            self._create_detailed_display(agent_description)
    
    def _stop_live_display(self):
        """Stop the live display and show final summary."""
        ui_mode = get_ui_mode()  # Get current UI mode dynamically
        if ui_mode == UIMode.MINIMAL:
            self._show_minimal_summary()
        elif ui_mode == UIMode.NORMAL:
            self._show_detailed_summary()
        elif ui_mode == UIMode.DEBUG:
            self._show_detailed_summary()  # Same as normal but could add more debug info

        # Ensure live display is properly stopped
        if self._live_display:
            try:
                self._live_display.stop()
            except Exception:
                pass  # Live display might already be stopped
            self._live_display = None
    
    def _create_detailed_display(self, agent_description: str):
        """Create detailed live display."""
        # Create initial display
        display_content = self._build_display_content(agent_description)
        
        # Start live display
        self._live_display = Live(display_content, console=self.console, refresh_per_second=4)
        self._live_display.start()
    
    def _update_live_display(self):
        """Update the live display with current operation status."""
        if self._live_display:
            display_content = self._build_display_content("Processing")
            self._live_display.update(display_content)
    
    def _build_display_content(self, agent_description: str):
        """Build the content for the live display."""
        ui_mode = get_ui_mode()  # Get current UI mode dynamically
        if ui_mode == UIMode.MINIMAL:
            return self._build_minimal_display(agent_description)
        else:
            return self._build_detailed_display(agent_description)
    
    def _build_minimal_display(self, agent_description: str) -> str:
        """Build minimal display content."""
        completed = sum(1 for op in self._operations.values() if op.status == OperationStatus.COMPLETED)
        total = len(self._operations)

        # Build main display
        if total == 0:
            main_display = f"[cyan]🔍 {agent_description}...[/cyan]"
        elif completed == total:
            main_display = f"[green]✓ {agent_description} complete[/green]"
        else:
            progress = f"{completed}/{total}"
            main_display = f"[cyan]🔍 {agent_description}... ({progress})[/cyan]"

        # Add context footer if stats available
        if self._context_stats:
            footer = self._render_status_footer(self._context_stats)
            return f"{main_display}\n{footer}"

        return main_display
    
    def _build_detailed_display(self, agent_description: str) -> Panel:
        """Build detailed display content."""
        # Create table for operations
        table = Table(show_header=False, show_lines=True, border_style="cyan")
        table.add_column("Status", style="bold", width=3)
        table.add_column("Operation", style="dim", width=50)
        table.add_column("Result", style="dim")

        # Add operations
        for operation in self._operations.values():
            status_icon = self._get_status_icon(operation.status)
            status_color = self._get_status_color(operation.status)

            status_text = f"[{status_color}]{status_icon}[/{status_color}]"

            # Format description
            desc = operation.description
            if len(desc) > 45:
                desc = desc[:42] + "..."

            # Format result
            result_text = ""
            if operation.status == OperationStatus.COMPLETED and operation.result:
                result_text = operation.result[:30] + "..." if len(operation.result) > 30 else operation.result
            elif operation.status == OperationStatus.FAILED and operation.error:
                result_text = f"Error: {operation.error[:30]}..."
            elif operation.duration_ms:
                result_text = f"{operation.duration_ms:.0f}ms"

            table.add_row(status_text, desc, result_text)

        # Add context footer if stats available
        if self._context_stats:
            footer = self._render_status_footer(self._context_stats)
            table.add_row("", "", "")  # Spacer
            table.add_row("", footer, "")

        # Create panel
        duration = time.time() - self._start_time if self._start_time else 0
        duration_str = f" ({duration:.1f}s)" if duration > 0 else ""

        return Panel(
            table,
            title=f"[cyan]🔍 {agent_description}{duration_str}[/cyan]",
            border_style="cyan"
        )
    
    def _get_status_icon(self, status: OperationStatus) -> str:
        """Get icon for operation status."""
        icons = {
            OperationStatus.PENDING: "○",
            OperationStatus.IN_PROGRESS: "◐",
            OperationStatus.COMPLETED: "●",
            OperationStatus.FAILED: "✗",
            OperationStatus.SKIPPED: "⊘",
        }
        return icons.get(status, "?")
    
    def _get_status_color(self, status: OperationStatus) -> str:
        """Get color for operation status."""
        colors = {
            OperationStatus.PENDING: "dim",
            OperationStatus.IN_PROGRESS: "yellow",
            OperationStatus.COMPLETED: "green",
            OperationStatus.FAILED: "red",
            OperationStatus.SKIPPED: "dim cyan",
        }
        return colors.get(status, "white")

    def _render_status_footer(self, stats: Dict[str, Any]) -> str:
        """
        Render status bar footer with context budget info.

        Args:
            stats: Statistics dictionary from conversation.get_truncation_stats()

        Returns:
            Formatted status footer string
        """
        import sys

        mode = get_ui_mode()
        tokens = stats.get('current_token_count', 0)
        max_tokens = stats.get('max_tokens', 100000)
        utilization = stats.get('token_utilization', 0)

        # Use ASCII-safe bar on Windows to avoid encoding issues
        if sys.platform == "win32":
            filled_char = "#"
            empty_char = "-"
        else:
            filled_char = "█"
            empty_char = "░"

        if mode == UIMode.MINIMAL:
            # Minimal: Just percentage
            color = "red" if utilization >= 90 else "yellow" if utilization >= 70 else "dim"
            return f"[{color}]Context: {utilization:.0f}%[/{color}]"

        elif mode == UIMode.NORMAL:
            # Normal: Bar + percentage
            bar_width = 20
            filled = int((utilization / 100) * bar_width)
            bar = filled_char * filled + empty_char * (bar_width - filled)
            color = "red" if utilization >= 90 else "yellow" if utilization >= 70 else "green"
            return f"[{color}]Context: [{bar}] {utilization:.0f}%[/{color}]"

        else:  # DEBUG
            # Debug: Full details
            bar_width = 20
            filled = int((utilization / 100) * bar_width)
            bar = filled_char * filled + empty_char * (bar_width - filled)
            color = "red" if utilization >= 90 else "yellow" if utilization >= 70 else "green"
            msgs = stats.get('current_message_count', 0)
            avg = stats.get('avg_tokens_per_message', 0)
            return (f"[{color}]Context: {tokens:,}/{max_tokens:,} [{bar}] {utilization:.0f}% | "
                    f"{msgs} msgs (avg {avg:.0f}t/msg)[/{color}]")

    def _show_minimal_summary(self):
        """Show final summary in minimal mode."""
        completed = sum(1 for op in self._operations.values() if op.status == OperationStatus.COMPLETED)
        failed = sum(1 for op in self._operations.values() if op.status == OperationStatus.FAILED)
        total = len(self._operations)
        
        if failed == 0:
            self.console.print(f"[green]✓ Completed {completed}/{total} operations[/green]")
        else:
            self.console.print(f"[yellow]⚠ Completed {completed}/{total}, {failed} failed[/yellow]")
    
    def _show_detailed_summary(self):
        """Show final summary in detailed mode."""
        completed = sum(1 for op in self._operations.values() if op.status == OperationStatus.COMPLETED)
        failed = sum(1 for op in self._operations.values() if op.status == OperationStatus.FAILED)
        total = len(self._operations)

        # Note: live display is stopped in _stop_live_display, not here to avoid double stop

        # Show summary table
        summary_table = Table(title="Operation Summary", show_header=False, border_style="green")
        summary_table.add_column("Metric", style="dim")
        summary_table.add_column("Value", style="bold")
        
        summary_table.add_row("Total Operations", str(total))
        summary_table.add_row("Completed", f"[green]{completed}[/green]")
        summary_table.add_row("Failed", f"[red]{failed}[/red]")
        
        if total > 0:
            success_rate = (completed / total) * 100
            summary_table.add_row("Success Rate", f"{success_rate:.1f}%")
        
        self.console.print(summary_table)
    
    def get_operation_summary(self) -> Dict[str, Any]:
        """Get summary of all operations."""
        completed = sum(1 for op in self._operations.values() if op.status == OperationStatus.COMPLETED)
        failed = sum(1 for op in self._operations.values() if op.status == OperationStatus.FAILED)
        in_progress = sum(1 for op in self._operations.values() if op.status == OperationStatus.IN_PROGRESS)
        
        return {
            "total": len(self._operations),
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "success_rate": (completed / len(self._operations) * 100) if self._operations else 0,
            "operations": [
                {
                    "id": op.id,
                    "name": op.name,
                    "description": op.description,
                    "status": op.status.value,
                    "duration_ms": op.duration_ms,
                    "result": op.result,
                    "error": op.error,
                }
                for op in self._operations.values()
            ]
        }


# Global consolidated display instance
_consolidated_display = ConsolidatedDisplay()


def get_consolidated_display() -> ConsolidatedDisplay:
    """Get the global consolidated display instance."""
    return _consolidated_display


def create_consolidated_console(original_console: Console) -> ConsolidatedConsole:
    """Create a consolidated console that routes output to consolidated display."""
    return ConsolidatedConsole(original_console, _consolidated_display)