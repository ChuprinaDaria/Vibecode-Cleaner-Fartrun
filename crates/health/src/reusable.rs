//! Check 3.6 — Reusable Component Detection (Frontend).
//!
//! Finds repeated JSX/HTML patterns: same tag + className combination
//! appearing in multiple files. Suggests extracting into components.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use pyo3::prelude::*;

use crate::common::{collect_source_files, is_test_path, WalkOpts};

/// Extensions that may contain JSX.
const JSX_EXTENSIONS: &[&str] = &["jsx", "tsx"];

/// Per-file contribution: each pattern this file contains, with how many
/// times it appears here and one preview line. Persisted between runs so
/// warm re-scans only re-walk JSX trees for files that changed.
#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct PerFilePattern {
    pattern: String,
    count: u32,
    preview: String,
}

/// Run the JSX-pattern walk on one file and return the per-file pattern
/// contributions. Pulled out so the full-scan and per-file-API paths
/// share one walker.
fn extract_file_patterns(content: &str, rel_path: &str, ext: &str) -> Vec<PerFilePattern> {
    let mut parser = tree_sitter::Parser::new();
    let lang = if ext == "tsx" {
        tree_sitter_typescript::LANGUAGE_TSX.into()
    } else {
        tree_sitter_javascript::LANGUAGE.into()
    };
    if let Err(e) = parser.set_language(&lang) {
        eprintln!(
            "health::reusable: set_language({ext}) failed for {rel_path}: {e}"
        );
        return Vec::new();
    }
    let Some(tree) = parser.parse(content, None) else {
        return Vec::new();
    };

    let mut by_pattern: HashMap<String, (u32, String)> = HashMap::new();
    let mut cursor = tree.walk();
    crate::common::walk_nodes(&mut cursor, &mut |node| {
        if let Some(pattern) = extract_jsx_pattern(node, content) {
            let entry = by_pattern.entry(pattern.clone()).or_insert_with(|| {
                let preview = node
                    .utf8_text(content.as_bytes())
                    .unwrap_or("")
                    .lines()
                    .take(2)
                    .collect::<Vec<_>>()
                    .join(" ");
                let short = if preview.chars().count() > 80 {
                    let truncated: String = preview.chars().take(77).collect();
                    format!("{truncated}...")
                } else {
                    preview
                };
                (0, short)
            });
            entry.0 += 1;
        }
    });

    by_pattern
        .into_iter()
        .map(|(pattern, (count, preview))| PerFilePattern { pattern, count, preview })
        .collect()
}

/// Cross-file aggregation: combine per-file pattern contributions into
/// the final `ReusableResult` (filtered to patterns that appear in 3+
/// files / 3+ times, capped at 15, sorted by occurrences desc).
fn compute_reusable_from_files(
    files: &HashMap<String, Vec<PerFilePattern>>,
) -> ReusableResult {
    let mut by_pattern: HashMap<String, (Vec<String>, u32, String)> = HashMap::new();
    for (rel_path, entries) in files {
        for entry in entries {
            let agg = by_pattern
                .entry(entry.pattern.clone())
                .or_insert_with(|| (Vec::new(), 0, entry.preview.clone()));
            agg.1 += entry.count;
            if !agg.0.contains(rel_path) {
                agg.0.push(rel_path.clone());
            }
        }
    }
    let mut patterns: Vec<ReusablePattern> = by_pattern
        .into_iter()
        .filter(|(_, (files, count, _))| files.len() >= 3 && *count >= 3)
        .map(|(pattern, (files, count, preview))| ReusablePattern {
            pattern,
            occurrences: count,
            files,
            preview,
        })
        .collect();
    patterns.sort_by(|a, b| b.occurrences.cmp(&a.occurrences));
    patterns.truncate(15);
    ReusableResult { patterns }
}

#[pyclass]
#[derive(Clone)]
pub struct ReusablePattern {
    #[pyo3(get)]
    pub pattern: String,
    #[pyo3(get)]
    pub occurrences: u32,
    #[pyo3(get)]
    pub files: Vec<String>,
    #[pyo3(get)]
    pub preview: String,
}

#[pyclass]
#[derive(Clone)]
pub struct ReusableResult {
    #[pyo3(get)]
    pub patterns: Vec<ReusablePattern>,
}

