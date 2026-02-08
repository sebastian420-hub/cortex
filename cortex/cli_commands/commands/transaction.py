"""Transaction management commands"""

from typing import Optional
from rich.panel import Panel

from .base import Command, CommandContext
from ...ui.console import console


class RollbackCommand(Command):
    """Rollback active transaction"""

    @property
    def name(self) -> str:
        return "rollback"

    @property
    def description(self) -> str:
        return "Rollback active transaction"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the rollback command"""
        from ...core.transaction import get_transaction_manager

        tm = get_transaction_manager(ctx.agent.config.get_transactions_config())

        if tm.has_active_transaction():
            tx = tm.get_current_transaction()
            files = tx.get_files_modified()
            if tm.rollback():
                console.print(f"[green]✓[/green] Rolled back {len(files)} file(s)")
                for f in files:
                    console.print(f"  [dim]- {f}[/dim]")
            else:
                console.print("[red]Error:[/red] Rollback failed")
        else:
            console.print("[yellow]No active transaction to rollback[/yellow]")
            # Show last transaction info
            last_tx = tm.get_last_transaction()
            if last_tx:
                console.print(f"[dim]Last transaction: {last_tx.id} ({last_tx.state.value})[/dim]")


class TransactionsCommand(Command):
    """Show transaction statistics"""

    @property
    def name(self) -> str:
        return "transactions"

    @property
    def description(self) -> str:
        return "Show transaction statistics"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the transactions command"""
        from ...core.transaction import get_transaction_manager

        tm = get_transaction_manager(ctx.agent.config.get_transactions_config())
        stats = tm.get_stats()
        info = f"""
[bold]Transaction Statistics[/bold]
Enabled: {stats['enabled']}
Active Transaction: {stats['active_transaction'] or 'None'}
History: {stats['history_count']} / {stats['max_backups']}
Committed: {stats['committed']}
Rolled Back: {stats['rolled_back']}
Backup Dir: {stats['backup_dir']}
"""
        console.print(Panel(info, title="Transactions"))
