# Health Report: fartrun-release

Scanned: 2026-04-21 08:16
Total findings: 214 (actionable: 200)

🟠 high: 1 | 🟡 medium: 94 | 🔵 low: 105 | ℹ️ info: 14

**Files:** 362
**Entry points:** gui/app/main.py, gui/app/__main__.py, core/hooks/frozen_check.py

## Recommended action order

1. **HIGH:** split monster files (1 items)
2. reduce tech debt (30 items)
3. remove unused imports (20 items)
4. remove dead code (17 items)
5. extract duplicates (15 items)
6. split large files (11 items)
7. modules (1 items)

---

## 🟠 HIGH (1)

> Monster files are hard for AI to work with — context window limits mean Claude can't see the whole file at once. Split to improve AI-assisted development.

- [ ] **Monster: crates/health/src/dead_code.rs**
  - crates/health/src/dead_code.rs — 1205 lines, 32 functions.


## 🟡 MEDIUM (94)

- [ ] **Circular: plugins/security_scan/scanners/base.py ↔ plugins/security_scan/scanners/sentinel.py**
  - plugins/security_scan/scanners/base.py imports plugins/security_scan/scanners/sentinel.py, and plugins/security_scan/scanners/sentinel.py imports plugins/security_scan/scanners/base.py.

> Monster files are hard for AI to work with — context window limits mean Claude can't see the whole file at once. Split to improve AI-assisted development.

- [ ] **Monster: gui/pages/hasselhoff_wizard.py**
  - gui/pages/hasselhoff_wizard.py — 815 lines, 31 functions.

- [ ] **Monster: crates/health/src/module_map.rs**
  - crates/health/src/module_map.rs — 752 lines, 16 functions.

- [ ] **Monster: gui/pages/activity/page.py**
  - gui/pages/activity/page.py — 657 lines, 24 functions.

- [ ] **Monster: gui/app/main.py**
  - gui/app/main.py — 654 lines, 25 functions.

- [ ] **Monster: gui/pages/health/page.py**
  - gui/pages/health/page.py — 646 lines, 34 functions.

- [ ] **Monster: gui/pages/overview.py**
  - gui/pages/overview.py — 584 lines, 21 functions.

- [ ] **Monster: gui/security_explanations.py**
  - gui/security_explanations.py — 580 lines, 3 functions.

- [ ] **Monster: gui/pages/safety_net/page.py**
  - gui/pages/safety_net/page.py — 539 lines, 20 functions.

- [ ] **Monster: core/mcp/tools/health.py**
  - core/mcp/tools/health.py — 536 lines, 17 functions.

- [ ] **Monster: i18n/ua.py**
  - i18n/ua.py — 517 lines, 0 functions.

- [ ] **Monster: i18n/en.py**
  - i18n/en.py — 517 lines, 0 functions.

> Unused imports add noise, slow down IDE indexing, and can mask real dependencies. Safe to remove after verifying they're not side-effect imports.

- [ ] **Unused: get_platform**
  - get_platform imported in gui/pages/settings.py:266 but never used.

- [ ] **Unused: Path**
  - Path imported in gui/pages/settings.py:293 but never used.

- [ ] **Unused: Qt**
  - Qt imported in gui/pages/prompt_helper.py:17 but never used.

- [ ] **Unused: pyqtSlot**
  - pyqtSlot imported in gui/pages/docker.py:11 but never used.

- [ ] **Unused: get_language**
  - get_language imported in gui/pages/snapshots/page.py:29 but never used.

- [ ] **Unused: Path**
  - Path imported in gui/pages/safety_net/page.py:9 but never used.

- [ ] **Unused: pyqtSignal**
  - pyqtSignal imported in gui/pages/health/page.py:8 but never used.

- [ ] **Unused: get_string**
  - get_string imported in gui/pages/hasselhoff_wizard.py:24 but never used.

