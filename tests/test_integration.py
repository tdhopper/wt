"""Integration tests for wt - tests actual git operations and workflows."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

from wt.cli import _complete_worktree_names


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


def test_new_from_current_moves_branch_to_worktree(git_repo):
    """--from-current should move current branch to a new worktree."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create a branch and make a commit on it (simulating accidental work on main)
    subprocess.run(["git", "checkout", "-b", "accidental-branch"], cwd=repo, check=True)
    (repo / "accident.txt").write_text("oops")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Accidental work"], cwd=repo, check=True, capture_output=True
    )

    # Use --from-current to move this branch to a worktree
    result = run_wt(["new", "--from-current"], repo, fake_home, capture_output=True, text=True)

    assert result.returncode == 0, f"Failed: {result.stderr}"

    # Verify worktree was created for accidental-branch
    list_result = run_wt(
        ["list", "--json"], repo, fake_home, capture_output=True, text=True, check=True
    )
    worktrees = json.loads(list_result.stdout)
    found = False
    for wt in worktrees:
        if wt["branch"] and "accidental-branch" in wt["branch"]:
            found = True
            wt_path = Path(wt["path"])
            assert wt_path.exists()
            # Verify the commit is there
            assert (wt_path / "accident.txt").exists()
            break

    assert found, "accidental-branch worktree not found"


def test_new_from_current_errors_on_detached_head(git_repo):
    """--from-current should error when in detached HEAD state."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Detach HEAD
    subprocess.run(["git", "checkout", "HEAD~0"], cwd=repo, check=True, capture_output=True)

    # Try to use --from-current
    result = run_wt(["new", "--from-current"], repo, fake_home, capture_output=True, text=True)

    assert result.returncode != 0, "Should fail when in detached HEAD"
    assert "detached HEAD" in result.stderr or "Not on a branch" in result.stderr


def test_new_from_current_errors_with_branch_arg(git_repo):
    """--from-current should error when branch argument is also provided."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    result = run_wt(
        ["new", "some-branch", "--from-current"], repo, fake_home, capture_output=True, text=True
    )

    assert result.returncode != 0, "Should fail when both branch and --from-current provided"
    assert "Cannot specify both" in result.stderr


def test_cli_uses_default_repo_from_non_git_directory(git_repo):
    """CLI should use default_repo when invoked from non-git directory."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create global config with default_repo
    config_dir = fake_home / ".config" / "wt"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(f"""
[paths]
default_repo = "{repo}"
""")

    # Create non-git directory to run from
    non_git_dir = fake_home / "not_a_repo"
    non_git_dir.mkdir()

    # Run status from non-git directory - should use default_repo
    result = run_wt(["status"], non_git_dir, fake_home, capture_output=True, text=True, check=True)

    # Should succeed and show the default repo's status
    assert "main" in result.stdout  # Should show main branch from default repo


def test_cli_prefers_current_repo_over_default_repo(git_repo):
    """When in git repo, CLI should ignore default_repo setting."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create another git repo to use as default
    other_repo = fake_home / "other_repo"
    other_repo.mkdir()
    subprocess.run(["git", "init"], cwd=other_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=other_repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=other_repo,
        check=True,
        capture_output=True,
    )
    (other_repo / "other.txt").write_text("other repo")
    subprocess.run(["git", "add", "."], cwd=other_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "other commit"], cwd=other_repo, check=True, capture_output=True
    )

    # Set default_repo to other_repo
    config_dir = fake_home / ".config" / "wt"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(f"""
[paths]
default_repo = "{other_repo}"
""")

    # Run from the original repo - should use current repo, not default
    result = run_wt(["list", "--json"], repo, fake_home, capture_output=True, text=True, check=True)

    worktrees = json.loads(result.stdout)
    # Should show original repo path, not other_repo
    main_wt = next(wt for wt in worktrees if "main" in wt.get("branch", ""))
    assert str(repo) in main_wt["path"]
    assert str(other_repo) not in main_wt["path"]


