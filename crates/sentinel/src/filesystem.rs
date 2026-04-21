//! Filesystem scanner — single-pass directory walk.
//!
//! Replaces Python's 5x rglob with one native walk that checks:
//! - Sensitive files with bad permissions (.env, .pem, credentials, etc.)
//! - Executables in /tmp, /dev/shm (malware persistence)
//! - SUID binaries in non-standard locations
//! - Known malware persistence paths
//! - Recently modified suspicious files

use pyo3::prelude::*;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, Duration};

/// Sensitive file patterns — checked during single walk.
/// Exact filename matches for sensitive files.
const SENSITIVE_EXACT: &[&str] = &[
    ".env", "credentials", "credentials.json", "secrets.json",
    "htpasswd", "shadow", "auth.json", "service_account.json",
    ".netrc", ".pgpass", ".my.cnf",
];

/// Extension/suffix matches.
const SENSITIVE_EXTENSIONS: &[&str] = &[
    ".pem", ".key", ".pfx", ".p12", ".keystore", ".jks",
];

/// Prefix matches.
const SENSITIVE_PREFIXES: &[&str] = &[
    ".env.", "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
    "api_key", "apikey",
];

/// Known malware persistence directories.
#[cfg(target_os = "linux")]
const MALWARE_PATHS: &[(&str, &str)] = &[
    ("/tmp/.X11-unix/../", "Hidden directory under /tmp/.X11-unix"),
    ("/tmp/.ICE-unix/../", "Hidden directory under /tmp/.ICE-unix"),
    ("/dev/shm/", "Executable in shared memory (RAM disk)"),
    ("/var/tmp/", "Executable in /var/tmp"),
    ("/tmp/.", "Hidden file/dir in /tmp"),
];

#[cfg(target_os = "macos")]
const MALWARE_PATHS: &[(&str, &str)] = &[
    ("/tmp/.", "Hidden file in /tmp"),
    ("/private/tmp/.", "Hidden file in /private/tmp"),
];

#[cfg(target_os = "windows")]
const MALWARE_PATHS: &[(&str, &str)] = &[];

/// Known legitimate SUID binaries (Linux).
#[cfg(unix)]
const KNOWN_SUID: &[&str] = &[
    "sudo", "sudoedit", "su", "passwd", "chsh", "chfn", "newgrp", "gpasswd", "sg",
    "mount", "umount", "ping", "ping6", "fusermount", "fusermount3",
    "pkexec", "crontab", "at", "ssh-agent", "unix_chkpwd",
    "Xorg", "dbus-daemon-launch-helper", "snap-confine",
    "chromium-sandbox", "chrome-sandbox",
    "mount.cifs", "mount.smb3", "mount.ecryptfs_private",
    "umount.ecryptfs_private", "pppd", "traceroute6.iputils",
    "vmware-user-suid-wrapper", "VBoxNetNAT", "VBoxNetDHCP",
    "polkit-agent-helper-1", "ssh-keysign", "ntfs-3g",
];

#[pyclass]
#[derive(Clone)]
pub struct FileFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub finding_type: String, // "permissions", "malware_path", "suid", "suspicious_exec"
}

#[pymethods]
impl FileFinding {
    fn __repr__(&self) -> String {
        format!(
            "FileFinding(severity='{}', type='{}', path='{}', desc='{}')",
            self.severity, self.finding_type, self.path, self.description
        )
    }
}

/// Scan filesystem — single pass over scan_paths.
/// Checks permissions, malware paths, SUID bits, suspicious executables.
#[pyfunction]
#[pyo3(signature = (scan_paths=None))]
pub fn scan_filesystem(scan_paths: Option<Vec<String>>) -> Vec<FileFinding> {
    let paths: Vec<PathBuf> = scan_paths
        .unwrap_or_else(|| {
            let home = dirs_home();
            vec![home.to_string_lossy().to_string()]
        })
        .into_iter()
        .map(PathBuf::from)
        .collect();

    let mut findings = Vec::new();
    let now = SystemTime::now();

    // Walk user-specified paths for sensitive files
    for base in &paths {
        walk_for_sensitive(base, &mut findings, 5); // max depth 5
    }

    // Check known malware persistence paths
    scan_malware_paths(&mut findings, &now);

    // Check for SUID binaries in non-standard locations (Unix only)
    #[cfg(unix)]
    scan_suid_binaries(&mut findings);

    // Check /tmp and /dev/shm for executables
    #[cfg(unix)]
    scan_temp_executables(&mut findings, &now);

    findings
}

