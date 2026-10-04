"""Git checkpoints: undo for everything a request did to the project, shell commands included.

The per-file transaction backups (core/transaction.py) only see changes made through Cortex's
own file tools. A shell command can delete a directory or rewrite a hundred files and none of
that is recorded. A checkpoint is a snapshot of the whole working tree, taken before the first
thing in a request that could change it, so ``/undo`` can put the project back.

How it stays out of the user's way:

- The snapshot is a commit stored under a private ref (``refs/cortex/<session>/<n>``), built
  with a *temporary* index. HEAD, branches, the real index, stashes and the working tree are not
  touched, so ``git status`` looks the same before and after.
- Restoring changes only the files that differ from the snapshot. The state just before a
  restore is saved on a second stack, so ``/undo`` can be undone with ``/redo``. Each ``/undo``
  uses up one checkpoint, so pressing it again steps back one more request.

What it does not cover (by design, and said so to the user):

- Files that git ignores (build output, virtual environments, logs). They are not in the snapshot.
- Branch positions. If a command moved HEAD (commit, reset), files are restored but the branch is
  not; the result says so, and ``git reflog`` has the old position.
- Repositories that use git filters (LFS, eol conversion): the round trip goes through them.
"""

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

REF_ROOT = "refs/cortex"  # checkpoints: what /undo restores
REDO_ROOT = "refs/cortex-redo"  # states saved just before an undo: what /redo restores
_IDENTITY = {
    "GIT_AUTHOR_NAME": "Cortex",
    "GIT_AUTHOR_EMAIL": "cortex@localhost",
    "GIT_COMMITTER_NAME": "Cortex",
    "GIT_COMMITTER_EMAIL": "cortex@localhost",
}
_PATHS_PER_COMMAND = 200


@dataclass
class Snapshot:
    ref: str
    commit: str
    head: Optional[str]  # where HEAD pointed when the snapshot was taken
    label: str


@dataclass
class RestoreResult:
    snapshot: Snapshot
    restored: List[str] = field(default_factory=list)  # changed or deleted since: put back
    removed: List[str] = field(default_factory=list)  # created since: deleted
    failed: List[str] = field(default_factory=list)
    head_at_snapshot: Optional[str] = None
    head_moved: bool = False
    safety: Optional[Snapshot] = None  # the state just before the restore (the other stack)


