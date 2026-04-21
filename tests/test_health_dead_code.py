"""Tests for dead code detection."""

from core.health.project_map import run_all_checks


def test_unused_import_detected(tmp_path):
    """Python file with unused import should be flagged."""
    (tmp_path / "app.py").write_text(
        "import os\nimport sys\n\nprint(sys.argv)\n"
    )
    report = run_all_checks(str(tmp_path))
    unused = [f for f in report.findings if f.check_id == "dead.unused_imports"]
    names = [f.title for f in unused]
    assert any("os" in n for n in names), f"Expected unused 'os', got: {names}"


def test_used_import_not_flagged(tmp_path):
    """Used import should NOT be flagged."""
    (tmp_path / "app.py").write_text(
        "import os\n\nprint(os.getcwd())\n"
    )
    report = run_all_checks(str(tmp_path))
    unused = [f for f in report.findings if f.check_id == "dead.unused_imports"]
    names = [f.title for f in unused]
    assert not any("os" in n for n in names), f"os should not be flagged: {names}"


def test_unused_function_detected(tmp_path):
    """Function defined but never called should be flagged."""
    (tmp_path / "utils.py").write_text(
        "def helper():\n    pass\n\ndef unused_func():\n    pass\n"
    )
    (tmp_path / "main.py").write_text(
        "from utils import helper\nhelper()\n"
    )
    report = run_all_checks(str(tmp_path))
    unused_defs = [f for f in report.findings if f.check_id == "dead.unused_definitions"]
    names = [f.title for f in unused_defs]
    assert any("unused_func" in n for n in names), f"Expected unused_func, got: {names}"


def test_decorated_function_not_flagged(tmp_path):
    """Decorated functions should NOT be flagged."""
    (tmp_path / "routes.py").write_text(
        "from flask import Flask\napp = Flask(__name__)\n\n"
        "@app.route('/')\ndef index():\n    return 'hi'\n"
    )
    report = run_all_checks(str(tmp_path))
    unused_defs = [f for f in report.findings if f.check_id == "dead.unused_definitions"]
    names = [f.title for f in unused_defs]
    assert not any("index" in n for n in names), f"Decorated index should not be flagged: {names}"


def test_commented_code_detected(tmp_path):
    """Block of commented-out code should be flagged."""
    lines = [
        "x = 1",
        "# def old_function():",
        "#     x = 1",
        "#     y = 2",
        "#     return x + y",
        "#     if x > 0:",
        "#         print(x)",
        "y = 2",
    ]
    (tmp_path / "app.py").write_text("\n".join(lines))
    report = run_all_checks(str(tmp_path))
    commented = [f for f in report.findings if f.check_id == "dead.commented_code"]
    assert len(commented) >= 1, f"Expected commented code block, got: {commented}"


def test_small_comment_not_flagged(tmp_path):
    """Less than 5 comment lines should NOT be flagged."""
    (tmp_path / "app.py").write_text(
        "# This is a comment\n# Another comment\n# Third one\nx = 1\n"
    )
    report = run_all_checks(str(tmp_path))
    commented = [f for f in report.findings if f.check_id == "dead.commented_code"]
    assert len(commented) == 0


def test_init_py_skipped(tmp_path):
    """__init__.py definitions should not be flagged as unused."""
    pkg = tmp_path / "mypackage"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("def public_api():\n    pass\n")
    report = run_all_checks(str(tmp_path))
    unused_defs = [f for f in report.findings if f.check_id == "dead.unused_definitions"]
    names = [f.title for f in unused_defs]
    assert not any("public_api" in n for n in names)


def test_star_import_file_skipped(tmp_path):
    """Files with star imports should be skipped for unused import check."""
    (tmp_path / "app.py").write_text(
        "from os.path import *\nimport json\n\nprint(join('a', 'b'))\n"
    )
    report = run_all_checks(str(tmp_path))
    unused = [f for f in report.findings if f.check_id == "dead.unused_imports"]
    assert not any("json" in f.title for f in unused)