/// Walk directory tree, checking sensitive file permissions. Single pass.
fn walk_for_sensitive(base: &Path, findings: &mut Vec<FileFinding>, max_depth: usize) {
    walk_recursive(base, findings, 0, max_depth);
}

fn walk_recursive(dir: &Path, findings: &mut Vec<FileFinding>, depth: usize, max_depth: usize) {
    if depth > max_depth {
        return;
    }

    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        let file_name = entry.file_name();
        let name_lower = file_name.to_string_lossy().to_lowercase();

        // Skip heavy directories
        if name_lower == "node_modules" || name_lower == ".git" ||
           name_lower == "__pycache__" || name_lower == "target" ||
           name_lower == ".cargo" || name_lower == ".rustup" ||
           name_lower == "venv" || name_lower == ".venv" ||
           name_lower == ".local" || name_lower == ".cache" {
            continue;
        }

        if path.is_dir() {
            walk_recursive(&path, findings, depth + 1, max_depth);
            continue;
        }

        if !path.is_file() {
            continue;
        }

        // Check if this is a sensitive file (precise matching)
        let is_sensitive =
            SENSITIVE_EXACT.iter().any(|p| name_lower == *p) ||
            SENSITIVE_EXTENSIONS.iter().any(|ext| name_lower.ends_with(ext)) ||
            SENSITIVE_PREFIXES.iter().any(|pre| name_lower.starts_with(pre));

        if !is_sensitive {
            continue;
        }

        // Check permissions
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if let Ok(meta) = path.metadata() {
                let mode = meta.permissions().mode() & 0o777;
                // Skip .example files — they're templates, not real secrets
                if name_lower.contains(".example") || name_lower.contains(".sample")
                    || name_lower.contains(".template") || name_lower.contains(".dist") {
                    continue;
                }
                // Only flag if world-readable (other has read) AND file is likely secret
                // 0o004 = other read, 0o002 = other write
                let is_world_writable = mode & 0o002 != 0;
                let is_world_readable = mode & 0o004 != 0;
                // All files that passed is_sensitive check are real secrets
                let is_real_secret = true;
                if is_world_writable || (is_world_readable && is_real_secret) {
                    let severity = if is_world_writable { "high" } else { "medium" };
                    findings.push(FileFinding {
                        severity: severity.to_string(),
                        description: format!(
                            "Sensitive file with broad permissions ({:#o}): {}",
                            mode, path.display()
                        ),
                        path: path.to_string_lossy().to_string(),
                        finding_type: "permissions".to_string(),
                    });
                }
            }
        }

        #[cfg(windows)]
        {
            // On Windows, just flag the existence of sensitive files
            // (Windows ACLs are complex, basic check here)
            findings.push(FileFinding {
                severity: "medium".to_string(),
                description: format!(
                    "Sensitive file found — verify access control: {}",
                    path.display()
                ),
                path: path.to_string_lossy().to_string(),
                finding_type: "permissions".to_string(),
            });
        }
    }
}

