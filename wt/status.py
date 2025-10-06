"""Worktree status aggregation."""

from pathlib import Path
from typing import NamedTuple

from . import gitutil


class WorktreeStatus(NamedTuple):
    """Status information for a worktree."""

    path: Path
    branch: str | None
    sha_short: str
    is_dirty: bool
    ahead: int
    behind: int
    behind_main: int
    locked: str | None


def get_worktree_status(
    worktree_info: gitutil.WorktreeInfo,
    base_branch: str,
) -> WorktreeStatus:
    """
    Get detailed status for a worktree.

    Args:
        worktree_info: Basic worktree information
        base_branch: Base branch to check against (e.g., "origin/main")

    Returns:
        WorktreeStatus with detailed information
    """
    path = worktree_info.path

    # Get short SHA
    sha_short = gitutil.get_current_sha(path, short=True)

    # Check if dirty
    is_dirty = gitutil.is_dirty(path)

    # Get ahead/behind upstream
    behind, ahead = gitutil.count_ahead_behind(path)

    # Get behind main
    behind_main = gitutil.count_behind_base(path, base_branch)

    return WorktreeStatus(
        path=path,
        branch=worktree_info.branch,
        sha_short=sha_short,
        is_dirty=is_dirty,
        ahead=ahead,
        behind=behind,
        behind_main=behind_main,
        locked=worktree_info.locked,
    )


def get_all_worktree_statuses(
    repo_root: Path,
    base_branch: str,
) -> list[WorktreeStatus]:
    """
    Get status for all worktrees.

    Args:
        repo_root: Repository root path
        base_branch: Base branch to check against

    Returns:
        List of WorktreeStatus objects
    """
    worktrees = gitutil.list_worktrees(repo_root)
    statuses = []

    for wt in worktrees:
        # Skip bare worktrees
        if wt.is_bare:
            continue

        status = get_worktree_status(wt, base_branch)
        statuses.append(status)

    return statuses
