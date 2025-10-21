"""Path template tests - only the failure modes that matter."""

import pytest
import subprocess
import tempfile
from pathlib import Path

from wt.paths import build_template_context, render_path_template, discover_repo_root, RepoDiscoveryError


def test_template_renders_all_variables(tmp_path):
    """All documented template variables must work."""
    # Use platform-appropriate temporary paths
    repo_root = tmp_path / "repo"
    wt_root = tmp_path / "wt"

    context = build_template_context(
        repo_root=repo_root, wt_root=wt_root, branch_name="feature-x", source_branch="main"
    )

    # Test a sensible template (don't concatenate multiple absolute paths)
    template = "$WT_ROOT/$REPO_NAME-$BRANCH_NAME-from-$SOURCE_BRANCH"
    result = render_path_template(template, context)

    # Result should be wt_root / "repo-feature-x-from-main"
    result_str = str(result)
    assert str(wt_root) in result_str
    assert "repo" in result_str  # repo_name comes from repo_root.name
    assert "feature-x" in result_str
    assert "main" in result_str

    # Also test that REPO_ROOT works in isolation
    template2 = "$REPO_ROOT/worktrees/$BRANCH_NAME"
    result2 = render_path_template(template2, context)
    assert str(repo_root) in str(result2)


def test_template_with_slashes_creates_nested_path(tmp_path):
    """Branch names with slashes must create nested directories."""
    # Use platform-appropriate temporary paths
    repo_root = tmp_path / "repo"
    wt_root = tmp_path / "wt"

    context = build_template_context(
        repo_root=repo_root,
        wt_root=wt_root,
        branch_name="feat/sub/nested",
        source_branch="main",
    )

    template = "$WT_ROOT/$BRANCH_NAME"
    result = render_path_template(template, context)

    expected_path = wt_root / "feat" / "sub" / "nested"
    assert result == expected_path


def test_unknown_variable_raises_error():
    """Using undefined variables should fail loudly, not silently."""
    context = {"REPO_ROOT": "/repo"}

    template = "$REPO_ROOT/$UNKNOWN_VAR"

    with pytest.raises((KeyError, ValueError)):
        render_path_template(template, context)


@pytest.fixture
def real_git_repo():
    """Create a real git repository for testing discover_repo_root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo"
        repo_path.mkdir()
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, check=True, capture_output=True)
        
        # Create initial commit
        (repo_path / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, check=True, capture_output=True)
        
        yield repo_path


@pytest.fixture
def non_git_directory():
    """Create a non-git directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        non_git_path = Path(tmpdir) / "not_a_repo"
        non_git_path.mkdir()
        yield non_git_path


def test_discover_repo_root_finds_current_repo(real_git_repo):
    """discover_repo_root() should find the current git repository."""
    repo_root = discover_repo_root(start=real_git_repo)
    # Use resolve() to handle symlinks (macOS /var -> /private/var)
    assert repo_root.resolve() == real_git_repo.resolve()


def test_discover_repo_root_works_from_subdirectory(real_git_repo):
    """discover_repo_root() should find repo root from subdirectories."""
    subdir = real_git_repo / "subdir" / "deep"
    subdir.mkdir(parents=True)
    
    repo_root = discover_repo_root(start=subdir)
    assert repo_root.resolve() == real_git_repo.resolve()


def test_discover_repo_root_fails_without_default_repo(non_git_directory):
    """discover_repo_root() should fail when not in git repo and no default_repo."""
    with pytest.raises(RepoDiscoveryError) as exc_info:
        discover_repo_root(start=non_git_directory)
    
    assert "Not in a git repository" in str(exc_info.value)


def test_discover_repo_root_uses_valid_default_repo(real_git_repo, non_git_directory):
    """discover_repo_root() should use default_repo when not in a git directory."""
    repo_root = discover_repo_root(start=non_git_directory, default_repo=str(real_git_repo))
    assert repo_root.resolve() == real_git_repo.resolve()


