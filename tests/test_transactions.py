"""Tests for transaction/backup/rollback functionality."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from cortex.core.transaction import (
    TransactionManager,
    Transaction,
    TransactionState,
    FileBackup,
    get_transaction_manager,
    reset_transaction_manager,
)


@pytest.fixture(autouse=True)
def reset_global_tm():
    """Reset global transaction manager before each test."""
    reset_transaction_manager()
    yield
    reset_transaction_manager()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_file(temp_dir):
    """Create a temporary file for testing."""
    path = temp_dir / "test_file.txt"
    path.write_text("Original content")
    return path


@pytest.fixture
def tm(temp_dir):
    """Create a test transaction manager."""
    return TransactionManager(backup_dir=temp_dir / "backups", max_backups=5, enabled=True)


class TestFileBackup:
    """Tests for FileBackup class."""

    def test_backup_restore_existing_file(self, temp_file):
        """Test backup and restore of an existing file."""
        original_content = temp_file.read_text()

        backup = FileBackup(
            original_path=temp_file,
            backup_path=None,
            operation="edit",
            content=original_content,
            existed=True,
        )

        # Modify the file
        temp_file.write_text("Modified content")
        assert temp_file.read_text() == "Modified content"

        # Restore
        assert backup.restore() is True
        assert temp_file.read_text() == original_content

    def test_backup_restore_new_file(self, temp_dir):
        """Test backup and restore removes newly created file."""
        new_file = temp_dir / "new_file.txt"

        backup = FileBackup(
            original_path=new_file, backup_path=None, operation="write", content=None, existed=False
        )

        # Create the file
        new_file.write_text("New content")
        assert new_file.exists()

        # Restore (should remove it)
        assert backup.restore() is True
        assert not new_file.exists()

    def test_backup_restore_with_file_backup(self, temp_dir, temp_file):
        """Test backup and restore using file-based backup."""
        original_content = temp_file.read_text()

        # Create a backup file
        backup_path = temp_dir / "backup.bak"
        backup_path.write_text(original_content)

        backup = FileBackup(
            original_path=temp_file,
            backup_path=backup_path,
            operation="edit",
            content=None,  # No in-memory content
            existed=True,
        )

        # Modify the file
        temp_file.write_text("Modified content")

        # Restore
        assert backup.restore() is True
        assert temp_file.read_text() == original_content


class TestTransaction:
    """Tests for Transaction class."""

    def test_transaction_creation(self):
        """Test transaction creation."""
        tx = Transaction(id="test123")
        assert tx.id == "test123"
        assert tx.state == TransactionState.ACTIVE
        assert tx.get_backup_count() == 0
        assert tx.get_files_modified() == []

    def test_transaction_add_backup(self, temp_file):
        """Test adding backup to transaction."""
        tx = Transaction(id="test123")

        backup = FileBackup(
            original_path=temp_file,
            backup_path=None,
            operation="edit",
            content="content",
            existed=True,
        )

        tx.add_backup(backup)
        assert tx.get_backup_count() == 1
        assert temp_file in tx.get_files_modified()


class TestTransactionManager:
    """Tests for TransactionManager class."""

    def test_begin_transaction(self, tm):
        """Test beginning a transaction."""
        tx = tm.begin(metadata={"test": True})

        assert tx is not None
        assert tx.state == TransactionState.ACTIVE
        assert tx.metadata == {"test": True}
        assert tm.has_active_transaction()

    def test_begin_transaction_while_active_fails(self, tm):
        """Test that beginning a transaction while one is active fails."""
        tm.begin()

        with pytest.raises(RuntimeError, match="already active"):
            tm.begin()

    def test_commit_transaction(self, tm, temp_file):
        """Test committing a transaction."""
        tm.begin()
        tm.backup_file(temp_file, "edit")

        # Modify file
        temp_file.write_text("Modified")

        assert tm.commit() is True
        assert not tm.has_active_transaction()

        # History should contain the transaction
        history = tm.get_transaction_history()
        assert len(history) == 1
        assert history[0].state == TransactionState.COMMITTED

    def test_rollback_transaction(self, tm, temp_file):
        """Test rolling back a transaction."""
        original_content = temp_file.read_text()

        tm.begin()
        tm.backup_file(temp_file, "edit")

        # Modify file
        temp_file.write_text("Modified")

        assert tm.rollback() is True
        assert not tm.has_active_transaction()

        # File should be restored
        assert temp_file.read_text() == original_content

        # History should contain the transaction
        history = tm.get_transaction_history()
        assert len(history) == 1
        assert history[0].state == TransactionState.ROLLED_BACK

    def test_rollback_new_file(self, tm, temp_dir):
        """Test rolling back creation of a new file."""
        new_file = temp_dir / "new_file.txt"
        assert not new_file.exists()

        tm.begin()
        tm.backup_file(new_file, "write")

        # Create file
        new_file.write_text("New content")
        assert new_file.exists()

        # Rollback should remove it
        assert tm.rollback() is True
        assert not new_file.exists()

    def test_transaction_context_manager_success(self, tm, temp_file):
        """Test transaction context manager with successful operation."""
        original_content = temp_file.read_text()

        with tm.transaction() as tx:
            tm.backup_file(temp_file, "edit")
            temp_file.write_text("Modified")

        # Should be committed
        assert temp_file.read_text() == "Modified"
        assert tx.state == TransactionState.COMMITTED

    def test_transaction_context_manager_exception(self, tm, temp_file):
        """Test transaction context manager with exception (auto-rollback)."""
        original_content = temp_file.read_text()

        with pytest.raises(ValueError):
            with tm.transaction() as tx:
                tm.backup_file(temp_file, "edit")
                temp_file.write_text("Modified")
                raise ValueError("Test error")

        # Should be rolled back
        assert temp_file.read_text() == original_content
        assert tx.state == TransactionState.ROLLED_BACK

    def test_backup_small_file_in_memory(self, tm, temp_file):
        """Test that small files are backed up in memory."""
        tm.begin()
        backup = tm.backup_file(temp_file, "edit")

        # Small file should use in-memory backup
        assert backup is not None
        assert backup.content is not None
        assert backup.backup_path is None

    def test_backup_large_file_on_disk(self, tm, temp_dir):
        """Test that large files are backed up to disk."""
        large_file = temp_dir / "large_file.txt"
        # Create a file larger than MEMORY_BACKUP_THRESHOLD (100KB)
        large_content = "x" * (150 * 1024)
        large_file.write_text(large_content)

        tm.begin()
        backup = tm.backup_file(large_file, "edit")

        # Large file should use file backup
        assert backup is not None
        assert backup.content is None
        assert backup.backup_path is not None
        assert backup.backup_path.exists()

    def test_multiple_file_backups(self, tm, temp_dir):
        """Test backing up multiple files in one transaction."""
        files = []
        original_contents = []

        for i in range(3):
            f = temp_dir / f"file_{i}.txt"
            f.write_text(f"Original {i}")
            files.append(f)
            original_contents.append(f"Original {i}")

        tm.begin()
        for f in files:
            tm.backup_file(f, "edit")
            f.write_text("Modified")

        # All files are modified
        for f in files:
            assert f.read_text() == "Modified"

        # Rollback all
        tm.rollback()

        # All files should be restored
        for i, f in enumerate(files):
            assert f.read_text() == original_contents[i]

    def test_history_cleanup(self, temp_dir):
        """Test that history is cleaned up when max_backups exceeded."""
        tm = TransactionManager(backup_dir=temp_dir / "backups", max_backups=3, enabled=True)

        # Create 5 transactions
        for i in range(5):
            tm.begin()
            tm.commit()

        # Only last 3 should be in history
        history = tm.get_transaction_history()
        assert len(history) == 3

    def test_disabled_transaction_manager(self, temp_dir, temp_file):
        """Test that disabled transaction manager doesn't backup."""
        tm = TransactionManager(backup_dir=temp_dir / "backups", enabled=False)

        tx = tm.begin()
        assert tx.id == "disabled"

        backup = tm.backup_file(temp_file, "edit")
        assert backup is None

        # Commit/rollback still work (no-op)
        assert tm.commit() is True
        assert tm.rollback() is True

    def test_get_stats(self, tm):
        """Test getting transaction statistics."""
        stats = tm.get_stats()

        assert stats["enabled"] is True
        assert stats["active_transaction"] is None
        assert stats["history_count"] == 0
        assert stats["max_backups"] == 5
        assert stats["committed"] == 0
        assert stats["rolled_back"] == 0

    def test_get_last_transaction(self, tm):
        """Test getting the last transaction."""
        assert tm.get_last_transaction() is None

        tm.begin()
        tm.commit()

        last = tm.get_last_transaction()
        assert last is not None
        assert last.state == TransactionState.COMMITTED


