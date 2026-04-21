"""Tests for tech debt detection."""

from core.health.project_map import run_all_checks


def test_missing_types_detected(tmp_path):
    """Function without type hints should be flagged."""
    (tmp_path / "app.py").write_text(
        "def process(data, count):\n    return data * count\n"
    )
    report = run_all_checks(str(tmp_path))
    types = [f for f in report.findings if f.check_id == "debt.no_types"]
    assert any("process" in f.title for f in types)


def test_typed_function_not_flagged(tmp_path):
    """Function with full type hints should NOT be flagged."""
    (tmp_path / "app.py").write_text(
        "def process(data: list, count: int) -> list:\n    return data * count\n"
    )
    report = run_all_checks(str(tmp_path))
    types = [f for f in report.findings if f.check_id == "debt.no_types"]
    assert not any("process" in f.title for f in types)


def test_bare_except_detected(tmp_path):
    """Bare except should be flagged."""
    (tmp_path / "app.py").write_text(
        "try:\n    x = 1\nexcept:\n    pass\n"
    )
    report = run_all_checks(str(tmp_path))
    gaps = [f for f in report.findings if f.check_id == "debt.error_handling"]
    assert len(gaps) >= 1
    assert any("bare_except" in f.title or "except_pass" in f.title for f in gaps)


def test_proper_except_not_flagged(tmp_path):
    """Proper except with type should not be flagged as bare."""
    (tmp_path / "app.py").write_text(
        "try:\n    x = 1\nexcept ValueError as e:\n    print(e)\n"
    )
    report = run_all_checks(str(tmp_path))
    gaps = [f for f in report.findings if f.check_id == "debt.error_handling"]
    bare = [f for f in gaps if "bare_except" in f.title]
    assert len(bare) == 0


def test_todo_detected(tmp_path):
    """TODO comments should be found."""
    (tmp_path / "app.py").write_text(
        "x = 1\n# TODO: fix this later\ny = 2\n# FIXME: broken\n"
    )
    report = run_all_checks(str(tmp_path))
    todos = [f for f in report.findings if f.check_id == "debt.todos"]
    assert len(todos) >= 2
    kinds = [f.title.split(":")[0] for f in todos]
    assert "TODO" in kinds
    assert "FIXME" in kinds


def test_hardcoded_url_detected(tmp_path):
    """Hardcoded URLs should be flagged."""
    (tmp_path / "app.py").write_text(
        'API_URL = "https://api.production.company.com/v2"\n'
    )
    report = run_all_checks(str(tmp_path))
    hc = [f for f in report.findings if f.check_id == "debt.hardcoded"]
    assert len(hc) >= 1


def test_dunder_methods_skipped(tmp_path):
    """__init__ and other dunder methods should not be flagged for types."""
    (tmp_path / "app.py").write_text(
        "class Foo:\n    def __init__(self, x):\n        self.x = x\n"
    )
    report = run_all_checks(str(tmp_path))
    types = [f for f in report.findings if f.check_id == "debt.no_types"]
    assert not any("__init__" in f.title for f in types)
