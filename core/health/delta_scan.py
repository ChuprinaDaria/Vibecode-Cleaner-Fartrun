"""Apply git-delta optimizations on top of a cached ancestor scan.

When an ancestor commit has a cached HealthReport, we can avoid re-walking
the whole tree for per-file scanners by:

1. Carrying over per-file results for files that did NOT change
2. Re-running the per-file scanner on just `plan.added_or_modified`
3. Letting deleted files fall away (they're absent from both lists above)

For now this covers `map.monsters` only, since it has a clean path-keyed
shape and a `scan_monsters_files` Rust API. tech_debt and others follow in
separate commits as their per-file shape gets cleaned up.

Cross-file scanners (dead_code, module_map, duplicates, reusable) are
unaffected by this module — `run_all_checks` still re-runs them in full
because their results depend on global symbol/import tables.
"""

from __future__ import annotations

import logging

from core.health import tips
from core.health.git_delta import DeltaPlan
from core.health.models import HealthFinding, HealthReport

log = logging.getLogger(__name__)


def _make_monster_dict(m) -> dict:
    return {
        "path": m.path,
        "lines": m.lines,
        "functions": m.functions,
        "classes": m.classes,
        "severity": m.severity,
    }


def _make_monster_finding(m) -> HealthFinding:
    return HealthFinding(
        check_id="map.monsters",
        title=f"Monster: {m.path}",
        severity=m.severity,
        message=tips.tip_monster(m.path, m.lines, m.functions),
        details={"path": m.path},
    )


def apply_monsters_delta(
    report: HealthReport,
    health_rs,
    project_dir: str,
    plan: DeltaPlan,
    ancestor: HealthReport,
) -> None:
    """Populate report.monsters and `map.monsters` findings using cached
    ancestor data plus a per-file rescan of `plan.added_or_modified`.

    This mutates `report` in place — same contract as the full-scan branch
    in project_map.run_all_checks so callers can drop it in.
    """
    changed_set = set(plan.added_or_modified) | set(plan.deleted)

    # Carry over monsters for files that did not change.
    for m in ancestor.monsters:
        if m.get("path") not in changed_set:
            report.monsters.append(m)

    # Carry over `map.monsters` findings whose path is unchanged. Findings
    # that don't track a path in `details` (older cache entries pre-migration)
    # are dropped — re-running the per-file scanner below restores any that
    # are still relevant for changed files; for unchanged files the cost of
    # an occasional missed carry-over is negligible vs. the risk of
    # double-counting.
    for f in ancestor.findings:
        if f.check_id != "map.monsters":
            continue
        path = (f.details or {}).get("path")
        if path is not None and path not in changed_set:
            report.findings.append(f)

    # Re-scan only the added/modified files. Deleted files have nothing to
    # rescan, and their old findings were already filtered out above.
    if plan.added_or_modified:
        try:
            result = health_rs.scan_monsters_files(project_dir, plan.added_or_modified)
        except BaseException as e:  # PyO3 surfaces ValueError on bad root etc.
            log.error("delta_scan: scan_monsters_files failed: %s", e)
            return
        report.monsters.extend(_make_monster_dict(m) for m in result.monsters)
        for m in result.monsters:
            report.findings.append(_make_monster_finding(m))


def append_full_monsters(report: HealthReport, monsters_result) -> None:
    """Same population as the legacy inline block in `run_all_checks` but
    co-located with the delta path so additions stay in sync. Now also
    stores `path` in finding details for future delta filtering."""
    report.monsters = [_make_monster_dict(m) for m in monsters_result.monsters]
    for m in monsters_result.monsters:
        report.findings.append(_make_monster_finding(m))


def apply_tech_debt_delta(
    report: HealthReport,
    health_rs,
    project_dir: str,
    plan: DeltaPlan,
    ancestor: HealthReport,
) -> None:
    """Patch tech-debt findings (`debt.no_types`, `debt.error_handling`,
    `debt.hardcoded`, `debt.todos`) using cached ancestor data plus a
    per-file rescan of `plan.added_or_modified`.

    Findings without a `path` in details are dropped on delta replay —
    the per-file rescan recreates entries for changed files; entries for
    unchanged files are lost once and refreshed by the next full scan.
    """
    from core.health import tech_debt as tech_debt_mod

    changed_set = set(plan.added_or_modified) | set(plan.deleted)

    for f in ancestor.findings:
        if f.check_id not in tech_debt_mod.CHECK_IDS:
            continue
        path = (f.details or {}).get("path")
        if path is not None and path not in changed_set:
            report.findings.append(f)

    if plan.added_or_modified:
        try:
            result = health_rs.scan_tech_debt_files(project_dir, plan.added_or_modified)
        except BaseException as e:
            log.error("delta_scan: scan_tech_debt_files failed: %s", e)
            return
        # Per-file rescan returns the un-capped result for the small set of
        # changed files; we append every finding without re-capping. See
        # `tech_debt.append_findings_from_result` for why.
        tech_debt_mod.append_findings_from_result(report, result, project_dir)
