"""Tests for pytest-lifecycle whitelist (Task 11).

setup_method, teardown_method, setUp, tearDown are called by pytest/unittest
automatically. They MUST NOT appear in unused_definitions. Same for
@pytest.fixture-decorated functions.
"""
from __future__ import annotations

import health as health_rs


def _write(root, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _unused_defs(result) -> set[str]:
    return {u.name for u in result.unused_definitions}


def test_setup_method_not_flagged(tmp_path):
    _write(
        tmp_path,
        "tests/test_x.py",
        "class TestX:\n"
        "    def setup_method(self):\n"
        "        self.x = 1\n"
        "    def test_foo(self):\n"
        "        assert self.x == 1\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert "setup_method" not in _unused_defs(r)


def test_teardown_method_not_flagged(tmp_path):
    _write(
        tmp_path,
        "tests/test_x.py",
        "class TestX:\n"
        "    def teardown_method(self):\n"
        "        pass\n"
        "    def test_foo(self):\n"
        "        pass\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert "teardown_method" not in _unused_defs(r)


def test_setup_class_not_flagged(tmp_path):
    _write(
        tmp_path,
        "tests/test_x.py",
        "class TestX:\n"
        "    @classmethod\n"
        "    def setup_class(cls):\n"
        "        cls.x = 1\n"
        "    def test_foo(self):\n"
        "        pass\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert "setup_class" not in _unused_defs(r)


def test_unittest_setUp_tearDown_not_flagged(tmp_path):
    _write(
        tmp_path,
        "tests/test_x.py",
        "import unittest\n\n"
        "class TestX(unittest.TestCase):\n"
        "    def setUp(self):\n"
        "        self.x = 1\n"
        "    def tearDown(self):\n"
        "        pass\n"
        "    def test_foo(self):\n"
        "        self.assertEqual(self.x, 1)\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    unused = _unused_defs(r)
    assert "setUp" not in unused
    assert "tearDown" not in unused


def test_setup_module_level_not_flagged(tmp_path):
    """Module-scope `setup_module` and `teardown_module` functions."""
    _write(
        tmp_path,
        "tests/test_x.py",
        "def setup_module(module):\n"
        "    pass\n\n"
        "def teardown_module(module):\n"
        "    pass\n\n"
        "def test_foo():\n"
        "    pass\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    unused = _unused_defs(r)
    assert "setup_module" not in unused
    assert "teardown_module" not in unused


def test_pytest_fixture_not_flagged(tmp_path):
    _write(
        tmp_path,
        "tests/conftest.py",
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def my_fixture():\n"
        "    return object()\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert "my_fixture" not in _unused_defs(r)


def test_pytest_fixture_with_params_not_flagged(tmp_path):
    _write(
        tmp_path,
        "tests/conftest.py",
        "import pytest\n\n"
        "@pytest.fixture(scope='session')\n"
        "def db():\n"
        "    return {}\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert "db" not in _unused_defs(r)


def test_regular_unused_function_still_flagged(tmp_path):
    """Regression: a genuinely dead function must still appear."""
    _write(
        tmp_path,
        "utils.py",
        "def helper_a():\n    pass\n\n"
        "def never_called():\n    pass\n",
    )
    _write(tmp_path, "main.py", "from utils import helper_a\n\nhelper_a()\n")
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert "never_called" in _unused_defs(r)


def test_setup_method_in_non_test_file_still_flagged(tmp_path):
    """Whitelist only applies to tests/ files or test_*.py / *_test.py.

    If somebody happened to call a helper `setup_method` outside the test
    tree, it's not protected.
    """
    _write(
        tmp_path,
        "app.py",
        "class MyService:\n"
        "    def setup_method(self):\n"
        "        pass\n",
    )
    r = health_rs.scan_dead_code(str(tmp_path), [])
    assert "setup_method" in _unused_defs(r)