/// Extract a normalized pattern from a JSX element:
/// "<button className='btn-primary'>" → "button.btn-primary"
fn extract_jsx_pattern(node: tree_sitter::Node, source: &str) -> Option<String> {
    // Must be jsx_element or jsx_self_closing_element
    let kind = node.kind();
    if kind != "jsx_element" && kind != "jsx_self_closing_element" {
        return None;
    }

    // Get tag name
    let tag_node = if kind == "jsx_element" {
        // jsx_element → jsx_opening_element → tag name
        node.child(0)? // jsx_opening_element
    } else {
        node // jsx_self_closing_element has name directly
    };

    let tag_name = tag_node
        .child_by_field_name("name")
        .and_then(|n| n.utf8_text(source.as_bytes()).ok())?;

    let tag = tag_name.to_string();

    // Skip capitalized tags — these are React components that are ALREADY
    // reusable. `<Section>` used 300 times isn't repetition to extract,
    // it's the extracted component being used. We only want to flag raw
    // HTML patterns like `<div class='card'>` that deserve extraction.
    if tag.chars().next().is_some_and(|c| c.is_ascii_uppercase()) {
        return None;
    }

    // Extract className or variant prop
    let mut class_name = String::new();
    let attrs_node = if kind == "jsx_element" {
        node.child(0) // opening element
    } else {
        Some(node)
    };

    if let Some(attrs) = attrs_node {
        // Walk all children looking for jsx_attribute nodes
        let mut stack = vec![attrs];
        while let Some(current) = stack.pop() {
            for i in 0..current.child_count() {
                if let Some(child) = current.child(i as u32) {
                    if child.kind() == "jsx_attribute" {
                        let attr_text = child.utf8_text(source.as_bytes()).unwrap_or("");
                        // Check if this attribute is className, class, or variant
                        if attr_text.starts_with("className=")
                            || attr_text.starts_with("class=")
                            || attr_text.starts_with("variant=")
                        {
                            // Extract value after =
                            if let Some(eq_pos) = attr_text.find('=') {
                                let val = &attr_text[eq_pos + 1..];
                                let clean = val.trim_matches(|c: char| {
                                    c == '"' || c == '\'' || c == '{' || c == '}'
                                });
                                if !clean.is_empty() && !clean.contains("${") {
                                    class_name = clean.to_string();
                                }
                            }
                        }
                    } else if child.child_count() > 0 {
                        stack.push(child);
                    }
                }
            }
        }
    }

    if class_name.is_empty() {
        // Only track elements with className/variant — bare <div> is too generic.
        // Also skip React Native core primitives — they're like HTML tags.
        if [
            // HTML primitives — too generic to suggest extraction
            "div", "span", "p", "a", "li", "ul", "ol", "section", "header", "footer",
            "nav", "main", "aside", "article", "h1", "h2", "h3", "h4", "h5", "h6",
            "button", "input", "select", "option", "textarea", "form", "label",
            "table", "thead", "tbody", "tr", "th", "td", "tfoot",
            "img", "br", "hr", "strong", "em", "b", "i", "small", "sup", "sub",
            "pre", "code", "blockquote", "details", "summary", "dialog",
            "svg", "path", "circle", "rect", "line", "g", "defs", "clipPath",
            "video", "audio", "source", "canvas", "iframe",
            // React Native core primitives
            "View", "Text", "Pressable", "TouchableOpacity", "TouchableHighlight",
            "ScrollView", "FlatList", "SectionList", "SafeAreaView", "KeyboardAvoidingView",
            "TextInput", "Image", "ImageBackground", "StatusBar", "ActivityIndicator",
            "Modal", "Switch",
        ].contains(&tag.as_str())
        {
            return None;
        }
        Some(format!("<{tag}>"))
    } else {
        Some(format!("<{tag} class='{class_name}'>"))
    }
}

#[pyfunction]
pub fn scan_reusable(path: &str) -> PyResult<ReusableResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {path}"),
        ));
    }

    let mut per_file: HashMap<String, Vec<PerFilePattern>> = HashMap::new();
    let opts = WalkOpts {
        allowed_extensions: JSX_EXTENSIONS,
        ..WalkOpts::default()
    };
    for src in collect_source_files(root, &opts) {
        if is_test_path(&src.rel_path) {
            continue;
        }
        let Ok(content) = fs::read_to_string(&src.abs_path) else {
            continue;
        };
        let entries = extract_file_patterns(&content, &src.rel_path, src.ext.as_str());
        if !entries.is_empty() {
            per_file.insert(src.rel_path, entries);
        }
    }
    Ok(compute_reusable_from_files(&per_file))
}

/// Parse one JSX/TSX file and return the JSON-encoded
/// `Vec<PerFilePattern>` of its pattern contributions. Empty payload
/// (`""`) means the file produced no patterns — callers drop such
/// entries.
#[pyfunction]
pub fn parse_reusable_file_json(
    rel_path: &str,
    content: &str,
    ext: &str,
) -> PyResult<String> {
    if !JSX_EXTENSIONS.iter().any(|e| e.eq_ignore_ascii_case(ext)) {
        return Ok(String::new());
    }
    let entries = extract_file_patterns(content, rel_path, ext);
    if entries.is_empty() {
        return Ok(String::new());
    }
    serde_json::to_string(&entries)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

/// Walk the project, run the JSX-pattern extractor on every analysable
/// file, and return `{rel_path: payload_json}`. Used by the orchestrator
/// to populate file_data_cache on full scans.
#[pyfunction]
pub fn collect_reusable_state(
    path: &str,
) -> PyResult<std::collections::HashMap<String, String>> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {path}"),
        ));
    }
    let mut out = std::collections::HashMap::new();
    let opts = WalkOpts {
        allowed_extensions: JSX_EXTENSIONS,
        ..WalkOpts::default()
    };
    for src in collect_source_files(root, &opts) {
        if is_test_path(&src.rel_path) {
            continue;
        }
        let Ok(content) = fs::read_to_string(&src.abs_path) else {
            continue;
        };
        let entries = extract_file_patterns(&content, &src.rel_path, src.ext.as_str());
        if entries.is_empty() {
            continue;
        }
        match serde_json::to_string(&entries) {
            Ok(payload) => {
                out.insert(src.rel_path, payload);
            }
            Err(e) => eprintln!(
                "collect_reusable_state: serialize failed for {}: {e}",
                src.rel_path
            ),
        }
    }
    Ok(out)
}

/// Run the cross-file aggregation against a `{rel_path: payload}` map.
#[pyfunction]
pub fn assemble_reusable_from_json(
    file_states: std::collections::HashMap<String, String>,
) -> PyResult<ReusableResult> {
    let mut per_file: HashMap<String, Vec<PerFilePattern>> = HashMap::with_capacity(file_states.len());
    for (rel_path, payload) in file_states {
        if payload.is_empty() {
            continue;
        }
        match serde_json::from_str::<Vec<PerFilePattern>>(&payload) {
            Ok(entries) => {
                per_file.insert(rel_path, entries);
            }
            Err(e) => eprintln!(
                "assemble_reusable_from_json: skipping malformed payload for {rel_path}: {e}"
            ),
        }
    }
    Ok(compute_reusable_from_files(&per_file))
}
