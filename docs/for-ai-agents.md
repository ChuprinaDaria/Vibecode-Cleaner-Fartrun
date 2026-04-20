# Guide for AI Agents

This document explains how AI coding agents should interpret and act on fartrun data. If you are an AI agent reading this through MCP tool descriptions or project context, follow these guidelines.

## Reading Health Reports

### Action Priority

Findings are ordered by severity. Process them in this order:

1. **High severity** — fix these before writing new code. Security issues, broken imports, unreachable auth code.
2. **Medium severity** — fix during the current session if they are in files you are already editing. Monster functions, N+1 queries, missing tests for code you are changing.
3. **Low severity** — fix only if the user asks or you are already touching the file. Missing docstrings, old TODOs.
4. **Info** — read for context, do not act unless asked. Stack detection, file counts, dependency inventory.

### File and Line References

Every finding includes `file` and `line` fields. Use these to navigate directly to the problem:

```
file: src/api/routes.py
line: 142
message: Function `calculate_legacy_discount` is never called
```

Read the surrounding context (10-20 lines) before deciding what to do. The line number points to the definition, not necessarily the best place to make a change.

### Context7 Snippets

When a finding includes a `context7` field, it contains a documentation snippet from the relevant library's current version. Prefer this over your training data — library APIs change frequently.

```
context7:
  library: fastapi
  version: 0.115.0
  snippet: "Use Annotated[Depends(...)] instead of = Depends(...) for dependency injection"
```

Always use the Context7 snippet's version-specific advice over general knowledge.

## Trust Levels

Not all findings are equally reliable. Calibrate your response based on finding type:

| Finding Type | Trust Level | Agent Action |
|-------------|-------------|--------------|
| Hardcoded secrets | Very High | Always flag, never ignore |
| Unused imports | Very High | Safe to remove |
| Dead functions (Python, TS) | High | Remove if no dynamic dispatch |
| Dead functions (Django) | Medium | Verify — ORM signals and receivers create hidden usage |
| N+1 queries | High | Fix with `select_related`/`prefetch_related` |
| Missing tests | High | Note, but do not auto-generate tests without asking |
| Monster functions | High | Suggest refactoring, do not auto-refactor |
| Duplicate code | Medium | May be intentional (test fixtures, protocol implementations) |
| Missing docstrings | Medium | Add only if user asks or you are creating new code |
| Tech debt TODOs | Low | Informational, do not resolve without explicit instruction |
| UI/UX issues | Medium | Fix accessibility issues, leave style choices to the user |
| Overengineering | Medium | Informational — simplification is a design decision |

## False Positive Handling

When you suspect a finding is a false positive:

1. **Do not silently ignore it.** Mention it to the user: "The scanner flagged X, but this appears to be a false positive because Y."
2. **Common false positive patterns:**
   - Functions used via `getattr()`, reflection, or dynamic dispatch
   - Django signal receivers and management commands
   - Test helpers imported by conftest but not directly by test files
   - Go interface implementations where the function is called through the interface
   - React components used only in routing configuration
3. **If the user confirms it is a false positive**, suggest adding a suppression comment:
   ```python
   def legacy_handler():  # fartrun:ignore dead_code
   ```

## Save Points

### When to Create Save Points

Create a save point (via `create_save_point` tool) before:
- Refactoring multiple files
- Deleting code (dead code removal, dependency cleanup)
- Changing configuration files
- Running migrations
- Any operation the user describes as "risky" or "experimental"

You do not need to ask permission to create a save point. It is a safety measure, not a destructive operation.

### When to Suggest Rollback

Suggest rollback when:
- Tests that were passing now fail after your changes
- The health score dropped significantly after your work
- The user says something went wrong
- You realize mid-session that your approach was wrong

Use `rollback_save_point` to restore, then explain what happened.

## Frozen Files

**Frozen files must never be edited.** This is not a suggestion — it is a hard constraint.

When you encounter a frozen file:
1. Read it to understand its API/interface
2. Build around it — write code that uses it, do not modify it
3. If you think a frozen file needs changes, tell the user: "File X is frozen. To make this change, you would need to unfreeze it first."
4. Never suggest unfreezing as a casual step — the user froze it for a reason

Check frozen files before starting work:
```json
{"tool": "list_frozen", "input": {"dir": "/project"}}
```

## Token Efficiency Tips

### Use Summary Tools First

Start with `get_health_summary` instead of `run_health_scan`. The summary is compact and tells you if a full scan is warranted.

```json
{"tool": "get_health_summary", "input": {"dir": "/project"}}
```

### Request Specific Phases

If you only need security info, use `get_security_issues` instead of a full scan. Each phase has its own tool:
- `get_unused_code` — dead code only
- `get_tech_debt` — complexity and debt markers only
- `get_git_health` — git hygiene only
- `get_test_coverage` — test analysis only

### Limit Save Point Queries

Use the `limit` parameter when listing save points:
```json
{"tool": "list_save_points", "input": {"dir": "/project", "limit": 3}}
```

### Use search_code Wisely

The `search_code` tool is powerful but can return large results. Always provide a `glob` filter:
```json
{"tool": "search_code", "input": {"dir": "/project", "pattern": "def process_payment", "glob": "*.py"}}
```

## Workflow Example

A typical AI agent session with fartrun:

1. `get_health_summary` — understand the project state
2. `list_frozen` — know what you cannot touch
3. `create_save_point` — safety net before changes
4. Read the user's request and relevant findings
5. Make changes, respecting frozen files and finding priorities
6. `get_health_summary` — verify score did not drop
7. Report what you did and any findings you addressed

## Reporting to the User

When referencing fartrun findings in your responses:
- Include the file path and line number
- Quote the finding message
- Explain what you did about it (fixed, skipped, flagged as false positive)
- If you improved the health score, mention the before/after

Do not dump the entire scan output to the user. Summarize: "The scan found 3 high-severity issues in the auth module. I fixed the hardcoded key and the unused import. The third finding (dead function `legacy_auth`) may be used via dynamic dispatch — please confirm if it is safe to remove."