- [ ] **Unused: QFont**
  - QFont imported in gui/sidebar.py:8 but never used.

- [ ] **Unused: UI_ELEMENTS**
  - UI_ELEMENTS imported in gui/ui_dictionary_popup.py:12 but never used.

- [ ] **Unused: Qt**
  - Qt imported in gui/app/main.py:13 but never used.

- [ ] **Unused: os**
  - os imported in gui/app/main.py:298 but never used.

- [ ] **Unused: field**
  - field imported in core/plugin.py:6 but never used.

- [ ] **Unused: datetime**
  - datetime imported in core/prompt_parser.py:15 but never used.

- [ ] **Unused: os**
  - os imported in core/nagger/hasselhoff.py:3 but never used.

- [ ] **Unused: Path**
  - Path imported in core/prompt_builder.py:22 but never used.

- [ ] **Unused: ModelUsage**
  - ModelUsage imported in core/usage_analyzer.py:1 but never used.

- [ ] **Unused: Path**
  - Path imported in core/history.py:7 but never used.

- [ ] **Unused: timedelta**
  - timedelta imported in core/health/tech_debt.py:8 but never used.

- [ ] **Unused: datetime**
  - datetime imported in plugins/security_scan/plugin.py:7 but never used.

> Dead code confuses AI assistants and developers. If a function isn't called, it's either forgotten or accessed via framework magic — verify before deleting.

- [ ] **Unused class: DockerPage**
  - class DockerPage in gui/pages/docker.py — exists but nobody uses it.

- [ ] **Unused method: set_docker_client**
  - set_docker_client() in gui/pages/docker.py — defined but never called anywhere in the project.

- [ ] **Unused function: fmt_tokens**
  - fmt_tokens() in gui/fmt_utils.py — defined but never called anywhere in the project.

- [ ] **Unused class: CopyableSection**
  - class CopyableSection in gui/copyable_widgets.py — exists but nobody uses it.

- [ ] **Unused class: AboutDialog**
  - class AboutDialog in gui/dialogs/about.py — exists but nobody uses it.

- [ ] **Unused function: severity_color**
  - severity_color() in gui/win95.py — defined but never called anywhere in the project.

- [ ] **Unused method: play_file**
  - play_file() in core/alerts.py — defined but never called anywhere in the project.

- [ ] **Unused method: get_tip**
  - get_tip() in core/haiku_client.py — defined but never called anywhere in the project.

- [ ] **Unused method: get_hooks_nudge**
  - get_hooks_nudge() in core/git_educator.py — defined but never called anywhere in the project.

- [ ] **Unused method: open_file**
  - open_file() in core/platform.py — defined but never called anywhere in the project.

- [ ] **Unused function: reset_platform**
  - reset_platform() in core/platform.py — defined but never called anywhere in the project.

- [ ] **Unused method: is_file_frozen**
  - is_file_frozen() in core/history.py — defined but never called anywhere in the project.

- [ ] **Unused method: count_save_points**
  - count_save_points() in core/history.py — defined but never called anywhere in the project.

- [ ] **Unused method: open_file**
  - open_file() in core/platform_backends/windows.py — defined but never called anywhere in the project.

- [ ] **Unused method: open_file**
  - open_file() in core/platform_backends/linux.py — defined but never called anywhere in the project.

- [ ] **Unused method: open_file**
  - open_file() in core/platform_backends/macos.py — defined but never called anywhere in the project.

- [ ] **Unused method: update_events**
  - update_events() in plugins/docker_monitor/widget.py — defined but never called anywhere in the project.

> Duplicated code means fixing a bug in one place leaves the same bug alive in the copy. Extract shared logic into a common module.

- [ ] **Duplicate: core/platform_backends/macos.py ↔ core/platform_backends/windows.py (23 lines)**
  - 23 duplicate lines: core/platform_backends/macos.py:108 and core/platform_backends/windows.py:123.

