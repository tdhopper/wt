"""Path template tests - only the failure modes that matter."""

import pytest
from pathlib import Path
from wt.paths import render_path_template, build_template_context


def test_template_renders_all_variables():
    """All documented template variables must work."""
    context = build_template_context(
        repo_root=Path("/repo"),
        wt_root=Path("/wt"),
        branch_name="feature-x",
        source_branch="main"
    )

    template = "$REPO_ROOT/$REPO_NAME/$WT_ROOT/$BRANCH_NAME/$SOURCE_BRANCH"
    result = render_path_template(template, context)

    assert "/repo" in str(result)
    assert "repo" in str(result)  # repo_name comes from repo_root.name
    assert "/wt" in str(result)
    assert "feature-x" in str(result)
    assert "main" in str(result)


def test_template_with_slashes_creates_nested_path():
    """Branch names with slashes must create nested directories."""
    context = build_template_context(
        repo_root=Path("/repo"),
        wt_root=Path("/wt"),
        branch_name="feat/sub/nested",
        source_branch="main"
    )

    template = "$WT_ROOT/$BRANCH_NAME"
    result = render_path_template(template, context)

    expected_path = Path("/wt/feat/sub/nested")
    assert result == expected_path


def test_unknown_variable_raises_error():
    """Using undefined variables should fail loudly, not silently."""
    context = {"REPO_ROOT": "/repo"}

    template = "$REPO_ROOT/$UNKNOWN_VAR"

    with pytest.raises((KeyError, ValueError)):
        render_path_template(template, context)