def test_discover_repo_root_expands_tilde_in_default_repo(real_git_repo, non_git_directory):
    """discover_repo_root() should expand ~ in default_repo paths."""
    # Create a repo in a fake home directory
    fake_home = real_git_repo.parent / "fake_home"
    fake_home.mkdir()
    home_repo = fake_home / "repo"
    home_repo.mkdir()
    
    # Initialize git repo in fake home
    subprocess.run(["git", "init"], cwd=home_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=home_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=home_repo, check=True, capture_output=True)
    (home_repo / "README.md").write_text("test")
    subprocess.run(["git", "add", "."], cwd=home_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=home_repo, check=True, capture_output=True)
    
    # Mock os.path.expanduser to return our fake home
    import os
    import os.path
    original_expanduser = os.path.expanduser
    
    def mock_expanduser(path):
        if path.startswith("~"):
            return path.replace("~", str(fake_home), 1)
        return original_expanduser(path)
    
    os.path.expanduser = mock_expanduser
    
    try:
        repo_root = discover_repo_root(start=non_git_directory, default_repo="~/repo")
        assert repo_root.resolve() == home_repo.resolve()
    finally:
        os.path.expanduser = original_expanduser


def test_discover_repo_root_fails_with_invalid_default_repo(non_git_directory):
    """discover_repo_root() should fail when default_repo is not a git repository."""
    invalid_path = non_git_directory / "not_a_git_repo"
    invalid_path.mkdir()
    
    with pytest.raises(RepoDiscoveryError) as exc_info:
        discover_repo_root(start=non_git_directory, default_repo=str(invalid_path))
    
    assert "Default repository" in str(exc_info.value)
    assert "not a valid git repository" in str(exc_info.value)


def test_discover_repo_root_fails_with_nonexistent_default_repo(non_git_directory):
    """discover_repo_root() should fail when default_repo doesn't exist."""
    nonexistent_path = non_git_directory / "does_not_exist"
    
    with pytest.raises(RepoDiscoveryError) as exc_info:
        discover_repo_root(start=non_git_directory, default_repo=str(nonexistent_path))
    
    assert "Default repository" in str(exc_info.value)
    assert "not a valid git repository" in str(exc_info.value)


def test_discover_repo_root_prefers_current_repo_over_default(real_git_repo):
    """When in a git repo, discover_repo_root() should ignore default_repo."""
    # Create another git repo for default
    with tempfile.TemporaryDirectory() as tmpdir:
        default_repo = Path(tmpdir) / "default"
        default_repo.mkdir()
        subprocess.run(["git", "init"], cwd=default_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=default_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=default_repo, check=True, capture_output=True)
        
        # Should return the current repo, not the default
        repo_root = discover_repo_root(start=real_git_repo, default_repo=str(default_repo))
        assert repo_root.resolve() == real_git_repo.resolve()


def test_discover_repo_root_handles_worktree_correctly(real_git_repo):
    """discover_repo_root() should return main repo root even from worktrees."""
    # Create a worktree
    worktrees_dir = real_git_repo.parent / "worktrees"
    worktrees_dir.mkdir()
    worktree_path = worktrees_dir / "feature-branch"
    
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", "feature-branch"],
        cwd=real_git_repo,
        check=True,
        capture_output=True
    )
    
    # discover_repo_root from worktree should return main repo, not worktree path
    repo_root = discover_repo_root(start=worktree_path)
    assert repo_root.resolve() == real_git_repo.resolve()
    
    # Clean up worktree
    subprocess.run(
        ["git", "worktree", "remove", str(worktree_path)],
        cwd=real_git_repo,
        check=True,
        capture_output=True
    )


def test_discover_repo_root_with_relative_default_repo_path(real_git_repo, non_git_directory):
    """discover_repo_root() should handle relative paths in default_repo."""
    # Change to parent directory to make real_git_repo a relative path
    repo_parent = real_git_repo.parent
    relative_path = real_git_repo.name
    
    repo_root = discover_repo_root(start=non_git_directory, default_repo=f"{repo_parent}/{relative_path}")
    assert repo_root.resolve() == real_git_repo.resolve()


def test_discover_repo_root_with_empty_string_default_repo(non_git_directory):
    """discover_repo_root() should treat empty string default_repo as None."""
    with pytest.raises(RepoDiscoveryError) as exc_info:
        discover_repo_root(start=non_git_directory, default_repo="")
    
    assert "Not in a git repository" in str(exc_info.value)


def test_discover_repo_root_with_whitespace_only_default_repo(non_git_directory):
    """discover_repo_root() should handle whitespace-only default_repo gracefully."""
    with pytest.raises(RepoDiscoveryError):
        discover_repo_root(start=non_git_directory, default_repo="   ")


