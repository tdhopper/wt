"""Command-line interface for wt."""

import argparse
import json
import os
from pathlib import Path
import sys

from . import config, gitutil, hooks, lock, paths, status, table, vscode


def cmd_new(args, cfg, repo_root):
    """Create a new worktree."""
    # Keep original branch name for folder path
    folder_branch_name = args.branch

    # Apply auto_prefix for git branch name
    git_branch_name = args.branch
    auto_prefix = cfg["branches"]["auto_prefix"]
    if auto_prefix and not git_branch_name.startswith(auto_prefix):
        git_branch_name = auto_prefix + git_branch_name

    # Fetch origin
    print("Fetching from origin...", flush=True)
    gitutil.fetch_origin(repo_root)

    # Resolve source branch (auto-detect if default was used)
    source_branch = args.from_branch
    if source_branch == "origin/main":
        source_branch = gitutil.get_default_branch(repo_root)

    # Check if source branch exists
    if not gitutil.remote_ref_exists(source_branch, repo_root):
        print(f"Error: Source branch '{source_branch}' does not exist", file=sys.stderr)
        sys.exit(1)

    # Check if branch already has a worktree (using git branch name)
    existing_path = gitutil.worktree_path_for_branch(git_branch_name, repo_root)
    if existing_path:
        print(
            f"Error: Branch '{git_branch_name}' is already checked out at: {existing_path}",
            file=sys.stderr,
        )
        print("       Git does not allow the same branch in multiple worktrees", file=sys.stderr)
        sys.exit(1)

    # Resolve worktree path (using folder branch name without prefix)
    worktree_path = paths.resolve_worktree_path(repo_root, folder_branch_name, source_branch, cfg)

    # Check if directory exists
    if worktree_path.exists():
        if args.force and not any(worktree_path.iterdir()):
            # Empty directory, remove it
            worktree_path.rmdir()
        else:
            print(f"Error: Directory already exists: {worktree_path}", file=sys.stderr)
            print("Use --force to override if directory is empty", file=sys.stderr)
            sys.exit(1)

    # Create parent directories
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if branch exists (using git branch name)
    create_branch = not gitutil.branch_exists(git_branch_name, repo_root)

    # Create worktree (using git branch name)
    print(f"Creating worktree for '{git_branch_name}' at {worktree_path}...", flush=True)
    gitutil.create_worktree(repo_root, worktree_path, git_branch_name, source_branch, create_branch)

    # Set upstream tracking if requested
    if args.track:
        upstream = f"origin/{git_branch_name}"
        if gitutil.remote_ref_exists(upstream, repo_root):
            gitutil.set_upstream(worktree_path, git_branch_name, upstream)
            print(f"Set upstream to {upstream}", flush=True)

    # Run post-create hooks (use git branch name in context)
    wt_root = paths.resolve_worktree_root(repo_root, cfg)
    context = paths.build_template_context(
        repo_root, wt_root, git_branch_name, source_branch, worktree_path
    )

    local_config_path = config.get_local_config_path(repo_root)
    global_config_path = config.get_global_config_path()

    # Create VS Code settings if enabled
    vscode.create_vscode_settings(worktree_path, git_branch_name, repo_root.name, cfg)

    try:
        hooks.run_post_create_hooks(
            worktree_path,
            context,
            local_config_path if local_config_path.exists() else None,
            global_config_path,
            cfg,
        )
    except hooks.HookError as e:
        print(f"Error running hooks: {e}", file=sys.stderr)
        sys.exit(1)

    print(worktree_path)


def cmd_list(args, cfg, repo_root):
    """List all worktrees."""
    worktrees = gitutil.list_worktrees(repo_root)

    if args.json:
        data = [
            {
                "path": str(wt.path),
                "branch": wt.branch,
                "sha": wt.sha,
                "is_bare": wt.is_bare,
                "locked": wt.locked,
            }
            for wt in worktrees
        ]
        print(json.dumps(data, indent=cfg["ui"]["json_indent"]))
    else:
        table.print_list_table(worktrees, rich=cfg["ui"]["rich"])