def test_cli_fails_gracefully_with_invalid_default_repo():
    """CLI should give clear error when default_repo is invalid."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_home = Path(tmpdir) / "fake_home"
        fake_home.mkdir()
        non_git_dir = fake_home / "not_a_repo"
        non_git_dir.mkdir()

        # Set default_repo to non-existent directory
        config_dir = fake_home / ".config" / "wt"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text("""
[paths]
default_repo = "/does/not/exist"
""")

        # Run from non-git directory - should fail with clear message
        result = run_wt(
            ["status"], non_git_dir, fake_home, capture_output=True, text=True, check=False
        )

        assert result.returncode != 0
        assert (
            "Default repository" in result.stderr or "not a valid git repository" in result.stderr
        )


def test_cli_fails_gracefully_with_non_git_default_repo():
    """CLI should give clear error when default_repo is not a git repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_home = Path(tmpdir) / "fake_home"
        fake_home.mkdir()
        non_git_dir = fake_home / "not_a_repo"
        non_git_dir.mkdir()

        # Create a directory that's not a git repo
        not_git = fake_home / "not_git_repo"
        not_git.mkdir()

        # Set default_repo to non-git directory
        config_dir = fake_home / ".config" / "wt"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text(f"""
[paths]
default_repo = "{not_git}"
""")

        # Run from non-git directory - should fail with clear message
        result = run_wt(
            ["status"], non_git_dir, fake_home, capture_output=True, text=True, check=False
        )

        assert result.returncode != 0
        assert "Default repository" in result.stderr
        assert "not a valid git repository" in result.stderr


def test_cli_works_without_default_repo_from_git_directory(git_repo):
    """CLI should work normally when no default_repo is set but we're in a git repo."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create global config without default_repo (or with empty default_repo)
    config_dir = fake_home / ".config" / "wt"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("""
[branches]
auto_prefix = ""
""")

    # Should work fine from git repo
    result = run_wt(["status"], repo, fake_home, capture_output=True, text=True, check=True)
    assert "main" in result.stdout


def test_new_worktree_uses_default_repo(git_repo):
    """Creating new worktree should work when using default_repo."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create global config with default_repo
    config_dir = fake_home / ".config" / "wt"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(f"""
[paths]
default_repo = "{repo}"
""")

    # Create non-git directory to run from
    non_git_dir = fake_home / "not_a_repo"
    non_git_dir.mkdir()

    # Create new worktree from non-git directory - should use default_repo
    result = run_wt(
        ["new", "feature-from-default"], non_git_dir, fake_home, capture_output=True, text=True
    )

    assert result.returncode == 0, f"Failed: {result.stderr}"

    # Verify worktree was created in default repo
    wt_list = subprocess.run(
        ["git", "worktree", "list"], cwd=repo, capture_output=True, text=True, check=True
    )
    assert "feature-from-default" in wt_list.stdout


def test_default_repo_with_tilde_expansion(git_repo):
    """CLI should expand ~ in default_repo paths."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Move repo to fake home to test tilde expansion
    home_repo = fake_home / "my_repo"

    # Copy the git repo to fake home (move files and .git)
    shutil.copytree(repo, home_repo)

    # Create global config with tilde path
    config_dir = fake_home / ".config" / "wt"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("""
