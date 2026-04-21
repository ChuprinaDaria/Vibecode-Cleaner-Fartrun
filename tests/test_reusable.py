"""Tests for reusable component detection."""

import health


def test_repeated_button_detected(tmp_path):
    """Same button className in 3+ files should be flagged."""
    for name in ["PageA.jsx", "PageB.jsx", "PageC.jsx"]:
        (tmp_path / name).write_text(
            'import React from "react";\n'
            "function Page() {\n"
            '  return <button className="btn-primary">Click</button>;\n'
            "}\n"
            "export default Page;\n"
        )

    result = health.scan_reusable(str(tmp_path))
    assert len(result.patterns) >= 1
    assert any("btn-primary" in p.pattern for p in result.patterns)


def test_unique_elements_not_flagged(tmp_path):
    """Different classNames should not be flagged."""
    (tmp_path / "A.jsx").write_text(
        '<button className="btn-save">Save</button>\n'
    )
    (tmp_path / "B.jsx").write_text(
        '<button className="btn-cancel">Cancel</button>\n'
    )
    (tmp_path / "C.jsx").write_text(
        '<button className="btn-delete">Delete</button>\n'
    )

    result = health.scan_reusable(str(tmp_path))
    assert len(result.patterns) == 0


def test_no_jsx_files(tmp_path):
    """Non-JSX project should return empty."""
    (tmp_path / "app.py").write_text("x = 1\n")
    result = health.scan_reusable(str(tmp_path))
    assert len(result.patterns) == 0


def test_two_files_not_enough(tmp_path):
    """Pattern in only 2 files should not be flagged (need 3+)."""
    for name in ["A.jsx", "B.jsx"]:
        (tmp_path / name).write_text(
            '<button className="btn-primary">Go</button>\n'
        )

    result = health.scan_reusable(str(tmp_path))
    assert len(result.patterns) == 0
