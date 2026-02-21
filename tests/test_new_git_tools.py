
import subprocess
import pytest
from pathlib import Path

from cortex.tools import create_tool_instance
from cortex.models import PermissionMode


@pytest.fixture
def git_repo(tmp_path):
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    (repo_path / "file1.txt").write_text("file1 content")
    subprocess.run(["git", "add", "file1.txt"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)
    return repo_path


def test_git_show_tool(git_repo):
    from cortex.ui.console import console
    tool = create_tool_instance("git_show", git_repo, PermissionMode.NORMAL, console)
    result = tool.execute(ref="HEAD")
    assert result["success"]
    assert "Initial commit" in result["data"]["output"]


def test_git_checkout_tool(git_repo):
    from cortex.ui.console import console
    tool = create_tool_instance("git_checkout", git_repo, PermissionMode.AUTO_APPROVE, console)

    # Test creating a new branch
    result = tool.execute(branch="new_feature", new_branch=True)
    assert result["success"]

    # Check if the branch was created
    branches_result = subprocess.run(["git", "branch"], cwd=git_repo, capture_output=True, text=True, check=True)  # noqa: E501
    assert "new_feature" in branches_result.stdout

    # Test switching to the new branch
    result = tool.execute(branch="new_feature")
    assert result["success"]


def test_git_reset_tool(git_repo):
    from cortex.ui.console import console
    # Create and commit file2.txt
    (git_repo / "file2.txt").write_text("initial file2 content")
    subprocess.run(["git", "add", "file2.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Add file2"], cwd=git_repo, check=True)

    # Modify file2.txt and stage the changes
    (git_repo / "file2.txt").write_text("modified file2 content")
    subprocess.run(["git", "add", "file2.txt"], cwd=git_repo, check=True)

    # Verify file2.txt is staged
    status_before_reset = subprocess.run(["git", "status"], cwd=git_repo, capture_output=True, text=True, check=True)  # noqa: E501
    assert "Changes to be committed" in status_before_reset.stdout
    assert "file2.txt" in status_before_reset.stdout

    tool = create_tool_instance("git_reset", git_repo, PermissionMode.AUTO_APPROVE, console)
    result = tool.execute(files=["file2.txt"])
    assert result["success"]

    # Check if the file is unstaged
    status_after_reset = subprocess.run(["git", "status"], cwd=git_repo, capture_output=True, text=True, check=True)  # noqa: E501
    assert "Changes not staged for commit" in status_after_reset.stdout
    assert "file2.txt" in status_after_reset.stdout
    assert "Changes to be committed" not in status_after_reset.stdout


@pytest.fixture
def remote_repo(tmp_path):
    # Create a bare remote repository
    remote_path = tmp_path / "remote_repo.git"
    remote_path.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_path, check=True)
    return remote_path


def test_git_fetch_tool(git_repo, remote_repo, tmp_path):
    from cortex.ui.console import console
    # Add a remote to the local repository
    subprocess.run(["git", "remote", "add", "origin", str(remote_repo)], cwd=git_repo, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=git_repo, check=True)

    # Make a commit in the remote repo
    clone_path = tmp_path / "clone_repo"
    subprocess.run(["git", "clone", str(remote_repo), str(clone_path)], check=True)
    (clone_path / "file2.txt").write_text("file2 content")
    subprocess.run(["git", "add", "file2.txt"], cwd=clone_path, check=True)
    subprocess.run(["git", "commit", "-m", "Second commit"], cwd=clone_path, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=clone_path, check=True)

    tool = create_tool_instance("git_fetch", git_repo, PermissionMode.AUTO_APPROVE, console)
    result = tool.execute(remote="origin")

    assert result["success"]


def test_git_pull_tool(git_repo, remote_repo, tmp_path):
    from cortex.ui.console import console
    # Add a remote to the local repository
    subprocess.run(["git", "remote", "add", "origin", str(remote_repo)], cwd=git_repo, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=git_repo, check=True)

    # Make a commit in the remote repo
    clone_path = tmp_path / "clone_repo"
    subprocess.run(["git", "clone", str(remote_repo), str(clone_path)], check=True)
    (clone_path / "file2.txt").write_text("file2 content")
    subprocess.run(["git", "add", "file2.txt"], cwd=clone_path, check=True)
    subprocess.run(["git", "commit", "-m", "Second commit"], cwd=clone_path, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=clone_path, check=True)

    tool = create_tool_instance("git_pull", git_repo, PermissionMode.AUTO_APPROVE, console)
    result = tool.execute(remote="origin", branch="main")

    assert result["success"]
    # Check that the pulled file is now in the local repo
    assert (git_repo / "file2.txt").exists()
