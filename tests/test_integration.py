"""Integration tests for wt - tests actual git operations and workflows."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest


def run_wt(args: list[str], cwd: Path, fake_home: Path, check=False, **kwargs):
    """Run wt command with isolated environment (no global config/hooks)."""
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    return subprocess.run(
        [sys.executable, "-m", "wt.cli", *args], cwd=cwd, env=env, check=check, **kwargs
    )


@pytest.fixture
def git_repo():
    """Create a real git repo with a remote for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "test-repo"
        remote = Path(tmpdir) / "remote.git"
        fake_home = Path(tmpdir) / "fake-home"
        fake_home.mkdir()

        # Create bare remote
        remote.mkdir()
        subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

        # Create local repo
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # Initial commit
        (repo / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True
        )
        subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True
        )

        yield {"repo": repo, "remote": remote, "fake_home": fake_home}


def test_new_worktree_creates_and_tracks(git_repo):
    """The most critical path: creating a new worktree actually works."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    result = run_wt(["new", "feature-test"], repo, fake_home, capture_output=True, text=True)

    assert result.returncode == 0, f"Failed: {result.stderr}"

    # Verify worktree exists
    wt_list = subprocess.run(
        ["git", "worktree", "list"], cwd=repo, capture_output=True, text=True, check=True
    )
    assert "feature-test" in wt_list.stdout

    # Verify branch was created
    branches = subprocess.run(
        ["git", "branch", "-a"], cwd=repo, capture_output=True, text=True, check=True
    )
    assert "feature-test" in branches.stdout


def test_status_shows_dirty_worktrees(git_repo):
    """Users need to see which worktrees have uncommitted changes."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create worktree
    run_wt(["new", "feature-dirty"], repo, fake_home, check=True, capture_output=True)

    # Get worktree path from list using JSON output
    list_result = run_wt(
        ["list", "--json"], repo, fake_home, capture_output=True, text=True, check=True
    )

    import json

    worktrees = json.loads(list_result.stdout)
    wt_path = None
    for wt in worktrees:
        if "feature-dirty" in wt["branch"]:
            wt_path = Path(wt["path"])
            break

    assert wt_path is not None, f"Worktree path not found. Got: {list_result.stdout}"
    assert wt_path.exists(), f"Worktree path does not exist: {wt_path}"

    # Make it dirty
    (wt_path / "test.txt").write_text("dirty")

    # Check status
    status = run_wt(["status"], repo, fake_home, capture_output=True, text=True, check=True)

    assert "✓" in status.stdout or "dirty" in status.stdout.lower()


def test_prune_merged_runs_without_error(git_repo):
    """Prune command should run without error."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Just test that prune-merged runs successfully even with no branches to prune
    result = run_wt(["prune-merged", "--yes"], repo, fake_home, capture_output=True, text=True)

    # Should succeed (either pruned something or found nothing to prune)
    assert result.returncode == 0, f"Prune failed: {result.stderr}"
    assert "No branches to prune" in result.stdout or "Found" in result.stdout


def test_config_precedence_actually_works(git_repo):
    """Config overrides must work or users will be confused."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Set local config
    config_dir = repo / ".wt"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text("""
[branches]
auto_prefix = "test/"
""")

    # Create worktree
    run_wt(["new", "feature"], repo, fake_home, capture_output=True, text=True, check=True)

    # Check branch name has prefix
    branches = subprocess.run(
        ["git", "branch", "-a"], cwd=repo, capture_output=True, text=True, check=True
    )

    assert "test/feature" in branches.stdout


def test_path_template_creates_nested_dirs(git_repo):
    """Template paths with slashes must create nested directories."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Set template config
    config_dir = repo / ".wt"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text("""
[paths]
worktree_path_template = "$WT_ROOT/branches/$BRANCH_NAME"
""")

    # Create worktree with slash in name
    run_wt(["new", "feat/nested"], repo, fake_home, capture_output=True, text=True, check=True)

    # Verify nested path exists
    list_result = run_wt(["list"], repo, fake_home, capture_output=True, text=True, check=True)

    assert (
        "branches/feat/nested" in list_result.stdout
        or "branches\\feat\\nested" in list_result.stdout
    )


def test_doctor_catches_missing_git(tmp_path):
    """Doctor should detect broken environments."""
    # Run doctor with PATH that doesn't include git
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)  # Empty PATH

    result = subprocess.run(
        [sys.executable, "-m", "wt.cli", "doctor"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    # Should warn about git not found
    assert "git" in result.stdout.lower() or result.returncode != 0


def test_new_worktree_with_existing_branch_not_detached(git_repo):
    """Regression: creating worktree for existing branch should checkout that branch, not create detached HEAD."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # First, create a branch directly with git
    subprocess.run(["git", "branch", "existing-branch"], cwd=repo, check=True, capture_output=True)

    # Now create a worktree for this existing branch
    result = run_wt(["new", "existing-branch"], repo, fake_home, capture_output=True, text=True)

    assert result.returncode == 0, f"Failed: {result.stderr}"

    # Get worktree path
    list_result = run_wt(
        ["list", "--json"], repo, fake_home, capture_output=True, text=True, check=True
    )

    import json

    worktrees = json.loads(list_result.stdout)
    wt_path = None
    for wt in worktrees:
        if wt["branch"] and "existing-branch" in wt["branch"]:
            wt_path = Path(wt["path"])
            break

    assert wt_path is not None, f"Worktree not found for existing-branch. Got: {list_result.stdout}"
    assert wt_path.exists(), f"Worktree path does not exist: {wt_path}"

    # Verify it's on the branch, not detached
    status_result = subprocess.run(
        ["git", "status"], cwd=wt_path, capture_output=True, text=True, check=True
    )

    # Should NOT say "Not currently on any branch" (detached)
    assert (
        "Not currently on any branch" not in status_result.stdout
    ), "Worktree is detached HEAD, should be on existing-branch"
    # The branch name might have a prefix from config, so just check it contains "existing-branch"
    assert (
        "existing-branch" in status_result.stdout
    ), f"Worktree should be on existing-branch, got: {status_result.stdout}"


