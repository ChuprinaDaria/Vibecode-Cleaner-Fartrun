//! Autostart persistence scanner — shell RC files, systemd user services,
//! XDG autostart entries, and macOS `LaunchAgents`.
//!
//! Looks for: pipe-to-shell, base64 decode, reverse shells, crypto miners,
//! suspicious PATH modifications, and recently created persistence entries.

use pyo3::prelude::*;

/// Suspicious patterns in autostart commands.
const SUSPICIOUS_CMD_PATTERNS: &[(&str, &str, &str)] = &[
    ("curl|bash",      "critical", "Pipe-to-shell in autostart: {}"),
    ("curl|sh",        "critical", "Pipe-to-shell in autostart: {}"),
    ("wget|bash",      "critical", "Pipe-to-shell in autostart: {}"),
    ("wget|sh",        "critical", "Pipe-to-shell in autostart: {}"),
    ("curl -s|",       "critical", "Silent curl piped in autostart: {}"),
    ("base64 -d",      "critical", "Base64 decode in autostart: {}"),
    ("base64 --decode","critical", "Base64 decode in autostart: {}"),
    ("eval $(",        "critical", "Eval in autostart: {}"),
    ("eval \"$(",      "critical", "Eval in autostart: {}"),
    ("python -c",      "high",     "Inline Python in autostart: {}"),
    ("python3 -c",     "high",     "Inline Python in autostart: {}"),
    ("nc -e",          "critical", "Netcat exec in autostart: {}"),
    ("ncat -e",        "critical", "Ncat exec in autostart: {}"),
    ("socat exec",     "critical", "Socat exec in autostart: {}"),
    ("/dev/tcp/",      "critical", "TCP redirect in autostart: {}"),
    ("stratum+tcp://", "critical", "Mining pool URL in autostart: {}"),
    ("stratum+ssl://", "critical", "Mining pool URL in autostart: {}"),
    ("xmrig",          "critical", "Cryptominer in autostart: {}"),
    ("minerd",         "critical", "Cryptominer in autostart: {}"),
    ("/tmp/.",         "high",     "Hidden /tmp path in autostart: {}"),
    ("/dev/shm/",      "high",     "/dev/shm path in autostart: {}"),
];

/// Suspicious PATH additions — /tmp, /dev/shm, /var/tmp prepended to PATH.
const SUSPICIOUS_PATH_DIRS: &[&str] = &["/tmp", "/dev/shm", "/var/tmp"];

#[pyclass]
#[derive(Clone)]
pub struct AutostartFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub source_type: String, // "shell_rc" | "systemd_user" | "xdg_autostart" | "launchd_user"
    #[pyo3(get)]
    pub line_number: u32,
}

#[pymethods]
impl AutostartFinding {
    fn __repr__(&self) -> String {
        format!(
            "AutostartFinding(severity='{}', source_type='{}', path='{}', line={}, desc='{}')",
            self.severity,
            self.source_type,
            self.path,
            self.line_number,
            self.description,
        )
    }
}

/// Scan shell RC files, systemd user services, XDG autostart and `LaunchAgents`
/// for suspicious persistence mechanisms.
#[pyfunction]
pub fn scan_autostart() -> Vec<AutostartFinding> {
    let mut findings = Vec::new();

    scan_shell_rc_files(&mut findings);

    #[cfg(target_os = "linux")]
    {
        scan_systemd_user_services(&mut findings);
        scan_xdg_autostart(&mut findings);
    }

    #[cfg(target_os = "macos")]
    {
        scan_launch_agents(&mut findings);
    }

    findings
}

// ---------------------------------------------------------------------------
// Shell RC files
// ---------------------------------------------------------------------------

fn shell_rc_paths() -> Vec<std::path::PathBuf> {
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return Vec::new(),
    };

    let names = [
        ".bashrc",
        ".bash_profile",
        ".profile",
        ".zshrc",
        ".zprofile",
        ".bash_login",
        ".zlogin",
    ];

    names
        .iter()
        .map(|n| std::path::PathBuf::from(format!("{home}/{n}")))
        .collect()
}