def cmd_status(args, cfg, repo_root):
    """Show status of all worktrees."""
    # Fetch for accurate status
    print("Fetching from origin...", flush=True)
    gitutil.fetch_origin(repo_root)

    # Resolve base branch (auto-detect if default was used)
    base_branch = cfg["update"]["base"]
    if base_branch == "origin/main":
        base_branch = gitutil.get_default_branch(repo_root)

    statuses = status.get_all_worktree_statuses(repo_root, base_branch)

    if args.json:
        data = [
            {
                "path": str(s.path),
                "branch": s.branch,
                "sha": s.sha_short,
                "dirty": s.is_dirty,
                "ahead": s.ahead,
                "behind": s.behind,
                "behind_main": s.behind_main,
                "locked": s.locked,
            }
            for s in statuses
        ]
        print(json.dumps(data, indent=cfg["ui"]["json_indent"]))
    else:
        use_rich = args.rich if args.rich is not None else cfg["ui"]["rich"]
        table.print_status_table(statuses, rich=use_rich)


def cmd_rm(args, cfg, repo_root):
    """Remove a worktree."""
    branch_name = args.branch

    # Apply auto_prefix if configured
    auto_prefix = cfg["branches"]["auto_prefix"]
    if auto_prefix and not branch_name.startswith(auto_prefix):
        branch_name = auto_prefix + branch_name

    # Find worktree
    worktree_path = gitutil.worktree_path_for_branch(branch_name, repo_root)
    if not worktree_path:
        print(f"Error: No worktree found for branch '{branch_name}'", file=sys.stderr)
        sys.exit(1)

    # Confirm if not --yes
    if not args.yes:
        response = input(f"Remove worktree at {worktree_path}? [y/N] ")
        if response.lower() != "y":
            print("Aborted")
            return

    # Remove worktree
    print(f"Removing worktree at {worktree_path}...", flush=True)
    gitutil.remove_worktree(repo_root, worktree_path, force=args.force)

    # Delete branch if requested
    if args.delete_branch:
        # Check for unpushed commits unless --force
        if not args.force:
            unpushed = gitutil.count_unpushed_commits(worktree_path, branch_name)
            if unpushed > 0:
                print(
                    f"Error: Branch '{branch_name}' has {unpushed} unpushed commits",
                    file=sys.stderr,
                )
                print("Use --force to delete anyway", file=sys.stderr)
                sys.exit(1)

        print(f"Deleting branch '{branch_name}'...", flush=True)
        gitutil.delete_branch(repo_root, branch_name, force=args.force)

    print("Done")


def cmd_prune_merged(args, cfg, repo_root):
    """Prune worktrees for merged branches."""
    # Fetch
    print("Fetching from origin...", flush=True)
    gitutil.fetch_origin(repo_root)

    # Resolve base branch (auto-detect if default was used)
    base_branch = args.base or cfg["update"]["base"]
    if base_branch == "origin/main":
        base_branch = gitutil.get_default_branch(repo_root)

    protected = set(args.protected or cfg["prune"]["protected"])

    # Get merged branches
    merged = gitutil.list_merged_branches(repo_root, base_branch)

    # Get current branch
    current = gitutil.get_current_branch(repo_root)

    # Filter out protected and current
    to_prune = [b for b in merged if b not in protected and b != current]

    if not to_prune:
        print("No branches to prune")
        return

    print(f"Found {len(to_prune)} merged branches:")
    for branch in to_prune:
        print(f"  - {branch}")

    # Confirm if not --yes
    if not args.yes:
        response = input("Prune these branches? [y/N] ")
        if response.lower() != "y":
            print("Aborted")
            return

    # Prune each branch
    for branch in to_prune:
        # Find worktree
        worktree_path = gitutil.worktree_path_for_branch(branch, repo_root)

        if worktree_path:
            print(f"Removing worktree for '{branch}'...", flush=True)
            gitutil.remove_worktree(repo_root, worktree_path, force=True)

        # Delete branch if configured
        if args.delete_branch or cfg["prune"]["delete_branch_with_worktree"]:
            print(f"Deleting branch '{branch}'...", flush=True)
            gitutil.delete_branch(repo_root, branch, force=False)

    print("Done")