def test_tree_shows_flat_structure(git_repo):
    """Tree command should show flat structure when all branches from main."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create two worktrees with commits so they show in tree
    run_wt(["new", "feature-a"], repo, fake_home, check=True, capture_output=True)
    run_wt(["new", "feature-b"], repo, fake_home, check=True, capture_output=True)

    # Get worktree paths and add commits
    list_result = run_wt(
        ["list", "--json"], repo, fake_home, capture_output=True, text=True, check=True
    )
    worktrees = json.loads(list_result.stdout)

    for wt in worktrees:
        if wt["branch"] and "feature-" in wt["branch"]:
            wt_path = Path(wt["path"])
            (wt_path / "file.txt").write_text("test")
            subprocess.run(["git", "add", "."], cwd=wt_path, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Add file"], cwd=wt_path, check=True, capture_output=True
            )

    # Run tree command
    result = run_wt(["tree"], repo, fake_home, capture_output=True, text=True, check=True)

    # Should show main as root with both features as children
    assert "main" in result.stdout
    assert "feature-a" in result.stdout
    assert "feature-b" in result.stdout
    # Should use ASCII tree characters
    assert "├──" in result.stdout or "└──" in result.stdout


def test_tree_shows_nested_structure(git_repo):
    """Tree command should show nested structure for stacked branches."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create first worktree
    run_wt(["new", "feature-a"], repo, fake_home, check=True, capture_output=True)

    # Get feature-a path
    list_result = run_wt(
        ["list", "--json"], repo, fake_home, capture_output=True, text=True, check=True
    )
    worktrees = json.loads(list_result.stdout)
    feature_a_path = None
    for wt in worktrees:
        if wt["branch"] and "feature-a" in wt["branch"]:
            feature_a_path = Path(wt["path"])
            break

    # Create a commit in feature-a
    (feature_a_path / "a.txt").write_text("a")
    subprocess.run(["git", "add", "."], cwd=feature_a_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add a"], cwd=feature_a_path, check=True, capture_output=True
    )

    # Create feature-b from feature-a
    run_wt(
        ["new", "feature-b", "--from", "feature-a"],
        repo,
        fake_home,
        check=True,
        capture_output=True,
    )

    # Run tree command
    result = run_wt(["tree"], repo, fake_home, capture_output=True, text=True, check=True)

    # Should show hierarchical structure
    assert "main" in result.stdout
    assert "feature-a" in result.stdout
    assert "feature-b" in result.stdout

    # feature-b should appear after feature-a (nested)
    assert result.stdout.index("feature-a") < result.stdout.index("feature-b")


def test_tree_rich_uses_box_drawing(git_repo):
    """Tree command with --rich should use box-drawing characters."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create worktree
    run_wt(["new", "feature-x"], repo, fake_home, check=True, capture_output=True)

    # Get worktree path and add a commit so it shows in tree
    list_result = run_wt(
        ["list", "--json"], repo, fake_home, capture_output=True, text=True, check=True
    )
    worktrees = json.loads(list_result.stdout)
    for wt in worktrees:
        if wt["branch"] and "feature-x" in wt["branch"]:
            wt_path = Path(wt["path"])
            (wt_path / "file.txt").write_text("test")
            subprocess.run(["git", "add", "."], cwd=wt_path, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Add file"], cwd=wt_path, check=True, capture_output=True
            )
            break

    # Run tree command with --rich
    result = run_wt(["tree", "--rich"], repo, fake_home, capture_output=True, text=True, check=True)

    # Should show main and feature
    assert "main" in result.stdout
    assert "feature-x" in result.stdout
    # Should use box-drawing characters
    assert "└─" in result.stdout or "├─" in result.stdout


def test_tree_highlights_current_worktree(git_repo):
    """Tree command should highlight the current worktree."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create worktree
    run_wt(["new", "current-branch"], repo, fake_home, check=True, capture_output=True)

    # Get worktree path
    list_result = run_wt(
        ["list", "--json"], repo, fake_home, capture_output=True, text=True, check=True
    )
    worktrees = json.loads(list_result.stdout)
    wt_path = None
    for wt in worktrees:
        if wt["branch"] and "current-branch" in wt["branch"]:
            wt_path = Path(wt["path"])
            break

    # Add a commit so the branch shows in tree
    (wt_path / "file.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=wt_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add file"], cwd=wt_path, check=True, capture_output=True
    )

    # Run tree from within the worktree (simple mode)
    result = run_wt(["tree"], wt_path, fake_home, capture_output=True, text=True, check=True)

    # Should highlight current-branch with *
    assert "current-branch *" in result.stdout or "current-branch*" in result.stdout

    # Run tree with --rich from within the worktree
    result_rich = run_wt(
        ["tree", "--rich"], wt_path, fake_home, capture_output=True, text=True, check=True
    )

    # Should highlight current-branch with ●
    assert "current-branch ●" in result_rich.stdout or "current-branch●" in result_rich.stdout


def test_tree_handles_no_worktrees(git_repo):
    """Tree command should handle case with only main branch."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Run tree with no additional worktrees
    result = run_wt(["tree"], repo, fake_home, capture_output=True, text=True, check=True)

    # Should just show main
    assert "main" in result.stdout
    # Should complete successfully
    assert result.returncode == 0
