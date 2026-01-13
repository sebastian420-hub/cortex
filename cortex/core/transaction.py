"""Transaction support for file operations with backup/rollback capability."""

import os
import shutil
import threading
import logging
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from contextlib import contextmanager
from enum import Enum

logger = logging.getLogger(__name__)


class TransactionState(Enum):
    """Transaction state."""

    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class FileBackup:
    """Backup of a single file."""

    original_path: Path
    backup_path: Optional[Path]
    operation: str  # 'write', 'edit', 'delete'
    content: Optional[str]  # In-memory backup for small files
    existed: bool  # Whether file existed before operation
    timestamp: datetime = field(default_factory=datetime.now)

    def restore(self) -> bool:
        """Restore the file to its original state."""
        try:
            if not self.existed:
                # File didn't exist, remove it
                if self.original_path.exists():
                    self.original_path.unlink()
                    logger.debug(f"Removed newly created file: {self.original_path}")
                return True

            # File existed, restore content
            if self.content is not None:
                # Restore from in-memory backup
                self.original_path.write_text(self.content, encoding="utf-8")
                logger.debug(f"Restored from memory: {self.original_path}")
            elif self.backup_path and self.backup_path.exists():
                # Restore from file backup
                shutil.copy2(self.backup_path, self.original_path)
                logger.debug(f"Restored from backup file: {self.original_path}")
            else:
                logger.error(f"No backup available for: {self.original_path}")
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to restore {self.original_path}: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up backup files."""
        if self.backup_path and self.backup_path.exists():
            try:
                self.backup_path.unlink()
                logger.debug(f"Cleaned up backup: {self.backup_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up backup {self.backup_path}: {e}")


@dataclass
class Transaction:
    """Represents a file operation transaction."""

    id: str
    state: TransactionState = TransactionState.ACTIVE
    backups: List[FileBackup] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def add_backup(self, backup: FileBackup) -> None:
        """Add a backup to the transaction."""
        self.backups.append(backup)

    def get_backup_count(self) -> int:
        """Get number of backups in transaction."""
        return len(self.backups)

    def get_files_modified(self) -> List[Path]:
        """Get list of files modified in this transaction."""
        return [b.original_path for b in self.backups]


# Threshold for in-memory vs file backup (100KB)
MEMORY_BACKUP_THRESHOLD = 100 * 1024


class TransactionManager:
    """
    Manages file operation transactions with backup and rollback support.

    Features:
    - Automatic backup before file modifications
    - In-memory backup for small files (<100KB)
    - File-based backup for large files
    - Rollback support
    - Transaction history
    - Thread-safe operations

    Usage:
        tm = TransactionManager(backup_dir=Path(".cortex/backups"))

        # Context manager usage (recommended)
        with tm.transaction():
            tm.backup_file(path, "edit")
            path.write_text(new_content, encoding="utf-8")
        # Auto-commits on success, auto-rollback on exception

        # Manual usage
        tx = tm.begin()
        tm.backup_file(path, "edit")
        # ... make changes ...
        tm.commit()  # or tm.rollback()
    """

    def __init__(
        self, backup_dir: Optional[Path] = None, max_backups: int = 10, enabled: bool = True
    ):
        """
        Initialize TransactionManager.

        Args:
            backup_dir: Directory for file backups (default: .cortex/backups)
            max_backups: Maximum number of backup transactions to keep
            enabled: Whether transaction support is enabled
        """
        self.backup_dir = backup_dir or Path.home() / ".cortex" / "backups"
        self.max_backups = max_backups
        self.enabled = enabled

        self._current_transaction: Optional[Transaction] = None
        self._transaction_history: List[Transaction] = []
        self._lock = threading.Lock()

        # Ensure backup directory exists
        if self.enabled:
            self.backup_dir.mkdir(parents=True, exist_ok=True)

    def begin(self, metadata: Optional[Dict[str, Any]] = None) -> Transaction:
        """
        Begin a new transaction.

        Args:
            metadata: Optional metadata for the transaction

        Returns:
            The new Transaction

        Raises:
            RuntimeError: If a transaction is already active
        """
        if not self.enabled:
            # Return a dummy transaction
            return Transaction(id="disabled")

        with self._lock:
            if self._current_transaction is not None:
                raise RuntimeError("A transaction is already active. Commit or rollback first.")

            tx_id = str(uuid.uuid4())[:8]
            self._current_transaction = Transaction(id=tx_id, metadata=metadata or {})
            logger.debug(f"Transaction started: {tx_id}")
            return self._current_transaction

    def backup_file(self, path: Path, operation: str) -> Optional[FileBackup]:
        """
        Create backup of a file before modification.

        Args:
            path: Path to the file
            operation: Type of operation ('write', 'edit', 'delete')

        Returns:
            FileBackup object or None if disabled/no active transaction
        """
        if not self.enabled:
            return None

        with self._lock:
            if self._current_transaction is None:
                logger.warning("No active transaction for backup")
                return None

            existed = path.exists()
            content = None
            backup_path = None

            if existed:
                try:
                    file_size = path.stat().st_size

                    if file_size <= MEMORY_BACKUP_THRESHOLD:
                        # Small file - backup in memory
                        content = path.read_text(encoding="utf-8")
                        logger.debug(f"In-memory backup: {path} ({file_size} bytes)")
                    else:
                        # Large file - backup to disk
                        tx_backup_dir = self.backup_dir / self._current_transaction.id
                        tx_backup_dir.mkdir(parents=True, exist_ok=True)

                        # Create unique backup filename
                        backup_name = f"{path.name}.{len(self._current_transaction.backups)}.bak"
                        backup_path = tx_backup_dir / backup_name
                        shutil.copy2(path, backup_path)
                        logger.debug(f"File backup: {path} -> {backup_path}")

                except Exception as e:
                    logger.error(f"Failed to backup {path}: {e}")
                    return None

            backup = FileBackup(
                original_path=path,
                backup_path=backup_path,
                operation=operation,
                content=content,
                existed=existed,
            )

            self._current_transaction.add_backup(backup)
            return backup

    def commit(self) -> bool:
        """
        Commit the current transaction.

        Cleans up backup files and marks transaction as committed.

        Returns:
            True if committed successfully
        """
        if not self.enabled:
            return True

        with self._lock:
            if self._current_transaction is None:
                logger.warning("No active transaction to commit")
                return False

            tx = self._current_transaction

            # Clean up backup files
            for backup in tx.backups:
                backup.cleanup()

            # Clean up transaction backup directory
            tx_backup_dir = self.backup_dir / tx.id
            if tx_backup_dir.exists():
                try:
                    shutil.rmtree(tx_backup_dir)
                except Exception as e:
                    logger.warning(f"Failed to clean up transaction dir: {e}")

            tx.state = TransactionState.COMMITTED
            tx.completed_at = datetime.now()

            # Add to history and maintain max_backups limit
            self._transaction_history.append(tx)
            self._cleanup_history()

            self._current_transaction = None
            logger.debug(f"Transaction committed: {tx.id}")
            return True

    def rollback(self) -> bool:
        """
        Rollback the current transaction.

        Restores all backed up files to their original state.

        Returns:
            True if rolled back successfully
        """
        if not self.enabled:
            return True

        with self._lock:
            if self._current_transaction is None:
                logger.warning("No active transaction to rollback")
                return False

            tx = self._current_transaction
            success = True

            # Restore files in reverse order
            for backup in reversed(tx.backups):
                if not backup.restore():
                    success = False

            # Clean up backup files
            for backup in tx.backups:
                backup.cleanup()

            # Clean up transaction backup directory
            tx_backup_dir = self.backup_dir / tx.id
            if tx_backup_dir.exists():
                try:
                    shutil.rmtree(tx_backup_dir)
                except Exception as e:
                    logger.warning(f"Failed to clean up transaction dir: {e}")

            tx.state = TransactionState.ROLLED_BACK
            tx.completed_at = datetime.now()

            # Add to history
            self._transaction_history.append(tx)
            self._cleanup_history()

            self._current_transaction = None
            logger.debug(f"Transaction rolled back: {tx.id}")
            return success

    @contextmanager
    def transaction(self, auto_commit: bool = True, metadata: Optional[Dict[str, Any]] = None):
        """
        Context manager for transactions.

        Args:
            auto_commit: Auto-commit on success (default: True)
            metadata: Optional metadata for the transaction

        Yields:
            The active Transaction

        Example:
            with tm.transaction():
                tm.backup_file(path, "edit")
                path.write_text(new_content, encoding="utf-8")
            # Auto-commits on success
        """
        tx = self.begin(metadata)
        try:
            yield tx
            if auto_commit:
                self.commit()
        except Exception as e:
            logger.error(f"Transaction failed, rolling back: {e}")
            self.rollback()
            raise

    def _cleanup_history(self) -> None:
        """Clean up old transactions from history."""
        while len(self._transaction_history) > self.max_backups:
            old_tx = self._transaction_history.pop(0)
            # Clean up any remaining backup files
            tx_backup_dir = self.backup_dir / old_tx.id
            if tx_backup_dir.exists():
                try:
                    shutil.rmtree(tx_backup_dir)
                except Exception as e:
                    logger.warning(f"Failed to clean up old transaction: {e}")

    def get_current_transaction(self) -> Optional[Transaction]:
        """Get the current active transaction."""
        with self._lock:
            return self._current_transaction

    def get_transaction_history(self) -> List[Transaction]:
        """Get transaction history."""
        with self._lock:
            return list(self._transaction_history)

    def get_last_transaction(self) -> Optional[Transaction]:
        """Get the most recent transaction."""
        with self._lock:
            if self._transaction_history:
                return self._transaction_history[-1]
            return None

    def has_active_transaction(self) -> bool:
        """Check if a transaction is currently active."""
        with self._lock:
            return self._current_transaction is not None

    def get_stats(self) -> Dict[str, Any]:
        """Get transaction manager statistics."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "active_transaction": (
                    self._current_transaction.id if self._current_transaction else None
                ),
                "history_count": len(self._transaction_history),
                "max_backups": self.max_backups,
                "backup_dir": str(self.backup_dir),
                "committed": sum(
                    1 for t in self._transaction_history if t.state == TransactionState.COMMITTED
                ),
                "rolled_back": sum(
                    1 for t in self._transaction_history if t.state == TransactionState.ROLLED_BACK
                ),
            }


# Global transaction manager instance
_transaction_manager: Optional[TransactionManager] = None
_tm_lock = threading.Lock()


def get_transaction_manager(config: Optional[Dict[str, Any]] = None) -> TransactionManager:
    """
    Get or create global transaction manager.

    Args:
        config: Optional configuration dict with keys:
            - enabled: bool (default True)
            - max_backups: int (default 10)
            - backup_dir: str (default .cortex/backups)

    Returns:
        TransactionManager instance
    """
    global _transaction_manager

    with _tm_lock:
        if _transaction_manager is None:
            config = config or {}
            backup_dir = config.get("backup_dir")
            if backup_dir:
                backup_dir = Path(backup_dir)
            _transaction_manager = TransactionManager(
                backup_dir=backup_dir,
                max_backups=config.get("max_backups", 10),
                enabled=config.get("enabled", True),
            )
        return _transaction_manager


def reset_transaction_manager() -> None:
    """Reset global transaction manager (for testing)."""
    global _transaction_manager
    with _tm_lock:
        _transaction_manager = None
