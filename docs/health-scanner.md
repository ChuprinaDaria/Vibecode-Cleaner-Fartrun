# Health Scanner

The health scanner runs 9 phases against your codebase, producing findings with severity levels and actionable recommendations. Heavy lifting is done by compiled Rust modules via PyO3 bindings for speed and accuracy.

## Scan Phases

### Phase 1: Project Map

Builds a complete file tree and module dependency graph. Identifies entry points (main files, CLI scripts, API routers), package boundaries, and circular imports.

Rust modules used: `file_tree`, `module_map`, `entry_points`

Detects: orphaned files, circular dependencies, overly deep directory nesting, missing `__init__.py` files.

### Phase 2: Dead Code

Finds unused functions, classes, imports, and variables by cross-referencing AST definitions against all usages across the project.

Rust module: `dead_code`

Uses tree-sitter for language-specific AST parsing. Understands Python decorators (`@app.route`, `@pytest.fixture`), Go interface implementations, React component exports, and framework-specific patterns that create implicit usage.

### Phase 3: Tech Debt

Flags accumulated technical debt markers.

Rust modules: `tech_debt`, `monsters`

Checks for:
- TODO/FIXME/HACK/XXX comments with age (git blame)
- Functions exceeding complexity thresholds (cyclomatic > 10)
- "Monster" functions: 100+ lines or 5+ levels of nesting
- Duplicated code blocks (exact and near-duplicates via `duplicates` module)
- Files over 500 lines
- Functions with 6+ parameters

### Phase 4: Git Hygiene

Analyzes the git repository health.

Checks for:
- Files over 1MB tracked in git
- Missing `.gitignore` for detected stack
- Committed secrets (basic pattern matching — see security scanner for full analysis)
- Stale branches (no commits in 90+ days)
- Force-push history on main branch
- Unsigned commits in production branches
- Uncommitted changes older than 24 hours

### Phase 5: Test Coverage

Maps test files to source files and identifies gaps.

Checks for:
- Test-to-source file ratio (flags below 0.3)
- Source modules with zero corresponding test files
- Test files that import nothing from the project (orphaned tests)
- Missing test configuration (pytest.ini, jest.config, etc.)
- Test files without assertions

### Phase 6: Documentation

Evaluates documentation completeness.

Checks for:
- Public functions/classes missing docstrings
- README.md freshness (last modified vs. last code change)
- Stale API documentation
- Missing type hints (Python), JSDoc (JavaScript), or GoDoc
- Undocumented exported symbols

### Phase 7: Framework Checks

Stack-specific best practice validation.

**Django/DRF:**
- N+1 query patterns (missing `select_related`/`prefetch_related`)
- Unindexed foreign keys
- Raw SQL without parameterization
- Missing CSRF middleware
- `DEBUG = True` in production config files

**FastAPI:**
- Sync functions in async routes
- Missing response models
- Untyped path/query parameters

**React/TypeScript:**
- Missing `key` props in lists
- Direct DOM manipulation
- `useEffect` with missing dependencies
- `any` type usage
- Components over 300 lines

### Phase 8: UI/UX Sanity

Frontend-specific checks for common mistakes.

Rust module: `ux_sanity`

Checks for:
- Missing `alt` attributes on images
- Hardcoded color values (should use theme/variables)
- z-index values over 9999
- Missing viewport meta tags
- Hardcoded strings (i18n candidates)
- Inaccessible click handlers (div with onClick, no keyboard equivalent)
- Missing form labels

### Phase 9: Context7 Recommendations

Cross-references findings with Context7 library documentation to suggest specific fixes using current best practices. Requires Context7 MCP to be installed.

Provides: library version-specific code examples, migration guides for outdated patterns, links to relevant documentation sections.

## Rust Backend

The scanner's core analysis is handled by compiled Rust modules exposed via PyO3:

| Module | Purpose |
|--------|---------|
| `dead_code` | Unused symbol detection via tree-sitter AST |
| `duplicates` | Near-duplicate code block detection |
| `entry_points` | Main file and API route entry point identification |
| `file_tree` | Fast recursive directory scanning with gitignore |
| `module_map` | Import graph construction |
| `tech_debt` | Complexity analysis, TODO scanning, monster detection |
| `monsters` | Large/complex function identification |
| `ux_sanity` | Frontend accessibility and sanity checks |

## Accuracy

Measured against manually annotated projects with known issues:

| Stack | Accuracy | Notes |
|-------|----------|-------|
| Python (stdlib) | 97% | Decorator-aware, handles `__all__` |
| Go | 97% | Interface-aware, handles embedded structs |
| TypeScript/React | 99% | JSX-aware, handles re-exports |
| FastAPI + React | 96% | Cross-stack, API contract validation |
| Django + DRF | 91% | Implicit ORM usage harder to trace |

False positive rate: <5% across all stacks. Django's lower accuracy comes from dynamic ORM patterns and implicit signal/receiver connections.

## Severity Levels

| Level | Meaning | Example |
|-------|---------|---------|
| `high` | Fix immediately — security risk or broken code | Committed API key, unreachable code in auth |
| `medium` | Fix soon — maintainability or performance impact | Monster function, N+1 query, missing tests |
| `low` | Fix when convenient — code quality improvement | Missing docstring, TODO older than 6 months |
| `info` | Awareness only — not necessarily a problem | Large file, many dependencies, stack detection |

## Output Format

Each finding includes:
```
severity: high
phase: dead_code
file: src/api/routes.py
line: 142
message: Function `calculate_legacy_discount` is never called
suggestion: Remove or verify it's used via dynamic dispatch
context7: null
```

When Context7 is available, `context7` contains a documentation snippet with the recommended pattern.
