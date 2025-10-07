"""Hook discovery and execution."""

import os
from pathlib import Path
import subprocess


class HookError(Exception):
    """Raised when a hook fails."""


def discover_hooks(
    local_config_path: Path | None,
    global_config_path: Path,
    hook_dir_name: str,
) -> list[Path]:
    """Discover hook scripts in local and global directories.

    Args:
        local_config_path: Path to local config file (or None)
        global_config_path: Path to global config file
        hook_dir_name: Hook directory name (e.g., "hooks/post_create.d")

    Returns:
        List of executable hook paths in execution order (local first, then global)

    """
    hooks = []

    # Local hooks (check directory exists, not just config file)
    if local_config_path:
        local_hook_dir = local_config_path.parent / hook_dir_name
        if local_hook_dir.exists() and local_hook_dir.is_dir():
            hooks.extend(_collect_executable_hooks(local_hook_dir))

    # Global hooks
    global_hook_dir = global_config_path.parent / hook_dir_name
    if global_hook_dir.exists() and global_hook_dir.is_dir():
        hooks.extend(_collect_executable_hooks(global_hook_dir))

    return hooks


def _collect_executable_hooks(directory: Path) -> list[Path]:
    """Collect executable files from a directory in lexicographic order.

    Args:
        directory: Directory to scan

    Returns:
        List of executable file paths

    """
    hooks = []

    for entry in sorted(directory.iterdir()):
        if entry.is_file() and os.access(entry, os.X_OK):
            hooks.append(entry)

    return hooks


def find_non_executable_hooks(
    local_config_path: Path | None,
    global_config_path: Path,
    hook_dir_name: str,
) -> list[Path]:
    """Find hook files that exist but are not executable.

    Args:
        local_config_path: Path to local config file (or None)
        global_config_path: Path to global config file
        hook_dir_name: Hook directory name (e.g., "hooks/post_create.d")

    Returns:
        List of non-executable hook file paths

    """
    non_executable = []

    # Local hooks (check directory exists, not just config file)
    if local_config_path:
        local_hook_dir = local_config_path.parent / hook_dir_name
        if local_hook_dir.exists() and local_hook_dir.is_dir():
            non_executable.extend(_collect_non_executable_hooks(local_hook_dir))

    # Global hooks
    global_hook_dir = global_config_path.parent / hook_dir_name
    if global_hook_dir.exists() and global_hook_dir.is_dir():
        non_executable.extend(_collect_non_executable_hooks(global_hook_dir))

    return non_executable


def _collect_non_executable_hooks(directory: Path) -> list[Path]:
    """Collect files that look like hooks but are not executable.

    Args:
        directory: Directory to scan

    Returns:
        List of non-executable hook file paths

    """
    non_executable = []

    for entry in sorted(directory.iterdir()):
        # Skip directories and hidden files
        if not entry.is_file() or entry.name.startswith("."):
            continue

        # Check if file looks like a hook (common extensions)
        if (entry.suffix in [".sh", ".py", ".bash"] or not entry.suffix) and not os.access(
            entry, os.X_OK
        ):
            non_executable.append(entry)

    return non_executable


def build_hook_env(context: dict[str, str]) -> dict[str, str]:
    """Build environment variables for hook execution.

    Args:
        context: Template context dictionary

    Returns:
        Environment dict with WT_* variables

    """
    env = os.environ.copy()

    # Add WT_* prefixed variables
    for key, value in context.items():
        env[f"WT_{key}"] = value

    return env


def run_post_create_hooks(
    worktree_path: Path,
    context: dict[str, str],
    local_config_path: Path | None,
    global_config_path: Path,
    config: dict,
) -> None:
    """Run post-create hooks for a new worktree.

    Args:
        worktree_path: Path to the new worktree
        context: Template context with variables
        local_config_path: Path to local config (or None)
        global_config_path: Path to global config
        config: Full config dictionary

    Raises:
        HookError: If a hook fails and continue_on_error is False

    """
    hook_dir_name = config["hooks"]["post_create_dir"]
    timeout_seconds = config["hooks"]["timeout_seconds"]
    continue_on_error = config["hooks"]["continue_on_error"]

    # Check for non-executable hooks and warn
    non_executable = find_non_executable_hooks(local_config_path, global_config_path, hook_dir_name)
    for hook_path in non_executable:
        print(
            f"Warning: Hook '{hook_path}' is not executable. Run: chmod +x {hook_path}", flush=True
        )

    hooks = discover_hooks(local_config_path, global_config_path, hook_dir_name)

    if not hooks:
        return

    env = build_hook_env(context)

    for hook_path in hooks:
        try:
            _run_hook(hook_path, worktree_path, env, timeout_seconds)
        except HookError as e:
            if continue_on_error:
                print(f"Warning: Hook {hook_path.name} failed: {e}", flush=True)
            else:
                raise


def _run_hook(hook_path: Path, cwd: Path, env: dict[str, str], timeout: int) -> None:
    """Run a single hook script.

    Args:
        hook_path: Path to hook script
        cwd: Working directory (worktree path)
        env: Environment variables
        timeout: Timeout in seconds

    Raises:
        HookError: If hook execution fails

    """
    # Determine how to run the hook
    if hook_path.suffix == ".sh":
        # Run with bash if available, else sh
        shell = "bash" if _command_exists("bash") else "sh"
        cmd = [shell, str(hook_path)]
    elif hook_path.suffix == ".py":
        # Run with uv run
        cmd = ["uv", "run", str(hook_path)]
    else:
        # Run directly (must be executable)
        cmd = [str(hook_path)]

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            raise HookError(  # noqa: TRY301
                f"{hook_path.name} exited with code {result.returncode}: {result.stderr.strip()}"
            )

        # Print hook output if any
        if result.stdout:
            print(result.stdout, end="", flush=True)

    except subprocess.TimeoutExpired as e:
        raise HookError(f"{hook_path.name} timed out after {timeout} seconds") from e
    except FileNotFoundError as e:
        raise HookError(f"Failed to execute {hook_path.name}: {e}") from e
    except Exception as e:
        raise HookError(f"Unexpected error running {hook_path.name}: {e}") from e


def _command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        subprocess.run(
            ["which", command],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    else:
        return True
