# Configuration

Fartrun uses TOML for configuration. Settings control scanner behavior, sound effects, alerts, plugins, and safety net features.

## Config File Locations

The config file is searched in this order (first found wins):

1. Path specified by `FARTRUN_CONFIG` environment variable
2. `./fartrun.toml` (project-local)
3. `~/.config/fartrun/config.toml` (Linux)
4. `~/Library/Application Support/fartrun/config.toml` (macOS)
5. `%APPDATA%\fartrun\config.toml` (Windows)

If no config file is found, defaults are used. Project-local config overrides user-level config for settings that exist in both.

## Data Directory

Save points database, scan cache, and activity logs are stored in:

| OS | Path |
|----|------|
| Linux | `~/.local/share/fartrun/` |
| macOS | `~/Library/Application Support/fartrun/` |
| Windows | `%LOCALAPPDATA%\fartrun\` |

Override with `FARTRUN_DATA_DIR` environment variable.

## Full Config Reference

### `[general]`

```toml
[general]
language = "en"           # "en" or "ua" — affects nagger messages
editor = "code"           # editor command for "open file" actions
theme = "win95"           # GUI theme: "win95", "win98", "winxp"
auto_scan = true          # run scan on project open (GUI only)
scan_on_save = false      # re-scan after creating a save point
verbose = false           # default verbosity for CLI output
```

### `[sounds]`

```toml
[sounds]
enabled = true            # master switch for all sounds
volume = 0.7              # 0.0 to 1.0
fart_mode = "gentle"      # "gentle" or "loud"
hasselhoff = false        # enable Hasselhoff mode
hasselhoff_song = "auto"  # "auto", "freedom", "survivor", "du"
```

When `hasselhoff = true`, low health scores trigger David Hasselhoff motivational audio instead of standard fart sounds.

### `[alerts]`

```toml
[alerts]
min_severity = "medium"   # minimum severity to display: "high", "medium", "low", "info"
desktop_notifications = true  # OS-native notifications
tray_badge = true         # show issue count on tray icon
sound_on_high = true      # play sound for high-severity findings
```

### `[plugins]`

```toml
[plugins]
enabled = ["security_scan", "test_runner", "docker_monitor", "port_map"]
custom_dir = "~/.config/fartrun/plugins"  # directory for custom plugins
```

Disable a built-in plugin by removing it from the `enabled` list.

### `[snapshots]`

```toml
[snapshots]
auto_save = false         # create save point before every scan
max_save_points = 50      # auto-prune oldest save points beyond this count
prune_older_than = "90d"  # auto-prune save points older than this
keep_backup_branches = true  # keep fartrun-backup-* branches on prune
```

### `[haiku]`

```toml
[haiku]
enabled = true            # show haiku in scan output
language = "en"           # "en" or "ua"
```

When enabled, scan results include a contextual haiku about your code health. This is a cosmetic feature.

### `[safety_net]`

```toml
[safety_net]
hook_enabled = true       # PreToolUse hook active
claude_md_sync = true     # sync frozen files to CLAUDE.md
frozen_files = [          # files to freeze (also manageable via CLI)
    "src/core/auth.py",
    "src/config/production.toml",
    "migrations/*.py"
]
```

### `[status]`

```toml
[status]
show_score = true         # show health score in status
show_issues = 5           # number of top issues to show
show_saves = 3            # number of recent save points to show
show_frozen = true        # show frozen file count
```

### `[alert_filters]`

```toml
[alert_filters]
ignore_patterns = [
    "test_fixtures/**",
    "docs/examples/**",
    "*.generated.py"
]
ignore_modules = []       # e.g., ["secrets"] to skip a security module
ignore_phases = []        # e.g., ["ui_ux"] to skip a scanner phase
ignore_rules = [          # specific rule IDs
    "dead-code-test-helper",
    "todo-in-test-file"
]
```

### `[tests]`

```toml
[tests]
runner = "auto"           # "auto", "pytest", "jest", "go", "cargo"
test_dir = "tests"        # override test directory detection
min_coverage = 60         # flag projects below this coverage percentage
timeout = 300             # test runner timeout in seconds
```

## Environment Variables

| Variable | Description | Overrides |
|----------|-------------|-----------|
| `FARTRUN_CONFIG` | Config file path | Search order |
| `FARTRUN_DATA_DIR` | Data directory path | OS-specific default |
| `FARTRUN_LOG` | Log level (error/warn/info/debug/trace) | — |
| `ANTHROPIC_API_KEY` | For prompt generation | — |
| `NO_COLOR` | Disable colored output | `general.color` |
| `EDITOR` | Fallback editor command | `general.editor` |

## Config Precedence

When the same setting is specified in multiple places:

1. **CLI flags** (highest priority) — e.g., `--verbose` overrides `general.verbose`
2. **Environment variables** — e.g., `NO_COLOR` overrides color settings
3. **Project-local config** — `./fartrun.toml`
4. **User-level config** — `~/.config/fartrun/config.toml`
5. **Defaults** (lowest priority)

## Generating a Default Config

```bash
fartrun config init                # create config with defaults
fartrun config init --project      # create project-local fartrun.toml
fartrun config show                # print resolved config (all sources merged)
fartrun config validate            # check config for errors
```
