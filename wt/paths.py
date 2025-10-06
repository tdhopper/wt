"""Path discovery and template rendering."""

from datetime import datetime
from pathlib import Path
import subprocess


class RepoDiscoveryError(Exception):
    """Raised when repository discovery fails."""


def discover_repo_root(start: Path | None = None) -> Path:
    """Discover the main git repository root (not worktree root).

    When run from a worktree, this returns the main repo root, not the worktree path.

    Args:
        start: Starting directory (defaults to current working directory)

    Returns:
        Path to main repository root

    Raises:
        RepoDiscoveryError: If not in a git repository

    """
    cwd = start or Path.cwd()

    try:
        # Get the common git directory (works in both main repo and worktrees)
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        git_common_dir = Path(result.stdout.strip())

        # Make it absolute if it's relative
        if not git_common_dir.is_absolute():
            git_common_dir = (cwd / git_common_dir).resolve()

        # The parent of the common git directory is the main repo root
        # In a regular repo: .git -> repo_root
        # In a worktree: /path/to/main/repo/.git -> main repo_root
        return git_common_dir.parent
    except subprocess.CalledProcessError as e:
        raise RepoDiscoveryError(f"Not in a git repository: {e.stderr.strip()}") from e
    except FileNotFoundError as e:
        raise RepoDiscoveryError("git command not found") from e


def default_wt_root(repo_root: Path) -> Path:
    """Compute default worktree root.

    Returns a sibling directory: <parent>/{repo_name}-worktrees

    Args:
        repo_root: Repository root path

    Returns:
        Default worktree root path

    """
    repo_name = repo_root.name
    parent = repo_root.parent
    return parent / f"{repo_name}-worktrees"


def render_path_template(
    template: str, context: dict[str, str], allow_unknown: bool = False
) -> Path:
    """Render a path template with variable substitution.

    Supports simple $VARNAME expansion (no eval).

    Args:
        template: Template string with $VARNAME placeholders
        context: Dictionary of variable values
        allow_unknown: If False, raise error on unknown variables

    Returns:
        Rendered path

    Raises:
        ValueError: If template contains unknown variables and allow_unknown is False

    """
    result = template

    # Find all $VARNAME patterns
    import re

    pattern = re.compile(r"\$([A-Z_][A-Z0-9_]*)")

    def replace_var(match):
        var_name = match.group(1)
        if var_name not in context:
            if not allow_unknown:
                raise ValueError(f"Unknown template variable: ${var_name}")
            return match.group(0)  # Leave unchanged
        return context[var_name]

    result = pattern.sub(replace_var, result)

    return Path(result)


def build_template_context(
    repo_root: Path,
    wt_root: Path,
    branch_name: str,
    source_branch: str,
    worktree_path: Path | None = None,
) -> dict[str, str]:
    """Build template context dictionary.

    Args:
        repo_root: Repository root path
        wt_root: Worktree root path
        branch_name: Target branch name
        source_branch: Source branch name
        worktree_path: Worktree path (if already computed)

    Returns:
        Dictionary of template variables

    """
    now = datetime.now()

    context = {
        "REPO_ROOT": str(repo_root.absolute()),
        "REPO_NAME": repo_root.name,
        "WT_ROOT": str(wt_root.absolute()),
        "BRANCH_NAME": branch_name,
        "SOURCE_BRANCH": source_branch,
        "DATE_ISO": now.strftime("%Y-%m-%d"),
        "TIME_ISO": now.strftime("%H:%M:%S"),
    }

    if worktree_path:
        context["WORKTREE_PATH"] = str(worktree_path.absolute())

    return context


def resolve_worktree_root(repo_root: Path, config: dict) -> Path:
    """Resolve the worktree root from config.

    Args:
        repo_root: Repository root path
        config: Configuration dictionary

    Returns:
        Worktree root path

    """
    wt_root_config = config["paths"]["worktree_root"]

    if not wt_root_config:
        # Use default
        return default_wt_root(repo_root)

    # Render template
    context = {
        "REPO_ROOT": str(repo_root.absolute()),
        "REPO_NAME": repo_root.name,
    }

    return render_path_template(wt_root_config, context)


def resolve_worktree_path(
    repo_root: Path,
    branch_name: str,
    source_branch: str,
    config: dict,
) -> Path:
    """Resolve the full worktree path for a branch.

    Args:
        repo_root: Repository root path
        branch_name: Target branch name
        source_branch: Source branch name
        config: Configuration dictionary

    Returns:
        Full worktree path

    """
    wt_root = resolve_worktree_root(repo_root, config)
    template = config["paths"]["worktree_path_template"]

    # Build context without worktree_path
    context = build_template_context(repo_root, wt_root, branch_name, source_branch)

    # Render template
    worktree_path = render_path_template(template, context)

    return worktree_path
