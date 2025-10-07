![https://pypi.org/project/wt-cli/](https://img.shields.io/pypi/v/wt-cli)

<div align="center">
  <img src="https://tdhopper.com/images/wt.png" alt="wt logo" width="200">
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

> [!IMPORTANT]
> Requires Python ≥3.11 (for native TOML support via `tomllib`)

```bash
uv tool install wt-cli

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

> [!TIP]
> Branch names containing slashes (e.g., `feature/login`) automatically create nested directories. Useful for organizing worktrees by category.

### Run commands after creating worktrees

Hooks automatically run scripts after creating a new worktree. Use them to install dependencies, open editors, or initialize databases.

**Quick start:**

```bash
# Create global hooks directory with example template
wt hooks init --template

# Edit the template to customize
# ~/.config/wt/hooks/post_create.d/00-example.sh

# Or create local hooks for a specific repo
wt hooks init --local --template
```

> [!TIP]
> See **[examples/hooks/](examples/hooks/)** for ready-to-use hook examples including npm install, Python venv setup, VS Code integration, Docker Compose, and more. Copy them to your hooks directory to get started quickly.

**Example: Install dependencies automatically**

Create a hook file at `~/repos/myproject/.wt/hooks/post_create.d/01-install.sh`:

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

Or use `wt hooks init --local --template` to create an example hook that's already executable.

**Check your hooks:**

```bash
# List all hooks and their status
wt hooks list
```

**Hook environment variables:**
- `WT_REPO_ROOT`, `WT_REPO_NAME`
- `WT_BRANCH_NAME`, `WT_SOURCE_BRANCH`
- `WT_WORKTREE_PATH`
- `WT_DATE_ISO`, `WT_TIME_ISO`
- All template variables available as `WT_*`

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

Prevent accidental deletion during batch operations:

```toml
[prune]
protected = ["main", "develop", "staging"]
delete_branch_with_worktree = false
```

> [!TIP]
> Protected branches only affect `wt prune-merged` (batch cleanup). They do not prevent `wt rm <branch>` (explicit removal), since explicitly naming a branch indicates intent.

### Find and jump to worktrees

```bash
# Print path (useful for scripting)
wt where my-feature

# Jump to worktree
cd $(wt where my-feature)

# Open in editor
code $(wt where my-feature)
```

### Recreate worktrees for existing branches

If you removed a worktree but kept the branch, you can recreate it:

```bash
# Previously: wt rm my-feature (without --delete-branch)
# Branch still exists, but no worktree

# Recreate the worktree for the existing branch
wt new my-feature

# This checks out the existing branch at a new worktree location
```

> [!WARNING]
> You cannot create multiple worktrees for the same branch. Git prevents the same branch from being checked out in multiple locations simultaneously.

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

> [!NOTE]
> Settings are only created if `.vscode/settings.json` doesn't already exist, so existing customizations are preserved.

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

Hooks automatically run scripts after creating new worktrees, enabling workflow automation.

### Setting Up Hooks

**Initialize hooks with a template:**

```bash
# Create global hooks directory with example template
wt hooks init --template

# Create local hooks directory (repo-specific)
wt hooks init --local --template

# List all configured hooks
wt hooks list
```

The `--template` flag creates an example hook (`00-example.sh`) that documents all available environment variables and includes common examples.

### Hook Execution

Hooks run in two phases:

1. **Local hooks first:** All executable files from `<repo>/.wt/hooks/post_create.d/` (sorted alphabetically)
2. **Global hooks second:** All executable files from `~/.config/wt/hooks/post_create.d/` (sorted alphabetically)

This gives repo-specific hooks priority to run before global hooks.

**Supported:**
- Shell scripts: `*.sh`
- Python scripts: `*.py`
- Any executable

> [!TIP]
> Use `wt hooks list` to check which hooks are configured and whether they're executable. Non-executable hooks are detected and you'll get instructions to fix them with `chmod +x`.

### Hook Environment

> [!NOTE]
> All template variables are automatically injected as `WT_*` environment variables into your hooks.

```bash
#!/bin/bash
echo "Created worktree for $WT_BRANCH_NAME at $WT_WORKTREE_PATH"
echo "Repo: $WT_REPO_NAME ($WT_REPO_ROOT)"
```

### Hook Examples

See **[examples/hooks/](examples/hooks/)** for a complete collection of ready-to-use hooks. Here are a few quick examples:

**Install dependencies:**
```bash
#!/bin/bash
# .wt/hooks/post_create.d/01-npm-install.sh
set -e
echo "Installing npm dependencies..."
npm install --quiet
echo "✓ Dependencies installed"
```

**Open worktree in editor:**
```bash
#!/bin/bash
# ~/.config/wt/hooks/post_create.d/03-open-vscode.sh
code .
```

**Python virtual environment:**
```bash
#!/bin/bash
# .wt/hooks/post_create.d/02-python-venv.sh
set -e
if [ -f "requirements.txt" ]; then
    echo "Creating Python virtual environment..."
    python -m venv .venv
    .venv/bin/pip install -r requirements.txt --quiet
    echo "✓ Virtual environment ready"
fi
```

**Copy environment files from main repo:**
```bash
#!/bin/bash
# .wt/hooks/post_create.d/05-setup-env.sh
set -e
if [ -f "$WT_REPO_ROOT/.env.local" ]; then
    cp "$WT_REPO_ROOT/.env.local" .env.local
    echo "✓ Environment file copied"
fi
```

> [!TIP]
> Copy hooks from [examples/hooks/](examples/hooks/) to your hooks directory and make them executable with `chmod +x`. See the [examples README](examples/hooks/README.md) for installation instructions and more examples.

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

> [!IMPORTANT]
> `wt` uses a repo-scoped advisory lock (`.git/wt.lock`) to prevent concurrent modifications. Operations are serialized per-repo but can run concurrently across different repos.

### Windows Support

Fully supported. Uses PID-based locking on Windows instead of `fcntl`.

### Performance

- Single `git fetch` per operation (not per worktree)
- Serial execution with minimal subprocess overhead
- Stdlib-only, no external dependencies

---

## Troubleshooting

### Stale worktree entries

> [!CAUTION]
> Manually deleting worktree directories (with `rm -rf` or file explorer) leaves stale git entries. Always use `wt rm` instead.

If you already manually deleted a worktree directory:

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
