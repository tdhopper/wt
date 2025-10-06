<div align="center">
  <img src="logo.png" alt="wt logo" width="200">
  <h1>wt</h1>
  <p><strong>Zero-friction git worktree manager</strong></p>
</div>

`wt` is a fast, deterministic CLI for creating and managing git worktrees without interactive prompts. Stop juggling branches in a single working directory - work on multiple features simultaneously with isolated, organized worktrees.

```bash
# Create a worktree for a new feature
wt new my-feature

# See what you're working on
wt status

# Keep everything in sync
wt pull-main --stash

# Clean up merged work
wt prune-merged --yes
```

---

## Why wt?

**Git worktrees** let you check out multiple branches simultaneously in separate directories. They're perfect for:
- Working on multiple features without stashing or committing incomplete work
- Running tests on one branch while developing on another
- Reviewing PRs in isolation without disrupting your current work
- Keeping long-running branches separate from daily work

**But vanilla git worktrees are tedious:** paths are manual, cleanup is forgotten, and there's no workflow automation.

**wt fixes this:** deterministic paths via templates, automatic cleanup, post-create hooks, and zero prompts for scripting.

---

## Quick Start

### Installation

```bash
# Install from source
uv tool install -e .

# Verify installation
wt doctor
```

### Basic Usage

```bash
# Create a worktree for a new feature branch
wt new my-feature
# -> /Users/you/repos/myproject-worktrees/my-feature

# List all worktrees
wt list

# See status with tracking info
wt status --rich

# Jump to a worktree
cd $(wt where my-feature)

# Remove a worktree when done
wt rm my-feature --yes --delete-branch
```

---

## Tutorial: Your First Worktree

Let's create a worktree for a new feature, make some changes, and clean up.

### 1. Create a worktree

```bash
cd ~/repos/myproject
wt new login-redesign
```

This creates a new branch `login-redesign` from `origin/main` and checks it out in a separate directory adjacent to your repo:
```
~/repos/myproject-worktrees/login-redesign
```

### 2. Work in the worktree

```bash
cd $(wt where login-redesign)
# Make your changes
git add .
git commit -m "Redesign login form"
git push -u origin login-redesign
```

Your main worktree is untouched - you can keep working there simultaneously.

### 3. Keep both worktrees in sync

```bash
# From anywhere in your repo
wt pull-main --stash
```

This fetches updates and rebases (or merges) all your worktrees with `origin/main`, stashing dirty changes automatically.

### 4. Clean up when merged

After your PR is merged:

```bash
wt prune-merged --yes --delete-branch
```

Automatically removes worktrees for merged branches and optionally deletes the local branches too.

---

## How-To Guides

### Set up auto-prefixing for branches

Add your username to all new branches automatically:

**`~/.config/wt/config.toml`:**
```toml
[branches]
auto_prefix = "alice/"
```

Now `wt new feature` creates branch `alice/feature`.

### Customize worktree paths

Use template variables to organize worktrees:

**`~/repos/myproject/.wt/config.toml`:**
```toml
[paths]
worktree_root = "/Users/alice/work"
worktree_path_template = "$WT_ROOT/$REPO_NAME/$BRANCH_NAME"
```

Variables available:
- `$REPO_ROOT` - Absolute path to main repo
- `$REPO_NAME` - Repository directory name
- `$WT_ROOT` - Resolved worktree root
- `$BRANCH_NAME` - Branch name (with slashes for nesting)
- `$SOURCE_BRANCH` - Branch this worktree was created from
- `$DATE_ISO` / `$TIME_ISO` - Timestamps

### Run commands after creating worktrees

**Example: Install dependencies automatically**

Create `~/repos/myproject/.wt/hooks/post_create.d/01-install.sh`:

```bash
#!/bin/bash
set -e

echo "Installing dependencies in $WT_WORKTREE_PATH..."
npm install
```

Make it executable:
```bash
chmod +x ~/repos/myproject/.wt/hooks/post_create.d/01-install.sh
```

Now every `wt new` runs this hook in the new worktree.

**Hook environment variables:**
- `WT_REPO_ROOT`, `WT_REPO_NAME`
- `WT_BRANCH_NAME`, `WT_SOURCE_BRANCH`
- `WT_WORKTREE_PATH`
- All template variables available

### Use different update strategies

```bash
# Merge instead of rebase
wt pull-main --strategy merge

# Fast-forward only (fails on divergence)
wt pull-main --strategy ff-only
```

Set defaults in config:
```toml
[update]
base = "origin/develop"  # Use develop instead of main
strategy = "merge"       # Default to merge
auto_stash = true        # Always stash automatically
```

### Protect important branches