class GitCheckpointStore:
    """Snapshots and restores the working tree of the git repository containing ``project_dir``."""

    def __init__(
        self,
        project_dir: Path,
        session_id: str,
        keep: int = 20,
        timeout: float = 60.0,
        stale_days: Optional[float] = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.session_id = session_id
        # When set, snapshots left by other sessions older than this are deleted once, with the
        # first snapshot (so a session that never changes anything does no git work at all)
        self._stale_days = stale_days
        self.keep = max(int(keep), 2)  # a restore itself adds a snapshot
        self.timeout = timeout
        self._lock = threading.RLock()
        self._toplevel: Optional[Path] = None
        self._prefix = ""
        self._available: Optional[bool] = None

    # ----------------------------------------------------------------------------------
    # git plumbing
    # ----------------------------------------------------------------------------------

    def _git(
        self,
        *args: str,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Path] = None,
        check: bool = True,
    ) -> "subprocess.CompletedProcess[bytes]":
        command = [
            "git",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.safecrlf=false",
            "--literal-pathspecs",
            *args,
        ]
        full_env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C", **(env or {})}
        return subprocess.run(
            command,
            cwd=str(cwd or self._toplevel or self.project_dir),
            env=full_env,
            capture_output=True,
            check=check,
            timeout=self.timeout,
        )

    def _text(self, *args: str, **kwargs) -> str:
        return os.fsdecode(self._git(*args, **kwargs).stdout).strip()

    def available(self) -> bool:
        """True when ``project_dir`` is inside a git work tree and git can be run."""
        with self._lock:
            if self._available is None:
                try:
                    inside = self._text("rev-parse", "--is-inside-work-tree", cwd=self.project_dir)
                    if inside != "true":
                        raise RuntimeError("not inside a work tree")
                    self._toplevel = Path(
                        self._text("rev-parse", "--show-toplevel", cwd=self.project_dir)
                    ).resolve()
                    self._prefix = self._text("rev-parse", "--show-prefix", cwd=self.project_dir)
                    self._available = True
                except (OSError, RuntimeError, subprocess.SubprocessError):
                    self._available = False
            return self._available

    @property
    def _pathspec(self) -> str:
        return self._prefix.rstrip("/") or "."

    def _head(self) -> Optional[str]:
        result = self._git("rev-parse", "-q", "--verify", "HEAD", check=False)
        return os.fsdecode(result.stdout).strip() or None if result.returncode == 0 else None

    def _working_tree(self) -> str:
        """A tree object for the project as it is now (tracked and untracked, not ignored).

        Built in a temporary copy of the index, so the user's own index is never written. Seeding
        the copy from the real index lets git skip hashing files that have not changed.
        """
        with tempfile.TemporaryDirectory(prefix="cortex-index-") as tmp:
            index = Path(tmp) / "index"
            real = Path(self._text("rev-parse", "--git-path", "index"))
            if not real.is_absolute():
                real = self._toplevel / real
            if real.exists():
                shutil.copyfile(real, index)
            env = {"GIT_INDEX_FILE": str(index)}
            self._git("add", "-A", "--", self._pathspec, env=env)
            return self._text("write-tree", env=env)

    def _namespace(self, root: str) -> str:
        return f"{root}/{self.session_id}"

    def _refs(self, root: str = REF_ROOT) -> List[str]:
        out = self._text("for-each-ref", "--format=%(refname)", f"{self._namespace(root)}/")
        return sorted(line for line in out.splitlines() if line)

    def _make_snapshot(self, tree: str, label: str, root: str = REF_ROOT) -> Snapshot:
        head = self._head()
        parent = ["-p", head] if head else []
        message = f"cortex checkpoint: {label}\n\nhead: {head or 'none'}\n"
        commit = self._text("commit-tree", tree, *parent, "-m", message, env=_IDENTITY)
        refs = self._refs(root)
        sequence = int(refs[-1].rsplit("/", 1)[1]) + 1 if refs else 1
        ref = f"{self._namespace(root)}/{sequence:06d}"
        self._git("update-ref", ref, commit)
        self._prune(root)
        return Snapshot(ref=ref, commit=commit, head=head, label=label)

    def _prune(self, root: str) -> None:
        refs = self._refs(root)
        for ref in refs[: max(len(refs) - self.keep, 0)]:
            self._git("update-ref", "-d", ref, check=False)

    def _newest(self, root: str) -> Optional[Snapshot]:
        refs = self._refs(root)
        if not refs:
            return None
        ref = refs[-1]
        commit = self._text("rev-parse", ref)
        lines = self._text("log", "-1", "--format=%B", commit).splitlines()
        label = lines[0].split(":", 1)[1].strip() if lines and ":" in lines[0] else ""
        head = None
        for line in lines:
            if line.startswith("head: ") and line[6:] != "none":
                head = line[6:]
        return Snapshot(ref=ref, commit=commit, head=head, label=label)

    # ----------------------------------------------------------------------------------
    # public API
    # ----------------------------------------------------------------------------------

    def snapshot(self, label: str) -> Optional[Snapshot]:
        """Save the project as it is now. Returns None, never raises, if that is not possible."""
        with self._lock:
            if not self.available():
                return None
            if self._stale_days is not None:
                days, self._stale_days = self._stale_days, None
                try:
                    self.sweep_stale(days)
                except (OSError, subprocess.SubprocessError) as e:
                    logger.debug(f"Checkpoint sweep skipped: {e}")
            try:
                return self._make_snapshot(self._working_tree(), label.strip()[:100] or "request")
            except (OSError, subprocess.SubprocessError) as e:
                logger.warning(f"Could not take a git checkpoint: {e}")
                return None

    def latest(self) -> Optional[Snapshot]:
        """The checkpoint ``/undo`` would restore next, if any."""
        with self._lock:
            return self._newest(REF_ROOT) if self.available() else None

    def latest_redo(self) -> Optional[Snapshot]:
        """The saved state ``/redo`` would restore next, if any."""
        with self._lock:
            return self._newest(REDO_ROOT) if self.available() else None

    def clear(self) -> None:
        """Delete this session's snapshots (called when the session ends)."""
        with self._lock:
            if not self.available():
                return
            for root in (REF_ROOT, REDO_ROOT):
                for ref in self._refs(root):
                    self._git("update-ref", "-d", ref, check=False)

    def sweep_stale(self, max_age_days: float = 7.0, now: Optional[float] = None) -> int:
        """Delete snapshots of other sessions older than ``max_age_days``; returns how many.

        A session that crashed never cleared its snapshots. They hold copies of untracked files,
        so they are not left in the repository for ever.
        """
        with self._lock:
            if not self.available():
                return 0
            cutoff = (time.time() if now is None else now) - max_age_days * 86400
            removed = 0
            for root in (REF_ROOT, REDO_ROOT):
                listing = self._text(
                    "for-each-ref", "--format=%(refname) %(committerdate:unix)", f"{root}/"
                )
                for line in listing.splitlines():
                    ref, _, stamp = line.rpartition(" ")
                    own = ref.startswith(self._namespace(root) + "/")
                    if own or not ref or not stamp.isdigit() or int(stamp) >= cutoff:
                        continue
                    self._git("update-ref", "-d", ref, check=False)
                    removed += 1
            return removed

    def restore(self, snapshot: Optional[Snapshot] = None) -> RestoreResult:
        """Undo: put the project back to ``snapshot`` (default: the latest checkpoint).

        Only files that differ are touched. The state just before is saved for ``redo()`` (and
        returned as ``result.safety``). Restoring the default checkpoint uses it up, so the next
        call goes back one more request.
        """
        with self._lock:
            consume = snapshot is None
            target = snapshot or self.latest()
            if target is None:
                raise LookupError(
                    "No checkpoint in this session yet: nothing has run that could change files."
                )
            result = self._apply(target, save_to=REDO_ROOT, label="before undo")
            if consume:
                self._git("update-ref", "-d", target.ref, check=False)
            return result

    def redo(self) -> RestoreResult:
        """Redo: reapply the state that the last ``restore()`` took away."""
        with self._lock:
            target = self.latest_redo()
            if target is None:
                raise LookupError("Nothing to redo: no undo has been made in this session.")
            # whatever is there now becomes an undo checkpoint, so new work is never lost
            result = self._apply(target, save_to=REF_ROOT, label="before redo")
            self._git("update-ref", "-d", target.ref, check=False)
            return result

    def _apply(self, target: Snapshot, save_to: str, label: str) -> RestoreResult:
        current_tree = self._working_tree()
        safety = self._make_snapshot(current_tree, label, root=save_to)
        result = RestoreResult(
            snapshot=target,
            head_at_snapshot=target.head,
            head_moved=target.head != self._head(),
            safety=safety,
        )

        tokens = os.fsdecode(
            self._git(
                "diff-tree",
                "-r",
                "-z",
                "--name-status",
                "--no-renames",
                target.commit,
                current_tree,
                "--",
                self._pathspec,
            ).stdout
        ).split("\0")
        to_restore: List[str] = []
        to_remove: List[str] = []
        for status, path in zip(tokens[0::2], tokens[1::2]):
            if status == "A":  # created since the snapshot
                to_remove.append(path)
            elif status:  # modified, deleted, or type-changed since
                to_restore.append(path)

        self._restore_paths(target, to_restore, result)
        self._remove_paths(to_remove, result)
        result.restored.sort()
        result.removed.sort()
        return result

    # ----------------------------------------------------------------------------------
    # applying a restore
    # ----------------------------------------------------------------------------------

    def _relative(self, path: str) -> str:
        return path[len(self._prefix) :] if self._prefix and path.startswith(self._prefix) else path

    def _restore_paths(self, target: Snapshot, paths: List[str], result: RestoreResult) -> None:
        for start in range(0, len(paths), _PATHS_PER_COMMAND):
            chunk = paths[start : start + _PATHS_PER_COMMAND]
            done = self._git(
                "restore", f"--source={target.commit}", "--worktree", "--", *chunk, check=False
            )
            if done.returncode == 0:
                result.restored.extend(self._relative(p) for p in chunk)
                continue
            for path in chunk:  # find out which one it was
                single = self._git(
                    "restore", f"--source={target.commit}", "--worktree", "--", path, check=False
                )
                (result.restored if single.returncode == 0 else result.failed).append(
                    self._relative(path)
                )

    def _remove_paths(self, paths: List[str], result: RestoreResult) -> None:
        for path in paths:
            full = self._toplevel / path
            try:
                if full.is_symlink() or full.is_file():
                    full.unlink()
                result.removed.append(self._relative(path))
            except OSError as e:
                logger.warning(f"Could not remove {full}: {e}")
                result.failed.append(self._relative(path))
                continue
            parent = full.parent
            while parent != self.project_dir and self.project_dir in parent.parents:
                try:
                    parent.rmdir()  # only succeeds when empty
                except OSError:
                    break
                parent = parent.parent