- [ ] **Duplicate: core/platform_backends/linux.py ↔ core/platform_backends/macos.py (20 lines)**
  - 20 duplicate lines: core/platform_backends/linux.py:162 and core/platform_backends/macos.py:107.

- [ ] **Duplicate: core/platform_backends/linux.py ↔ core/platform_backends/windows.py (19 lines)**
  - 19 duplicate lines: core/platform_backends/linux.py:163 and core/platform_backends/windows.py:123.

- [ ] **Duplicate: crates/health/src/duplicates.rs ↔ crates/health/src/overengineering.rs (19 lines)**
  - 19 duplicate lines: crates/health/src/duplicates.rs:145 and crates/health/src/overengineering.rs:396.

- [ ] **Duplicate: crates/health/src/duplicates.rs ↔ crates/health/src/tech_debt.rs (19 lines)**
  - 19 duplicate lines: crates/health/src/duplicates.rs:145 and crates/health/src/tech_debt.rs:465.

- [ ] **Duplicate: crates/health/src/overengineering.rs ↔ crates/health/src/tech_debt.rs (19 lines)**
  - 19 duplicate lines: crates/health/src/overengineering.rs:396 and crates/health/src/tech_debt.rs:465.

- [ ] **2 duplicate blocks: crates/health/src/ux_sanity/rules/async_handler_no_catch.rs ↔ crates/health/src/ux_sanity/rules/effect_no_deps.rs**
  - Total: ~34 duplicated lines. Extract shared logic into a common module.
  - Lines: ↔12 (17L), ↔45 (17L)

- [ ] **Duplicate: core/context_fetcher.py ↔ core/health/docs_context.py (16 lines)**
  - 16 duplicate lines: core/context_fetcher.py:265 and core/health/docs_context.py:191.

- [ ] **Duplicate: crates/health/src/dead_code.rs ↔ crates/health/src/duplicates.rs (16 lines)**
  - 16 duplicate lines: crates/health/src/dead_code.rs:1096 and crates/health/src/duplicates.rs:145.

- [ ] **Duplicate: crates/health/src/dead_code.rs ↔ crates/health/src/monsters.rs (16 lines)**
  - 16 duplicate lines: crates/health/src/dead_code.rs:1096 and crates/health/src/monsters.rs:112.

- [ ] **Duplicate: crates/health/src/dead_code.rs ↔ crates/health/src/overengineering.rs (16 lines)**
  - 16 duplicate lines: crates/health/src/dead_code.rs:1096 and crates/health/src/overengineering.rs:396.

- [ ] **Duplicate: crates/health/src/dead_code.rs ↔ crates/health/src/tech_debt.rs (16 lines)**
  - 16 duplicate lines: crates/health/src/dead_code.rs:1096 and crates/health/src/tech_debt.rs:465.

- [ ] **Duplicate: crates/health/src/duplicates.rs ↔ crates/health/src/monsters.rs (16 lines)**
  - 16 duplicate lines: crates/health/src/duplicates.rs:145 and crates/health/src/monsters.rs:112.

- [ ] **Duplicate: crates/health/src/monsters.rs ↔ crates/health/src/overengineering.rs (16 lines)**
  - 16 duplicate lines: crates/health/src/monsters.rs:112 and crates/health/src/overengineering.rs:396.

> Missing type hints make AI code generation less accurate — Claude guesses parameter types instead of knowing them. Add types to improve AI output.

- [ ] **wheelEvent() — 1 params without types, no return type**
  - wheelEvent() in gui/copyable_table.py:14 — 1 params without types, no return type.

- [ ] **keyPressEvent() — 1 params without types, no return type**
  - keyPressEvent() in gui/copyable_table.py:25 — 1 params without types, no return type.

- [ ] **_write_toml_fallback() — 1 params without types**
  - _write_toml_fallback() in gui/pages/settings.py:16 — 1 params without types.

- [ ] **_toml_value() — 1 params without types**
  - _toml_value() in gui/pages/settings.py:37 — 1 params without types.

