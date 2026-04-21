//! Network scanner — detects suspicious ESTABLISHED connections.
//!
//! Checks for: C2 ports, Tor, IRC, mining pools, unexpected outbound connections.
//! Cross-platform via sysinfo + direct /proc/net/tcp parsing on Linux.

use pyo3::prelude::*;
use std::collections::HashSet;
use std::net::IpAddr;

/// Known C2/malware/suspicious destination ports.
const SUSPICIOUS_PORTS: &[(u16, &str, &str)] = &[
    // IRC — classic C2 channel
    (6667, "IRC", "high"),
    (6668, "IRC", "high"),
    (6669, "IRC", "high"),
    (6697, "IRC/TLS", "high"),
    (7000, "IRC", "medium"),

    // Tor
    (9050, "Tor SOCKS proxy", "high"),
    (9051, "Tor control", "critical"),
    (9150, "Tor Browser SOCKS", "medium"),

    // Common C2 framework ports
    (4444, "Metasploit default", "critical"),
    (5555, "Common backdoor/ADB", "high"),
    (1234, "Common backdoor", "high"),
    (31337, "Back Orifice/Elite", "critical"),
    (12345, "NetBus trojan", "critical"),
    (65535, "Suspicious high port", "medium"),

    // Cobalt Strike
    (50050, "Cobalt Strike teamserver", "critical"),

    // Mining pools (common ports)
    (3333, "Mining pool stratum", "high"),
    (14444, "Mining pool stratum", "high"),
    (45700, "Mining pool (MoneroOcean)", "critical"),

    // Reverse shell common ports
    (8888, "Common reverse shell", "medium"),
    (9999, "Common reverse shell", "medium"),
];

/// Known malicious/suspicious IP ranges (simplified — just a few known-bad ranges).
/// In production you'd use threat intel feeds, but these catch obvious stuff.
const SUSPICIOUS_IP_PREFIXES: &[(&str, &str)] = &[
    // Tor exit node ranges (partial — for demo, real IDS uses full lists)
    // We don't hardcode IPs, but flag connections to Tor ports
];

/// Private/reserved IP ranges — connections to these are generally OK.
fn is_private_ip(ip: &IpAddr) -> bool {
    match ip {
        IpAddr::V4(v4) => {
            v4.is_loopback() ||       // 127.0.0.0/8
            v4.is_private() ||         // 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
            v4.is_link_local() ||      // 169.254.0.0/16
            v4.is_unspecified()        // 0.0.0.0
        }
        IpAddr::V6(v6) => {
            v6.is_loopback() || v6.is_unspecified()
        }
    }
}

#[pyclass]
#[derive(Clone)]
pub struct NetworkFinding {
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub local_addr: String,
    #[pyo3(get)]
    pub remote_addr: String,
    #[pyo3(get)]
    pub remote_port: u16,
    #[pyo3(get)]
    pub pid: u32,
    #[pyo3(get)]
    pub process_name: String,
}

#[pymethods]
impl NetworkFinding {
    fn __repr__(&self) -> String {
        format!(
            "NetworkFinding(severity='{}', remote='{}:{}', process='{}', desc='{}')",
            self.severity, self.remote_addr, self.remote_port,
            self.process_name, self.description
        )
    }
}

/// Scan established network connections for suspicious destinations.
#[pyfunction]
pub fn scan_network() -> Vec<NetworkFinding> {
    let mut findings = Vec::new();
    let mut seen = HashSet::new();

    #[cfg(target_os = "linux")]
    {
        scan_proc_net_tcp(&mut findings, &mut seen);
    }

    #[cfg(not(target_os = "linux"))]
    {
        scan_sysinfo_network(&mut findings, &mut seen);
    }

    // Also scan listening ports for risky services on 0.0.0.0
    scan_listening_ports(&mut findings, &mut seen);

    findings
}

