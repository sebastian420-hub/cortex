"""A task's own git worktree and branch.

An unattended run must not touch the checkout you are working in, and must not leave a mess when
it fails. So each task gets a new branch checked out in a separate directory (a git worktree, made
from the committed state of the base). Whatever the agent does happens there. When the task
succeeds the directory is removed and the branch, with its commit, stays; when it fails both go.
"""

import os
import re
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Set

# Used for the commit when git has no identity of its own (a fresh scheduled-job machine)
FALLBACK_IDENTITY = ("Cortex", "cortex@localhost")

# What running a project's tests leaves behind, and Cortex's own working files. These are not part
# of the work, so they are never committed, whether or not the repository ignores them.
NOT_COMMITTED = (
    ".cortex/**",
    "**/__pycache__/**",
    "**/*.pyc",
    ".pytest_cache/**",
    ".mypy_cache/**",
)


class WorkspaceError(RuntimeError):
    """The workspace could not be set up, or a git command it needs failed."""


def _slug(text: str, limit: int = 30) -> str:
    """The first words of ``text`` as a branch-name fragment, cut between words, not in one."""
    slug = ""
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        candidate = f"{slug}-{word}" if slug else word
        if len(candidate) > limit:
            break
        slug = candidate
    return slug or re.sub(r"[^a-z0-9]+", "", text.lower())[:limit] or "task"


def _subcommand(args: Sequence[str]) -> str:
    """The git subcommand in an argument list, skipping leading ``-c key=value`` settings."""
    remaining = iter(args)
    for arg in remaining:
        if arg == "-c":
            next(remaining, None)
        else:
            return arg
    return ""


def _git(cwd: Path, *args: str, check: bool = True) -> "subprocess.CompletedProcess[str]":
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        errors="replace",
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise WorkspaceError(f"git {_subcommand(args)} failed: {detail}")
    return result


class Workspace:
    """One task's worktree. Make it with :meth:`create`; always finish with :meth:`remove`."""

    def __init__(self, repo: Path, path: Path, parent: Path, branch: str, base: str):
        self.repo = repo
        self.path = path
        self.branch = branch
        self.base = base
        self._parent = parent
        self._removed = False

    # ---- creating ----------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        project_dir: Path,
        task: str = "task",
        base_ref: str = "HEAD",
        branch: Optional[str] = None,
    ) -> "Workspace":
        """A new branch of the repository containing ``project_dir``, checked out in a new
        directory. The branch starts from the committed ``base_ref``; uncommitted changes in your
        own checkout are not part of it."""
        project_dir = Path(project_dir)
        probe = _git(project_dir, "rev-parse", "--show-toplevel", check=False)
        if probe.returncode != 0:
            raise WorkspaceError(
                f"{project_dir} is not inside a git repository. Headless runs work on a branch, "
                "so the project needs to be one (git init, then commit something)."
            )
        repo = Path(probe.stdout.strip())

        resolved = _git(
            repo, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}", check=False
        )
        if resolved.returncode != 0:
            if base_ref == "HEAD":
                raise WorkspaceError(
                    f"{repo} has no commits yet. Make a commit first: a task starts from one."
                )
            raise WorkspaceError(f"The base '{base_ref}' is not a commit in {repo}.")
        base = resolved.stdout.strip()

        branch = branch or f"cortex/{_slug(task)}-{secrets.token_hex(3)}"
        exists = _git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
        if exists.returncode == 0:
            raise WorkspaceError(f"The branch {branch} already exists; it is not overwritten.")

        parent = Path(tempfile.mkdtemp(prefix="cortex-run-"))
        path = parent / repo.name  # the agent sees the project's real name
        try:
            _git(repo, "worktree", "add", "-q", "-b", branch, str(path), base)
        except WorkspaceError:
            shutil.rmtree(parent, ignore_errors=True)
            raise
        return cls(repo, path, parent, branch, base)

    # ---- looking ----------------------------------------------------------------------

    def branches(self) -> Set[str]:
        """The repository's local branches. Branches are shared by every worktree, so this is how
        a run notices one that appeared while it ran."""
        out = _git(self.repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout
        return {name for name in out.splitlines() if name}

    def settle(self) -> None:
        """Put the worktree back on the task branch, with the state it is in.

        The agent can leave the branch (``git checkout -b ...`` through the shell, or a detached
        HEAD). What was verified is the state of the worktree, so the work is moved onto the task
        branch, commits and uncommitted changes alike, rather than lost or filed somewhere else.
        """
        current = _git(self.path, "symbolic-ref", "-q", "--short", "HEAD", check=False).stdout
        if current.strip() != self.branch:
            _git(self.path, "checkout", "-q", "-B", self.branch)

    def head(self) -> str:
        return _git(self.path, "rev-parse", "HEAD").stdout.strip()

    def files_changed(self) -> List[str]:
        """Files that differ between the base and what is staged or committed on the branch.

        Renames are listed as a deletion and an addition, so both paths are seen.
        """
        out = _git(
            self.path, "diff", "--cached", "--name-only", "--no-renames", "-z", self.base
        ).stdout
        return [name for name in out.split("\0") if name]

    def has_changes(self) -> bool:
        """Whether the branch differs from the base (stage or commit the leftovers first to
        include them)."""
        return bool(self.files_changed())

    def diff_stat(self) -> str:
        return _git(
            self.path, "diff", "--cached", "--stat", "--no-renames", self.base
        ).stdout.strip()

    # ---- committing -------------------------------------------------------------------

    def _identity_args(self) -> Sequence[str]:
        """``-c`` settings that give the commit an author when git has none."""
        args: List[str] = []
        name, email = FALLBACK_IDENTITY
        for key, fallback in (("user.name", name), ("user.email", email)):
            configured = _git(self.path, "config", key, check=False).stdout.strip()
            if not configured:
                args += ["-c", f"{key}={fallback}"]
        return args

    def stage(self) -> None:
        """Stage everything the agent left, except the files in :data:`NOT_COMMITTED`."""
        excludes = [f":(exclude,glob){pattern}" for pattern in NOT_COMMITTED]
        _git(self.path, "add", "-A", "--", ".", *excludes)

    def commit(self, message: str) -> Optional[str]:
        """Commit what is staged. Returns the new commit, or None when nothing was staged."""
        if _git(self.path, "diff", "--cached", "--quiet", check=False).returncode == 0:
            return None
        # The verify command is the gate here, not the repository's commit hooks, which may need
        # tools or a terminal an unattended run does not have
        _git(
            self.path,
            *self._identity_args(),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            message,
        )
        return self.head()

    def commit_all(self, message: str) -> Optional[str]:
        """Stage and commit everything the agent left; None when there was nothing to commit."""
        self.stage()
        return self.commit(message)

    # ---- cleaning up ------------------------------------------------------------------

    def remove(self, keep_branch: bool) -> None:
        """Remove the directory, and the branch too unless ``keep_branch``. Safe to repeat."""
        if self._removed:
            return
        self._removed = True

        removed = _git(self.repo, "worktree", "remove", "--force", str(self.path), check=False)
        if removed.returncode != 0:
            shutil.rmtree(self.path, ignore_errors=True)
            _git(self.repo, "worktree", "prune", check=False)
        shutil.rmtree(self._parent, ignore_errors=True)

        if not keep_branch:
            _git(self.repo, "branch", "-D", self.branch, check=False)
