//! Supply chain scanner — verify lock file integrity, detect tampered dependencies.

use pyo3::prelude::*;
use std::path::Path;

#[pyclass]
#[derive(Clone)]
pub struct SupplyChainFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub path: String,
}

const SUSPICIOUS_URLS: &[&str] = &[
    "pastebin.com", "bit.ly", "tinyurl.com", "ngrok.io",
    "serveo.net", "localhost:", "127.0.0.1", "0.0.0.0",
];

// Patterns indicating malicious install scripts in lock files
const SUSPICIOUS_INSTALL_SCRIPTS: &[&str] = &[
    "curl ", "wget ", "powershell ",
    "child_process", "net.connect", "/dev/tcp/",
    "base64 -d", "base64 --decode",
];

#[pyfunction]
pub fn scan_supply_chain(scan_paths: Vec<String>) -> Vec<SupplyChainFinding> {
    let mut findings = Vec::new();
    for base in &scan_paths {
        let base_path = Path::new(base);
        if base_path.is_dir() {
            scan_dir(base_path, &mut findings, 4);
        }
    }
    findings
}

fn scan_dir(dir: &Path, findings: &mut Vec<SupplyChainFinding>, depth: u32) {
    if depth == 0 {
        return;
    }
    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if name == "node_modules" || name == ".git" || name == "__pycache__" || name.starts_with('.') {
            continue;
        }
        if path.is_dir() {
            scan_dir(&path, findings, depth - 1);
            continue;
        }
        match name.as_str() {
            "package-lock.json" | "yarn.lock" | "pnpm-lock.yaml" => {
                check_js_lock(&path, findings);
            }
            "Pipfile.lock" | "poetry.lock" => {
                check_python_lock(&path, findings);
            }
            _ => {}
        }
    }
}

fn check_js_lock(path: &Path, findings: &mut Vec<SupplyChainFinding>) {
    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return,
    };
    let path_str = path.to_string_lossy().to_string();

    for url_pattern in SUSPICIOUS_URLS {
        if content.contains(url_pattern) {
            findings.push(SupplyChainFinding {
                severity: "high".into(),
                description: format!(
                    "Lock file contains suspicious URL '{url_pattern}' — possible dependency hijack"
                ),
                path: path_str.clone(),
            });
        }
    }
    for pattern in SUSPICIOUS_INSTALL_SCRIPTS {
        if content.contains(pattern) {
            findings.push(SupplyChainFinding {
                severity: "critical".into(),
                description: format!(
                    "Lock file references suspicious command '{pattern}' — possible supply chain attack"
                ),
                path: path_str.clone(),
            });
        }
    }
    if content.contains("\"resolved\": \"http://") {
        findings.push(SupplyChainFinding {
            severity: "high".into(),
            description: "Lock file has HTTP (not HTTPS) resolved URLs — vulnerable to MITM".into(),
            path: path_str,
        });
    }
}

fn check_python_lock(path: &Path, findings: &mut Vec<SupplyChainFinding>) {
    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return,
    };
    let path_str = path.to_string_lossy().to_string();

    for url_pattern in SUSPICIOUS_URLS {
        if content.contains(url_pattern) {
            findings.push(SupplyChainFinding {
                severity: "high".into(),
                description: format!(
                    "Python lock file contains suspicious URL '{url_pattern}' — check dependency sources"
                ),
                path: path_str.clone(),
            });
        }
    }
}
