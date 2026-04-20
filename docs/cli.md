# CLI Reference

Fartrun ships as a single binary. All commands operate on the current directory unless `-C` is specified.

## Global Flags

| Flag | Description |
|------|-------------|
| `-C, --dir <path>` | Run in a different directory |
| `-v, --verbose` | Show detailed output (scanner internals, timing, file lists) |
| `-y, --yes` | Skip confirmation prompts (useful in CI) |
| `--no-color` | Disable colored output (also respects `NO_COLOR` env var) |
| `--json` | Output machine-readable JSON where supported |

## Commands

### `fartrun scan`

Run the full 9-phase health scan on the current project.

```bash
fartrun scan                  # standard scan
fartrun scan -v               # verbose — shows per-file findings, timing per phase
fartrun scan --json           # JSON output for piping to other tools
fartrun scan -C ~/projects/my-app
```

The scanner auto-detects project stack (Python, Go, TypeScript, React, Django, FastAPI) and adjusts checks accordingly. Results are grouped by severity: high, medium, low, info.

### `fartrun status`

Print a one-screen project health summary. Shows last scan time, overall score, top 5 issues, frozen file count, and save point history.

```bash
fartrun status
fartrun status --json
```

### `fartrun save`

Create a save point — a tagged git commit with SQLite metadata.

```bash
fartrun save                       # auto-generated message
fartrun save "before refactor"     # custom label
fartrun save -y                    # skip confirmation
```

Save points record: git SHA, timestamp, branch, file count, scan score (if available).

### `fartrun rollback`

Restore to a previous save point.

```bash
fartrun rollback                   # interactive — pick from list
fartrun rollback sp-20260418-1     # rollback to specific save point
fartrun rollback --latest          # rollback to most recent save point
```

Creates a backup branch `fartrun-backup-<timestamp>` before resetting, so nothing is truly lost.

### `fartrun freeze <path>`

Mark a file as frozen. Frozen files are protected by two layers: CLAUDE.md documentation and a PreToolUse hook that blocks edits.

```bash
fartrun freeze src/core/auth.py
fartrun freeze "src/config/*.toml"    # glob patterns supported
```

### `fartrun unfreeze <path>`

Remove freeze protection from a file.

```bash
fartrun unfreeze src/core/auth.py
```

### `fartrun list`

List frozen files and save points.

```bash
fartrun list frozen          # show all frozen files
fartrun list saves           # show all save points
fartrun list saves --limit 5 # last 5 save points
```

### `fartrun prompt`

Build a health-aware prompt for AI coding assistants. Outputs a structured prompt that includes current scan results, frozen file warnings, and action recommendations.

```bash
fartrun prompt                     # copy-paste ready prompt
fartrun prompt --clipboard         # copy directly to clipboard
fartrun prompt --format markdown   # markdown formatted
```

### `fartrun mcp`

Start the MCP server. Used by AI coding tools (Claude Code, Cursor, Windsurf) to access fartrun's 29 tools programmatically.

```bash
fartrun mcp                  # stdio transport (default)
fartrun mcp --http :3333     # HTTP/SSE transport on port 3333
```

Typically configured in your MCP client settings rather than run manually. See [MCP documentation](mcp.md).

### `fartrun context7-install`

Install Context7 MCP server for library documentation lookups.

```bash
fartrun context7-install           # install for detected MCP client
fartrun context7-install --cursor  # explicitly target Cursor
```

### `fartrun hook-install`

Install the PreToolUse hook that enforces frozen file protection in Claude Code.

```bash
fartrun hook-install
```

The hook reads JSON from stdin on each tool invocation and blocks writes to frozen files with a non-zero exit code.

### `fartrun hook-uninstall`

Remove the PreToolUse hook.

```bash
fartrun hook-uninstall
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (invalid args, missing config) |
| `2` | Scan completed with high-severity findings |
| `3` | Rollback failed (dirty working tree, missing save point) |
| `4` | Hook blocked an operation (frozen file edit attempt) |
| `10` | Network error (GitHub API, Context7) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required for prompt generation features |
| `NO_COLOR` | Disable colored output (any value) |
| `FARTRUN_CONFIG` | Override config file path |
| `FARTRUN_DATA_DIR` | Override data directory (save points DB, cache) |
| `FARTRUN_LOG` | Set log level: `error`, `warn`, `info`, `debug`, `trace` |

## Shell Completion

```bash
fartrun completions bash > ~/.local/share/bash-completion/completions/fartrun
fartrun completions zsh > ~/.zfunc/_fartrun
fartrun completions fish > ~/.config/fish/completions/fartrun.fish
```
