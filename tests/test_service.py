"""
Tests for service module.

PURPOSE: Verify service management functionality across platforms.
AI CONTEXT: Tests for systemd (Linux), launchd (macOS), Task Scheduler (Windows).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_session_tracker_mcp.service import (
    LAUNCHD_PLIST_TEMPLATE,
    SERVICE_DESCRIPTION,
    SERVICE_NAME,
    SYSTEMD_SERVICE_TEMPLATE,
    LinuxServiceManager,
    MacOSServiceManager,
    ServiceManager,
    WindowsServiceManager,
    get_service_manager,
)


class MockFileSystem:
    """Mock filesystem for testing."""

    def __init__(self) -> None:
        """Initialize mock filesystem."""
        self.files: dict[str, str] = {}
        self.removed: list[str] = []

    def exists(self, path: str) -> bool:
        """Check if path exists."""
        return path in self.files

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        """Create directory."""
        pass

    def read_text(self, path: str) -> str:
        """Read file content."""
        return self.files.get(path, "")

    def write_text(self, path: str, content: str) -> None:
        """Write file content."""
        self.files[path] = content

    def remove(self, path: str) -> None:
        """Remove file."""
        self.removed.append(path)
        if path in self.files:
            del self.files[path]

    def rename(self, src: str, dst: str) -> None:
        """Rename file."""
        if src in self.files:
            self.files[dst] = self.files[src]
            del self.files[src]


# ============================================================
# Base ServiceManager Tests
# ============================================================


class TestServiceManagerBase:
    """Tests for ServiceManager base class."""

    def test_install_raises_not_implemented(self) -> None:
        """Test that base install raises NotImplementedError."""
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.install()

    def test_uninstall_raises_not_implemented(self) -> None:
        """Test that base uninstall raises NotImplementedError."""
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.uninstall()

    def test_start_raises_not_implemented(self) -> None:
        """Test that base start raises NotImplementedError."""
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.start()

    def test_stop_raises_not_implemented(self) -> None:
        """Test that base stop raises NotImplementedError."""
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.stop()

    def test_status_raises_not_implemented(self) -> None:
        """Test that base status raises NotImplementedError."""
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.status()

    def test_get_executable_command_with_script(self) -> None:
        """Test executable command when script exists."""
        fs = MockFileSystem()
        manager = ServiceManager(fs)

        # Mock the bin directory check
        with patch.object(Path, "exists", return_value=True):
            cmd = manager._get_executable_command()
            assert "server" in cmd

    def test_get_executable_command_fallback(self) -> None:
        """Test executable command falls back to module."""
        fs = MockFileSystem()
        manager = ServiceManager(fs)

        with patch.object(Path, "exists", return_value=False):
            cmd = manager._get_executable_command()
            assert "-m" in cmd
            assert "ai_session_tracker_mcp" in cmd


# ============================================================
# Linux ServiceManager Tests
# ============================================================


class TestLinuxServiceManager:
    """Tests for Linux systemd service manager."""

    def test_init_sets_paths(self) -> None:
        """Test initialization sets correct paths."""
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)

        assert ".config/systemd/user" in str(manager._service_dir)
        assert f"{SERVICE_NAME}.service" in str(manager._service_file)

    @patch("subprocess.run")
    def test_install_creates_service_file(self, mock_run: MagicMock) -> None:
        """Test install creates systemd service file."""
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.install()

        assert result is True
        assert len(fs.files) == 1
        service_content = list(fs.files.values())[0]
        assert "[Unit]" in service_content
        assert SERVICE_DESCRIPTION in service_content

    @patch("subprocess.run")
    def test_install_runs_systemctl_commands(self, mock_run: MagicMock) -> None:
        """Test install runs daemon-reload and enable."""
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        manager.install()

        calls = mock_run.call_args_list
        assert any("daemon-reload" in str(call) for call in calls)
        assert any("enable" in str(call) for call in calls)

    @patch("subprocess.run")
    def test_install_handles_error(self, mock_run: MagicMock) -> None:
        """Test install handles subprocess errors."""
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.side_effect = OSError("Failed")

        result = manager.install()

        assert result is False

    @patch("subprocess.run")
    def test_uninstall_removes_service(self, mock_run: MagicMock) -> None:
        """Test uninstall removes service file."""
        fs = MockFileSystem()
        service_path = str(Path.home() / ".config/systemd/user" / f"{SERVICE_NAME}.service")
        fs.files[service_path] = "content"
        manager = LinuxServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.uninstall()

        assert result is True
        assert service_path in fs.removed

    @patch("subprocess.run")
    def test_start_runs_systemctl(self, mock_run: MagicMock) -> None:
        """Test start runs systemctl start."""
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.start()

        assert result is True
        assert "start" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_stop_runs_systemctl(self, mock_run: MagicMock) -> None:
        """Test stop runs systemctl stop."""
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.stop()

        assert result is True
        assert "stop" in str(mock_run.call_args)

    def test_status_not_installed(self) -> None:
        """Test status when service not installed."""
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)

        status = manager.status()

        assert status["installed"] is False
        assert status["running"] is False
        assert "not installed" in status["status"]

    @patch("subprocess.run")
    def test_status_installed_running(self, mock_run: MagicMock) -> None:
        """Test status when service is installed and running."""
        fs = MockFileSystem()
        service_path = str(Path.home() / ".config/systemd/user" / f"{SERVICE_NAME}.service")
        fs.files[service_path] = "content"
        manager = LinuxServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0, stdout="active")

        status = manager.status()

        assert status["installed"] is True
        assert status["running"] is True


# ============================================================
# macOS ServiceManager Tests
# ============================================================


class TestMacOSServiceManager:
    """Tests for macOS launchd service manager."""

    def test_init_sets_paths(self) -> None:
        """Test initialization sets correct paths."""
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)

        assert "Library/LaunchAgents" in str(manager._agents_dir)
        assert ".plist" in str(manager._plist_file)

    @patch("subprocess.run")
    def test_install_creates_plist(self, mock_run: MagicMock) -> None:
        """Test install creates launchd plist file."""
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.install()

        assert result is True
        assert len(fs.files) == 1
        plist_content = list(fs.files.values())[0]
        assert "com.ai-session-tracker.mcp" in plist_content

    @patch("subprocess.run")
    def test_uninstall_removes_plist(self, mock_run: MagicMock) -> None:
        """Test uninstall removes plist file."""
        fs = MockFileSystem()
        plist_path = str(Path.home() / "Library/LaunchAgents/com.ai-session-tracker.mcp.plist")
        fs.files[plist_path] = "content"
        manager = MacOSServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.uninstall()

        assert result is True
        assert plist_path in fs.removed

    @patch("subprocess.run")
    def test_start_runs_launchctl(self, mock_run: MagicMock) -> None:
        """Test start runs launchctl start."""
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.start()

        assert result is True
        assert "start" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_stop_runs_launchctl(self, mock_run: MagicMock) -> None:
        """Test stop runs launchctl stop."""
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.stop()

        assert result is True
        assert "stop" in str(mock_run.call_args)

    def test_status_not_installed(self) -> None:
        """Test status when service not installed."""
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)

        status = manager.status()

        assert status["installed"] is False
        assert status["running"] is False


# ============================================================
# Windows ServiceManager Tests
# ============================================================


class TestWindowsServiceManager:
    """Tests for Windows Task Scheduler service manager."""

    def test_init_sets_task_name(self) -> None:
        """Test initialization sets correct task name."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)

        assert manager._task_name == "AISessionTracker"

    @patch("subprocess.run")
    def test_install_creates_task(self, mock_run: MagicMock) -> None:
        """Test install creates scheduled task."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.install()

        assert result is True
        assert "schtasks" in str(mock_run.call_args)
        assert "/create" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_uninstall_removes_task(self, mock_run: MagicMock) -> None:
        """Test uninstall removes scheduled task."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.uninstall()

        assert result is True
        assert "/delete" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_start_runs_task(self, mock_run: MagicMock) -> None:
        """Test start runs scheduled task."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.start()

        assert result is True
        assert "/run" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_stop_ends_task(self, mock_run: MagicMock) -> None:
        """Test stop ends scheduled task."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.stop()

        assert result is True
        assert "/end" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_status_not_installed(self, mock_run: MagicMock) -> None:
        """Test status when task not installed."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=1)

        status = manager.status()

        assert status["installed"] is False


# ============================================================
# Factory Function Tests
# ============================================================


class TestGetServiceManager:
    """Tests for get_service_manager factory function."""

    @patch("ai_session_tracker_mcp.service.sys.platform", "linux")
    def test_returns_linux_manager(self) -> None:
        """Test returns LinuxServiceManager on Linux."""
        manager = get_service_manager()
        assert isinstance(manager, LinuxServiceManager)

    @patch("ai_session_tracker_mcp.service.sys.platform", "darwin")
    def test_returns_macos_manager(self) -> None:
        """Test returns MacOSServiceManager on macOS."""
        manager = get_service_manager()
        assert isinstance(manager, MacOSServiceManager)

    @patch("ai_session_tracker_mcp.service.sys.platform", "win32")
    @patch("ai_session_tracker_mcp.service.os.name", "nt")
    def test_returns_windows_manager(self) -> None:
        """Test returns WindowsServiceManager on Windows."""
        manager = get_service_manager()
        assert isinstance(manager, WindowsServiceManager)

    @patch("ai_session_tracker_mcp.service.sys.platform", "freebsd")
    @patch("ai_session_tracker_mcp.service.os.name", "posix")
    def test_unsupported_platform_raises(self) -> None:
        """Test raises NotImplementedError on unsupported platform."""
        with pytest.raises(NotImplementedError, match="Unsupported platform"):
            get_service_manager()


# ============================================================
# Template Tests
# ============================================================


class TestServiceTemplates:
    """Tests for service configuration templates."""

    def test_systemd_template_has_required_sections(self) -> None:
        """Test systemd template has all required sections."""
        assert "[Unit]" in SYSTEMD_SERVICE_TEMPLATE
        assert "[Service]" in SYSTEMD_SERVICE_TEMPLATE
        assert "[Install]" in SYSTEMD_SERVICE_TEMPLATE
        assert "ExecStart" in SYSTEMD_SERVICE_TEMPLATE

    def test_launchd_template_has_required_keys(self) -> None:
        """Test launchd template has all required keys."""
        assert "Label" in LAUNCHD_PLIST_TEMPLATE
        assert "ProgramArguments" in LAUNCHD_PLIST_TEMPLATE
        assert "RunAtLoad" in LAUNCHD_PLIST_TEMPLATE


# ============================================================
# Error Path Tests (CalledProcessError handling)
# ============================================================


class TestLinuxServiceManagerErrors:
    """Tests for Linux service manager error handling."""

    @patch("subprocess.run")
    def test_uninstall_handles_error(self, mock_run: MagicMock) -> None:
        """Test uninstall handles subprocess errors."""
        fs = MockFileSystem()
        service_path = str(Path.home() / ".config/systemd/user" / f"{SERVICE_NAME}.service")
        fs.files[service_path] = "content"
        manager = LinuxServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")

        result = manager.uninstall()

        assert result is False

    @patch("subprocess.run")
    def test_start_handles_error(self, mock_run: MagicMock) -> None:
        """Test start handles subprocess errors."""
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")

        result = manager.start()

        assert result is False

    @patch("subprocess.run")
    def test_stop_handles_error(self, mock_run: MagicMock) -> None:
        """Test stop handles subprocess errors."""
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")

        result = manager.stop()

        assert result is False

    @patch("subprocess.run")
    def test_status_handles_error(self, mock_run: MagicMock) -> None:
        """Test status handles subprocess errors."""
        fs = MockFileSystem()
        service_path = str(Path.home() / ".config/systemd/user" / f"{SERVICE_NAME}.service")
        fs.files[service_path] = "content"
        manager = LinuxServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")

        status = manager.status()

        assert status["installed"] is True
        assert status["running"] is False
        assert "Unable to determine status" in status["status"]


class TestMacOSServiceManagerErrors:
    """Tests for macOS service manager error handling."""

    @patch("subprocess.run")
    def test_install_handles_error(self, mock_run: MagicMock) -> None:
        """Test install handles subprocess errors."""
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

        result = manager.install()

        assert result is False

    @patch("subprocess.run")
    def test_uninstall_handles_error(self, mock_run: MagicMock) -> None:
        """Test uninstall handles subprocess errors."""
        fs = MockFileSystem()
        plist_path = str(Path.home() / "Library/LaunchAgents/com.ai-session-tracker.mcp.plist")
        fs.files[plist_path] = "content"
        manager = MacOSServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

        result = manager.uninstall()

        assert result is False

    @patch("subprocess.run")
    def test_start_handles_error(self, mock_run: MagicMock) -> None:
        """Test start handles subprocess errors."""
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

        result = manager.start()

        assert result is False

    @patch("subprocess.run")
    def test_stop_handles_error(self, mock_run: MagicMock) -> None:
        """Test stop handles subprocess errors."""
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

        result = manager.stop()

        assert result is False

    @patch("subprocess.run")
    def test_status_handles_error(self, mock_run: MagicMock) -> None:
        """Test status handles subprocess errors."""
        fs = MockFileSystem()
        plist_path = str(Path.home() / "Library/LaunchAgents/com.ai-session-tracker.mcp.plist")
        fs.files[plist_path] = "content"
        manager = MacOSServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

        status = manager.status()

        assert status["installed"] is True
        assert status["running"] is False
        assert "Unable to determine status" in status["status"]


class TestWindowsServiceManagerErrors:
    """Tests for Windows service manager error handling."""

    @patch("subprocess.run")
    def test_install_handles_error(self, mock_run: MagicMock) -> None:
        """Test install handles subprocess errors."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        result = manager.install()

        assert result is False

    @patch("subprocess.run")
    def test_uninstall_handles_error(self, mock_run: MagicMock) -> None:
        """Test uninstall handles subprocess errors."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        result = manager.uninstall()

        assert result is False

    @patch("subprocess.run")
    def test_start_handles_error(self, mock_run: MagicMock) -> None:
        """Test start handles subprocess errors."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        result = manager.start()

        assert result is False

    @patch("subprocess.run")
    def test_stop_handles_error(self, mock_run: MagicMock) -> None:
        """Test stop handles subprocess errors."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        result = manager.stop()

        assert result is False

    @patch("subprocess.run")
    def test_status_handles_error(self, mock_run: MagicMock) -> None:
        """Test status handles CalledProcessError."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        status = manager.status()

        assert status["installed"] is False
        assert status["running"] is False
        assert "Unable to determine status" in status["status"]

    @patch("subprocess.run")
    def test_status_installed_and_running(self, mock_run: MagicMock) -> None:
        """Test status when task is installed and running."""
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0, stdout='"Task","Running","Ready"')

        status = manager.status()

        assert status["installed"] is True
        assert status["running"] is True
        assert "running" in status["status"].lower()