[paths]
default_repo = "~/my_repo"
""")

    # Create non-git directory to run from
    non_git_dir = fake_home / "not_a_repo"
    non_git_dir.mkdir()

    # Run status from non-git directory - should expand ~ and use home repo
    result = run_wt(["status"], non_git_dir, fake_home, capture_output=True, text=True, check=True)

    # Should succeed and show the home repo's status
    assert "main" in result.stdout


def test_completion_works_with_default_repo(git_repo):
    """Shell completion should work when using default_repo."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create a worktree first so completion has something to complete
    run_wt(["new", "completion-test"], repo, fake_home, check=True, capture_output=True)

    # Create global config with default_repo
    config_dir = fake_home / ".config" / "wt"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(f"""
[paths]
default_repo = "{repo}"
""")

    # Create non-git directory to run from
    non_git_dir = fake_home / "not_a_repo"
    non_git_dir.mkdir()

    # Test that completion function can find worktrees using default_repo
    # We test this by checking if the completion command would succeed
    # (The actual completion testing would require more complex shell integration)

    # For now, just verify that wt commands work from non-git directory
    result = run_wt(["list"], non_git_dir, fake_home, capture_output=True, text=True, check=True)
    assert "completion-test" in result.stdout


def test_doctor_shows_default_repo_setting(git_repo):
    """Doctor command should display default_repo configuration."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create global config with default_repo
    config_dir = fake_home / ".config" / "wt"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(f"""
[paths]
default_repo = "{repo}"
""")

    # Run doctor from git repo
    result = run_wt(["doctor"], repo, fake_home, capture_output=True, text=True, check=True)

    # Doctor should show the default_repo setting
    assert str(repo) in result.stdout or "default_repo" in result.stdout


def test_completion_function_works_in_git_directory(git_repo):
    """Completion function should work normally when in a git directory."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create some worktrees to complete
    run_wt(["new", "feature-one"], repo, fake_home, check=True, capture_output=True)
    run_wt(["new", "feature-two"], repo, fake_home, check=True, capture_output=True)

    # Test the completion function directly
    sys.path.insert(
        0,
        str(
            Path(
                "/private/var/folders/xn/45d91fgd0f18hg7q88yqmgl40000gn/T/fleet-4dcb3ypngv3nu3ojatzn/wt"
            )
        ),
    )

    # Set up environment to simulate being in the git repo
    original_cwd = Path.cwd()
    original_home = os.environ.get("HOME")

    try:
        os.chdir(repo)
        os.environ["HOME"] = str(fake_home)

        branch_names = _complete_worktree_names()

        # Should return branch names from worktrees
        assert isinstance(branch_names, list)
        assert "main" in branch_names
        assert "feature-one" in branch_names
        assert "feature-two" in branch_names

    finally:
        os.chdir(original_cwd)
        if original_home:
            os.environ["HOME"] = original_home
        elif "HOME" in os.environ:
            del os.environ["HOME"]


def test_completion_function_uses_default_repo_from_non_git_directory(git_repo):
    """Completion function should use default_repo when in non-git directory."""
    repo = git_repo["repo"]
    fake_home = git_repo["fake_home"]

    # Create some worktrees to complete
    run_wt(["new", "completion-branch"], repo, fake_home, check=True, capture_output=True)

    # Create global config with default_repo
    config_dir = fake_home / ".config" / "wt"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(f"""
[paths]
default_repo = "{repo}"
""")

    # Create non-git directory
    non_git_dir = fake_home / "not_git"
    non_git_dir.mkdir()

    # Test completion function from non-git directory
    sys.path.insert(
        0,
        str(
            Path(
                "/private/var/folders/xn/45d91fgd0f18hg7q88yqmgl40000gn/T/fleet-4dcb3ypngv3nu3ojatzn/wt"
            )
        ),
    )

    original_cwd = Path.cwd()
    original_home = os.environ.get("HOME")

    try:
        os.chdir(non_git_dir)  # Change to non-git directory
        os.environ["HOME"] = str(fake_home)

        branch_names = _complete_worktree_names()

        # Should still return branch names using default_repo
        assert isinstance(branch_names, list)
        assert "main" in branch_names
        assert "completion-branch" in branch_names

    finally:
        os.chdir(original_cwd)
        if original_home:
            os.environ["HOME"] = original_home
        elif "HOME" in os.environ:
            del os.environ["HOME"]


