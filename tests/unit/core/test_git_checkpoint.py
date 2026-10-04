"""Git checkpoints: a snapshot of the working tree on a private ref, restorable with /undo.

Unlike the per-file transaction backups, this also covers whatever a shell command did.
The snapshot must never disturb the user's own git state (HEAD, branches, index, working tree).
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

from cortex.core.checkpoints import GitCheckpointStore


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    (root / "tracked.txt").write_text("tracked v1\n")
    (root / "other.txt").write_text("other v1\n")
    (root / ".gitignore").write_text("ignored.log\nbuild/\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "init")
    return root


def store(repo: Path, **kwargs) -> GitCheckpointStore:
    return GitCheckpointStore(repo, session_id="sess", **kwargs)


def user_git_state(repo: Path):
    return (
        git(repo, "rev-parse", "HEAD"),
        git(repo, "branch", "--show-current"),
        git(repo, "status", "--porcelain=v1", "-uall"),
        git(repo, "diff", "--cached"),
        git(repo, "stash", "list"),
    )


def test_snapshot_does_not_disturb_the_users_git_state(repo):
    (repo / "tracked.txt").write_text("edited, unstaged\n")
    (repo / "other.txt").write_text("edited and staged\n")
    git(repo, "add", "other.txt")
    (repo / "new.txt").write_text("untracked\n")
    before = user_git_state(repo)

    snapshot = store(repo).snapshot("a request")

    assert snapshot is not None
    assert user_git_state(repo) == before
    assert (repo / "tracked.txt").read_text() == "edited, unstaged\n"


def test_snapshot_lives_on_a_private_ref(repo):
    snapshot = store(repo).snapshot("a request")

    refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/cortex/").split()
    assert refs == [snapshot.ref]
    assert snapshot.ref.startswith("refs/cortex/sess/")
    assert "cortex" not in git(repo, "branch", "--list")


def test_restore_brings_back_an_edited_file(repo):
    s = store(repo)
    s.snapshot("before")
    (repo / "tracked.txt").write_text("ruined\n")

    result = s.restore()

    assert (repo / "tracked.txt").read_text() == "tracked v1\n"
    assert result.restored == ["tracked.txt"]


def test_restore_brings_back_a_deleted_tracked_file(repo):
    s = store(repo)
    s.snapshot("before")
    (repo / "tracked.txt").unlink()

    s.restore()

    assert (repo / "tracked.txt").read_text() == "tracked v1\n"


def test_restore_brings_back_a_deleted_untracked_file(repo):
    (repo / "scratch.txt").write_text("never committed\n")
    s = store(repo)
    s.snapshot("before")
    (repo / "scratch.txt").unlink()

    s.restore()

    assert (repo / "scratch.txt").read_text() == "never committed\n"


def test_restore_removes_files_created_since_and_their_empty_directories(repo):
    s = store(repo)
    s.snapshot("before")
    (repo / "made").mkdir()
    (repo / "made" / "deep").mkdir()
    (repo / "made" / "deep" / "new.txt").write_text("x")
    (repo / "top.txt").write_text("y")

    result = s.restore()

    assert not (repo / "top.txt").exists()
    assert not (repo / "made").exists()
    assert sorted(result.removed) == ["made/deep/new.txt", "top.txt"]


def test_restore_leaves_ignored_files_alone(repo):
    s = store(repo)
    s.snapshot("before")
    (repo / "ignored.log").write_text("log line\n")
    (repo / "build").mkdir()
    (repo / "build" / "out.bin").write_text("artifact")

    s.restore()

    assert (repo / "ignored.log").exists()
    assert (repo / "build" / "out.bin").exists()


def test_restore_does_not_move_head_or_touch_the_index(repo):
    s = store(repo)
    s.snapshot("before")
    (repo / "tracked.txt").write_text("changed\n")
    git(repo, "add", "tracked.txt")
    staged = git(repo, "diff", "--cached")
    head = git(repo, "rev-parse", "HEAD")

    s.restore()

    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "diff", "--cached") == staged


def test_restore_keeps_the_executable_bit(repo):
    script = repo / "run.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(0o755)
    s = store(repo)
    s.snapshot("before")
    script.unlink()

    s.restore()

    assert script.stat().st_mode & stat.S_IXUSR


def test_a_restore_can_itself_be_undone(repo):
    s = store(repo)
    s.snapshot("before")
    (repo / "tracked.txt").write_text("after the command\n")
    (repo / "extra.txt").write_text("extra\n")

    first = s.restore()
    assert (repo / "tracked.txt").read_text() == "tracked v1\n"
    assert not (repo / "extra.txt").exists()

    s.restore(first.safety)

    assert (repo / "tracked.txt").read_text() == "after the command\n"
    assert (repo / "extra.txt").read_text() == "extra\n"


def test_unusual_file_names_survive_a_round_trip(repo):
    names = ["with space.txt", "star*.txt", "ünïcode.txt", "[bracket].txt", "dir with space/a.txt"]
    for name in names:
        path = repo / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"content of {name}\n")
    s = store(repo)
    s.snapshot("before")
    for name in names:
        (repo / name).write_text("clobbered\n")

    s.restore()

    for name in names:
        assert (repo / name).read_text() == f"content of {name}\n"


def test_works_in_a_repository_with_no_commits_yet(tmp_path):
    root = tmp_path / "fresh"
    root.mkdir()
    git(root, "init", "-q")
    (root / "a.txt").write_text("one\n")
    s = store(root)

    assert s.snapshot("before") is not None
    (root / "a.txt").write_text("two\n")
    s.restore()

    assert (root / "a.txt").read_text() == "one\n"


def test_works_without_a_configured_git_identity(repo, monkeypatch, tmp_path):
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.delenv(var, raising=False)

    assert store(repo).snapshot("before") is not None


def test_not_available_outside_a_git_repository(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    s = store(plain)

    assert s.available() is False
    assert s.snapshot("before") is None
    assert s.latest() is None


def test_project_in_a_subdirectory_only_touches_that_subdirectory(repo):
    sub = repo / "pkg"
    sub.mkdir()
    (sub / "inside.txt").write_text("inside v1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "add pkg")
    s = GitCheckpointStore(sub, session_id="sess")
    s.snapshot("before")
    (sub / "inside.txt").write_text("inside v2\n")
    (repo / "tracked.txt").write_text("outside change\n")

    s.restore()

    assert (sub / "inside.txt").read_text() == "inside v1\n"
    assert (repo / "tracked.txt").read_text() == "outside change\n"


def test_restore_reports_when_head_moved(repo):
    s = store(repo)
    snapshot = s.snapshot("before")
    (repo / "tracked.txt").write_text("v2\n")
    git(repo, "commit", "-qam", "a commit the command made")

    result = s.restore()

    assert result.head_at_snapshot == snapshot.head
    assert result.head_moved is True
    assert (repo / "tracked.txt").read_text() == "tracked v1\n"


def test_latest_returns_the_newest_snapshot_and_old_ones_are_pruned(repo):
    s = store(repo, keep=3)
    made = [s.snapshot(f"request {i}") for i in range(5)]

    assert s.latest().ref == made[-1].ref
    refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/cortex/").split()
    assert refs == [m.ref for m in made[-3:]]


def test_restore_without_any_snapshot_raises_a_clear_error(repo):
    with pytest.raises(LookupError, match="No checkpoint"):
        store(repo).restore()


def test_restoring_a_file_nobody_changed_is_a_no_op(repo):
    s = store(repo)
    s.snapshot("before")

    result = s.restore()

    assert result.restored == [] and result.removed == []
    assert os.path.exists(repo / "tracked.txt")


# ---- undo/redo as two stacks -------------------------------------------------------------


def _states(repo: Path):
    return (repo / "tracked.txt").read_text()


def test_undoing_twice_walks_back_through_requests(repo):
    s = store(repo)
    s.snapshot("request 1")  # state S0
    (repo / "tracked.txt").write_text("S1\n")
    s.snapshot("request 2")
    (repo / "tracked.txt").write_text("S2\n")

    s.restore()
    assert _states(repo) == "S1\n"
    s.restore()
    assert _states(repo) == "tracked v1\n"
    with pytest.raises(LookupError, match="No checkpoint"):
        s.restore()


def test_redo_reapplies_what_undo_took_away(repo):
    s = store(repo)
    s.snapshot("request")
    (repo / "tracked.txt").write_text("after\n")
    (repo / "new.txt").write_text("new\n")
    s.restore()

    s.redo()

    assert _states(repo) == "after\n"
    assert (repo / "new.txt").read_text() == "new\n"


def test_redo_with_nothing_undone_raises_a_clear_error(repo):
    s = store(repo)
    s.snapshot("request")

    with pytest.raises(LookupError, match="Nothing to redo"):
        s.redo()


def test_redo_after_new_work_does_not_lose_that_work(repo):
    s = store(repo)
    s.snapshot("request")
    (repo / "tracked.txt").write_text("S1\n")
    s.restore()  # back to v1
    (repo / "tracked.txt").write_text("new work after the undo\n")

    s.redo()  # S1 again, and the new work is saved as a checkpoint
    assert _states(repo) == "S1\n"

    s.restore()
    assert _states(repo) == "new work after the undo\n"


def test_latest_ignores_the_redo_stack(repo):
    s = store(repo)
    first = s.snapshot("request")
    (repo / "tracked.txt").write_text("changed\n")
    s.restore()  # consumes the checkpoint, pushes a redo snapshot

    assert s.latest() is None
    assert first is not None


# ---- housekeeping ------------------------------------------------------------------------


def _all_refs(repo: Path):
    return git(
        repo, "for-each-ref", "--format=%(refname)", "refs/cortex/", "refs/cortex-redo/"
    ).split()


def test_clear_removes_this_sessions_snapshots_from_both_stacks(repo):
    s = store(repo)
    s.snapshot("one")
    (repo / "tracked.txt").write_text("x\n")
    s.restore()  # leaves a redo snapshot
    other = GitCheckpointStore(repo, session_id="other")
    other.snapshot("someone else")
    assert len(_all_refs(repo)) == 2

    s.clear()

    assert [r for r in _all_refs(repo)] == [other.latest().ref]


def test_sweep_removes_old_snapshots_of_other_sessions_only(repo):
    old = GitCheckpointStore(repo, session_id="crashed")
    old.snapshot("left behind")
    mine = store(repo)
    mine.snapshot("current")

    import time

    assert mine.sweep_stale(max_age_days=7) == 0  # nothing is old yet
    assert mine.sweep_stale(max_age_days=7, now=time.time() + 8 * 86400) == 1
    assert old.latest() is None
    assert mine.latest() is not None  # never sweeps its own


def test_the_stale_sweep_runs_with_the_first_snapshot_not_at_construction(repo):
    stale = GitCheckpointStore(repo, session_id="crashed")
    stale.snapshot("left behind")

    mine = GitCheckpointStore(repo, session_id="sess", stale_days=-1)  # everything foreign is stale
    assert stale.latest() is not None, "constructing the store must not touch git"

    mine.snapshot("first change")

    assert stale.latest() is None
    assert mine.latest() is not None
