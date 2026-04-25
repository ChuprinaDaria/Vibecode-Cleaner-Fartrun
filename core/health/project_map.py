"""Check 1.5 — Config & Env Inventory + orchestrator for all Phase 1 checks."""

from __future__ import annotations

import logging
from pathlib import Path

from core.health.models import (
    ConfigFile, ConfigInventoryResult, HealthFinding, HealthReport,
)
from core.health import cache, delta_scan, git_delta, tips

log = logging.getLogger(__name__)

# Config file patterns: (glob_pattern, kind, description_template)
_CONFIG_PATTERNS: list[tuple[str, str, str]] = [
    (".env", "env", "Environment variables"),
    (".env.*", "env", "Environment variables"),
    ("docker-compose*.yml", "docker", "Docker Compose config"),
    ("docker-compose*.yaml", "docker", "Docker Compose config"),
    ("Dockerfile*", "docker", "Docker image build"),
    ("pyproject.toml", "python_deps", "Python project config"),
    ("setup.py", "python_deps", "Python package config"),
    ("setup.cfg", "python_deps", "Python package config"),
    ("requirements*.txt", "python_deps", "Python dependencies"),
    ("Pipfile", "python_deps", "Python dependencies (Pipenv)"),
    ("package.json", "js_config", "Node.js project config"),
    ("tsconfig*.json", "js_config", "TypeScript config"),
    ("Makefile", "build", "Build/automation commands"),
    ("Procfile", "build", "Production process config"),
    (".github/workflows/*.yml", "ci", "GitHub Actions CI/CD"),
    (".github/workflows/*.yaml", "ci", "GitHub Actions CI/CD"),
    (".gitlab-ci.yml", "ci", "GitLab CI/CD"),
]


def scan_config_inventory(project_dir: str) -> ConfigInventoryResult:
    """Check 1.5 — find all config files in the project."""
    root = Path(project_dir)
    configs: list[ConfigFile] = []
    env_count = 0
    has_docker = False
    has_ci = False
    seen_paths: set[str] = set()

    for pattern, kind, desc_template in _CONFIG_PATTERNS:
        for match_path in root.glob(pattern):
            rel = str(match_path.relative_to(root))
            if rel in seen_paths:
                continue
            seen_paths.add(rel)

            description = desc_template
            severity = "info"

            if kind == "env":
                env_count += 1
                severity = "warning"
                try:
                    lines = match_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    var_count = sum(
                        1 for l in lines
                        if l.strip() and not l.strip().startswith("#")
                    )
                    description = f"{desc_template} ({var_count} vars)"
                except OSError:
                    pass

            if kind == "docker":
                has_docker = True
            if kind == "ci":
                has_ci = True

            configs.append(ConfigFile(
                path=rel,
                kind=kind,
                description=description,
                severity=severity,
            ))

    return ConfigInventoryResult(
        configs=configs,
        env_file_count=env_count,
        has_docker=has_docker,
        has_ci=has_ci,
    )


def _run_module_map(
    health_rs,
    project_dir: str,
    entry_paths: list[str],
    *,
    scan_ctx,
    delta_context,
):
    """Module-map dispatch: delta when ancestor state is cached, full
    scan otherwise. Always persists state under the current HEAD so
    the next delta-eligible run can be incremental.
    """
    from core.health import cache as cache_mod
    from core.health.module_map import incremental_module_map_scan

    new_state: dict[str, str] | None = None
    result = None

    if delta_context is not None:
        plan, _ancestor_report = delta_context
        prior_state = cache_mod.get_file_data(
            project_dir, plan.ancestor_hash, "module_map",
        )
        if prior_state:
            try:
                result, new_state = incremental_module_map_scan(
                    health_rs, project_dir, entry_paths,
                    prior_state,
                    changed_paths=set(plan.added_or_modified),
                    deleted_paths=set(plan.deleted),
                )
                log.info(
                    "module_map: incremental run, %d carried over, %d re-parsed",
                    len(prior_state) - len(plan.added_or_modified) - len(plan.deleted),
                    len(plan.added_or_modified),
                )
            except BaseException as e:
                log.error("incremental module_map failed, falling back: %s", e)
                result = None
                new_state = None

    if result is None:
        new_state = health_rs.collect_module_map_state(project_dir, scan_ctx)
        result = health_rs.assemble_module_map_from_json(
            project_dir, entry_paths, new_state, None,
        )

    if new_state is not None:
        head = cache_mod.head_hash(project_dir)
        if head:
            cache_mod.put_file_data(project_dir, head, "module_map", new_state)

    return result