fn scan_shell_rc_files(findings: &mut Vec<AutostartFinding>) {
    for path in shell_rc_paths() {
        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let path_str = path.display().to_string();

        for (line_no, raw_line) in content.lines().enumerate() {
            let line = raw_line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }

            let line_lower = line.to_lowercase();
            let line_number = (line_no + 1) as u32;

            // Check suspicious commands
            if let Some(finding) = match_suspicious_cmd(&line_lower, line, &path_str, "shell_rc", line_number) {
                findings.push(finding);
                continue; // one finding per line is enough
            }

            // Check suspicious PATH additions
            if line_lower.starts_with("export path=") || line_lower.contains(" path=") {
                for dir in SUSPICIOUS_PATH_DIRS {
                    if line_lower.contains(dir) {
                        findings.push(AutostartFinding {
                            severity: "high".to_string(),
                            description: format!(
                                "Suspicious PATH modification adds {}: {}",
                                dir,
                                truncate(line, 150),
                            ),
                            path: path_str.clone(),
                            source_type: "shell_rc".to_string(),
                            line_number,
                        });
                        break;
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Linux: systemd user services
// ---------------------------------------------------------------------------

#[cfg(target_os = "linux")]
fn scan_systemd_user_services(findings: &mut Vec<AutostartFinding>) {
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return,
    };

    let dir = format!("{home}/.config/systemd/user");
    let entries = match std::fs::read_dir(&dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().is_none_or(|e| e != "service") {
            continue;
        }

        let path_str = path.display().to_string();

        // Flag recently created service files (<24h)
        if let Ok(meta) = std::fs::metadata(&path) {
            if let Ok(created) = meta.modified() {
                if let Ok(age) = std::time::SystemTime::now().duration_since(created) {
                    if age.as_secs() < 86_400 {
                        findings.push(AutostartFinding {
                            severity: "medium".to_string(),
                            description: format!(
                                "Systemd user service created less than 24h ago: {}",
                                path.file_name().unwrap_or_default().to_string_lossy(),
                            ),
                            path: path_str.clone(),
                            source_type: "systemd_user".to_string(),
                            line_number: 0,
                        });
                    }
                }
            }
        }

        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        for (line_no, raw_line) in content.lines().enumerate() {
            let line = raw_line.trim();
            let line_lower = line.to_lowercase();
            let line_number = (line_no + 1) as u32;

            if !line_lower.starts_with("execstart=") {
                continue;
            }

            let cmd = &line["ExecStart=".len()..];
            let cmd_lower = cmd.to_lowercase();

            // Flag ExecStart from temp dirs
            for dir in &["/tmp", "/dev/shm", "/var/tmp"] {
                if cmd_lower.starts_with(dir) || cmd_lower.contains(&format!(" {dir}")) {
                    findings.push(AutostartFinding {
                        severity: "critical".to_string(),
                        description: format!(
                            "Systemd user service ExecStart from temp directory: {}",
                            truncate(cmd, 150),
                        ),
                        path: path_str.clone(),
                        source_type: "systemd_user".to_string(),
                        line_number,
                    });
                    break;
                }
            }

            // Check suspicious commands
            if let Some(finding) = match_suspicious_cmd(&cmd_lower, cmd, &path_str, "systemd_user", line_number) {
                findings.push(finding);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Linux: XDG autostart
// ---------------------------------------------------------------------------

#[cfg(target_os = "linux")]
fn scan_xdg_autostart(findings: &mut Vec<AutostartFinding>) {
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return,
    };

    let dirs = [
        format!("{home}/.config/autostart"),
        format!("{home}/.local/share/applications"),
    ];

    for dir in &dirs {
        let entries = match std::fs::read_dir(dir) {
            Ok(e) => e,
            Err(_) => continue,
        };

        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().is_none_or(|e| e != "desktop") {
                continue;
            }

            let path_str = path.display().to_string();
            let content = match std::fs::read_to_string(&path) {
                Ok(c) => c,
                Err(_) => continue,
            };

            // Collect key values in one pass for combo checks
            let mut hidden = false;
            let mut no_display = false;
            let mut exec_line: Option<(String, u32)> = None;

            for (line_no, raw_line) in content.lines().enumerate() {
                let line = raw_line.trim();
                let line_lower = line.to_lowercase();
                let line_number = (line_no + 1) as u32;

                if line_lower == "hidden=true" {
                    hidden = true;
                }
                if line_lower == "nodisplay=true" {
                    no_display = true;
                }
                // Match only "Exec=" key, not ExecStop= / ExecStartPre= etc.
                if line_lower.starts_with("exec=") && !line_lower.starts_with("execstart") && !line_lower.starts_with("execstop") {
                    let cmd = &line["Exec=".len()..];
                    exec_line = Some((cmd.to_string(), line_number));

                    let cmd_lower = cmd.to_lowercase();

                    // Exec from temp dirs
                    for dir in &["/tmp", "/dev/shm", "/var/tmp"] {
                        if cmd_lower.starts_with(dir) {
                            findings.push(AutostartFinding {
                                severity: "critical".to_string(),
                                description: format!(
                                    "XDG autostart Exec from temp directory: {}",
                                    truncate(cmd, 150),
                                ),
                                path: path_str.clone(),
                                source_type: "xdg_autostart".to_string(),
                                line_number,
                            });
                            break;
                        }
                    }

                    // Check suspicious commands
                    if let Some(finding) = match_suspicious_cmd(&cmd_lower, cmd, &path_str, "xdg_autostart", line_number) {
                        findings.push(finding);
                    }
                }
            }

            // Hidden=true + NoDisplay=true combo — classic hiding technique
            if hidden && no_display {
                let line_number = exec_line.as_ref().map_or(0, |(_, ln)| *ln);
                findings.push(AutostartFinding {
                    severity: "high".to_string(),
                    description: format!(
                        "XDG autostart entry with Hidden=true and NoDisplay=true (hidden from all views): {}",
                        path.file_name().unwrap_or_default().to_string_lossy(),
                    ),
                    path: path_str.clone(),
                    source_type: "xdg_autostart".to_string(),
                    line_number,
                });
            }
        }
    }
}

// ---------------------------------------------------------------------------
// macOS: LaunchAgents
// ---------------------------------------------------------------------------

#[cfg(target_os = "macos")]
fn scan_launch_agents(findings: &mut Vec<AutostartFinding>) {
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return,
    };

    let dirs = [
        format!("{}/Library/LaunchAgents", home),
    ];

    for dir in &dirs {
        let entries = match std::fs::read_dir(dir) {
            Ok(e) => e,
            Err(_) => continue,
        };

        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().map(|e| e != "plist").unwrap_or(true) {
                continue;
            }

            let path_str = path.display().to_string();

            // Flag recently created plist files (<24h)
            if let Ok(meta) = std::fs::metadata(&path) {
                if let Ok(modified) = meta.modified() {
                    if let Ok(age) = std::time::SystemTime::now().duration_since(modified) {
                        if age.as_secs() < 86_400 {
                            findings.push(AutostartFinding {
                                severity: "medium".to_string(),
                                description: format!(
                                    "LaunchAgent plist created/modified less than 24h ago: {}",
                                    path.file_name().unwrap_or_default().to_string_lossy(),
                                ),
                                path: path_str.clone(),
                                source_type: "launchd_user".to_string(),
                                line_number: 0,
                            });
                        }
                    }
                }
            }

            let content = match std::fs::read_to_string(&path) {
                Ok(c) => c,
                Err(_) => continue,
            };

            let content_lower = content.to_lowercase();

            // Check suspicious patterns in the whole plist (includes ProgramArguments strings)
            if let Some(finding) = match_suspicious_cmd(&content_lower, &content, &path_str, "launchd_user", 0) {
                findings.push(finding);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn match_suspicious_cmd(
    cmd_lower: &str,
    cmd_original: &str,
    path: &str,
    source_type: &str,
    line_number: u32,
) -> Option<AutostartFinding> {
    for &(pattern, severity, desc_template) in SUSPICIOUS_CMD_PATTERNS {
        if cmd_lower.contains(pattern) {
            return Some(AutostartFinding {
                severity: severity.to_string(),
                description: desc_template.replace("{}", &truncate(cmd_original, 150)),
                path: path.to_string(),
                source_type: source_type.to_string(),
                line_number,
            });
        }
    }
    None
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        format!("{}…", &s[..max])
    }
}