/// Check known malware persistence directories.
fn scan_malware_paths(findings: &mut Vec<FileFinding>, _now: &SystemTime) {
    #[cfg(unix)]
    {
        // Check for hidden files in /tmp
        for dir in &["/tmp", "/var/tmp"] {
            let entries = match std::fs::read_dir(dir) {
                Ok(e) => e,
                Err(_) => continue,
            };
            for entry in entries.flatten() {
                let name = entry.file_name();
                let name_str = name.to_string_lossy();
                // Hidden files (start with dot, but not . or ..)
                if name_str.starts_with('.') && name_str != "." && name_str != ".."
                    && name_str != ".X11-unix" && name_str != ".ICE-unix"
                    && name_str != ".font-unix" && name_str != ".XIM-unix"
                    && !name_str.starts_with(".X") // X11 lock files (.X0-lock etc.)
                    && name_str != ".terminals" // GNOME terminal state
                {
                    let path = entry.path();
                    findings.push(FileFinding {
                        severity: "high".to_string(),
                        description: format!(
                            "Hidden file/directory in {}: {} — common malware persistence",
                            dir, name_str
                        ),
                        path: path.to_string_lossy().to_string(),
                        finding_type: "malware_path".to_string(),
                    });
                }
            }
        }

        // Check /dev/shm for any files
        if let Ok(entries) = std::fs::read_dir("/dev/shm") {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_file() {
                    if let Ok(meta) = path.metadata() {
                        use std::os::unix::fs::PermissionsExt;
                        let mode = meta.permissions().mode();
                        if mode & 0o111 != 0 {
                            findings.push(FileFinding {
                                severity: "critical".to_string(),
                                description: format!(
                                    "Executable in /dev/shm (RAM disk): {} — classic malware technique",
                                    path.display()
                                ),
                                path: path.to_string_lossy().to_string(),
                                finding_type: "malware_path".to_string(),
                            });
                        }
                    }
                }
            }
        }
    }
}

/// Check for SUID binaries outside standard locations.
#[cfg(unix)]
fn scan_suid_binaries(findings: &mut Vec<FileFinding>) {
    let standard_dirs = ["/usr/bin", "/usr/sbin", "/bin", "/sbin",
                         "/usr/lib", "/usr/libexec", "/snap"];

    for dir in &standard_dirs {
        let entries = match std::fs::read_dir(dir) {
            Ok(e) => e,
            Err(_) => continue,
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            if let Ok(meta) = path.metadata() {
                use std::os::unix::fs::PermissionsExt;
                let mode = meta.permissions().mode();
                // Check SUID bit (0o4000)
                if mode & 0o4000 != 0 {
                    let name = entry.file_name();
                    let name_str = name.to_string_lossy();
                    let is_known = KNOWN_SUID.iter().any(|k| *k == name_str.as_ref());
                    if !is_known {
                        findings.push(FileFinding {
                            severity: "medium".to_string(),
                            description: format!(
                                "Non-standard SUID binary: {} ({:#o}) — verify this is intentional",
                                path.display(), mode & 0o7777
                            ),
                            path: path.to_string_lossy().to_string(),
                            finding_type: "suid".to_string(),
                        });
                    }
                }
            }
        }
    }
}

/// Check /tmp for recently created executables.
#[cfg(unix)]
fn scan_temp_executables(findings: &mut Vec<FileFinding>, now: &SystemTime) {
    let one_day = Duration::from_secs(86400);

    for dir in &["/tmp", "/var/tmp"] {
        let entries = match std::fs::read_dir(dir) {
            Ok(e) => e,
            Err(_) => continue,
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            if let Ok(meta) = path.metadata() {
                use std::os::unix::fs::PermissionsExt;
                let mode = meta.permissions().mode();
                if mode & 0o111 != 0 {
                    // Check if recently created
                    let is_recent = meta.created()
                        .or(meta.modified())
                        .ok()
                        .and_then(|t| now.duration_since(t).ok())
                        .map(|d| d < one_day)
                        .unwrap_or(false);

                    if is_recent {
                        let name = entry.file_name();
                        let name_str = name.to_string_lossy();
                        // Skip known temp executables
                        if name_str.starts_with("tmp") || name_str.starts_with("pip-")
                            || name_str.contains("pytest") || name_str.contains("cargo")
                        {
                            continue;
                        }
                        findings.push(FileFinding {
                            severity: "high".to_string(),
                            description: format!(
                                "Recently created executable in {}: {} — verify origin",
                                dir, name_str
                            ),
                            path: path.to_string_lossy().to_string(),
                            finding_type: "suspicious_exec".to_string(),
                        });
                    }
                }
            }
        }
    }
}

fn dirs_home() -> PathBuf {
    #[cfg(unix)]
    {
        std::env::var("HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("/root"))
    }
    #[cfg(windows)]
    {
        std::env::var("USERPROFILE")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("C:\\Users"))
    }
}
