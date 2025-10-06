"""Config tests - only testing merge logic that could actually break."""

import tempfile
from pathlib import Path
import pytest
from wt.config import load_config, merge_configs, get_default_config


def test_merge_configs_deep_override():
    """Nested config values must override correctly."""
    base = {
        "paths": {"worktree_root": "/old", "template": "old"},
        "branches": {"auto_prefix": "base/"}
    }
    override = {
        "paths": {"worktree_root": "/new"},
        "update": {"strategy": "rebase"}
    }

    result = merge_configs(base, override)

    assert result["paths"]["worktree_root"] == "/new"
    assert result["paths"]["template"] == "old"  # Not overridden
    assert result["branches"]["auto_prefix"] == "base/"  # Preserved
    assert result["update"]["strategy"] == "rebase"  # New section


def test_load_config_local_overrides_global():
    """Local config must win over global."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()

        # Create local config
        wt_dir = repo / ".wt"
        wt_dir.mkdir()
        (wt_dir / "config.toml").write_text("""
[branches]
auto_prefix = "local/"
""")

        # Create fake global config
        global_dir = Path(tmpdir) / "global"
        global_dir.mkdir()
        (global_dir / "config.toml").write_text("""
[branches]
auto_prefix = "global/"
""")

        # Load with override
        import wt.config
        orig_func = wt.config.get_global_config_path

        def mock_global_path():
            return global_dir / "config.toml"

        wt.config.get_global_config_path = mock_global_path
        try:
            config = load_config(repo_root=repo)
            assert config["branches"]["auto_prefix"] == "local/"
        finally:
            wt.config.get_global_config_path = orig_func
