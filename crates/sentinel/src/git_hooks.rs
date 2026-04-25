//! Git hooks auditor — detect suspicious scripts in .git/hooks/.

use pyo3::prelude::*;
use std::path::Path;

#[pyclass]
#[derive(Clone)]
pub struct GitHookFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub path: String,
}

const SUSPICIOUS_COMMANDS: &[&str] = &[
    "curl ", "wget ", "nc ", "ncat ", "netcat ",
    "base64", "/dev/tcp/", "python -c", "python3 -c",
    "powershell", "cmd /c", "| sh", "| bash", "| zsh",
    "chmod +x /tmp", "chmod 777",
];

const DANGEROUS_HOOKS: &[&str] = &[
    "pre-commit", "post-commit", "pre-push", "post-checkout",
    "post-merge", "pre-rebase",
];

#[pyfunction]
pub fn scan_git_hooks(scan_paths: Vec<String>) -> Vec<GitHookFinding> {
    let mut findings = Vec::new();
    for base in &scan_paths {
        scan_for_git_dirs(Path::new(base), &mut findings, 3);
    }
    findings
}

fn scan_for_git_dirs(dir: &Path, findings: &mut Vec<GitHookFinding>, depth: u32) {
    if depth == 0 {
        return;
    }
    let git_dir = dir.join(".git");
    if git_dir.is_dir() {
        let hooks_dir = git_dir.join("hooks");
        if hooks_dir.is_dir() {
            check_hooks(&hooks_dir, findings, dir);
        }
    }
    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if path.is_dir() && !name.starts_with('.') && name != "node_modules" && name != "__pycache__" {
            scan_for_git_dirs(&path, findings, depth - 1);
        }
    }
}

fn check_hooks(hooks_dir: &Path, findings: &mut Vec<GitHookFinding>, project_dir: &Path) {
    let entries = match std::fs::read_dir(hooks_dir) {
        Ok(e) => e,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();

        if name.ends_with(".sample") {
            continue;
        }
        if !DANGEROUS_HOOKS.iter().any(|h| name.starts_with(h)) {
            continue;
        }

        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let path_str = path.to_string_lossy().to_string();
        let project = project_dir
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();

        for pattern in SUSPICIOUS_COMMANDS {
            if content.to_lowercase().contains(&pattern.to_lowercase()) {
                findings.push(GitHookFinding {
                    severity: "critical".into(),
                    description: format!(
                        "Git hook '{}' in '{}' contains suspicious command: {}",
                        name, project, pattern.trim()
                    ),
                    path: path_str.clone(),
                });
                break;
            }
        }

        // Download-and-execute pattern
        if (content.contains("curl") || content.contains("wget"))
            && (content.contains("| sh") || content.contains("| bash"))
        {
            findings.push(GitHookFinding {
                severity: "critical".into(),
                description: format!(
                    "Git hook '{name}' in '{project}' downloads and executes code — potential backdoor"
                ),
                path: path_str,
            });
        }
    }
}
