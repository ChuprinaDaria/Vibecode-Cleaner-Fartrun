pub mod issue;
pub mod parser;
pub mod rules;

use issue::Issue;
use oxc_allocator::Allocator;
use std::path::Path;
use walkdir::WalkDir;

pub fn scan_directory(root: &Path) -> Vec<Issue> {
    let mut all = Vec::new();

    for entry in WalkDir::new(root).into_iter().filter_map(std::result::Result::ok) {
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let ext = path.extension().and_then(|e| e.to_str()).unwrap_or("");
        if !matches!(ext, "jsx" | "tsx" | "js" | "ts") {
            continue;
        }
        let s = path.to_string_lossy();
        if s.contains("node_modules")
            || s.contains("/dist/")
            || s.contains("/build/")
            || s.contains("/.next/")
            || s.contains("/.venv/")
            || s.contains("/venv/")
        {
            continue;
        }

        let Ok(source) = std::fs::read_to_string(path) else {
            continue;
        };

        // Build relative path from root
        let rel_path = path
            .strip_prefix(root)
            .unwrap_or(path)
            .to_string_lossy()
            .to_string();

        let allocator = Allocator::default();
        let Some(parsed) = parser::parse(&allocator, &source, &rel_path) else {
            continue;
        };

        all.extend(rules::button_no_handler::check(&parsed, &rel_path));
        all.extend(rules::handler_called::check(&parsed, &rel_path));
        all.extend(rules::effect_no_deps::check(&parsed, &rel_path));
        all.extend(rules::setstate_in_render::check(&parsed, &rel_path));
        all.extend(rules::async_handler_no_catch::check(&parsed, &rel_path));
    }

    all
}
