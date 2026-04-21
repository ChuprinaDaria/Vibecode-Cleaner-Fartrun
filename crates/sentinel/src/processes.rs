//! Process scanner — detects cryptominers, reverse shells, suspicious commands.
//!
//! Cross-platform via sysinfo crate (Linux, macOS, Windows).

use pyo3::prelude::*;
use sysinfo::System;

/// Known suspicious process patterns.
/// Each entry: (pattern, severity, description_template)
const SUSPICIOUS_NAMES: &[(&str, &str, &str)] = &[
    ("xmrig", "critical", "Cryptominer detected: {}"),
    ("minerd", "critical", "Cryptominer detected: {}"),
    ("cpuminer", "critical", "Cryptominer detected: {}"),
    ("ethminer", "critical", "Cryptominer detected: {}"),
    ("cgminer", "critical", "Cryptominer detected: {}"),
    ("bfgminer", "critical", "Cryptominer detected: {}"),
    ("nbminer", "critical", "Cryptominer detected: {}"),
    ("t-rex", "critical", "Cryptominer detected: {}"),
    ("phoenixminer", "critical", "Cryptominer detected: {}"),
    ("lolminer", "critical", "Cryptominer detected: {}"),
    ("kswapd0", "critical", "Possible hidden miner (fake kernel thread): {}"),

    // Tunneling tools
    ("chisel", "high", "Tunneling tool detected: {}"),
    ("ngrok", "high", "Tunnel/expose tool detected: {}"),
    ("cloudflared", "high", "Cloudflare tunnel detected: {}"),
    ("frpc", "high", "Fast reverse proxy client detected: {}"),
    ("bore", "high", "TCP tunnel detected: {}"),

    // Brute force tools
    ("hydra", "critical", "Password brute force tool: {}"),
    ("john", "high", "Password cracker (John the Ripper): {}"),
    ("hashcat", "high", "Hash cracking tool: {}"),
    ("medusa", "critical", "Parallel brute force tool: {}"),

    // Recon/exploit
    ("nmap", "high", "Port scanner detected: {}"),
    ("masscan", "high", "Mass port scanner detected: {}"),
    ("sqlmap", "critical", "SQL injection tool: {}"),
    ("msfconsole", "critical", "Metasploit framework: {}"),
    ("msfvenom", "critical", "Metasploit payload generator: {}"),
];

/// Suspicious command-line argument patterns.
const SUSPICIOUS_ARGS: &[(&str, &str, &str)] = &[
    // Reverse shells
    ("bash -i >& /dev/tcp/", "critical", "Reverse shell (bash TCP): {}"),
    ("bash -i >& /dev/udp/", "critical", "Reverse shell (bash UDP): {}"),
    ("/bin/sh -i", "critical", "Interactive shell spawned: {}"),
    ("nc -e /bin/", "critical", "Netcat reverse shell: {}"),
    ("nc -l", "high", "Netcat listener — possible backdoor: {}"),
    ("ncat -e", "critical", "Ncat reverse shell: {}"),
    ("socat exec:", "critical", "Socat reverse shell: {}"),
    ("python -c 'import socket", "critical", "Python reverse shell: {}"),
    ("python3 -c 'import socket", "critical", "Python reverse shell: {}"),
    ("perl -e 'use Socket", "critical", "Perl reverse shell: {}"),
    ("ruby -rsocket", "critical", "Ruby reverse shell: {}"),

    // Pipe-to-shell (curl | bash etc.)
    ("curl|bash", "critical", "Pipe-to-shell detected (curl|bash): {}"),
    ("curl|sh", "critical", "Pipe-to-shell detected (curl|sh): {}"),
    ("wget|bash", "critical", "Pipe-to-shell detected (wget|bash): {}"),
    ("wget|sh", "critical", "Pipe-to-shell detected (wget|sh): {}"),
    ("curl -s|bash", "critical", "Pipe-to-shell detected: {}"),

    // Suspicious data manipulation
    ("base64 -d|bash", "critical", "Base64 decode piped to shell: {}"),
    ("base64 -d|sh", "critical", "Base64 decode piped to shell: {}"),
    ("base64 --decode|bash", "critical", "Base64 decode piped to shell: {}"),
    ("eval $(curl", "critical", "Remote code execution via eval+curl: {}"),
    ("eval $(wget", "critical", "Remote code execution via eval+wget: {}"),

    // Privilege escalation tools
    ("mimikatz", "critical", "Credential dumping tool (mimikatz): {}"),
    ("lazagne", "critical", "Password recovery tool (lazagne): {}"),
    ("linpeas", "high", "Linux privilege escalation scanner: {}"),
    ("winpeas", "high", "Windows privilege escalation scanner: {}"),
    ("pspy", "high", "Process snooping tool: {}"),

    // Crypto/mining args
    ("--coin=", "high", "Mining-related argument: {}"),
    ("stratum+tcp://", "critical", "Mining pool connection: {}"),
    ("stratum+ssl://", "critical", "Mining pool connection: {}"),
    ("-o pool.", "high", "Possible mining pool argument: {}"),
];