def cmd_pull_main(args, cfg, repo_root):
    """Pull main into all worktrees."""
    # Fetch
    print("Fetching from origin...", flush=True)
    gitutil.fetch_origin(repo_root)

    # Resolve base branch (auto-detect if default was used)
    base_branch = cfg["update"]["base"]
    if base_branch == "origin/main":
        base_branch = gitutil.get_default_branch(repo_root)

    strategy = args.strategy or cfg["update"]["strategy"]
    auto_stash = args.stash if args.stash is not None else cfg["update"]["auto_stash"]

    # Get all worktrees
    worktrees = gitutil.list_worktrees(repo_root)

    for wt in worktrees:
        if wt.is_bare:
            continue

        print(f"\nUpdating {wt.branch or '(detached)'} at {wt.path}...", flush=True)

        # Check if dirty
        is_dirty = gitutil.is_dirty(wt.path)

        if is_dirty and not auto_stash:
            print("  Skipping (dirty, use --stash to auto-stash)", flush=True)
            continue

        # Stash if needed
        stashed = False
        if is_dirty and auto_stash:
            print("  Stashing changes...", flush=True)
            gitutil.stash_push(wt.path)
            stashed = True

        # Update
        try:
            gitutil.update_with_strategy(wt.path, base_branch, strategy)
            print(f"  Updated with {strategy}", flush=True)
        except gitutil.GitError as e:
            print(f"  Error: {e}", file=sys.stderr)
            if stashed:
                print("  Warning: Changes are stashed, run 'git stash pop' manually", flush=True)
            continue

        # Pop stash if we stashed
        if stashed:
            try:
                gitutil.stash_pop(wt.path)
                print("  Popped stash", flush=True)
            except gitutil.GitError as e:
                print(f"  Warning: Failed to pop stash: {e}", flush=True)
                print("  Run 'git stash pop' manually to recover changes", flush=True)

    print("\nDone")


def cmd_where(args, cfg, repo_root):
    """Print path to a worktree."""
    branch_name = args.branch

    # Apply auto_prefix if configured
    auto_prefix = cfg["branches"]["auto_prefix"]
    if auto_prefix and not branch_name.startswith(auto_prefix):
        branch_name = auto_prefix + branch_name

    # Find worktree
    worktree_path = gitutil.worktree_path_for_branch(branch_name, repo_root)
    if not worktree_path:
        print(f"Error: No worktree found for branch '{branch_name}'", file=sys.stderr)
        sys.exit(1)

    print(worktree_path)


def cmd_open(args, cfg, repo_root):
    """Print path to a worktree (alias for where)."""
    cmd_where(args, cfg, repo_root)


def cmd_gc(_args, cfg, repo_root):
    """Clean up stale worktrees."""
    print("Pruning stale worktree entries...", flush=True)
    gitutil.prune_worktrees(repo_root)

    # Clean up empty directories
    wt_root = paths.resolve_worktree_root(repo_root, cfg)

    if wt_root.exists():
        print(f"Cleaning up empty directories in {wt_root}...", flush=True)

        # Get valid worktree paths
        worktrees = gitutil.list_worktrees(repo_root)
        valid_paths = {wt.path for wt in worktrees}

        # Remove empty directories
        removed = 0
        for item in wt_root.rglob("*"):
            if item.is_dir() and not any(item.iterdir()) and item not in valid_paths:
                item.rmdir()
                removed += 1

        print(f"Removed {removed} empty directories", flush=True)

    print("Done")


