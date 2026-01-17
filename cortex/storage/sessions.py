"""Session persistence for Cortex"""

import json
import logging
import os
import stat
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)

# Platform-specific file locking
if sys.platform == "win32":
    import msvcrt

    LOCK_EX = 0x1  # Exclusive lock
    LOCK_SH = 0x0  # Shared lock (read)
    LOCK_NB = 0x2  # Non-blocking
else:
    import fcntl

    LOCK_EX = fcntl.LOCK_EX
    LOCK_SH = fcntl.LOCK_SH
    LOCK_NB = fcntl.LOCK_NB

console = Console()


class SessionManager:
    """Manages saving and loading conversation sessions"""

    # File permission: owner read/write only (0600)
    FILE_PERMISSION = stat.S_IRUSR | stat.S_IWUSR
    # Directory permission: owner only (0700)
    DIR_PERMISSION = stat.S_IRWXU

    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self._ensure_secure_directory()
        self._lock_timeout = 5.0  # Timeout for acquiring locks (seconds)

    def _ensure_secure_directory(self) -> None:
        """Create storage directory with secure permissions"""
        if not self.sessions_dir.exists():
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            # Set secure permissions on Unix systems
            if sys.platform != "win32":
                try:
                    os.chmod(self.sessions_dir, self.DIR_PERMISSION)
                except OSError as e:
                    logger.warning(f"Could not set directory permissions: {e}")
        else:
            # Fix permissions on existing directory (Unix only)
            if sys.platform != "win32":
                try:
                    current_mode = self.sessions_dir.stat().st_mode
                    # Check if group or others have any access
                    if current_mode & (stat.S_IRWXG | stat.S_IRWXO):
                        os.chmod(self.sessions_dir, self.DIR_PERMISSION)
                        logger.info("Fixed insecure directory permissions")
                except OSError as e:
                    logger.warning(f"Could not check/fix directory permissions: {e}")

    def _secure_file(self, file_path: Path) -> None:
        """Set secure permissions on a file (owner read/write only)"""
        if sys.platform != "win32":
            try:
                os.chmod(file_path, self.FILE_PERMISSION)
            except OSError as e:
                logger.warning(f"Could not set file permissions on {file_path}: {e}")

    def _acquire_lock(self, file_handle, exclusive: bool = True, blocking: bool = True) -> bool:
        """
        Acquire a file lock.

        Args:
            file_handle: Open file handle
            exclusive: True for write lock, False for read lock
            blocking: True to wait for lock, False to fail immediately

        Returns:
            True if lock acquired, False otherwise
        """
        try:
            if sys.platform == "win32":
                # Windows locking
                mode = LOCK_EX if exclusive else LOCK_SH
                if not blocking:
                    mode |= LOCK_NB
                msvcrt.locking(file_handle.fileno(), mode, 1)
            else:
                # Unix locking
                mode = LOCK_EX if exclusive else LOCK_SH
                if not blocking:
                    mode |= LOCK_NB
                fcntl.flock(file_handle.fileno(), mode)
            return True
        except (IOError, OSError):
            return False

    def _release_lock(self, file_handle) -> None:
        """Release a file lock."""
        try:
            if sys.platform == "win32":
                msvcrt.locking(file_handle.fileno(), 0, 1)  # Unlock
            else:
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
        except (IOError, OSError):
            pass  # Ignore errors on release

    def _atomic_write(self, file_path: Path, data: Dict[str, Any]) -> bool:
        """
        Atomically write session data to file with locking and secure permissions.

        Args:
            file_path: Target file path
            data: Data to write

        Returns:
            True if successful, False otherwise
        """
        temp_file = file_path.with_suffix(".tmp")
        lock_file = file_path.with_suffix(".lock")

        # Set restrictive umask before creating files (Unix only)
        old_umask = None
        if sys.platform != "win32":
            old_umask = os.umask(0o077)

        try:
            # Write to temporary file first
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk

            # Set secure permissions on temp file
            self._secure_file(temp_file)

            # Acquire exclusive lock on lock file
            lock_acquired = False
            start_time = time.time()

            while not lock_acquired and (time.time() - start_time) < self._lock_timeout:
                try:
                    with open(lock_file, "w") as lock_f:
                        if self._acquire_lock(lock_f, exclusive=True, blocking=False):
                            lock_acquired = True
                            # Atomic rename (works on both Unix and Windows)
                            temp_file.replace(file_path)
                            # Set secure permissions on final file
                            self._secure_file(file_path)
                            return True
                except (IOError, OSError):
                    pass  # Ignore errors and retry
                time.sleep(0.1)  # Brief wait before retry

            # If we couldn't acquire lock, still try atomic rename
            # (on some systems, rename is atomic even without explicit locking)
            if not lock_acquired:
                temp_file.replace(file_path)
                # Set secure permissions on final file
                self._secure_file(file_path)
                return True

        except Exception as e:
            logger.warning(f"Could not acquire lock for {file_path.name}: {e}")
            # Fallback: try direct write without locking
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self._secure_file(file_path)
                return True
            except Exception as write_error:
                logger.error(f"Failed to write session file: {write_error}")
                return False
        finally:
            # Restore umask
            if old_umask is not None:
                os.umask(old_umask)
            # Clean up temp file if it still exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            if lock_file.exists():
                try:
                    lock_file.unlink()
                except OSError:
                    pass

        return False

    def save_session(
        self,
        session_name: str,
        conversation_history: List[Dict[str, Any]],
        project_dir: str,
        model: str,
        permission_mode: str,
    ) -> bool:
        """
        Save a conversation session.

        Args:
            session_name: Name for the session
            conversation_history: Full conversation history
            project_dir: Project directory path
            model: Model name used
            permission_mode: Permission mode used

        Returns:
            True if saved successfully
        """
        try:
            # Sanitize session name
            safe_name = "".join(c for c in session_name if c.isalnum() or c in ("-", "_"))
            if not safe_name:
                safe_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            session_file = self.sessions_dir / f"{safe_name}.json"

            session_data = {
                "session_name": safe_name,
                "conversation_history": conversation_history,
                "project_dir": project_dir,
                "model": model,
                "permission_mode": permission_mode,
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
            }

            # Use atomic write with locking
            if self._atomic_write(session_file, session_data):
                console.print(f"[green]✓[/green] Session saved: {safe_name}")
                return True
            else:
                console.print(f"[red]Error saving session:[/red] Failed to write {safe_name}")
                return False

        except Exception as e:
            console.print(f"[red]Error saving session:[/red] {e}")
            return False

    def load_session(self, session_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a conversation session.

        Args:
            session_name: Name of the session to load

        Returns:
            Session data or None if not found
        """
        try:
            # Try with and without .json extension
            session_file = self.sessions_dir / session_name
            if not session_file.exists():
                session_file = self.sessions_dir / f"{session_name}.json"

            if not session_file.exists():
                console.print(f"[red]Session not found:[/red] {session_name}")
                return None

            # Try to acquire read lock (non-blocking)
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    # Try to acquire shared lock (non-blocking)
                    if self._acquire_lock(f, exclusive=False, blocking=False):
                        try:
                            session_data = json.load(f)
                            console.print(f"[green]✓[/green] Session loaded: {session_name}")
                            return session_data
                        finally:
                            self._release_lock(f)
                    else:
                        # If lock unavailable, read without lock (may get partial read)
                        # This is acceptable for read operations
                        session_data = json.load(f)
                        console.print(f"[green]✓[/green] Session loaded: {session_name}")
                        return session_data
            except json.JSONDecodeError as e:
                console.print(
                    f"[red]Error loading session:[/red] Invalid JSON in {session_name}: {e}"
                )
                return None

        except Exception as e:
            console.print(f"[red]Error loading session:[/red] {e}")
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all saved sessions.

        Returns:
            List of session metadata
        """
        sessions = []

        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append(
                        {
                            "name": session_file.stem,
                            "created_at": data.get("created_at", "Unknown"),
                            "model": data.get("model", "Unknown"),
                            "project_dir": data.get("project_dir", "Unknown"),
                        }
                    )
            except (json.JSONDecodeError, KeyError, IOError, OSError) as e:
                logger.debug(f"Failed to load session {session_file}: {e}")
                continue

        # Sort by creation time (newest first)
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions

    def show_sessions(self) -> None:
        """Display all sessions in a table"""
        sessions = self.list_sessions()

        if not sessions:
            console.print("[dim]No saved sessions[/dim]")
            return

        table = Table(title="📚 Saved Sessions")
        table.add_column("Name", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Model", style="yellow")
        table.add_column("Project", style="blue")

        for session in sessions:
            table.add_row(
                session["name"],
                (
                    session["created_at"][:19]
                    if len(session["created_at"]) > 19
                    else session["created_at"]
                ),
                session["model"],
                Path(session["project_dir"]).name,
            )

        console.print(table)

    def delete_session(self, session_name: str) -> bool:
        """
        Delete a saved session.

        Args:
            session_name: Name of session to delete

        Returns:
            True if deleted successfully
        """
        try:
            session_file = self.sessions_dir / f"{session_name}.json"
            if session_file.exists():
                session_file.unlink()
                console.print(f"[green]✓[/green] Session deleted: {session_name}")
                return True
            else:
                console.print(f"[red]Session not found:[/red] {session_name}")
                return False
        except Exception as e:
            console.print(f"[red]Error deleting session:[/red] {e}")
            return False