class TestGlobalTransactionManager:
    """Tests for global transaction manager functions."""

    def test_get_transaction_manager_singleton(self):
        """Test that get_transaction_manager returns singleton."""
        tm1 = get_transaction_manager()
        tm2 = get_transaction_manager()
        assert tm1 is tm2

    def test_get_transaction_manager_with_config(self):
        """Test get_transaction_manager with custom config."""
        config = {"enabled": True, "max_backups": 20}
        tm = get_transaction_manager(config)
        stats = tm.get_stats()
        assert stats["max_backups"] == 20


class TestTransactionManagerThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_transactions_fail(self, tm):
        """Test that concurrent transactions from different threads fail."""
        import threading
        import time

        errors = []
        tx_started = threading.Event()

        def thread1():
            try:
                tm.begin()
                tx_started.set()
                time.sleep(0.2)  # Hold transaction
                tm.commit()
            except Exception as e:
                errors.append(e)

        def thread2():
            tx_started.wait()  # Wait for thread1 to start transaction
            try:
                tm.begin()  # Should fail
            except RuntimeError as e:
                errors.append(e)

        t1 = threading.Thread(target=thread1)
        t2 = threading.Thread(target=thread2)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Thread2 should have raised RuntimeError
        assert len(errors) == 1
        assert "already active" in str(errors[0])
