//! Scheduled tasks scanner — crontab, systemd timers, launchd, Windows Task Scheduler.
//!
//! Looks for: suspicious URLs, pipe-to-shell, base64 decode, crypto mining,
//! unknown scripts running as root.

use pyo3::prelude::*;
use std::path::PathBuf;

/// Suspicious patterns in scheduled task commands.
const SUSPICIOUS_CMD_PATTERNS: &[(&str, &str, &str)] = &[
    ("curl|bash", "critical", "Pipe-to-shell in scheduled task: {}"),
    ("curl|sh", "critical", "Pipe-to-shell in scheduled task: {}"),
    ("wget|bash", "critical", "Pipe-to-shell in scheduled task: {}"),
    ("wget|sh", "critical", "Pipe-to-shell in scheduled task: {}"),
    ("curl -s|", "critical", "Silent curl piped in scheduled task: {}"),
    ("base64 -d", "critical", "Base64 decode in scheduled task: {}"),
    ("base64 --decode", "critical", "Base64 decode in scheduled task: {}"),
    ("eval $(", "critical", "Eval in scheduled task: {}"),
    ("python -c", "high", "Inline Python in scheduled task: {}"),
    ("python3 -c", "high", "Inline Python in scheduled task: {}"),
    ("nc -e", "critical", "Netcat exec in scheduled task: {}"),
    ("ncat -e", "critical", "Ncat exec in scheduled task: {}"),
    ("/dev/tcp/", "critical", "TCP redirect in scheduled task: {}"),
    ("stratum+tcp://", "critical", "Mining pool in scheduled task: {}"),
    ("stratum+ssl://", "critical", "Mining pool in scheduled task: {}"),
    ("xmrig", "critical", "Cryptominer in scheduled task: {}"),
    ("minerd", "critical", "Cryptominer in scheduled task: {}"),
    ("/tmp/.", "high", "Hidden /tmp path in scheduled task: {}"),
    ("/dev/shm/", "high", "/dev/shm path in scheduled task: {}"),
];

#[pyclass]
#[derive(Clone)]
pub struct CronFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub source: String,    // "crontab", "systemd-timer", "launchd", "task-scheduler"
    #[pyo3(get)]
    pub command: String,
    #[pyo3(get)]
    pub schedule: String,
}

#[pymethods]
impl CronFinding {
    fn __repr__(&self) -> String {
        format!(
            "CronFinding(severity='{}', source='{}', desc='{}')",
            self.severity, self.source, self.description
        )
    }
}

/// Scan all scheduled tasks for suspicious commands.
#[pyfunction]
pub fn scan_scheduled_tasks() -> Vec<CronFinding> {
    let mut findings = Vec::new();

    #[cfg(target_os = "linux")]
    {
        scan_user_crontab(&mut findings);
        scan_cron_dirs(&mut findings);
        scan_systemd_timers(&mut findings);
    }

    #[cfg(target_os = "macos")]
    {
        scan_user_crontab(&mut findings);
        scan_launchd(&mut findings);
    }

    #[cfg(target_os = "windows")]
    {
        scan_windows_tasks(&mut findings);
    }

    findings
}

/// Parse current user's crontab.
#[cfg(unix)]
fn scan_user_crontab(findings: &mut Vec<CronFinding>) {
    let output = match std::process::Command::new("crontab")
        .arg("-l")
        .output()
    {
        Ok(o) => o,
        Err(_) => return,
    };

    if !output.status.success() {
        return; // No crontab for this user
    }

    let content = String::from_utf8_lossy(&output.stdout);
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        // Crontab format: min hour dom mon dow command
        let parts: Vec<&str> = line.splitn(6, char::is_whitespace).collect();
        if parts.len() < 6 {
            continue;
        }

        let schedule = parts[..5].join(" ");
        let command = parts[5];
        let cmd_lower = command.to_lowercase();

        check_suspicious_command(&cmd_lower, command, &schedule, "crontab", findings);
    }
}

/// Scan system cron directories.
#[cfg(target_os = "linux")]
fn scan_cron_dirs(findings: &mut Vec<CronFinding>) {
    let dirs = [
        "/etc/cron.d",
        "/etc/cron.daily",
        "/etc/cron.hourly",
        "/etc/cron.weekly",
        "/etc/cron.monthly",
    ];

    for dir in &dirs {
        let entries = match std::fs::read_dir(dir) {
            Ok(e) => e,
            Err(_) => continue,
        };

        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }

            let content = match std::fs::read_to_string(&path) {
                Ok(c) => c,
                Err(_) => continue,
            };

            for line in content.lines() {
                let line = line.trim();
                if line.is_empty() || line.starts_with('#') {
                    continue;
                }

                let cmd_lower = line.to_lowercase();
                let source = format!("cron:{}", path.display());
                check_suspicious_command(&cmd_lower, line, dir, &source, findings);
            }
        }
    }
}

