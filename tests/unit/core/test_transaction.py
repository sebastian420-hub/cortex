"""
Unit tests for transaction management (cortex/core/transaction.py).
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from cortex.core.transaction import (
    TransactionState,
    FileBackup,
    Transaction,
    TransactionManager,
    MEMORY_BACKUP_THRESHOLD,
)


class TestTransactionState:
    """Test TransactionState enum."""

    def test_enum_values(self):
        """Test that TransactionState has correct values."""
        assert TransactionState.ACTIVE.value == "active"
        assert TransactionState.COMMITTED.value == "committed"
        assert TransactionState.ROLLED_BACK.value == "rolled_back"
        assert TransactionState.FAILED.value == "failed"


class TestFileBackup:
    """Test FileBackup class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for file operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_file_backup_creation(self):
        """Test creating a FileBackup instance."""
        original_path = Path("/test/file.txt")
        backup_path = Path("/backup/file.txt.bak")

        backup = FileBackup(
            original_path=original_path,
            backup_path=backup_path,
            operation="write",
            content="File content",
            existed=True,
        )

        assert backup.original_path == original_path
        assert backup.backup_path == backup_path
        assert backup.operation == "write"
        assert backup.content == "File content"
        assert backup.existed is True
        assert backup.timestamp is not None

    def test_restore_existing_file_from_content(self, temp_dir):
        """Test restoring a file from in-memory content."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Original content")

        backup = FileBackup(
            original_path=test_file,
            backup_path=None,
            operation="edit",
            content="Original content",  # Backup content
            existed=True,
        )

        # Modify the file
        test_file.write_text("Modified content")

        # Restore from backup
        result = backup.restore()

        assert result is True
        assert test_file.read_text() == "Original content"

    def test_restore_existing_file_from_backup_file(self, temp_dir):
        """Test restoring a file from backup file."""
        original_file = temp_dir / "original.txt"
        original_file.write_text("Original content")

        backup_file = temp_dir / "backup.txt"
        shutil.copy2(original_file, backup_file)

        backup = FileBackup(
            original_path=original_file,
            backup_path=backup_file,
            operation="edit",
            content=None,  # No in-memory content
            existed=True,
        )

        # Modify original
        original_file.write_text("Modified content")

        # Restore from backup file
        result = backup.restore()

        assert result is True
        assert original_file.read_text() == "Original content"
        assert backup_file.exists()

    def test_restore_nonexistent_file(self, temp_dir):
        """Test restoring a file that didn't exist originally."""
        test_file = temp_dir / "newfile.txt"

        backup = FileBackup(
            original_path=test_file,
            backup_path=None,
            operation="write",
            content=None,
            existed=False,
        )

        # Create the file (simulating it was created)
        test_file.write_text("New content")

        # Restore should delete the file
        result = backup.restore()

        assert result is True
        assert not test_file.exists()

    def test_restore_without_backup(self, temp_dir):
        """Test restoring when no backup is available."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Content")

        backup = FileBackup(
            original_path=test_file,
            backup_path=None,
            operation="edit",
            content=None,  # No backup
            existed=True,
        )

        # Restore should fail
        with patch("cortex.core.transaction.logger") as mock_logger:
            result = backup.restore()

            assert result is False
            mock_logger.error.assert_called()

    def test_restore_exception_handling(self, temp_dir):
        """Test exception handling during restore."""
        test_file = temp_dir / "test.txt"

        backup = FileBackup(
            original_path=test_file,
            backup_path=Path("/nonexistent/backup.bak"),
            operation="edit",
            content=None,
            existed=True,
        )

        # File doesn't exist, but existed=True - should cause error
        with patch("cortex.core.transaction.logger") as mock_logger:
            result = backup.restore()

            assert result is False
            mock_logger.error.assert_called()

    def test_cleanup(self, temp_dir):
        """Test cleaning up backup files."""
        backup_file = temp_dir / "backup.bak"
        backup_file.write_text("Backup content")

        backup = FileBackup(
            original_path=Path("/test/original.txt"),
            backup_path=backup_file,
            operation="edit",
            content=None,
            existed=True,
        )

        # Clean up backup file
        backup.cleanup()

        assert not backup_file.exists()

    def test_cleanup_nonexistent_file(self):
        """Test cleanup when backup file doesn't exist."""
        backup = FileBackup(
            original_path=Path("/test/original.txt"),
            backup_path=Path("/nonexistent/backup.bak"),
            operation="edit",
            content=None,
            existed=True,
        )

        # Should not raise exception
        backup.cleanup()


