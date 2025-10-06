"""Path template tests - only the failure modes that matter."""

from pathlib import Path

import pytest

from wt.paths import build_template_context, render_path_template


def test_template_renders_all_variables(tmp_path):
    """All documented template variables must work."""
    # Use platform-appropriate temporary paths
    repo_root = tmp_path / "repo"
    wt_root = tmp_path / "wt"

    context = build_template_context(
        repo_root=repo_root,
        wt_root=wt_root,
        branch_name="feature-x",
        source_branch="main"
    )

    # Test a sensible template (don't concatenate multiple absolute paths)
    template = "$WT_ROOT/$REPO_NAME-$BRANCH_NAME-from-$SOURCE_BRANCH"
    result = render_path_template(template, context)

    # Result should be wt_root / "repo-feature-x-from-main"
    result_str = str(result)
    assert str(wt_root) in result_str
    assert "repo" in result_str  # repo_name comes from repo_root.name
    assert "feature-x" in result_str
    assert "main" in result_str

    # Also test that REPO_ROOT works in isolation
    template2 = "$REPO_ROOT/worktrees/$BRANCH_NAME"
    result2 = render_path_template(template2, context)
    assert str(repo_root) in str(result2)


def test_template_with_slashes_creates_nested_path(tmp_path):
    """Branch names with slashes must create nested directories."""
    # Use platform-appropriate temporary paths
    repo_root = tmp_path / "repo"
    wt_root = tmp_path / "wt"

    context = build_template_context(
        repo_root=repo_root,
        wt_root=wt_root,
        branch_name="feat/sub/nested",
        source_branch="main",
    )

    template = "$WT_ROOT/$BRANCH_NAME"
    result = render_path_template(template, context)

    expected_path = wt_root / "feat" / "sub" / "nested"
    assert result == expected_path


def test_unknown_variable_raises_error():
    """Using undefined variables should fail loudly, not silently."""
    context = {"REPO_ROOT": "/repo"}

    template = "$REPO_ROOT/$UNKNOWN_VAR"

    with pytest.raises((KeyError, ValueError)):
        render_path_template(template, context)
