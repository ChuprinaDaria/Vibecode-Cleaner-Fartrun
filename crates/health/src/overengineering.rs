//! Check 4.5 — Overengineering Detector.
//!
//! Finds: classes with 1 method, tiny files with 1 function,
//! deeply nested dirs with 1 file each.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use pyo3::prelude::*;

use crate::common::{collect_source_files, is_test_path, WalkOpts};
use crate::scan_ctx::{parse_or_cached, CtxLang, ScanContext};

/// Return true if this file follows a framework pattern that INTENTIONALLY
/// produces single-method classes: `NestJS` commands/migrations, Django/Alembic
/// migrations, Celery tasks, etc. Flagging these as "overengineered" is noise.
fn is_framework_single_method_file(rel_path: &str) -> bool {
    let p = rel_path.replace('\\', "/");
    // Path-segment based (directory convention)
    for seg in &[
        "/migrations/",
        "/commands/",
        "/upgrade-version-command/",
        "/alembic/versions/",
    ] {
        if p.contains(seg) {
            return true;
        }
    }
    let basename = p.rsplit('/').next().unwrap_or(&p);
    let stem = basename
        .rsplit('.')
        .nth(1)
        .or(Some(basename))
        .unwrap_or(basename);
    // Filename conventions — frameworks that expect single-method classes.
    // Match BOTH `foo.guard.ts` (dot-separated) and `foo-guard.ts` (dash-separated).
    let nest_suffixes = [
        "command", "migration", "guard", "interceptor", "pipe",
        "strategy", "filter", "middleware", "decorator", "listener",
    ];
    for suf in &nest_suffixes {
        // foo.guard.ts
        if basename.ends_with(&format!(".{suf}.ts"))
            || basename.ends_with(&format!(".{suf}.js"))
        {
            return true;
        }
        // foo-guard.ts
        if stem.ends_with(&format!("-{suf}")) {
            return true;
        }
    }
    // Python frameworks
    basename.ends_with(".job.py")
        || basename.ends_with(".command.py")
        || basename.ends_with("_migration.py")
}

#[pyclass]
#[derive(Clone)]
pub struct OverengineeringIssue {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub kind: String, // "single_method_class", "tiny_file", "deep_nesting"
    #[pyo3(get)]
    pub description: String,
}

#[pyclass]
#[derive(Clone)]
pub struct OverengineeringResult {
    #[pyo3(get)]
    pub issues: Vec<OverengineeringIssue>,
}

/// Base classes whose subclasses legitimately have few methods.
/// `QThread`: __init__ + `run()` is the standard pattern.
/// QDialog/QWidget: __init__ sets up UI, may have 1 accessor.
/// Thread: same as `QThread`.
/// Command (management commands, Click): __init__ + `handle()/invoke()`.
const FRAMEWORK_BASE_CLASSES: &[&str] = &[
    // Qt
    "QThread",
    "QRunnable",
    "QDialog",
    "QWidget",
    "QMainWindow",
    "QFrame",
    "QGroupBox",
    "QAbstractTableModel",
    "QAbstractItemModel",
    "QStyledItemDelegate",
    "QSortFilterProxyModel",
    "QTextEdit",
    "QPlainTextEdit",
    "QLineEdit",
    "QLabel",
    "QGraphicsView",
    // Python stdlib
    "Thread",
    "Process",
    // Django
    "BaseCommand",
    "View",
    "APIView",
    "ViewSet",
    "ModelViewSet",
    "Serializer",
    "ModelSerializer",
    "Migration",
    "AppConfig",
    "Middleware",
    // Django ORM & forms
    "Model",
    "Manager",
    "QuerySet",
    "Form",
    "ModelForm",
    // Flask / FastAPI
    "Resource",
    // Generic patterns
    "Exception",
    "Error",
    "TestCase",
    "Enum",
    "IntEnum",
    "StrEnum",
    "Protocol",
    "ABC",
    "TypedDict",
    "NamedTuple",
    "BaseModel",
];