- [ ] **set_haiku_error_callback() — 1 params without types**
  - set_haiku_error_callback() in gui/pages/prompt_helper.py:93 — 1 params without types.

- [ ] **_add_section_header() — no return type**
  - _add_section_header() in gui/pages/discover.py:100 — no return type.

- [ ] **_add_resource_item() — no return type**
  - _add_resource_item() in gui/pages/discover.py:105 — no return type.

- [ ] **wheelEvent() — 1 params without types, no return type**
  - wheelEvent() in gui/pages/activity/page.py:41 — 1 params without types, no return type.

- [ ] **set_haiku_error_callback() — 1 params without types**
  - set_haiku_error_callback() in gui/pages/activity/page.py:80 — 1 params without types.

- [ ] **show_if_new() — 1 params without types**
  - show_if_new() in gui/pages/security.py:153 — 1 params without types.

- [ ] **_on_row_selected() — 4 params without types, no return type**
  - _on_row_selected() in gui/pages/security.py:320 — 4 params without types, no return type.

- [ ] **set_docker_client() — 1 params without types**
  - set_docker_client() in gui/pages/docker.py:155 — 1 params without types.

- [ ] **_show_context_menu() — 1 params without types, no return type**
  - _show_context_menu() in gui/pages/docker.py:232 — 1 params without types, no return type.

- [ ] **set_haiku_error_callback() — 1 params without types**
  - set_haiku_error_callback() in gui/pages/snapshots/page.py:52 — 1 params without types.

- [ ] **update_data() — 2 params without types**
  - update_data() in gui/pages/overview.py:388 — 2 params without types.

- [ ] **update_claude_status() — 1 params without types**
  - update_claude_status() in gui/pages/overview.py:611 — 1 params without types.

- [ ] **set_haiku_error_callback() — 1 params without types**
  - set_haiku_error_callback() in gui/pages/save_points_page.py:129 — 1 params without types.

- [ ] **take_auto_snapshot() — 2 params without types**
  - take_auto_snapshot() in gui/pages/save_points_page.py:161 — 2 params without types.

- [ ] **set_haiku_error_callback() — 1 params without types**
  - set_haiku_error_callback() in gui/pages/health/page.py:55 — 1 params without types.

- [ ] **_on_test_finished() — 1 params without types**
  - _on_test_finished() in gui/pages/health/page.py:188 — 1 params without types.

- [ ] **_test_run_to_dict() — 1 params without types**
  - _test_run_to_dict() in gui/pages/health/page.py:206 — 1 params without types.

- [ ] **_render_test_status_for() — 1 params without types**
  - _render_test_status_for() in gui/pages/health/page.py:217 — 1 params without types.

- [ ] **on_modified() — 1 params without types, no return type**
  - on_modified() in gui/pages/health/page.py:673 — 1 params without types, no return type.

- [ ] **closeEvent() — 1 params without types, no return type**
  - closeEvent() in gui/pages/health/page.py:694 — 1 params without types, no return type.

- [ ] **_download_for_os() — no return type**
  - _download_for_os() in gui/pages/hasselhoff_wizard.py:295 — no return type.

- [ ] **_on_install_requested() — no return type**
  - _on_install_requested() in gui/pages/hasselhoff_wizard.py:641 — no return type.

- [ ] **_start_install() — no return type**
  - _start_install() in gui/pages/hasselhoff_wizard.py:667 — no return type.

- [ ] **_on_install_progress() — no return type**
  - _on_install_progress() in gui/pages/hasselhoff_wizard.py:710 — no return type.

- [ ] **_on_install_ok() — no return type**
  - _on_install_ok() in gui/pages/hasselhoff_wizard.py:713 — no return type.

- [ ] **_on_install_error() — no return type**
  - _on_install_error() in gui/pages/hasselhoff_wizard.py:744 — no return type.


