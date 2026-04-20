# Rust Backend

Fartrun's performance-critical analysis is implemented in Rust and exposed to Python via PyO3 bindings. There are two crates: `health` for code analysis and `sentinel` for security scanning.

## Crate: `health`

The health crate provides AST-based code analysis using tree-sitter. It powers phases 1-3 and phase 8 of the health scanner.

### Modules

#### `dead_code`

Detects unused functions, classes, imports, and variables across the entire project.

How it works:
1. Parses every source file into a tree-sitter AST
2. Extracts all symbol definitions (functions, classes, constants, type aliases)
3. Extracts all symbol references (calls, imports, type annotations, decorators)
4. Cross-references definitions against references across all files
5. Filters out false positives: framework patterns, `__all__` exports, decorated handlers

Supported languages: Python, TypeScript/JavaScript, Go, Rust.

Language-specific awareness:
- **Python**: `@app.route`, `@pytest.fixture`, `@receiver`, `__init__`, `__all__`, `TYPE_CHECKING` blocks
- **TypeScript**: Re-exports, JSX component usage, barrel files (index.ts)
- **Go**: Interface implementations, `init()`, `main()`, exported symbols
- **Rust**: `#[test]`, `#[derive]`, trait implementations, `pub` visibility

#### `entry_points`

Identifies main entry points for the project.

Detects:
- `if __name__ == "__main__"` blocks
- `main()` functions (Go, Rust)
- Package `bin` entries (package.json)
- Framework CLI commands (manage.py, artisan)
- API router registrations (FastAPI, Express, Gin)
- Serverless handlers (Lambda, Cloud Functions)

#### `file_tree`

Fast recursive directory walker with `.gitignore` support.

Built on the `ignore` crate, which natively parses `.gitignore` files at every directory level. Skips binary files, node_modules, `.git`, `__pycache__`, and other common noise directories.

Returns a flat file list with metadata: path, size, last modified, language (detected by extension and shebang).

#### `module_map`

Builds an import dependency graph.

Parses import statements from AST (not regex) to handle:
- Python: `import x`, `from x import y`, relative imports
- TypeScript: `import`, `require()`, dynamic `import()`
- Go: `import` blocks, including aliased imports
- Rust: `use`, `mod`, `extern crate`

Returns an adjacency list suitable for cycle detection and dependency analysis.

#### `duplicates`

Near-duplicate code block detection.

Uses a rolling hash (Rabin fingerprint) over normalized AST nodes. Two code blocks are considered duplicates if they share 80%+ of their AST structure after normalizing identifiers. This catches renamed copies that simple text comparison would miss.

Minimum block size: 5 statements. Reports are grouped by duplicate clusters.

#### `reusable`

Identifies code that could be extracted into reusable functions or modules.

Looks for:
- Repeated patterns across files (similar but not identical logic)
- Long inline sequences that appear in multiple places
- Copy-pasted error handling blocks

#### `tech_debt`

Analyzes complexity and debt markers.

Metrics per function:
- Cyclomatic complexity
- Nesting depth (max and average)
- Line count
- Parameter count
- Cognitive complexity (weighted by nesting)

Also scans for: TODO/FIXME/HACK/XXX comments with git blame age, long files (500+ lines).

#### `monsters`

Flags "monster" functions — functions that are too large or complex for comfortable maintenance.

Thresholds (configurable):
- Lines > 100
- Cyclomatic complexity > 15
- Nesting depth > 5
- Parameters > 6

Returns the function name, location, and which thresholds were exceeded.

#### `overengineering`

Detects patterns that suggest unnecessary complexity.

Checks for:
- Abstract classes with a single implementation
- Factory patterns wrapping a single class
- Deeply nested generic types
- Interfaces implemented by one struct
- Configuration objects with 20+ fields

#### `ux_sanity`

Frontend-specific checks parsed from JSX/TSX/HTML AST.

Checks for:
- Missing `alt` on `<img>` elements
- Click handlers on non-interactive elements (`<div onClick>`)
- Hardcoded color values (not CSS variables or theme tokens)
- z-index values > 9999
- Missing `<label>` for form inputs
- Hardcoded strings (i18n candidates, detected by heuristics)

## Crate: `sentinel`

The sentinel crate implements the 10 security scanning modules. See [Security Scanner](security-scanner.md) for module details.

Each module is a Rust function that takes a file path and returns a vector of findings. The modules use:
- Compiled regex patterns (built once, reused per file)
- `rayon` for parallel file scanning
- `walkdir` + `.gitignore` for file discovery

## PyO3 Bindings

Both crates expose their public API through `#[pyfunction]` and `#[pyclass]` annotations:

```rust
#[pyfunction]
fn scan_dead_code(project_dir: &str, language: &str) -> PyResult<Vec<Finding>> {
    // ...
}

#[pyclass]
struct Finding {
    #[pyo3(get)]
    file: String,
    #[pyo3(get)]
    line: usize,
    #[pyo3(get)]
    message: String,
    #[pyo3(get)]
    severity: String,
}
```

Python calls these directly:
```python
from fartrun._rust import scan_dead_code, scan_security
findings = scan_dead_code("/path/to/project", "python")
```

## Building with Maturin

The Rust backend is built using [maturin](https://github.com/PyO3/maturin), which creates Python wheels with compiled Rust extensions.

### Development Build

```bash
cd rust/
maturin develop --release    # builds and installs into current venv
```

### Release Build

```bash
maturin build --release      # creates wheel in target/wheels/
```

### CI Build

GitHub Actions builds wheels for all platform/Python combinations:
- Linux: x86_64 + aarch64 (manylinux2014)
- macOS: x86_64 + arm64 (universal2)
- Windows: x86_64

## Performance Benchmarks

Measured on a 2023 MacBook Pro M3 (single-threaded unless noted):

| Operation | 10K files | 50K files | 100K files |
|-----------|-----------|-----------|------------|
| File tree scan | 45ms | 180ms | 340ms |
| Dead code (Python) | 320ms | 1.4s | 2.8s |
| Dead code (TypeScript) | 280ms | 1.2s | 2.4s |
| Module map | 150ms | 620ms | 1.1s |
| Duplicate detection | 410ms | 1.8s | 3.5s |
| Security sentinel (all 10) | 180ms | 750ms | 1.4s |
| Full health scan (all phases) | 1.2s | 4.8s | 9.1s |

Multi-threaded (8 cores): full health scan on 100K files completes in approximately 2.3s.

Tree-sitter parsing is the bottleneck for most operations. File I/O is negligible due to OS page cache on repeated scans.

## Tree-sitter Grammars

Bundled grammars (compiled into the binary):
- `tree-sitter-python`
- `tree-sitter-typescript` (includes TSX)
- `tree-sitter-javascript` (includes JSX)
- `tree-sitter-go`
- `tree-sitter-rust`
- `tree-sitter-html` (for UX sanity checks)
- `tree-sitter-css`

Adding a new language requires: adding the grammar crate to `Cargo.toml`, writing query patterns for dead code / imports / definitions, and testing against a reference project.
