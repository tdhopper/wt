#!/usr/bin/env python3
"""Create VS Code settings for visual worktree distinction.

This hook creates .vscode/settings.json in new worktrees with:
- Colored window borders (deterministic from branch name)
- Custom window title with repo name and branch

Environment variables from wt:
- WT_BRANCH_NAME: Branch name for this worktree
- WT_REPO_NAME: Repository name
- WT_WORKTREE_PATH: Path to the new worktree
"""

import hashlib
import json
import os
from pathlib import Path
import sys


def calculate_luminance(hex_color: str) -> float:
    """Calculate relative luminance of a color.

    Uses the WCAG formula for relative luminance.

    Args:
        hex_color: 6-character hex color string (without #)

    Returns:
        Relative luminance (0.0 to 1.0)

    """
    # Convert hex to RGB
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255

    # Apply gamma correction
    def gamma_correct(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r = gamma_correct(r)
    g = gamma_correct(g)
    b = gamma_correct(b)

    # Calculate luminance
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def generate_branch_color(branch_name: str) -> str:
    """Generate a deterministic color from a branch name.

    Uses SHA256 hash to create a consistent 6-character hex color.

    Args:
        branch_name: Branch name to hash

    Returns:
        6-character hex color string (without #)

    """
    hash_obj = hashlib.sha256(branch_name.encode())
    return hash_obj.hexdigest()[:6]


def get_contrasting_text_color(bg_color: str) -> str:
    """Get contrasting text color (white or black) for a background.

    Uses WCAG luminance calculation to determine if white or black
    text will have better contrast.

    Args:
        bg_color: 6-character hex color string (without #)

    Returns:
        "#ffffff" for white text or "#000000" for black text

    """
    luminance = calculate_luminance(bg_color)
    # Use white text for dark backgrounds, black for light backgrounds
    return "#ffffff" if luminance < 0.5 else "#000000"


def main():
    """Create VS Code settings for the new worktree."""
    # Get environment variables
    branch_name = os.environ.get("WT_BRANCH_NAME")
    repo_name = os.environ.get("WT_REPO_NAME")
    worktree_path = Path(os.environ.get("WT_WORKTREE_PATH", "."))

    if not branch_name or not repo_name:
        print("Error: Missing required environment variables")
        return 1

    # Check if settings already exist
    vscode_dir = worktree_path / ".vscode"
    settings_file = vscode_dir / "settings.json"

    if settings_file.exists():
        print(f"VS Code settings already exist at {settings_file}, skipping")
        return 0

    # Generate color customizations
    color = generate_branch_color(branch_name)
    text_color = get_contrasting_text_color(color)

    settings = {
        "workbench.colorCustomizations": {
            "titleBar.activeBackground": f"#{color}",
            "titleBar.inactiveBackground": f"#{color}",
            "titleBar.activeForeground": text_color,
            "titleBar.inactiveForeground": text_color,
        },
        "window.title": f"{repo_name}${{separator}}{branch_name}",
    }

    # Create directory and write settings
    vscode_dir.mkdir(parents=True, exist_ok=True)

    with settings_file.open("w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")  # Add trailing newline

    print(f"Created VS Code settings with color #{color}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
