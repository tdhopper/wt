#!/bin/bash
# Copy environment configuration from main worktree
#
# This hook copies .env.local or .env from the main repository
# to the new worktree, avoiding the need to reconfigure each time.

set -e

# Look for .env files in the main repo
if [ -f "$WT_REPO_ROOT/.env.local" ]; then
    echo "Copying .env.local from main repo..."
    cp "$WT_REPO_ROOT/.env.local" .env.local
    echo "✓ Environment file copied"
elif [ -f "$WT_REPO_ROOT/.env" ]; then
    echo "Copying .env from main repo..."
    cp "$WT_REPO_ROOT/.env" .env
    echo "✓ Environment file copied"
fi
