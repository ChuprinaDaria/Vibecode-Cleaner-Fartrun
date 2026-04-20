# Architecture Overview

## High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                         │
├──────────┬──────────┬──────────────────┬────────────────┤
│  CLI     │  GUI     │  MCP Server      │  npm Installer │
│ (Python) │ (PyQt5)  │ (stdio / HTTP)   │  (Node.js)    │
├──────────┴──────────┴──────────────────┴────────────────┤
│                     CORE ENGINE                           │
├────────────┬────────────┬───────────────┬───────────────┤
│  Health    │  Security  │  Safety Net   │  Token        │
│  Scanner   │  Sentinel  │  (git-based)  │  Monitor      │
├────────────┴────────────┴───────────────┴───────────────┤
│                   RUST BACKEND (PyO3)                     │
├─────────────────────────────────────────────────────────┤
│  dead_code │ entry_points │ module_map │ duplicates     │
│  tech_debt │ monsters     │ ux_sanity  │ file_tree      │
└─────────────────────────────────────────────────────────┘
```

## Design Principles

1. **Everything local.** No code leaves the machine. No API calls for analysis. No telemetry.
2. **Rust for speed.** Tree-sitter AST parsing, PyO3 bindings to Python. Thousands of files in <2s.
3. **Python for flexibility.** CLI, GUI, MCP server, plugin system — all Python 3.11+.
4. **Degrade gracefully.** No Haiku key? Template prompts. No Rust crate? Python fallback. No GUI? CLI works.
5. **Vibe-coder first.** Messages explain *what* went wrong and *why* it matters in human language.

## Key Data Flows

### Health Scan
```
User → CLI/MCP/GUI
  → core.health.project_map.run_all_checks()
    → Rust: file_tree, entry_points, dead_code, duplicates, monsters
    → Python: git_survival, brake_system, framework_checks, test_detector
    → Context7: documentation recommendations
  → HealthReport (findings with severity + messages)
  → Output: terminal / Markdown / JSON / GUI
```

### Save Point
```
User → "fartrun save 'before AI touches this'"
  → SafetyNet.create_save_point()
    → git add -A && git commit (tagged)
    → SQLite: store metadata (id, label, timestamp, file_count)
  → Result: save point ID for future rollback
```

### MCP Tool Call
```
Claude Code → JSON-RPC → fartrun MCP server (stdio)
  → _registry.TOOL_HANDLERS[tool_name](args)
  → Returns TextContent (JSON or markdown)
```

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Core logic | Python 3.11+ |
| Performance | Rust + PyO3 |
| Desktop GUI | PyQt5 (Win95 theme) |
| Database | SQLite (thread-safe) |
| MCP transport | stdio (default) / HTTP+SSE |
| npm installer | Node.js 18+ |
| Build | PyInstaller (single binary) |
| CI/CD | GitHub Actions |
