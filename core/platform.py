"""Cross-platform abstraction layer for OS-specific operations."""

from __future__ import annotations

import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Protocol


class PlatformType(Enum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"


def detect_platform() -> PlatformType:
    if sys.platform == "darwin":
        return PlatformType.MACOS
    if sys.platform == "win32":
        return PlatformType.WINDOWS
    return PlatformType.LINUX


class PlatformBackend(Protocol):
    """Interface every platform backend must implement."""

    def config_dir(self) -> Path: ...
    def cache_dir(self) -> Path: ...
    def data_dir(self) -> Path: ...
    def notify(self, title: str, message: str, urgency: str = "normal") -> None: ...
    def play_sound(self, path: Path) -> subprocess.Popen | None: ...
    def open_url(self, url: str) -> None: ...
    def open_file(self, path: Path) -> None: ...
    def check_firewall(self) -> dict: ...
    def check_system_updates(self) -> list[str]: ...
    def check_ssh_config(self) -> dict: ...
    def check_sudoers(self) -> dict: ...
    def elevate_command(self, cmd: list[str]) -> list[str]: ...


_cached_platform: PlatformBackend | None = None


def get_platform() -> PlatformBackend:
    global _cached_platform
    if _cached_platform is not None:
        return _cached_platform

    pt = detect_platform()
    if pt == PlatformType.LINUX:
        from core.platform_backends.linux import LinuxBackend
        _cached_platform = LinuxBackend()
    elif pt == PlatformType.MACOS:
        from core.platform_backends.macos import MacOSBackend
        _cached_platform = MacOSBackend()
    else:
        from core.platform_backends.windows import WindowsBackend
        _cached_platform = WindowsBackend()
    return _cached_platform


def reset_platform() -> None:
    """Reset cached platform — for testing only."""
    global _cached_platform
    _cached_platform = None
