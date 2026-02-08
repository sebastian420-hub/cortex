"""Statistics and information commands"""

from typing import Optional
from datetime import datetime
from rich.table import Table
from rich.panel import Panel

from .base import Command, CommandContext
from ...ui.console import console


class ProjectCommand(Command):
    """Show project information"""

    @property
    def name(self) -> str:
        return "project"

    @property
    def description(self) -> str:
        return "Show project information"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the project command"""
        info = f"""
[bold]Project Information[/bold]
Path: {ctx.agent.project_dir}
Mode: {ctx.agent.permission_mode}
Model: {ctx.agent.model}
Session: {(datetime.now() - ctx.agent.session_start).seconds // 60} minutes
Tokens: {ctx.agent.conversation.get_token_count()}
"""
        console.print(Panel(info, title="Project"))


class StatsCommand(Command):
    """Show session statistics"""

    @property
    def name(self) -> str:
        return "stats"

    @property
    def description(self) -> str:
        return "Show session statistics"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the stats command"""
        stats = ctx.agent.conversation.get_truncation_stats()

        table = Table(title="Session Statistics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        # Token statistics
        table.add_row("Current Tokens", f"{stats['current_token_count']:,}")
        table.add_row("Max Tokens", f"{stats['max_tokens']:,}")
        table.add_row("Utilization", f"{stats['token_utilization']:.1f}%")
        table.add_row("Remaining", f"{stats['tokens_remaining']:,}")
        table.add_row("", "")

        # Message statistics
        table.add_row("Messages", str(stats['current_message_count']))
        table.add_row("Avg Tokens/Msg", f"{stats['avg_tokens_per_message']:.0f}")
        table.add_row("", "")

        # Optimization statistics
        table.add_row("Truncations", str(stats['truncation_count']))
        table.add_row("Summarizations", str(stats['summarization_count']))
        table.add_row("Messages Removed", str(stats['total_messages_removed']))

        console.print(table)


class RoutingCommand(Command):
    """Show routing statistics"""

    @property
    def name(self) -> str:
        return "routing"

    @property
    def description(self) -> str:
        return "Show routing statistics"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the routing command"""
        if hasattr(ctx.agent, 'get_routing_statistics'):
            routing_stats = ctx.agent.get_routing_statistics()
            if routing_stats:
                stats_text = f"""
[bold]Routing Statistics[/bold]

Total Requests: {routing_stats.get('total_requests', 0)}
Cache Hits: {routing_stats.get('cache_hits', 0)}
Cache Misses: {routing_stats.get('cache_misses', 0)}
Cache Hit Rate: {routing_stats.get('cache_hit_rate', 0):.1%}
Errors: {routing_stats.get('errors', 0)}

[bold]Performance[/bold]
Avg Task Analysis: {routing_stats.get('avg_task_analysis_time_ms', 0):.1f}ms
Avg Routing Time: {routing_stats.get('avg_routing_time_ms', 0):.1f}ms

[bold]Cache[/bold]
Entries: {routing_stats.get('cache_size', 0)}
"""
                console.print(Panel(stats_text, title="Routing Stats", border_style="cyan"))
            else:
                console.print("[dim]Routing is not enabled. Use --routing flag to enable.[/dim]")
        else:
            console.print("[dim]Routing is not available.[/dim]")


class StorageCommand(Command):
    """Show storage statistics"""

    @property
    def name(self) -> str:
        return "storage"

    @property
    def description(self) -> str:
        return "Show storage statistics"

    def __init__(self, session_manager):
        """Initialize with session manager"""
        self._session_manager = session_manager

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the storage command"""
        from ...storage.cleanup import SessionCleanupManager

        cleanup_manager = SessionCleanupManager(
            sessions_dir=self._session_manager.sessions_dir,
            max_age_days=ctx.agent.config.session_retention.get("max_age_days", 30),
            max_count=ctx.agent.config.session_retention.get("max_count", 100),
            max_total_size_mb=ctx.agent.config.session_retention.get("max_total_size_mb", 500),
        )
        stats = cleanup_manager.get_storage_stats()
        info = f"""
[bold]Storage Statistics[/bold]
Sessions: {stats['session_count']} / {stats['limit_count']} ({stats['usage_percent_count']}%)
Size: {stats['total_size_mb']} MB / {stats['limit_size_mb']} MB ({stats['usage_percent_size']}%)
Max Age: {stats['limit_age_days']} days

Oldest: {stats['oldest_session'] or 'N/A'}
Newest: {stats['newest_session'] or 'N/A'}
"""
        console.print(Panel(info, title="Storage"))


class CleanupCommand(Command):
    """Manual session cleanup"""

    @property
    def name(self) -> str:
        return "cleanup"

    @property
    def description(self) -> str:
        return "Manual session cleanup"

    def __init__(self, session_manager):
        """Initialize with session manager"""
        self._session_manager = session_manager

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the cleanup command"""
        from ...storage.cleanup import SessionCleanupManager

        cleanup_manager = SessionCleanupManager(
            sessions_dir=self._session_manager.sessions_dir,
            max_age_days=ctx.agent.config.session_retention.get("max_age_days", 30),
            max_count=ctx.agent.config.session_retention.get("max_count", 100),
            max_total_size_mb=ctx.agent.config.session_retention.get("max_total_size_mb", 500),
        )
        stats = cleanup_manager.run_full_cleanup()
        if stats.sessions_removed > 0:
            console.print(
                f"[green]✓[/green] Removed {stats.sessions_removed} sessions, "
                f"freed {stats.bytes_freed // 1024} KB"
            )
        else:
            console.print("[green]✓[/green] No sessions needed cleanup")
        if stats.errors:
            for error in stats.errors:
                console.print(f"[red]Error:[/red] {error}")
