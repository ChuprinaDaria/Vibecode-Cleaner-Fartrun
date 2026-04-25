//! Check 1.3 — Module/Component Map.
//!
//! Parses imports via tree-sitter, builds dependency graph,
//! finds hub modules and circular dependencies.

use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

use pyo3::prelude::*;

use crate::common::{collect_source_files, is_generated_or_data_file, WalkOpts};
use crate::scan_ctx::{CtxLang, ScanContext};

#[pyclass]
#[derive(Clone)]
pub struct ModuleInfo {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub imports: Vec<String>,
    #[pyo3(get)]
    pub imported_by_count: u32,
}

#[pyclass]
#[derive(Clone)]
pub struct CircularDep {
    #[pyo3(get)]
    pub file_a: String,
    #[pyo3(get)]
    pub file_b: String,
    /// true if at least one side uses a lazy import (inside function/method),
    /// meaning the cycle is intentional and safe at module-load time.
    #[pyo3(get)]
    pub is_lazy: bool,
}

#[pyclass]
#[derive(Clone)]
pub struct ModuleMapResult {
    #[pyo3(get)]
    pub modules: Vec<ModuleInfo>,
    #[pyo3(get)]
    pub hub_modules: Vec<(String, u32)>,
    #[pyo3(get)]
    pub circular_deps: Vec<CircularDep>,
    #[pyo3(get)]
    pub orphan_candidates: Vec<String>,
}

/// An import with metadata about whether it's at module top-level.
#[derive(Clone)]
struct ImportEntry {
    module: String,
    /// true when the import sits at module top-level (not inside a function/method/class body).
    is_top_level: bool,
}

/// Walk a parsed tree-sitter `Tree` and collect imports, given the
/// language family. Pulled out so cached and uncached paths share one
/// implementation — the only difference is who allocates the `Tree`.
fn collect_imports_from_tree(
    tree: &tree_sitter::Tree,
    content: &str,
    family: &str,
) -> Vec<ImportEntry> {
    let mut imports = Vec::new();
    let mut cursor = tree.walk();
    collect_imports_recursive(&mut cursor, content, &mut imports, family, 0);
    imports
}

/// Extract import sources from a Python file. When `ctx` is provided the
/// parsed `Tree` is taken from / inserted into the cross-scanner cache so
/// other context-aware scanners (e.g. dead_code) can reuse it for free.
fn extract_python_imports(
    content: &str,
    rel_path: &str,
    ctx: Option<&ScanContext>,
) -> Vec<ImportEntry> {
    if let Some(ctx) = ctx {
        let Some(tree) = ctx.parse(rel_path, CtxLang::Python, content) else {
            return vec![];
        };
        return collect_imports_from_tree(&tree, content, "python");
    }
    let mut parser = tree_sitter::Parser::new();
    if parser
        .set_language(&tree_sitter_python::LANGUAGE.into())
        .is_err()
    {
        return vec![];
    }
    let Some(tree) = parser.parse(content, None) else {
        return vec![];
    };
    collect_imports_from_tree(&tree, content, "python")
}

/// Extract import sources from a JS/TS file. See `extract_python_imports`
/// for the `ctx` semantics.
fn extract_js_imports(
    content: &str,
    rel_path: &str,
    ext: &str,
    ctx: Option<&ScanContext>,
) -> Vec<ImportEntry> {
    if let Some(ctx) = ctx {
        let Some(lang) = CtxLang::from_ext(ext) else {
            return vec![];
        };
        let Some(tree) = ctx.parse(rel_path, lang, content) else {
            return vec![];
        };
        return collect_imports_from_tree(&tree, content, "js");
    }
    let mut parser = tree_sitter::Parser::new();
    let lang = match ext {
        "ts" | "mts" | "cts" => tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into(),
        "tsx" | "jsx" => tree_sitter_typescript::LANGUAGE_TSX.into(),
        _ => tree_sitter_javascript::LANGUAGE.into(),
    };
    if parser.set_language(&lang).is_err() {
        return vec![];
    }
    let Some(tree) = parser.parse(content, None) else {
        return vec![];
    };
    collect_imports_from_tree(&tree, content, "js")
}