class TestTransaction:
    """Test Transaction class."""

    def test_transaction_creation(self):
        """Test creating a Transaction."""
        transaction = Transaction(
            id="tx_123", state=TransactionState.ACTIVE, metadata={"user": "test", "action": "edit"}
        )

        assert transaction.id == "tx_123"
        assert transaction.state == TransactionState.ACTIVE
        assert transaction.backups == []
        assert transaction.metadata == {"user": "test", "action": "edit"}
        assert transaction.created_at is not None
        assert transaction.completed_at is None

    def test_add_backup(self):
        """Test adding a backup to transaction."""
        transaction = Transaction(id="tx_1")
        backup = FileBackup(
            original_path=Path("/test.txt"),
            backup_path=None,
            operation="edit",
            content="test",
            existed=True,
        )

        transaction.add_backup(backup)

        assert len(transaction.backups) == 1
        assert transaction.backups[0] == backup

    def test_get_backup_count(self):
        """Test getting backup count."""
        transaction = Transaction(id="tx_1")
        assert transaction.get_backup_count() == 0

        backup = Mock(spec=FileBackup)
        transaction.add_backup(backup)

        assert transaction.get_backup_count() == 1

    def test_get_files_modified(self):
        """Test getting list of modified files."""
        transaction = Transaction(id="tx_1")

        path1 = Path("/file1.txt")
        path2 = Path("/file2.txt")

        backup1 = Mock(spec=FileBackup, original_path=path1)
        backup2 = Mock(spec=FileBackup, original_path=path2)

        transaction.add_backup(backup1)
        transaction.add_backup(backup2)

        modified_files = transaction.get_files_modified()

        assert len(modified_files) == 2
        assert path1 in modified_files
        assert path2 in modified_files