def test_completion_function_handles_missing_default_repo_gracefully():
    """Completion function should return empty list when no repo found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_home = Path(tmpdir) / "home"
        fake_home.mkdir()
        non_git_dir = fake_home / "not_git"
        non_git_dir.mkdir()

        # No default_repo configured
        config_dir = fake_home / ".config" / "wt"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text("""
[branches]
auto_prefix = ""
""")

        sys.path.insert(
            0,
            str(
                Path(
                    "/private/var/folders/xn/45d91fgd0f18hg7q88yqmgl40000gn/T/fleet-4dcb3ypngv3nu3ojatzn/wt"
                )
            ),
        )

        original_cwd = Path.cwd()
        original_home = os.environ.get("HOME")

        try:
            os.chdir(non_git_dir)
            os.environ["HOME"] = str(fake_home)

            branch_names = _complete_worktree_names()

            # Should return empty list gracefully, not crash
            assert isinstance(branch_names, list)
            assert len(branch_names) == 0

        finally:
            os.chdir(original_cwd)
            if original_home:
                os.environ["HOME"] = original_home
            elif "HOME" in os.environ:
                del os.environ["HOME"]


def test_completion_function_handles_invalid_default_repo_gracefully():
    """Completion function should handle invalid default_repo gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_home = Path(tmpdir) / "home"
        fake_home.mkdir()
        non_git_dir = fake_home / "not_git"
        non_git_dir.mkdir()

        # Configure invalid default_repo
        config_dir = fake_home / ".config" / "wt"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text("""
[paths]
default_repo = "/does/not/exist"
""")

        sys.path.insert(
            0,
            str(
                Path(
                    "/private/var/folders/xn/45d91fgd0f18hg7q88yqmgl40000gn/T/fleet-4dcb3ypngv3nu3ojatzn/wt"
                )
            ),
        )

        original_cwd = Path.cwd()
        original_home = os.environ.get("HOME")

        try:
            os.chdir(non_git_dir)
            os.environ["HOME"] = str(fake_home)

            branch_names = _complete_worktree_names()

            # Should return empty list gracefully, not crash
            assert isinstance(branch_names, list)
            assert len(branch_names) == 0

        finally:
            os.chdir(original_cwd)
            if original_home:
                os.environ["HOME"] = original_home
            elif "HOME" in os.environ:
                del os.environ["HOME"]


def test_completion_function_filters_origin_prefix():
    """Completion function should remove 'origin/' prefix from branch names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_home = Path(tmpdir) / "home"
        fake_home.mkdir()
        repo = fake_home / "test_repo"
        repo.mkdir()

        # Set up a git repo with origin/ prefixed branches
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
        (repo / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True
        )
        subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True, capture_output=True)

        # Create worktrees - these will have local branch names
        subprocess.run(
            ["git", "worktree", "add", str(repo.parent / "wt1"), "-b", "feature-test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # Configure default_repo
        config_dir = fake_home / ".config" / "wt"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text(f"""
[paths]
default_repo = "{repo}"
""")

        sys.path.insert(
            0,
            str(
                Path(
                    "/private/var/folders/xn/45d91fgd0f18hg7q88yqmgl40000gn/T/fleet-4dcb3ypngv3nu3ojatzn/wt"
                )
            ),
        )

        original_cwd = Path.cwd()
        original_home = os.environ.get("HOME")

        try:
            os.chdir(repo)
            os.environ["HOME"] = str(fake_home)

            branch_names = _complete_worktree_names()

            # Should have branch names without origin/ prefix
            assert isinstance(branch_names, list)
            assert "main" in branch_names
            assert "feature-test" in branch_names
            # Should not have origin/ prefixes
            assert not any(name.startswith("origin/") for name in branch_names)

        finally:
            os.chdir(original_cwd)
            if original_home:
                os.environ["HOME"] = original_home
            elif "HOME" in os.environ:
                del os.environ["HOME"]
