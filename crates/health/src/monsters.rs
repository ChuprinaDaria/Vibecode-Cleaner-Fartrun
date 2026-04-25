//! Check 1.4 — Monster File Detection.
//!
//! Finds files > 500 lines with function/class counts via tree-sitter.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use pyo3::prelude::*;

use crate::common::{collect_source_files, is_generated_or_data_file, normalize_path, SOURCE_EXTENSIONS, WalkOpts};
use crate::scan_ctx::{parse_or_cached, CtxLang, ScanContext};

#[pyclass]
#[derive(Clone)]
pub struct MonsterFile {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub lines: u32,
    #[pyo3(get)]
    pub functions: u32,
    #[pyo3(get)]
    pub classes: u32,
    #[pyo3(get)]
    pub severity: String,
}

#[pyclass]
#[derive(Clone)]
pub struct MonstersResult {
    #[pyo3(get)]
    pub monsters: Vec<MonsterFile>,
}

fn severity_for_lines(lines: u32) -> Option<&'static str> {
    if lines > 3000 {
        Some("critical")
    } else if lines > 1000 {
        Some("high")
    } else if lines > 500 {
        Some("medium")
    } else {
        None
    }
}

/// Walk a parsed tree counting Python function/class definitions.
fn count_python_in_tree(tree: &tree_sitter::Tree) -> (u32, u32) {
    let mut functions: u32 = 0;
    let mut classes: u32 = 0;
    let mut cursor = tree.walk();
    crate::common::walk_nodes(&mut cursor, &mut |node| match node.kind() {
        "function_definition" => functions += 1,
        "class_definition" => classes += 1,
        _ => {}
    });
    (functions, classes)
}

/// Walk a parsed tree counting JS/TS function/class definitions.
fn count_js_in_tree(tree: &tree_sitter::Tree) -> (u32, u32) {
    let mut functions: u32 = 0;
    let mut classes: u32 = 0;
    let mut cursor = tree.walk();
    crate::common::walk_nodes(&mut cursor, &mut |node| match node.kind() {
        "function_declaration" | "arrow_function" | "method_definition"
        | "function_expression" | "generator_function_declaration" => functions += 1,
        "class_declaration" => classes += 1,
        _ => {}
    });
    (functions, classes)
}

/// Pure per-file analysis. Returns `None` when the file is too small to be
/// a "monster" or when reading/parsing fails — callers should treat that
/// as "this file produces no finding" rather than as an error.
fn analyze_monster_file(
    abs_path: &Path,
    rel_path: String,
    ext: &str,
    ctx: Option<&ScanContext>,
) -> Option<MonsterFile> {
    let content_arc: Arc<String> = if let Some(c) = ctx {
        c.read_file(&rel_path, abs_path)?
    } else {
        Arc::new(fs::read_to_string(abs_path).ok()?)
    };
    let content = content_arc.as_str();

    let line_count = content.lines().filter(|l| !l.trim().is_empty()).count() as u32;
    let severity = severity_for_lines(line_count)?;

    let (functions, classes) = match ext {
        "py" => {
            let tree = parse_or_cached(ctx, &rel_path, CtxLang::Python, content)?;
            count_python_in_tree(&tree)
        }
        "ts" | "mts" | "cts" => {
            let tree = parse_or_cached(ctx, &rel_path, CtxLang::TypeScript, content)?;
            count_js_in_tree(&tree)
        }
        "tsx" => {
            let tree = parse_or_cached(ctx, &rel_path, CtxLang::Tsx, content)?;
            count_js_in_tree(&tree)
        }
        "js" | "mjs" | "cjs" | "jsx" => {
            let tree = parse_or_cached(ctx, &rel_path, CtxLang::JavaScript, content)?;
            count_js_in_tree(&tree)
        }
        // Languages we don't tree-sitter parse: still report line count,
        // but functions/classes are reported as 0 (same as before).
        _ => (0, 0),
    };

    Some(MonsterFile {
        path: rel_path,
        lines: line_count,
        functions,
        classes,
        severity: severity.to_string(),
    })
}

#[pyfunction]
pub fn scan_monsters(path: &str) -> PyResult<MonstersResult> {
    scan_monsters_inner(path, None)
}

#[pyfunction]
pub fn scan_monsters_with_context(
    ctx: &ScanContext,
    path: &str,
) -> PyResult<MonstersResult> {
    scan_monsters_inner(path, Some(ctx))
}

fn scan_monsters_inner(path: &str, ctx: Option<&ScanContext>) -> PyResult<MonstersResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {path}"),
        ));
    }

    let mut monsters: Vec<MonsterFile> = Vec::new();

    for src in collect_source_files(root, &WalkOpts::default()) {
        if let Some(m) = analyze_monster_file(&src.abs_path, src.rel_path, src.ext.as_str(), ctx) {
            monsters.push(m);
        }
    }

    monsters.sort_by(|a, b| b.lines.cmp(&a.lines));
    Ok(MonstersResult { monsters })
}

/// Per-file variant: analyse only the explicitly-given relative paths.
/// Used by the orchestrator's git-delta path so a small change set
/// re-scans a few files instead of walking the whole tree.
///
/// Files that don't exist (e.g. deleted between the cached commit and HEAD),
/// have a non-source extension, or look generated are silently skipped —
/// callers handle "removed file" by pruning the cached entry separately.
#[pyfunction]
pub fn scan_monsters_files(root: &str, files: Vec<String>) -> PyResult<MonstersResult> {
    let root_path = Path::new(root);
    if !root_path.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {root}"),
        ));
    }

    let mut monsters: Vec<MonsterFile> = Vec::new();
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
        if let Some(m) = analyze_monster_file(&abs_path, rel_norm, &ext_lower, None) {
            monsters.push(m);
        }
    }

    monsters.sort_by(|a, b| b.lines.cmp(&a.lines));
    Ok(MonstersResult { monsters })
}