/// Extract base class names from a Python `class_definition` node.
///
/// In tree-sitter-python the base-class list has field name "superclasses"
/// and node kind "`argument_list`". We look it up by field name first; if that
/// fails (older grammar versions) we fall back to scanning children for an
/// "`argument_list`" node.
fn extract_base_classes(node: tree_sitter::Node, content: &str) -> Vec<String> {
    let mut bases = Vec::new();

    let collect = |container: tree_sitter::Node, out: &mut Vec<String>| {
        for j in 0..container.child_count() {
            if let Some(base) = container.child(j as u32) {
                if let Ok(text) = base.utf8_text(content.as_bytes()) {
                    // Handle `module.ClassName` — take last segment.
                    let name = text.rsplit('.').next().unwrap_or(text).trim();
                    if !name.is_empty()
                        && !name.starts_with('(')
                        && !name.starts_with(')')
                        && name != ","
                    {
                        out.push(name.to_string());
                    }
                }
            }
        }
    };

    // tree-sitter-python uses field name "superclasses" for the base-class list.
    if let Some(superclasses) = node.child_by_field_name("superclasses") {
        collect(superclasses, &mut bases);
    }

    // Fallback: scan all children for an "argument_list" node.
    if bases.is_empty() {
        for i in 0..node.child_count() {
            if let Some(child) = node.child(i as u32) {
                if child.kind() == "argument_list" {
                    collect(child, &mut bases);
                }
            }
        }
    }

    bases
}

/// Check for single-method classes in Python.
fn check_single_method_classes_python(
    content: &str,
    rel_path: &str,
    ctx: Option<&ScanContext>,
) -> Vec<OverengineeringIssue> {
    let Some(tree) = parse_or_cached(ctx, rel_path, CtxLang::Python, content) else {
        return vec![];
    };

    let mut issues = Vec::new();
    let root = tree.root_node();

    for i in 0..root.child_count() {
        if let Some(node) = root.child(i as u32) {
            if node.kind() == "class_definition" {
                let class_name = node
                    .child_by_field_name("name")
                    .and_then(|n| n.utf8_text(content.as_bytes()).ok())
                    .unwrap_or("");
                let line = node.start_position().row as u32 + 1;

                // Skip classes that inherit from known framework bases.
                let bases = extract_base_classes(node, content);
                let is_framework_subclass = bases.iter().any(|b| {
                    FRAMEWORK_BASE_CLASSES.contains(&b.as_str())
                });
                if is_framework_subclass {
                    continue;
                }

                // Count methods (function_definition inside class body)
                let mut method_count = 0;
                let mut non_init_methods = 0;
                if let Some(body) = node.child_by_field_name("body") {
                    for j in 0..body.child_count() {
                        if let Some(child) = body.child(j as u32) {
                            if child.kind() == "function_definition" {
                                method_count += 1;
                                let method_name = child
                                    .child_by_field_name("name")
                                    .and_then(|n| n.utf8_text(content.as_bytes()).ok())
                                    .unwrap_or("");
                                if method_name != "__init__" && !method_name.starts_with("__") {
                                    non_init_methods += 1;
                                }
                            }
                        }
                    }
                }

                // Class with only 1 non-dunder method (+ optional __init__)
                if non_init_methods == 1 && method_count <= 2 {
                    issues.push(OverengineeringIssue {
                        path: rel_path.to_string(),
                        line,
                        kind: "single_method_class".to_string(),
                        description: format!(
                            "class {class_name} has only 1 method. Maybe just a function?"
                        ),
                    });
                }
            }
        }
    }

    issues
}

/// JS/TS base class names that are valid single-method patterns.
const JS_FRAMEWORK_BASES: &[&str] = &[
    // React
    "Component",
    "PureComponent",
    // Node.js
    "EventEmitter",
    "Transform",
    "Readable",
    "Writable",
    "Duplex",
    // Web Components
    "HTMLElement",
    // Testing
    "Error",
    "TypeError",
    "RangeError",
    // Nest.js / Angular
    "Injectable",
    "Controller",
    "Module",
    "Guard",
    "Interceptor",
    "Pipe",
];

