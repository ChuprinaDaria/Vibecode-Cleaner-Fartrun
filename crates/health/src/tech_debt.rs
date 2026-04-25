//! Check 3.2–3.5 — Tech Debt Detection.
//!
//! Missing type hints, error handling gaps, hardcoded values, TODO/FIXME audit.

use std::fs;
use std::path::{Path, PathBuf};

use pyo3::prelude::*;
use regex::Regex;

use crate::common::{
    collect_source_files, is_generated_or_data_file, is_test_path, normalize_path,
    SOURCE_EXTENSIONS, WalkOpts,
};

// --- PyO3 result structs ---

#[pyclass]
#[derive(Clone)]
pub struct MissingType {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub function_name: String,
    #[pyo3(get)]
    pub param_count: u32,
    #[pyo3(get)]
    pub missing_return: bool,
}

#[pyclass]
#[derive(Clone)]
pub struct ErrorGap {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub kind: String,
    #[pyo3(get)]
    pub description: String,
}

#[pyclass]
#[derive(Clone)]
pub struct HardcodedValue {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub value: String,
    #[pyo3(get)]
    pub kind: String,
}

#[pyclass]
#[derive(Clone)]
pub struct TodoItem {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub text: String,
    #[pyo3(get)]
    pub kind: String,
}

#[pyclass]
#[derive(Clone)]
pub struct TechDebtResult {
    #[pyo3(get)]
    pub missing_types: Vec<MissingType>,
    #[pyo3(get)]
    pub error_gaps: Vec<ErrorGap>,
    #[pyo3(get)]
    pub hardcoded: Vec<HardcodedValue>,
    #[pyo3(get)]
    pub todos: Vec<TodoItem>,
}

// --- Check 3.2: Missing Type Hints ---

fn check_missing_types_python(content: &str, rel_path: &str) -> Vec<MissingType> {
    let mut parser = tree_sitter::Parser::new();
    if let Err(e) = parser.set_language(&tree_sitter_python::LANGUAGE.into()) {
        eprintln!("health::tech_debt: set_language(python) failed for {rel_path}: {e}");
        return vec![];
    }
    let tree = match parser.parse(content, None) {
        Some(t) => t,
        None => return vec![],
    };

    let mut results = Vec::new();
    let mut cursor = tree.walk();

    crate::common::walk_nodes(&mut cursor, &mut |node| {
        if node.kind() != "function_definition" {
            return;
        }

        let line = node.start_position().row as u32 + 1;

        // Get function name
        let func_name = node
            .child_by_field_name("name")
            .and_then(|n| n.utf8_text(content.as_bytes()).ok())
            .unwrap_or("");

        // Skip dunders, test funcs, private
        if func_name.starts_with("__") || func_name.starts_with("test_") {
            return;
        }

        // Skip FastAPI/Flask endpoint functions — return type is defined
        // by the decorator (@router.get, @app.post, response_model=...).
        if let Some(parent) = node.parent() {
            if parent.kind() == "block" || parent.kind() == "decorated_definition" {
                let check_node = if parent.kind() == "decorated_definition" {
                    parent
                } else {
                    // Walk up from block to possible decorated_definition
                    parent.parent().filter(|gp| gp.kind() == "decorated_definition")
                        .unwrap_or(parent)
                };
                if check_node.kind() == "decorated_definition" {
                    let dec_text = check_node.utf8_text(content.as_bytes()).unwrap_or("");
                    let first_line = dec_text.lines().next().unwrap_or("");
                    if first_line.contains("router.") || first_line.contains("app.") {
                        return;
                    }
                }
            }
        }

        // Check parameters
        let params = match node.child_by_field_name("parameters") {
            Some(p) => p,
            None => return,
        };

        let mut untyped_count: u32 = 0;
        let mut total_params: u32 = 0;

        for i in 0..params.child_count() {
            if let Some(param) = params.child(i as u32) {
                // Skip self, cls, *args, **kwargs, /, *
                let kind = param.kind();
                if kind == "identifier" {
                    let name = param.utf8_text(content.as_bytes()).unwrap_or("");
                    if name == "self" || name == "cls" {
                        continue;
                    }
                    total_params += 1;
                    untyped_count += 1;
                } else if kind == "typed_parameter" {
                    total_params += 1;
                    // Has type — not untyped
                } else if kind == "default_parameter" {
                    total_params += 1;
                    // Check if it has a type annotation
                    let param_text = param.utf8_text(content.as_bytes()).unwrap_or("");
                    if !param_text.contains(':') {
                        untyped_count += 1;
                    }
                }
            }
        }

        // Check return type
        let return_type = node.child_by_field_name("return_type");
        let missing_return = return_type.is_none();

        if untyped_count > 0 || (missing_return && total_params > 0) {
            results.push(MissingType {
                path: rel_path.to_string(),
                line,
                function_name: func_name.to_string(),
                param_count: untyped_count,
                missing_return,
            });
        }
    });

    results
}

