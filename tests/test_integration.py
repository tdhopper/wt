"""Integration tests for wt - tests actual git operations and workflows."""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
import shutil
import pytest


@pytest.fixture
def git_repo():
    """Create a real git repo with a remote for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "test-repo"
        remote = Path(tmpdir) / "remote.git"

        # Create bare remote
        remote.mkdir()
        subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

        # Create local repo
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True, capture_output=True)

        # Initial commit
        (repo / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True)

        yield {"repo": repo, "remote": remote}


def test_new_worktree_creates_and_tracks(git_repo):
    """The most critical path: creating a new worktree actually works."""
    repo = git_repo["repo"]

    result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "new", "feature-test"],
        cwd=repo,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Failed: {result.stderr}"

    # Verify worktree exists
    wt_list = subprocess.run(
        ["git", "worktree", "list"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True
    )
    assert "feature-test" in wt_list.stdout

    # Verify branch was created
    branches = subprocess.run(
        ["git", "branch", "-a"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True
    )
    assert "feature-test" in branches.stdout


def test_status_shows_dirty_worktrees(git_repo):
    """Users need to see which worktrees have uncommitted changes."""
    repo = git_repo["repo"]

    # Create worktree
    subprocess.run([sys.executable, "-m", "wt.cli", "new", "feature-dirty"], cwd=repo, check=True, capture_output=True)

    # Get worktree path from list using JSON output
    list_result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "list", "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True
    )

    import json
    worktrees = json.loads(list_result.stdout)
    wt_path = None
    for wt in worktrees:
        if "feature-dirty" in wt["branch"]:
            wt_path = Path(wt["path"])
            break

    assert wt_path and wt_path.exists(), f"Worktree path not found. Got: {list_result.stdout}"

    # Make it dirty
    (wt_path / "test.txt").write_text("dirty")

    # Check status
    status = subprocess.run(
        [sys.executable, "-m", "wt.cli", "status"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True
    )

    assert "✓" in status.stdout or "dirty" in status.stdout.lower()


def test_prune_merged_runs_without_error(git_repo):
    """Prune command should run without error."""
    repo = git_repo["repo"]

    # Just test that prune-merged runs successfully even with no branches to prune
    result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "prune-merged", "--yes"],
        cwd=repo,
        capture_output=True,
        text=True
    )

    # Should succeed (either pruned something or found nothing to prune)
    assert result.returncode == 0, f"Prune failed: {result.stderr}"
    assert "No branches to prune" in result.stdout or "Found" in result.stdout


def test_config_precedence_actually_works(git_repo):
    """Config overrides must work or users will be confused."""
    repo = git_repo["repo"]

    # Set local config
    config_dir = repo / ".wt"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text("""
[branches]
auto_prefix = "test/"
""")

    # Create worktree
    result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "new", "feature"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True
    )

    # Check branch name has prefix
    branches = subprocess.run(
        ["git", "branch", "-a"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True
    )

    assert "test/feature" in branches.stdout


def test_path_template_creates_nested_dirs(git_repo):
    """Template paths with slashes must create nested directories."""
    repo = git_repo["repo"]

    # Set template config
    config_dir = repo / ".wt"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text("""
[paths]
worktree_path_template = "$WT_ROOT/branches/$BRANCH_NAME"
""")

    # Create worktree with slash in name
    result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "new", "feat/nested"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True
    )

    # Verify nested path exists
    list_result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "list"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True
    )

    assert "branches/feat/nested" in list_result.stdout or "branches\\feat\\nested" in list_result.stdout


def test_doctor_catches_missing_git(tmp_path):
    """Doctor should detect broken environments."""
    # Run doctor with PATH that doesn't include git
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)  # Empty PATH

    result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "doctor"],
        capture_output=True,
        text=True,
        env=env
    )

    # Should warn about git not found
    assert "git" in result.stdout.lower() or result.returncode != 0


def test_new_worktree_with_existing_branch_not_detached(git_repo):
    """Regression: creating worktree for existing branch should checkout that branch, not create detached HEAD."""
    repo = git_repo["repo"]

    # First, create a branch directly with git
    subprocess.run(["git", "branch", "existing-branch"], cwd=repo, check=True, capture_output=True)

    # Now create a worktree for this existing branch
    result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "new", "existing-branch"],
        cwd=repo,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Failed: {result.stderr}"

    # Get worktree path
    list_result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "list", "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True
    )

    import json
    worktrees = json.loads(list_result.stdout)
    wt_path = None
    for wt in worktrees:
        if wt["branch"] and "existing-branch" in wt["branch"]:
            wt_path = Path(wt["path"])
            break

    assert wt_path and wt_path.exists(), f"Worktree not found for existing-branch. Got: {list_result.stdout}"

    # Verify it's on the branch, not detached
    status_result = subprocess.run(
        ["git", "status"],
        cwd=wt_path,
        capture_output=True,
        text=True,
        check=True
    )

    # Should NOT say "Not currently on any branch" (detached)
    assert "Not currently on any branch" not in status_result.stdout, "Worktree is detached HEAD, should be on existing-branch"
    assert "On branch existing-branch" in status_result.stdout, "Worktree should be on existing-branch"
