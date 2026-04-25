//! Check 2.5 — Duplicate Code Blocks.
//!
//! Token-based matching: normalize lines (strip whitespace/comments),
//! build N-gram hashes, find matching sequences across files.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use pyo3::prelude::*;

use crate::common::{collect_source_files, is_test_path, WalkOpts};

const MIN_DUPLICATE_LINES: usize = 10;
const NGRAM_SIZE: usize = 10;

/// Per-file normalized state. Persisted between runs so warm re-scans
/// only re-normalize files that changed.
#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct FileInfo {
    rel_path: String,
    /// (original_line_number, normalized_content)
    normalized_lines: Vec<(usize, String)>,
    /// Raw lines, kept for previews when a duplicate hit lands on this file.
    original_lines: Vec<String>,
}

/// Map an extension to the language family `normalize_line` understands.
fn lang_for_ext(ext: &str) -> &'static str {
    match ext {
        "py" => "python",
        "ts" | "tsx" | "mts" | "cts" => "ts",
        "js" | "jsx" | "mjs" | "cjs" => "js",
        "rs" => "rust",
        "go" => "go",
        "c" | "h" | "cpp" | "hpp" | "cc" | "cxx" | "hxx" => "c",
        "java" | "kt" | "kts" => "java",
        "rb" => "ruby",
        "php" => "php",
        "swift" => "swift",
        "cs" => "cs",
        _ => "js",
    }
}

/// Build a FileInfo for one file. Returns None when the file has fewer
/// than MIN_DUPLICATE_LINES of analysis-eligible lines (no point in
/// caching empty rows, and the cross-file phase ignores those anyway).
fn build_file_info(rel_path: &str, content: &str, ext: &str) -> Option<FileInfo> {
    let lang = lang_for_ext(ext);
    let original_lines: Vec<String> = content.lines().map(std::string::ToString::to_string).collect();
    let mut normalized = Vec::new();
    for (idx, line) in original_lines.iter().enumerate() {
        if let Some(norm) = normalize_line(line, lang) {
            normalized.push((idx + 1, norm));
        }
    }
    if normalized.len() < MIN_DUPLICATE_LINES {
        return None;
    }
    Some(FileInfo {
        rel_path: rel_path.to_string(),
        normalized_lines: normalized,
        original_lines,
    })
}

#[pyclass]
#[derive(Clone)]
pub struct DuplicateBlock {
    #[pyo3(get)]
    pub file_a: String,
    #[pyo3(get)]
    pub line_a: u32,
    #[pyo3(get)]
    pub file_b: String,
    #[pyo3(get)]
    pub line_b: u32,
    #[pyo3(get)]
    pub line_count: u32,
    #[pyo3(get)]
    pub preview: String,
}

#[pyclass]
#[derive(Clone)]
pub struct DuplicatesResult {
    #[pyo3(get)]
    pub duplicates: Vec<DuplicateBlock>,
}

/// Normalize a source line: strip whitespace, skip comments and empty lines.
/// Returns None if line should be skipped.
fn normalize_line(line: &str, lang: &str) -> Option<String> {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return None;
    }

    match lang {
        "python" | "ruby" => {
            if trimmed.starts_with('#') {
                return None;
            }
            if trimmed == "\"\"\"" || trimmed == "'''" {
                return None;
            }
        }
        "js" | "ts" | "rust" | "go" | "c" | "java" | "swift" | "cs" | "php" => {
            if trimmed.starts_with("//") {
                return None;
            }
            if trimmed.starts_with('*') || trimmed.starts_with("/*") || trimmed.starts_with("*/") {
                return None;
            }
        }
        _ => {}
    }

    // Skip import/use/include lines (too generic, many files have same imports)
    let lower = trimmed.to_lowercase();
    if lower.starts_with("import ")
        || lower.starts_with("from ")
        || lower.contains("require(")
        || lower.starts_with("export ")
        || lower.starts_with("use ")       // Rust / PHP
        || lower.starts_with("#include")   // C/C++
        || lower.starts_with("package ")   // Go/Java
        || lower.starts_with("using ")     // C#
        || lower.starts_with("require ")   // Ruby
    {
        return None;
    }

    // Normalize: collapse whitespace
    let normalized: String = trimmed.split_whitespace().collect::<Vec<_>>().join(" ");
    if normalized.len() < 3 {
        return None; // Skip trivial lines like "}", ")", "]"
    }

    Some(normalized)
}

