"""A task runs in its own git worktree on its own branch, so the checkout you are working in is
never touched, and a failed task leaves nothing behind."""

import os
import subprocess

import pytest

from cortex.headless.workspace import Workspace, WorkspaceError

from tests.unit.headless.gitutil import GIT_ENV, git


def branches(repo):
    return set(git(repo, "branch", "--format=%(refname:short)").split())


def snapshot(repo):
    """What the user's own checkout looks like: branch, commit and files (without .git)."""
    files = {
        str(p.relative_to(repo)): p.read_bytes()
        for p in sorted(repo.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(repo).parts
    }
    return git(repo, "branch", "--show-current"), git(repo, "rev-parse", "HEAD"), files


# ---- creating -----------------------------------------------------------------------------


def test_the_task_gets_its_own_branch_and_directory(repo):
    workspace = Workspace.create(repo, task="fix the parser")

    try:
        assert workspace.path.is_dir() and workspace.path != repo
        assert (workspace.path / "a.py").read_text() == "def hello():\n    return 1\n"
        assert git(workspace.path, "branch", "--show-current") == workspace.branch
        assert workspace.branch.startswith("cortex/fix-the-parser-")
        assert workspace.base == git(repo, "rev-parse", "HEAD")
    finally:
        workspace.remove(keep_branch=False)


def test_your_checkout_is_not_touched(repo):
    before = snapshot(repo)

    workspace = Workspace.create(repo, task="t")
    (workspace.path / "a.py").write_text("changed\n")
    (workspace.path / "new.py").write_text("new\n")
    workspace.commit_all("work")
    workspace.remove(keep_branch=True)

    assert snapshot(repo) == before


def test_uncommitted_changes_in_your_checkout_are_not_part_of_the_task(repo):
    (repo / "a.py").write_text("uncommitted\n")

    workspace = Workspace.create(repo, task="t")
    try:
        assert (workspace.path / "a.py").read_text() == "def hello():\n    return 1\n"
    finally:
        workspace.remove(keep_branch=False)


def test_it_can_start_from_another_ref(repo):
    git(repo, "branch", "release")
    (repo / "later.py").write_text("x\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "later")

    workspace = Workspace.create(repo, task="t", base_ref="release")
    try:
        assert not (workspace.path / "later.py").exists()
        assert workspace.base == git(repo, "rev-parse", "release")
    finally:
        workspace.remove(keep_branch=False)


def test_an_explicit_branch_name_is_used(repo):
    workspace = Workspace.create(repo, task="t", branch="cortex/nightly-lint")
    try:
        assert workspace.branch == "cortex/nightly-lint"
    finally:
        workspace.remove(keep_branch=False)


def test_two_runs_of_the_same_task_get_different_branches(repo):
    first = Workspace.create(repo, task="same task")
    second = Workspace.create(repo, task="same task")
    try:
        assert first.branch != second.branch
        assert first.path != second.path
    finally:
        first.remove(keep_branch=False)
        second.remove(keep_branch=False)


def test_an_existing_branch_is_refused_not_overwritten(repo):
    git(repo, "branch", "cortex/taken")

    with pytest.raises(WorkspaceError, match="cortex/taken"):
        Workspace.create(repo, task="t", branch="cortex/taken")


def test_a_subdirectory_of_the_repository_is_fine(repo):
    workspace = Workspace.create(repo / "tests", task="t")
    try:
        assert (workspace.path / "a.py").exists()
    finally:
        workspace.remove(keep_branch=False)


def test_a_directory_that_is_not_a_repository_is_refused(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(WorkspaceError, match="git repository"):
        Workspace.create(plain, task="t")


def test_a_repository_without_commits_is_refused(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init", "-q")

    with pytest.raises(WorkspaceError, match="commit"):
        Workspace.create(empty, task="t")


def test_an_unknown_base_is_refused(repo):
    with pytest.raises(WorkspaceError, match="nope"):
        Workspace.create(repo, task="t", base_ref="nope")


# ---- committing ---------------------------------------------------------------------------


def test_everything_the_agent_left_is_committed(repo):
    workspace = Workspace.create(repo, task="t")
    try:
        (workspace.path / "a.py").write_text("def hello():\n    return 2\n")
        (workspace.path / "new.py").write_text("x = 1\n")
        (workspace.path / "tests" / "test_a.py").unlink()

        head = workspace.commit_all("cortex: change")

        assert head == git(workspace.path, "rev-parse", "HEAD")
        assert git(workspace.path, "status", "--porcelain") == ""
        assert set(workspace.files_changed()) == {"a.py", "new.py", "tests/test_a.py"}
        assert git(workspace.path, "log", "-1", "--format=%s") == "cortex: change"
    finally:
        workspace.remove(keep_branch=False)


def test_nothing_to_commit_gives_none(repo):
    workspace = Workspace.create(repo, task="t")
    try:
        assert workspace.commit_all("nothing") is None
        assert workspace.files_changed() == []
        assert workspace.has_changes() is False
    finally:
        workspace.remove(keep_branch=False)


def test_changes_the_agent_committed_itself_still_count(repo):
    workspace = Workspace.create(repo, task="t")
    try:
        (workspace.path / "mine.py").write_text("x\n")
        git(workspace.path, "add", ".")
        git(workspace.path, "commit", "-qm", "agent commit")

        assert workspace.has_changes() is True  # relative to the base, not the last commit
        assert workspace.files_changed() == ["mine.py"]
        assert workspace.commit_all("leftovers") is None  # nothing uncommitted remains
    finally:
        workspace.remove(keep_branch=False)


def test_junk_from_running_tests_is_not_committed(repo):
    workspace = Workspace.create(repo, task="t")
    try:
        (workspace.path / "real.py").write_text("x\n")
        (workspace.path / "__pycache__").mkdir()
        (workspace.path / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"\0")
        (workspace.path / "tests" / "__pycache__").mkdir()
        (workspace.path / "tests" / "__pycache__" / "t.pyc").write_bytes(b"\0")
        (workspace.path / ".pytest_cache").mkdir()
        (workspace.path / ".pytest_cache" / "v").write_text("1")
        (workspace.path / ".cortex").mkdir()
        (workspace.path / ".cortex" / "db").write_text("1")

        workspace.commit_all("t")

        assert workspace.files_changed() == ["real.py"]
    finally:
        workspace.remove(keep_branch=False)


def test_committing_works_without_a_configured_git_identity(repo):
    # the fixture removed every identity; a scheduled job on a fresh machine looks like this
    assert (
        subprocess.run(
            ["git", "config", "user.email"], cwd=repo, capture_output=True, env=os.environ
        ).stdout.strip()
        == b""
    )
    workspace = Workspace.create(repo, task="t")
    try:
        (workspace.path / "x.py").write_text("x\n")

        assert workspace.commit_all("work") is not None
    finally:
        workspace.remove(keep_branch=False)


def test_your_own_git_identity_is_used_when_there_is_one(repo, monkeypatch):
    for name, value in GIT_ENV.items():
        monkeypatch.setenv(name, value)
    workspace = Workspace.create(repo, task="t")
    try:
        (workspace.path / "x.py").write_text("x\n")
        workspace.commit_all("work")

        assert git(workspace.path, "log", "-1", "--format=%an") == "t"
    finally:
        workspace.remove(keep_branch=False)


def test_the_diff_summary_names_what_changed(repo):
    workspace = Workspace.create(repo, task="t")
    try:
        (workspace.path / "a.py").write_text("def hello():\n    return 2\n")
        workspace.commit_all("work")

        assert "a.py" in workspace.diff_stat()
    finally:
        workspace.remove(keep_branch=False)


# ---- cleaning up --------------------------------------------------------------------------


def test_discarding_leaves_nothing_behind(repo):
    before = branches(repo)
    workspace = Workspace.create(repo, task="t")
    (workspace.path / "x.py").write_text("x\n")
    workspace.commit_all("work")
    path = workspace.path

    workspace.remove(keep_branch=False)

    assert not path.exists()
    assert branches(repo) == before
    assert len(git(repo, "worktree", "list").splitlines()) == 1


def test_keeping_the_branch_removes_only_the_directory(repo):
    workspace = Workspace.create(repo, task="t")
    (workspace.path / "x.py").write_text("x\n")
    workspace.commit_all("work")
    path, branch = workspace.path, workspace.branch

    workspace.remove(keep_branch=True)

    assert not path.exists()
    assert branch in branches(repo)
    assert git(repo, "show", f"{branch}:x.py") == "x"


def test_removing_twice_is_harmless(repo):
    workspace = Workspace.create(repo, task="t")
    workspace.remove(keep_branch=False)

    workspace.remove(keep_branch=False)
