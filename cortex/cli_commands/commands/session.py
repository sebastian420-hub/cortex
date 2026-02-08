"""Session management commands"""

from typing import Optional
from datetime import datetime

from .base import Command, CommandContext
from ...ui.console import console


class SaveSessionCommand(Command):
    """Save current session"""

    @property
    def name(self) -> str:
        return "save"

    @property
    def description(self) -> str:
        return "Save current session"

    def __init__(self, session_manager):
        """Initialize with session manager reference"""
        self._session_manager = session_manager

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the save command"""
        session_name = (
            args.strip() if args else f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self._session_manager.save_session(
            session_name,
            ctx.agent.get_conversation_history(),
            str(ctx.agent.project_dir),
            ctx.agent.model,
            ctx.agent.permission_mode,
        )


class LoadSessionCommand(Command):
    """Load a saved session"""

    @property
    def name(self) -> str:
        return "load"

    @property
    def description(self) -> str:
        return "Load a saved session"

    def __init__(self, session_manager):
        """Initialize with session manager reference"""
        self._session_manager = session_manager

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the load command"""
        if args:
            session_name = args.strip()
            session_data = self._session_manager.load_session(session_name)
            if session_data:
                ctx.agent.conversation.history = session_data["conversation_history"]
                ctx.agent.model = session_data.get("model", ctx.agent.model)
                ctx.agent.permission_mode = session_data.get("permission_mode", ctx.agent.permission_mode)
                console.print("[green]✓[/green] Session loaded")
        else:
            console.print("[red]Usage: /load <session_name>[/red]")


class ListSessionsCommand(Command):
    """List all saved sessions"""

    @property
    def name(self) -> str:
        return "sessions"

    @property
    def description(self) -> str:
        return "List all saved sessions"

    def __init__(self, session_manager):
        """Initialize with session manager reference"""
        self._session_manager = session_manager

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the sessions command"""
        self._session_manager.show_sessions()


class SessionRecoveryCommand(Command):
    """Session recovery operations (validate/repair/rollback/checkpoint)"""

    @property
    def name(self) -> str:
        return "session"

    @property
    def description(self) -> str:
        return "Session recovery operations"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the session command"""
        parts = args.strip().split() if args else []
        subcommand = parts[0] if parts else "help"

        if subcommand == "validate":
            self._validate_session(ctx)
        elif subcommand == "repair":
            self._repair_session(ctx, parts[1] if len(parts) > 1 else None)
        elif subcommand == "rollback":
            self._rollback_session(ctx, parts[1] if len(parts) > 1 else None)
        elif subcommand == "checkpoint":
            self._create_checkpoint(ctx)
        else:
            self._show_help()

    def _validate_session(self, ctx: CommandContext):
        """Validate current session health"""
        console.print("[cyan]🔍 Validating session health...[/cyan]")
        health_report = ctx.agent.validate_session_health()

        if health_report["healthy"]:
            console.print("[green]✅ Session is healthy[/green]")
        else:
            console.print("[red]❌ Session has issues[/red]")

        # Display issues
        if health_report.get("issues"):
            console.print("\n[bold]Issues Found:[/bold]")
            for issue in health_report["issues"]:
                severity_color = {
                    "critical": "red",
                    "warning": "yellow",
                    "info": "blue"
                }.get(issue.get("severity", "info"), "white")
                console.print(f"  [{severity_color}]• {issue['message']}[/{severity_color}]")

        # Display recommendations
        if health_report.get("recommendations"):
            console.print("\n[bold]Recommendations:[/bold]")
            for rec in health_report["recommendations"]:
                console.print(f"  [cyan]• {rec}[/cyan]")

    def _repair_session(self, ctx: CommandContext, strategy: Optional[str]):
        """Trigger recovery repair"""
        console.print("[cyan]🔧 Attempting to repair session...[/cyan]")

        # Get session health first
        health_report = ctx.agent.validate_session_health()

        if health_report["healthy"]:
            console.print("[green]✅ Session is already healthy - no repair needed[/green]")
            return

        # Analyze and recommend recovery
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        action = ctx.agent.recovery_orchestrator.analyze_and_recommend(
            session_id, ctx.agent.get_conversation_history()
        )

        console.print(f"[cyan]Recommended strategy: {action.strategy.value}[/cyan]")

        # Execute recovery
        result = ctx.agent.recovery_orchestrator.execute_recovery(
            action, ctx.agent.get_conversation_history(), session_id
        )

        if result["success"]:
            console.print("[green]✅ Session repair completed successfully[/green]")
            console.print(f"[dim]Strategy used: {result['strategy']}[/dim]")
        else:
            console.print("[red]❌ Session repair failed[/red]")
            console.print("[dim]Consider using /clear to start fresh[/dim]")

    def _rollback_session(self, ctx: CommandContext, checkpoint_id: Optional[str]):
        """Rollback to checkpoint"""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        checkpoints = ctx.agent.checkpoint_manager.list_checkpoints(session_id)

        if not checkpoints:
            console.print("[yellow]❌ No checkpoints available for rollback[/yellow]")
            console.print("[dim]Checkpoints are created automatically during sessions[/dim]")
            return

        if checkpoint_id:
            # Specific checkpoint requested
            checkpoint = next((cp for cp in checkpoints if cp.id == checkpoint_id), None)
            if not checkpoint:
                console.print(f"[red]❌ Checkpoint '{checkpoint_id}' not found[/red]")
                console.print("[dim]Available checkpoints:[/dim]")
                for cp in checkpoints[:5]:  # Show first 5
                    console.print(f"  [dim]- {cp.id} ({cp.timestamp})[/dim]")
                return
        else:
            # Use most recent checkpoint
            checkpoint = checkpoints[0]  # Already sorted by timestamp desc
            console.print(f"[cyan]Using latest checkpoint: {checkpoint.id}[/cyan]")

        console.print("[cyan]🔄 Rolling back to checkpoint...[/cyan]")

        # Restore checkpoint
        restored_history = ctx.agent.checkpoint_manager.restore_checkpoint(checkpoint)

        if restored_history:
            ctx.agent.conversation.history = restored_history
            console.print("[green]✅ Session rolled back successfully[/green]")
            console.print(f"[dim]Restored {len(restored_history)} messages[/dim]")
        else:
            console.print("[red]❌ Failed to restore checkpoint[/red]")

    def _create_checkpoint(self, ctx: CommandContext):
        """Create manual checkpoint"""
        console.print("[cyan]📝 Creating checkpoint...[/cyan]")

        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        health_report = ctx.agent.health_monitor.analyze_health(ctx.agent.get_conversation_history())

        checkpoint = ctx.agent.checkpoint_manager.create_checkpoint(
            session_id,
            ctx.agent.get_conversation_history(),
            health_score=health_report.overall_score
        )

        console.print("[green]✅ Checkpoint created[/green]")
        console.print(f"[dim]ID: {checkpoint.id}[/dim]")
        console.print(f"[dim]Messages: {checkpoint.message_count}[/dim]")
        console.print(f"[dim]Health Score: {health_report.overall_score:.1f}[/dim]")

    def _show_help(self):
        """Show session command help"""
        console.print("[dim]Session recovery commands:[/dim]")
        console.print("  [cyan]/session validate[/cyan]  - Check session health")
        console.print("  [cyan]/session repair[/cyan]    - Attempt automatic repair")
        console.print("  [cyan]/session rollback[/cyan]  - Rollback to checkpoint")
        console.print("  [cyan]/session checkpoint[/cyan] - Create manual checkpoint")