## 🔵 LOW (105)

- [ ] **Circular: gui/app/main.py ↔ gui/app/tray.py (lazy import — safe)**
  - gui/app/main.py imports gui/app/tray.py, and gui/app/tray.py imports gui/app/main.py.

- [ ] **Orphan: gui/pages/docker.py**
  - gui/pages/docker.py — nobody imports it, not an entry point.

- [ ] **Orphan: npm/bin/cli.js**
  - npm/bin/cli.js — nobody imports it, not an entry point.

- [ ] **Orphan: gui/dialogs/about.py**
  - gui/dialogs/about.py — nobody imports it, not an entry point.

> Bare except/empty catch blocks silently swallow errors. When something breaks, you won't know what or where. Log or handle specifically.

- [ ] **then_no_catch: crates/sentinel/src/secrets.rs:203**
  - crates/sentinel/src/secrets.rs:203 — .then() without .catch() — unhandled promise rejection.

- [ ] **except_pass: gui/pages/overview.py:653**
  - gui/pages/overview.py:653 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: gui/pages/hasselhoff_wizard.py:176**
  - gui/pages/hasselhoff_wizard.py:176 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: gui/app/main.py:313**
  - gui/app/main.py:313 — except with only 'pass' — silently swallows errors.

- [ ] **empty_catch: npm/bin/cli.js:309**
  - npm/bin/cli.js:309 — Empty catch block — errors silently swallowed.

- [ ] **except_pass: core/hooks/frozen_check.py:39**
  - core/hooks/frozen_check.py:39 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/repo_scanner.py:53**
  - core/repo_scanner.py:53 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/repo_scanner.py:71**
  - core/repo_scanner.py:71 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/context_fetcher.py:208**
  - core/context_fetcher.py:208 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/context_fetcher.py:237**
  - core/context_fetcher.py:237 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/context_fetcher.py:255**
  - core/context_fetcher.py:255 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/autodiscovery.py:104**
  - core/autodiscovery.py:104 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/nagger/hasselhoff.py:106**
  - core/nagger/hasselhoff.py:106 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/activity_tracker.py:145**
  - core/activity_tracker.py:145 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/token_parser.py:39**
  - core/token_parser.py:39 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/token_parser.py:92**
  - core/token_parser.py:92 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/safety_net/manager.py:99**
  - core/safety_net/manager.py:99 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/safety_net/manager.py:112**
  - core/safety_net/manager.py:112 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/stack_detector.py:116**
  - core/stack_detector.py:116 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: core/health/framework_checks.py:28**
  - core/health/framework_checks.py:28 — except with only 'pass' — silently swallows errors.

> Hardcoded values (URLs, ports, keys) break when environments change. Extract to config/env vars.

- [ ] **Hardcoded url: gui/pages/about.py:16**
  - gui/pages/about.py:16 — https://www.linkedin.com/in/dchuprina/.

- [ ] **Hardcoded url: gui/pages/about.py:18**
  - gui/pages/about.py:18 — https://www.threads.com/@sonya_orehovaya.

- [ ] **Hardcoded url: gui/pages/about.py:20**
  - gui/pages/about.py:20 — https://www.reddit.com/user/Illustrious_Grass534/.

- [ ] **Hardcoded url: gui/security_explanations.py:17**
  - gui/security_explanations.py:17 — https://www.coursera.org/learn/packt-fundamentals-of-secure-.

- [ ] **Hardcoded url: gui/security_explanations.py:18**
  - gui/security_explanations.py:18 — https://www.coursera.org/professional-certificates/google-cy.

- [ ] **Hardcoded url: gui/security_explanations.py:19**
  - gui/security_explanations.py:19 — https://www.coursera.org/learn/cybersecurity-for-everyone.

- [ ] **Hardcoded url: gui/security_explanations.py:20**
  - gui/security_explanations.py:20 — https://www.coursera.org/learn/python.

