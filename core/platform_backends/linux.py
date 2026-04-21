"""Linux platform backend."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

_URGENCY_MAP = {"critical": "critical", "warning": "normal", "info": "low"}

_SOUND_PLAYERS = [
    ("pw-play", lambda p: ["pw-play", str(p)]),
    ("paplay", lambda p: ["paplay", str(p)]),
    ("ffplay", lambda p: ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(p)]),
    ("aplay", lambda p: ["aplay", str(p)]),
]


class LinuxBackend:
    def config_dir(self) -> Path:
        return Path.home() / ".config" / "claude-monitor"

    def cache_dir(self) -> Path:
        return Path.home() / ".cache" / "claude-monitor"

    def data_dir(self) -> Path:
        return Path.home() / ".local" / "share" / "claude-monitor"

    def notify(self, title: str, message: str, urgency: str = "normal") -> None:
        u = _URGENCY_MAP.get(urgency, "normal")
        if not shutil.which("notify-send"):
            log.warning("notify-send not found")
            return
        try:
            subprocess.Popen(
                ["notify-send", "-u", u, title, message],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass

    def play_sound(self, path: Path) -> subprocess.Popen | None:
        """Play sound file, return process handle (can be killed to stop)."""
        for cmd_name, args_fn in _SOUND_PLAYERS:
            if shutil.which(cmd_name):
                try:
                    return subprocess.Popen(
                        args_fn(path),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                except FileNotFoundError:
                    continue
        log.warning("No sound player found (tried pw-play, paplay, ffplay, aplay)")
        return None

    def open_url(self, url: str) -> None:
        if not url.startswith(("http://", "https://")):
            log.warning("Blocked non-HTTP URL: %s", url[:80])
            return
        try:
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.warning("xdg-open not found")

    def open_file(self, path: Path) -> None:
        self.open_url(str(path))

    def check_firewall(self) -> dict:
        """Return {"active": bool, "tool": str, "details": str}."""
        # Try ufw
        try:
            result = subprocess.run(
                ["ufw", "status"], capture_output=True, text=True, timeout=10,
            )
            if "inactive" in result.stdout.lower():
                return {"active": False, "tool": "ufw", "details": "ufw is inactive"}
            if result.returncode == 0:
                return {"active": True, "tool": "ufw", "details": result.stdout.strip()[:200]}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try nftables
        try:
            result = subprocess.run(
                ["nft", "list", "ruleset"], capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return {"active": True, "tool": "nftables", "details": "nftables rules found"}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try iptables
        try:
            result = subprocess.run(
                ["iptables", "-L", "-n"], capture_output=True, text=True, timeout=10,
            )
            lines = [l for l in result.stdout.strip().split("\n")
                     if l.strip() and not l.startswith("Chain") and not l.startswith("target")]
            if lines:
                return {"active": True, "tool": "iptables", "details": f"{len(lines)} rules"}
            return {"active": False, "tool": "iptables", "details": "no rules configured"}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return {"active": False, "tool": "none", "details": "no firewall found"}

    def check_system_updates(self) -> list[str]:
        """Return list of available security update descriptions."""
        # Try apt (Debian/Ubuntu)
        try:
            result = subprocess.run(
                ["apt", "list", "--upgradable"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split("\n")
                         if l and not l.startswith("Listing")]
                security = [l for l in lines if "security" in l.lower()]
                if security:
                    return [f"{len(security)} security updates (apt)"]
                if len(lines) > 10:
                    return [f"{len(lines)} package updates (apt)"]
            return []
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try dnf (Fedora/RHEL)
        try:
            result = subprocess.run(
                ["dnf", "check-update", "--security", "-q"],
                capture_output=True, text=True, timeout=30,
            )
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            if lines:
                return [f"{len(lines)} security updates (dnf)"]
            return []
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try pacman (Arch)
        try:
            result = subprocess.run(
                ["pacman", "-Qu"], capture_output=True, text=True, timeout=30,
            )
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            if lines:
                return [f"{len(lines)} package updates (pacman)"]
            return []
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return []

    def check_ssh_config(self) -> dict:
        """Return {"exists": bool, "issues": list[str]}."""
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
        if config.get("permitemptypasswords") == "yes":
            issues.append("empty passwords allowed")
        if config.get("port", "22") == "22":
            issues.append("default port 22")

        return {"exists": True, "issues": issues}

    def check_sudoers(self) -> dict:
        """Return {"nopasswd_all": bool}."""
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
        if shutil.which("pkexec"):
            return ["pkexec"] + cmd
        return ["sudo"] + cmd