/// Parse /proc/net/tcp directly — fastest way on Linux.
#[cfg(target_os = "linux")]
fn scan_proc_net_tcp(findings: &mut Vec<NetworkFinding>, seen: &mut HashSet<String>) {
    use sysinfo::System;

    let mut sys = System::new();
    sys.refresh_processes(sysinfo::ProcessesToUpdate::All, false);

    for path in &["/proc/net/tcp", "/proc/net/tcp6"] {
        let content = match std::fs::read_to_string(path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        for line in content.lines().skip(1) {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() < 10 {
                continue;
            }

            // State 01 = ESTABLISHED
            let state = parts[3];
            if state != "01" {
                continue;
            }

            let local = parse_hex_addr(parts[1]);
            let remote = parse_hex_addr(parts[2]);

            let (remote_ip_str, remote_port) = match &remote {
                Some((ip, port)) => (ip.to_string(), *port),
                None => continue,
            };

            let remote_ip: IpAddr = match remote_ip_str.parse() {
                Ok(ip) => ip,
                Err(_) => continue,
            };

            // Skip private IPs
            if is_private_ip(&remote_ip) {
                continue;
            }

            let local_str = local
                .map(|(ip, port)| format!("{}:{}", ip, port))
                .unwrap_or_default();
            let remote_str = format!("{}:{}", remote_ip_str, remote_port);

            let dedup_key = format!("{}:{}", remote_ip_str, remote_port);
            if seen.contains(&dedup_key) {
                continue;
            }

            // Get PID from inode
            let uid = parts.get(7).unwrap_or(&"0");
            let inode = parts.get(9).unwrap_or(&"0");
            let pid = find_pid_for_inode(inode).unwrap_or(0);

            let process_name = if pid > 0 {
                let spid = sysinfo::Pid::from_u32(pid);
                sys.process(spid)
                    .map(|p| p.name().to_string_lossy().to_string())
                    .unwrap_or_default()
            } else {
                String::new()
            };

            // Check against suspicious ports
            for &(port, service, severity) in SUSPICIOUS_PORTS {
                if remote_port == port {
                    seen.insert(dedup_key.clone());
                    findings.push(NetworkFinding {
                        severity: severity.to_string(),
                        description: format!(
                            "Connection to {} port {} ({}) from '{}' (PID {}) — possible {}",
                            remote_ip_str, remote_port, service,
                            if process_name.is_empty() { "unknown" } else { &process_name },
                            pid, service
                        ),
                        local_addr: local_str.clone(),
                        remote_addr: remote_ip_str.clone(),
                        remote_port,
                        pid,
                        process_name: process_name.clone(),
                    });
                    break;
                }
            }
        }
    }
}

/// Parse hex address from /proc/net/tcp format: "0100007F:0035" -> ("127.0.0.1", 53)
#[cfg(target_os = "linux")]
fn parse_hex_addr(s: &str) -> Option<(String, u16)> {
    let parts: Vec<&str> = s.split(':').collect();
    if parts.len() != 2 {
        return None;
    }

    let port = u16::from_str_radix(parts[1], 16).ok()?;

    let hex_ip = parts[0];
    if hex_ip.len() == 8 {
        // IPv4
        let ip = u32::from_str_radix(hex_ip, 16).ok()?;
        let a = ip & 0xff;
        let b = (ip >> 8) & 0xff;
        let c = (ip >> 16) & 0xff;
        let d = (ip >> 24) & 0xff;
        Some((format!("{}.{}.{}.{}", a, b, c, d), port))
    } else if hex_ip.len() == 32 {
        // IPv6 — simplified
        let bytes: Vec<u8> = (0..32)
            .step_by(2)
            .filter_map(|i| u8::from_str_radix(&hex_ip[i..i + 2], 16).ok())
            .collect();
        if bytes.len() == 16 {
            // Reorder from little-endian 32-bit words
            let mut reordered = [0u8; 16];
            for group in 0..4 {
                for byte in 0..4 {
                    reordered[group * 4 + byte] = bytes[group * 4 + (3 - byte)];
                }
            }
            let ipv6 = std::net::Ipv6Addr::from(reordered);
            Some((ipv6.to_string(), port))
        } else {
            None
        }
    } else {
        None
    }
}

/// Find PID that owns a socket inode (Linux-specific).
#[cfg(target_os = "linux")]
fn find_pid_for_inode(inode: &str) -> Option<u32> {
    let target = format!("socket:[{}]", inode);
    let proc_dir = match std::fs::read_dir("/proc") {
        Ok(d) => d,
        Err(_) => return None,
    };

    for entry in proc_dir.flatten() {
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        let pid: u32 = match name_str.parse() {
            Ok(p) => p,
            Err(_) => continue,
        };

        let fd_dir = format!("/proc/{}/fd", pid);
        let fds = match std::fs::read_dir(&fd_dir) {
            Ok(d) => d,
            Err(_) => continue,
        };

        for fd_entry in fds.flatten() {
            if let Ok(link) = std::fs::read_link(fd_entry.path()) {
                if link.to_string_lossy() == target {
                    return Some(pid);
                }
            }
        }
    }
    None
}

/// Non-Linux fallback using sysinfo (macOS, Windows).
#[cfg(not(target_os = "linux"))]
fn scan_sysinfo_network(findings: &mut Vec<NetworkFinding>, seen: &mut HashSet<String>) {
    // sysinfo doesn't expose network connections directly on all platforms.
    // On macOS/Windows we'd use platform-specific APIs.
    // For now, fall back to command-line tools.

    #[cfg(target_os = "macos")]
    {
        if let Ok(output) = std::process::Command::new("netstat")
            .args(["-an", "-p", "tcp"])
            .output()
        {
            let stdout = String::from_utf8_lossy(&output.stdout);
            parse_netstat_output(&stdout, findings, seen);
        }
    }

    #[cfg(target_os = "windows")]
    {
        if let Ok(output) = std::process::Command::new("netstat")
            .args(["-ano"])
            .output()
        {
            let stdout = String::from_utf8_lossy(&output.stdout);
            parse_netstat_windows(&stdout, findings, seen);
        }
    }
}

/// Parse macOS netstat output.
#[cfg(target_os = "macos")]
fn parse_netstat_output(output: &str, findings: &mut Vec<NetworkFinding>, seen: &mut HashSet<String>) {
    for line in output.lines() {
        if !line.contains("ESTABLISHED") {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 5 {
            continue;
        }
        // parts[3] = remote address (ip.port)
        let remote = parts[3];
        if let Some(last_dot) = remote.rfind('.') {
            let ip_str = &remote[..last_dot];
            let port_str = &remote[last_dot + 1..];
            let port: u16 = match port_str.parse() {
                Ok(p) => p,
                Err(_) => continue,
            };
            let ip: IpAddr = match ip_str.parse() {
                Ok(ip) => ip,
                Err(_) => continue,
            };
            if is_private_ip(&ip) {
                continue;
            }
            let dedup_key = format!("{}:{}", ip_str, port);
            if seen.contains(&dedup_key) {
                continue;
            }
            for &(suspicious_port, service, severity) in SUSPICIOUS_PORTS {
                if port == suspicious_port {
                    seen.insert(dedup_key.clone());
                    findings.push(NetworkFinding {
                        severity: severity.to_string(),
                        description: format!(
                            "Connection to {} port {} ({}) — possible {}",
                            ip_str, port, service, service
                        ),
                        local_addr: parts.get(4).unwrap_or(&"").to_string(),
                        remote_addr: ip_str.to_string(),
                        remote_port: port,
                        pid: 0,
                        process_name: String::new(),
                    });
                    break;
                }
            }
        }
    }
}

/// Parse Windows netstat -ano output.
#[cfg(target_os = "windows")]
fn parse_netstat_windows(output: &str, findings: &mut Vec<NetworkFinding>, seen: &mut HashSet<String>) {
    for line in output.lines() {
        if !line.contains("ESTABLISHED") {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 5 {
            continue;
        }
        // TCP  local_addr  remote_addr  ESTABLISHED  PID
        let remote = parts[2];
        let pid: u32 = parts[4].parse().unwrap_or(0);
        if let Some(last_colon) = remote.rfind(':') {
            let ip_str = &remote[..last_colon];
            let port_str = &remote[last_colon + 1..];
            let port: u16 = match port_str.parse() {
                Ok(p) => p,
                Err(_) => continue,
            };
            let ip: IpAddr = match ip_str.parse() {
                Ok(ip) => ip,
                Err(_) => continue,
            };
            if is_private_ip(&ip) {
                continue;
            }
            let dedup_key = format!("{}:{}", ip_str, port);
            if seen.contains(&dedup_key) {
                continue;
            }
            for &(suspicious_port, service, severity) in SUSPICIOUS_PORTS {
                if port == suspicious_port {
                    seen.insert(dedup_key.clone());
                    findings.push(NetworkFinding {
                        severity: severity.to_string(),
                        description: format!(
                            "Connection to {} port {} ({}) — PID {} — possible {}",
                            ip_str, port, service, pid, service
                        ),
                        local_addr: parts[1].to_string(),
                        remote_addr: ip_str.to_string(),
                        remote_port: port,
                        pid,
                        process_name: String::new(),
                    });
                    break;
                }
            }
        }
    }
}

/// Scan for risky services listening on 0.0.0.0.
fn scan_listening_ports(findings: &mut Vec<NetworkFinding>, seen: &mut HashSet<String>) {
    let risky_services: &[(u16, &str)] = &[
        (3306, "MySQL"),
        (5432, "PostgreSQL"),
        (6379, "Redis"),
        (27017, "MongoDB"),
        (11211, "Memcached"),
        (9200, "Elasticsearch"),
        (5601, "Kibana"),
        (8080, "HTTP proxy/dev server"),
        (2375, "Docker API (unencrypted!)"),
        (2376, "Docker API"),
        (5900, "VNC"),
        (5901, "VNC"),
        (1433, "MSSQL"),
        (1521, "Oracle DB"),
        (9042, "Cassandra"),
        (7474, "Neo4j"),
        (15672, "RabbitMQ Management"),
        (8500, "Consul"),
        (2181, "Zookeeper"),
    ];

    #[cfg(target_os = "linux")]
    {
        let content = match std::fs::read_to_string("/proc/net/tcp") {
            Ok(c) => c,
            Err(_) => return,
        };

        for line in content.lines().skip(1) {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() < 4 {
                continue;
            }
            // State 0A = LISTEN
            if parts[3] != "0A" {
                continue;
            }
            if let Some((ip, port)) = parse_hex_addr(parts[1]) {
                if ip == "0.0.0.0" {
                    let key = format!("listen:0.0.0.0:{}", port);
                    if seen.contains(&key) {
                        continue;
                    }
                    for &(risky_port, service) in risky_services {
                        if port == risky_port {
                            seen.insert(key.clone());
                            findings.push(NetworkFinding {
                                severity: "high".to_string(),
                                description: format!(
                                    "{} (port {}) listening on 0.0.0.0 — accessible from network, should be localhost",
                                    service, port
                                ),
                                local_addr: format!("0.0.0.0:{}", port),
                                remote_addr: String::new(),
                                remote_port: 0,
                                pid: 0,
                                process_name: service.to_string(),
                            });
                            break;
                        }
                    }
                }
            }
        }
    }
}
