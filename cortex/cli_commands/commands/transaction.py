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


def _checkpoint_store(ctx: CommandContext):
    """The session's git checkpoint store, or None when checkpoints are off."""
    return getattr(ctx.agent, "checkpoints", None)


def _explain_unavailable(store) -> None:
    if store is None:
        console.print("[yellow]Git checkpoints are turned off (checkpoints.enabled).[/yellow]")
    else:
        console.print(
            "[yellow]/undo needs the project to be in a git repository.[/yellow] "
            "[dim]/rollback still undoes edits made with Cortex's file tools.[/dim]"
        )


def _report_restore(result, verb: str) -> None:
    files = len(result.restored) + len(result.removed)
    label = f' "{result.snapshot.label}"' if result.snapshot.label else ""
    console.print(
        f"[green]✓[/green] {verb}: restored {len(result.restored)} file(s), "
        f"removed {len(result.removed)} created since{label}"
        if files
        else f"[green]✓[/green] {verb}: the project already matched that checkpoint"
    )
    for path in result.restored[:20]:
        console.print(f"  [dim]restored {path}[/dim]")
    for path in result.removed[:20]:
        console.print(f"  [dim]removed  {path}[/dim]")
    if files > 40:
        console.print(f"  [dim]... and {files - 40} more[/dim]")
    if result.failed:
        console.print(f"[red]Could not restore {len(result.failed)} file(s):[/red]")
        for path in result.failed[:20]:
            console.print(f"  [dim]{path}[/dim]")
    if result.head_moved and result.head_at_snapshot:
        console.print(
            "[yellow]A command moved the git branch since this checkpoint.[/yellow] Files were "
            "restored; the branch was not. To move it back: "
            f"[cyan]git reset --soft {result.head_at_snapshot[:12]}[/cyan] (see also git reflog)"
        )


class UndoCommand(Command):
    """Restore the project to how it was before the last request"""

    @property
    def name(self) -> str:
        return "undo"

    @property
    def description(self) -> str:
        return "Restore the project to before the last request (git checkpoint)"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        store = _checkpoint_store(ctx)
        if store is None or not store.available():
            _explain_unavailable(store)
            return
        try:
            result = store.restore()
        except LookupError as e:
            console.print(f"[yellow]{e}[/yellow]")
            return
        except Exception as e:  # git failed halfway: say so rather than crash the session
            console.print(f"[red]Undo failed:[/red] {e}")
            return
        _report_restore(result, "Undone")
        console.print("[dim]/redo brings the undone changes back.[/dim]")


class RedoCommand(Command):
    """Bring back what the last /undo took away"""

    @property
    def name(self) -> str:
        return "redo"

    @property
    def description(self) -> str:
        return "Bring back the changes the last /undo removed"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        store = _checkpoint_store(ctx)
        if store is None or not store.available():
            _explain_unavailable(store)
            return
        try:
            result = store.redo()
        except LookupError as e:
            console.print(f"[yellow]{e}[/yellow]")
            return
        except Exception as e:
            console.print(f"[red]Redo failed:[/red] {e}")
            return
        _report_restore(result, "Redone")
