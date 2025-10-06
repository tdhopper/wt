"""Simple table formatting using stdlib only."""

import sys
from typing import Any


# ANSI color codes
class Color:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright variants
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_CYAN = "\033[96m"


def colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Color.RESET}"


def format_table(headers: list[str], rows: list[list[Any]], rich: bool = False) -> str:
    """Format data as a table.

    Args:
        headers: Column headers
        rows: Data rows
        rich: If True, use colors (box-drawing removed)

    Returns:
        Formatted table string

    """
    if not rows:
        return ""

    # Convert all cells to strings, but strip ANSI codes for width calculation
    str_rows = [[str(cell) for cell in row] for row in rows]
    str_headers = [str(h) for h in headers]

    # Calculate column widths (strip ANSI codes for accurate width)
    col_widths = [_visible_len(h) for h in str_headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], _visible_len(cell))

    # Build table
    lines = []

    # Headers
    lines.append(_format_row(str_headers, col_widths))

    # Separator
    lines.append(_format_separator(col_widths))

    # Rows
    for row in str_rows:
        lines.append(_format_row(row, col_widths))

    return "\n".join(lines)


def _visible_len(text: str) -> int:
    """Calculate visible length of text, excluding ANSI codes."""
    import re

    # Remove ANSI escape sequences
    ansi_escape = re.compile(r"\033\[[0-9;]*m")
    return len(ansi_escape.sub("", text))


def _pad_with_ansi(text: str, width: int) -> str:
    """Pad text to width, accounting for ANSI codes."""
    visible = _visible_len(text)
    padding = width - visible
    return text + (" " * padding)


def _format_row(cells: list[str], widths: list[int]) -> str:
    """Format a single row."""
    padded = [_pad_with_ansi(cell, width) for cell, width in zip(cells, widths, strict=False)]
    return "  ".join(padded)


def _format_separator(widths: list[int]) -> str:
    """Format a simple separator line."""
    return "  ".join(["-" * width for width in widths])


def _get_dirty_marker() -> str:
    """Get dirty marker that works with current encoding."""
    encoding = sys.stdout.encoding or 'ascii'
    # Try to encode checkmark; fall back to asterisk if it fails
    try:
        "✓".encode(encoding)
        return "✓"
    except (UnicodeEncodeError, LookupError):
        return "*"


def _safe_print(text: str) -> None:
    """Print text with encoding fallback for Windows compatibility."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fall back to UTF-8 with error handling
        sys.stdout.buffer.write(text.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')


def print_status_table(statuses: list[Any], rich: bool = False) -> None:
    """Print a status table for worktrees.

    Args:
        statuses: List of WorktreeStatus objects
        rich: If True, use rich formatting with colors

    """
    if not statuses:
        print("No worktrees found.")
        return

    headers = ["Branch", "Path", "SHA", "Dirty", "Ahead", "Behind", "Behind Main"]

    if rich:
        # Bold headers
        headers = [colorize(h, Color.BOLD) for h in headers]

    # Choose dirty marker based on encoding support
    dirty_marker = _get_dirty_marker()

    rows = []
    for status in statuses:
        # Branch name - cyan for normal, yellow for detached, green if clean and current
        branch_name = status.branch or "(detached)"
        if rich:
            if status.branch:
                # Green if clean and up-to-date, cyan otherwise
                if (
                    not status.is_dirty
                    and status.ahead == 0
                    and status.behind == 0
                    and status.behind_main == 0
                ):
                    branch_name = colorize(branch_name, Color.BRIGHT_GREEN)
                else:
                    branch_name = colorize(branch_name, Color.CYAN)
            else:
                branch_name = colorize("(detached)", Color.YELLOW)

        # Path - dimmed to reduce visual noise
        path_str = str(status.path)
        if rich:
            path_str = colorize(path_str, Color.DIM)

        # SHA - dimmed cyan
        sha_str = status.sha_short
        if rich:
            sha_str = colorize(sha_str, Color.DIM + Color.CYAN)

        # Dirty - red marker if dirty
        dirty_str = dirty_marker if status.is_dirty else ""
        if rich and dirty_str:
            dirty_str = colorize(dirty_str, Color.BRIGHT_RED)

        # Ahead - green if ahead
        ahead_str = f"+{status.ahead}" if status.ahead > 0 else ""
        if rich and ahead_str:
            ahead_str = colorize(ahead_str, Color.BRIGHT_GREEN)

        # Behind - red if behind
        behind_str = f"-{status.behind}" if status.behind > 0 else ""
        if rich and behind_str:
            behind_str = colorize(behind_str, Color.BRIGHT_RED)

        # Behind main - yellow if behind
        behind_main_str = f"-{status.behind_main}" if status.behind_main > 0 else ""
        if rich and behind_main_str:
            behind_main_str = colorize(behind_main_str, Color.YELLOW)

        rows.append(
            [
                branch_name,
                path_str,
                sha_str,
                dirty_str,
                ahead_str,
                behind_str,
                behind_main_str,
            ]
        )

    _safe_print(format_table(headers, rows, rich=rich))


def print_list_table(worktrees: list[Any], rich: bool = False) -> None:
    """Print a list table for worktrees.

    Args:
        worktrees: List of WorktreeInfo objects
        rich: If True, use rich formatting with colors

    """
    if not worktrees:
        print("No worktrees found.")
        return

    headers = ["Branch", "Path", "SHA", "Locked"]

    if rich:
        # Bold headers
        headers = [colorize(h, Color.BOLD) for h in headers]

    rows = []
    for wt in worktrees:
        if wt.is_bare:
            continue

        # Branch name - cyan for normal, yellow for detached
        branch_name = wt.branch or "(detached)"
        if rich:
            if wt.branch:
                branch_name = colorize(branch_name, Color.CYAN)
            else:
                branch_name = colorize("(detached)", Color.YELLOW)

        # Path - dimmed
        path_str = str(wt.path)
        if rich:
            path_str = colorize(path_str, Color.DIM)

        # SHA - dimmed cyan
        sha_str = wt.sha[:7] if len(wt.sha) > 7 else wt.sha
        if rich:
            sha_str = colorize(sha_str, Color.DIM + Color.CYAN)

        # Locked - red if locked
        locked_str = wt.locked or ""
        if rich and locked_str:
            locked_str = colorize(locked_str, Color.BRIGHT_RED)

        rows.append(
            [
                branch_name,
                path_str,
                sha_str,
                locked_str,
            ]
        )

    _safe_print(format_table(headers, rows, rich=rich))
