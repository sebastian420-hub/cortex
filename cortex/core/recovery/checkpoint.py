"""Checkpoint management for session recovery."""

import json
import gzip
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, NamedTuple
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """A conversation checkpoint for recovery purposes."""

    id: str
    session_id: str
    timestamp: datetime
    message_count: int
    conversation_hash: str
    health_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[Path] = None

    @property
    def age_seconds(self) -> float:
        """Get age of checkpoint in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()

    @property
    def is_recent(self) -> bool:
        """Check if checkpoint is recent (< 5 minutes)."""
        return self.age_seconds < 300

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "message_count": self.message_count,
            "conversation_hash": self.conversation_hash,
            "health_score": self.health_score,
            "metadata": self.metadata,
            "file_path": str(self.file_path) if self.file_path else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message_count=data["message_count"],
            conversation_hash=data["conversation_hash"],
            health_score=data.get("health_score", 1.0),
            metadata=data.get("metadata", {}),
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
        )


class CheckpointManager:
    """
    Manages conversation checkpoints for session recovery.

    Provides automatic checkpointing, manual checkpoints, and recovery operations.
    """

    def __init__(
        self,
        checkpoint_dir: Path,
        max_checkpoints: int = 10,
        auto_checkpoint_interval: int = 50,  # messages
        compression_enabled: bool = True,
        retention_days: int = 7,
    ):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoints
            max_checkpoints: Maximum checkpoints to keep per session
            auto_checkpoint_interval: Message interval for auto-checkpoints
            compression_enabled: Whether to compress checkpoint files
            retention_days: How long to keep checkpoints (days)
        """
        self.checkpoint_dir = checkpoint_dir
        self.max_checkpoints = max_checkpoints
        self.auto_checkpoint_interval = auto_checkpoint_interval
        self.compression_enabled = compression_enabled
        self.retention_days = retention_days

        # Ensure checkpoint directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of checkpoints
        self._checkpoint_cache: Dict[str, List[Checkpoint]] = {}
        self._session_message_counts: Dict[str, int] = {}

    def should_checkpoint(self, session_id: str, current_message_count: int) -> bool:
        """
        Check if a checkpoint should be created based on message count.

        Args:
            session_id: Session identifier
            current_message_count: Current number of messages

        Returns:
            True if checkpoint should be created
        """
        last_count = self._session_message_counts.get(session_id, 0)
        if current_message_count - last_count >= self.auto_checkpoint_interval:
            return True
        return False

    def create_checkpoint(
        self,
        session_id: str,
        conversation_history: List[Dict[str, Any]],
        health_score: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Checkpoint:
        """
        Create a new checkpoint of the conversation.

        Args:
            session_id: Session identifier
            conversation_history: Current conversation history
            health_score: Health score of the conversation (0-1)
            metadata: Additional metadata to store
            force: Force creation even if not at interval

        Returns:
            Created checkpoint
        """
        # Update message count tracking
        message_count = len(conversation_history)
        self._session_message_counts[session_id] = message_count

        # Generate conversation hash for change detection
        conversation_hash = self._hash_conversation(conversation_history)

        # Check if we need to create checkpoint
        if not force and not self.should_checkpoint(session_id, message_count):
            # Return existing checkpoint if one exists with same hash
            existing = self._find_checkpoint_by_hash(session_id, conversation_hash)
            if existing:
                return existing

        # Generate checkpoint ID
        timestamp = datetime.now()
        checkpoint_id = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{message_count:04d}"

        # Create checkpoint metadata
        checkpoint_metadata = metadata or {}
        checkpoint_metadata.update(
            {
                "created_by": "auto" if not force else "manual",
                "compression": self.compression_enabled,
                "version": "1.0",
            }
        )

        # Create checkpoint object
        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=session_id,
            timestamp=timestamp,
            message_count=message_count,
            conversation_hash=conversation_hash,
            health_score=health_score,
            metadata=checkpoint_metadata,
        )

        # Save checkpoint to disk
        self._save_checkpoint(checkpoint, conversation_history)

        # Cache checkpoint
        if session_id not in self._checkpoint_cache:
            self._checkpoint_cache[session_id] = []
        self._checkpoint_cache[session_id].append(checkpoint)

        # Clean up old checkpoints
        self._cleanup_old_checkpoints(session_id)

        logger.info(
            f"Created checkpoint {checkpoint_id} for session {session_id} "
            f"({message_count} messages, health: {health_score:.2f})"
        )

        return checkpoint

    def list_checkpoints(self, session_id: str) -> List[Checkpoint]:
        """
        List all checkpoints for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of checkpoints, sorted by timestamp (newest first)
        """
        checkpoints = self._checkpoint_cache.get(session_id, [])
        if not checkpoints:
            # Load from disk if not cached
            checkpoints = self._load_checkpoints(session_id)
            self._checkpoint_cache[session_id] = checkpoints

        # Sort by timestamp descending
        return sorted(checkpoints, key=lambda x: x.timestamp, reverse=True)

    def get_checkpoint(self, session_id: str, checkpoint_id: str) -> Optional[Checkpoint]:
        """
        Get a specific checkpoint.

        Args:
            session_id: Session identifier
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint if found, None otherwise
        """
        checkpoints = self.list_checkpoints(session_id)
        for checkpoint in checkpoints:
            if checkpoint.id == checkpoint_id:
                return checkpoint
        return None

    def restore_checkpoint(self, checkpoint: Checkpoint) -> List[Dict[str, Any]]:
        """
        Restore conversation history from a checkpoint.

        Args:
            checkpoint: Checkpoint to restore from

        Returns:
            Conversation history from the checkpoint

        Raises:
            FileNotFoundError: If checkpoint file doesn't exist
            ValueError: If checkpoint data is corrupted
        """
        if not checkpoint.file_path or not checkpoint.file_path.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {checkpoint.file_path}")

        try:
            # Load checkpoint data
            conversation_history = self._load_checkpoint_data(checkpoint.file_path)

            logger.info(
                f"Restored checkpoint {checkpoint.id} " f"({len(conversation_history)} messages)"
            )

            return conversation_history

        except Exception as e:
            logger.error(f"Failed to restore checkpoint {checkpoint.id}: {e}")
            raise ValueError(f"Corrupted checkpoint data: {e}") from e

    def delete_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """
        Delete a checkpoint.

        Args:
            checkpoint: Checkpoint to delete

        Returns:
            True if deleted successfully
        """
        try:
            # Remove from cache
            if checkpoint.session_id in self._checkpoint_cache:
                self._checkpoint_cache[checkpoint.session_id] = [
                    cp
                    for cp in self._checkpoint_cache[checkpoint.session_id]
                    if cp.id != checkpoint.id
                ]

            # Remove file
            if checkpoint.file_path and checkpoint.file_path.exists():
                checkpoint.file_path.unlink()

            # Remove metadata file
            metadata_file = self._get_metadata_file_path(checkpoint.session_id, checkpoint.id)
            if metadata_file.exists():
                metadata_file.unlink()

            logger.info(f"Deleted checkpoint {checkpoint.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete checkpoint {checkpoint.id}: {e}")
            return False

    def get_latest_checkpoint(self, session_id: str) -> Optional[Checkpoint]:
        """
        Get the most recent checkpoint for a session.

        Args:
            session_id: Session identifier

        Returns:
            Latest checkpoint or None if no checkpoints exist
        """
        checkpoints = self.list_checkpoints(session_id)
        return checkpoints[0] if checkpoints else None

    def cleanup_expired_checkpoints(self) -> int:
        """
        Clean up checkpoints older than retention period.

        Returns:
            Number of checkpoints deleted
        """
        deleted_count = 0
        cutoff_time = datetime.now().timestamp() - (self.retention_days * 24 * 60 * 60)

        # Check all session directories
        for session_dir in self.checkpoint_dir.iterdir():
            if not session_dir.is_dir():
                continue

            session_id = session_dir.name
            checkpoints = self.list_checkpoints(session_id)

            for checkpoint in checkpoints:
                if checkpoint.timestamp.timestamp() < cutoff_time:
                    if self.delete_checkpoint(checkpoint):
                        deleted_count += 1

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired checkpoints")

        return deleted_count

    def _save_checkpoint(
        self, checkpoint: Checkpoint, conversation_history: List[Dict[str, Any]]
    ) -> None:
        """Save checkpoint data to disk."""
        session_dir = self.checkpoint_dir / checkpoint.session_id
        session_dir.mkdir(exist_ok=True)

        # Create filename
        filename = f"{checkpoint.id}.json"
        if self.compression_enabled:
            filename += ".gz"

        file_path = session_dir / filename
        checkpoint.file_path = file_path

        # Prepare checkpoint data
        checkpoint_data = {
            "checkpoint": checkpoint.to_dict(),
            "conversation": conversation_history,
        }

        # Save with or without compression
        try:
            if self.compression_enabled:
                with gzip.open(file_path, "wt", encoding="utf-8") as f:
                    json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

            # Save metadata separately for quick loading
            self._save_checkpoint_metadata(checkpoint)

        except Exception as e:
            logger.error(f"Failed to save checkpoint {checkpoint.id}: {e}")
            raise

    def _load_checkpoint_data(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load checkpoint data from disk."""
        try:
            if file_path.suffix == ".gz":
                with gzip.open(file_path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            return data["conversation"]

        except Exception as e:
            logger.error(f"Failed to load checkpoint data from {file_path}: {e}")
            raise

    def _load_checkpoints(self, session_id: str) -> List[Checkpoint]:
        """Load checkpoints for a session from disk."""
        session_dir = self.checkpoint_dir / session_id
        if not session_dir.exists():
            return []

        checkpoints = []

        # Load from metadata files (faster than parsing full checkpoint files)
        for metadata_file in session_dir.glob("*.meta.json"):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    checkpoint_data = json.load(f)
                    checkpoint = Checkpoint.from_dict(checkpoint_data)

                    # Reconstruct file path
                    checkpoint_id = checkpoint.id
                    filename = f"{checkpoint_id}.json"
                    if self.compression_enabled:
                        filename += ".gz"
                    checkpoint.file_path = session_dir / filename

                    checkpoints.append(checkpoint)

            except Exception as e:
                logger.warning(f"Failed to load checkpoint metadata from {metadata_file}: {e}")

        return checkpoints

    def _save_checkpoint_metadata(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint metadata for quick loading."""
        metadata_file = self._get_metadata_file_path(checkpoint.session_id, checkpoint.id)

        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save checkpoint metadata for {checkpoint.id}: {e}")

    def _get_metadata_file_path(self, session_id: str, checkpoint_id: str) -> Path:
        """Get path for checkpoint metadata file."""
        session_dir = self.checkpoint_dir / session_id
        return session_dir / f"{checkpoint_id}.meta.json"

    def _cleanup_old_checkpoints(self, session_id: str) -> None:
        """Clean up old checkpoints to stay within max_checkpoints limit."""
        checkpoints = self.list_checkpoints(session_id)

        if len(checkpoints) <= self.max_checkpoints:
            return

        # Sort by timestamp (oldest first)
        checkpoints.sort(key=lambda x: x.timestamp)

        # Delete oldest checkpoints
        to_delete = checkpoints[: len(checkpoints) - self.max_checkpoints]

        for checkpoint in to_delete:
            self.delete_checkpoint(checkpoint)

        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} old checkpoints for session {session_id}")

    def _find_checkpoint_by_hash(
        self, session_id: str, conversation_hash: str
    ) -> Optional[Checkpoint]:
        """Find existing checkpoint with matching conversation hash."""
        checkpoints = self.list_checkpoints(session_id)
        for checkpoint in checkpoints:
            if checkpoint.conversation_hash == conversation_hash:
                return checkpoint
        return None

    def _hash_conversation(self, conversation_history: List[Dict[str, Any]]) -> str:
        """Generate hash of conversation for change detection."""
        # Create a normalized representation for hashing
        normalized = []
        for msg in conversation_history:
            # Include key fields but exclude timestamps and IDs that might vary
            msg_copy = {
                "role": msg.get("role"),
                "content": msg.get("content"),
                "tool_calls": msg.get("tool_calls"),
                "tool_call_id": msg.get("tool_call_id"),
            }
            normalized.append(msg_copy)

        # Hash the normalized conversation
        conversation_str = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(conversation_str.encode("utf-8")).hexdigest()[:16]  # Short hash
