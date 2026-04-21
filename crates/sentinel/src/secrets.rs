//! Secret scanner — detects hardcoded API keys, tokens, passwords in source files.
//!
//! Uses compiled regex patterns and parallel directory walk (rayon) for speed.
//! One finding per line, skips test mocks and obvious placeholders.

use pyo3::prelude::*;
use regex::Regex;
use rayon::prelude::*;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

/// File extensions to scan.
const SCAN_EXTENSIONS: &[&str] = &[
    "py", "js", "ts", "jsx", "tsx", "rb", "go", "java", "rs", "php",
    "env", "txt", "yaml", "yml", "json", "toml", "cfg", "ini", "conf",
    "sh", "bash", "zsh", "properties", "xml",
];

/// Directories to skip during walk.
const SKIP_DIRS: &[&str] = &[
    "node_modules", ".git", "__pycache__", "target", ".cargo", ".rustup",
    "venv", ".venv", ".local", ".cache", "dist", "build", ".next",
    ".nuxt", "vendor", "proc", "sys", "dev",
];

/// Absolute path prefixes to skip (Linux kernel/device filesystems).
const SKIP_PATH_PREFIXES: &[&str] = &[
    "/proc", "/sys", "/dev",
];

/// Max file size: 1 MB.
const MAX_FILE_SIZE: u64 = 1024 * 1024;

/// Max directory depth.
const MAX_DEPTH: usize = 10;

/// False-positive placeholder substrings — skip if the matched value contains these.
const FP_PLACEHOLDERS: &[&str] = &[
    "xxx", "your_", "your-", "<your", "example", "changeme", "placeholder",
    "insert_", "put_your", "replace_me", "dummy", "fake", "test_token",
    "test_key", "test_secret", "sample", "xxxxxxxx", "000000000000",
    "111111111111",
];

/// Each pattern: (name, regex_str)
/// All findings are "critical" severity as required.
static PATTERNS: &[(&str, &str)] = &[
    // AWS access keys
    (
        "aws_access_key",
        r"(?i)(AKIA[0-9A-Z]{16})",
    ),
    // GitHub tokens
    (
        "github_token",
        r"(?i)(ghp_[A-Za-z0-9]{36,}|gho_[A-Za-z0-9]{36,}|ghs_[A-Za-z0-9]{36,}|ghu_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{20,})",
    ),
    // OpenAI API key
    (
        "openai_api_key",
        r"(?i)(sk-[A-Za-z0-9]{20,})",
    ),
    // Anthropic API key
    (
        "anthropic_api_key",
        r"(?i)(sk-ant-[A-Za-z0-9\-_]{20,})",
    ),
    // Stripe keys
    (
        "stripe_key",
        r"(?i)(sk_live_[A-Za-z0-9]{24,}|sk_test_[A-Za-z0-9]{24,}|pk_live_[A-Za-z0-9]{24,}|pk_test_[A-Za-z0-9]{24,})",
    ),
    // Slack tokens
    (
        "slack_token",
        r"(?i)(xox[boaprs]-[A-Za-z0-9\-]{10,})",
    ),
    // Private key blocks
    (
        "private_key",
        r"-----BEGIN (RSA |EC |DSA |OPENSSH |)?PRIVATE KEY-----",
    ),
    // Generic: password=value (not empty, not placeholder)
    (
        "generic_password",
        r#"(?i)(?:^|[^a-zA-Z])password\s*[:=]\s*["']?([A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?/]{8,})["']?"#,
    ),
    // Generic: secret=value
    (
        "generic_secret",
        r#"(?i)(?:^|[^a-zA-Z])secret\s*[:=]\s*["']?([A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?/]{8,})["']?"#,
    ),
    // Generic: token=value
    (
        "generic_token",
        r#"(?i)(?:^|[^a-zA-Z])token\s*[:=]\s*["']?([A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?/]{16,})["']?"#,
    ),
    // Generic: api_key=value
    (
        "generic_api_key",
        r#"(?i)(?:^|[^a-zA-Z])api[_\-]?key\s*[:=]\s*["']?([A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?/]{16,})["']?"#,
    ),
    // Database URLs with credentials (postgres://, mysql://, mongodb://)
    (
        "database_url",
        r"(?i)((?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis)://[^:@\s]+:[^@\s]+@[^\s]+)",
    ),
    // Bearer tokens in code/config (not HTTP headers — actual hardcoded values)
    (
        "bearer_token",
        r#"(?i)(?:Authorization|auth)[^=:\n]*[:=]\s*["']?Bearer\s+([A-Za-z0-9\-._~+/]{20,}=*)["']?"#,
    ),
    // Google API keys
    (
        "google_api_key",
        r"(?i)(AIza[0-9A-Za-z\-_]{35})",
    ),
    // Telegram bot tokens
    (
        "telegram_bot_token",
        r"(?i)(\b[0-9]{8,10}:[A-Za-z0-9_\-]{35}\b)",
    ),
];

