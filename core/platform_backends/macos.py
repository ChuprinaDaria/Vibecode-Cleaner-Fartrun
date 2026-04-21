"""macOS platform backend."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _escape_applescript(s: str) -> str:
    """Escape string for safe use in AppleScript double-quoted strings."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


class MacOSBackend:
    def config_dir(self) -> Path:
        return Path.home() / "Library" / "Application Support" / "claude-monitor"

    def cache_dir(self) -> Path:
        return Path.home() / "Library" / "Caches" / "claude-monitor"

    def data_dir(self) -> Path:
        return Path.home() / "Library" / "Application Support" / "claude-monitor"

    def notify(self, title: str, message: str, urgency: str = "normal") -> None:
        safe_title = _escape_applescript(title)
        safe_message = _escape_applescript(message)
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        try:
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.warning("osascript not found")

    def play_sound(self, path: Path) -> subprocess.Popen | None:
        """Play sound file, return process handle (can be killed to stop)."""
        try:
            return subprocess.Popen(
                ["afplay", str(path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.warning("afplay not found")
            return None

    def open_url(self, url: str) -> None:
        if not url.startswith(("http://", "https://")):
            log.warning("Blocked non-HTTP URL: %s", url[:80])
            return
        try:
            subprocess.Popen(
                ["open", url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.warning("open command not found")

    def open_file(self, path: Path) -> None:
        self.open_url(str(path))

    def check_firewall(self) -> dict:
        # Application firewall
        try:
            result = subprocess.run(
                ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"],
                capture_output=True, text=True, timeout=10,
            )
            if "enabled" in result.stdout.lower():
                return {"active": True, "tool": "socketfilterfw",
                        "details": result.stdout.strip()[:200]}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # pf firewall
        try:
            result = subprocess.run(
                ["pfctl", "-s", "info"], capture_output=True, text=True, timeout=10,
            )
            combined = result.stderr.lower() + result.stdout.lower()
            if "enabled" in combined:
                return {"active": True, "tool": "pf", "details": "pf is enabled"}
            return {"active": False, "tool": "pf", "details": "pf is disabled"}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return {"active": False, "tool": "none", "details": "no firewall detected"}

    def check_system_updates(self) -> list[str]:
        try:
            result = subprocess.run(
                ["softwareupdate", "-l"],
                capture_output=True, text=True, timeout=60,
            )
            lines = [l.strip() for l in result.stdout.split("\n")
                     if l.strip() and "Security" in l]
            if lines:
                return [f"{len(lines)} security updates (softwareupdate)"]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return []

    def check_ssh_config(self) -> dict:
        sshd_config = Path("/etc/ssh/sshd_config")
        if not sshd_config.exists():
            return {"exists": False, "issues": []}

        try:
            content = sshd_config.read_text()
        except PermissionError:
            return {"exists": True, "issues": ["cannot read — permission denied"]}

        config = {}
        for line in content.lower().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                config[parts[0]] = parts[1]

        issues = []
        if config.get("permitrootlogin") not in ("no", "prohibit-password"):
            issues.append("root login allowed")
        if config.get("passwordauthentication") == "yes":
            issues.append("password auth enabled")
        return {"exists": True, "issues": issues}

    def check_sudoers(self) -> dict:
        try:
            result = subprocess.run(
                ["sudo", "-l", "-n"],
                capture_output=True, text=True, timeout=10,
            )
            has_nopasswd = "NOPASSWD" in result.stdout and "ALL" in result.stdout
            return {"nopasswd_all": has_nopasswd}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {"nopasswd_all": False}

    def elevate_command(self, cmd: list[str]) -> list[str]:
        import shlex
        safe_cmd = _escape_applescript(shlex.join(cmd))
        return [
            "osascript", "-e",
            f'do shell script "{safe_cmd}" with administrator privileges',
        ]