- [ ] **Hardcoded url: gui/security_explanations.py:21**
  - gui/security_explanations.py:21 — https://www.coursera.org/learn/developing-frontend-apps-with.

- [ ] **Hardcoded url: gui/security_explanations.py:22**
  - gui/security_explanations.py:22 — https://www.coursera.org/specializations/ai-agents.

- [ ] **Hardcoded url: gui/security_explanations.py:23**
  - gui/security_explanations.py:23 — https://www.coursera.org/learn/securing-linux-systems.

- [ ] **Hardcoded url: gui/security_explanations.py:24**
  - gui/security_explanations.py:24 — https://www.coursera.org/learn/docker-basics-for-devops.

- [ ] **Hardcoded url: gui/security_explanations.py:25**
  - gui/security_explanations.py:25 — https://www.coursera.org/learn/crypto.

- [ ] **Hardcoded url: gui/security_explanations.py:26**
  - gui/security_explanations.py:26 — https://www.coursera.org/learn/generative-ai-llm-security.

- [ ] **Hardcoded url: gui/security_explanations.py:27**
  - gui/security_explanations.py:27 — https://www.coursera.org/courses?query=application%20securit.

- [ ] **Hardcoded url: gui/dialogs/about.py:14**
  - gui/dialogs/about.py:14 — https://www.linkedin.com/in/dchuprina/.

- [ ] **Hardcoded url: gui/dialogs/about.py:16**
  - gui/dialogs/about.py:16 — https://www.threads.com/@sonya_orehovaya.

- [ ] **Hardcoded url: gui/dialogs/about.py:18**
  - gui/dialogs/about.py:18 — https://www.reddit.com/user/Illustrious_Grass534/.

- [ ] **Hardcoded url: core/status_checker.py:17**
  - core/status_checker.py:17 — https://status.anthropic.com/api/v2/status.json.

- [ ] **Hardcoded url: core/changelog_watcher.py:18**
  - core/changelog_watcher.py:18 — https://docs.anthropic.com/en/docs/changelog.

- [ ] **Hardcoded url: core/changelog_watcher.py:111**
  - core/changelog_watcher.py:111 — https://....

> Old TODOs are broken promises. If they've been there for weeks, either implement them or delete them — stale TODOs train you to ignore all TODOs.

- [ ] **TEMP: crates/sentinel/src/crontab.rs:285**
  - TEMP in crates/sentinel/src/crontab.rs:285 — /appdata (from 2026-04-21).

- [ ] **2 TODOs in crates/sentinel/src/autostart.rs**
  - :223 — dirs
  - :305 — dirs

- [ ] **TEMP: crates/sentinel/src/filesystem.rs:353**
  - TEMP in crates/sentinel/src/filesystem.rs:353 — executables (from 2026-04-21).

- [ ] **TEMP: crates/sentinel/src/processes.rs:223**
  - TEMP in crates/sentinel/src/processes.rs:223 — directory (suspicious execution location) (from 2026-04-21).

- [ ] **2 TODOs in crates/health/src/dead_code.rs**
  - :866 — list).
  - :942 — list or bullet-point comment.

- [ ] **2 TODOs in crates/health/src/tech_debt.rs**
  - :3 — /FIXME audit.
  - :408 — /FIXME/HACK ---

- [ ] **3 TODOs in core/health/report_md.py**
  - :202 — internal/station/manager.go:212"
  - :217 — message
  - :228 — text from message

- [ ] **XXX: data/hooks_guide_en.py:120**
  - XXX in data/hooks_guide_en.py:120 — '\n" (from 2026-04-21).

- [ ] **TODO: tests/test_health_dead_code_commented.py:117**
  - TODO in tests/test_health_dead_code_commented.py:117 — items for next release:\n" (from 2026-04-21).

- [ ] **TODO: tests/test_health_tech_debt.py:51**
  - TODO in tests/test_health_tech_debt.py:51 — fix this later\ny = 2\n# FIXME: broken\n" (from 2026-04-21).

