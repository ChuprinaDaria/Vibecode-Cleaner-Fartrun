# Safety Net

The safety net protects your codebase from AI-induced damage through three mechanisms: Save Points, Rollback, and Frozen Files. These work together to ensure you can always undo what an AI agent did and protect critical files from being modified.

## Save Points

A save point is a lightweight snapshot of your project state. Under the hood it creates a git commit with a special tag and stores metadata in a local SQLite database.

### What Gets Saved

- All tracked files (staged and unstaged changes are committed)
- Git branch name and HEAD SHA
- Timestamp
- Optional user-provided label
- Health scan score (if a scan was run before saving)
- List of frozen files at time of save

### How It Works

1. `fartrun save` stages all changes (`git add -A`)
2. Creates a commit with message `[fartrun] save point: <label>`
3. Tags the commit as `fartrun-sp-<YYYYMMDD>-<N>`
4. Records metadata in `~/.local/share/fartrun/savepoints.db` (SQLite)

The SQLite database stores:
```sql
CREATE TABLE save_points (
    id TEXT PRIMARY KEY,
    sha TEXT NOT NULL,
    branch TEXT NOT NULL,
    label TEXT,
    created_at TEXT NOT NULL,
    score REAL,
    frozen_files TEXT,
    file_count INTEGER
);
```

### CLI Usage

```bash
fartrun save                        # auto-label with timestamp
fartrun save "before AI refactor"   # custom label
fartrun list saves                  # show all save points
fartrun list saves --limit 5        # last 5
```

### MCP Usage

```json
{"tool": "create_save_point", "input": {"dir": "/project", "message": "before migration"}}
{"tool": "list_save_points", "input": {"dir": "/project", "limit": 10}}
```

## Rollback

Rollback restores your project to a previous save point. It is designed to be safe — you never lose the current state.

### Rollback Process

1. Creates a backup branch: `fartrun-backup-<timestamp>` pointing to current HEAD
2. Performs `git reset --hard <save-point-sha>`
3. Records the rollback event in SQLite (who, when, from which SHA, to which save point)
4. Prints summary of what changed

### Safety Guarantees

- **Current state is always preserved** on the backup branch
- Rollback refuses to run if there are uncommitted changes (use `fartrun save` first or `--force`)
- The backup branch is never deleted automatically
- Rollback history is queryable via `fartrun list saves` (shows both saves and rollbacks)

### CLI Usage

```bash
fartrun rollback                    # interactive picker
fartrun rollback sp-20260418-1      # specific save point
fartrun rollback --latest           # most recent save point
```

### Failure Modes

| Situation | Behavior |
|-----------|----------|
| Dirty working tree | Refuses, asks to save first |
| Save point SHA missing (rebased away) | Error with suggestion to check backup branches |
| Not a git repo | Error |
| No save points exist | Error with instructions |

## Frozen Files

Frozen files cannot be edited by AI agents. Protection is enforced through two independent layers.

### Layer 1: CLAUDE.md Documentation

When you freeze a file, fartrun adds it to the project's `CLAUDE.md` under a "DO NOT TOUCH" section:

```markdown
## DO NOT TOUCH — managed by fartrun

These files are locked by the developer. **Do not edit or rewrite them.** Build around them.

- `src/core/auth.py`
- `src/config/production.toml`
```

Well-behaved AI agents read CLAUDE.md and respect these instructions. This layer works with any AI tool that supports project instructions.

### Layer 2: PreToolUse Hook Enforcement

For Claude Code specifically, fartrun installs a hook that intercepts file operations before they execute.

#### How the Hook Works

1. Claude Code calls the hook before every file write/edit operation
2. The hook receives a JSON payload on stdin:
```json
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/project/src/core/auth.py",
    "old_string": "...",
    "new_string": "..."
  }
}
```
3. The hook checks the target path against the frozen files list
4. Exit code determines the outcome:

| Exit Code | Meaning |
|-----------|---------|
| `0` | Allowed — proceed with the operation |
| `1` | Blocked — file is frozen, operation is rejected |
| `2` | Error in hook (operation proceeds with warning) |

The hook reads the frozen files list from `CLAUDE.md` and the SQLite database. Both sources must agree — if a file is in either list, it's considered frozen.

#### Installing the Hook

```bash
fartrun hook-install      # installs to .claude/hooks/
fartrun hook-uninstall    # removes the hook
```

The hook is a small Python script placed at `.claude/hooks/pre-tool-use.py`. It executes in under 50ms per check.

### Managing Frozen Files

```bash
fartrun freeze src/core/auth.py          # freeze a file
fartrun freeze "src/migrations/*.py"     # freeze with glob
fartrun unfreeze src/core/auth.py        # unfreeze
fartrun list frozen                      # show all frozen files
```

### Frozen Files in MCP

```json
{"tool": "freeze_file", "input": {"dir": "/project", "path": "src/core/auth.py"}}
{"tool": "unfreeze_file", "input": {"dir": "/project", "path": "src/core/auth.py"}}
{"tool": "list_frozen", "input": {"dir": "/project"}}
```

## Best Practices

1. **Save before every AI session.** Run `fartrun save` before asking an AI to make changes.
2. **Freeze auth, payment, and config files.** These are the most dangerous to edit incorrectly.
3. **Install the hook.** CLAUDE.md is advisory. The hook is enforcement.
4. **Check backup branches periodically.** Clean up old `fartrun-backup-*` branches when you're confident the rollbacks worked.
5. **Use labels.** `fartrun save "before AI refactor of payment flow"` is much more useful than an auto-timestamp.
