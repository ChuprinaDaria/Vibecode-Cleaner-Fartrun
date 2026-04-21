//! Check 1.4 — Monster File Detection.
//!
//! Finds files > 500 lines with function/class counts via tree-sitter.

use std::fs;
use std::path::Path;

use ignore::WalkBuilder;
use pyo3::prelude::*;

use crate::common::{is_generated_or_data_file, should_skip_entry, SOURCE_EXTENSIONS};

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

fn count_definitions_python(content: &str) -> (u32, u32) {
    let mut parser = tree_sitter::Parser::new();
    if parser
        .set_language(&tree_sitter_python::LANGUAGE.into())
        .is_err()
    {
        return (0, 0);
    }

    let tree = match parser.parse(content, None) {
        Some(t) => t,
        None => return (0, 0),
    };

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

fn count_definitions_js(content: &str, is_ts: bool) -> (u32, u32) {
    let mut parser = tree_sitter::Parser::new();
    if is_ts {
        let _ = parser.set_language(&tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into());
    } else {
        let _ = parser.set_language(&tree_sitter_javascript::LANGUAGE.into());
    }

    let tree = match parser.parse(content, None) {
        Some(t) => t,
        None => return (0, 0),
    };

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

#[pyfunction]
pub fn scan_monsters(path: &str) -> PyResult<MonstersResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {}", path),
        ));
    }

    let mut monsters: Vec<MonsterFile> = Vec::new();

    let walker = WalkBuilder::new(root)
        .hidden(false)
        .git_ignore(true)
        .git_global(false)
        .git_exclude(true)
        .filter_entry(|entry| !should_skip_entry(entry))
        .build();

    for entry in walker.flatten() {
        let entry_path = entry.path();
        if !entry_path.is_file() {
            continue;
        }

        let ext = match entry_path.extension().and_then(|e| e.to_str()) {
            Some(e) => e,
            None => continue,
        };

        if !SOURCE_EXTENSIONS.contains(&ext) {
            continue;
        }

        // Skip generated code, mock/seed data, vendored binaries — these are
        // never the "monster" the dev needs to refactor.
        let rel_for_check = entry_path
            .strip_prefix(root)
            .unwrap_or(entry_path)
            .to_string_lossy()
            .to_string();
        if is_generated_or_data_file(&rel_for_check) {
            continue;
        }

        let content = match fs::read_to_string(entry_path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let line_count = content.lines().filter(|l| !l.trim().is_empty()).count() as u32;

        let severity = match severity_for_lines(line_count) {
            Some(s) => s,
            None => continue,
        };

        let (functions, classes) = if ext == "py" {
            count_definitions_python(&content)
        } else if ext == "ts" || ext == "tsx" || ext == "mts" || ext == "cts" {
            count_definitions_js(&content, true)
        } else {
            count_definitions_js(&content, false)
        };

        let rel_path = entry_path
            .strip_prefix(root)
            .unwrap_or(entry_path)
            .to_string_lossy()
            .to_string();

        monsters.push(MonsterFile {
            path: rel_path,
            lines: line_count,
            functions,
            classes,
            severity: severity.to_string(),
        });
    }

    monsters.sort_by(|a, b| b.lines.cmp(&a.lines));

    Ok(MonstersResult { monsters })
}