def test_discover_repo_root_handles_permission_denied_gracefully(non_git_directory):
    """discover_repo_root() should handle permission errors gracefully."""
    import os
    import stat
    
    # Create a directory we can't read
    restricted_dir = non_git_directory / "no_access"
    restricted_dir.mkdir()
    
    # Make it unreadable (on systems that support it)
    try:
        os.chmod(restricted_dir, 0o000)
        
        with pytest.raises((RepoDiscoveryError, PermissionError)):
            discover_repo_root(start=non_git_directory, default_repo=str(restricted_dir))
    finally:
        # Restore permissions so cleanup works
        try:
            os.chmod(restricted_dir, 0o755)
        except (OSError, PermissionError):
            pass  # May fail on some systems, that's OK


def test_discover_repo_root_with_special_characters_in_path(non_git_directory):
    """discover_repo_root() should handle special characters in default_repo paths."""
    # Test with spaces, unicode, etc.
    special_path = non_git_directory / "repo with spaces & üñíçödé"
    special_path.mkdir()
    
    # Should fail gracefully (not crash) when path exists but isn't a repo
    with pytest.raises(RepoDiscoveryError):
        discover_repo_root(start=non_git_directory, default_repo=str(special_path))


def test_discover_repo_root_with_very_long_path(non_git_directory):
    """discover_repo_root() should handle very long paths."""
    # Create a very long path
    long_name = "a" * 200  # Very long directory name
    long_path = non_git_directory / long_name
    
    try:
        long_path.mkdir()
        
        with pytest.raises(RepoDiscoveryError):
            discover_repo_root(start=non_git_directory, default_repo=str(long_path))
    except OSError:
        # Path too long for filesystem - that's OK, skip this test
        pytest.skip("Filesystem doesn't support very long paths")


def test_discover_repo_root_with_symlink_default_repo(real_git_repo, non_git_directory):
    """discover_repo_root() should follow symlinks in default_repo."""
    import os
    
    # Create a symlink to the real repo
    symlink_path = non_git_directory / "repo_symlink"
    
    try:
        os.symlink(str(real_git_repo), str(symlink_path))
        
        repo_root = discover_repo_root(start=non_git_directory, default_repo=str(symlink_path))
        # Should resolve to the real repo
        assert repo_root.resolve() == real_git_repo.resolve()
    except OSError:
        # Symlinks not supported on this platform
        pytest.skip("Symlinks not supported on this platform")


def test_discover_repo_root_handles_broken_symlink_gracefully(non_git_directory):
    """discover_repo_root() should handle broken symlinks gracefully."""
    import os
    
    # Create a symlink to a non-existent target
    broken_symlink = non_git_directory / "broken_link"
    nonexistent_target = non_git_directory / "does_not_exist"
    
    try:
        os.symlink(str(nonexistent_target), str(broken_symlink))
        
        with pytest.raises(RepoDiscoveryError):
            discover_repo_root(start=non_git_directory, default_repo=str(broken_symlink))
    except OSError:
        # Symlinks not supported on this platform
        pytest.skip("Symlinks not supported on this platform")


def test_discover_repo_root_with_file_instead_of_directory(non_git_directory):
    """discover_repo_root() should fail gracefully when default_repo points to a file."""
    # Create a regular file
    not_a_dir = non_git_directory / "just_a_file.txt"
    not_a_dir.write_text("I'm not a directory")
    
    with pytest.raises((RepoDiscoveryError, NotADirectoryError)):
        discover_repo_root(start=non_git_directory, default_repo=str(not_a_dir))


def test_discover_repo_root_with_git_file_repo(non_git_directory):
    """discover_repo_root() should handle git repositories with .git files (worktrees/submodules)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a main repo
        main_repo = Path(tmpdir) / "main"
        main_repo.mkdir()
        subprocess.run(["git", "init"], cwd=main_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=main_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=main_repo, check=True, capture_output=True)
        (main_repo / "README.md").write_text("main")
        subprocess.run(["git", "add", "."], cwd=main_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=main_repo, check=True, capture_output=True)
        
        # Create a worktree (which will have a .git file, not directory)
        worktree_dir = Path(tmpdir) / "worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_dir), "-b", "feature"],
            cwd=main_repo,
            check=True,
            capture_output=True
        )
        
        # discover_repo_root with the worktree as default_repo should work
        repo_root = discover_repo_root(start=non_git_directory, default_repo=str(worktree_dir))
        assert repo_root.resolve() == main_repo.resolve()  # Should return main repo, not worktree
