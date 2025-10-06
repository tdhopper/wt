"""Simple table formatting using stdlib only."""

from typing import Any


def format_table(headers: list[str], rows: list[list[Any]], rich: bool = False) -> str:
    """
    Format data as a table.

    Args:
        headers: Column headers
        rows: Data rows
        rich: If True, use box-drawing characters (basic implementation)

    Returns:
        Formatted table string
    """
    if not rows:
        return ""

    # Convert all cells to strings
    str_rows = [[str(cell) for cell in row] for row in rows]
    str_headers = [str(h) for h in headers]

    # Calculate column widths
    col_widths = [len(h) for h in str_headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    # Build table
    lines = []

    if rich:
        # Top border
        lines.append(_format_border(col_widths, "top"))

        # Headers
        lines.append(_format_row(str_headers, col_widths, rich=True))

        # Header separator
        lines.append(_format_border(col_widths, "middle"))

        # Rows
        for row in str_rows:
            lines.append(_format_row(row, col_widths, rich=True))

        # Bottom border
        lines.append(_format_border(col_widths, "bottom"))
    else:
        # Simple format
        # Headers
        lines.append(_format_row(str_headers, col_widths, rich=False))

        # Separator
        lines.append(_format_separator(col_widths))

        # Rows
        for row in str_rows:
            lines.append(_format_row(row, col_widths, rich=False))

    return "\n".join(lines)


def _format_row(cells: list[str], widths: list[int], rich: bool) -> str:
    """Format a single row."""
    if rich:
        padded = [cell.ljust(width) for cell, width in zip(cells, widths)]
        return "│ " + " │ ".join(padded) + " │"
    else:
        padded = [cell.ljust(width) for cell, width in zip(cells, widths)]
        return "  ".join(padded)


def _format_separator(widths: list[int]) -> str:
    """Format a simple separator line."""
    return "  ".join(["-" * width for width in widths])


def _format_border(widths: list[int], position: str) -> str:
    """Format a box-drawing border."""
    if position == "top":
        left, mid, right, fill = "┌", "┬", "┐", "─"
    elif position == "middle":
        left, mid, right, fill = "├", "┼", "┤", "─"
    else:  # bottom
        left, mid, right, fill = "└", "┴", "┘", "─"

    segments = [fill * (width + 2) for width in widths]
    return left + mid.join(segments) + right


def print_status_table(statuses: list[Any], rich: bool = False) -> None:
    """
    Print a status table for worktrees.

    Args:
        statuses: List of WorktreeStatus objects
        rich: If True, use rich formatting
    """
    if not statuses:
        print("No worktrees found.")
        return

    headers = ["Branch", "Path", "SHA", "Dirty", "Ahead", "Behind", "Behind Main"]
    rows = []

    for status in statuses:
        rows.append([
            status.branch or "(detached)",
            str(status.path),
            status.sha_short,
            "✓" if status.is_dirty else "",
            f"+{status.ahead}" if status.ahead > 0 else "",
            f"-{status.behind}" if status.behind > 0 else "",
            f"-{status.behind_main}" if status.behind_main > 0 else "",
        ])

    print(format_table(headers, rows, rich=rich))


def print_list_table(worktrees: list[Any], rich: bool = False) -> None:
    """
    Print a list table for worktrees.

    Args:
        worktrees: List of WorktreeInfo objects
        rich: If True, use rich formatting
    """
    if not worktrees:
        print("No worktrees found.")
        return

    headers = ["Branch", "Path", "SHA", "Locked"]
    rows = []

    for wt in worktrees:
        if wt.is_bare:
            continue

        rows.append([
            wt.branch or "(detached)",
            str(wt.path),
            wt.sha[:7] if len(wt.sha) > 7 else wt.sha,
            wt.locked or "",
        ])

    print(format_table(headers, rows, rich=rich))