/// Scan systemd timers for suspicious commands.
#[cfg(target_os = "linux")]
fn scan_systemd_timers(findings: &mut Vec<CronFinding>) {
    // List active timers
    let output = match std::process::Command::new("systemctl")
        .args(["list-timers", "--all", "--no-pager", "--no-legend"])
        .output()
    {
        Ok(o) => o,
        Err(_) => return,
    };

    let stdout = String::from_utf8_lossy(&output.stdout);

    for line in stdout.lines() {
        let parts: Vec<&str> = line.split_whitespace().collect();
        // Format: NEXT LEFT LAST PASSED UNIT ACTIVATES
        if parts.len() < 6 {
            continue;
        }

        let unit = parts[parts.len() - 2]; // UNIT column
        let service = parts[parts.len() - 1]; // ACTIVATES column

        // Read the service file to get ExecStart
        let service_content = try_read_service(service);
        if let Some(content) = service_content {
            for line in content.lines() {
                let line = line.trim();
                if line.starts_with("ExecStart=") {
                    let cmd = &line["ExecStart=".len()..];
                    let cmd_lower = cmd.to_lowercase();
                    let schedule = format!("timer:{}", unit);
                    check_suspicious_command(&cmd_lower, cmd, &schedule, "systemd-timer", findings);
                }
            }
        }
    }
}

#[cfg(target_os = "linux")]
fn try_read_service(name: &str) -> Option<String> {
    let paths = [
        format!("/etc/systemd/system/{}", name),
        format!("/usr/lib/systemd/system/{}", name),
        format!("/lib/systemd/system/{}", name),
    ];
    // Also check user services
    let home = std::env::var("HOME").unwrap_or_default();
    let user_path = format!("{}/.config/systemd/user/{}", home, name);

    for path in paths.iter().chain(std::iter::once(&user_path)) {
        if let Ok(content) = std::fs::read_to_string(path) {
            return Some(content);
        }
    }
    None
}

/// Scan macOS launchd agents/daemons.
#[cfg(target_os = "macos")]
fn scan_launchd(findings: &mut Vec<CronFinding>) {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/Users".to_string());
    let dirs = [
        format!("{}/Library/LaunchAgents", home),
        "/Library/LaunchAgents".to_string(),
        "/Library/LaunchDaemons".to_string(),
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

            let content = match std::fs::read_to_string(&path) {
                Ok(c) => c,
                Err(_) => continue,
            };

            // Simple plist parsing — look for ProgramArguments
            let cmd_lower = content.to_lowercase();
            let source = format!("launchd:{}", path.display());
            check_suspicious_command(&cmd_lower, &content, "launchd", &source, findings);
        }
    }
}

/// Scan Windows Task Scheduler.
#[cfg(target_os = "windows")]
fn scan_windows_tasks(findings: &mut Vec<CronFinding>) {
    let output = match std::process::Command::new("schtasks")
        .args(["/Query", "/FO", "CSV", "/V"])
        .output()
    {
        Ok(o) => o,
        Err(_) => return,
    };

    let stdout = String::from_utf8_lossy(&output.stdout);
    for line in stdout.lines().skip(1) {
        // CSV format: "HostName","TaskName","Next Run Time","Status","Logon Mode","Last Run Time","Last Result","Author","Task To Run","Start In",...
        let fields: Vec<&str> = line.split(',')
            .map(|f| f.trim_matches('"'))
            .collect();

        if fields.len() < 9 {
            continue;
        }

        let task_name = fields[1];
        let command = fields[8];
        let cmd_lower = command.to_lowercase();
        let schedule = fields.get(2).unwrap_or(&"");
        let source = format!("task-scheduler:{}", task_name);

        check_suspicious_command(&cmd_lower, command, schedule, &source, findings);

        // Windows-specific: check for tasks running from temp/appdata
        if cmd_lower.contains("\\temp\\") || cmd_lower.contains("\\tmp\\") {
            findings.push(CronFinding {
                severity: "high".to_string(),
                description: format!(
                    "Scheduled task running from temp directory: {} — {}",
                    task_name, command
                ),
                source,
                command: command.to_string(),
                schedule: schedule.to_string(),
            });
        }

        // Check for PowerShell encoded commands
        if cmd_lower.contains("powershell") && cmd_lower.contains("-encodedcommand") {
            findings.push(CronFinding {
                severity: "critical".to_string(),
                description: format!(
                    "Scheduled task with encoded PowerShell: {} — common malware technique",
                    task_name
                ),
                source: format!("task-scheduler:{}", task_name),
                command: command.to_string(),
                schedule: schedule.to_string(),
            });
        }
    }
}

/// Known legitimate system cron jobs that use patterns we'd normally flag.
const SYSTEM_CRON_WHITELIST: &[&str] = &[
    "apt-compat", "apt-config", "google-chrome", "google-earth",
    "dpkg", "logrotate", "man-db", "sysstat", "popularity-contest",
    "update-notifier-common", "certbot", "letsencrypt",
    "unattended-upgrade", "fwupd", "snapd",
];

fn check_suspicious_command(
    cmd_lower: &str,
    cmd_original: &str,
    schedule: &str,
    source: &str,
    findings: &mut Vec<CronFinding>,
) {
    // Skip known system cron jobs
    let source_lower = source.to_lowercase();
    if SYSTEM_CRON_WHITELIST.iter().any(|w| source_lower.contains(w)) {
        return;
    }

    for &(pattern, severity, desc_template) in SUSPICIOUS_CMD_PATTERNS {
        if cmd_lower.contains(pattern) {
            findings.push(CronFinding {
                severity: severity.to_string(),
                description: desc_template.replace(
                    "{}",
                    &truncate(cmd_original, 150),
                ),
                source: source.to_string(),
                command: truncate(cmd_original, 200),
                schedule: schedule.to_string(),
            });
            break;
        }
    }
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        format!("{}…", &s[..max])
    }
}
