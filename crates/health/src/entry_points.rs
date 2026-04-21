//! Check 1.2 — Entry Points Detection.
//!
//! Finds main.py, index.js, package.json scripts, __main__.py,
//! and files with `if __name__ == "__main__"` or server creation patterns.

use std::collections::HashSet;
use std::fs;
use std::path::Path;

use ignore::WalkBuilder;
use pyo3::prelude::*;

use crate::common::should_skip_entry;

/// Known entry point file names.
const PYTHON_ENTRY_NAMES: &[&str] = &[
    "main.py", "app.py", "manage.py", "wsgi.py", "asgi.py",
    "__main__.py", "run.py", "server.py", "cli.py",
];

const JS_ENTRY_NAMES: &[&str] = &[
    "index.js", "index.ts", "index.jsx", "index.tsx",
    "index.mjs", "index.mts",
    "app.js", "app.ts", "app.jsx", "app.tsx",
    "server.js", "server.ts",
    "main.js", "main.ts",
];

#[pyclass]
#[derive(Clone)]
pub struct EntryPoint {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub kind: String,
    #[pyo3(get)]
    pub description: String,
}

#[pyclass]
#[derive(Clone)]
pub struct EntryPointsResult {
    #[pyo3(get)]
    pub entry_points: Vec<EntryPoint>,
}

#[pyfunction]
pub fn scan_entry_points(path: &str) -> PyResult<EntryPointsResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {}", path),
        ));
    }

    let mut entries: Vec<EntryPoint> = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();

    // Check package.json scripts
    let pkg_json = root.join("package.json");
    if pkg_json.is_file() {
        if let Ok(content) = fs::read_to_string(&pkg_json) {
            let mut scripts_found = Vec::new();
            if let Some(main_field) = extract_json_string(&content, "main") {
                scripts_found.push(main_field);
            }
            for script_name in &["start", "dev", "serve"] {
                if content.contains(&format!("\"{}\"", script_name)) {
                    scripts_found.push(script_name.to_string());
                }
            }
            if !scripts_found.is_empty() {
                let rel = "package.json".to_string();
                if seen.insert(rel.clone()) {
                    let desc = scripts_found.join(", ");
                    entries.push(EntryPoint {
                        path: rel,
                        kind: "package_json".to_string(),
                        description: format!("Node.js project config (scripts: {})", desc),
                    });
                }
            }
        }
    }

    // Walk source files
    let walker = WalkBuilder::new(root)
        .hidden(false)
        .git_ignore(true)
        .git_global(false)
        .git_exclude(true)
        .max_depth(Some(6))
        .filter_entry(|entry| !should_skip_entry(entry))
        .build();

    for entry in walker.flatten() {
        let entry_path = entry.path();
        if !entry_path.is_file() {
            continue;
        }

        let file_name = match entry_path.file_name().and_then(|n| n.to_str()) {
            Some(n) => n.to_lowercase(),
            None => continue,
        };

        let rel_path = match entry_path.strip_prefix(root) {
            Ok(r) => r.to_string_lossy().to_string(),
            Err(_) => continue,
        };

        if seen.contains(&rel_path) {
            continue;
        }

        // Check Python entry points by name
        if PYTHON_ENTRY_NAMES.iter().any(|n| *n == file_name) {
            let kind = if file_name == "manage.py" {
                "django_manage"
            } else if file_name == "__main__.py" {
                "python_package_main"
            } else if file_name == "wsgi.py" || file_name == "asgi.py" {
                "python_wsgi"
            } else {
                "python_main"
            };
            let desc = match kind {
                "django_manage" => "Django management script",
                "python_package_main" => "Python package entry point",
                "python_wsgi" => "WSGI/ASGI server entry",
                _ => "Python main module",
            };
            seen.insert(rel_path.clone());
            entries.push(EntryPoint {
                path: rel_path,
                kind: kind.to_string(),
                description: desc.to_string(),
            });
            continue;
        }

        // Check JS/TS entry points by name
        if JS_ENTRY_NAMES.iter().any(|n| *n == file_name) {
            seen.insert(rel_path.clone());
            entries.push(EntryPoint {
                path: rel_path,
                kind: "js_entry".to_string(),
                description: "JavaScript/TypeScript entry point".to_string(),
            });
            continue;
        }

        // Check file content for patterns (only source files, max 50KB)
        let ext = entry_path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("");
        if !crate::common::SOURCE_EXTENSIONS.contains(&ext) {
            continue;
        }
        if let Ok(meta) = entry_path.metadata() {
            if meta.len() > 50_000 {
                continue;
            }
        }
        if let Ok(content) = fs::read_to_string(entry_path) {
            if ext == "py" && content.contains("if __name__") && content.contains("__main__") {
                seen.insert(rel_path.clone());
                entries.push(EntryPoint {
                    path: rel_path,
                    kind: "python_main_guard".to_string(),
                    description: "Python script with __main__ guard".to_string(),
                });
            } else if ["js", "ts", "mjs", "mts"].contains(&ext) {
                if content.contains("createServer")
                    || content.contains(".listen(")
                    || content.contains("createApp")
                    || content.contains("express()")
                {
                    seen.insert(rel_path.clone());
                    entries.push(EntryPoint {
                        path: rel_path,
                        kind: "js_server".to_string(),
                        description: "Server/app creation detected".to_string(),
                    });
                }
            }
        }
    }

    Ok(EntryPointsResult { entry_points: entries })
}

/// Extract a string value for a top-level key from JSON (simple, no serde needed).
fn extract_json_string(json: &str, key: &str) -> Option<String> {
    let pattern = format!("\"{}\"", key);
    let pos = json.find(&pattern)?;
    let after = &json[pos + pattern.len()..];
    let after = after.trim_start();
    let after = after.strip_prefix(':')?;
    let after = after.trim_start();
    let after = after.strip_prefix('"')?;
    let end = after.find('"')?;
    Some(after[..end].to_string())
}
