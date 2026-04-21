//! Check 1.1 — File Tree Summary.
//!
//! Scans project directory, counts files by extension, measures depth.

use std::collections::HashMap;
use std::path::Path;

use ignore::WalkBuilder;
use pyo3::prelude::*;

use crate::common::should_skip_entry;

#[pyclass]
#[derive(Clone)]
pub struct FileTreeResult {
    #[pyo3(get)]
    pub total_files: u64,
    #[pyo3(get)]
    pub total_dirs: u64,
    #[pyo3(get)]
    pub total_size_bytes: u64,
    #[pyo3(get)]
    pub max_depth: u32,
    #[pyo3(get)]
    pub files_by_ext: HashMap<String, u64>,
    #[pyo3(get)]
    pub largest_dirs: Vec<(String, u64)>,
}

#[pyfunction]
pub fn scan_file_tree(path: &str) -> PyResult<FileTreeResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {}", path),
        ));
    }

    let mut total_files: u64 = 0;
    let mut total_dirs: u64 = 0;
    let mut total_size: u64 = 0;
    let mut max_depth: u32 = 0;
    let mut ext_counts: HashMap<String, u64> = HashMap::new();
    let mut dir_counts: HashMap<String, u64> = HashMap::new();

    let walker = WalkBuilder::new(root)
        .hidden(false)
        .git_ignore(true)
        .git_global(false)
        .git_exclude(true)
        .filter_entry(|entry| !should_skip_entry(entry))
        .build();

    for entry in walker.flatten() {
        let entry_path = entry.path();

        // Calculate depth relative to root
        if let Ok(rel) = entry_path.strip_prefix(root) {
            let depth = rel.components().count() as u32;
            if depth > max_depth {
                max_depth = depth;
            }
        }

        if entry_path.is_dir() {
            total_dirs += 1;
            continue;
        }

        // File
        total_files += 1;

        if let Ok(meta) = entry_path.metadata() {
            total_size += meta.len();
        }

        // Extension count
        if let Some(ext) = entry_path.extension().and_then(|e| e.to_str()) {
            let ext_lower = ext.to_lowercase();
            *ext_counts.entry(ext_lower).or_insert(0) += 1;
        } else {
            *ext_counts.entry(String::new()).or_insert(0) += 1;
        }

        // Parent directory file count
        if let Some(parent) = entry_path.parent() {
            if let Ok(rel) = parent.strip_prefix(root) {
                let dir_key = rel.to_string_lossy().to_string();
                *dir_counts.entry(dir_key).or_insert(0) += 1;
            }
        }
    }

    // Top 10 extensions by count
    let mut ext_vec: Vec<(String, u64)> = ext_counts.into_iter().collect();
    ext_vec.sort_by(|a, b| b.1.cmp(&a.1));
    let files_by_ext: HashMap<String, u64> = ext_vec.into_iter().take(10).collect();

    // Top 5 largest directories
    let mut dir_vec: Vec<(String, u64)> = dir_counts.into_iter().collect();
    dir_vec.sort_by(|a, b| b.1.cmp(&a.1));
    let largest_dirs: Vec<(String, u64)> = dir_vec.into_iter().take(5).collect();

    Ok(FileTreeResult {
        total_files,
        total_dirs,
        total_size_bytes: total_size,
        max_depth,
        files_by_ext,
        largest_dirs,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_scan_empty_dir() {
        let tmp = tempfile::tempdir().unwrap();
        let result = scan_file_tree(tmp.path().to_str().unwrap()).unwrap();
        assert_eq!(result.total_files, 0);
    }

    #[test]
    fn test_scan_with_files() {
        let tmp = tempfile::tempdir().unwrap();
        fs::write(tmp.path().join("main.py"), "print('hi')").unwrap();
        fs::write(tmp.path().join("app.js"), "console.log('hi')").unwrap();
        fs::create_dir(tmp.path().join("src")).unwrap();
        fs::write(tmp.path().join("src/utils.py"), "x = 1").unwrap();

        let result = scan_file_tree(tmp.path().to_str().unwrap()).unwrap();
        assert_eq!(result.total_files, 3);
        assert!(result.max_depth >= 1);
        assert!(result.files_by_ext.contains_key("py"));
        assert_eq!(*result.files_by_ext.get("py").unwrap(), 2);
    }

    #[test]
    fn test_skips_node_modules() {
        let tmp = tempfile::tempdir().unwrap();
        fs::create_dir(tmp.path().join("node_modules")).unwrap();
        fs::write(tmp.path().join("node_modules/junk.js"), "x").unwrap();
        fs::write(tmp.path().join("app.js"), "y").unwrap();

        let result = scan_file_tree(tmp.path().to_str().unwrap()).unwrap();
        assert_eq!(result.total_files, 1);
    }
}
