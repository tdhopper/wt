"""Configuration loading and management."""

import tomllib
from pathlib import Path
from typing import Any


def get_default_config() -> dict[str, Any]:
    """Return default configuration."""
    return {
        "paths": {
            "worktree_root": "",
            "worktree_path_template": "$WT_ROOT/$BRANCH_NAME",
        },
        "branches": {
            "auto_prefix": "",
        },
        "hooks": {
            "post_create_dir": "hooks/post_create.d",
            "continue_on_error": False,
            "timeout_seconds": 300,
        },
        "update": {
            "base": "origin/main",
            "strategy": "rebase",
            "auto_stash": False,
        },
        "prune": {
            "protected": ["main", "master", "develop"],
            "delete_branch_with_worktree": False,
        },
        "ui": {
            "rich": False,
            "json_indent": 2,
        },
    }


def load_toml_file(path: Path) -> dict[str, Any]:
    """Load a TOML config file."""
    if not path.exists():
        return {}

    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load config from {path}: {e}")


def merge_configs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two config dicts, with override taking precedence."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result


def get_global_config_path() -> Path:
    """Return path to global config file."""
    return Path.home() / ".config" / "wt" / "config.toml"


def get_local_config_path(repo_root: Path) -> Path:
    """Return path to local config file."""
    return repo_root / ".wt" / "config.toml"


def load_config(repo_root: Path | None, cli_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Load configuration with precedence: CLI > local > global > defaults.

    Args:
        repo_root: Repository root path (None if not in a repo)
        cli_overrides: Configuration overrides from CLI arguments

    Returns:
        Merged configuration dictionary
    """
    # Start with defaults
    config = get_default_config()

    # Merge global config
    global_config_path = get_global_config_path()
    if global_config_path.exists():
        global_config = load_toml_file(global_config_path)
        config = merge_configs(config, global_config)

    # Merge local config (if in a repo)
    if repo_root:
        local_config_path = get_local_config_path(repo_root)
        if local_config_path.exists():
            local_config = load_toml_file(local_config_path)
            config = merge_configs(config, local_config)

    # Merge CLI overrides
    if cli_overrides:
        config = merge_configs(config, cli_overrides)

    return config
