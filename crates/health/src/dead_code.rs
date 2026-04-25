//! Check 2.1–2.4 — Dead Code Detection.
//!
//! Single pass per file: tree-sitter parse → collect imports, definitions, identifiers.
//! Cross-file: check if definitions are used anywhere.
//! Commented-out code detection re-parses stripped comment blocks.

use std::collections::HashSet;
use std::fs;
use std::path::Path;

use pyo3::prelude::*;

use crate::common::{collect_source_files, WalkOpts};

#[pyclass]
#[derive(Clone)]
pub struct UnusedImport {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub import_statement: String,
}

#[pyclass]
#[derive(Clone)]
pub struct UnusedDefinition {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub kind: String,
}

#[pyclass]
#[derive(Clone)]
pub struct CommentedBlock {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub start_line: u32,
    #[pyo3(get)]
    pub end_line: u32,
    #[pyo3(get)]
    pub line_count: u32,
    #[pyo3(get)]
    pub preview: String,
}

#[pyclass]
#[derive(Clone)]
pub struct DeadCodeResult {
    #[pyo3(get)]
    pub unused_imports: Vec<UnusedImport>,
    #[pyo3(get)]
    pub unused_definitions: Vec<UnusedDefinition>,
    #[pyo3(get)]
    pub orphan_files: Vec<String>,
    #[pyo3(get)]
    pub commented_blocks: Vec<CommentedBlock>,
}

/// Per-file parsed data.
struct FileData {
    rel_path: String,
    lang: Lang,
    content: String,
    imports: Vec<(String, u32, String)>,
    definitions: Vec<(String, u32, String)>,
    used_identifiers: HashSet<String>,
    has_star_import: bool,
    is_init: bool,
    is_route_file: bool,
}

#[derive(Clone, Copy, PartialEq)]
enum Lang {
    Python,
    JavaScript,
    TypeScript,
    Tsx,
}

/// Names that pytest (and unittest-via-pytest) call automatically in any
/// class or module under a test scope. They look like dead code because
/// nothing in the source calls them directly — the test runner does.
const PYTEST_LIFECYCLE_NAMES: &[&str] = &[
    // pytest xunit-style functions and methods
    "setup_function",
    "teardown_function",
    "setup_method",
    "teardown_method",
    "setup_class",
    "teardown_class",
    "setup_module",
    "teardown_module",
    // unittest-style names that pytest also honors
    "setUp",
    "tearDown",
    "setUpClass",
    "tearDownClass",
    "setUpModule",
    "tearDownModule",
    "asyncSetUp",
    "asyncTearDown",
];

/// Method names that are called by frameworks (not by user code).
/// These look dead but are event handlers, callbacks, or protocol methods
/// that the framework invokes automatically.
///
/// IMPORTANT: Only include names that are distinctive enough to be
/// unambiguous. Generic names like `invoke`, `event`, `dispatch` are
/// excluded because they could be regular user functions.
/// These are only checked for definitions INSIDE classes (see usage below).
const FRAMEWORK_CALLBACK_NAMES: &[&str] = &[
    // watchdog (FileSystemEventHandler)
    "on_modified",
    "on_created",
    "on_deleted",
    "on_moved",
    "on_closed",
    "on_any_event",
    // Qt overrides (common in PyQt/PySide) — camelCase = distinctive
    "paintEvent",
    "resizeEvent",
    "closeEvent",
    "showEvent",
    "hideEvent",
    "keyPressEvent",
    "keyReleaseEvent",
    "mousePressEvent",
    "mouseReleaseEvent",
    "mouseMoveEvent",
    "wheelEvent",
    "dragEnterEvent",
    "dragMoveEvent",
    "dropEvent",
    "focusInEvent",
    "focusOutEvent",
    "enterEvent",
    "leaveEvent",
    "timerEvent",
    "changeEvent",
    "contextMenuEvent",
    "eventFilter",
    "sizeHint",
    "minimumSizeHint",
    "retranslateUi",
    "retranslate",
    // Django — distinctive prefixed names only
    "get_queryset",
    "get_context_data",
    "get_serializer_class",
    "get_permissions",
    "get_form_class",
    "get_form_kwargs",
    "get_success_url",
    "get_redirect_url",
    "get_object",
    "perform_create",
    "perform_update",
    "perform_destroy",
    "form_valid",
    "form_invalid",
    "add_arguments",
    // Flask / FastAPI
    "on_startup",
    "on_shutdown",
    // celery
    "on_success",
    "on_failure",
    "on_retry",
    // dataclass / pydantic
    "model_post_init",
    // Django admin hooks
    "has_add_permission",
    "has_change_permission",
    "has_delete_permission",
    "has_view_permission",
    "has_module_permission",
    "get_readonly_fields",
    "get_list_display",
    "get_list_filter",
    "get_search_fields",
    "get_fieldsets",
    "get_inline_instances",
    "get_urls",
    "save_model",
    "delete_model",
    "get_changeform_initial_data",
    // Textual TUI framework
    "compose",
    "on_mount",
    "on_unmount",
    "on_show",
    "on_hide",
    "on_focus",
    "on_blur",
    "on_key",
    "on_resize",
    "on_idle",
    "watch_dark",
    "render",
    // unittest / pytest class methods
    "setUp",
    "tearDown",
    "setUpClass",
    "tearDownClass",
    // html.parser.HTMLParser — stdlib parser callbacks invoked by feed()
    "handle_starttag",
    "handle_endtag",
    "handle_startendtag",
    "handle_data",
    "handle_entityref",
    "handle_charref",
    "handle_comment",
    "handle_decl",
    "handle_pi",
    "unknown_decl",
    // xml.sax.ContentHandler — stdlib SAX parser callbacks
    "startElement",
    "endElement",
    "startElementNS",
    "endElementNS",
    "characters",
    "ignorableWhitespace",
    "processingInstruction",
    "startDocument",
    "endDocument",
    "startPrefixMapping",
    "endPrefixMapping",
];