/// Simple hash for a string.
fn hash_str(s: &str) -> u64 {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in s.bytes() {
        h ^= u64::from(b);
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

/// Build N-gram hashes for normalized lines of a file.
/// Returns vec of (`ngram_hash`, `start_line_in_original`).
fn build_ngrams(
    lines: &[(usize, String)], // (original_line_number, normalized_content)
) -> Vec<(u64, usize)> {
    if lines.len() < NGRAM_SIZE {
        return vec![];
    }

    let mut ngrams = Vec::new();
    for i in 0..=lines.len() - NGRAM_SIZE {
        let window: String = lines[i..i + NGRAM_SIZE]
            .iter()
            .map(|(_, s)| s.as_str())
            .collect::<Vec<_>>()
            .join("\n");
        let h = hash_str(&window);
        ngrams.push((h, lines[i].0)); // original line number
    }

    ngrams
}

#[pyfunction]
pub fn scan_duplicates(path: &str) -> PyResult<DuplicatesResult> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {path}"),
        ));
    }

    // Phase 1: Collect and normalize all source files
    let mut files: Vec<FileInfo> = Vec::new();

    for src in collect_source_files(root, &WalkOpts::default()) {
        if is_test_path(&src.rel_path) {
            continue;
        }
        let content = match fs::read_to_string(&src.abs_path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        if let Some(info) = build_file_info(&src.rel_path, &content, src.ext.as_str()) {
            files.push(info);
        }
    }

    Ok(compute_duplicates_from_files(&files))
}

/// Parse one file into its FileInfo and return the JSON payload, or an
/// empty string when the file has fewer than MIN_DUPLICATE_LINES of
/// analysable lines (callers handle empty payload as "drop entry").
#[pyfunction]
pub fn parse_duplicates_file_json(
    rel_path: &str,
    content: &str,
    ext: &str,
) -> PyResult<String> {
    let Some(info) = build_file_info(rel_path, content, ext) else {
        return Ok(String::new());
    };
    serde_json::to_string(&info)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

/// Walk the project, build one FileInfo per analysable file, and return
/// `{rel_path: payload_json}`. Used by the orchestrator to populate
/// file_data_cache on full scans.
#[pyfunction]
pub fn collect_duplicates_state(
    path: &str,
) -> PyResult<std::collections::HashMap<String, String>> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Not a directory: {path}"),
        ));
    }
    let mut out = std::collections::HashMap::new();
    for src in collect_source_files(root, &WalkOpts::default()) {
        if is_test_path(&src.rel_path) {
            continue;
        }
        let Ok(content) = fs::read_to_string(&src.abs_path) else {
            continue;
        };
        let Some(info) = build_file_info(&src.rel_path, &content, src.ext.as_str()) else {
            continue;
        };
        match serde_json::to_string(&info) {
            Ok(payload) => {
                out.insert(src.rel_path, payload);
            }
            Err(e) => eprintln!(
                "collect_duplicates_state: serialize failed for {}: {e}",
                src.rel_path
            ),
        }
    }
    Ok(out)
}

/// Run the duplicates cross-file phase against a precomputed set of
/// FileInfo payloads. Same DuplicatesResult shape as `scan_duplicates`.
#[pyfunction]
pub fn assemble_duplicates_from_json(
    file_data_jsons: Vec<String>,
) -> PyResult<DuplicatesResult> {
    let mut files: Vec<FileInfo> = Vec::with_capacity(file_data_jsons.len());
    for payload in file_data_jsons {
        if payload.is_empty() {
            // Empty payloads represent files we deliberately didn't index
            // (below MIN_DUPLICATE_LINES). Skip silently.
            continue;
        }
        match serde_json::from_str::<FileInfo>(&payload) {
            Ok(info) => files.push(info),
            Err(e) => eprintln!(
                "assemble_duplicates_from_json: skipping malformed payload: {e}"
            ),
        }
    }
    Ok(compute_duplicates_from_files(&files))
}

