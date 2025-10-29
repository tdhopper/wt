"""Config tests - only testing merge logic that could actually break."""

from pathlib import Path
import tempfile

import wt.config
from wt.config import get_default_config, load_config, merge_configs


def test_merge_configs_deep_override():
    """Nested config values must override correctly."""
    base = {
        "paths": {"worktree_root": "/old", "template": "old"},
        "branches": {"auto_prefix": "base/"},
    }
    override = {"paths": {"worktree_root": "/new"}, "update": {"strategy": "rebase"}}

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
        orig_func = wt.config.get_global_config_path

        def mock_global_path():
            return global_dir / "config.toml"

        wt.config.get_global_config_path = mock_global_path
        try:
            config = load_config(repo_root=repo)
            assert config["branches"]["auto_prefix"] == "local/"
        finally:
            wt.config.get_global_config_path = orig_func


def test_default_config_includes_default_repo():
    """Default config must include default_repo field with empty value."""
    default_config = get_default_config()

    assert "paths" in default_config
    assert "default_repo" in default_config["paths"]
    assert default_config["paths"]["default_repo"] == ""


def test_load_config_with_default_repo_setting():
    """Config loading should handle default_repo in global config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        global_dir = Path(tmpdir) / "global"
        global_dir.mkdir()

        # Create global config with default_repo
        test_repo_path = "/path/to/default/repo"
        (global_dir / "config.toml").write_text(f"""
[paths]
default_repo = "{test_repo_path}"
""")

        orig_func = wt.config.get_global_config_path

        def mock_global_path():
            return global_dir / "config.toml"

        wt.config.get_global_config_path = mock_global_path
        try:
            config = load_config(repo_root=None)  # No repo context
            assert config["paths"]["default_repo"] == test_repo_path
        finally:
            wt.config.get_global_config_path = orig_func


def test_default_repo_merges_correctly():
    """default_repo should merge correctly between global and local configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()

        # Create global config with default_repo
        global_dir = Path(tmpdir) / "global"
        global_dir.mkdir()
        (global_dir / "config.toml").write_text("""
[paths]
default_repo = "/global/repo"
worktree_root = ""
""")

        # Create local config with different default_repo
        wt_dir = repo / ".wt"
        wt_dir.mkdir()
        (wt_dir / "config.toml").write_text("""
[paths]
default_repo = "/local/repo"
""")

        orig_func = wt.config.get_global_config_path

        def mock_global_path():
            return global_dir / "config.toml"

        wt.config.get_global_config_path = mock_global_path
        try:
            config = load_config(repo_root=repo)
            # Local should override global
            assert config["paths"]["default_repo"] == "/local/repo"
            # Other paths settings should still be present
            assert "worktree_root" in config["paths"]
        finally:
            wt.config.get_global_config_path = orig_func


def test_empty_default_repo_evaluates_to_none():
    """Empty string default_repo should be treated as None/unset."""
    with tempfile.TemporaryDirectory() as tmpdir:
        global_dir = Path(tmpdir) / "global"
        global_dir.mkdir()

        # Create config with empty default_repo
        (global_dir / "config.toml").write_text("""
[paths]
default_repo = ""
""")

        orig_func = wt.config.get_global_config_path

        def mock_global_path():
            return global_dir / "config.toml"

        wt.config.get_global_config_path = mock_global_path
        try:
            config = load_config(repo_root=None)
            # Empty string should be preserved (caller will check for falsy value)
            assert config["paths"]["default_repo"] == ""
        finally:
            wt.config.get_global_config_path = orig_func


def test_cli_overrides_default_repo():
    """CLI overrides should be able to override default_repo."""
    cli_overrides = {"paths": {"default_repo": "/cli/override/repo"}}

    config = load_config(repo_root=None, cli_overrides=cli_overrides)
    assert config["paths"]["default_repo"] == "/cli/override/repo"


def test_default_repo_with_tilde_in_config():
    """Config should preserve tilde paths for later expansion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        global_dir = Path(tmpdir) / "global"
        global_dir.mkdir()

        # Create config with tilde path
        (global_dir / "config.toml").write_text("""
[paths]
default_repo = "~/my-default-repo"
""")

        orig_func = wt.config.get_global_config_path

        def mock_global_path():
            return global_dir / "config.toml"

        wt.config.get_global_config_path = mock_global_path
        try:
            config = load_config(repo_root=None)
            # Tilde should be preserved (expansion happens in discover_repo_root)
            assert config["paths"]["default_repo"] == "~/my-default-repo"
        finally:
            wt.config.get_global_config_path = orig_func
