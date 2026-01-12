"""Session cleanup and retention management for Cortex"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CleanupStats:
    """Statistics from cleanup operation."""

    sessions_removed: int = 0
    bytes_freed: int = 0
    sessions_kept: int = 0
    errors: List[str] = field(default_factory=list)

    def merge(self, other: "CleanupStats") -> "CleanupStats":
        """Merge another CleanupStats into this one."""
        return CleanupStats(
            sessions_removed=self.sessions_removed + other.sessions_removed,
            bytes_freed=self.bytes_freed + other.bytes_freed,
            sessions_kept=other.sessions_kept,  # Use the latest kept count
            errors=self.errors + other.errors,
        )


class SessionCleanupManager:
    """
    Manages session retention and cleanup.

    Supports cleanup by:
    - Age: Remove sessions older than max_age_days
    - Count: Keep only max_count sessions (oldest removed first)
    - Size: Keep total storage under max_total_size_mb
    """

    def __init__(
        self,
        sessions_dir: Path,
        max_age_days: int = 30,
        max_count: int = 100,
        max_total_size_mb: int = 500,
    ):
        """
        Initialize cleanup manager.

        Args:
            sessions_dir: Directory containing session files
            max_age_days: Maximum session age in days
            max_count: Maximum number of sessions to keep
            max_total_size_mb: Maximum total storage size in MB
        """
        self.sessions_dir = Path(sessions_dir)
        self.max_age_days = max_age_days
        self.max_count = max_count
        self.max_total_size_bytes = max_total_size_mb * 1024 * 1024

    def get_session_info(self, session_file: Path) -> Optional[Dict[str, Any]]:
        """
        Get session metadata without loading full content.

        Args:
            session_file: Path to session JSON file

        Returns:
            Session info dict or None if file can't be read
        """
        try:
            stat = session_file.stat()
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "path": session_file,
                "name": session_file.stem,
                "size_bytes": stat.st_size,
                "modified_time": datetime.fromtimestamp(stat.st_mtime),
                "created_at": data.get("created_at"),
                "model": data.get("model"),
                "message_count": len(data.get("conversation_history", [])),
            }
        except Exception as e:
            logger.warning(f"Error reading session {session_file}: {e}")
            return None

    def list_sessions_by_age(self) -> List[Dict[str, Any]]:
        """
        List all sessions sorted by age (oldest first).

        Returns:
            List of session info dicts sorted by modified time
        """
        if not self.sessions_dir.exists():
            return []

        sessions = []
        for f in self.sessions_dir.glob("*.json"):
            info = self.get_session_info(f)
            if info:
                sessions.append(info)

        # Sort by modified time (oldest first)
        sessions.sort(key=lambda x: x["modified_time"])
        return sessions

    def cleanup_by_age(self) -> CleanupStats:
        """
        Remove sessions older than max_age_days.

        Returns:
            CleanupStats with results
        """
        stats = CleanupStats()
        cutoff = datetime.now() - timedelta(days=self.max_age_days)

        for session in self.list_sessions_by_age():
            if session["modified_time"] < cutoff:
                try:
                    session["path"].unlink()
                    stats.sessions_removed += 1
                    stats.bytes_freed += session["size_bytes"]
                    logger.debug(f"Removed old session: {session['name']}")
                except Exception as e:
                    stats.errors.append(f"Failed to remove {session['name']}: {e}")
            else:
                stats.sessions_kept += 1

        return stats

    def cleanup_by_count(self) -> CleanupStats:
        """
        Remove oldest sessions if count exceeds max_count.

        Returns:
            CleanupStats with results
        """
        stats = CleanupStats()
        sessions = self.list_sessions_by_age()

        if len(sessions) <= self.max_count:
            stats.sessions_kept = len(sessions)
            return stats

        # Remove oldest sessions
        to_remove = len(sessions) - self.max_count
        for session in sessions[:to_remove]:
            try:
                session["path"].unlink()
                stats.sessions_removed += 1
                stats.bytes_freed += session["size_bytes"]
                logger.debug(f"Removed excess session: {session['name']}")
            except Exception as e:
                stats.errors.append(f"Failed to remove {session['name']}: {e}")

        stats.sessions_kept = self.max_count
        return stats

    def cleanup_by_size(self) -> CleanupStats:
        """
        Remove oldest sessions if total size exceeds limit.

        Returns:
            CleanupStats with results
        """
        stats = CleanupStats()
        sessions = self.list_sessions_by_age()

        total_size = sum(s["size_bytes"] for s in sessions)

        if total_size <= self.max_total_size_bytes:
            stats.sessions_kept = len(sessions)
            return stats

        # Remove oldest until under limit
        for session in sessions:
            if total_size <= self.max_total_size_bytes:
                break
            try:
                session["path"].unlink()
                stats.sessions_removed += 1
                stats.bytes_freed += session["size_bytes"]
                total_size -= session["size_bytes"]
                logger.debug(f"Removed large session: {session['name']}")
            except Exception as e:
                stats.errors.append(f"Failed to remove {session['name']}: {e}")

        stats.sessions_kept = len(sessions) - stats.sessions_removed
        return stats

    def run_full_cleanup(self) -> CleanupStats:
        """
        Run all cleanup strategies in order: age, count, size.

        Returns:
            Combined CleanupStats from all strategies
        """
        total_stats = CleanupStats()

        # Run each strategy in order
        for cleanup_method in [
            self.cleanup_by_age,
            self.cleanup_by_count,
            self.cleanup_by_size,
        ]:
            stats = cleanup_method()
            total_stats = total_stats.merge(stats)

        # Count remaining sessions
        total_stats.sessions_kept = len(list(self.sessions_dir.glob("*.json")))

        if total_stats.sessions_removed > 0:
            logger.info(
                f"Cleanup complete: removed {total_stats.sessions_removed} sessions, "
                f"freed {total_stats.bytes_freed // 1024}KB"
            )

        return total_stats

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get current storage statistics.

        Returns:
            Dict with storage metrics and limits
        """
        sessions = self.list_sessions_by_age()
        total_size = sum(s["size_bytes"] for s in sessions)

        oldest = sessions[0] if sessions else None
        newest = sessions[-1] if sessions else None

        return {
            "session_count": len(sessions),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_session": oldest["name"] if oldest else None,
            "oldest_session_date": oldest["modified_time"].isoformat() if oldest else None,
            "newest_session": newest["name"] if newest else None,
            "newest_session_date": newest["modified_time"].isoformat() if newest else None,
            "limit_count": self.max_count,
            "limit_size_mb": self.max_total_size_bytes / (1024 * 1024),
            "limit_age_days": self.max_age_days,
            "usage_percent_count": (
                round((len(sessions) / self.max_count) * 100, 1) if self.max_count > 0 else 0
            ),
            "usage_percent_size": (
                round((total_size / self.max_total_size_bytes) * 100, 1)
                if self.max_total_size_bytes > 0
                else 0
            ),
        }


def create_cleanup_manager_from_config(
    sessions_dir: Path, config: Dict[str, Any]
) -> SessionCleanupManager:
    """
    Create a SessionCleanupManager from configuration dict.

    Args:
        sessions_dir: Directory containing session files
        config: session_retention configuration dict

    Returns:
        Configured SessionCleanupManager instance
    """
    return SessionCleanupManager(
        sessions_dir=sessions_dir,
        max_age_days=config.get("max_age_days", 30),
        max_count=config.get("max_count", 100),
        max_total_size_mb=config.get("max_total_size_mb", 500),
    )
