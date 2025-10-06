#!/bin/bash
# Run test suite to verify the worktree works
#
# Runs your test suite to catch any issues early.
# Customize the test command for your project.

set -e

if [ -f "package.json" ]; then
    # Node.js project
    if grep -q '"test":' package.json; then
        echo "Running tests..."
        npm test
    fi
elif [ -f "pyproject.toml" ] || [ -f "pytest.ini" ]; then
    # Python project
    echo "Running tests..."
    pytest -q
fi