/// Compiled pattern entry.
struct CompiledPattern {
    name: &'static str,
    regex: Regex,
}

/// A single secret finding.
#[pyclass]
#[derive(Clone)]
pub struct SecretFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub line_number: usize,
    #[pyo3(get)]
    pub secret_type: String,
}

#[pymethods]
impl SecretFinding {
    fn __repr__(&self) -> String {
        format!(
            "SecretFinding(severity='{}', type='{}', path='{}', line={})",
            self.severity, self.secret_type, self.path, self.line_number
        )
    }
}

/// Scan files in scan_paths for hardcoded secrets.
/// Defaults to current directory if no paths given.
#[pyfunction]
#[pyo3(signature = (scan_paths=None))]
pub fn scan_secrets(scan_paths: Option<Vec<String>>) -> Vec<SecretFinding> {
    let paths: Vec<PathBuf> = scan_paths
        .unwrap_or_else(|| {
            let cwd = std::env::current_dir()
                .unwrap_or_else(|_| PathBuf::from("."));
            vec![cwd.to_string_lossy().to_string()]
        })
        .into_iter()
        .map(PathBuf::from)
        .collect();

    // Compile patterns once.
    let compiled: Vec<CompiledPattern> = PATTERNS
        .iter()
        .filter_map(|(name, pat)| {
            Regex::new(pat).ok().map(|regex| CompiledPattern { name, regex })
        })
        .collect();
    let compiled = Arc::new(compiled);

    // Collect all candidate files in parallel using rayon.
    let findings: Arc<Mutex<Vec<SecretFinding>>> = Arc::new(Mutex::new(Vec::new()));

    let files = collect_files(&paths);

    files.par_iter().for_each(|file_path| {
        let compiled = Arc::clone(&compiled);
        let findings = Arc::clone(&findings);
        if let Some(mut file_findings) = scan_file(file_path, &compiled) {
            let mut lock = findings.lock().unwrap();
            lock.append(&mut file_findings);
        }
    });

    let findings = Arc::try_unwrap(findings)
        .unwrap_or_else(|a| {
            let guard = a.lock().unwrap();
            std::sync::Mutex::new(guard.clone())
        });
    let mut result = findings.into_inner().unwrap_or_default();

    // Sort by path then line for deterministic output.
    result.sort_by(|a, b| a.path.cmp(&b.path).then(a.line_number.cmp(&b.line_number)));
    result
}

/// Recursively collect all scannable files respecting depth and skip rules.
fn collect_files(roots: &[PathBuf]) -> Vec<PathBuf> {
    let files: Arc<Mutex<Vec<PathBuf>>> = Arc::new(Mutex::new(Vec::new()));
    for root in roots {
        collect_recursive(root, &files, 0);
    }
    let files = Arc::try_unwrap(files)
        .unwrap_or_else(|a| {
            let guard = a.lock().unwrap();
            std::sync::Mutex::new(guard.clone())
        });
    files.into_inner().unwrap_or_default()
}