- [ ] **XXX: tests/test_project_detector.py:17**
  - XXX in tests/test_project_detector.py:17 — /myproject -> -tmp-xxx-myproject (from 2026-04-21).

- [ ] **Unfinished work: 1 uncommitted files**
  - You have 1 uncommitted files.

> Single-method classes and deep nesting add complexity without value. Simplify to plain functions where possible.

- [ ] **tiny_file: gui/fmt_utils.py**
  - gui/fmt_utils.py — 8 lines, 1 function.

- [ ] **tiny_file: core/lang_detect.py**
  - core/lang_detect.py — 12 lines, 1 function.

- [ ] **single_method_class: plugins/port_map/widget.py**
  - class PortSummary has only 1 method.

- [ ] **single_method_class: plugins/port_map/widget.py**
  - class PortMapWidget has only 1 method.

- [ ] **single_method_class: plugins/security_scan/widget.py**
  - class SecuritySummary has only 1 method.

- [ ] **single_method_class: plugins/security_scan/widget.py**
  - class SecurityWidget has only 1 method.

- [ ] **tiny_file: plugins/security_scan/scanners/network.py**
  - plugins/security_scan/scanners/network.py — 13 lines, 1 function.

- [ ] **single_method_class: plugins/docker_monitor/widget.py**
  - class EventsLog has only 1 method.

- [ ] **single_method_class: plugins/docker_monitor/widget.py**
  - class DockerMonitorWidget has only 1 method.

> Giant commits are hard to review, hard to revert, and hard for AI to understand. Keep commits focused on one change.

- [ ] **Big commit: 7398e24 (43831 lines)**
  - Commit 'feat: open-source full codebase — Python core, Rust crates, GUI, tests, plugins' changed 43831 lines.

- [ ] **Working directly on master**
  - You're on 'master' and committing directly.

- [ ] **JS/TS files but no package.json**
  - You have JavaScript/TypeScript files but no package.json.

- [ ] **Style Scan: 0 AI slop, 31 quality issues**
  - 31 design quality issues — cramped padding, tiny fonts, !important abuse..

- [ ] **Design: cramped-padding (gui/win95_popup.py:70)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: contrast-check (gui/ui_dictionary_popup.py:97)**
  - Check text/background contrast ratio.

- [ ] **Design: cramped-padding (gui/ui_dictionary_popup.py:107)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: contrast-check (gui/ui_dictionary_popup.py:98)**
  - Check text/background contrast ratio.

- [ ] **Design: contrast-check (gui/changelog_popup.py:65)**
  - Check text/background contrast ratio.

- [ ] **Design: contrast-check (gui/changelog_popup.py:66)**
  - Check text/background contrast ratio.

- [ ] **Design: cramped-padding (gui/win95.py:142)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/win95.py:158)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/win95.py:229)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/security.py:81)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/security.py:94)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/security.py:82)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/security.py:95)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: contrast-check (gui/pages/docker.py:95)**
  - Check text/background contrast ratio.

- [ ] **Design: contrast-check (gui/pages/docker.py:96)**
  - Check text/background contrast ratio.

- [ ] **Design: cramped-padding (gui/pages/docker.py:207)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/docker.py:215)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/frozen_tab.py:164)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: contrast-check (gui/pages/overview.py:108)**
  - Check text/background contrast ratio.

- [ ] **Design: cramped-padding (gui/pages/overview.py:297)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: contrast-check (gui/pages/overview.py:109)**
  - Check text/background contrast ratio.

- [ ] **Design: cramped-padding (gui/pages/overview.py:298)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/activity/page.py:478)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/activity/page.py:696)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/safety_net/page.py:359)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/safety_net/page.py:360)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/health/page.py:329)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/health/page.py:428)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/health/page.py:458)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/health/page.py:477)**
  - Padding under 4px — too cramped, looks amateur.