/// Fallback check: does `name` appear as a word in the file content
/// on any line OTHER than the import line? This catches cases where
/// tree-sitter's identifier tracking misses usages (e.g. shorthand
/// properties in object literals, or identifiers in template literals).
fn name_used_outside_import(content: &str, name: &str, import_line: u32) -> bool {
    for (idx, line) in content.lines().enumerate() {
        let line_num = idx as u32 + 1;
        if line_num == import_line {
            continue;
        }
        // Check if name appears as a word boundary match in this line
        if let Some(pos) = line.find(name) {
            let before_ok = pos == 0
                || !line.as_bytes()[pos - 1].is_ascii_alphanumeric()
                    && line.as_bytes()[pos - 1] != b'_';
            let end = pos + name.len();
            let after_ok = end >= line.len()
                || !line.as_bytes()[end].is_ascii_alphanumeric()
                    && line.as_bytes()[end] != b'_';
            if before_ok && after_ok {
                return true;
            }
        }
    }
    false
}

/// Return true if this file lives in a scope where pytest will pick up
/// lifecycle hooks automatically: anything under `tests/`, any
/// `test_*.py` / `*_test.py`, or a `conftest.py`.
fn is_pytest_scope(rel_path: &str) -> bool {
    let path = rel_path.replace('\\', "/");
    if path.starts_with("tests/") || path.contains("/tests/") {
        return true;
    }
    let file_name = path.rsplit('/').next().unwrap_or(&path);
    if file_name == "conftest.py" {
        return true;
    }
    if file_name.starts_with("test_") && file_name.ends_with(".py") {
        return true;
    }
    if file_name.ends_with("_test.py") {
        return true;
    }
    false
}

/// Check whether the given source line carries a `# noqa` marker that
/// silences unused-import warnings for this line.
///
/// Rules (mirroring pyflakes/flake8/ruff conventions):
/// - `# noqa` (no code) — silences everything, including F401.
/// - `# noqa: F401` — silences F401 (unused import).
/// - `# noqa: F401, F811` — comma-separated list; matches if F401 is in it.
/// - `# noqa: E501` — does NOT silence F401 (wrong code).
/// - Case-insensitive. JS equivalent handled via explicit check below.
fn has_noqa_unused_import(line_text: &str, lang: Lang) -> bool {
    let lower = line_text.to_ascii_lowercase();
    match lang {
        Lang::Python => {
            let Some(idx) = lower.find("# noqa") else {
                return false;
            };
            let rest = &lower[idx + "# noqa".len()..];
            let trimmed = rest.trim_start();
            if !trimmed.starts_with(':') {
                // Bare `# noqa` — silences everything.
                return true;
            }
            // `# noqa: <codes>` — look for f401 in the comma list.
            let codes_part = &trimmed[1..]; // skip ':'
            codes_part
                .split(|c: char| c == ',' || c.is_whitespace())
                .any(|tok| tok.trim() == "f401")
        }
        Lang::JavaScript | Lang::TypeScript | Lang::Tsx => {
            // `// eslint-disable-line no-unused-vars` (or next-line, or bare disable-line)
            lower.contains("eslint-disable-line")
                || lower.contains("eslint-disable-next-line")
        }
    }
}

/// Return true if the given node sits inside an `if TYPE_CHECKING:` block.
/// Imports in such blocks are used only for type annotations and should NOT
/// be reported as unused.
fn is_inside_type_checking(node: tree_sitter::Node, source: &str) -> bool {
    let mut current = node;
    while let Some(parent) = current.parent() {
        if parent.kind() == "if_statement" {
            if let Some(cond) = parent.child_by_field_name("condition") {
                if let Ok(text) = cond.utf8_text(source.as_bytes()) {
                    if text == "TYPE_CHECKING" {
                        return true;
                    }
                }
            }
        }
        current = parent;
    }
    false
}