def run_all_checks(project_dir: str, *, use_cache: bool = True) -> HealthReport:
    """Run all Phase 1 checks and assemble a HealthReport.

    When `use_cache` is true (the default) and the project is a clean git
    working tree, the result for the current HEAD commit is reused from
    on-disk cache instead of re-running every scanner. Pass `use_cache=False`
    to force a fresh scan (CLI `--no-cache`, tests, debugging).
    """
    if use_cache:
        cached = cache.get(project_dir)
        if cached is not None:
            log.info(
                "Using cached scan for %s @ %s",
                project_dir, (cache.head_hash(project_dir) or "")[:8],
            )
            return cached

    # Delta scan: when no exact-HEAD cache hit but we have a cached
    # ancestor commit, re-use those per-file findings for files that did
    # not change. `delta_context` is consumed by individual scanner blocks
    # (currently only monsters); when None, every scanner full-runs.
    delta_context: tuple[git_delta.DeltaPlan, HealthReport] | None = None
    if use_cache:
        plan = git_delta.plan_delta(project_dir)
        if plan is not None:
            ancestor = cache.get_at(project_dir, plan.ancestor_hash)
            if ancestor is not None:
                delta_context = (plan, ancestor)
                log.info(
                    "delta scan: %d files changed since %s",
                    len(plan.changed), plan.ancestor_hash[:8],
                )

    report = HealthReport(project_dir=project_dir)

    _rust_available = False
    health_rs = None
    try:
        import health as health_rs
        _rust_available = True
    except ImportError:
        log.warning("health crate not installed — Rust checks skipped")
        report.findings.append(HealthFinding(
            check_id="system",
            title="Health crate not installed",
            severity="warning",
            message="Build the health crate: cd crates/health && maturin develop",
        ))

    # ScanContext shares parsed tree-sitter trees across scanners so a
    # Python file walked by both module_map and dead_code is parsed once,
    # not twice. Created lazily so we don't pay the construction cost in
    # the cache-hit fast-path or pure-Python branch above.
    scan_ctx = health_rs.ScanContext() if _rust_available else None

    if _rust_available:
        # Check 1.1 — File Tree
        try:
            tree = health_rs.scan_file_tree(project_dir)
            report.file_tree = {
                "total_files": tree.total_files,
                "total_dirs": tree.total_dirs,
                "total_size_bytes": tree.total_size_bytes,
                "max_depth": tree.max_depth,
                "files_by_ext": dict(tree.files_by_ext),
                "largest_dirs": list(tree.largest_dirs),
            }
            ext_sorted = sorted(tree.files_by_ext.items(), key=lambda x: x[1], reverse=True)
            top_ext, top_count = ext_sorted[0] if ext_sorted else ("?", 0)
            report.findings.append(HealthFinding(
                check_id="map.file_tree",
                title="Project Map",
                severity="info",
                message=tips.tip_file_tree(tree.total_files, top_ext, top_count),
                details=report.file_tree,
            ))
        except BaseException as e:
            log.error("file_tree scan error: %s", e)

        # Check 1.2 — Entry Points
        try:
            ep_result = health_rs.scan_entry_points(project_dir)
            ep_list = [
                {"path": ep.path, "kind": ep.kind, "description": ep.description}
                for ep in ep_result.entry_points
            ]
            report.entry_points = ep_list
            severity = "info" if ep_list else "medium"
            report.findings.append(HealthFinding(
                check_id="map.entry_points",
                title="Entry Points",
                severity=severity,
                message=tips.tip_entry_points(len(ep_list)),
                details={"entry_points": ep_list},
            ))
        except BaseException as e:
            log.error("entry_points scan error: %s", e)

        # Check 1.3 — Module Map (delta-aware via file_data_cache)
        try:
            entry_paths = [ep["path"] for ep in report.entry_points]
            mm_result = _run_module_map(
                health_rs, project_dir, entry_paths,
                scan_ctx=scan_ctx,
                delta_context=delta_context,
            )
            report.module_map = {
                "hub_modules": list(mm_result.hub_modules),
                "circular_deps": list(mm_result.circular_deps),
                "orphan_candidates": list(mm_result.orphan_candidates),
                "total_modules": len(mm_result.modules),
            }
            for path, count in mm_result.hub_modules[:3]:
                report.findings.append(HealthFinding(
                    check_id="map.modules",
                    title=f"Hub: {path}",
                    severity="info",
                    message=tips.tip_hub_module(path, count),
                ))
            # Filter out circulars involving generated/mock files, and cap
            # the total to avoid flooding the report on large projects.
            _gen_markers = (
                "/generated/", "/__generated__/", "/generated-metadata/",
                "/mock-data/", "/mocks/", "/__mocks__/",
            )
            _is_gen = lambda p: any(m in p.replace("\\", "/") for m in _gen_markers)
            filtered = [cd for cd in mm_result.circular_deps
                        if not _is_gen(cd.file_a) and not _is_gen(cd.file_b)]
            for cd in filtered[:15]:
                severity = "low" if cd.is_lazy else "medium"
                lazy_note = " (lazy import — safe)" if cd.is_lazy else ""
                report.findings.append(HealthFinding(
                    check_id="map.modules",
                    title=f"Circular: {cd.file_a} \u2194 {cd.file_b}{lazy_note}",
                    severity=severity,
                    message=tips.tip_circular(cd.file_a, cd.file_b),
                ))
            if len(filtered) > 15:
                report.findings.append(HealthFinding(
                    check_id="map.modules",
                    title=f"Circular: +{len(filtered)-15} more cycles",
                    severity="info",
                    message=f"Showing 15 of {len(filtered)} circular dependencies.",
                ))
            for orphan in mm_result.orphan_candidates[:5]:
                report.findings.append(HealthFinding(
                    check_id="map.modules",
                    title=f"Orphan: {orphan}",
                    severity="low",
                    message=tips.tip_orphan(orphan),
                ))
        except BaseException as e:
            log.error("module_map scan error: %s", e)

        # Check 1.4 — Monsters (delta-aware, context-aware)
        try:
            if delta_context is not None:
                plan, ancestor = delta_context
                delta_scan.apply_monsters_delta(
                    report, health_rs, project_dir, plan, ancestor,
                )
            else:
                if scan_ctx is not None:
                    monsters_result = health_rs.scan_monsters_with_context(
                        scan_ctx, project_dir,
                    )
                else:
                    monsters_result = health_rs.scan_monsters(project_dir)
                delta_scan.append_full_monsters(report, monsters_result)
        except BaseException as e:
            log.error("monsters scan error: %s", e)

        # Phase 2: Dead Code (delta-aware via file_data_cache)
        try:
            from core.health.dead_code import run_dead_code_checks
            entry_paths = [ep["path"] for ep in report.entry_points]
            run_dead_code_checks(
                report, health_rs, project_dir, entry_paths,
                scan_ctx=scan_ctx,
                delta_context=delta_context,
            )
        except BaseException as e:
            log.error("dead_code scan error: %s", e)

        # Check 2.5: Duplicate Code
        try:
            dup_result = health_rs.scan_duplicates(project_dir)
            for dup in dup_result.duplicates[:15]:
                report.findings.append(HealthFinding(
                    check_id="dead.duplicates",
                    title=f"Duplicate: {dup.file_a} \u2194 {dup.file_b} ({dup.line_count} lines)",
                    severity="medium",
                    message=(
                        f"{dup.line_count} duplicate lines: "
                        f"{dup.file_a}:{dup.line_a} and {dup.file_b}:{dup.line_b}. "
                        f"Extract into a shared function, import from both."
                    ),
                ))
        except BaseException as e:
            log.error("duplicates scan error: %s", e)

        # Check 3.6: Reusable Components (frontend)
        try:
            reuse_result = health_rs.scan_reusable(project_dir)
            for pat in reuse_result.patterns[:10]:
                report.findings.append(HealthFinding(
                    check_id="debt.no_reuse",
                    title=f"{pat.pattern} in {len(pat.files)} files ({pat.occurrences}x)",
                    severity="medium",
                    message=(
                        f"{pat.pattern} appears {pat.occurrences} times in {len(pat.files)} files: "
                        f"{', '.join(pat.files[:3])}. "
                        f"Extract into a reusable component. Write once, use everywhere."
                    ),
                ))
        except BaseException as e:
            log.error("reusable scan error: %s", e)

        # Phase 11: UX Sanity (JSX/TSX checks)
        try:
            from core.health.ux_sanity import run_ux_sanity_checks
            run_ux_sanity_checks(report, health_rs, project_dir)
        except BaseException as e:
            log.error("ux_sanity scan error: %s", e)

        # Phase 3: Tech Debt (delta-aware, context-aware)
        try:
            if delta_context is not None:
                plan, ancestor = delta_context
                delta_scan.apply_tech_debt_delta(
                    report, health_rs, project_dir, plan, ancestor,
                )
            else:
                from core.health.tech_debt import run_tech_debt_checks
                run_tech_debt_checks(
                    report, health_rs, project_dir, scan_ctx=scan_ctx,
                )
        except BaseException as e:
            log.error("tech_debt scan error: %s", e)

        # Check 3.1: Outdated Dependencies (needs network)
        try:
            from core.health.outdated_deps import run_outdated_deps_check
            from core.history import HistoryDB
            _dep_db = HistoryDB()
            _dep_db.init()
            run_outdated_deps_check(report, project_dir, db=_dep_db)
            _dep_db.close()
        except Exception as e:
            log.error("outdated_deps scan error: %s", e)

        # Phase 4: Brake System
        try:
            from core.health.brake_system import run_brake_checks
            run_brake_checks(report, health_rs, project_dir, scan_ctx=scan_ctx)
        except Exception as e:
            log.error("brake_system scan error: %s", e)

    # Brake checks that don't need Rust (unfinished work, test health, scope creep)
    if not _rust_available:
        try:
            from core.health.brake_system import (
                check_unfinished_work, check_test_health, check_scope_creep,
            )
            check_unfinished_work(report, project_dir)
            check_test_health(report, project_dir)
            check_scope_creep(report, project_dir)
        except Exception as e:
            log.error("brake_system (no rust) error: %s", e)

    # Phase 5: Git Survival (always Python, no Rust needed)
    try:
        from core.health.git_survival import run_git_survival_checks
        run_git_survival_checks(report, project_dir)
    except Exception as e:
        log.error("git_survival scan error: %s", e)

    # Phase 6: Docs & Context (always Python)
    try:
        from core.health.docs_context import run_docs_context_checks
        run_docs_context_checks(report, project_dir)
    except Exception as e:
        log.error("docs_context scan error: %s", e)

    # Phase 7: UI/UX Design Quality (always Python, no Rust needed)
    try:
        from core.health.ui_ux_design import run_ui_ux_checks
        run_ui_ux_checks(report, project_dir)
    except Exception as e:
        log.error("ui_ux_design scan error: %s", e)

    # Phase 8: Framework & Infra checks (Django, Docker, frontend bundle)
    try:
        from core.health.framework_checks import run_framework_checks
        run_framework_checks(report, project_dir)
    except Exception as e:
        log.error("framework_checks scan error: %s", e)

    # Check 1.5 — Config Inventory (always Python)
    try:
        config_result = scan_config_inventory(project_dir)
        report.configs = [
            {
                "path": c.path,
                "kind": c.kind,
                "description": c.description,
                "severity": c.severity,
            }
            for c in config_result.configs
        ]
        if config_result.env_file_count > 0:
            report.findings.append(HealthFinding(
                check_id="map.configs",
                title="Config Files",
                severity="warning" if config_result.env_file_count > 1 else "info",
                message=tips.tip_env_files(config_result.env_file_count),
                details={"configs": report.configs},
            ))
        elif config_result.configs:
            report.findings.append(HealthFinding(
                check_id="map.configs",
                title="Config Files",
                severity="info",
                message=f"{len(config_result.configs)} config files found.",
                details={"configs": report.configs},
            ))
    except Exception as e:
        log.error("config inventory error: %s", e)

    # Phase 9: Context7 fix recommendations (enrich findings with real docs)
    try:
        import shutil
        if not shutil.which("npx"):
            log.info("Context7 skipped: npx not found. Install Node.js for doc recommendations.")
        else:
            from core.health.context7_recommendations import enrich_findings_with_context7
            enrich_findings_with_context7(report, project_dir)
    except subprocess.TimeoutExpired:
        log.info("Context7 timed out — skipping doc recommendations.")
    except Exception as e:
        log.error("context7 recommendations error: %s", e)

    # Always save .md report
    try:
        from core.health.report_md import save_report_md
        save_report_md(report)
    except Exception as e:
        log.warning("Could not save .md report: %s", e)

    if use_cache:
        cache.put(project_dir, report)

    return report