fn compute_duplicates_from_files(files: &[FileInfo]) -> DuplicatesResult {

    // Phase 2: Build ngram hashes per file
    // Map: ngram_hash → [(file_index, original_line)]
    let mut hash_map: HashMap<u64, Vec<(usize, usize)>> = HashMap::new();

    for (file_idx, file_info) in files.iter().enumerate() {
        let ngrams = build_ngrams(&file_info.normalized_lines);
        for (h, line) in ngrams {
            hash_map.entry(h).or_default().push((file_idx, line));
        }
    }

    // Phase 3: Find duplicates (hash appears in 2+ different files)
    let mut duplicates: Vec<DuplicateBlock> = Vec::new();
    let mut seen_pairs: std::collections::HashSet<(usize, usize, usize, usize)> =
        std::collections::HashSet::new();

    for locations in hash_map.values() {
        if locations.len() < 2 {
            continue;
        }

        // Check all pairs
        for i in 0..locations.len() {
            for j in (i + 1)..locations.len() {
                let (fi_a, line_a) = locations[i];
                let (fi_b, line_b) = locations[j];

                // Must be different files
                if fi_a == fi_b {
                    continue;
                }

                // Deduplicate: normalize pair order
                let key = if fi_a < fi_b {
                    (fi_a, line_a, fi_b, line_b)
                } else {
                    (fi_b, line_b, fi_a, line_a)
                };

                if !seen_pairs.insert(key) {
                    continue;
                }

                // Calculate actual matching length (may be longer than NGRAM_SIZE)
                let file_a = &files[fi_a];
                let file_b = &files[fi_b];

                let norm_a: Vec<&str> = file_a
                    .normalized_lines
                    .iter()
                    .filter(|(l, _)| *l >= line_a)
                    .map(|(_, s)| s.as_str())
                    .collect();
                let norm_b: Vec<&str> = file_b
                    .normalized_lines
                    .iter()
                    .filter(|(l, _)| *l >= line_b)
                    .map(|(_, s)| s.as_str())
                    .collect();

                let match_len = norm_a
                    .iter()
                    .zip(norm_b.iter())
                    .take_while(|(a, b)| a == b)
                    .count();

                if match_len < MIN_DUPLICATE_LINES {
                    continue;
                }

                // Preview: first 3 original lines from file A
                let preview: String = file_a
                    .original_lines
                    .iter()
                    .skip(line_a.saturating_sub(1))
                    .take(3)
                    .map(std::string::String::as_str)
                    .collect::<Vec<_>>()
                    .join("\n");

                // Normalize file order so merge can match overlapping pairs.
                let (norm_file_a, norm_line_a, norm_file_b, norm_line_b) =
                    if file_a.rel_path <= file_b.rel_path {
                        (&file_a.rel_path, line_a, &file_b.rel_path, line_b)
                    } else {
                        (&file_b.rel_path, line_b, &file_a.rel_path, line_a)
                    };
                duplicates.push(DuplicateBlock {
                    file_a: norm_file_a.clone(),
                    line_a: norm_line_a as u32,
                    file_b: norm_file_b.clone(),
                    line_b: norm_line_b as u32,
                    line_count: match_len as u32,
                    preview,
                });
            }
        }
    }

    // Merge overlapping duplicates between the same file pair.
    // When N-gram windows overlap, we get entries like:
    //   (fileA:105, fileB:120, 15 lines)
    //   (fileA:106, fileB:121, 14 lines)
    //   (fileA:107, fileB:122, 13 lines)
    // These are the same duplication — keep only the longest.
    duplicates.sort_by(|a, b| {
        (&a.file_a, &a.file_b, a.line_a).cmp(&(&b.file_a, &b.file_b, b.line_a))
    });

    let mut merged: Vec<DuplicateBlock> = Vec::new();
    for dup in duplicates {
        let dominated = merged.iter().any(|existing| {
            existing.file_a == dup.file_a
                && existing.file_b == dup.file_b
                && dup.line_a >= existing.line_a
                && dup.line_a <= existing.line_a + existing.line_count
                && dup.line_b >= existing.line_b
                && dup.line_b <= existing.line_b + existing.line_count
        });
        if !dominated {
            merged.push(dup);
        }
    }

    // Sort by line count desc
    merged.sort_by(|a, b| b.line_count.cmp(&a.line_count));

    // Cap at 20
    merged.truncate(20);

    DuplicatesResult { duplicates: merged }
}
