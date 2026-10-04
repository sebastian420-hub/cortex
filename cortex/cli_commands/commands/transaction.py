"""Transaction management commands"""

from typing import Optional
from rich.panel import Panel

from .base import Command, CommandContext
from ...ui.console import console


def _transaction_manager(ctx: CommandContext):
    """The session's transaction manager (the one the tools actually back up through)."""
    return ctx.agent.transaction_manager


class RollbackCommand(Command):
    """Undo the file changes of the last request"""

    @property
    def name(self) -> str:
        return "rollback"

    @property
    def description(self) -> str:
        return "Undo the file changes made by the last request"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the rollback command"""
        tm = _transaction_manager(ctx)

        if not tm.enabled:
            console.print(
                "[yellow]Transactions are disabled, so there is nothing to roll back.[/yellow]"
            )
            return

        transaction = tm.get_current_transaction()
        if transaction is not None and transaction.get_backup_count():
            # The same file may be changed several times in one request: list it once
            files = list(dict.fromkeys(transaction.get_files_modified()))
            if tm.rollback():
                console.print(f"[green]✓[/green] Rolled back {len(files)} file(s)")
                for f in files:
                    console.print(f"  [dim]- {f}[/dim]")
            else:
                console.print("[red]Error:[/red] Rollback failed for at least one file")
        else:
            console.print(
                "[yellow]The last request changed no files; nothing to roll back[/yellow]"
            )
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
        tm = _transaction_manager(ctx)
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
