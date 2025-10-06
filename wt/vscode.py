"""VS Code settings generation for worktrees."""

import hashlib
import json
from pathlib import Path


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


def create_vscode_settings(
    worktree_path: Path,
    branch_name: str,
    repo_name: str,
    config: dict,
) -> None:
    """Create .vscode/settings.json in a worktree.

    Generates settings that make the VS Code window visually distinct:
    - Colored window borders (deterministic from branch name)
    - Custom window title with repo name and branch

    Args:
        worktree_path: Path to the worktree
        branch_name: Branch name for this worktree
        repo_name: Repository name
        config: Configuration dictionary

    """
    if not config["vscode"]["create_settings"]:
        return

    vscode_dir = worktree_path / ".vscode"
    settings_file = vscode_dir / "settings.json"

    # Don't overwrite existing settings
    if settings_file.exists():
        return

    settings = {}

    # Add color customizations
    if config["vscode"]["color_borders"]:
        color = generate_branch_color(branch_name)
        text_color = get_contrasting_text_color(color)
        settings["workbench.colorCustomizations"] = {
            "titleBar.activeBackground": f"#{color}",
            "titleBar.inactiveBackground": f"#{color}",
            "titleBar.activeForeground": text_color,
            "titleBar.inactiveForeground": text_color,
        }

    # Add custom window title
    if config["vscode"]["custom_title"]:
        settings["window.title"] = f"{repo_name}${{separator}}{branch_name}"

    # Create directory and write settings
    vscode_dir.mkdir(parents=True, exist_ok=True)

    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")  # Add trailing newline