// --- Check 3.3: Error Handling Gaps ---

fn check_error_gaps_python(content: &str, rel_path: &str) -> Vec<ErrorGap> {
    let mut parser = tree_sitter::Parser::new();
    if let Err(e) = parser.set_language(&tree_sitter_python::LANGUAGE.into()) {
        eprintln!("health::tech_debt: set_language(python) failed for {rel_path}: {e}");
        return vec![];
    }
    let tree = match parser.parse(content, None) {
        Some(t) => t,
        None => return vec![],
    };

    let mut results = Vec::new();
    let mut cursor = tree.walk();

    crate::common::walk_nodes(&mut cursor, &mut |node| {
        if node.kind() == "except_clause" {
            let line = node.start_position().row as u32 + 1;
            let text = node.utf8_text(content.as_bytes()).unwrap_or("");

            // Check if text matches bare "except:" pattern
            let trimmed = text.trim();
            if trimmed.starts_with("except:") || trimmed == "except :" {
                results.push(ErrorGap {
                    path: rel_path.to_string(),
                    line,
                    kind: "bare_except".to_string(),
                    description: "Bare except catches everything including KeyboardInterrupt".to_string(),
                });
            }

            // Check for except ... : pass
            if let Some(body) = node.child_by_field_name("body")
                .or_else(|| {
                    // Find block child
                    (0..node.child_count())
                        .filter_map(|i| node.child(i as u32))
                        .find(|c| c.kind() == "block")
                })
            {
                let body_text = body.utf8_text(content.as_bytes()).unwrap_or("").trim().to_string();
                if body_text == "pass" || body_text.ends_with("\n    pass") || body_text.trim() == "pass" {
                    // Check if the block only has 'pass'
                    let child_count = body.child_count();
                    let non_trivial = (0..child_count)
                        .filter_map(|i| body.child(i as u32))
                        .filter(|c| c.kind() != "pass_statement" && c.kind() != "comment")
                        .count();
                    if non_trivial == 0 {
                        results.push(ErrorGap {
                            path: rel_path.to_string(),
                            line,
                            kind: "except_pass".to_string(),
                            description: "except with only 'pass' — silently swallows errors".to_string(),
                        });
                    }
                }
            }
        }
    });

    results
}

