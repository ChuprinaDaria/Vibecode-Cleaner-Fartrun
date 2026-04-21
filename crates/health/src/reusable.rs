//! Check 3.6 — Reusable Component Detection (Frontend).
//!
//! Finds repeated JSX/HTML patterns: same tag + className combination
//! appearing in multiple files. Suggests extracting into components.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use ignore::WalkBuilder;
use pyo3::prelude::*;

use crate::common::{is_generated_or_data_file, should_skip_entry};

/// Extensions that may contain JSX.
const JSX_EXTENSIONS: &[&str] = &["jsx", "tsx"];

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
    if tag.chars().next().map(|c| c.is_ascii_uppercase()).unwrap_or(false) {
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
        Some(format!("<{}>", tag))
    } else {
        Some(format!("<{} class='{}'>", tag, class_name))
    }
}

#[pyfunction]
pub fn scan_reusable(path: &str) -> PyResult<ReusableResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {}", path),
        ));
    }

    // pattern → {files: set, count, preview}
    let mut pattern_map: HashMap<String, (Vec<String>, u32, String)> = HashMap::new();

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
        if !JSX_EXTENSIONS.contains(&ext) {
            continue;
        }
        let rel_path = match entry_path.strip_prefix(root) {
            Ok(r) => crate::common::normalize_path(&r.to_string_lossy()),
            Err(_) => continue,
        };

        // Skip test files
        if rel_path.contains("/test") || rel_path.starts_with("test") || rel_path.contains("/__tests__/") {
            continue;
        }
        // Skip generated/mock files
        if is_generated_or_data_file(&rel_path) {
            continue;
        }

        let content = match fs::read_to_string(entry_path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        // Parse with tree-sitter
        let mut parser = tree_sitter::Parser::new();
        let lang = if ext == "tsx" {
            tree_sitter_typescript::LANGUAGE_TSX.into()
        } else {
            tree_sitter_javascript::LANGUAGE.into()
        };
        if parser.set_language(&lang).is_err() {
            continue;
        }
        let tree = match parser.parse(&content, None) {
            Some(t) => t,
            None => continue,
        };

        let mut cursor = tree.walk();
        crate::common::walk_nodes(&mut cursor, &mut |node| {
            if let Some(pattern) = extract_jsx_pattern(node, &content) {
                let entry = pattern_map.entry(pattern.clone()).or_insert_with(|| {
                    let preview = node
                        .utf8_text(content.as_bytes())
                        .unwrap_or("")
                        .lines()
                        .take(2)
                        .collect::<Vec<_>>()
                        .join(" ");
                    let short_preview = if preview.chars().count() > 80 {
                        let truncated: String = preview.chars().take(77).collect();
                        format!("{}...", truncated)
                    } else {
                        preview
                    };
                    (Vec::new(), 0, short_preview)
                });
                entry.1 += 1;
                if !entry.0.contains(&rel_path) {
                    entry.0.push(rel_path.clone());
                }
            }
        });
    }

    // Filter: pattern must appear in 3+ files
    let mut patterns: Vec<ReusablePattern> = pattern_map
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

    Ok(ReusableResult { patterns })
}
