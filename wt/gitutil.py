"""Git command wrappers using subprocess."""

import subprocess
from pathlib import Path
from typing import NamedTuple


class GitError(Exception):
    """Raised when a git command fails."""


class WorktreeInfo(NamedTuple):
    """Information about a git worktree."""

    path: Path
    branch: str | None
    sha: str
    is_bare: bool
    locked: str | None


def git(*args: str, cwd: Path, check: bool = True) -> str:
    """
    Run a git command and return stdout.

    Args:
        *args: Git command arguments
        cwd: Working directory
        check: If True, raise GitError on non-zero exit

    Returns:
        Command stdout

    Raises:
        GitError: If command fails and check=True
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Git command failed: {e.stderr.strip()}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def branch_exists(name: str, cwd: Path) -> bool:
    """
    Check if a branch exists.

    Args:
        name: Branch name
        cwd: Working directory

    Returns:
        True if branch exists
    """
    try:
        git("rev-parse", "--verify", name, cwd=cwd)
        return True
    except GitError:
        return False


def remote_ref_exists(name: str, cwd: Path) -> bool:
    """
    Check if a remote ref exists.

    Args:
        name: Remote ref name (e.g., "origin/main")
        cwd: Working directory

    Returns:
        True if remote ref exists
    """
    try:
        git("rev-parse", "--verify", name, cwd=cwd)
        return True
    except GitError:
        return False


def get_default_branch(cwd: Path, remote: str = "origin") -> str:
    """
    Detect the default branch (main or master) on the remote.

    Args:
        cwd: Working directory
        remote: Remote name (default: "origin")

    Returns:
        Default branch name with remote prefix (e.g., "origin/main" or "origin/master")
    """
    # Check for main first, then fall back to master
    for branch in ["main", "master"]:
        ref = f"{remote}/{branch}"
        if remote_ref_exists(ref, cwd):
            return ref

    # If neither exists, default to origin/main
    return f"{remote}/main"


def list_worktrees(repo_root: Path) -> list[WorktreeInfo]:
    """
    List all worktrees in the repository.

    Args:
        repo_root: Repository root path

    Returns:
        List of WorktreeInfo objects
    """
    output = git("worktree", "list", "--porcelain", cwd=repo_root)

    worktrees = []
    current = {}

    for line in output.splitlines():
        if not line:
            if current:
                worktrees.append(
                    WorktreeInfo(
                        path=Path(current["worktree"]),
                        branch=current.get("branch"),
                        sha=current["HEAD"],
                        is_bare=current.get("bare", False),
                        locked=current.get("locked"),
                    )
                )
                current = {}
            continue

        if line.startswith("worktree "):
            current["worktree"] = line[9:]
        elif line.startswith("HEAD "):
            current["HEAD"] = line[5:]
        elif line.startswith("branch "):
            # Extract branch name from refs/heads/...
            ref = line[7:]
            if ref.startswith("refs/heads/"):
                current["branch"] = ref[11:]
            else:
                current["branch"] = ref
        elif line == "bare":
            current["bare"] = True
        elif line.startswith("locked "):
            current["locked"] = line[7:]

    # Don't forget the last worktree
    if current:
        worktrees.append(
            WorktreeInfo(
                path=Path(current["worktree"]),
                branch=current.get("branch"),
                sha=current["HEAD"],
                is_bare=current.get("bare", False),
                locked=current.get("locked"),
            )
        )

    return worktrees


def worktree_path_for_branch(branch: str, repo_root: Path) -> Path | None:
    """
    Find the worktree path for a given branch.

    Args:
        branch: Branch name
        repo_root: Repository root path

    Returns:
        Path to worktree, or None if not found
    """
    worktrees = list_worktrees(repo_root)

    for wt in worktrees:
        if wt.branch == branch:
            return wt.path

    return None


def is_dirty(path: Path) -> bool:
    """
    Check if a worktree has uncommitted changes.

    Args:
        path: Worktree path

    Returns:
        True if worktree is dirty
    """
    output = git("status", "--porcelain", cwd=path)
    return bool(output)


def get_upstream_branch(path: Path) -> str | None:
    """
    Get the upstream tracking branch.

    Args:
        path: Worktree path

    Returns:
        Upstream branch name, or None if not set
    """
    try:
        return git("rev-parse", "--abbrev-ref", "@{u}", cwd=path)
    except GitError:
        return None


def count_ahead_behind(path: Path) -> tuple[int, int]:
    """
    Count commits ahead/behind upstream.

    Args:
        path: Worktree path

    Returns:
        Tuple of (behind, ahead) counts, or (0, 0) if no upstream
    """
    upstream = get_upstream_branch(path)
    if not upstream:
        return (0, 0)

    try:
        output = git("rev-list", "--left-right", "--count", f"{upstream}...HEAD", cwd=path)
        parts = output.split()
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))
    except GitError:
        pass

    return (0, 0)


def count_behind_base(path: Path, base: str) -> int:
    """
    Count commits behind a base branch.

    Args:
        path: Worktree path
        base: Base branch name (e.g., "origin/main")

    Returns:
        Number of commits behind
    """
    try:
        output = git("rev-list", "--count", f"HEAD..{base}", cwd=path)
        return int(output)
    except GitError:
        return 0


def get_current_sha(path: Path, short: bool = True) -> str:
    """
    Get current commit SHA.

    Args:
        path: Worktree path
        short: If True, return short SHA

    Returns:
        Commit SHA
    """
    args = ["rev-parse"]
    if short:
        args.append("--short")
    args.append("HEAD")

    return git(*args, cwd=path)


def fetch_origin(repo_root: Path) -> None:
    """
    Fetch from origin with prune.

    Args:
        repo_root: Repository root path

    Raises:
        GitError: If fetch fails
    """
    git("fetch", "origin", "--prune", cwd=repo_root)


def list_merged_branches(repo_root: Path, base: str) -> list[str]:
    """
    List branches merged into base.

    Args:
        repo_root: Repository root path
        base: Base branch name

    Returns:
        List of branch names
    """
    output = git("branch", "--format=%(refname:short)", f"--merged={base}", cwd=repo_root)
    return [line for line in output.splitlines() if line]


def get_current_branch(repo_root: Path) -> str | None:
    """
    Get current branch name.

    Args:
        repo_root: Repository root path

    Returns:
        Branch name, or None if detached HEAD
    """
    try:
        return git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root)
    except GitError:
        return None


def count_unpushed_commits(path: Path, branch: str) -> int:
    """
    Count commits not pushed to upstream.

    Args:
        path: Worktree path
        branch: Branch name

    Returns:
        Number of unpushed commits, or 0 if no upstream
    """
    upstream = get_upstream_branch(path)
    if not upstream:
        return 0

    try:
        output = git("rev-list", "--count", f"{upstream}..{branch}", cwd=path)
        return int(output)
    except GitError:
        return 0


def create_worktree(
    repo_root: Path,
    path: Path,
    branch: str,
    source: str,
    create_branch: bool = True,
) -> None:
    """
    Create a new worktree.

    Args:
        repo_root: Repository root path
        path: Worktree path
        branch: Branch name
        source: Source branch/commit
        create_branch: If True, create new branch with -b

    Raises:
        GitError: If worktree creation fails
    """
    args = ["worktree", "add"]

    if create_branch:
        # Create new branch from source
        args.extend(["-b", branch, str(path), source])
    else:
        # Checkout existing branch
        args.extend([str(path), branch])

    git(*args, cwd=repo_root)


def remove_worktree(repo_root: Path, path: Path, force: bool = False) -> None:
    """
    Remove a worktree.

    Args:
        repo_root: Repository root path
        path: Worktree path
        force: If True, use --force flag

    Raises:
        GitError: If worktree removal fails
    """
    args = ["worktree", "remove"]

    if force:
        args.append("--force")

    args.append(str(path))

    git(*args, cwd=repo_root)


def delete_branch(repo_root: Path, branch: str, force: bool = False) -> None:
    """
    Delete a branch.

    Args:
        repo_root: Repository root path
        branch: Branch name
        force: If True, use -D instead of -d

    Raises:
        GitError: If branch deletion fails
    """
    flag = "-D" if force else "-d"
    git("branch", flag, branch, cwd=repo_root)


def prune_worktrees(repo_root: Path) -> None:
    """
    Prune stale worktree entries.

    Args:
        repo_root: Repository root path

    Raises:
        GitError: If prune fails
    """
    git("worktree", "prune", cwd=repo_root)


def set_upstream(path: Path, branch: str, upstream: str) -> None:
    """
    Set upstream tracking branch.

    Args:
        path: Worktree path
        branch: Local branch name
        upstream: Upstream branch name (e.g., "origin/main")

    Raises:
        GitError: If setting upstream fails
    """
    git("branch", "-u", upstream, branch, cwd=path)


def update_with_strategy(
    path: Path,
    base: str,
    strategy: str,
) -> None:
    """
    Update worktree with base using specified strategy.

    Args:
        path: Worktree path
        base: Base branch name
        strategy: Update strategy (rebase, merge, ff-only)

    Raises:
        GitError: If update fails
    """
    if strategy == "rebase":
        git("rebase", base, cwd=path)
    elif strategy == "merge":
        git("merge", "--no-edit", base, cwd=path)
    elif strategy == "ff-only":
        git("merge", "--ff-only", base, cwd=path)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def stash_push(path: Path, message: str = "wt-autostash") -> None:
    """
    Stash uncommitted changes.

    Args:
        path: Worktree path
        message: Stash message

    Raises:
        GitError: If stash fails
    """
    git("stash", "push", "-u", "-m", message, cwd=path)


def stash_pop(path: Path) -> None:
    """
    Pop stashed changes.

    Args:
        path: Worktree path

    Raises:
        GitError: If stash pop fails
    """
    git("stash", "pop", cwd=path)