fn check_error_gaps_js(content: &str, rel_path: &str, is_ts: bool) -> Vec<ErrorGap> {
    let mut parser = tree_sitter::Parser::new();
    let lang = if is_ts {
        tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into()
    } else {
        tree_sitter_javascript::LANGUAGE.into()
    };
    if let Err(e) = parser.set_language(&lang) {
        eprintln!(
            "health::tech_debt: set_language({}) failed for {rel_path}: {e}",
            if is_ts { "ts" } else { "js" }
        );
        return vec![];
    }
    let tree = match parser.parse(content, None) {
        Some(t) => t,
        None => return vec![],
    };

    let mut results = Vec::new();
    let mut cursor = tree.walk();

    crate::common::walk_nodes(&mut cursor, &mut |node| {
        // Empty catch block
        if node.kind() == "catch_clause" {
            let line = node.start_position().row as u32 + 1;
            if let Some(body) = node.child_by_field_name("body") {
                let body_text = body.utf8_text(content.as_bytes()).unwrap_or("").trim().to_string();
                // Empty body: just { } or { // comment }
                let stripped = body_text.trim_start_matches('{').trim_end_matches('}').trim();
                if stripped.is_empty() || stripped.starts_with("//") {
                    results.push(ErrorGap {
                        path: rel_path.to_string(),
                        line,
                        kind: "empty_catch".to_string(),
                        description: "Empty catch block — errors silently swallowed".to_string(),
                    });
                }
            }
        }

        // .then() without .catch()
        if node.kind() == "call_expression" {
            if let Some(func) = node.child_by_field_name("function") {
                if func.kind() == "member_expression" {
                    if let Some(prop) = func.child_by_field_name("property") {
                        let prop_name = prop.utf8_text(content.as_bytes()).unwrap_or("");
                        if prop_name == "then" {
                            // Check if parent chain has .catch()
                            let line = node.start_position().row as u32 + 1;
                            let full_line = content.lines().nth(line as usize - 1).unwrap_or("");
                            if !full_line.contains(".catch") {
                                // Check next few lines too
                                let next_lines: String = content
                                    .lines()
                                    .skip(line as usize)
                                    .take(3)
                                    .collect::<Vec<_>>()
                                    .join(" ");
                                if !next_lines.contains(".catch") {
                                    results.push(ErrorGap {
                                        path: rel_path.to_string(),
                                        line,
                                        kind: "then_no_catch".to_string(),
                                        description: ".then() without .catch() — unhandled promise rejection".to_string(),
                                    });
                                }
                            }
                        }
                    }
                }
            }
        }
    });

    results
}

// --- Check 3.4: Hardcoded Values ---

fn check_hardcoded(content: &str, rel_path: &str) -> Vec<HardcodedValue> {
    use std::sync::LazyLock;
    static URL_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r#"["'](https?://[^"']+)["']"#).unwrap());
    static SLEEP_PY_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"sleep\((\d+)\)").unwrap());
    static SLEEP_JS_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"setTimeout\([^,]+,\s*(\d+)\)").unwrap());
    let url_re = &*URL_RE;
    let sleep_py_re = &*SLEEP_PY_RE;
    let sleep_js_re = &*SLEEP_JS_RE;

    let mut results = Vec::new();

    for (idx, line) in content.lines().enumerate() {
        let line_num = idx as u32 + 1;
        let trimmed = line.trim();

        // Skip comments
        if trimmed.starts_with('#') || trimmed.starts_with("//") || trimmed.starts_with('*') {
            continue;
        }
        // Skip test files (by content pattern)
        if trimmed.starts_with("assert") || trimmed.starts_with("expect(") {
            continue;
        }

        // Hardcoded URLs
        for cap in url_re.captures_iter(line) {
            let url = &cap[1];
            // Skip common non-issues
            if url.contains("localhost")
                || url.contains("127.0.0.1")
                || url.contains("example.com")
                || url.contains("schema.org")
                || url.contains("w3.org")
                || url.contains("github.com")
                || url.contains("pypi.org")
                || url.contains("npmjs.com")
            {
                continue;
            }
            results.push(HardcodedValue {
                path: rel_path.to_string(),
                line: line_num,
                value: url.to_string(),
                kind: "url".to_string(),
            });
        }

        // sleep() with large values
        for cap in sleep_py_re.captures_iter(line) {
            if let Ok(val) = cap[1].parse::<u64>() {
                if val > 10 {
                    results.push(HardcodedValue {
                        path: rel_path.to_string(),
                        line: line_num,
                        value: format!("sleep({val})"),
                        kind: "sleep".to_string(),
                    });
                }
            }
        }

        // setTimeout with large values
        for cap in sleep_js_re.captures_iter(line) {
            if let Ok(val) = cap[1].parse::<u64>() {
                if val > 10000 {
                    results.push(HardcodedValue {
                        path: rel_path.to_string(),
                        line: line_num,
                        value: format!("setTimeout(..., {val})"),
                        kind: "timeout".to_string(),
                    });
                }
            }
        }
    }

    results
}

// --- Check 3.5: TODO/FIXME/HACK ---

