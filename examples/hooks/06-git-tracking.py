#!/usr/bin/env python3
"""Push branch to remote and set up tracking.

This hook pushes the new branch to origin and sets up tracking,
so you can immediately start pushing and pulling.
"""

import os
import subprocess
import sys


branch = os.environ["WT_BRANCH_NAME"]

print(f"Setting up remote tracking for {branch}...")

try:
    # Push to origin and set upstream
    subprocess.run(
        ["git", "push", "-u", "origin", branch],
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"✓ Branch {branch} pushed to origin with tracking")
except subprocess.CalledProcessError as e:
    print(f"✗ Failed to push branch: {e.stderr}", file=sys.stderr)
    sys.exit(1)
