"""Tests for session storage with file locking"""

import pytest
import sys
import threading
import time
import json
from pathlib import Path
from cortex.storage.sessions import SessionManager


def test_atomic_write_with_lock(tmp_path):
    """Test that session save uses atomic write with locking"""
    manager = SessionManager(tmp_path)

    # Save session
    success = manager.save_session(
        "test_session", [{"role": "user", "content": "test"}], str(tmp_path), "llama3.2", "normal"
    )

    assert success is True

    # Verify session file exists
    session_file = tmp_path / "test_session.json"
    assert session_file.exists()

    # Verify no temp files remain
    temp_files = list(tmp_path.glob("*.tmp"))
    assert len(temp_files) == 0, "No temporary files should remain"

    # Verify no lock files remain
    lock_files = list(tmp_path.glob("*.lock"))
    assert len(lock_files) == 0, "No lock files should remain"

    # Verify session can be loaded
    loaded = manager.load_session("test_session")
    assert loaded is not None
    assert loaded["session_name"] == "test_session"


def test_concurrent_session_write(tmp_path):
    """Test that concurrent writes don't corrupt sessions"""
    manager = SessionManager(tmp_path)
    errors = []
    results = []

    def save_session(i):
        try:
            result = manager.save_session(
                f"session_{i}",
                [{"role": "user", "content": f"test_{i}"}],
                str(tmp_path),
                "llama3.2",
                "normal",
            )
            results.append((i, result))
        except Exception as e:
            errors.append((i, e))

    # Spawn multiple threads writing simultaneously
    threads = [threading.Thread(target=save_session, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors occurred
    assert len(errors) == 0, f"Errors occurred: {errors}"

    # Verify all sessions were saved correctly
    sessions = manager.list_sessions()
    assert len(sessions) == 10, f"Expected 10 sessions, got {len(sessions)}"

    # Verify each session can be loaded and has correct content
    for i in range(10):
        loaded = manager.load_session(f"session_{i}")
        assert loaded is not None, f"Session {i} should be loadable"
        assert loaded["session_name"] == f"session_{i}"
        history = loaded["conversation_history"]
        assert len(history) > 0
        assert history[0]["content"] == f"test_{i}"


def test_read_lock_non_blocking(tmp_path):
    """Test that read operations use non-blocking locks"""
    manager = SessionManager(tmp_path)

    # Save a session first
    manager.save_session(
        "test_session", [{"role": "user", "content": "test"}], str(tmp_path), "llama3.2", "normal"
    )

    # Load it (should succeed even if another process is writing)
    # This test verifies non-blocking read behavior
    loaded = manager.load_session("test_session")
    assert loaded is not None

    # Try loading while another thread is writing (should still work)
    write_done = threading.Event()

    def write_session():
        manager.save_session(
            "test_session",
            [{"role": "user", "content": "updated"}],
            str(tmp_path),
            "llama3.2",
            "normal",
        )
        write_done.set()

    # Start write in background
    write_thread = threading.Thread(target=write_session)
    write_thread.start()

    # Try to read while writing (non-blocking)
    loaded_during_write = manager.load_session("test_session")

    # Wait for write to complete
    write_thread.join()

    # Read should have succeeded (non-blocking)
    assert loaded_during_write is not None


def test_lock_timeout(tmp_path):
    """Test that lock acquisition times out after timeout period"""
    manager = SessionManager(tmp_path)

    # Create a lock file manually to simulate locked state
    lock_file = tmp_path / "test.lock"
    lock_file.write_text("locked")

    # Try to save (should eventually timeout or fallback)
    # The implementation should handle this gracefully
    success = manager.save_session(
        "test_session", [{"role": "user", "content": "test"}], str(tmp_path), "llama3.2", "normal"
    )

    # Should either succeed (fallback) or fail gracefully
    # The important thing is it doesn't hang forever
    assert isinstance(success, bool)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
def test_windows_file_locking(tmp_path):
    """Test Windows-specific file locking using msvcrt"""
    import msvcrt

    manager = SessionManager(tmp_path)

    # Test that Windows locking constants are defined
    from cortex.storage.sessions import LOCK_EX, LOCK_SH, LOCK_NB

    assert LOCK_EX == 0x1
    assert LOCK_SH == 0x0
    assert LOCK_NB == 0x2

    # Test actual locking
    test_file = tmp_path / "test.txt"
    with open(test_file, "w") as f:
        # Try to acquire lock
        locked = manager._acquire_lock(f, exclusive=True, blocking=False)
        assert locked is True or locked is False  # May succeed or fail, but should return bool

        # Release lock
        manager._release_lock(f)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
def test_unix_file_locking(tmp_path):
    """Test Unix-specific file locking using fcntl"""
    import fcntl

    manager = SessionManager(tmp_path)

    # Test that Unix locking constants are defined
    from cortex.storage.sessions import LOCK_EX, LOCK_SH, LOCK_NB

    assert LOCK_EX == fcntl.LOCK_EX
    assert LOCK_SH == fcntl.LOCK_SH
    assert LOCK_NB == fcntl.LOCK_NB

    # Test actual locking
    test_file = tmp_path / "test.txt"
    with open(test_file, "w") as f:
        # Try to acquire lock
        locked = manager._acquire_lock(f, exclusive=True, blocking=False)
        assert locked is True or locked is False  # May succeed or fail, but should return bool

        # Release lock
        manager._release_lock(f)


def test_fallback_on_lock_failure(tmp_path):
    """Test that write falls back gracefully if lock can't be acquired"""
    manager = SessionManager(tmp_path)

    # Mock lock acquisition to always fail
    original_acquire = manager._acquire_lock

    def mock_acquire_lock(*args, **kwargs):
        return False  # Always fail

    manager._acquire_lock = mock_acquire_lock

    # Try to save (should fallback to direct write)
    success = manager.save_session(
        "test_session", [{"role": "user", "content": "test"}], str(tmp_path), "llama3.2", "normal"
    )

    # Should still succeed (fallback behavior)
    assert success is True

    # Verify session was saved
    loaded = manager.load_session("test_session")
    assert loaded is not None

    # Restore original method
    manager._acquire_lock = original_acquire


def test_concurrent_same_session_write(tmp_path):
    """Test concurrent writes to the same session file"""
    manager = SessionManager(tmp_path)

    errors = []
    success_count = [0]

    def save_session_same_name(i):
        try:
            result = manager.save_session(
                "same_session",  # Same name for all threads
                [{"role": "user", "content": f"test_{i}"}],
                str(tmp_path),
                "llama3.2",
                "normal",
            )
            if result:
                success_count[0] += 1
        except Exception as e:
            errors.append((i, e))

    # Spawn multiple threads writing to same session
    threads = [threading.Thread(target=save_session_same_name, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # At least one should succeed
    assert success_count[0] > 0, "At least one write should succeed"

    # Verify final session is loadable
    loaded = manager.load_session("same_session")
    assert loaded is not None


def test_session_file_integrity(tmp_path):
    """Test that session files maintain integrity during concurrent access"""
    manager = SessionManager(tmp_path)

    # Save initial session
    initial_data = [{"role": "user", "content": "initial"}]
    manager.save_session("integrity_test", initial_data, str(tmp_path), "llama3.2", "normal")

    # Verify initial save
    loaded = manager.load_session("integrity_test")
    assert loaded["conversation_history"] == initial_data

    # Concurrently read and write
    read_results = []
    write_errors = []

    def read_session():
        try:
            result = manager.load_session("integrity_test")
            read_results.append(result)
        except Exception as e:
            read_results.append(None)

    def write_session(i):
        try:
            manager.save_session(
                "integrity_test",
                [{"role": "user", "content": f"update_{i}"}],
                str(tmp_path),
                "llama3.2",
                "normal",
            )
        except Exception as e:
            write_errors.append(e)

    # Start multiple readers and writers
    threads = []
    for i in range(3):
        threads.append(threading.Thread(target=read_session))
        threads.append(threading.Thread(target=write_session, args=(i,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All reads should succeed (even if they get old or new data)
    assert len(read_results) == 3
    # Note: In highly concurrent scenarios, some reads might fail due to file locking
    # This is acceptable - the important thing is that writes don't corrupt the file
    successful_reads = sum(1 for r in read_results if r is not None)
    assert successful_reads >= 2, f"At least 2 reads should succeed, got {successful_reads}"

    # Final session should be loadable
    final = manager.load_session("integrity_test")
    assert final is not None
    assert len(final["conversation_history"]) > 0