/// Check for single-method classes in JS/TS.
fn check_single_method_classes_js(
    content: &str,
    rel_path: &str,
    is_ts: bool,
    ctx: Option<&ScanContext>,
) -> Vec<OverengineeringIssue> {
    let lang = if is_ts { CtxLang::TypeScript } else { CtxLang::JavaScript };
    let Some(tree) = parse_or_cached(ctx, rel_path, lang, content) else {
        return vec![];
    };

    let mut issues = Vec::new();
    let root = tree.root_node();

    let mut cursor = root.walk();
    crate::common::walk_nodes(&mut cursor, &mut |node| {
        if node.kind() == "class_declaration" {
            let class_name = node
                .child_by_field_name("name")
                .and_then(|n| n.utf8_text(content.as_bytes()).ok())
                .unwrap_or("");
            let line = node.start_position().row as u32 + 1;

            // Check `extends BaseClass` — skip if it's a known framework class.
            let mut is_framework = false;
            for i in 0..node.child_count() {
                if let Some(child) = node.child(i as u32) {
                    if child.kind() == "class_heritage" {
                        if let Ok(text) = child.utf8_text(content.as_bytes()) {
                            let base = text
                                .trim_start_matches("extends")
                                .trim()
                                .split(|c: char| c.is_whitespace() || c == '<' || c == '{')
                                .next()
                                .unwrap_or("")
                                .rsplit('.')
                                .next()
                                .unwrap_or("");
                            if JS_FRAMEWORK_BASES.contains(&base) {
                                is_framework = true;
                            }
                        }
                    }
                }
            }
            if is_framework {
                return;
            }

            if let Some(body) = node.child_by_field_name("body") {
                let mut method_count = 0;
                let mut non_constructor = 0;
                for j in 0..body.child_count() {
                    if let Some(child) = body.child(j as u32) {
                        if child.kind() == "method_definition" {
                            method_count += 1;
                            let name = child
                                .child_by_field_name("name")
                                .and_then(|n| n.utf8_text(content.as_bytes()).ok())
                                .unwrap_or("");
                            if name != "constructor" {
                                non_constructor += 1;
                            }
                        }
                    }
                }
                if non_constructor == 1 && method_count <= 2 {
                    issues.push(OverengineeringIssue {
                        path: rel_path.to_string(),
                        line,
                        kind: "single_method_class".to_string(),
                        description: format!(
                            "class {class_name} has only 1 method. Maybe just a function?"
                        ),
                    });
                }
            }
        }
    });

    issues
}

#[pyfunction]
pub fn scan_overengineering(path: &str) -> PyResult<OverengineeringResult> {
    scan_overengineering_inner(path, None)
}

#[pyfunction]
pub fn scan_overengineering_with_context(
    ctx: &ScanContext,
    path: &str,
) -> PyResult<OverengineeringResult> {
    scan_overengineering_inner(path, Some(ctx))
}