Prevent accidental deletion of specific branches:

```toml
[prune]
protected = ["main", "develop", "staging"]
delete_branch_with_worktree = false
```

### Find and jump to worktrees

```bash
# Print path (useful for scripting)
wt where my-feature

# Jump to worktree
cd $(wt where my-feature)

# Open in editor
code $(wt where my-feature)
```

### Make VS Code windows visually distinct

Enable automatic creation of VS Code settings to make each worktree window unique:

```toml
[vscode]
create_settings = true
color_borders = true     # Deterministic colored borders per branch
custom_title = true      # Show repo name + branch in title bar
```

When enabled, `wt new` creates `.vscode/settings.json` with:
- **Colored window borders** - Each branch gets a unique color (generated from branch name hash)
- **Custom window title** - Shows `{repo_name} | {branch_name}` instead of just the path

This makes it easy to visually distinguish between multiple VS Code windows when working across worktrees.

**Note:** Settings are only created if `.vscode/settings.json` doesn't already exist, so existing customizations are preserved.

---

## Command Reference

### `wt new <branch>`

Create a new worktree.

**Options:**
- `--from <branch>` - Source branch (default: `origin/main`)
- `--track` - Set upstream tracking to `origin/<branch>`
- `--force` - Overwrite empty directory if exists

**Examples:**
```bash
wt new feature-x
wt new hotfix --from origin/v1.2
wt new experiment --track
```

### `wt list`

List all worktrees.

**Options:**
- `--json` - Output as JSON

**Examples:**
```bash
wt list
wt list --json | jq '.[] | select(.branch == "main")'
```

### `wt status`

Show status of all worktrees with dirty/ahead/behind indicators.

**Options:**
- `--json` - Output as JSON
- `--rich` - Use box-drawing table (can be set as default in config)

**Examples:**
```bash
wt status
wt status --rich
```

### `wt rm <branch>`

Remove a worktree.

**Options:**
- `--yes` - Skip confirmation prompt
- `--delete-branch` - Also delete the local branch
- `--force` - Force deletion even with unpushed commits

**Examples:**
```bash
wt rm old-feature --yes
wt rm merged-feature --yes --delete-branch
```

### `wt pull-main`

Update all worktrees from the base branch.

**Options:**
- `--base <branch>` - Base branch (default: from config)
- `--strategy <rebase|merge|ff-only>` - Update strategy
- `--stash` - Auto-stash dirty worktrees

**Examples:**
```bash
wt pull-main --stash
wt pull-main --strategy merge
```

### `wt prune-merged`

Remove worktrees for branches merged into base.

**Options:**
- `--base <branch>` - Base branch to check against
- `--protected <branches...>` - Additional protected branches
- `--yes` - Skip confirmation prompt
- `--delete-branch` - Also delete local branches

**Examples:**
```bash
wt prune-merged --yes
wt prune-merged --delete-branch --yes
```

### `wt where <branch>`

Print the path to a worktree (useful for scripting).

**Examples:**
```bash
cd $(wt where my-feature)
code $(wt where my-feature)
```

### `wt gc`

Clean up stale worktree entries and empty directories.

**Examples:**
```bash
wt gc
```

### `wt doctor`

Check configuration and environment health.

**Examples:**
```bash
wt doctor
```

---

## Configuration

Configuration uses TOML with precedence: **CLI args > local > global > defaults**

**Global:** `~/.config/wt/config.toml` (all repos)
**Local:** `<repo>/.wt/config.toml` (specific repo)

### Full Example

```toml
[paths]
worktree_root = "$REPO_ROOT/../$REPO_NAME-worktrees"
worktree_path_template = "$WT_ROOT/$BRANCH_NAME"

[branches]
auto_prefix = "alice/"

[hooks]
post_create_dir = "post_create.d"
continue_on_error = false
timeout_seconds = 300

[update]
base = "origin/main"
strategy = "rebase"  # or "merge", "ff-only"
auto_stash = false

[prune]
protected = ["main", "develop"]
delete_branch_with_worktree = false

[ui]
rich = false
json_indent = 2

[vscode]
create_settings = false
color_borders = true
custom_title = true
```

### Default Behavior

- **Worktree location:** Sibling directory to your repo
  - Repo at `/Users/alice/repos/myproject`
  - Worktrees at `/Users/alice/repos/myproject-worktrees/`
- **Base branch:** `origin/main`
- **Update strategy:** `rebase`
- **Protected branches:** `["main"]`

---

## Understanding Worktrees

### Directory Layout