- [ ] **Design: cramped-padding (gui/pages/health/page.py:330)**
  - Padding under 4px — too cramped, looks amateur.


---

## ⚠️ Possible false positives

The scanner uses static analysis and may flag valid code. Check these before blindly fixing:

- **map.modules**: Orphan detection doesn't track dynamic imports (importlib, __import__), lazy imports inside functions, or framework auto-discovery (Django admin autodiscover, pytest conftest). Files like `main.jsx`, `index.js`, `mongo-init.js` are often entry points loaded by bundlers or Docker — not real orphans.
- **dead.unused_imports**: Scanner may flag imports used only as type annotations in complex generics, or side-effect imports (e.g. model registration). Verify before deleting — check if the import is used in type hints, decorators, or has side effects on import.
- **dead.unused_definitions**: Functions/methods called dynamically (getattr, signals, event handlers) or exposed as public API may be flagged. Also: celery tasks discovered by name, pytest fixtures in conftest.py, and Django/DRF auto-discovered methods. Verify the function isn't called via string name or framework magic.
- **debt.no_types**: FastAPI/Flask endpoints with @router decorators get return types from the decorator (response_model=). Scanner skips these, but custom decorators may still trigger false alerts.

---

<details>
<summary>ℹ️ Info (14 items)</summary>

- **Project Map**: In your project: 362 files. Most common: .py (253). This is just context — now you know what's inside.
- **Entry Points**: Entry point = the file where everything starts. Like doors to a building. You have 11.
- **Hub: core/history.py**: core/history.py is imported by 34 files. This is your most important module. Break it — break everything.
- **Hub: i18n/__init__.py**: i18n/__init__.py is imported by 29 files. This is your most important module. Break it — break everything.
- **Hub: core/health/models.py**: core/health/models.py is imported by 20 files. This is your most important module. Break it — break everything.
- **Tests: 75 files (pytest)**: 75 test files found (75 Python). Framework: pytest.
- **Session: 8 commits, ~354 files touched**: Last 8 hours: 8 commits, ~354 files modified.
- **Before building — search first**: Before writing a new feature: google it. Check GitHub repos, PyPI, npm. Someone probably already built what you need. Don't reinvent the wheel — steal the wheel.
- **Git status: 1 untracked (new files git doesn't know about)**: Working tree: 1 untracked (new files git doesn't know about). Untracked files won't be saved until you 'git add' them.
- **Git commands you need right now**: git add <file> — start tracking a new file | git stash — temporarily hide changes, work on something else | git checkout -b my-feature — create a branch before changing master
- **README: 282 lines**: README looks complete (1364 words). Has install and run instructions.
- **Unknown packages: http, security, dev**: AI might not know these packages: http (pypi), security (pypi), dev (pypi). Fetch their docs so AI understands your stack.
### LLM Context Summary

Copy this to give AI context about your project:
# Project: fartrun-release

**Stack:** Python, JavaScript/TypeScript

**Size:** 362 files, 62 dirs

**Entry points:**
- `gui/app/main.py` — Python main module
- `gui/app/__main__.py` — Python package entry point
- `core/hooks/frozen_check.py` — Python script with __main__ guard
- `core/mcp/server.py` — Python main module
- `core/parser.py` — Python script with __main__ guard

**Key modules:**
- `core/history.py` (imported by 34 files)
- `i18n/__init__.py` (imported by 29 files)
- `core/health/models.py` (imported by 20 files)
- `core/haiku_client.py` (imported by 15 files)
- `gui/win95.py` (imported by 15 files)

- **Config Files**: 2 config files found.

</details>

---

## How to use this report with AI

Paste this file to Claude/Cursor and say:
```
Fix the issues in this health report, starting from HIGH severity.
Skip items marked as possible false positives.
```

---
*Scanned: [fartrun-release](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun) · Generated by [fartrun](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun) · MCP: `npx fartrun@latest install`*