def cmd_hooks_init(args, cfg, repo_root):
    """Initialize hooks directory with optional template."""
    hook_dir_name = cfg["hooks"]["post_create_dir"]

    # Determine target directory
    if args.local:
        local_config_path = config.get_local_config_path(repo_root)
        hook_dir = local_config_path.parent / hook_dir_name
        scope = "local"
    else:
        global_config_path = config.get_global_config_path()
        hook_dir = global_config_path.parent / hook_dir_name
        scope = "global"

    # Create directory
    if hook_dir.exists():
        print(f"Hook directory already exists: {hook_dir}")
    else:
        hook_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created {scope} hook directory: {hook_dir}")

    # Create template if requested
    if args.template:
        template_path = hook_dir / "00-example.sh"

        if template_path.exists() and not args.force:
            print(f"Template already exists: {template_path}")
            print("Use --force to overwrite")
            sys.exit(1)

        template_content = """#!/bin/bash
# Example post-create hook for wt
#
# This hook runs after a new worktree is created.
# The following environment variables are available:
#
#   WT_REPO_ROOT      - Path to main repository
#   WT_REPO_NAME      - Repository name
#   WT_WT_ROOT        - Worktree root directory
#   WT_BRANCH_NAME    - New branch name
#   WT_SOURCE_BRANCH  - Source branch (e.g., origin/main)
#   WT_WORKTREE_PATH  - Path to new worktree
#   WT_DATE_ISO       - Current date (YYYY-MM-DD)
#   WT_TIME_ISO       - Current time (HH:MM:SS)
#
# Example: Echo a message when creating worktrees
echo "Setting up worktree: $WT_BRANCH_NAME"

# Example: Install dependencies (uncomment to use)
# echo "Installing dependencies..."
# npm install

# Example: Open in editor (uncomment to use)
# code .

# Add your setup commands here
"""

        template_path.write_text(template_content)
        template_path.chmod(0o755)  # Make executable

        print(f"Created template hook: {template_path}")
        print("Hook is executable and ready to use")
        print("\nEdit the hook to customize your setup:")
        print(f"  {template_path}")


def cmd_hooks_list(_args, cfg, repo_root):
    """List all hooks and their status."""
    hook_dir_name = cfg["hooks"]["post_create_dir"]

    local_config_path = config.get_local_config_path(repo_root)
    global_config_path = config.get_global_config_path()

    # Determine hook directories
    local_hook_dir = local_config_path.parent / hook_dir_name
    global_hook_dir = global_config_path.parent / hook_dir_name

    # Get all hooks (always pass local_config_path, hooks can exist without config file)
    executable_hooks = hooks.discover_hooks(
        local_config_path,
        global_config_path,
        hook_dir_name,
    )

    non_executable_hooks = hooks.find_non_executable_hooks(
        local_config_path,
        global_config_path,
        hook_dir_name,
    )

    # Local hooks
    print(f"Local hooks ({local_hook_dir}):")
    if local_hook_dir.exists():
        local_executable = [h for h in executable_hooks if h.is_relative_to(local_hook_dir)]
        local_non_executable = [h for h in non_executable_hooks if h.is_relative_to(local_hook_dir)]

        if local_executable or local_non_executable:
            for hook in local_executable:
                print(f"  ✓ {hook.name} (executable)")
            for hook in local_non_executable:
                print(f"  ✗ {hook.name} (not executable - run: chmod +x {hook})")
        else:
            print("  (none)")
    else:
        print("  (directory does not exist)")
        print("  Run: wt hooks init --local")

    print()

    # Global hooks
    print(f"Global hooks ({global_hook_dir}):")
    if global_hook_dir.exists():
        global_executable = [h for h in executable_hooks if h.is_relative_to(global_hook_dir)]
        global_non_executable = [
            h for h in non_executable_hooks if h.is_relative_to(global_hook_dir)
        ]

        if global_executable or global_non_executable:
            for hook in global_executable:
                print(f"  ✓ {hook.name} (executable)")
            for hook in global_non_executable:
                print(f"  ✗ {hook.name} (not executable - run: chmod +x {hook})")
        else:
            print("  (none)")
    else:
        print("  (directory does not exist)")
        print("  Run: wt hooks init")

    # Summary
    total_executable = len(executable_hooks)
    total_non_executable = len(non_executable_hooks)

    print()
    print(f"Summary: {total_executable} executable, {total_non_executable} non-executable")

    if total_non_executable > 0:
        print("\nTo make hooks executable, run:")
        for hook in non_executable_hooks:
            print(f"  chmod +x {hook}")


