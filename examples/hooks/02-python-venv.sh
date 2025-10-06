#!/bin/bash
# Create and activate Python virtual environment
#
# This hook creates a virtual environment and installs dependencies
# from requirements.txt if it exists.

set -e

if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
    echo "Creating Python virtual environment..."
    python -m venv .venv

    echo "Installing dependencies..."
    if [ -f "pyproject.toml" ]; then
        .venv/bin/pip install -e . --quiet
    elif [ -f "requirements.txt" ]; then
        .venv/bin/pip install -r requirements.txt --quiet
    fi

    echo "✓ Virtual environment ready"
    echo "  Activate with: source .venv/bin/activate"
fi
