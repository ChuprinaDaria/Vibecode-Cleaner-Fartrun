"""Tests for git status --porcelain parsing (Task 16).

The old parser had no branch for unstaged deletions (` D`),
renames, or unmerged entries, so counts didn't reconcile.
"""
from __future__ import annotations

from core.health.git_survival import parse_git_status_porcelain


def test_unstaged_deletion_counted():
    out = " D core/tips.py\n"
    c = parse_git_status_porcelain(out)
    assert c.deleted == ["core/tips.py"]
    assert c.staged == []
    assert c.modified == []
    assert c.total == 1


def test_unstaged_modification_counted():
    out = " M gui/app/main.py\n"
    c = parse_git_status_porcelain(out)
    assert c.modified == ["gui/app/main.py"]
    assert c.total == 1


def test_staged_add_counted():
    out = "A  new_file.py\n"
    c = parse_git_status_porcelain(out)
    assert c.staged == ["new_file.py"]
    assert c.total == 1


def test_staged_and_modified_same_file():
    """`MM path` — staged changes + further unstaged changes."""
    out = "MM gui/app.py\n"
    c = parse_git_status_porcelain(out)
    assert "gui/app.py" in c.staged
    assert "gui/app.py" in c.modified


def test_untracked_counted():
    out = "?? new.py\n?? docs/\n"
    c = parse_git_status_porcelain(out)
    assert set(c.untracked) == {"new.py", "docs/"}


def test_rename_counted():
    """`R  old -> new` — staged rename."""
    out = "R  old.py -> new.py\n"
    c = parse_git_status_porcelain(out)
    assert c.total == 1
    assert c.renamed == ["old.py -> new.py"] or c.staged == ["old.py -> new.py"]


def test_unmerged_counted():
    """`UU path` — both sides modified, unresolved merge."""
    out = "UU conflict.py\n"
    c = parse_git_status_porcelain(out)
    assert c.unmerged == ["conflict.py"]


def test_repo_like_real_state():
    """Mirror of this repo's state: 3 unstaged deletions + 19 modified + 4 untracked."""
    lines = (
        [" D core/tips.py", " D gui/pages/tips.py", " D gui/pages/usage.py"]
        + [f" M file_{i}.py" for i in range(19)]
        + [f"?? new_{i}.py" for i in range(4)]
    )
    out = "\n".join(lines) + "\n"
    c = parse_git_status_porcelain(out)
    assert len(c.deleted) == 3
    assert len(c.modified) == 19
    assert len(c.untracked) == 4
    assert len(c.staged) == 0
    # The key assertion: sum reconciles to the raw line count
    assert c.total == 26


def test_empty_input_is_clean():
    c = parse_git_status_porcelain("")
    assert c.total == 0


def test_total_excludes_duplicates_from_combined_status():
    """A file with `MM` appears in both staged and modified — but is
    ONE uncommitted file. Total must deduplicate."""
    out = "MM app.py\n M other.py\n"
    c = parse_git_status_porcelain(out)
    # 2 distinct files, 1 is in both buckets
    assert c.total == 2
