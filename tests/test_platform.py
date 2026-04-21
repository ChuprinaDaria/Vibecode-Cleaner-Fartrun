"""Tests for cross-platform abstraction layer."""

from unittest.mock import patch
from pathlib import Path

from core.platform import detect_platform, PlatformType, reset_platform


class TestPlatformDetection:
    def test_detect_linux(self):
        with patch("core.platform.sys.platform", "linux"):
            assert detect_platform() == PlatformType.LINUX

    def test_detect_macos(self):
        with patch("core.platform.sys.platform", "darwin"):
            assert detect_platform() == PlatformType.MACOS

    def test_detect_windows(self):
        with patch("core.platform.sys.platform", "win32"):
            assert detect_platform() == PlatformType.WINDOWS

    def test_detect_freebsd_falls_to_linux(self):
        with patch("core.platform.sys.platform", "freebsd"):
            assert detect_platform() == PlatformType.LINUX


from unittest.mock import MagicMock
from core.platform_backends.linux import LinuxBackend


class TestLinuxBackend:
    def setup_method(self):
        self.backend = LinuxBackend()

    def test_config_dir(self):
        d = self.backend.config_dir()
        assert d == Path.home() / ".config" / "claude-monitor"

    def test_cache_dir(self):
        d = self.backend.cache_dir()
        assert d == Path.home() / ".cache" / "claude-monitor"

    def test_data_dir(self):
        d = self.backend.data_dir()
        assert d == Path.home() / ".local" / "share" / "claude-monitor"

    @patch("shutil.which", return_value="/usr/bin/notify-send")
    @patch("subprocess.Popen")
    def test_notify(self, mock_popen, mock_which):
        self.backend.notify("Test", "Message", "critical")
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "notify-send" in args
        assert "-u" in args
        assert "critical" in args

    @patch("core.platform_backends.linux.shutil.which",
           side_effect=lambda x: "/usr/bin/pw-play" if x == "pw-play" else None)
    @patch("subprocess.Popen")
    def test_play_sound_pipewire(self, mock_popen, mock_which):
        self.backend.play_sound(Path("/tmp/test.wav"))
        args = mock_popen.call_args[0][0]
        assert "pw-play" in args[0]

    @patch("core.platform_backends.linux.shutil.which",
           side_effect=lambda x: "/usr/bin/paplay" if x == "paplay" else None)
    @patch("subprocess.Popen")
    def test_play_sound_pulseaudio(self, mock_popen, mock_which):
        self.backend.play_sound(Path("/tmp/test.wav"))
        args = mock_popen.call_args[0][0]
        assert "paplay" in args[0]

    @patch("subprocess.Popen")
    def test_open_url(self, mock_popen):
        self.backend.open_url("https://example.com")
        args = mock_popen.call_args[0][0]
        assert "xdg-open" in args

    def test_elevate_command_with_pkexec(self):
        with patch("core.platform_backends.linux.shutil.which", return_value="/usr/bin/pkexec"):
            cmd = self.backend.elevate_command(["ufw", "enable"])
            assert cmd[0] == "pkexec"
            assert "ufw" in cmd


from core.platform_backends.macos import MacOSBackend


class TestMacOSBackend:
    def setup_method(self):
        self.backend = MacOSBackend()

    def test_config_dir(self):
        d = self.backend.config_dir()
        assert "Library/Application Support/claude-monitor" in str(d)

    def test_cache_dir(self):
        d = self.backend.cache_dir()
        assert "Library/Caches/claude-monitor" in str(d)

    @patch("subprocess.Popen")
    def test_notify(self, mock_popen):
        self.backend.notify("Test", "Hello", "normal")
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "osascript" in args

    @patch("subprocess.Popen")
    def test_play_sound(self, mock_popen):
        self.backend.play_sound(Path("/tmp/test.wav"))
        args = mock_popen.call_args[0][0]
        assert "afplay" in args

    @patch("subprocess.Popen")
    def test_open_url(self, mock_popen):
        self.backend.open_url("https://example.com")
        args = mock_popen.call_args[0][0]
        assert "open" in args

    def test_elevate_command(self):
        cmd = self.backend.elevate_command(["pfctl", "-e"])
        assert "osascript" in cmd[0]


from core.platform_backends.windows import WindowsBackend


class TestWindowsBackend:
    def setup_method(self):
        self.backend = WindowsBackend()

    def test_config_dir(self):
        d = self.backend.config_dir()
        assert "claude-monitor" in str(d)

    def test_cache_dir(self):
        d = self.backend.cache_dir()
        assert "claude-monitor" in str(d)

    @patch("subprocess.Popen")
    def test_notify_powershell(self, mock_popen):
        self.backend.notify("Test", "Hello")
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "powershell" in args[0].lower()

    @patch("subprocess.Popen")
    def test_play_sound(self, mock_popen):
        self.backend.play_sound(Path("C:/test.wav"))
        mock_popen.assert_called_once()

    def test_elevate_command(self):
        cmd = self.backend.elevate_command(["netsh", "advfirewall", "show"])
        assert "powershell" in cmd[0].lower()
