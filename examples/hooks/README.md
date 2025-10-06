# Example Hooks

This directory contains example post-create hooks for `wt`. Copy them to your hooks directory and make them executable to use.

## Installation

### Global hooks (all repositories)

```bash
# Copy hooks you want to use
cp examples/hooks/03-open-vscode.sh ~/.config/wt/hooks/post_create.d/

# Make executable
chmod +x ~/.config/wt/hooks/post_create.d/03-open-vscode.sh
```

### Local hooks (specific repository)

```bash
# From your repository root
cp examples/hooks/01-npm-install.sh .wt/hooks/post_create.d/

# Make executable
chmod +x .wt/hooks/post_create.d/01-npm-install.sh
```

## Available Hooks

### Node.js / JavaScript

- **01-npm-install.sh** - Automatically run `npm install` in new worktrees
- **03-open-vscode.sh** - Open worktree in VS Code (or customize for other editors)
- **07-run-tests.sh** - Run test suite to verify the worktree

### Python

- **02-python-venv.sh** - Create virtual environment and install dependencies
- **07-run-tests.sh** - Run pytest to verify the worktree

### Docker

- **04-docker-compose.sh** - Start Docker Compose services automatically

### Git / Version Control

- **06-git-tracking.py** - Push branch to remote and set up tracking

### Configuration

- **05-setup-env.sh** - Copy `.env` files from main repo to worktree

### Notifications

- **08-notify.sh** - Send desktop notification when worktree is ready (macOS/Linux)

## Customization

All hooks receive environment variables from `wt`:

- `WT_REPO_ROOT` - Path to main repository
- `WT_REPO_NAME` - Repository name
- `WT_BRANCH_NAME` - Branch name
- `WT_WORKTREE_PATH` - Path to the new worktree
- `WT_SOURCE_BRANCH` - Source branch (e.g., `origin/main`)
- `WT_DATE_ISO`, `WT_TIME_ISO` - Timestamps

Edit the hooks to match your workflow and project requirements.

## Hook Naming

Hooks run in alphabetical order. Use numeric prefixes to control execution order:

- `01-` - Dependencies (npm install, venv creation)
- `02-` - Environment setup (env files, config)
- `03-` - Editor/IDE integration
- `90-` - Notifications (run last)

## Tips

- **Test hooks individually**: Run them manually in a worktree to verify they work
- **Use `set -e`**: Makes bash scripts exit on first error
- **Keep hooks fast**: Long-running hooks slow down worktree creation
- **Add output**: Echo messages so users know what's happening
- **Check for files**: Use conditionals to skip hooks when files don't exist

## Creating Your Own Hooks

1. Create a script in your hooks directory
2. Make it executable: `chmod +x your-hook.sh`
3. Test it: `wt new test-branch`
4. Verify with: `wt hooks list`
