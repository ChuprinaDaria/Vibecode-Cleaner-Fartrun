//! Check 2.5 — Duplicate Code Blocks.
//!
//! Token-based matching: normalize lines (strip whitespace/comments),
//! build N-gram hashes, find matching sequences across files.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use ignore::WalkBuilder;
use pyo3::prelude::*;

use crate::common::{is_generated_or_data_file, should_skip_entry, SOURCE_EXTENSIONS};

const MIN_DUPLICATE_LINES: usize = 10;
const NGRAM_SIZE: usize = 10;

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
        h ^= b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

/// Build N-gram hashes for normalized lines of a file.
/// Returns vec of (ngram_hash, start_line_in_original).
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
            format!("Not a directory: {}", path),
        ));
    }

    // Phase 1: Collect and normalize all source files
    struct FileInfo {
        rel_path: String,
        normalized_lines: Vec<(usize, String)>, // (original_line, normalized)
        original_lines: Vec<String>,             // for preview
    }

    let mut files: Vec<FileInfo> = Vec::new();

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
        let rel_path = match entry_path.strip_prefix(root) {
            Ok(r) => crate::common::normalize_path(&r.to_string_lossy()),
            Err(_) => continue,
        };

        // Skip test files
        if rel_path.contains("/test") || rel_path.starts_with("test") || rel_path.contains("/__tests__/") {
            continue;
        }

        // Skip generated/mock/seed data — they're not hand-authored, so
        // flagging them as duplicates is useless noise.
        if is_generated_or_data_file(&rel_path) {
            continue;
        }

        let content = match fs::read_to_string(entry_path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let lang = match ext {
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
        };

        let original_lines: Vec<String> = content.lines().map(|l| l.to_string()).collect();
        let mut normalized = Vec::new();
        for (idx, line) in original_lines.iter().enumerate() {
            if let Some(norm) = normalize_line(line, lang) {
                normalized.push((idx + 1, norm)); // 1-based line number
            }
        }

        if normalized.len() >= MIN_DUPLICATE_LINES {
            files.push(FileInfo {
                rel_path,
                normalized_lines: normalized,
                original_lines,
            });
        }
    }

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
                    .map(|l| l.as_str())
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

    Ok(DuplicatesResult { duplicates: merged })
}