/// Processes owned by unexpected users (Linux/macOS).
const SYSTEM_USERS: &[&str] = &[
    "root", "daemon", "bin", "sys", "sync", "games", "man", "lp",
    "mail", "news", "uucp", "proxy", "www-data", "backup", "list",
    "irc", "nobody", "systemd-network", "systemd-resolve",
    "messagebus", "syslog", "_apt", "avahi", "colord", "cups",
    "gdm", "gnome-initial-setup", "hplip", "kernoops", "lightdm",
    "polkitd", "pulse", "rtkit", "saned", "speech-dispatcher",
    "sshd", "statd", "whoopsie", "dnsmasq", "nm-openconnect",
    "nm-openvpn", "geoclue", "sssd", "snap_daemon",
    "fwupd-refresh", "tss",
];

#[pyclass]
#[derive(Clone)]
pub struct ProcessFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub pid: u32,
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub cmdline: String,
    #[pyo3(get)]
    pub user: String,
}

#[pymethods]
impl ProcessFinding {
    fn __repr__(&self) -> String {
        format!(
            "ProcessFinding(severity='{}', pid={}, name='{}', desc='{}')",
            self.severity, self.pid, self.name, self.description
        )
    }
}

/// Scan all running processes for suspicious activity.
#[pyfunction]
pub fn scan_processes() -> Vec<ProcessFinding> {
    let mut sys = System::new();
    sys.refresh_processes(sysinfo::ProcessesToUpdate::All, true);

    let mut findings = Vec::new();
    let current_user = get_current_user();

    for (pid, process) in sys.processes() {
        let name = process.name().to_string_lossy().to_lowercase();
        let cmd_parts: Vec<String> = process.cmd().iter()
            .map(|s| s.to_string_lossy().to_string())
            .collect();
        let cmdline = cmd_parts.join(" ").to_lowercase();
        let user = process.user_id()
            .map(|u| u.to_string())
            .unwrap_or_default();
        let pid_u32 = pid.as_u32();

        // Skip kernel threads (no cmdline, low PID on Linux)
        if cmdline.is_empty() && pid_u32 < 1000 {
            continue;
        }

        // Check process name against known malware
        for &(pattern, severity, desc_template) in SUSPICIOUS_NAMES {
            if name.contains(pattern) && !cmdline.is_empty() {
                findings.push(ProcessFinding {
                    severity: severity.to_string(),
                    description: desc_template.replace("{}", &format!(
                        "{} (PID {}, user: {})", name, pid_u32, user
                    )),
                    pid: pid_u32,
                    name: name.clone(),
                    cmdline: truncate(&cmdline, 200),
                    user: user.clone(),
                });
                break;
            }
        }

        // Check command-line arguments
        for &(pattern, severity, desc_template) in SUSPICIOUS_ARGS {
            if cmdline.contains(pattern) {
                findings.push(ProcessFinding {
                    severity: severity.to_string(),
                    description: desc_template.replace("{}", &format!(
                        "PID {} ({})", pid_u32, truncate(&cmdline, 120)
                    )),
                    pid: pid_u32,
                    name: name.clone(),
                    cmdline: truncate(&cmdline, 200),
                    user: user.clone(),
                });
                break;
            }
        }

        // High CPU usage without clear purpose (possible cryptominer)
        let cpu = process.cpu_usage();
        if cpu > 50.0 {
            let run_time = process.run_time();
            // Running > 60s at elevated CPU — suspicious
            if run_time > 60 {
                // Skip known heavy processes
                let known_heavy = [
                    "cc1", "cc1plus", "rustc", "cargo", "gcc", "g++", "clang",
                    "node", "python", "java", "javac", "webpack", "esbuild",
                    "ffmpeg", "blender", "make", "ninja", "cmake",
                    "apt", "dpkg", "snap", "flatpak", "pip",
                    "xorg", "gnome-shell", "kwin", "firefox", "chrome",
                    "chromium", "code", "electron", "vscode",
                ];
                let is_known = known_heavy.iter().any(|k| name.contains(k));
                if !is_known {
                    let (severity, label) = if cpu > 90.0 {
                        ("high", "possible cryptominer")
                    } else {
                        ("medium", "unexpectedly high CPU usage")
                    };
                    findings.push(ProcessFinding {
                        severity: severity.to_string(),
                        description: format!(
                            "Process '{}' (PID {}) using {:.0}% CPU for {}s — {}",
                            name, pid_u32, cpu, run_time, label
                        ),
                        pid: pid_u32,
                        name: name.clone(),
                        cmdline: truncate(&cmdline, 200),
                        user: user.clone(),
                    });
                }
            }
        }

        // Process running from temp directory (suspicious execution location)
        if let Some(exe_path) = process.exe() {
            let exe_str = exe_path.to_string_lossy();
            let suspicious_dirs = ["/tmp/", "/dev/shm/", "/var/tmp/"];
            if suspicious_dirs.iter().any(|d| exe_str.starts_with(d)) {
                findings.push(ProcessFinding {
                    severity: "critical".to_string(),
                    description: format!(
                        "Process '{}' (PID {}) executing from temp directory: {}",
                        name, pid_u32, exe_str
                    ),
                    pid: pid_u32,
                    name: name.clone(),
                    cmdline: truncate(&cmdline, 200),
                    user: user.clone(),
                });
            } else {
                // Process masquerading: name doesn't match binary and binary is from unusual location
                let binary_name = exe_path
                    .file_name()
                    .map(|f| f.to_string_lossy().to_lowercase())
                    .unwrap_or_default();
                let unusual_location = !exe_str.starts_with("/usr/")
                    && !exe_str.starts_with("/bin/")
                    && !exe_str.starts_with("/sbin/")
                    && !exe_str.starts_with("/snap/")
                    && !exe_str.starts_with("/opt/")
                    && !exe_str.starts_with("/lib/")
                    && !exe_str.contains("/nix/store/");
                if unusual_location && !binary_name.is_empty() && !name.is_empty()
                    && !binary_name.contains(&name[..]) && !name.contains(&binary_name[..])
                {
                    findings.push(ProcessFinding {
                        severity: "high".to_string(),
                        description: format!(
                            "Process masquerading: name '{}' doesn't match binary '{}' (PID {}, path: {})",
                            name, binary_name, pid_u32, exe_str
                        ),
                        pid: pid_u32,
                        name: name.clone(),
                        cmdline: truncate(&cmdline, 200),
                        user: user.clone(),
                    });
                }
            }
        }

        // Process from unexpected user (not root, not current user, not system)
        if !user.is_empty() && user != "root" && !is_same_user(&user, &current_user) {
            let is_system = SYSTEM_USERS.iter().any(|&su| user == su);
            if !is_system && !name.is_empty() {
                // Only flag if process has network or suspicious activity
                // (too noisy to flag all foreign-user processes)
                if cmdline.contains("listen") || cmdline.contains("bind") ||
                   cmdline.contains("server") || cmdline.contains("-p ") {
                    findings.push(ProcessFinding {
                        severity: "medium".to_string(),
                        description: format!(
                            "Process '{}' (PID {}) running as unexpected user '{}' with network args",
                            name, pid_u32, user
                        ),
                        pid: pid_u32,
                        name: name.clone(),
                        cmdline: truncate(&cmdline, 200),
                        user: user.clone(),
                    });
                }
            }
        }
    }

    findings
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        format!("{}…", &s[..max])
    }
}

fn get_current_user() -> String {
    #[cfg(unix)]
    {
        std::env::var("USER").unwrap_or_default()
    }
    #[cfg(windows)]
    {
        std::env::var("USERNAME").unwrap_or_default()
    }
}

fn is_same_user(uid_str: &str, current_user: &str) -> bool {
    // On Linux, sysinfo gives UID as number; compare with current user name heuristically
    if uid_str == current_user {
        return true;
    }
    // Try to match UID to current user's UID
    #[cfg(unix)]
    {
        if let Ok(uid) = uid_str.parse::<u32>() {
            unsafe {
                let pw = libc::getpwnam(
                    std::ffi::CString::new(current_user).unwrap_or_default().as_ptr()
                );
                if !pw.is_null() {
                    return (*pw).pw_uid == uid;
                }
            }
        }
    }
    false
}
