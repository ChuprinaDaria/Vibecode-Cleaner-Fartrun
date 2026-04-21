"""Verification scan on atbalance/web_biuro (Django + React project).

These tests run the scanner on a real Django+React project and verify
known false positives from Phase 2 are fixed. Skip if project not available.
"""

import os
from pathlib import Path

import pytest
import health as h
from core.health.project_map import run_all_checks

ATBALANCE = "/home/dchuprina/atbalance/web_biuro"
pytestmark = pytest.mark.skipif(
    not Path(ATBALANCE).is_dir(),
    reason="atbalance project not available"
)


class TestAtbalanceOrphans:
    """JSX components and Django files must not be false orphans."""

    def test_jsx_components_not_orphan(self):
        result = h.scan_module_map(ATBALANCE, [])
        orphans = set(result.orphan_candidates)
        known_not_orphans = [
            "frontend/src/pages/PrivacyPolicy.jsx",
            "frontend/src/components/About.jsx",
            "frontend/src/components/Contact.jsx",
            "frontend/src/components/CookieBanner.jsx",
            "frontend/src/pages/Home.jsx",
            "frontend/src/App.jsx",
        ]
        false_positives = [f for f in known_not_orphans if f in orphans]
        assert not false_positives, (
            f"These JSX files are imported but flagged as orphans: {false_positives}"
        )

    def test_config_files_not_orphan(self):
        result = h.scan_module_map(ATBALANCE, [])
        orphans = set(result.orphan_candidates)
        configs = [o for o in orphans if ".config." in o]
        assert not configs, f"Config files should not be orphans: {configs}"

    def test_django_files_not_orphan(self):
        result = h.scan_module_map(ATBALANCE, [])
        orphans = set(result.orphan_candidates)
        django_false = [
            o for o in orphans
            if o.endswith(("admin.py", "apps.py", "urls.py", "settings.py"))
        ]
        assert not django_false, f"Django conventional files should not be orphans: {django_false}"


class TestAtbalanceDeadCode:
    """Django/DRF patterns must not be false positives."""

    def test_no_false_meta(self):
        report = run_all_checks(ATBALANCE)
        unused = [f for f in report.findings if f.check_id == "dead.unused_definitions"]
        meta_flags = [f for f in unused if "Meta" in f.title and f.title.startswith("Unused class")]
        assert not meta_flags, f"Meta inner classes should not be flagged: {meta_flags}"

    def test_no_false_admin_hooks(self):
        report = run_all_checks(ATBALANCE)
        unused = [f for f in report.findings if f.check_id == "dead.unused_definitions"]
        admin_flags = [f for f in unused if "has_add_permission" in f.title or "has_delete_permission" in f.title]
        assert not admin_flags, f"Admin hooks should not be flagged: {admin_flags}"

    def test_no_false_validators(self):
        report = run_all_checks(ATBALANCE)
        unused = [f for f in report.findings if f.check_id == "dead.unused_definitions"]
        validator_flags = [f for f in unused if "validate_consent" in f.title]
        assert not validator_flags, f"DRF validators should not be flagged: {validator_flags}"