fn collect_imports_recursive(
    cursor: &mut tree_sitter::TreeCursor,
    source: &str,
    imports: &mut Vec<ImportEntry>,
    lang: &str,
    // Nesting depth inside function/method/class bodies.
    // 0 = module top-level.
    scope_depth: u32,
) {
    let node = cursor.node();
    let top_level = scope_depth == 0;

    // Track when we enter a function/method/class body — imports inside
    // those are "lazy" (deferred) and won't cause circular-import crashes.
    let enters_scope = matches!(
        node.kind(),
        "function_definition"
            | "function_declaration"
            | "method_definition"
            | "class_definition"
            | "class_declaration"
            | "arrow_function"
    );

    match lang {
        "python" => {
            if node.kind() == "import_from_statement" {
                let module_text = node
                    .child_by_field_name("module_name")
                    .and_then(|n| n.utf8_text(source.as_bytes()).ok().map(std::string::ToString::to_string));

                let mut names: Vec<String> = Vec::new();
                let mut has_star = false;
                let module_name_id = node.child_by_field_name("module_name").map(|n| n.id());
                for i in 0..node.child_count() {
                    if let Some(child) = node.child(i as u32) {
                        match child.kind() {
                            "wildcard_import" => has_star = true,
                            "dotted_name" => {
                                if module_name_id != Some(child.id()) {
                                    if let Ok(t) = child.utf8_text(source.as_bytes()) {
                                        names.push(t.to_string());
                                    }
                                }
                            }
                            "aliased_import" => {
                                if let Some(name_node) = child.child_by_field_name("name") {
                                    if let Ok(t) = name_node.utf8_text(source.as_bytes()) {
                                        names.push(t.to_string());
                                    }
                                }
                            }
                            _ => {}
                        }
                    }
                }

                if let Some(module) = module_text {
                    if has_star || names.is_empty() {
                        imports.push(ImportEntry { module, is_top_level: top_level });
                    } else {
                        let joiner = if module.ends_with('.') { "" } else { "." };
                        for n in names {
                            imports.push(ImportEntry {
                                module: format!("{module}{joiner}{n}"),
                                is_top_level: top_level,
                            });
                        }
                    }
                } else {
                    for i in 0..node.child_count() {
                        if let Some(child) = node.child(i as u32) {
                            if child.kind() == "relative_import" {
                                if let Ok(t) = child.utf8_text(source.as_bytes()) {
                                    if names.is_empty() {
                                        imports.push(ImportEntry { module: t.to_string(), is_top_level: top_level });
                                    } else {
                                        for n in &names {
                                            imports.push(ImportEntry {
                                                module: format!("{t}.{n}"),
                                                is_top_level: top_level,
                                            });
                                        }
                                    }
                                }
                                break;
                            }
                        }
                    }
                }
            } else if node.kind() == "import_statement" {
                for i in 0..node.child_count() {
                    if let Some(child) = node.child(i as u32) {
                        match child.kind() {
                            "dotted_name" => {
                                if let Ok(t) = child.utf8_text(source.as_bytes()) {
                                    imports.push(ImportEntry { module: t.to_string(), is_top_level: top_level });
                                }
                            }
                            "aliased_import" => {
                                if let Some(name_node) = child.child_by_field_name("name") {
                                    if let Ok(t) = name_node.utf8_text(source.as_bytes()) {
                                        imports.push(ImportEntry { module: t.to_string(), is_top_level: top_level });
                                    }
                                }
                            }
                            _ => {}
                        }
                    }
                }
            }
        }
        "js" => {
            if node.kind() == "import_statement" {
                // TypeScript `import type { X } from '...'` is erased at
                // compile time — it creates no runtime dependency. Skip it
                // from the module graph to avoid false-positive circular deps.
                let stmt_text = node
                    .utf8_text(source.as_bytes())
                    .unwrap_or("");
                let trimmed = stmt_text.trim_start();
                let is_type_only = trimmed.starts_with("import type")
                    || trimmed.starts_with("import type ")
                    || trimmed.starts_with("import type{");
                if !is_type_only {
                    if let Some(source_node) = node.child_by_field_name("source") {
                        if let Ok(text) = source_node.utf8_text(source.as_bytes()) {
                            let cleaned = text.trim_matches(|c| c == '\'' || c == '"');
                            imports.push(ImportEntry { module: cleaned.to_string(), is_top_level: top_level });
                        }
                    }
                }
            } else if node.kind() == "export_statement" {
                // export * from './module' / export { X } from './module'
                // Also skip `export type { X } from '...'` — erased at compile time.
                let stmt_text = node.utf8_text(source.as_bytes()).unwrap_or("");
                let trimmed = stmt_text.trim_start();
                let is_type_only = trimmed.starts_with("export type")
                    || trimmed.starts_with("export type ")
                    || trimmed.starts_with("export type{");
                if !is_type_only {
                    if let Some(source_node) = node.child_by_field_name("source") {
                        if let Ok(text) = source_node.utf8_text(source.as_bytes()) {
                            let cleaned = text.trim_matches(|c| c == '\'' || c == '"');
                            imports.push(ImportEntry { module: cleaned.to_string(), is_top_level: top_level });
                        }
                    }
                }
            } else if node.kind() == "call_expression" {
                if let Some(func) = node.child_by_field_name("function") {
                    if let Ok(fname) = func.utf8_text(source.as_bytes()) {
                        // require('...') or import('...') (dynamic)
                        if fname == "require" || fname == "import" {
                            if let Some(args) = node.child_by_field_name("arguments") {
                                if args.child_count() >= 2 {
                                    if let Some(arg) = args.child(1_u32) {
                                        if arg.kind() == "string" {
                                            if let Ok(text) = arg.utf8_text(source.as_bytes()) {
                                                let cleaned =
                                                    text.trim_matches(|c| c == '\'' || c == '"');
                                                imports.push(ImportEntry { module: cleaned.to_string(), is_top_level: top_level });
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        _ => {}
    }

    let child_depth = if enters_scope { scope_depth + 1 } else { scope_depth };
    if cursor.goto_first_child() {
        loop {
            collect_imports_recursive(cursor, source, imports, lang, child_depth);
            if !cursor.goto_next_sibling() {
                break;
            }
        }
        cursor.goto_parent();
    }
}

/// Check if an import string looks like a local import we can resolve.
///
/// `package_roots` is the set of top-level directories in the project
/// (e.g. {"core", "plugins", "gui"}). A Python import is local if it
/// either starts with `.` (relative) or its first dotted segment is
/// one of those roots (absolute project-rooted import).
fn is_local_import(
    imp: &str,
    lang: &str,
    package_roots: &HashSet<String>,
    local_stems: &HashSet<String>,
) -> bool {
    match lang {
        "python" => {
            if imp.starts_with('.') {
                return true;
            }
            let first = imp.split('.').next().unwrap_or("");
            if first.is_empty() {
                return false;
            }
            if package_roots.contains(first) {
                return true;
            }
            // Sibling-file sys.path.insert trick: `from schemas import X` in
            // examples/foo/pipeline.py refers to examples/foo/schemas.py.
            // If the first segment matches a .py file stem anywhere in the
            // project, allow resolution to try.
            local_stems.contains(first)
        }
        "js" => {
            imp.starts_with("./")
                || imp.starts_with("../")
                || imp.starts_with("@/")
                || imp.starts_with("~/")
                // bare `src/...` baseUrl — common in NestJS / tsconfig-paths
                || imp.starts_with("src/")
                || imp.starts_with("test/")
        }
        _ => false,
    }
}

/// Try to resolve a local import to a project file path.
fn resolve_local_import(
    imp: &str,
    source_file: &Path,
    root: &Path,
    all_files: &HashSet<String>,
    lang: &str,
) -> Option<String> {
    match lang {
        "python" => resolve_python_import(imp, source_file, root, all_files),
        "js" => resolve_js_import(imp, source_file, root, all_files),
        _ => None,
    }
}

fn resolve_python_import(
    imp: &str,
    source_file: &Path,
    root: &Path,
    all_files: &HashSet<String>,
) -> Option<String> {
    // Relative imports: `.foo`, `..foo.bar` — resolve against source_file's dir.
    // Absolute imports: `core.foo.bar` — try project root, then `src/` and
    // `packages/` roots (common Python/monorepo layouts).
    let mut bases: Vec<PathBuf> = Vec::new();
    let module: String;
    if imp.starts_with('.') {
        let dots = imp.chars().take_while(|c| *c == '.').count();
        module = imp[dots..].to_string();
        let mut base = source_file.parent()?.to_path_buf();
        for _ in 1..dots {
            base = base.parent()?.to_path_buf();
        }
        bases.push(base);
    } else {
        module = imp.to_string();
        bases.push(root.to_path_buf());
        // src/ layout fallback
        let src = root.join("src");
        if src.is_dir() {
            bases.push(src);
        }
        // monorepo packages/ layout — each subdir of packages/ is a package root
        let packages = root.join("packages");
        if let Ok(entries) = packages.read_dir() {
            for entry in entries.flatten() {
                let p = entry.path();
                if p.is_dir() {
                    bases.push(p);
                }
            }
        }
        // sibling-dir sys.path.insert trick: `from schemas import X` in
        // examples/foo/pipeline.py refers to examples/foo/schemas.py.
        // Try the source file's own directory as a last-resort base.
        // (Note: `from schemas import X` parses as "schemas.X" — contains dot.)
        if let Some(parent) = source_file.parent() {
            bases.push(parent.to_path_buf());
        }
    }

    if module.is_empty() {
        return None;
    }

    // Walk up the module path, trying the longest prefix first.
    let parts: Vec<&str> = module.split('.').collect();
    for base in &bases {
        for take in (1..=parts.len()).rev() {
            let prefix = parts[..take].join("/");
            let file_path = base.join(format!("{prefix}.py"));
            if let Some(rel) = try_rel(&file_path, root) {
                if all_files.contains(&rel) {
                    return Some(rel);
                }
            }
            let init_path = base.join(format!("{prefix}/__init__.py"));
            if let Some(rel) = try_rel(&init_path, root) {
                if all_files.contains(&rel) {
                    return Some(rel);
                }
            }
        }
    }

    None
}

fn resolve_js_import(
    imp: &str,
    source_file: &Path,
    root: &Path,
    all_files: &HashSet<String>,
) -> Option<String> {
    // Handle `@/` and `~/` path aliases: try several common targets since
    // tsconfig mappings differ across projects:
    //   - `@/*` → `./src/*`        (Next.js default)
    //   - `@/*` → `./src/modules/*` (Twenty twenty-front convention)
    //   - `~/*` → `./src/*`
    // Rather than parse tsconfig.json, try a small set of candidates and
    // return the first that resolves.
    if let Some(rest) = imp.strip_prefix("@/").or_else(|| imp.strip_prefix("~/")) {
        let alias_root = find_alias_root(source_file, root);
        let candidates = [
            alias_root.join(rest),                  // bare @/foo → ./foo
            alias_root.join("src").join(rest),      // @/foo → ./src/foo
            alias_root.join("src/modules").join(rest), // @/foo → ./src/modules/foo
        ];
        for cand in &candidates {
            if let Some(r) = resolve_js_path(cand, root, all_files) {
                return Some(r);
            }
        }
        return None;
    }

    // Bare `src/...` or `test/...` — tsconfig baseUrl style (NestJS, etc.)
    if imp.starts_with("src/") || imp.starts_with("test/") {
        let alias_root = find_alias_root(source_file, root);
        let target = alias_root.join(imp);
        return resolve_js_path(&target, root, all_files);
    }

    let source_dir = source_file.parent()?;
    let target = source_dir.join(imp);
    resolve_js_path(&target, root, all_files)
}

/// Find the closest ancestor directory with tsconfig.json (for @/ alias root).
fn find_alias_root(source_file: &Path, project_root: &Path) -> PathBuf {
    let mut dir = source_file.parent().unwrap_or(project_root);
    loop {
        if dir.join("tsconfig.json").exists() || dir.join("tsconfig.app.json").exists() {
            return dir.to_path_buf();
        }
        if dir == project_root || dir.parent().is_none() {
            return project_root.to_path_buf();
        }
        dir = dir.parent().unwrap_or(project_root);
    }
}

/// Resolve a JS/TS path to a project-relative file, trying extensions and index files.
fn resolve_js_path(target: &Path, root: &Path, all_files: &HashSet<String>) -> Option<String> {
    let normalized = if target.exists() {
        target.canonicalize().unwrap_or(target.to_path_buf())
    } else {
        normalize_path_components(target)
    };
    let rel = try_rel(&normalized, root)?;
    if all_files.contains(&rel) {
        return Some(rel);
    }
    for ext in &["js", "ts", "jsx", "tsx", "mjs", "mts"] {
        let with_ext = format!("{rel}.{ext}");
        if all_files.contains(&with_ext) {
            return Some(with_ext);
        }
        let index = format!("{rel}/index.{ext}");
        if all_files.contains(&index) {
            return Some(index);
        }
    }
    None
}

/// Normalize path components, resolving `..` and `.` without hitting the
/// filesystem (unlike `canonicalize`).
fn normalize_path_components(path: &Path) -> PathBuf {
    let mut components: Vec<std::path::Component> = Vec::new();
    for component in path.components() {
        match component {
            std::path::Component::ParentDir => {
                // Pop the last normal component if possible.
                if matches!(components.last(), Some(std::path::Component::Normal(_))) {
                    components.pop();
                } else {
                    components.push(component);
                }
            }
            std::path::Component::CurDir => {
                // Skip `.` components.
            }
            other => components.push(other),
        }
    }
    components.iter().collect()
}

fn try_rel(p: &Path, root: &Path) -> Option<String> {
    p.strip_prefix(root)
        .ok()
        .map(|r| r.to_string_lossy().replace('\\', "/"))
}

#[pyfunction]
pub fn scan_module_map(path: &str, entry_point_paths: Vec<String>) -> PyResult<ModuleMapResult> {
    scan_module_map_inner(path, entry_point_paths, None)
}

#[pyfunction]
pub fn scan_module_map_with_context(
    ctx: &ScanContext,
    path: &str,
    entry_point_paths: Vec<String>,
) -> PyResult<ModuleMapResult> {
    scan_module_map_inner(path, entry_point_paths, Some(ctx))
}

fn scan_module_map_inner(
    path: &str,
    entry_point_paths: Vec<String>,
    ctx: Option<&ScanContext>,
) -> PyResult<ModuleMapResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {path}"),
        ));
    }

    let mut all_files: HashSet<String> = HashSet::new();
    let mut source_files: Vec<(PathBuf, String)> = Vec::new();

    // module_map keeps generated files in the graph so it can resolve
    // imports of generated code that are still referenced from hand-written
    // sources. Disable the default skip-generated filter.
    let opts = WalkOpts {
        skip_generated: false,
        ..WalkOpts::default()
    };
    for src in collect_source_files(root, &opts) {
        all_files.insert(src.rel_path.clone());
        source_files.push((src.abs_path, src.rel_path));
    }

    // Top-level directory names that contain at least one source file —
    // used to classify absolute Python imports as local.
    let mut package_roots: HashSet<String> = all_files
        .iter()
        .filter_map(|f| f.split('/').next())
        .filter(|s| !s.is_empty() && !s.ends_with(".py") && !s.contains('.'))
        .map(std::string::ToString::to_string)
        .collect();
    // src/ layout: `src/foo/bar.py` means `foo` is also a package root.
    // Same for `packages/foo/...` monorepo layout.
    for prefix in &["src/", "packages/"] {
        for f in &all_files {
            if let Some(rest) = f.strip_prefix(prefix) {
                if let Some(pkg) = rest.split('/').next() {
                    if !pkg.is_empty() && !pkg.ends_with(".py") {
                        package_roots.insert(pkg.to_string());
                    }
                }
            }
        }
    }

    // Build set of all .py file stems for sibling-dir import detection
    // (sys.path.insert trick).
    let local_stems: HashSet<String> = all_files
        .iter()
        .filter(|f| f.ends_with(".py"))
        .filter_map(|f| {
            let stem = f.rsplit('/').next()?.strip_suffix(".py")?;
            if stem == "__init__" { None } else { Some(stem.to_string()) }
        })
        .collect();

    // resolved imports per file (deduped target paths).
    let mut file_imports: HashMap<String, Vec<String>> = HashMap::new();
    // Per-edge top-level flag: (source_file, target_file) → is_top_level.
    // If ANY import of target from source is top-level, the edge is top-level.
    let mut edge_is_top_level: HashMap<(String, String), bool> = HashMap::new();
    // Count unique importers per target file (not per symbol).
    let mut imported_by_set: HashMap<String, HashSet<String>> = HashMap::new();

    for (abs_path, rel_path) in &source_files {
        let ext = abs_path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("");

        // Prefer the cross-scanner cache when one was provided so other
        // context-aware scanners can reuse the same allocation.
        let content_holder = if let Some(ctx) = ctx {
            ctx.read_file(rel_path, abs_path)
        } else {
            fs::read_to_string(abs_path).ok().map(std::sync::Arc::new)
        };
        let Some(content_arc) = content_holder else {
            continue;
        };
        let content: &str = content_arc.as_str();

        let lang = match ext {
            "py" => "python",
            "js" | "jsx" | "mjs" | "cjs" | "ts" | "tsx" | "mts" | "cts" => "js",
            // Skip languages without import resolution support.
            _ => continue,
        };
        let raw_imports = if ext == "py" {
            extract_python_imports(content, rel_path, ctx)
        } else {
            extract_js_imports(content, rel_path, ext, ctx)
        };

        let mut resolved = Vec::new();
        for entry in &raw_imports {
            if is_local_import(&entry.module, lang, &package_roots, &local_stems) {
                let resolved_opt = resolve_local_import(&entry.module, abs_path, root, &all_files, lang);
                if let Some(resolved_path) = resolved_opt
                {
                    if &resolved_path != rel_path {
                        resolved.push(resolved_path.clone());
                        imported_by_set
                            .entry(resolved_path.clone())
                            .or_default()
                            .insert(rel_path.clone());
                        // Track whether the edge from this source to target is top-level.
                        let key = (rel_path.clone(), resolved_path);
                        let e = edge_is_top_level.entry(key).or_insert(false);
                        if entry.is_top_level {
                            *e = true;
                        }
                    }
                }
            }
        }

        resolved.sort();
        resolved.dedup();
        file_imports.insert(rel_path.clone(), resolved);
    }

    // Flatten to counts for the rest of the pipeline.
    let imported_by: HashMap<String, u32> = imported_by_set
        .iter()
        .map(|(k, v)| (k.clone(), v.len() as u32))
        .collect();

    let mut modules: Vec<ModuleInfo> = Vec::new();
    for (rel_path, imports) in &file_imports {
        let count = imported_by.get(rel_path).copied().unwrap_or(0);
        modules.push(ModuleInfo {
            path: rel_path.clone(),
            imports: imports.clone(),
            imported_by_count: count,
        });
    }

    let mut hub_list: Vec<(String, u32)> = imported_by
        .iter()
        .map(|(k, v)| (k.clone(), *v))
        .collect();
    hub_list.sort_by(|a, b| b.1.cmp(&a.1));
    let hub_modules: Vec<(String, u32)> = hub_list.into_iter().take(5).collect();

    // Circular dependency detection (direct A→B and B→A).
    // Mark as lazy if at least one direction uses a non-top-level import.
    let mut circular: Vec<CircularDep> = Vec::new();
    let mut seen_pairs: HashSet<(String, String)> = HashSet::new();

    for (file, imports) in &file_imports {
        for imp in imports {
            if let Some(reverse_imports) = file_imports.get(imp) {
                if reverse_imports.contains(file) {
                    let pair = if file < imp {
                        (file.clone(), imp.clone())
                    } else {
                        (imp.clone(), file.clone())
                    };
                    if seen_pairs.insert(pair.clone()) {
                        // Check if either direction is a lazy (non-top-level) import.
                        let a_to_b_top = edge_is_top_level
                            .get(&(file.clone(), imp.clone()))
                            .copied()
                            .unwrap_or(false);
                        let b_to_a_top = edge_is_top_level
                            .get(&(imp.clone(), file.clone()))
                            .copied()
                            .unwrap_or(false);
                        // Lazy if at least one direction is NOT top-level.
                        let is_lazy = !a_to_b_top || !b_to_a_top;
                        circular.push(CircularDep {
                            file_a: pair.0,
                            file_b: pair.1,
                            is_lazy,
                        });
                    }
                }
            }
        }
    }

    // Orphan candidates
    let entry_set: HashSet<&str> = entry_point_paths.iter().map(std::string::String::as_str).collect();

    // Build a set of files whose parent __init__.py imports them (re-exports).
    // If `gui/app/__init__.py` imports `gui/app/styles.py`, styles is not orphan.
    let mut reexported: HashSet<String> = HashSet::new();
    for (rel_path, imports) in &file_imports {
        if rel_path.ends_with("__init__.py") {
            for imp in imports {
                reexported.insert(imp.clone());
            }
        }
    }

    let orphan_candidates: Vec<String> = all_files
        .iter()
        .filter(|f| {
            !imported_by.contains_key(*f)
                && !reexported.contains(*f)
                && !entry_set.contains(f.as_str())
                && !is_generated_or_data_file(f)
                && !f.ends_with("__init__.py")
                && !f.ends_with("conftest.py")
                && !f.contains("/test")
                && !f.starts_with("test")
                // Skip migration files — they're run by framework, not imported
                && !f.contains("/migrations/")
                && !f.contains("/alembic/")
                // Skip common standalone scripts
                && !f.ends_with("setup.py")
                && !f.ends_with("manage.py")
                && !f.ends_with("wsgi.py")
                && !f.ends_with("asgi.py")
                // Rust: modules are included via `mod` in lib.rs/main.rs,
                // not via import statements. Skip .rs files from orphan
                // detection — Rust compiler enforces module structure.
                && !f.ends_with(".rs")
                // Go: same — packages are resolved by directory, not imports.
                && !f.ends_with(".go")
                // C/C++: headers are included via #include, not import.
                && !f.ends_with(".h")
                && !f.ends_with(".hpp")
                && !f.ends_with(".hxx")
                // Java/Kotlin: classpath resolution, not file imports.
                && !f.ends_with(".java")
                && !f.ends_with(".kt")
                && !f.ends_with(".kts")
                // Build tool config files — used by tooling, not imported
                && !f.ends_with(".config.js")
                && !f.ends_with(".config.ts")
                && !f.ends_with(".config.mjs")
                && !f.ends_with(".config.cjs")
                // Django/Flask auto-discovered modules
                && !f.ends_with("/admin.py")
                && !f.ends_with("/apps.py")
                && !f.ends_with("/urls.py")
                && !f.ends_with("settings.py")
                && !f.ends_with("/signals.py")
                && !f.ends_with("/receivers.py")
                && !f.ends_with("/tasks.py")
                // Next.js / Nuxt / SvelteKit convention files (auto-loaded by framework)
                && !f.ends_with("/layout.tsx") && !f.ends_with("/layout.jsx") && !f.ends_with("/layout.js")
                && !f.ends_with("/page.tsx") && !f.ends_with("/page.jsx") && !f.ends_with("/page.js")
                && !f.ends_with("/loading.tsx") && !f.ends_with("/loading.jsx")
                && !f.ends_with("/error.tsx") && !f.ends_with("/error.jsx")
                && !f.ends_with("/not-found.tsx") && !f.ends_with("/not-found.jsx")
                && !f.ends_with("/template.tsx") && !f.ends_with("/template.jsx")
                && !f.ends_with("/default.tsx") && !f.ends_with("/default.jsx")
                && !f.ends_with("robots.ts") && !f.ends_with("sitemap.ts")
                && !f.ends_with("middleware.ts") && !f.ends_with("middleware.js")
                // Docusaurus convention files (loaded by framework via config)
                && !f.ends_with("/sidebars.ts") && !f.ends_with("/sidebars.js")
                && !f.ends_with("/docusaurus.config.ts") && !f.ends_with("/docusaurus.config.js")
                && !f.ends_with("/babel.config.ts") && !f.ends_with("/babel.config.js")
                // TypeScript declaration files — used by compiler, not imported
                && !f.ends_with(".d.ts")
        })
        .cloned()
        .collect();

    Ok(ModuleMapResult {
        modules,
        hub_modules,
        circular_deps: circular,
        orphan_candidates,
    })
}
