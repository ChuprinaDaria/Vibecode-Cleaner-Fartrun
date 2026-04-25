//! Check 1.4 — Monster File Detection.
//!
//! Finds files > 500 lines with function/class counts via tree-sitter.

use std::fs;
use std::path::Path;

use pyo3::prelude::*;

use crate::common::{collect_source_files, WalkOpts};

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
    let lang_result = if is_ts {
        parser.set_language(&tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into())
    } else {
        parser.set_language(&tree_sitter_javascript::LANGUAGE.into())
    };
    if let Err(e) = lang_result {
        eprintln!(
            "health::monsters: set_language({}) failed: {e}",
            if is_ts { "ts" } else { "js" }
        );
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
            format!("Not a directory: {path}"),
        ));
    }

    let mut monsters: Vec<MonsterFile> = Vec::new();

    for src in collect_source_files(root, &WalkOpts::default()) {
        let content = match fs::read_to_string(&src.abs_path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let line_count = content.lines().filter(|l| !l.trim().is_empty()).count() as u32;

        let severity = match severity_for_lines(line_count) {
            Some(s) => s,
            None => continue,
        };

        let (functions, classes) = match src.ext.as_str() {
            "py" => count_definitions_python(&content),
            "ts" | "tsx" | "mts" | "cts" => count_definitions_js(&content, true),
            _ => count_definitions_js(&content, false),
        };

        monsters.push(MonsterFile {
            path: src.rel_path,
            lines: line_count,
            functions,
            classes,
            severity: severity.to_string(),
        });
    }

    monsters.sort_by(|a, b| b.lines.cmp(&a.lines));

    Ok(MonstersResult { monsters })
}
