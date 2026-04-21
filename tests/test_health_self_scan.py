"""Golden tests: run health scanner on claude-monitor itself.

These tests assert known truths about the claude-monitor codebase.
If the scanner reports a false positive for any of these, the test fails.
Update assertions if the codebase changes (e.g. file deleted or moved).
"""

from pathlib import Path

import health as h
from core.health.project_map import run_all_checks

PROJECT_ROOT = str(Path(__file__).parent.parent)


class TestSelfScanOrphans:
    """Known non-orphan files must not appear in orphan_candidates."""

    KNOWN_NOT_ORPHANS = [
        "core/mcp/tools/context7_install.py",
        "core/safety_net/models.py",
        "data/hooks_guide_en.py",
        "plugins/docker_monitor/plugin.py",
        "plugins/docker_monitor/collector.py",
    ]

    def test_no_false_orphans(self):
        result = h.scan_module_map(PROJECT_ROOT, [])
        orphans = set(result.orphan_candidates)
        false_positives = [f for f in self.KNOWN_NOT_ORPHANS if f in orphans]
        assert not false_positives, (
            f"These files are NOT orphans but scanner flagged them: {false_positives}"
        )


class TestSelfScanHubs:
    """Hub counting must reflect reality."""

    def test_models_hub_count(self):
        result = h.scan_module_map(PROJECT_ROOT, [])
        hub_dict = {path: count for path, count in result.hub_modules}
        # core/models.py is imported by at least 5 files (verified manually: 9)
        models_count = hub_dict.get("core/models.py", 0)
        assert models_count >= 5, (
            f"core/models.py should have >= 5 importers, got {models_count}"
        )


class TestSelfScanUnusedImports:
    """Known valid imports must not be flagged unused."""

    def test_type_checking_imports(self):
        """aiosqlite in core/plugin.py is under TYPE_CHECKING — not unused."""
        report = run_all_checks(PROJECT_ROOT)
        unused = [
            f for f in report.findings
            if f.check_id == "dead.unused_imports"
        ]
        false_positives = [
            f for f in unused
            if "aiosqlite" in f.title and "core/plugin.py" in f.title
        ]
        assert not false_positives, (
            f"aiosqlite under TYPE_CHECKING should not be flagged: {false_positives}"
        )

    def test_mcp_types_not_flagged(self):
        """mcp_types in core/mcp/server.py is used in type annotations."""
        report = run_all_checks(PROJECT_ROOT)
        unused = [
            f for f in report.findings
            if f.check_id == "dead.unused_imports"
        ]
        false_positives = [
            f for f in unused
            if "mcp_types" in f.title and "core/mcp/server.py" in f.title
        ]
        assert not false_positives, (
            f"mcp_types is used in annotations, should not be flagged: {false_positives}"
        )


class TestSelfScanSingleMethod:
    """QThread/QDialog subclasses must not be flagged as single-method."""

    KNOWN_NOT_SINGLE_METHOD = [
        "HealthScanThread",
        "HaikuHealthThread",
        "GitConfigDialog",
        "PickDialog",
    ]

    def test_qt_classes_not_flagged(self):
        result = h.scan_overengineering(PROJECT_ROOT)
        flagged_names = [
            i.description
            for i in result.issues
            if i.kind == "single_method_class"
        ]
        for class_name in self.KNOWN_NOT_SINGLE_METHOD:
            matches = [d for d in flagged_names if class_name in d]
            assert not matches, (
                f"{class_name} inherits from Qt base class, "
                f"should not be flagged: {matches}"
            )


class TestSelfScanCommentedCode:
    """Documentation comments must not be flagged as commented-out code."""

    def test_no_false_commented_code(self):
        report = run_all_checks(PROJECT_ROOT)
        commented = [
            f for f in report.findings
            if f.check_id == "dead.commented_code"
        ]
        # test_mcp_server.py:178 has doc comments, not code
        false_positives = [
            f for f in commented
            if "test_mcp_server.py" in f.title
        ]
        assert not false_positives, (
            f"Doc comments in test_mcp_server.py should not be flagged: {false_positives}"
        )