/// Return true if this identifier is the name being declared (function,
/// class, method) or lives inside an import statement's name list.
/// False for every usage site, including type hints and decorator targets.
fn is_decl_or_import_name(node: tree_sitter::Node) -> bool {
    // Case 1: direct parent is a declaration node and this identifier
    // is its `name` field.
    if let Some(parent) = node.parent() {
        match parent.kind() {
            "function_definition"
            | "class_definition"
            | "function_declaration"
            | "class_declaration"
            | "method_definition" => {
                if parent.child_by_field_name("name").map(|n| n.id()) == Some(node.id()) {
                    return true;
                }
            }
            _ => {}
        }
    }

    // Case 2: identifier lives anywhere inside an import statement's
    // name list. Walk up until we hit an import statement (true) or a
    // non-import statement/block boundary (false).
    let mut cur = node.parent();
    while let Some(p) = cur {
        match p.kind() {
            "import_statement" | "import_from_statement" => return true,
            // Statement/block boundaries — once we cross one of these,
            // we're out of the import's scope.
            "function_definition"
            | "class_definition"
            | "function_declaration"
            | "class_declaration"
            | "method_definition"
            | "if_statement"
            | "for_statement"
            | "while_statement"
            | "try_statement"
            | "with_statement"
            | "expression_statement"
            | "assignment"
            | "augmented_assignment"
            | "return_statement"
            | "decorator"
            | "call"
            | "block"
            | "module"
            | "program" => return false,
            _ => cur = p.parent(),
        }
    }
    false
}

/// File-based routing directories: default exports are route entry points.
/// Matches both top-level (app/) and nested (myproject/app/) structures.
const ROUTE_SEGMENTS: &[&str] = &["app/", "pages/", "routes/"];

fn is_route_path(rel_path: &str) -> bool {
    ROUTE_SEGMENTS.iter().any(|seg| {
        rel_path.starts_with(seg) || rel_path.contains(&format!("/{seg}"))
    })
}

