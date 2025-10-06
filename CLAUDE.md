# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`wt` is a zero-friction git worktree manager written in Python. It provides a fast, deterministic CLI for creating, managing, and cleaning up git worktrees without prompts, using configurable path templates and hooks.

**Core principles:**
- Stdlib only (Python ≥3.11 for `tomllib`), no runtime dependencies
- Shell out to git via `subprocess` (no `pygit2`)
- Deterministic paths via templates, no interactive prompts
- Fast CLI with optional pretty output via `--rich` flag

## Development Commands

```bash
# Run the CLI directly (development)
python -m wt.cli [command]

# Install in editable mode
pip install -e .

# After installation, use as 'wt'
wt [command]

# Common commands
wt doctor                     # Check configuration and environment
wt new feature-x              # Create new worktree
wt list                       # List all worktrees
wt status                     # Show status with dirty/ahead/behind info
wt status --rich              # Show status with box-drawing table
wt pull-main --stash          # Update all worktrees from main
wt prune-merged --yes         # Prune merged branches
wt rm feature-x --yes         # Remove worktree

# Run tests (when implemented)
pytest tests/
pytest tests/test_config.py  # Single test file
```

## Architecture

### Module Structure

```
wt/
  __init__.py  # Package initialization
  cli.py       # argparse setup, subcommand dispatch, command implementations
  config.py    # TOML config loading, merging precedence (CLI > local > global > defaults)
  gitutil.py   # Thin subprocess wrappers for git plumbing commands
  paths.py     # Repo discovery, path template rendering ($VARNAME expansion)
  hooks.py     # Post-create hook discovery & execution with env vars, timeout
  status.py    # Aggregate worktree status (dirty, ahead/behind tracking)
  table.py     # Simple table formatting with box-drawing (stdlib only)
  lock.py      # Repo-scoped advisory lock (fcntl on Unix, PID file on Windows)
```

**Key modules:**
- `cli.py` - Contains both argparse setup and all command implementations (cmd_new, cmd_list, cmd_status, etc.)
- `config.py` - Exports `load_config()`, `get_default_config()`, `get_global_config_path()`, `get_local_config_path()`
- `gitutil.py` - All git operations return strings or raise `GitError`. Key functions: `list_worktrees()`, `create_worktree()`, `is_dirty()`, `count_ahead_behind()`
- `paths.py` - Exports `discover_repo_root()`, `resolve_worktree_path()`, `build_template_context()`, `render_path_template()`
- `hooks.py` - Exports `run_post_create_hooks()` which handles discovery, env setup, and execution
- `lock.py` - `RepoLock` context manager for safe concurrent operations

### Configuration System

Two-layer config with precedence: **CLI args > local (.wt/config.toml) > global (~/.config/wt/config.toml) > defaults**

Key sections:
- `[paths]`: `worktree_root`, `worktree_path_template` with template variables
- `[branches]`: `auto_prefix` for auto-prepending username/namespace
- `[hooks]`: `post_create_dir`, `continue_on_error`, `timeout_seconds`
- `[update]`: `base`, `strategy` (rebase/merge/ff-only), `auto_stash`
- `[prune]`: `protected` branches list, `delete_branch_with_worktree`

### Path Resolution & Templates

- Default worktree root: `<parent(repo_root)>/.<repo_name>-worktrees` (hidden sibling)
- Template variables: `$REPO_ROOT`, `$REPO_NAME`, `$WT_ROOT`, `$BRANCH_NAME`, `$SOURCE_BRANCH`, `$WORKTREE_PATH`, `$DATE_ISO`, `$TIME_ISO`
- Template rendering uses simple `$VARNAME` substitution (no eval)
- Branch names with slashes create nested directories

### Git Operations

All git operations via `subprocess` using plumbing commands:
- `git worktree list --porcelain` for parsing worktree state
- `git rev-parse --show-toplevel` for repo discovery
- `git status --porcelain` for dirty checks
- `git rev-list --left-right --count @{u}...HEAD` for ahead/behind tracking
- `git fetch origin --prune` once per operation before iteration

### Hooks System

Post-creation hooks run in lexicographic order from:
1. Local: `<repo_root>/.wt/hooks/post_create.d/`
2. Global: `~/.config/wt/hooks/post_create.d/`

Supported: `*.sh` (bash/sh), `*.py` (python), any executable
Environment vars injected: `WT_REPO_ROOT`, `WT_BRANCH_NAME`, `WT_WORKTREE_PATH`, etc.
Timeout enforcement via `timeout_seconds` config

### Safety Mechanisms

- Repo-scoped lockfile: `<repo_root>/.git/wt.lock` (fcntl advisory lock)
- Never delete branches with unpushed commits unless `--force`
- Requires `--yes` for destructive batch operations
- Protected branches list prevents accidental deletion

## Command Behaviors

### `wt new <branch>`
1. Apply `auto_prefix` if configured
2. Fetch origin, resolve source branch (default `origin/main`)
3. Render path template, create parent dirs
4. Create branch (if needed) and worktree via `git worktree add`
5. Run post-create hooks in new worktree
6. Print resulting path

### `wt status`
For each worktree:
- Dirty check via `git status --porcelain`
- Ahead/behind upstream via `git rev-list --left-right --count`
- Behind main via `git rev-list --count HEAD..origin/main`
- Output plain or `--rich` table

### `wt pull-main`
- Single fetch, then iterate worktrees
- Optional `--stash` for dirty trees
- Apply strategy: `rebase`/`merge`/`ff-only`
- Attempt stash pop after update

### `wt prune-merged`
- Find branches merged into `origin/main`
- Exclude protected list + current branch
- Remove worktrees first, then optionally delete branches
- Safety: check for unpushed commits before delete

## Testing Strategy

- **Unit tests**: Template rendering, config precedence, hook discovery
- **Integration tests**: Require temp git repos with remotes
  - Create/list/status/pull-main/prune-merged workflows
  - Hook execution with env vars
  - Safety checks (unpushed commits, protected branches)
- **Edge cases**: Existing dirs, duplicate worktrees, Windows paths

## Key Implementation Notes

- Use `Path` from `pathlib` throughout (all path operations return `Path` objects)
- Single fetch per top-level operation to minimize network calls
- Serial execution with repo lock (no parallelism in current implementation)
- Template rendering errors on unknown variables (no `allow_unknown_vars` implemented yet)
- Hooks run with `cwd=worktree_path`, timeout enforced via `subprocess.run(timeout=...)`
- All commands acquire `RepoLock` via context manager before executing
- Git errors raise `GitError` exceptions with stderr details
- Config merge is recursive for nested dicts (see `merge_configs()` in config.py)
- Worktree parsing uses `--porcelain` format for stable output across git versions

## Common Workflows

### Adding a new command
1. Add subparser in `cli.py:main()` with arguments
2. Implement `cmd_<name>(args, cfg, repo_root)` function
3. Add dispatch in the command routing section
4. Command runs inside `RepoLock` context automatically

### Modifying config schema
1. Update defaults in `config.py:get_default_config()`
2. Update SPEC.md with new fields
3. Config is automatically merged with precedence (no additional code needed)

### Adding new template variables
1. Add to `build_template_context()` in `paths.py`
2. Update SPEC.md template variables section
3. Variables are auto-injected into hooks as `WT_<VARNAME>`
