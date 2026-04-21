//! Environment variable leak detection — scan process environ for exposed secrets.

use pyo3::prelude::*;
use regex::Regex;
use std::sync::LazyLock;

#[pyclass]
#[derive(Clone)]
pub struct EnvLeakFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub process: String,
}

static SECRET_PATTERNS: LazyLock<Vec<(&'static str, Regex)>> = LazyLock::new(|| {
    vec![
        ("AWS Access Key", Regex::new(r"AKIA[0-9A-Z]{16}").unwrap()),
        ("GitHub Token", Regex::new(r"gh[pousr]_[A-Za-z0-9_]{36,}").unwrap()),
        ("Anthropic API Key", Regex::new(r"sk-ant-[A-Za-z0-9_\-]{40,}").unwrap()),
        ("OpenAI API Key", Regex::new(r"sk-[A-Za-z0-9]{40,}").unwrap()),
        ("Stripe Key", Regex::new(r"[sr]k_live_[A-Za-z0-9]{20,}").unwrap()),
        ("Slack Token", Regex::new(r"xox[bporas]-[A-Za-z0-9\-]{10,}").unwrap()),
        ("Database URL with creds", Regex::new(r"(postgres|mysql|mongodb)://[^:]+:[^@]+@").unwrap()),
    ]
});

#[pyfunction]
pub fn scan_env_leaks() -> Vec<EnvLeakFinding> {
    let mut findings = Vec::new();

    #[cfg(target_os = "linux")]
    {
        if let Ok(entries) = std::fs::read_dir("/proc") {
            for entry in entries.flatten() {
                let pid = entry.file_name().to_string_lossy().to_string();
                if !pid.chars().all(|c| c.is_ascii_digit()) {
                    continue;
                }

                let environ_path = entry.path().join("environ");
                let environ = match std::fs::read_to_string(&environ_path) {
                    Ok(e) => e,
                    Err(_) => continue,
                };

                let cmdline = std::fs::read_to_string(entry.path().join("cmdline"))
                    .unwrap_or_default()
                    .replace('\0', " ");
                let cmdline_short: String = cmdline.chars().take(80).collect();

                for (name, pattern) in SECRET_PATTERNS.iter() {
                    if pattern.is_match(&environ) {
                        findings.push(EnvLeakFinding {
                            severity: "high".into(),
                            description: format!(
                                "{} found in environment of PID {} ({})", name, pid, cmdline_short
                            ),
                            process: format!("pid:{}", pid),
                        });
                        break;
                    }
                }
            }
        }
    }

    // macOS and Windows: check current process environment only
    #[cfg(not(target_os = "linux"))]
    {
        for (key, value) in std::env::vars() {
            let combined = format!("{}={}", key, value);
            for (name, pattern) in SECRET_PATTERNS.iter() {
                if pattern.is_match(&combined) {
                    findings.push(EnvLeakFinding {
                        severity: "high".into(),
                        description: format!("{} exposed in environment variable {}", name, key),
                        process: "current".into(),
                    });
                    break;
                }
            }
        }
    }

    findings
}