class TestTransactionManager:
    """Test TransactionManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for file operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def transaction_manager(self, temp_dir):
        """Create a TransactionManager instance."""
        backup_dir = temp_dir / "backups"
        return TransactionManager(backup_dir=backup_dir, enabled=True)

    def test_initialization(self, temp_dir):
        """Test TransactionManager initialization."""
        backup_dir = temp_dir / "backups"
        manager = TransactionManager(backup_dir=backup_dir, max_backups=5, enabled=False)

        assert manager.backup_dir == backup_dir
        assert manager.max_backups == 5
        assert manager.enabled is False
        assert manager._current_transaction is None
        assert manager._transaction_history == []

    def test_initialization_default_backup_dir(self):
        """Test initialization with default backup directory."""
        with patch("cortex.core.transaction.Path.home", return_value=Path("/home/user")):
            manager = TransactionManager()

            expected = Path("/home/user/.cortex/backups")
            assert manager.backup_dir == expected

    def test_begin_transaction(self, transaction_manager):
        """Test beginning a new transaction."""
        tx = transaction_manager.begin()

        assert tx is not None
        assert tx.state == TransactionState.ACTIVE
        assert transaction_manager._current_transaction == tx

        # Transaction should have an ID
        assert tx.id is not None
        assert len(tx.id) > 0

    def test_begin_transaction_when_one_active(self, transaction_manager):
        """Test beginning a transaction when one is already active."""
        transaction_manager.begin()

        with pytest.raises(RuntimeError):
            transaction_manager.begin()

    def test_commit_transaction(self, transaction_manager):
        """Test committing a transaction."""
        tx = transaction_manager.begin()

        result = transaction_manager.commit()

        assert result is True
        assert tx.state == TransactionState.COMMITTED
        assert tx.completed_at is not None
        assert transaction_manager._current_transaction is None

        # Transaction should be in history
        assert tx in transaction_manager._transaction_history

    def test_commit_no_active_transaction(self, transaction_manager):
        """Test committing when no transaction is active."""
        result = transaction_manager.commit()

        assert result is False

    def test_rollback_transaction(self, transaction_manager):
        """Test rolling back a transaction."""
        tx = transaction_manager.begin()

        result = transaction_manager.rollback()

        assert result is True
        assert tx.state == TransactionState.ROLLED_BACK
        assert tx.completed_at is not None
        assert transaction_manager._current_transaction is None

        # Transaction should be in history
        assert tx in transaction_manager._transaction_history

    def test_rollback_no_active_transaction(self, transaction_manager):
        """Test rolling back when no transaction is active."""
        result = transaction_manager.rollback()

        assert result is False

    def test_backup_file_small_file(self, transaction_manager, temp_dir):
        """Test backing up a small file (in-memory backup)."""
        test_file = temp_dir / "small.txt"
        test_content = "Small file content"
        test_file.write_text(test_content)

        transaction_manager.begin()

        backup = transaction_manager.backup_file(test_file, "edit")

        assert backup is not None
        assert backup.original_path == test_file
        assert backup.operation == "edit"
        assert backup.existed is True
        assert backup.content == test_content
        assert backup.backup_path is None

        # Should be added to current transaction
        tx = transaction_manager._current_transaction
        assert tx is not None
        assert backup in tx.backups

    def test_backup_file_large_file(self, transaction_manager, temp_dir):
        """Test backing up a large file (file backup)."""
        # Create a file larger than memory threshold
        test_file = temp_dir / "large.txt"
        large_content = "x" * (MEMORY_BACKUP_THRESHOLD + 1024)  # > 100KB
        test_file.write_text(large_content)

        transaction_manager.begin()

        backup = transaction_manager.backup_file(test_file, "edit")

        assert backup is not None
        assert backup.original_path == test_file
        assert backup.operation == "edit"
        assert backup.existed is True
        assert backup.content is None  # Too large for memory
        assert backup.backup_path is not None
        assert backup.backup_path.exists()

        # Backup file should contain original content
        assert backup.backup_path.read_text() == large_content

    def test_backup_file_nonexistent(self, transaction_manager, temp_dir):
        """Test backing up a file that doesn't exist."""
        test_file = temp_dir / "nonexistent.txt"

        transaction_manager.begin()

        backup = transaction_manager.backup_file(test_file, "write")

        assert backup is not None
        assert backup.original_path == test_file
        assert backup.operation == "write"
        assert backup.existed is False
        assert backup.content is None
        assert backup.backup_path is None

    def test_backup_file_without_transaction(self, transaction_manager, temp_dir):
        """Test backing up a file without active transaction."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Content")

        backup = transaction_manager.backup_file(test_file, "edit")

        # Should return None when no transaction active
        assert backup is None

    def test_backup_file_disabled(self, temp_dir):
        """Test backing up when transaction manager is disabled."""
        manager = TransactionManager(backup_dir=temp_dir / "backups", enabled=False)

        test_file = temp_dir / "test.txt"
        test_file.write_text("Content")

        manager.begin()
        backup = manager.backup_file(test_file, "edit")

        # Should return None when disabled
        assert backup is None

    def test_context_manager_success(self, transaction_manager, temp_dir):
        """Test transaction context manager on success."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Original")

        with transaction_manager.transaction() as tx:
            assert tx.state == TransactionState.ACTIVE

            # Backup and modify file
            transaction_manager.backup_file(test_file, "edit")
            test_file.write_text("Modified")

        # After context manager exits successfully
        assert tx.state == TransactionState.COMMITTED
        assert transaction_manager._current_transaction is None

        # File should remain modified
        assert test_file.read_text() == "Modified"

    def test_context_manager_exception(self, transaction_manager, temp_dir):
        """Test transaction context manager with exception (rollback)."""
        test_file = temp_dir / "test.txt"
        original_content = "Original content"
        test_file.write_text(original_content)

        try:
            with transaction_manager.transaction() as tx:
                transaction_manager.backup_file(test_file, "edit")
                test_file.write_text("Modified")
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Transaction should be rolled back
        assert tx.state == TransactionState.ROLLED_BACK

        # File should be restored to original
        assert test_file.read_text() == original_content

    def test_get_active_transaction(self, transaction_manager):
        """Test getting active transaction."""
        assert transaction_manager.get_active_transaction() is None

        tx = transaction_manager.begin()
        assert transaction_manager.get_active_transaction() == tx

        transaction_manager.commit()
        assert transaction_manager.get_active_transaction() is None

    def test_get_history(self, transaction_manager):
        """Test getting transaction history."""
        # Initially empty
        assert transaction_manager.get_history() == []

        # Commit a transaction
        tx1 = transaction_manager.begin()
        transaction_manager.commit()

        # Rollback a transaction
        tx2 = transaction_manager.begin()
        transaction_manager.rollback()

        history = transaction_manager.get_history()

        assert len(history) == 2
        assert tx1 in history
        assert tx2 in history
        assert history[0] == tx1
        assert history[1] == tx2

        def test_cleanup_old_backups(self, transaction_manager):
            """Test cleaning up old backups."""

            # Create more transactions than max_backups
            for i in range(transaction_manager.max_backups + 5):
                tx = transaction_manager.begin()
                transaction_manager.commit()

            history = transaction_manager.get_transaction_history()
            assert len(history) <= transaction_manager.max_backups

    def test_transaction_with_metadata(self, transaction_manager):
        """Test transaction with metadata."""
        metadata = {"user": "test", "action": "edit_file"}

        with transaction_manager.transaction(metadata=metadata) as tx:
            assert tx.metadata == metadata

        # Metadata should persist
        assert tx.metadata == metadata