fn parse_file(content: &str, rel_path: &str, lang: Lang) -> FileData {
    let is_init = rel_path.ends_with("__init__.py");
    let is_route_file = is_route_path(rel_path)
        && matches!(lang, Lang::JavaScript | Lang::TypeScript | Lang::Tsx);

    let mut parser = tree_sitter::Parser::new();
    let ts_lang = match lang {
        Lang::Python => tree_sitter_python::LANGUAGE.into(),
        Lang::JavaScript => tree_sitter_javascript::LANGUAGE.into(),
        Lang::TypeScript => tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into(),
        Lang::Tsx => tree_sitter_typescript::LANGUAGE_TSX.into(),
    };
    let empty = FileData {
        rel_path: rel_path.to_string(),
        lang,
        content: content.to_string(),
        imports: vec![],
        definitions: vec![],
        used_identifiers: HashSet::new(),
        has_star_import: false,
        is_init,
        is_route_file,
    };
    if parser.set_language(&ts_lang).is_err() {
        return empty;
    }
    let tree = match parser.parse(content, None) {
        Some(t) => t,
        None => return empty,
    };

    let mut imports: Vec<(String, u32, String)> = Vec::new();
    let mut definitions: Vec<(String, u32, String)> = Vec::new();
    let mut used_identifiers: HashSet<String> = HashSet::new();
    // NB: import_lines/def_lines are maintained for now but no longer
    // consulted by the usage-tracking logic (Task 12 — it used to exclude
    // identifiers on import/def lines, which killed type-hint references
    // like `aiosqlite.Connection` in `def f(db: aiosqlite.Connection)`).
    // Left in place in case future checks need per-line import/def maps.
    let mut import_lines: HashSet<u32> = HashSet::new();
    let mut def_lines: HashSet<u32> = HashSet::new();
    let mut has_star_import = false;
    let mut decorated_lines: HashSet<u32> = HashSet::new();

    let mut cursor = tree.walk();

    crate::common::walk_nodes(&mut cursor, &mut |node| {
        let line = node.start_position().row as u32 + 1;

        match lang {
            Lang::Python => {
                if node.kind() == "import_from_statement" {
                    // Skip imports inside `if TYPE_CHECKING:` blocks —
                    // they exist only for type annotations, not runtime usage.
                    if is_inside_type_checking(node, content) {
                        return;
                    }

                    let stmt_text = node
                        .utf8_text(content.as_bytes())
                        .unwrap_or("")
                        .to_string();

                    if stmt_text.contains("import *") {
                        has_star_import = true;
                        return;
                    }

                    // Imported names are siblings of `module_name` (and sit
                    // inside `import_list` only when parentheses are used).
                    // Walk every direct child and collect dotted_name /
                    // aliased_import nodes, skipping the one that is the
                    // `module_name` field.
                    let module_name_id = node.child_by_field_name("module_name").map(|n| n.id());
                    for i in 0..node.child_count() {
                        if let Some(child) = node.child(i as u32) {
                            match child.kind() {
                                "dotted_name" | "aliased_import" => {
                                    if module_name_id == Some(child.id()) {
                                        continue;
                                    }
                                    let name = if child.kind() == "aliased_import" {
                                        child
                                            .child_by_field_name("alias")
                                            .and_then(|n| n.utf8_text(content.as_bytes()).ok())
                                            .unwrap_or("")
                                    } else {
                                        child.utf8_text(content.as_bytes()).unwrap_or("")
                                    };
                                    if !name.is_empty() {
                                        imports.push((
                                            name.to_string(),
                                            line,
                                            stmt_text.clone(),
                                        ));
                                        import_lines.insert(line);
                                    }
                                }
                                // Parenthesized form: `from X import (Y, Z)`
                                // — names live inside an import_list child.
                                "import_list" => {
                                    for j in 0..child.child_count() {
                                        if let Some(name_node) = child.child(j as u32) {
                                            if name_node.kind() == "dotted_name"
                                                || name_node.kind() == "aliased_import"
                                            {
                                                let name = if name_node.kind() == "aliased_import"
                                                {
                                                    name_node
                                                        .child_by_field_name("alias")
                                                        .and_then(|n| {
                                                            n.utf8_text(content.as_bytes()).ok()
                                                        })
                                                        .unwrap_or("")
                                                } else {
                                                    name_node
                                                        .utf8_text(content.as_bytes())
                                                        .unwrap_or("")
                                                };
                                                if !name.is_empty() {
                                                    imports.push((
                                                        name.to_string(),
                                                        line,
                                                        stmt_text.clone(),
                                                    ));
                                                    import_lines.insert(line);
                                                }
                                            }
                                        }
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                } else if node.kind() == "import_statement" {
                    let stmt_text = node
                        .utf8_text(content.as_bytes())
                        .unwrap_or("")
                        .to_string();
                    for i in 0..node.child_count() {
                        if let Some(child) = node.child(i as u32) {
                            if child.kind() == "dotted_name" || child.kind() == "aliased_import" {
                                let name = if child.kind() == "aliased_import" {
                                    child
                                        .child_by_field_name("alias")
                                        .and_then(|n| n.utf8_text(content.as_bytes()).ok())
                                        .unwrap_or("")
                                } else {
                                    let full = child.utf8_text(content.as_bytes()).unwrap_or("");
                                    full.split('.').next().unwrap_or("")
                                };
                                if !name.is_empty() {
                                    imports.push((name.to_string(), line, stmt_text.clone()));
                                    import_lines.insert(line);
                                }
                            }
                        }
                    }
                } else if node.kind() == "function_definition" {
                    if let Some(name_node) = node.child_by_field_name("name") {
                        let name = name_node
                            .utf8_text(content.as_bytes())
                            .unwrap_or("")
                            .to_string();
                        if !name.is_empty() {
                            // Check if this function is a method inside a class.
                            let is_method = node.parent()
                                .is_some_and(|p| p.kind() == "block" && p.parent().is_some_and(|gp| gp.kind() == "class_definition"));
                            let kind = if is_method { "method" } else { "function" };
                            definitions.push((name, line, kind.to_string()));
                            def_lines.insert(line);
                        }
                    }
                } else if node.kind() == "class_definition" {
                    if let Some(name_node) = node.child_by_field_name("name") {
                        let name = name_node
                            .utf8_text(content.as_bytes())
                            .unwrap_or("")
                            .to_string();
                        if !name.is_empty() {
                            definitions.push((name, line, "class".to_string()));
                            def_lines.insert(line);
                        }
                    }
                } else if node.kind() == "decorator" {
                    let end_line = node.end_position().row as u32 + 2;
                    decorated_lines.insert(end_line);
                }
            }
            Lang::JavaScript | Lang::TypeScript | Lang::Tsx => {
                if node.kind() == "import_statement" {
                    let stmt_text = node
                        .utf8_text(content.as_bytes())
                        .unwrap_or("")
                        .to_string();
                    for i in 0..node.child_count() {
                        if let Some(child) = node.child(i as u32) {
                            if child.kind() == "import_clause" {
                                collect_js_import_names(
                                    child,
                                    content,
                                    &mut imports,
                                    line,
                                    &stmt_text,
                                    &mut import_lines,
                                );
                            }
                        }
                    }
                } else if node.kind() == "function_declaration" {
                    if let Some(name_node) = node.child_by_field_name("name") {
                        let name = name_node
                            .utf8_text(content.as_bytes())
                            .unwrap_or("")
                            .to_string();
                        if !name.is_empty() {
                            definitions.push((name, line, "function".to_string()));
                            def_lines.insert(line);
                        }
                    }
                } else if node.kind() == "class_declaration" {
                    if let Some(name_node) = node.child_by_field_name("name") {
                        let name = name_node
                            .utf8_text(content.as_bytes())
                            .unwrap_or("")
                            .to_string();
                        if !name.is_empty() {
                            definitions.push((name, line, "class".to_string()));
                            def_lines.insert(line);
                        }
                    }
                }
                // const X = require('Y') or const { X } = require('Y')
                if node.kind() == "variable_declarator" {
                    if let Some(init) = node.child_by_field_name("value") {
                        if init.kind() == "call_expression" {
                            let func_text = init
                                .child_by_field_name("function")
                                .and_then(|n| n.utf8_text(content.as_bytes()).ok())
                                .unwrap_or("");
                            if func_text == "require" {
                                if let Some(name_node) = node.child_by_field_name("name") {
                                    let stmt_text = node
                                        .parent()
                                        .and_then(|p| p.utf8_text(content.as_bytes()).ok())
                                        .unwrap_or("")
                                        .to_string();
                                    if name_node.kind() == "object_pattern" {
                                        // const { X, Y } = require('Z') — extract each binding
                                        collect_object_pattern_names(
                                            name_node,
                                            content,
                                            &mut imports,
                                            line,
                                            &stmt_text,
                                            &mut import_lines,
                                        );
                                    } else {
                                        let name = name_node
                                            .utf8_text(content.as_bytes())
                                            .unwrap_or("")
                                            .to_string();
                                        if !name.is_empty() {
                                            imports.push((name, line, stmt_text));
                                            import_lines.insert(line);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Collect all identifiers for usage tracking — but skip the
        // identifier that is itself the declared name (function/class)
        // or an imported name. Type hints on the same line as `def`
        // must still count as usages (Task 12).
        if (node.kind() == "identifier" || node.kind() == "property_identifier"
            || node.kind() == "type_identifier")
            && !is_decl_or_import_name(node) {
                if let Ok(text) = node.utf8_text(content.as_bytes()) {
                    used_identifiers.insert(text.to_string());
                }
            }
    });

    // Filter out decorated definitions
    definitions.retain(|(_, line, _)| !decorated_lines.contains(line));

    // Filter out Python dunders and test functions. If the file is a
    // test-scope file (tests/**, test_*.py, *_test.py, conftest.py),
    // also drop pytest / unittest lifecycle hooks that pytest invokes
    // automatically — they look dead but are not.
    if lang == Lang::Python {
        let is_test_file = is_pytest_scope(rel_path);
        definitions.retain(|(name, _, kind)| {
            if kind == "function" || kind == "method" {
                if name.starts_with("__") || name.starts_with("test_") {
                    return false;
                }
                if is_test_file && PYTEST_LIFECYCLE_NAMES.contains(&name.as_str()) {
                    return false;
                }
                // Skip known framework callbacks ONLY for methods inside classes.
                // Top-level functions named `dispatch` or `invoke` are legitimate.
                if kind == "method" && FRAMEWORK_CALLBACK_NAMES.contains(&name.as_str()) {
                    return false;
                }
                // DRF validate_<field> / Django clean_<field> — framework auto-discovery
                // Textual action_<name> — auto-bound to key bindings
                if kind == "method"
                    && (name.starts_with("validate_") || name.starts_with("clean_")
                        || name.starts_with("action_") || name.starts_with("watch_")
                        || name.starts_with("on_"))
                {
                    return false;
                }
                true
            } else {
                // Skip Meta inner classes — Django/DRF/Pydantic framework pattern
                if name == "Meta" {
                    return false;
                }
                // Skip AppConfig subclasses in apps.py — Django string-based discovery
                if name.ends_with("Config") && rel_path.ends_with("apps.py") {
                    return false;
                }
                !name.starts_with("Test")
            }
        });
    }

    FileData {
        rel_path: rel_path.to_string(),
        lang,
        content: content.to_string(),
        imports,
        definitions,
        used_identifiers,
        has_star_import,
        is_init,
        is_route_file,
    }
}

/// Extract individual binding names from `const { X, Y } = require(...)`.
fn collect_object_pattern_names(
    pattern: tree_sitter::Node,
    source: &str,
    imports: &mut Vec<(String, u32, String)>,
    line: u32,
    stmt: &str,
    import_lines: &mut HashSet<u32>,
) {
    for i in 0..pattern.child_count() {
        if let Some(child) = pattern.child(i as u32) {
            match child.kind() {
                // const { X } = require(...) — shorthand property
                "shorthand_property_identifier_pattern" | "shorthand_property" => {
                    if let Ok(text) = child.utf8_text(source.as_bytes()) {
                        let name = text.trim().to_string();
                        if !name.is_empty() {
                            imports.push((name, line, stmt.to_string()));
                            import_lines.insert(line);
                        }
                    }
                }
                // const { X: localName } = require(...) — aliased
                "pair_pattern" => {
                    // value field is the local binding name
                    if let Some(value) = child.child_by_field_name("value") {
                        if let Ok(text) = value.utf8_text(source.as_bytes()) {
                            let name = text.trim().to_string();
                            if !name.is_empty() {
                                imports.push((name, line, stmt.to_string()));
                                import_lines.insert(line);
                            }
                        }
                    }
                }
                _ => {}
            }
        }
    }
}

fn collect_js_import_names(
    node: tree_sitter::Node,
    source: &str,
    imports: &mut Vec<(String, u32, String)>,
    line: u32,
    stmt: &str,
    import_lines: &mut HashSet<u32>,
) {
    if node.kind() == "identifier" {
        if let Ok(text) = node.utf8_text(source.as_bytes()) {
            imports.push((text.to_string(), line, stmt.to_string()));
            import_lines.insert(line);
        }
        return;
    }

    for i in 0..node.child_count() {
        if let Some(child) = node.child(i as u32) {
            if child.kind() == "named_imports" {
                for j in 0..child.child_count() {
                    if let Some(spec) = child.child(j as u32) {
                        if spec.kind() == "import_specifier" {
                            let name = spec
                                .child_by_field_name("alias")
                                .or_else(|| spec.child_by_field_name("name"))
                                .and_then(|n| n.utf8_text(source.as_bytes()).ok())
                                .unwrap_or("");
                            if !name.is_empty() {
                                imports.push((name.to_string(), line, stmt.to_string()));
                                import_lines.insert(line);
                            }
                        }
                    }
                }
            } else if child.kind() == "identifier" {
                if let Ok(text) = child.utf8_text(source.as_bytes()) {
                    imports.push((text.to_string(), line, stmt.to_string()));
                    import_lines.insert(line);
                }
            } else if child.kind() == "namespace_import" {
                let last_idx = child.child_count().saturating_sub(1) as u32;
                if let Some(name_node) = child.child(last_idx) {
                    if name_node.kind() == "identifier" {
                        if let Ok(text) = name_node.utf8_text(source.as_bytes()) {
                            imports.push((text.to_string(), line, stmt.to_string()));
                            import_lines.insert(line);
                        }
                    }
                }
            } else {
                collect_js_import_names(child, source, imports, line, stmt, import_lines);
            }
        }
    }
}

/// Detect commented-out code blocks.
///
/// Strategy (Task 13): identify contiguous comment blocks of ≥5 lines,
/// strip the comment prefix, and feed the result to tree-sitter.
/// A block is real commented-out code iff:
///   - the parse succeeds with zero `ERROR` nodes, AND
///   - it contains at least one non-trivial statement (not just bare
///     identifiers like a TODO list).
/// English prose fails both checks.
fn find_commented_blocks(content: &str, rel_path: &str, lang: Lang) -> Vec<CommentedBlock> {
    let comment_prefix = match lang {
        Lang::Python => "#",
        Lang::JavaScript | Lang::TypeScript | Lang::Tsx => "//",
    };

    let mut blocks: Vec<CommentedBlock> = Vec::new();
    let mut current_block: Vec<(u32, String)> = Vec::new();

    for (idx, line) in content.lines().enumerate() {
        let trimmed = line.trim();
        let line_num = idx as u32 + 1;

        let is_comment = trimmed.starts_with(comment_prefix) && !trimmed.starts_with("#!");

        // Shebangs and encoding declarations are boundaries, not content.
        if lang == Lang::Python && (trimmed.starts_with("#!") || trimmed.starts_with("# -*-")) {
            if !current_block.is_empty() {
                maybe_emit_block(&mut blocks, &current_block, rel_path, lang);
                current_block.clear();
            }
            continue;
        }

        if is_comment {
            current_block.push((line_num, trimmed.to_string()));
        } else if !current_block.is_empty() {
            maybe_emit_block(&mut blocks, &current_block, rel_path, lang);
            current_block.clear();
        }
    }

    if !current_block.is_empty() {
        maybe_emit_block(&mut blocks, &current_block, rel_path, lang);
    }

    blocks
}

/// Strip the leading `# ` or `// ` (and any amount of whitespace) from one
/// comment line, returning the payload. Preserves indentation beyond the
/// marker so the result reparses cleanly.
fn strip_comment_prefix(line: &str, lang: Lang) -> String {
    let marker = match lang {
        Lang::Python => "#",
        Lang::JavaScript | Lang::TypeScript | Lang::Tsx => "//",
    };
    let trimmed = line.trim_start();
    if let Some(rest) = trimmed.strip_prefix(marker) {
        // Drop ONE leading space if present — preserve any structural
        // indentation after that (important for nested code).
        rest.strip_prefix(' ').unwrap_or(rest).to_string()
    } else {
        trimmed.to_string()
    }
}

/// Return true if the parsed tree has at least one ERROR node anywhere.
fn tree_has_errors(node: tree_sitter::Node) -> bool {
    if node.is_error() || node.kind() == "ERROR" {
        return true;
    }
    for i in 0..node.child_count() {
        if let Some(c) = node.child(i as u32) {
            if tree_has_errors(c) {
                return true;
            }
        }
    }
    false
}

/// Return true if the module body contains only trivial expression
/// statements whose sole content is a single identifier — the typical
/// shape of an english TODO list or bullet-point comment.
fn only_trivial_identifiers(root: tree_sitter::Node, source: &str) -> bool {
    let mut statement_count = 0usize;
    let mut trivial_count = 0usize;

    for i in 0..root.named_child_count() {
        let stmt = match root.named_child(i as u32) {
            Some(n) => n,
            None => continue,
        };
        if stmt.kind() == "comment" {
            continue;
        }
        statement_count += 1;

        // Classify each statement. Trivial: expression_statement whose
        // only named child is an identifier or a string (a line like
        // "os" or "investigate the memory leak" (which parses as
        // identifier sequence → ERROR, caught earlier)).
        let is_trivial = stmt.kind() == "expression_statement"
            && stmt.named_child_count() == 1
            && stmt
                .named_child(0)
                .is_some_and(|c| matches!(c.kind(), "identifier" | "string"));
        if is_trivial {
            trivial_count += 1;
        }
    }

    let _ = source; // reserved for richer heuristics later
    statement_count > 0 && trivial_count == statement_count
}

/// Return true if the stripped comment block looks like prose rather than code.
/// Heuristic: count lines containing Python/JS keywords or operator characters.
/// If fewer than 50% look like code, treat the whole block as prose.
fn looks_like_prose(stripped_lines: &[String], lang: Lang) -> bool {
    let keywords: &[&str] = match lang {
        Lang::Python => &[
            "def ", "class ", "import ", "from ", "return ", "if ", "for ",
            "while ", "with ", "try:", "except", "raise ", "yield ", "async ",
            "await ", "elif ", "else:", "finally:", "pass", "break", "continue",
            "lambda ", "assert ",
        ],
        Lang::JavaScript | Lang::TypeScript | Lang::Tsx => &[
            "function ", "const ", "let ", "var ", "return ", "if ", "for ",
            "while ", "import ", "export ", "class ", "async ", "await ",
            "try ", "catch ", "throw ", "switch ", "case ",
        ],
    };
    let operators = ['=', '(', ')', '[', ']', '{', '}'];

    let mut code_lines = 0usize;
    for line in stripped_lines {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let has_keyword = keywords.iter().any(|kw| trimmed.contains(kw));
        let has_operator = trimmed.chars().any(|c| operators.contains(&c));
        if has_keyword || has_operator {
            code_lines += 1;
        }
    }

    let total_non_empty = stripped_lines.iter().filter(|l| !l.trim().is_empty()).count();
    if total_non_empty == 0 {
        return true;
    }

    // Less than 50% code-looking lines → prose
    (code_lines as f64 / total_non_empty as f64) < 0.5
}

fn maybe_emit_block(
    blocks: &mut Vec<CommentedBlock>,
    current_block: &[(u32, String)],
    rel_path: &str,
    lang: Lang,
) {
    if current_block.len() < 5 {
        return;
    }

    let stripped_lines: Vec<String> = current_block
        .iter()
        .map(|(_, text)| strip_comment_prefix(text, lang))
        .collect();

    // Pre-filter: if the block looks like prose (< 50% code-like lines),
    // skip without parsing.
    if looks_like_prose(&stripped_lines, lang) {
        return;
    }

    let stripped = stripped_lines.join("\n");

    let ts_lang = match lang {
        Lang::Python => tree_sitter_python::LANGUAGE.into(),
        Lang::JavaScript => tree_sitter_javascript::LANGUAGE.into(),
        Lang::TypeScript => tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into(),
        Lang::Tsx => tree_sitter_typescript::LANGUAGE_TSX.into(),
    };
    let mut parser = tree_sitter::Parser::new();
    if parser.set_language(&ts_lang).is_err() {
        return;
    }
    let tree = match parser.parse(&stripped, None) {
        Some(t) => t,
        None => return,
    };
    let root = tree.root_node();

    if tree_has_errors(root) {
        return;
    }
    if root.named_child_count() == 0 {
        return;
    }
    if only_trivial_identifiers(root, &stripped) {
        return;
    }

    let start = current_block[0].0;
    let end = current_block.last().unwrap().0;
    let preview: String = current_block
        .iter()
        .take(3)
        .map(|(_, text)| text.as_str())
        .collect::<Vec<_>>()
        .join("\n");

    blocks.push(CommentedBlock {
        path: rel_path.to_string(),
        start_line: start,
        end_line: end,
        line_count: current_block.len() as u32,
        preview,
    });
}

#[pyfunction]
pub fn scan_dead_code(path: &str, _entry_point_paths: Vec<String>) -> PyResult<DeadCodeResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {path}"),
        ));
    }

    // Phase 1: Parse all source files
    let mut file_data: Vec<FileData> = Vec::new();

    for src in collect_source_files(root, &WalkOpts::default()) {
        let lang = match src.ext.as_str() {
            "py" => Lang::Python,
            "ts" | "mts" | "cts" => Lang::TypeScript,
            "tsx" | "jsx" => Lang::Tsx,
            "js" | "mjs" | "cjs" => Lang::JavaScript,
            // Skip languages we don't have tree-sitter analysis for yet.
            // They'll still be counted in file_tree but won't produce
            // false dead-code results.
            _ => continue,
        };
        let content = match fs::read_to_string(&src.abs_path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        file_data.push(parse_file(&content, &src.rel_path, lang));
    }

    // Phase 2: Unused imports (per-file)
    let mut unused_imports: Vec<UnusedImport> = Vec::new();
    for fd in &file_data {
        if fd.has_star_import || fd.is_init {
            continue;
        }
        // SQLAlchemy pattern: `from models import X` + `Base.metadata.create_all()`
        // Model imports are side-effects (register tables in metadata).
        let has_create_all = fd.content.contains("create_all")
            || fd.content.contains("metadata.create_all");
        // Pre-split file content into lines once per file so we can cheaply
        // look up the source line of each import to check for `# noqa`.
        let lines: Vec<&str> = fd.content.lines().collect();
        for (name, line, stmt) in &fd.imports {
            if fd.used_identifiers.contains(name.as_str()) {
                continue;
            }
            // Fallback: tree-sitter may miss identifiers in some contexts
            // (e.g. shorthand properties). Do a simple word-boundary check
            // in non-import lines of the file.
            if name.len() >= 2 && name_used_outside_import(&fd.content, name, *line) {
                continue;
            }
            // Respect `# noqa` / `# noqa: F401` on the import line.
            let line_text = lines
                .get((*line as usize).saturating_sub(1))
                .copied()
                .unwrap_or("");
            if has_noqa_unused_import(line_text, fd.lang) {
                continue;
            }
            // SQLAlchemy: model imports in files with create_all() are side-effects
            if has_create_all && stmt.to_lowercase().contains("model") {
                continue;
            }
            // Test framework imports: pytest/unittest are used implicitly
            if (name == "pytest" || name == "unittest")
                && is_pytest_scope(&fd.rel_path)
            {
                continue;
            }
            unused_imports.push(UnusedImport {
                path: fd.rel_path.clone(),
                line: *line,
                name: name.clone(),
                import_statement: stmt.clone(),
            });
        }
    }

    // Phase 3: Unused definitions (cross-file)
    let mut global_identifiers: HashSet<String> = HashSet::new();
    for fd in &file_data {
        for id in &fd.used_identifiers {
            global_identifiers.insert(id.clone());
        }
        // __init__.py re-exports: `from .module import Foo` or
        // `from .module import Foo as _Foo` makes the original name used.
        // Both the alias and the original name should be considered "used".
        if fd.is_init {
            for (name, _, stmt) in &fd.imports {
                global_identifiers.insert(name.clone());
                // For aliased imports like `reset_db_for_tests as _reset_db_for_tests`,
                // find the pattern `<original> as <alias>` where alias matches `name`.
                let search = format!(" as {name}");
                if let Some(pos) = stmt.find(&search) {
                    // Walk backwards from the match to find the original name.
                    let before = stmt[..pos].trim_end();
                    let original = before
                        .rsplit([' ', ',', '('])
                        .next()
                        .unwrap_or("")
                        .trim();
                    if !original.is_empty() {
                        global_identifiers.insert(original.to_string());
                    }
                }
            }
        }
    }

    let mut unused_definitions: Vec<UnusedDefinition> = Vec::new();
    for fd in &file_data {
        if fd.is_init {
            continue;
        }
        // File-based routing (Expo/Next.js/Nuxt/SvelteKit): default exports
        // in app/ or pages/ directories are route entry points, not dead code.
        if fd.is_route_file && fd.content.contains("export default") {
            continue;
        }
        // Alembic migration files: upgrade()/downgrade() are called by framework.
        if fd.rel_path.contains("alembic/versions/") || fd.rel_path.contains("migrations/versions/") {
            continue;
        }
        for (name, line, kind) in &fd.definitions {
            if global_identifiers.contains(name.as_str()) {
                continue;
            }
            if name.starts_with('_') {
                continue;
            }
            unused_definitions.push(UnusedDefinition {
                path: fd.rel_path.clone(),
                line: *line,
                name: name.clone(),
                kind: kind.clone(),
            });
        }
    }

    // Phase 4: Orphan files
    //
    // Orphan detection is now handled entirely by module_map.rs which uses
    // proper import resolution (including lazy/dynamic imports inside
    // functions). The old stem-matching heuristic here produced many false
    // positives (e.g. a file named "styles.py" was considered imported if
    // ANY identifier "styles" appeared anywhere). We keep the field in the
    // result for backwards compat but always return an empty vec — the
    // Python orchestrator uses module_map orphan_candidates instead.
    let orphan_files: Vec<String> = Vec::new();

    // Phase 5: Commented-out code (reuse stored content, no re-read)
    let mut commented_blocks: Vec<CommentedBlock> = Vec::new();
    for fd in &file_data {
        commented_blocks.extend(find_commented_blocks(&fd.content, &fd.rel_path, fd.lang));
    }

    Ok(DeadCodeResult {
        unused_imports,
        unused_definitions,
        orphan_files,
        commented_blocks,
    })
}