fn check_todos(content: &str, rel_path: &str) -> Vec<TodoItem> {
    use std::sync::LazyLock;
    static TODO_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?i)\b(TODO|FIXME|HACK|XXX|TEMP)\b(.*)").unwrap());
    let todo_re = &*TODO_RE;

    let mut results = Vec::new();

    for (idx, line) in content.lines().enumerate() {
        let trimmed = line.trim();
        // Only in comments
        if !trimmed.starts_with('#')
            && !trimmed.starts_with("//")
            && !trimmed.contains("# ")
            && !trimmed.contains("// ")
        {
            continue;
        }

        if let Some(cap) = todo_re.captures(trimmed) {
            let kind = cap[1].to_uppercase();
            let rest = cap.get(2).map_or("", |m| m.as_str()).trim();
            let text = if rest.starts_with(':') || rest.starts_with(' ') {
                rest.trim_start_matches(':').trim()
            } else {
                rest
            };

            results.push(TodoItem {
                path: rel_path.to_string(),
                line: idx as u32 + 1,
                text: text.to_string(),
                kind,
            });
        }
    }

    results
}

// --- Main scan function ---

/// Run all per-file tech-debt checks for a single file and append findings
/// to the four result vectors. Pure function — no cross-file state.
fn analyze_tech_debt_file(
    abs_path: &Path,
    rel_path: &str,
    ext: &str,
    missing_types: &mut Vec<MissingType>,
    error_gaps: &mut Vec<ErrorGap>,
    hardcoded: &mut Vec<HardcodedValue>,
    todos: &mut Vec<TodoItem>,
) {
    let is_test = is_test_path(rel_path);
    let Ok(content) = fs::read_to_string(abs_path) else {
        return;
    };

    if ext == "py" {
        if !is_test {
            missing_types.extend(check_missing_types_python(&content, rel_path));
        }
        error_gaps.extend(check_error_gaps_python(&content, rel_path));
    } else {
        let is_ts = matches!(ext, "ts" | "tsx" | "mts" | "cts");
        error_gaps.extend(check_error_gaps_js(&content, rel_path, is_ts));
        // JS type hint check only for .js (TS already has types)
        // Skip for now — JSDoc parsing is complex, add later
    }

    if !is_test {
        hardcoded.extend(check_hardcoded(&content, rel_path));
    }
    todos.extend(check_todos(&content, rel_path));
}

#[pyfunction]
pub fn scan_tech_debt(path: &str) -> PyResult<TechDebtResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {path}"),
        ));
    }

    let mut missing_types = Vec::new();
    let mut error_gaps = Vec::new();
    let mut hardcoded = Vec::new();
    let mut todos = Vec::new();

    for src in collect_source_files(root, &WalkOpts::default()) {
        analyze_tech_debt_file(
            &src.abs_path,
            &src.rel_path,
            src.ext.as_str(),
            &mut missing_types,
            &mut error_gaps,
            &mut hardcoded,
            &mut todos,
        );
    }

    Ok(TechDebtResult { missing_types, error_gaps, hardcoded, todos })
}

/// Per-file variant: analyse only the explicitly-given relative paths.
/// Same skip rules as `scan_tech_debt` (non-source extensions, generated
/// files, missing files) — see `scan_monsters_files` for rationale.
#[pyfunction]
pub fn scan_tech_debt_files(root: &str, files: Vec<String>) -> PyResult<TechDebtResult> {
    let root_path = Path::new(root);
    if !root_path.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {root}"),
        ));
    }

    let mut missing_types = Vec::new();
    let mut error_gaps = Vec::new();
    let mut hardcoded = Vec::new();
    let mut todos = Vec::new();

    for rel_raw in files {
        let rel_norm = normalize_path(&rel_raw);
        if is_generated_or_data_file(&rel_norm) {
            continue;
        }
        let abs_path: PathBuf = root_path.join(&rel_norm);
        let Some(ext_raw) = abs_path.extension().and_then(|e| e.to_str()) else {
            continue;
        };
        let ext_lower = ext_raw.to_ascii_lowercase();
        if !SOURCE_EXTENSIONS.iter().any(|e| e.eq_ignore_ascii_case(&ext_lower)) {
            continue;
        }
        if !abs_path.is_file() {
            continue;
        }
        analyze_tech_debt_file(
            &abs_path,
            &rel_norm,
            &ext_lower,
            &mut missing_types,
            &mut error_gaps,
            &mut hardcoded,
            &mut todos,
        );
    }

    Ok(TechDebtResult { missing_types, error_gaps, hardcoded, todos })
}