fn collect_recursive(dir: &Path, files: &Arc<Mutex<Vec<PathBuf>>>, depth: usize) {
    if depth > MAX_DEPTH {
        return;
    }

    // Skip known virtual/kernel FS paths.
    let path_str = dir.to_string_lossy();
    if SKIP_PATH_PREFIXES.iter().any(|p| path_str.starts_with(p)) {
        return;
    }

    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    let mut subdirs: Vec<PathBuf> = Vec::new();

    for entry in entries.flatten() {
        let path = entry.path();
        let file_name = entry.file_name();
        let name_str = file_name.to_string_lossy();

        if path.is_symlink() {
            // Don't follow symlinks to avoid loops.
            continue;
        }

        if path.is_dir() {
            let lower = name_str.to_lowercase();
            if SKIP_DIRS.iter().any(|&s| lower == s) {
                continue;
            }
            subdirs.push(path);
            continue;
        }

        if !path.is_file() {
            continue;
        }

        // Check extension.
        if let Some(ext) = path.extension() {
            let ext_lower = ext.to_string_lossy().to_lowercase();
            if !SCAN_EXTENSIONS.contains(&ext_lower.as_ref()) {
                // Also check for extensionless files like .env
                let name_lower = name_str.to_lowercase();
                if !name_lower.starts_with(".env") {
                    continue;
                }
            }
        } else {
            // No extension — check if it's a dotfile like .env
            let name_lower = name_str.to_lowercase();
            if !name_lower.starts_with(".env") {
                continue;
            }
        }

        // Check file size.
        if let Ok(meta) = path.metadata() {
            if meta.len() > MAX_FILE_SIZE {
                continue;
            }
        }

        files.lock().unwrap().push(path);
    }

    // Recurse into subdirectories.
    for subdir in subdirs {
        collect_recursive(&subdir, files, depth + 1);
    }
}

/// Scan a single file for secrets. Returns None if file can't be read.
fn scan_file(path: &Path, patterns: &[CompiledPattern]) -> Option<Vec<SecretFinding>> {
    let content = std::fs::read_to_string(path).ok()?;
    let path_str = path.to_string_lossy().to_string();

    let mut findings = Vec::new();

    'lines: for (line_idx, line) in content.lines().enumerate() {
        let line_number = line_idx + 1;

        // Skip blank lines.
        if line.trim().is_empty() {
            continue;
        }

        // Skip comment-heavy lines that are likely docs/examples.
        let trimmed = line.trim_start();
        // Allow lines that start with comment markers only if they contain actual secret patterns.
        // (We don't skip comments entirely — secrets DO appear in comments.)

        for pattern in patterns {
            if let Some(cap) = pattern.regex.captures(line) {
                // Get the captured group (group 1 if exists, else full match).
                let matched_value = cap.get(1)
                    .or_else(|| cap.get(0))
                    .map(|m| m.as_str())
                    .unwrap_or("");

                if matched_value.is_empty() {
                    continue;
                }

                // False positive: placeholder check.
                let value_lower = matched_value.to_lowercase();
                if FP_PLACEHOLDERS.iter().any(|fp| value_lower.contains(fp)) {
                    continue;
                }

                // False positive: test mock patterns in file path.
                let path_lower = path_str.to_lowercase();
                let is_test_file = path_lower.contains("/test")
                    || path_lower.contains("_test.")
                    || path_lower.contains(".test.")
                    || path_lower.contains("/spec")
                    || path_lower.contains("_spec.")
                    || path_lower.contains("/mock")
                    || path_lower.contains("_mock.")
                    || path_lower.contains("/fixture");

                // For test files, apply stricter placeholder filtering.
                if is_test_file {
                    // Skip if the whole line looks like a mock definition.
                    let line_lower = line.to_lowercase();
                    if line_lower.contains("mock") || line_lower.contains("fake")
                        || line_lower.contains("stub") || line_lower.contains("fixture")
                        || line_lower.contains("dummy")
                    {
                        continue;
                    }
                }

                // False positive: value too short or all-same-chars.
                if matched_value.len() < 8 {
                    continue;
                }
                // Skip values that are just repeated characters.
                let unique_chars = matched_value.chars().collect::<std::collections::HashSet<_>>();
                if unique_chars.len() < 4 {
                    continue;
                }

                findings.push(SecretFinding {
                    severity: "critical".to_string(),
                    description: format!(
                        "Possible {} found on line {}",
                        pattern.name, line_number
                    ),
                    path: path_str.clone(),
                    line_number,
                    secret_type: pattern.name.to_string(),
                });

                // One finding per line — break after first match.
                continue 'lines;
            }
        }

        // Suppress unused variable warning for trimmed (used above for intent clarity).
        let _ = trimmed;
    }

    Some(findings)
}
