"""Tests for duplicate code detection."""

import health


def test_identical_blocks(tmp_path):
    """Two files with identical code block should be detected."""
    shared_code = "\n".join(
        f"    result_{i} = process(data_{i})" for i in range(15)
    )
    (tmp_path / "api.py").write_text(f"def handler_a():\n{shared_code}\n    return result_0\n")
    (tmp_path / "views.py").write_text(f"def handler_b():\n{shared_code}\n    return result_0\n")

    result = health.scan_duplicates(str(tmp_path))
    assert len(result.duplicates) >= 1
    files = {result.duplicates[0].file_a, result.duplicates[0].file_b}
    assert "api.py" in files
    assert "views.py" in files


def test_no_duplicates(tmp_path):
    """Completely different files should not be flagged."""
    (tmp_path / "a.py").write_text("def foo():\n    x = 1\n    return x\n")
    (tmp_path / "b.py").write_text("def bar():\n    y = 'hello'\n    print(y)\n")

    result = health.scan_duplicates(str(tmp_path))
    assert len(result.duplicates) == 0


def test_small_overlap_not_flagged(tmp_path):
    """Less than 10 matching lines should not be flagged."""
    shared = "\n".join(f"    x_{i} = {i}" for i in range(5))
    (tmp_path / "a.py").write_text(f"def f():\n{shared}\n    return 1\n")
    (tmp_path / "b.py").write_text(f"def g():\n{shared}\n    return 2\n")

    result = health.scan_duplicates(str(tmp_path))
    assert len(result.duplicates) == 0


def test_imports_not_counted(tmp_path):
    """Import lines should be excluded from duplicate detection."""
    imports = "\n".join([
        "import os",
        "import sys",
        "import json",
        "import logging",
        "import hashlib",
        "import pathlib",
        "import subprocess",
        "import re",
        "import datetime",
        "import collections",
        "import itertools",
    ])
    (tmp_path / "a.py").write_text(f"{imports}\n\ndef unique_a():\n    pass\n")
    (tmp_path / "b.py").write_text(f"{imports}\n\ndef unique_b():\n    pass\n")

    result = health.scan_duplicates(str(tmp_path))
    assert len(result.duplicates) == 0


def test_test_files_skipped(tmp_path):
    """Test files should be excluded."""
    shared = "\n".join(f"    result_{i} = process({i})" for i in range(15))
    (tmp_path / "app.py").write_text(f"def handler():\n{shared}\n")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text(f"def test_handler():\n{shared}\n")

    result = health.scan_duplicates(str(tmp_path))
    # Should not flag app.py vs test_app.py
    for dup in result.duplicates:
        assert "test_app.py" not in dup.file_a
        assert "test_app.py" not in dup.file_b