```
~/repos/
├── myproject/              # Main repo (bare worktree)
└── myproject-worktrees/    # Managed by wt
    ├── feature-a/          # Worktree for feature-a branch
    ├── feature-b/          # Worktree for feature-b branch
    └── hotfix/             # Worktree for hotfix branch
```

Each worktree is a **full checkout** of your repo at a specific branch, sharing the same `.git` object store. Commits in any worktree are visible across all worktrees.

### When to Use Worktrees

**Great for:**
- Parallel feature development
- Long-running branches (experiments, refactors)
- PR reviews without context switching
- Running CI/tests on one branch while working on another

**Maybe not for:**
- Tiny repos where branch switching is instant
- Single-branch workflows
- Situations where disk space is extremely limited

### Worktree Lifecycle

1. **Create** -> `wt new my-feature` (deterministic path, optional hooks)
2. **Work** -> Make commits, push, create PRs
3. **Sync** -> `wt pull-main --stash` (keep up to date with base branch)
4. **Monitor** -> `wt status --rich` (see dirty/ahead/behind at a glance)
5. **Clean** -> `wt prune-merged --yes` (auto-remove merged branches)

---

## Hooks System

Hooks run in lexicographic order from two locations:

1. **Local:** `<repo>/.wt/hooks/post_create.d/`
2. **Global:** `~/.config/wt/hooks/post_create.d/`

**Supported:**
- Shell scripts: `*.sh`
- Python scripts: `*.py`
- Any executable

### Hook Environment

All template variables are injected as `WT_*` environment variables:

```bash
#!/bin/bash
echo "Created worktree for $WT_BRANCH_NAME at $WT_WORKTREE_PATH"
echo "Repo: $WT_REPO_NAME ($WT_REPO_ROOT)"
```

### Hook Examples

**Install dependencies:**
```bash
#!/bin/bash
# .wt/hooks/post_create.d/10-install.sh
npm install
```

**Create feature branch tracking:**
```python
#!/usr/bin/env python3
# .wt/hooks/post_create.d/20-tracking.py
import subprocess
import os

branch = os.environ["WT_BRANCH_NAME"]
subprocess.run(["git", "push", "-u", "origin", branch], check=True)
```

**Initialize database:**
```bash
#!/bin/bash
# .wt/hooks/post_create.d/30-db.sh
docker-compose up -d db
sleep 2
./scripts/migrate.sh
```

---

## Advanced Topics

### Scripting with wt

All commands support JSON output and use exit codes:

```bash
# Get all worktrees as JSON
wt list --json | jq -r '.[] | select(.dirty) | .path'

# Find worktrees behind main
wt status --json | jq -r '.[] | select(.behind_main > 0) | .branch'

# Batch operations
for branch in $(wt list --json | jq -r '.[].branch'); do
  cd $(wt where $branch)
  npm test
done
```

### Concurrent Safety

`wt` uses a repo-scoped advisory lock (`.git/wt.lock`) to prevent concurrent modifications. Operations are serialized per-repo but can run concurrently across different repos.

### Windows Support

Fully supported. Uses PID-based locking on Windows instead of `fcntl`.

### Performance

- Single `git fetch` per operation (not per worktree)
- Serial execution with minimal subprocess overhead
- Stdlib-only, no external dependencies

---

## Troubleshooting

### Stale worktree entries

If you manually deleted a worktree directory:

```bash
wt gc
```

### Hooks timing out

Increase timeout in config:

```toml
[hooks]
timeout_seconds = 600
```

### Wrong branch prefix

Check your `auto_prefix` config:

```bash
wt doctor
```

### Worktree paths not found

Ensure paths don't contain special shell characters. Quote template variables if using spaces.

---

## Design Philosophy

- **No runtime dependencies** - Python stdlib only (>=3.11 for `tomllib`)
- **No prompts** - Fully scriptable, deterministic behavior
- **Git plumbing** - Shell out to git via `subprocess`, no `pygit2`
- **Fast feedback** - Minimal output unless `--rich` requested
- **Safe defaults** - Protected branches, unpushed commit checks, confirmation prompts for destructive actions

---

## Contributing

`wt` is a small, focused tool. Contributions welcome for:
- Bug fixes
- Performance improvements
- Expanded test coverage
- Documentation improvements

**Not in scope:**
- Interactive TUI modes
- Non-git VCS support
- Heavy external dependencies

---

## License

MIT

---

## Related Tools

- [git-worktree(1)](https://git-scm.com/docs/git-worktree) - The underlying git command
- [git-workspace](https://github.com/orf/git-workspace) - Alternative with different workflow
- [worktree.nvim](https://github.com/ThePrimeagen/git-worktree.nvim) - Neovim integration

---

**Built with care for developers who work on multiple branches simultaneously.**
