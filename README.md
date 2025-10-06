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

## Table of Contents

- [Why wt?](#why-wt)
- [Quick Start](#quick-start)
- [Tutorial: Your First Worktree](#tutorial-your-first-worktree)
- [How-To Guides](#how-to-guides)
- [Configuration](#configuration)
- [Hooks System](#hooks-system)
- [Advanced Topics](#advanced-topics)
- [Troubleshooting](#troubleshooting)

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

**Open worktree in editor:**
```bash
#!/bin/bash
# ~/.config/wt/hooks/post_create.d/02_open.sh
cursor .
```

Make it executable:
```bash
chmod +x ~/.config/wt/hooks/post_create.d/02_open.sh
```

You can use any editor: `code .` for VS Code, `nvim .` for Neovim, etc.

**Note:** On Windows, use a `.bat` or `.cmd` file instead, or ensure you have Git Bash installed to run `.sh` scripts.

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

## License

MIT
