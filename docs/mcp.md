# MCP Server & Tools

Fartrun exposes 29 tools via the Model Context Protocol. AI coding assistants call these tools to scan, save, freeze, and query your project without leaving their workflow.

## Transports

### stdio (default)

The standard transport for local MCP clients. The client spawns `fartrun mcp` as a subprocess and communicates via JSON-RPC over stdin/stdout.

MCP client config:
```json
{
  "command": "/path/to/fartrun",
  "args": ["mcp"]
}
```

### HTTP/SSE

For remote or multi-client setups. Start with:

```bash
fartrun mcp --http :3333
```

Clients connect via Server-Sent Events at `http://localhost:3333/sse` and POST tool calls to `http://localhost:3333/message`.

## Tool Categories

### Health (15 tools)

#### `run_health_scan`
Run the full 9-phase health scan.
```json
{ "dir": "/path/to/project", "verbose": false }
```
Returns structured findings grouped by phase and severity.

#### `get_health_summary`
Get a compact summary: overall score, top issues, stack detection.
```json
{ "dir": "/path/to/project" }
```

#### `get_unused_code`
Dead code detection powered by Rust tree-sitter analysis.
```json
{ "dir": "/path/to/project", "language": "python" }
```

#### `get_tech_debt`
Scan for TODOs, FIXMEs, complex functions, deep nesting, long files.
```json
{ "dir": "/path/to/project", "threshold": "medium" }
```

#### `get_security_issues`
Run the 10-module security sentinel scan.
```json
{ "dir": "/path/to/project" }
```

#### `get_module_graph`
Generate a module dependency graph. Returns adjacency list.
```json
{ "dir": "/path/to/project", "format": "json" }
```

#### `get_complexity_report`
Cyclomatic complexity per function. Flags "monster" functions.
```json
{ "dir": "/path/to/project", "min_complexity": 10 }
```

#### `get_git_health`
Git hygiene: large files, missing .gitignore, commit frequency, branch count.
```json
{ "dir": "/path/to/project" }
```

#### `get_test_coverage`
Test file discovery, test-to-source ratio, untested modules.
```json
{ "dir": "/path/to/project" }
```

#### `get_docs_quality`
Documentation coverage: missing docstrings, stale README, undocumented exports.
```json
{ "dir": "/path/to/project" }
```

#### `get_ui_issues`
UI/UX sanity checks: accessibility, hardcoded strings, missing alt text, z-index chaos.
```json
{ "dir": "/path/to/project" }
```

#### `get_framework_check`
Framework-specific best practices (Django N+1, React key props, FastAPI async).
```json
{ "dir": "/path/to/project" }
```

#### `get_outdated_deps`
Check for outdated or vulnerable dependencies.
```json
{ "dir": "/path/to/project" }
```

#### `get_config_map`
Map all config files: .env, toml, yaml, json configs with key inventory.
```json
{ "dir": "/path/to/project" }
```

#### `generate_health_report`
Generate a full markdown health report suitable for PRs or documentation.
```json
{ "dir": "/path/to/project", "format": "markdown" }
```

### Status (4 tools)

#### `get_status`
Current project state: branch, dirty files, last scan, save points.
```json
{ "dir": "/path/to/project" }
```

#### `get_activity`
Recent activity log: scans, saves, rollbacks, freezes with timestamps.
```json
{ "dir": "/path/to/project", "limit": 20 }
```

#### `detect_project_stack`
Auto-detect languages, frameworks, package managers, and config files.
```json
{ "dir": "/path/to/project" }
```

#### `search_code`
Regex search across project files with context lines.
```json
{ "dir": "/path/to/project", "pattern": "TODO|FIXME", "glob": "*.py" }
```

### Prompts (1 tool)

#### `build_prompt`
Generate an AI-ready prompt with scan results, frozen files, and action plan.
```json
{ "dir": "/path/to/project", "focus": "security" }
```

### Save Points (3 tools)

#### `create_save_point`
```json
{ "dir": "/path/to/project", "message": "before migration" }
```

#### `rollback_save_point`
```json
{ "dir": "/path/to/project", "save_id": "sp-20260418-1" }
```

#### `list_save_points`
```json
{ "dir": "/path/to/project", "limit": 10 }
```

### Frozen Files (3 tools)

#### `freeze_file`
```json
{ "dir": "/path/to/project", "path": "src/auth.py" }
```

#### `unfreeze_file`
```json
{ "dir": "/path/to/project", "path": "src/auth.py" }
```

#### `list_frozen`
```json
{ "dir": "/path/to/project" }
```

### Integrations (3 tools)

#### `install_context7`
Install Context7 MCP server for library documentation lookups.
```json
{ "target": "claude" }
```

#### `uninstall_context7`
Remove Context7 integration.
```json
{ "target": "claude" }
```

#### `list_prompts`
List available prompt templates.
```json
{}
```

## Error Handling

All tools return structured errors:
```json
{
  "error": {
    "code": "SCAN_FAILED",
    "message": "Directory not found: /path/to/project",
    "details": null
  }
}
```

Common error codes: `SCAN_FAILED`, `SAVE_FAILED`, `ROLLBACK_FAILED`, `FROZEN_FILE`, `INVALID_INPUT`, `NOT_A_GIT_REPO`.