def cmd_doctor(_args, cfg, repo_root):  # noqa: PLR0912
    """Check configuration and environment."""
    print("Checking wt configuration and environment...\n")

    issues = []

    # Check git
    try:
        gitutil.git("--version", cwd=repo_root)
        print("✓ git is available")
    except gitutil.GitError as e:
        print("✗ git is not available")
        issues.append(str(e))

    # Check repo
    try:
        print(f"✓ Repository root: {repo_root}")
    except Exception as e:
        print("✗ Repository discovery failed")
        issues.append(str(e))

    # Check config
    global_config = config.get_global_config_path()
    if global_config.exists():
        print(f"✓ Global config: {global_config}")
    else:
        print(f"  No global config (optional): {global_config}")

    local_config = config.get_local_config_path(repo_root)
    if local_config.exists():
        print(f"✓ Local config: {local_config}")
    else:
        print(f"  No local config (optional): {local_config}")

    # Check worktree root
    wt_root = paths.resolve_worktree_root(repo_root, cfg)
    print(f"✓ Worktree root: {wt_root}")

    if wt_root.exists():
        if not os.access(wt_root, os.W_OK):
            print("✗ Worktree root is not writable")
            issues.append(f"Cannot write to {wt_root}")
        else:
            print("✓ Worktree root is writable")
    else:
        print("  Worktree root does not exist yet (will be created)")

    # Check hooks
    hook_dir = cfg["hooks"]["post_create_dir"]

    all_hooks = hooks.discover_hooks(
        local_config if local_config.exists() else None, global_config, hook_dir
    )

    if all_hooks:
        # Count local vs global by checking paths
        local_hook_dir = local_config.parent / hook_dir if local_config.exists() else None
        global_hook_dir = global_config.parent / hook_dir

        local_count = sum(
            1 for h in all_hooks if local_hook_dir and h.is_relative_to(local_hook_dir)
        )
        global_count = sum(1 for h in all_hooks if h.is_relative_to(global_hook_dir))

        print(f"✓ Found {local_count} local + {global_count} global hooks")
        for hook in all_hooks:
            print(f"  - {hook}")
    else:
        print("  No hooks configured (optional)")

    # Check for non-executable hooks
    non_executable = hooks.find_non_executable_hooks(
        local_config if local_config.exists() else None, global_config, hook_dir
    )
    if non_executable:
        print(f"✗ Found {len(non_executable)} non-executable hook(s):")
        for hook in non_executable:
            print(f"  - {hook}")
            print(f"    Fix: chmod +x {hook}")
        issues.append(f"{len(non_executable)} hooks are not executable")

    # Summary
    print()
    if issues:
        print(f"Found {len(issues)} issues:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("All checks passed ✓")


def main():  # noqa: PLR0915, PLR0912
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="wt - Zero-friction git worktree manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--repo", type=Path, help="Repository path (default: auto-discover)")
    parser.add_argument("--config", type=Path, help="Config file override")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # new
    parser_new = subparsers.add_parser("new", help="Create a new worktree")
    parser_new.add_argument("branch", help="Branch name")
    parser_new.add_argument(
        "--from", dest="from_branch", default="origin/main", help="Source branch"
    )
    parser_new.add_argument("--track", action="store_true", help="Set upstream tracking")
    parser_new.add_argument("--force", action="store_true", help="Force creation, remove empty dir")

    # list
    parser_list = subparsers.add_parser("list", help="List all worktrees")
    parser_list.add_argument("--json", action="store_true", help="Output as JSON")

    # status
    parser_status = subparsers.add_parser("status", help="Show worktree status")
    parser_status.add_argument("--json", action="store_true", help="Output as JSON")
    parser_status.add_argument(
        "--rich", action="store_true", default=None, help="Use rich formatting"
    )

    # rm
    parser_rm = subparsers.add_parser("rm", help="Remove a worktree")
    parser_rm.add_argument("branch", help="Branch name")
    parser_rm.add_argument("--yes", action="store_true", help="Skip confirmation")
    parser_rm.add_argument("--delete-branch", action="store_true", help="Also delete the branch")
    parser_rm.add_argument("--force", action="store_true", help="Force deletion")

    # prune-merged
    parser_prune = subparsers.add_parser("prune-merged", help="Prune merged branches")
    parser_prune.add_argument("--base", help="Base branch (default: from config)")
    parser_prune.add_argument(
        "--protected", nargs="*", help="Protected branches (default: from config)"
    )
    parser_prune.add_argument("--yes", action="store_true", help="Skip confirmation")
    parser_prune.add_argument("--delete-branch", action="store_true", help="Also delete branches")

    # pull-main
    parser_pull = subparsers.add_parser("pull-main", help="Update all worktrees from main")
    parser_pull.add_argument("--base", help="Base branch (default: from config)")
    parser_pull.add_argument(
        "--strategy", choices=["rebase", "merge", "ff-only"], help="Update strategy"
    )
    parser_pull.add_argument("--stash", action="store_true", help="Auto-stash dirty trees")

    # where
    parser_where = subparsers.add_parser("where", help="Print worktree path")
    parser_where.add_argument("branch", help="Branch name")

    # open
    parser_open = subparsers.add_parser("open", help="Print worktree path (alias for where)")
    parser_open.add_argument("branch", help="Branch name")

    # gc
    subparsers.add_parser("gc", help="Clean up stale worktrees")

    # doctor
    subparsers.add_parser("doctor", help="Check configuration")

    # hooks
    parser_hooks = subparsers.add_parser("hooks", help="Manage hooks")
    hooks_subparsers = parser_hooks.add_subparsers(dest="hooks_command", help="Hooks command")

    # hooks init
    parser_hooks_init = hooks_subparsers.add_parser("init", help="Initialize hooks directory")
    parser_hooks_init.add_argument(
        "--local", action="store_true", help="Create local hooks directory"
    )
    parser_hooks_init.add_argument(
        "--template", action="store_true", help="Create example template hook"
    )
    parser_hooks_init.add_argument(
        "--force", action="store_true", help="Overwrite existing template"
    )

    # hooks list
    hooks_subparsers.add_parser("list", help="List all hooks and their status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Discover repo root (except for doctor which handles errors)
    try:
        repo_root = paths.discover_repo_root(args.repo) if args.repo else paths.discover_repo_root()
    except paths.RepoDiscoveryError as e:
        if args.command != "doctor":
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        repo_root = Path.cwd()  # For doctor, use cwd

    # Load config
    cfg = config.load_config(repo_root)

    # Acquire lock
    with lock.RepoLock(repo_root):
        # Dispatch command
        if args.command == "new":
            cmd_new(args, cfg, repo_root)
        elif args.command == "list":
            cmd_list(args, cfg, repo_root)
        elif args.command == "status":
            cmd_status(args, cfg, repo_root)
        elif args.command == "rm":
            cmd_rm(args, cfg, repo_root)
        elif args.command == "prune-merged":
            cmd_prune_merged(args, cfg, repo_root)
        elif args.command == "pull-main":
            cmd_pull_main(args, cfg, repo_root)
        elif args.command == "where":
            cmd_where(args, cfg, repo_root)
        elif args.command == "open":
            cmd_open(args, cfg, repo_root)
        elif args.command == "gc":
            cmd_gc(args, cfg, repo_root)
        elif args.command == "doctor":
            cmd_doctor(args, cfg, repo_root)
        elif args.command == "hooks":
            if args.hooks_command == "init":
                cmd_hooks_init(args, cfg, repo_root)
            elif args.hooks_command == "list":
                cmd_hooks_list(args, cfg, repo_root)
            else:
                print("Usage: wt hooks {init,list}", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