fn scan_overengineering_inner(
    path: &str,
    ctx: Option<&ScanContext>,
) -> PyResult<OverengineeringResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {path}"),
        ));
    }

    let mut issues: Vec<OverengineeringIssue> = Vec::new();

    // Track directory nesting: dir_path → file count
    let mut dir_file_counts: HashMap<String, u32> = HashMap::new();

    // Walk all source files (including generated/vendored) so we can count
    // every file in dir_file_counts. Per-file analysis below applies the
    // generated-file and test-file skips itself.
    let opts = WalkOpts {
        skip_generated: false,
        ..WalkOpts::default()
    };
    for src in collect_source_files(root, &opts) {
        // Track dir file counts (includes generated and test files —
        // the original behavior).
        if let Some(parent) = src.abs_path.parent() {
            if let Ok(rel_parent) = parent.strip_prefix(root) {
                let dir_key = rel_parent.to_string_lossy().to_string();
                *dir_file_counts.entry(dir_key).or_insert(0) += 1;
            }
        }

        // Skip test files
        if is_test_path(&src.rel_path) {
            continue;
        }

        // Skip generated/vendored files (e.g. .yarn/releases/yarn-4.x.cjs)
        if crate::common::is_generated_or_data_file(&src.rel_path) {
            continue;
        }

        let rel_path = src.rel_path;
        let ext = src.ext.as_str();

        // Skip framework conventions where single-method classes are expected
        // (NestJS commands, Django migrations, etc.)
        if is_framework_single_method_file(&rel_path) {
            continue;
        }

        // Read content (cached if context provided).
        let content_arc: std::sync::Arc<String> = if let Some(c) = ctx {
            match c.read_file(&rel_path, &src.abs_path) {
                Some(s) => s,
                None => continue,
            }
        } else {
            match fs::read_to_string(&src.abs_path) {
                Ok(s) => std::sync::Arc::new(s),
                Err(_) => continue,
            }
        };
        let content = content_arc.as_str();

        // Check tiny files (<20 non-empty lines with only 1 function, no classes)
        let non_empty_lines = content.lines().filter(|l| !l.trim().is_empty()).count();
        if non_empty_lines > 0 && non_empty_lines < 20 && !rel_path.ends_with("__init__.py") {
            let mut func_count = 0u32;
            let mut class_count = 0u32;

            // Quick count via tree-sitter (Python only). Goes through the
            // cross-scanner cache when one is provided so this parse may
            // be a free hit if module_map already saw the file.
            if ext == "py" {
                if let Some(tree) = parse_or_cached(ctx, &rel_path, CtxLang::Python, &content) {
                    let r = tree.root_node();
                    for i in 0..r.child_count() {
                        if let Some(child) = r.child(i as u32) {
                            match child.kind() {
                                "function_definition" => func_count += 1,
                                "class_definition" => class_count += 1,
                                _ => {}
                            }
                        }
                    }
                }
            }

            if func_count == 1 && class_count == 0 && non_empty_lines < 15 {
                issues.push(OverengineeringIssue {
                    path: rel_path.clone(),
                    line: 1,
                    kind: "tiny_file".to_string(),
                    description: format!(
                        "{rel_path} — {non_empty_lines} lines, 1 function. Maybe inline it where it's used?"
                    ),
                });
            }
        }

        // Check single-method classes
        if ext == "py" {
            issues.extend(check_single_method_classes_python(&content, &rel_path, ctx));
        } else {
            let is_ts = ext == "ts" || ext == "tsx" || ext == "mts" || ext == "cts";
            issues.extend(check_single_method_classes_js(&content, &rel_path, is_ts, ctx));
        }
    }

    // Check deep nesting: >3 levels where each level has only 1 source file
    // Walk dir tree to find chains of single-file dirs
    let mut nested_chains: Vec<(String, u32)> = Vec::new();
    for (dir, count) in &dir_file_counts {
        if *count == 1 && !dir.is_empty() {
            // Check parent chain
            let depth = dir.matches('/').count() + 1;
            if depth >= 3 {
                // Check if all ancestor dirs also have 1 file
                let parts: Vec<&str> = dir.split('/').collect();
                let mut all_single = true;
                for i in 1..parts.len() {
                    let ancestor = parts[..i].join("/");
                    if let Some(ancestor_count) = dir_file_counts.get(&ancestor) {
                        if *ancestor_count > 1 {
                            all_single = false;
                            break;
                        }
                    }
                }
                if all_single {
                    nested_chains.push((dir.clone(), depth as u32));
                }
            }
        }
    }

    for (dir, depth) in nested_chains {
        issues.push(OverengineeringIssue {
            path: dir.clone(),
            line: 0,
            kind: "deep_nesting".to_string(),
            description: format!(
                "{dir} — {depth} levels deep with 1 file each. Flatten the structure."
            ),
        });
    }

    Ok(OverengineeringResult { issues })
}
