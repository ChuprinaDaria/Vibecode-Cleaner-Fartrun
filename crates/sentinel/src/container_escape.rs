//! Container escape detection — /.dockerenv, namespace leaks, CAP_SYS_ADMIN.

use pyo3::prelude::*;

#[pyclass]
#[derive(Clone)]
pub struct ContainerEscapeFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub evidence: String,
}

#[pyfunction]
pub fn scan_container_escape() -> Vec<ContainerEscapeFinding> {
    let mut findings = Vec::new();

    let in_container = std::path::Path::new("/.dockerenv").exists()
        || std::fs::read_to_string("/proc/1/cgroup")
            .map(|s| s.contains("docker") || s.contains("containerd") || s.contains("kubepods"))
            .unwrap_or(false);

    if !in_container {
        // Host-side: check for containers with CAP_SYS_ADMIN
        #[cfg(target_os = "linux")]
        {
            if let Ok(entries) = std::fs::read_dir("/proc") {
                for entry in entries.flatten() {
                    let status_path = entry.path().join("status");
                    if let Ok(content) = std::fs::read_to_string(&status_path) {
                        for line in content.lines() {
                            if line.starts_with("CapEff:") {
                                if let Some(hex) = line.split_whitespace().nth(1) {
                                    if let Ok(caps) = u64::from_str_radix(hex.trim(), 16) {
                                        // CAP_SYS_ADMIN = bit 21
                                        if caps & (1 << 21) != 0 {
                                            let cgroup_path = entry.path().join("cgroup");
                                            if let Ok(cgroup) = std::fs::read_to_string(&cgroup_path) {
                                                if cgroup.contains("docker") || cgroup.contains("containerd") {
                                                    let pid = entry.file_name().to_string_lossy().to_string();
                                                    let cmdline = std::fs::read_to_string(entry.path().join("cmdline"))
                                                        .unwrap_or_default()
                                                        .replace('\0', " ");
                                                    findings.push(ContainerEscapeFinding {
                                                        severity: "critical".into(),
                                                        description: format!(
                                                            "Container process PID {} has CAP_SYS_ADMIN — potential escape vector: {}",
                                                            pid, &cmdline[..cmdline.len().min(100)]
                                                        ),
                                                        evidence: format!("pid:{} caps:{:#x}", pid, caps),
                                                    });
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    } else {
        // Inside container — check for escape possibilities
        findings.push(ContainerEscapeFinding {
            severity: "info".into(),
            description: "Running inside a container — limited host visibility".into(),
            evidence: "/.dockerenv exists".into(),
        });

        if std::path::Path::new("/var/run/docker.sock").exists() {
            findings.push(ContainerEscapeFinding {
                severity: "critical".into(),
                description: "Docker socket accessible inside container — full host escape possible".into(),
                evidence: "/var/run/docker.sock".into(),
            });
        }

        #[cfg(target_os = "linux")]
        {
            use std::os::unix::fs::MetadataExt;
            if let Ok(meta) = std::fs::metadata("/proc/sysrq-trigger") {
                if meta.mode() & 0o222 != 0 {
                    findings.push(ContainerEscapeFinding {
                        severity: "high".into(),
                        description: "sysrq-trigger writable — can crash host from container".into(),
                        evidence: "/proc/sysrq-trigger".into(),
                    });
                }
            }
        }
    }

    findings
}
