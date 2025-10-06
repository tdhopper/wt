#!/bin/bash
# Install npm dependencies in the new worktree
#
# This hook automatically runs `npm install` after creating a worktree,
# ensuring dependencies are ready to use.

set -e

echo "Installing npm dependencies..."
npm install --quiet

echo "✓ Dependencies installed"
