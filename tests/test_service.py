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
    """In-memory filesystem mock for deterministic service manager testing.

    Provides a controlled filesystem abstraction that replaces real I/O operations
    during testing. Tracks all file operations (writes, reads, removes, renames) in
    memory, enabling assertions about service manager file interactions without
    touching the actual filesystem.

    Business context:
    Service managers create/remove platform-specific config files (systemd units,
    launchd plists, schtasks XML). This mock ensures tests verify file operations
    without requiring root privileges or polluting the host filesystem.

    Implementation details:
    - ``files`` dict maps path strings to content strings (simulates file existence).
    - ``removed`` list tracks deletion calls for assertion in uninstall tests.
    - All methods mirror the interface expected by ServiceManager subclasses.
    """

    def __init__(self) -> None:
        """Initialize mock filesystem with empty file store and removal tracker.

        Sets up the in-memory data structures used to simulate filesystem
        operations throughout service manager tests.

        Args:
            None — the mock starts empty; tests populate it via write_text()
            or direct dict assignment before exercising service managers.

        Returns:
            None — constructor; initializes instance attributes.

        Raises:
            No exceptions — initialization is unconditional.

        Business context:
            Each test starts with a fresh MockFileSystem to ensure isolation.
            Pre-populating files simulates "already installed" states, while
            empty filesystems simulate clean environments.

        Implementation details:
            - ``files`` (dict[str, str]): maps path → content for simulated
              file existence and reads. Keys are full path strings matching
              what ServiceManager subclasses compute internally.
            - ``removed`` (list[str]): tracks paths passed to ``remove()``
              for asserting that uninstall operations clean up correctly.

        Example::

            fs = MockFileSystem()
            fs.files["/path/to/service"] = "[Unit]\\nDescription=test"
            assert fs.exists("/path/to/service")
            fs.remove("/path/to/service")
            assert "/path/to/service" in fs.removed
        """
        self.files: dict[str, str] = {}
        self.removed: list[str] = []

    def exists(self, path: str) -> bool:
        """Check whether a path exists in the mock filesystem.

        Args:
            path: Filesystem path to check for existence.

        Returns:
            True if the path has been written to the mock store, False otherwise.

        Business context:
            Service managers check file existence to determine install state
            (e.g., whether a systemd unit file is present).
        """
        return path in self.files

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        """Simulate directory creation (no-op in mock).

        Args:
            path: Directory path to create.
            exist_ok: If True, suppress errors when directory already exists.

        Business context:
            Service managers call makedirs before writing config files to ensure
            parent directories exist (e.g., ~/.config/systemd/user/). The mock
            no-ops this since in-memory dict storage doesn't need directories.
        """
        pass

    def read_text(self, path: str) -> str:
        """Read content of a file from the mock filesystem.

        Args:
            path: Filesystem path to read.

        Returns:
            The string content stored at the path, or empty string if not found.

        Business context:
            Used by service managers to read back config files for validation
            or template rendering verification.
        """
        return self.files.get(path, "")

    def write_text(self, path: str, content: str) -> None:
        """Write content to a file in the mock filesystem.

        Args:
            path: Filesystem path to write to.
            content: String content to store.

        Business context:
            Service managers write platform-specific config files (systemd units,
            launchd plists) during installation. This mock captures the written
            content for assertion in tests.
        """
        self.files[path] = content

    def remove(self, path: str) -> None:
        """Remove a file from the mock filesystem and track the removal.

        Args:
            path: Filesystem path to remove.

        Business context:
            Service managers remove config files during uninstallation. The mock
            both removes from the files dict and appends to the removed list,
            enabling assertions that verify correct cleanup behavior.
        """
        self.removed.append(path)
        if path in self.files:
            del self.files[path]

    def rename(self, src: str, dst: str) -> None:
        """Rename/move a file in the mock filesystem.

        Args:
            src: Source path to rename from.
            dst: Destination path to rename to.

        Business context:
            Supports atomic file update patterns where service managers write
            to a temporary path then rename to the final location, ensuring
            config file integrity during updates.
        """
        if src in self.files:
            self.files[dst] = self.files[src]
            del self.files[src]


# ============================================================
# Base ServiceManager Tests
# ============================================================


class TestServiceManagerBase:
    """Tests for ServiceManager base class abstract method contracts.

    Validates that the ServiceManager ABC enforces the Template Method pattern
    by raising NotImplementedError for all lifecycle methods, and that the
    shared _get_executable_command() helper resolves the correct invocation
    path for service config file generation.
    """

    def test_install_raises_not_implemented(self) -> None:
        """Verifies install() raises NotImplementedError on the base class.

        Tests that the abstract contract is enforced by attempting to call
        install() directly on the base ServiceManager.

        Business context:
        The base class defines the interface; each platform subclass must
        provide its own install logic. Failing to override must produce a
        clear error rather than silently succeeding.

        Arrangement:
        1. Instantiate the bare ServiceManager (no subclass).

        Action:
        Call install() on the base instance.

        Assertion Strategy:
        Validates the abstract contract by confirming:
        - NotImplementedError is raised, preventing accidental base usage.

        Testing Principle:
        Validates interface enforcement, ensuring subclasses cannot skip
        implementing required lifecycle methods.
        """
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.install()

    def test_uninstall_raises_not_implemented(self) -> None:
        """Verifies uninstall() raises NotImplementedError on the base class.

        Tests that the abstract contract is enforced by attempting to call
        uninstall() directly on the base ServiceManager.

        Business context:
        Uninstall must be implemented per-platform to correctly remove
        service artifacts (systemd units, plists, scheduled tasks).

        Arrangement:
        1. Instantiate the bare ServiceManager (no subclass).

        Action:
        Call uninstall() on the base instance.

        Assertion Strategy:
        Validates the abstract contract by confirming:
        - NotImplementedError is raised, preventing accidental base usage.

        Testing Principle:
        Validates interface enforcement, ensuring platform-specific cleanup
        cannot be accidentally bypassed.
        """
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.uninstall()

    def test_start_raises_not_implemented(self) -> None:
        """Verifies start() raises NotImplementedError on the base class.

        Tests that the abstract contract is enforced by attempting to call
        start() directly on the base ServiceManager.

        Business context:
        Starting a service requires platform-specific system calls
        (systemctl, launchctl, schtasks). The base class cannot know which.

        Arrangement:
        1. Instantiate the bare ServiceManager (no subclass).

        Action:
        Call start() on the base instance.

        Assertion Strategy:
        Validates the abstract contract by confirming:
        - NotImplementedError is raised for the unimplemented operation.

        Testing Principle:
        Validates interface enforcement, ensuring service start requires
        a concrete platform implementation.
        """
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.start()

    def test_stop_raises_not_implemented(self) -> None:
        """Verifies stop() raises NotImplementedError on the base class.

        Tests that the abstract contract is enforced by attempting to call
        stop() directly on the base ServiceManager.

        Business context:
        Stopping a service requires platform-specific process management
        (systemctl stop, launchctl remove, schtasks /end).

        Arrangement:
        1. Instantiate the bare ServiceManager (no subclass).

        Action:
        Call stop() on the base instance.

        Assertion Strategy:
        Validates the abstract contract by confirming:
        - NotImplementedError is raised for the unimplemented operation.

        Testing Principle:
        Validates interface enforcement, ensuring service stop requires
        a concrete platform implementation.
        """
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.stop()

    def test_status_raises_not_implemented(self) -> None:
        """Verifies status() raises NotImplementedError on the base class.

        Tests that the abstract contract is enforced by attempting to call
        status() directly on the base ServiceManager.

        Business context:
        Status checks query platform-specific service registries. The base
        class cannot determine installation or running state generically.

        Arrangement:
        1. Instantiate the bare ServiceManager (no subclass).

        Action:
        Call status() on the base instance.

        Assertion Strategy:
        Validates the abstract contract by confirming:
        - NotImplementedError is raised for the unimplemented operation.

        Testing Principle:
        Validates interface enforcement, ensuring status queries require
        a concrete platform implementation.
        """
        manager = ServiceManager()
        with pytest.raises(NotImplementedError):
            manager.status()

    def test_get_executable_command_with_script(self) -> None:
        """Verifies _get_executable_command returns script path when bin exists.

        Tests the preferred executable resolution path where an installed
        console_script entry point is found in the Python environment's bin
        directory.

        Business context:
        Service config files (systemd units, plists) need the correct
        ExecStart/ProgramArguments path. When installed via pip, the
        ``server`` script in the bin directory is the canonical entry point.

        Arrangement:
        1. Create ServiceManager with mock filesystem.
        2. Patch Path.exists to return True (simulating bin/server exists).

        Action:
        Call _get_executable_command() to resolve the executable path.

        Assertion Strategy:
        Validates executable resolution by confirming:
        - The returned command references the ``server`` script entry point.

        Testing Principle:
        Validates the preferred path resolution, ensuring service configs
        point to the installed console script when available.
        """
        fs = MockFileSystem()
        manager = ServiceManager(fs)

        # Mock the bin directory check
        with patch.object(Path, "exists", return_value=True):
            cmd = manager._get_executable_command()
            assert "server" in cmd

    def test_get_executable_command_fallback(self) -> None:
        """Verifies _get_executable_command falls back to ``python -m`` invocation.

        Tests the fallback executable resolution path when no installed
        console_script entry point exists in the bin directory.

        Business context:
        During development or editable installs, the bin script may not
        exist. The fallback ``python -m ai_session_tracker_mcp`` ensures
        the service can still be started via module invocation.

        Arrangement:
        1. Create ServiceManager with mock filesystem.
        2. Patch Path.exists to return False (simulating no bin/server).

        Action:
        Call _get_executable_command() to resolve the executable path.

        Assertion Strategy:
        Validates fallback resolution by confirming:
        - The command includes ``-m`` flag for module invocation.
        - The command references ``ai_session_tracker_mcp`` as the module.

        Testing Principle:
        Validates graceful degradation, ensuring service configuration
        works even without installed entry points.
        """
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
    """Tests for Linux systemd service manager lifecycle operations.

    Validates that LinuxServiceManager correctly creates, removes, starts,
    stops, and queries systemd user services. Uses MockFileSystem for file
    I/O and patched subprocess.run for systemctl command verification.
    """

    def test_init_sets_paths(self) -> None:
        """Verifies LinuxServiceManager sets correct systemd file paths on init.

        Tests that construction computes the proper user-level systemd
        directory and service file paths based on the SERVICE_NAME constant.

        Business context:
        Systemd user services must be placed in ~/.config/systemd/user/
        with a .service extension. Incorrect paths cause silent install
        failures that are difficult to diagnose.

        Arrangement:
        1. Create LinuxServiceManager with mock filesystem.

        Action:
        Inspect the manager's internal path attributes after construction.

        Assertion Strategy:
        Validates path computation by confirming:
        - Service directory includes the standard systemd user path.
        - Service file includes the expected SERVICE_NAME.service filename.

        Testing Principle:
        Validates constructor correctness, ensuring path derivation logic
        produces valid systemd-compatible locations.
        """
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)

        assert ".config/systemd/user" in str(manager._service_dir)
        assert f"{SERVICE_NAME}.service" in str(manager._service_file)

    @patch("subprocess.run")
    def test_install_creates_service_file(self, mock_run: MagicMock) -> None:
        """Verifies install() writes a valid systemd unit file to disk.

        Tests that the install operation generates a properly formatted
        systemd service unit containing required sections and metadata.

        Business context:
        The systemd unit file is the primary artifact for Linux service
        registration. It must contain [Unit], [Service], and [Install]
        sections with the correct description to be recognized by systemd.

        Arrangement:
        1. Create LinuxServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call install() to write the service file and run systemctl commands.

        Assertion Strategy:
        Validates file creation by confirming:
        - install() returns True indicating success.
        - Exactly one file was written to the mock filesystem.
        - Written content contains [Unit] section header.
        - Written content contains the SERVICE_DESCRIPTION.

        Testing Principle:
        Validates the primary install artifact, ensuring the generated
        systemd unit file is structurally correct.
        """
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
        """Verifies install() executes daemon-reload and enable via systemctl.

        Tests that after writing the unit file, install triggers the
        necessary systemctl commands to register and enable the service.

        Business context:
        After writing a new unit file, systemd requires ``daemon-reload``
        to discover it and ``enable`` to set it for automatic startup.
        Missing either step leaves the service unregistered or non-persistent.

        Arrangement:
        1. Create LinuxServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed for all calls.

        Action:
        Call install() which writes the file then executes systemctl commands.

        Assertion Strategy:
        Validates systemctl integration by confirming:
        - A daemon-reload command was issued to refresh systemd's config cache.
        - An enable command was issued to persist the service across reboots.

        Testing Principle:
        Validates command orchestration, ensuring the full install sequence
        completes both file creation and systemd registration.
        """
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        manager.install()

        calls = mock_run.call_args_list
        assert any("daemon-reload" in str(call) for call in calls)
        assert any("enable" in str(call) for call in calls)

    @patch("subprocess.run")
    def test_install_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies install() returns False when subprocess raises OSError.

        Tests the error recovery path where system commands fail due to
        missing binaries or permission issues.

        Business context:
        Install may fail on systems without systemd or with restricted
        permissions. The manager must catch errors and return a clear
        failure signal rather than crashing the application.

        Arrangement:
        1. Create LinuxServiceManager with mock filesystem.
        2. Configure subprocess.run to raise OSError("Failed").

        Action:
        Call install() which encounters the simulated OS-level failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - install() returns False instead of propagating the exception.

        Testing Principle:
        Validates graceful degradation, ensuring system-level errors
        are caught and reported as actionable boolean results.
        """
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.side_effect = OSError("Failed")

        result = manager.install()

        assert result is False

    @patch("subprocess.run")
    def test_uninstall_removes_service(self, mock_run: MagicMock) -> None:
        """Verifies uninstall() removes the systemd service file from disk.

        Tests that uninstall correctly disables and deletes the service
        unit file when it exists in the expected location.

        Business context:
        Clean uninstallation requires removing the unit file to prevent
        systemd from attempting to start a non-existent service. Leftover
        files cause confusing systemctl status output.

        Arrangement:
        1. Pre-populate the mock filesystem with a service file at the expected path.
        2. Create LinuxServiceManager and stub subprocess.run to succeed.

        Action:
        Call uninstall() to disable and remove the service.

        Assertion Strategy:
        Validates cleanup by confirming:
        - uninstall() returns True indicating successful removal.
        - The service file path appears in the mock's removed list.

        Testing Principle:
        Validates complete cleanup, ensuring uninstall leaves no orphaned
        systemd artifacts on the filesystem.
        """
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
        """Verifies start() executes ``systemctl --user start`` for the service.

        Tests that the start operation delegates to systemctl with the
        correct start subcommand.

        Business context:
        Starting the service activates the MCP session tracker daemon,
        enabling automatic session monitoring. The command must use the
        ``--user`` flag for user-level service management.

        Arrangement:
        1. Create LinuxServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call start() to issue the systemctl start command.

        Assertion Strategy:
        Validates command execution by confirming:
        - start() returns True indicating the command succeeded.
        - The subprocess call includes the ``start`` subcommand.

        Testing Principle:
        Validates correct system command delegation, ensuring the
        manager translates start() into the proper systemctl invocation.
        """
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.start()

        assert result is True
        assert "start" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_stop_runs_systemctl(self, mock_run: MagicMock) -> None:
        """Verifies stop() executes ``systemctl --user stop`` for the service.

        Tests that the stop operation delegates to systemctl with the
        correct stop subcommand.

        Business context:
        Stopping the service halts session tracking, which may be needed
        for maintenance, debugging, or resource conservation. Must use
        the ``--user`` flag for user-level services.

        Arrangement:
        1. Create LinuxServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call stop() to issue the systemctl stop command.

        Assertion Strategy:
        Validates command execution by confirming:
        - stop() returns True indicating the command succeeded.
        - The subprocess call includes the ``stop`` subcommand.

        Testing Principle:
        Validates correct system command delegation, ensuring the
        manager translates stop() into the proper systemctl invocation.
        """
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.stop()

        assert result is True
        assert "stop" in str(mock_run.call_args)

    def test_status_not_installed(self) -> None:
        """Verifies status() reports not-installed when no service file exists.

        Tests the status detection path where the systemd unit file has
        not been written to the expected location.

        Business context:
        Users need clear feedback about service state. When no unit file
        exists, the status must unambiguously indicate the service is not
        installed rather than reporting a misleading error.

        Arrangement:
        1. Create LinuxServiceManager with empty mock filesystem (no service file).

        Action:
        Call status() to query the current service state.

        Assertion Strategy:
        Validates state detection by confirming:
        - installed field is False (no unit file found).
        - running field is False (can't run if not installed).
        - Status message contains "not installed" for clear user feedback.

        Testing Principle:
        Validates absence detection, ensuring the manager correctly
        distinguishes between not-installed and failed states.
        """
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)

        status = manager.status()

        assert status["installed"] is False
        assert status["running"] is False
        assert "not installed" in status["status"]

    @patch("subprocess.run")
    def test_status_installed_running(self, mock_run: MagicMock) -> None:
        """Verifies status() reports installed and running when systemctl confirms active.

        Tests the happy-path status detection where the service file exists
        and systemctl reports the service as active.

        Business context:
        The status endpoint is the primary diagnostic tool for users and
        monitoring systems. It must accurately reflect both installation
        state (file exists) and runtime state (systemctl active check).

        Arrangement:
        1. Pre-populate mock filesystem with the service file at the expected path.
        2. Create LinuxServiceManager and stub subprocess.run to return "active" stdout.

        Action:
        Call status() to query systemd for the current service state.

        Assertion Strategy:
        Validates combined state by confirming:
        - installed field is True (unit file found in filesystem).
        - running field is True (systemctl reports active status).

        Testing Principle:
        Validates the golden path, ensuring accurate reporting when
        both installation and runtime conditions are satisfied.
        """
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
    """Tests for macOS launchd service manager lifecycle operations.

    Validates that MacOSServiceManager correctly creates, removes, starts,
    stops, and queries launchd agents. Uses MockFileSystem for plist file
    I/O and patched subprocess.run for launchctl command verification.
    """

    def test_init_sets_paths(self) -> None:
        """Verifies MacOSServiceManager sets correct launchd agent paths on init.

        Tests that construction computes the proper LaunchAgents directory
        and plist file paths based on the service naming convention.

        Business context:
        macOS launchd agents must be placed in ~/Library/LaunchAgents/
        with a .plist extension and a reverse-DNS label. Incorrect paths
        prevent launchd from discovering the agent.

        Arrangement:
        1. Create MacOSServiceManager with mock filesystem.

        Action:
        Inspect the manager's internal path attributes after construction.

        Assertion Strategy:
        Validates path computation by confirming:
        - Agents directory includes Library/LaunchAgents.
        - Plist file path includes the .plist extension.

        Testing Principle:
        Validates constructor correctness, ensuring path derivation logic
        produces valid launchd-compatible locations.
        """
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)

        assert "Library/LaunchAgents" in str(manager._agents_dir)
        assert ".plist" in str(manager._plist_file)

    @patch("subprocess.run")
    def test_install_creates_plist(self, mock_run: MagicMock) -> None:
        """Verifies install() writes a valid launchd plist file to disk.

        Tests that the install operation generates a properly formatted
        plist XML file containing the service label identifier.

        Business context:
        The plist file is the primary artifact for macOS service registration.
        It must contain the correct Label for launchd to identify and manage
        the agent. Missing or malformed plists silently fail to load.

        Arrangement:
        1. Create MacOSServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call install() to write the plist file and run launchctl commands.

        Assertion Strategy:
        Validates file creation by confirming:
        - install() returns True indicating success.
        - Exactly one file was written to the mock filesystem.
        - Written content contains the service identifier label.

        Testing Principle:
        Validates the primary install artifact, ensuring the generated
        plist file contains the required launchd service identifier.
        """
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
        """Verifies uninstall() removes the launchd plist file from disk.

        Tests that uninstall correctly unloads and deletes the plist file
        when it exists at the expected LaunchAgents path.

        Business context:
        Clean uninstallation on macOS requires both unloading the agent
        from launchd and removing the plist file. Leftover plists cause
        launchd to repeatedly attempt loading a non-existent executable.

        Arrangement:
        1. Pre-populate the mock filesystem with a plist at the expected path.
        2. Create MacOSServiceManager and stub subprocess.run to succeed.

        Action:
        Call uninstall() to unload and remove the agent plist.

        Assertion Strategy:
        Validates cleanup by confirming:
        - uninstall() returns True indicating successful removal.
        - The plist file path appears in the mock's removed list.

        Testing Principle:
        Validates complete cleanup, ensuring uninstall leaves no orphaned
        launchd artifacts on the filesystem.
        """
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
        """Verifies start() executes launchctl with the start subcommand.

        Tests that the start operation delegates to launchctl to begin
        running the launchd agent.

        Business context:
        Starting the macOS agent activates session tracking via launchd.
        The command must use the correct launchctl syntax to bootstrap
        or start the agent within the user's GUI session.

        Arrangement:
        1. Create MacOSServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call start() to issue the launchctl start command.

        Assertion Strategy:
        Validates command execution by confirming:
        - start() returns True indicating the command succeeded.
        - The subprocess call includes the ``start`` subcommand.

        Testing Principle:
        Validates correct system command delegation, ensuring the
        manager translates start() into the proper launchctl invocation.
        """
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.start()

        assert result is True
        assert "start" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_stop_runs_launchctl(self, mock_run: MagicMock) -> None:
        """Verifies stop() executes launchctl with the stop subcommand.

        Tests that the stop operation delegates to launchctl to halt the
        running launchd agent.

        Business context:
        Stopping the macOS agent halts session tracking, needed for
        maintenance or debugging. The command must correctly unload or
        stop the agent without corrupting launchd's state.

        Arrangement:
        1. Create MacOSServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call stop() to issue the launchctl stop command.

        Assertion Strategy:
        Validates command execution by confirming:
        - stop() returns True indicating the command succeeded.
        - The subprocess call includes the ``stop`` subcommand.

        Testing Principle:
        Validates correct system command delegation, ensuring the
        manager translates stop() into the proper launchctl invocation.
        """
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.stop()

        assert result is True
        assert "stop" in str(mock_run.call_args)

    def test_status_not_installed(self) -> None:
        """Verifies status() reports not-installed when no plist file exists.

        Tests the status detection path where the launchd plist has not
        been written to the expected LaunchAgents location.

        Business context:
        Users need clear feedback about macOS agent state. When no plist
        exists, the status must indicate the agent is not installed rather
        than reporting confusing launchctl errors.

        Arrangement:
        1. Create MacOSServiceManager with empty mock filesystem (no plist).

        Action:
        Call status() to query the current agent state.

        Assertion Strategy:
        Validates state detection by confirming:
        - installed field is False (no plist found).
        - running field is False (can't run if not installed).

        Testing Principle:
        Validates absence detection, ensuring the manager correctly
        identifies an uninstalled state on macOS.
        """
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)

        status = manager.status()

        assert status["installed"] is False
        assert status["running"] is False


# ============================================================
# Windows ServiceManager Tests
# ============================================================


class TestWindowsServiceManager:
    """Tests for Windows Task Scheduler service manager lifecycle operations.

    Validates that WindowsServiceManager correctly creates, removes, starts,
    stops, and queries scheduled tasks. Uses MockFileSystem for any file I/O
    and patched subprocess.run for schtasks command verification.
    """

    def test_init_sets_task_name(self) -> None:
        """Verifies WindowsServiceManager sets the correct scheduled task name.

        Tests that construction assigns the canonical task name used for
        all schtasks operations.

        Business context:
        Windows Task Scheduler identifies tasks by name. The task name
        must be consistent across install, start, stop, uninstall, and
        status operations to avoid orphaned tasks or misidentification.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.

        Action:
        Inspect the manager's _task_name attribute after construction.

        Assertion Strategy:
        Validates naming by confirming:
        - _task_name equals "AISessionTracker" (the canonical identifier).

        Testing Principle:
        Validates constructor correctness, ensuring the task name constant
        is properly assigned for downstream schtasks operations.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)

        assert manager._task_name == "AISessionTracker"

    @patch("subprocess.run")
    def test_install_creates_task(self, mock_run: MagicMock) -> None:
        """Verifies install() creates a Windows scheduled task via schtasks.

        Tests that the install operation executes schtasks with the /create
        flag to register a new scheduled task.

        Business context:
        Windows lacks systemd/launchd equivalents; Task Scheduler is the
        standard mechanism for persistent background services. The /create
        flag with appropriate arguments registers the session tracker.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call install() to create the scheduled task via schtasks.

        Assertion Strategy:
        Validates task creation by confirming:
        - install() returns True indicating success.
        - The subprocess call references ``schtasks`` executable.
        - The subprocess call includes the ``/create`` flag.

        Testing Principle:
        Validates correct command construction, ensuring the install
        operation uses the proper schtasks syntax for task registration.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.install()

        assert result is True
        assert "schtasks" in str(mock_run.call_args)
        assert "/create" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_uninstall_removes_task(self, mock_run: MagicMock) -> None:
        """Verifies uninstall() removes the Windows scheduled task via schtasks.

        Tests that the uninstall operation executes schtasks with the /delete
        flag to remove the registered task.

        Business context:
        Clean uninstallation on Windows requires deleting the scheduled
        task to prevent Task Scheduler from continuing to invoke a
        removed executable. Orphaned tasks generate error events.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call uninstall() to delete the scheduled task.

        Assertion Strategy:
        Validates task removal by confirming:
        - uninstall() returns True indicating success.
        - The subprocess call includes the ``/delete`` flag.

        Testing Principle:
        Validates cleanup correctness, ensuring the uninstall operation
        removes the task registration from Windows Task Scheduler.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.uninstall()

        assert result is True
        assert "/delete" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_start_runs_task(self, mock_run: MagicMock) -> None:
        """Verifies start() runs the Windows scheduled task via schtasks /run.

        Tests that the start operation triggers immediate task execution
        using the schtasks /run flag.

        Business context:
        Starting the session tracker on Windows requires triggering the
        scheduled task's immediate execution. The /run flag forces the
        task to start now rather than waiting for its schedule trigger.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call start() to trigger immediate task execution.

        Assertion Strategy:
        Validates command execution by confirming:
        - start() returns True indicating the task was triggered.
        - The subprocess call includes the ``/run`` flag.

        Testing Principle:
        Validates correct command syntax, ensuring start() uses the
        proper schtasks invocation for immediate task execution.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.start()

        assert result is True
        assert "/run" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_stop_ends_task(self, mock_run: MagicMock) -> None:
        """Verifies stop() terminates the Windows scheduled task via schtasks /end.

        Tests that the stop operation terminates a running task instance
        using the schtasks /end flag.

        Business context:
        Stopping the session tracker on Windows requires terminating the
        running task instance. The /end flag signals Task Scheduler to
        stop the currently executing task process.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Stub subprocess.run to succeed (returncode=0).

        Action:
        Call stop() to terminate the running task.

        Assertion Strategy:
        Validates command execution by confirming:
        - stop() returns True indicating the task was terminated.
        - The subprocess call includes the ``/end`` flag.

        Testing Principle:
        Validates correct command syntax, ensuring stop() uses the
        proper schtasks invocation for task termination.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0)

        result = manager.stop()

        assert result is True
        assert "/end" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_status_not_installed(self, mock_run: MagicMock) -> None:
        """Verifies status() reports not-installed when schtasks query fails.

        Tests the status detection path where schtasks returns a non-zero
        exit code, indicating the task is not registered.

        Business context:
        Windows Task Scheduler returns a non-zero exit code when querying
        a non-existent task. The manager must interpret this as "not installed"
        rather than an error condition.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Stub subprocess.run to return returncode=1 (task not found).

        Action:
        Call status() to query Task Scheduler for the task state.

        Assertion Strategy:
        Validates state detection by confirming:
        - installed field is False (schtasks query returned non-zero).

        Testing Principle:
        Validates absence detection, ensuring the manager correctly
        interprets schtasks exit codes as installation state.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=1)

        status = manager.status()

        assert status["installed"] is False


# ============================================================
# Factory Function Tests
# ============================================================


class TestGetServiceManager:
    """Tests for get_service_manager() factory function platform routing.

    Validates that the factory function correctly inspects sys.platform
    and os.name to return the appropriate ServiceManager subclass, and
    raises NotImplementedError for unsupported platforms.
    """

    @patch("ai_session_tracker_mcp.service.sys.platform", "linux")
    def test_returns_linux_manager(self) -> None:
        """Verifies get_service_manager() returns LinuxServiceManager on Linux.

        Tests that the factory correctly routes to the systemd-based manager
        when sys.platform reports "linux".

        Business context:
        The factory is the public API entry point for service management.
        Linux users expect systemd integration; returning the wrong manager
        would attempt launchctl or schtasks commands on a Linux host.

        Arrangement:
        1. Patch sys.platform to "linux" to simulate a Linux environment.

        Action:
        Call get_service_manager() to obtain a platform-specific manager.

        Assertion Strategy:
        Validates platform routing by confirming:
        - The returned instance is a LinuxServiceManager.

        Testing Principle:
        Validates factory pattern correctness, ensuring platform detection
        maps to the correct service management implementation.
        """
        manager = get_service_manager()
        assert isinstance(manager, LinuxServiceManager)

    @patch("ai_session_tracker_mcp.service.sys.platform", "darwin")
    def test_returns_macos_manager(self) -> None:
        """Verifies get_service_manager() returns MacOSServiceManager on macOS.

        Tests that the factory correctly routes to the launchd-based manager
        when sys.platform reports "darwin".

        Business context:
        macOS users expect launchd integration for agent management.
        Incorrect routing would attempt systemctl commands on macOS,
        producing confusing "command not found" errors.

        Arrangement:
        1. Patch sys.platform to "darwin" to simulate a macOS environment.

        Action:
        Call get_service_manager() to obtain a platform-specific manager.

        Assertion Strategy:
        Validates platform routing by confirming:
        - The returned instance is a MacOSServiceManager.

        Testing Principle:
        Validates factory pattern correctness, ensuring Darwin platform
        detection maps to launchd-based service management.
        """
        manager = get_service_manager()
        assert isinstance(manager, MacOSServiceManager)

    @patch("ai_session_tracker_mcp.service.sys.platform", "win32")
    @patch("ai_session_tracker_mcp.service.os.name", "nt")
    def test_returns_windows_manager(self) -> None:
        """Verifies get_service_manager() returns WindowsServiceManager on Windows.

        Tests that the factory correctly routes to the schtasks-based manager
        when sys.platform reports "win32" and os.name reports "nt".

        Business context:
        Windows users expect Task Scheduler integration. Both sys.platform
        and os.name must be checked since some Windows environments report
        differently (e.g., Cygwin, MSYS).

        Arrangement:
        1. Patch sys.platform to "win32" and os.name to "nt" for Windows simulation.

        Action:
        Call get_service_manager() to obtain a platform-specific manager.

        Assertion Strategy:
        Validates platform routing by confirming:
        - The returned instance is a WindowsServiceManager.

        Testing Principle:
        Validates factory pattern correctness, ensuring Windows platform
        detection maps to Task Scheduler-based service management.
        """
        manager = get_service_manager()
        assert isinstance(manager, WindowsServiceManager)

    @patch("ai_session_tracker_mcp.service.sys.platform", "freebsd")
    @patch("ai_session_tracker_mcp.service.os.name", "posix")
    def test_unsupported_platform_raises(self) -> None:
        """Verifies get_service_manager() raises NotImplementedError for unknown platforms.

        Tests that the factory produces a clear error when running on a
        platform that has no ServiceManager implementation.

        Business context:
        Platforms like FreeBSD, Solaris, or AIX are not supported. The
        factory must fail explicitly with a descriptive error rather than
        returning None or silently using an incompatible manager.

        Arrangement:
        1. Patch sys.platform to "freebsd" and os.name to "posix".

        Action:
        Call get_service_manager() on the unsupported platform.

        Assertion Strategy:
        Validates error handling by confirming:
        - NotImplementedError is raised with "Unsupported platform" message.

        Testing Principle:
        Validates fail-fast behavior, ensuring unsupported platforms
        produce clear, actionable error messages.
        """
        with pytest.raises(NotImplementedError, match="Unsupported platform"):
            get_service_manager()


# ============================================================
# Template Tests
# ============================================================


class TestServiceTemplates:
    """Tests for service configuration template structural correctness.

    Validates that the systemd and launchd templates contain all required
    sections and keys for their respective service management systems.
    These are compile-time checks that catch template corruption before
    runtime installation attempts.
    """

    def test_systemd_template_has_required_sections(self) -> None:
        """Verifies the systemd unit template contains all mandatory sections.

        Tests that the SYSTEMD_SERVICE_TEMPLATE string includes the three
        required INI-style sections and the ExecStart directive.

        Business context:
        A systemd unit file without [Unit], [Service], or [Install] sections
        will fail to load with cryptic systemctl errors. The ExecStart
        directive is mandatory — without it, systemd cannot start the service.

        Arrangement:
        1. Access the SYSTEMD_SERVICE_TEMPLATE module constant directly.

        Action:
        Inspect the template string for required section headers and directives.

        Assertion Strategy:
        Validates template structure by confirming:
        - [Unit] section present (metadata and dependencies).
        - [Service] section present (execution configuration).
        - [Install] section present (enablement/WantedBy configuration).
        - ExecStart directive present (the command to run).

        Testing Principle:
        Validates structural completeness, ensuring the template cannot
        silently produce invalid systemd unit files.
        """
        assert "[Unit]" in SYSTEMD_SERVICE_TEMPLATE
        assert "[Service]" in SYSTEMD_SERVICE_TEMPLATE
        assert "[Install]" in SYSTEMD_SERVICE_TEMPLATE
        assert "ExecStart" in SYSTEMD_SERVICE_TEMPLATE

    def test_launchd_template_has_required_keys(self) -> None:
        """Verifies the launchd plist template contains all mandatory XML keys.

        Tests that the LAUNCHD_PLIST_TEMPLATE string includes the essential
        plist keys for agent registration with macOS launchd.

        Business context:
        A launchd plist without Label, ProgramArguments, or RunAtLoad keys
        will either fail to load or not start automatically. Label is the
        unique identifier; ProgramArguments defines the command; RunAtLoad
        controls automatic startup.

        Arrangement:
        1. Access the LAUNCHD_PLIST_TEMPLATE module constant directly.

        Action:
        Inspect the template string for required plist XML keys.

        Assertion Strategy:
        Validates template structure by confirming:
        - Label key present (unique agent identifier).
        - ProgramArguments key present (executable and arguments).
        - RunAtLoad key present (auto-start on login).

        Testing Principle:
        Validates structural completeness, ensuring the template cannot
        silently produce invalid launchd plist files.
        """
        assert "Label" in LAUNCHD_PLIST_TEMPLATE
        assert "ProgramArguments" in LAUNCHD_PLIST_TEMPLATE
        assert "RunAtLoad" in LAUNCHD_PLIST_TEMPLATE


# ============================================================
# Error Path Tests (CalledProcessError handling)
# ============================================================


class TestLinuxServiceManagerErrors:
    """Tests for Linux service manager CalledProcessError handling.

    Validates that all LinuxServiceManager lifecycle operations gracefully
    handle subprocess.CalledProcessError exceptions from failed systemctl
    commands, returning appropriate failure signals instead of propagating.
    """

    @patch("subprocess.run")
    def test_uninstall_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies uninstall() returns False when systemctl raises CalledProcessError.

        Tests error recovery when the systemctl disable/stop commands fail
        during service removal, e.g., due to permission issues or systemd
        being in a degraded state.

        Business context:
        Uninstall may encounter CalledProcessError if systemctl cannot
        communicate with the user session bus or the service is in a
        transient state. The manager must still signal failure gracefully.

        Arrangement:
        1. Pre-populate mock filesystem with service file (so uninstall proceeds).
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call uninstall() which encounters the systemctl failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - uninstall() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring systemctl failures during
        uninstall produce recoverable boolean results.
        """
        fs = MockFileSystem()
        service_path = str(Path.home() / ".config/systemd/user" / f"{SERVICE_NAME}.service")
        fs.files[service_path] = "content"
        manager = LinuxServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")

        result = manager.uninstall()

        assert result is False

    @patch("subprocess.run")
    def test_start_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies start() returns False when systemctl start raises CalledProcessError.

        Tests error recovery when the systemctl start command fails, e.g.,
        due to a missing ExecStart binary or resource constraints.

        Business context:
        Start failures are common when the service binary was removed
        or the environment changed after installation. The manager must
        report failure without crashing the caller.

        Arrangement:
        1. Create LinuxServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call start() which encounters the systemctl failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - start() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring start failures are
        communicated as actionable boolean results.
        """
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")

        result = manager.start()

        assert result is False

    @patch("subprocess.run")
    def test_stop_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies stop() returns False when systemctl stop raises CalledProcessError.

        Tests error recovery when the systemctl stop command fails, e.g.,
        when the service is not running or the process already exited.

        Business context:
        Stop failures may occur if the service crashed before stop was
        called or if systemd's state is inconsistent. The manager must
        handle this gracefully rather than raising to the caller.

        Arrangement:
        1. Create LinuxServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call stop() which encounters the systemctl failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - stop() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring stop failures on already-stopped
        or crashed services produce recoverable results.
        """
        fs = MockFileSystem()
        manager = LinuxServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")

        result = manager.stop()

        assert result is False

    @patch("subprocess.run")
    def test_status_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies status() returns degraded info when systemctl query fails.

        Tests that status correctly reports the service as installed (file
        exists) but unable to determine runtime state when the systemctl
        is-active check raises CalledProcessError.

        Business context:
        Status queries must always return a result dict, even when systemctl
        fails. Users need to know the service is installed even if runtime
        state cannot be determined — this guides troubleshooting.

        Arrangement:
        1. Pre-populate mock filesystem with service file (installed state).
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call status() which can detect the file but fails on systemctl query.

        Assertion Strategy:
        Validates degraded reporting by confirming:
        - installed is True (file exists, independent of systemctl).
        - running is False (can't confirm active state).
        - Status message indicates inability to determine status.

        Testing Principle:
        Validates partial-failure handling, ensuring file-based state
        detection works independently of systemctl availability.
        """
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
    """Tests for macOS service manager CalledProcessError handling.

    Validates that all MacOSServiceManager lifecycle operations gracefully
    handle subprocess.CalledProcessError exceptions from failed launchctl
    commands, returning appropriate failure signals instead of propagating.
    """

    @patch("subprocess.run")
    def test_install_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies install() returns False when launchctl raises CalledProcessError.

        Tests error recovery when launchctl load fails during plist
        registration, e.g., due to permission issues or a malformed plist.

        Business context:
        Install may fail if the user's LaunchAgents directory has restrictive
        permissions or launchd rejects the plist schema. The manager must
        catch errors and return a clear failure signal.

        Arrangement:
        1. Create MacOSServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError for launchctl.

        Action:
        Call install() which encounters the launchctl failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - install() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring launchctl failures during
        install produce recoverable boolean results.
        """
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

        result = manager.install()

        assert result is False

    @patch("subprocess.run")
    def test_uninstall_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies uninstall() returns False when launchctl raises CalledProcessError.

        Tests error recovery when launchctl unload fails during agent
        removal, e.g., when the agent is in a stuck state.

        Business context:
        Uninstall on macOS may fail if launchctl cannot unload the agent
        (e.g., agent process is stuck or launchd state is corrupted).
        The manager must still report failure gracefully.

        Arrangement:
        1. Pre-populate mock filesystem with plist file (so uninstall proceeds).
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call uninstall() which encounters the launchctl failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - uninstall() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring launchctl failures during
        uninstall produce recoverable boolean results.
        """
        fs = MockFileSystem()
        plist_path = str(Path.home() / "Library/LaunchAgents/com.ai-session-tracker.mcp.plist")
        fs.files[plist_path] = "content"
        manager = MacOSServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

        result = manager.uninstall()

        assert result is False

    @patch("subprocess.run")
    def test_start_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies start() returns False when launchctl start raises CalledProcessError.

        Tests error recovery when the launchctl start/bootstrap command
        fails, e.g., due to a missing executable or resource limits.

        Business context:
        Start failures on macOS may occur if the referenced executable was
        removed after installation or if the system is under memory pressure.
        The manager must report failure without crashing.

        Arrangement:
        1. Create MacOSServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call start() which encounters the launchctl failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - start() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring start failures are
        communicated as actionable boolean results.
        """
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

        result = manager.start()

        assert result is False

    @patch("subprocess.run")
    def test_stop_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies stop() returns False when launchctl stop raises CalledProcessError.

        Tests error recovery when the launchctl stop/remove command fails,
        e.g., when the agent is not currently loaded or already stopped.

        Business context:
        Stop failures may occur if the agent crashed before stop was called
        or if launchd's state is inconsistent. The manager must handle this
        gracefully rather than raising to the caller.

        Arrangement:
        1. Create MacOSServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call stop() which encounters the launchctl failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - stop() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring stop failures produce
        recoverable results without exception propagation.
        """
        fs = MockFileSystem()
        manager = MacOSServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

        result = manager.stop()

        assert result is False

    @patch("subprocess.run")
    def test_status_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies status() returns degraded info when launchctl query fails.

        Tests that status correctly reports the agent as installed (plist
        exists) but unable to determine runtime state when launchctl
        list raises CalledProcessError.

        Business context:
        Status queries must always return a result dict, even when launchctl
        fails. Users need to know the agent is installed even if runtime
        state cannot be determined — this guides macOS-specific troubleshooting.

        Arrangement:
        1. Pre-populate mock filesystem with plist file (installed state).
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call status() which detects the file but fails on launchctl query.

        Assertion Strategy:
        Validates degraded reporting by confirming:
        - installed is True (plist exists, independent of launchctl).
        - running is False (can't confirm active state).
        - Status message indicates inability to determine status.

        Testing Principle:
        Validates partial-failure handling, ensuring file-based state
        detection works independently of launchctl availability.
        """
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
    """Tests for Windows service manager CalledProcessError handling.

    Validates that all WindowsServiceManager lifecycle operations gracefully
    handle subprocess.CalledProcessError exceptions from failed schtasks
    commands, returning appropriate failure signals instead of propagating.
    """

    @patch("subprocess.run")
    def test_install_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies install() returns False when schtasks /create raises CalledProcessError.

        Tests error recovery when the schtasks create command fails, e.g.,
        due to insufficient privileges or a conflicting task name.

        Business context:
        Windows Task Scheduler may reject task creation if the user lacks
        the required permissions or if a task with the same name already
        exists. The manager must catch this and return a failure signal.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError for schtasks.

        Action:
        Call install() which encounters the schtasks failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - install() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring schtasks failures during
        install produce recoverable boolean results.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        result = manager.install()

        assert result is False

    @patch("subprocess.run")
    def test_uninstall_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies uninstall() returns False when schtasks /delete raises CalledProcessError.

        Tests error recovery when the schtasks delete command fails, e.g.,
        when the task is currently running or the user lacks permissions.

        Business context:
        Task deletion may fail if the task is in a running state or
        protected by access control. The manager must handle this
        gracefully and signal failure to the caller.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call uninstall() which encounters the schtasks failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - uninstall() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring schtasks failures during
        uninstall produce recoverable boolean results.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        result = manager.uninstall()

        assert result is False

    @patch("subprocess.run")
    def test_start_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies start() returns False when schtasks /run raises CalledProcessError.

        Tests error recovery when the schtasks run command fails, e.g.,
        due to a missing executable or disabled task state.

        Business context:
        Start failures on Windows may occur if the task's executable path
        is invalid or the task was disabled by an administrator. The
        manager must report failure without crashing.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call start() which encounters the schtasks failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - start() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring start failures are
        communicated as actionable boolean results.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        result = manager.start()

        assert result is False

    @patch("subprocess.run")
    def test_stop_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies stop() returns False when schtasks /end raises CalledProcessError.

        Tests error recovery when the schtasks end command fails, e.g.,
        when the task is not currently running or already terminated.

        Business context:
        Stop failures may occur if the task process already exited or if
        the Task Scheduler service itself is in a degraded state. The
        manager must handle this gracefully.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call stop() which encounters the schtasks failure.

        Assertion Strategy:
        Validates error handling by confirming:
        - stop() returns False rather than propagating the exception.

        Testing Principle:
        Validates fault tolerance, ensuring stop failures produce
        recoverable results without exception propagation.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        result = manager.stop()

        assert result is False

    @patch("subprocess.run")
    def test_status_handles_error(self, mock_run: MagicMock) -> None:
        """Verifies status() returns degraded info when schtasks query raises CalledProcessError.

        Tests that status reports the task as not installed with an
        informative error message when the schtasks query command fails.

        Business context:
        Unlike Linux/macOS where file existence is checked separately,
        Windows status relies entirely on schtasks query. A CalledProcessError
        must be interpreted as "unable to determine status" with safe defaults.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Configure subprocess.run to raise CalledProcessError.

        Action:
        Call status() which encounters the schtasks query failure.

        Assertion Strategy:
        Validates error-state reporting by confirming:
        - installed is False (cannot confirm registration).
        - running is False (cannot confirm execution).
        - Status message indicates inability to determine status.

        Testing Principle:
        Validates safe-default behavior, ensuring query failures produce
        conservative status reports that don't mislead users.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks")

        status = manager.status()

        assert status["installed"] is False
        assert status["running"] is False
        assert "Unable to determine status" in status["status"]

    @patch("subprocess.run")
    def test_status_installed_and_running(self, mock_run: MagicMock) -> None:
        """Verifies status() reports installed and running when schtasks output confirms active task.

        Tests the happy-path status detection where schtasks query returns
        a zero exit code and the stdout contains indicators of a running task.

        Business context:
        The status endpoint must parse schtasks CSV output to determine
        both registration state (task exists) and execution state (task
        is running). This is the primary diagnostic tool for Windows users.

        Arrangement:
        1. Create WindowsServiceManager with mock filesystem.
        2. Stub subprocess.run to return CSV output indicating a running task.

        Action:
        Call status() to query Task Scheduler for the task state.

        Assertion Strategy:
        Validates combined state by confirming:
        - installed is True (schtasks query succeeded).
        - running is True (stdout indicates active execution).
        - Status message contains "running" for clear user feedback.

        Testing Principle:
        Validates the golden path, ensuring accurate reporting when
        both registration and execution conditions are satisfied.
        """
        fs = MockFileSystem()
        manager = WindowsServiceManager(fs)
        mock_run.return_value = MagicMock(returncode=0, stdout='"Task","Running","Ready"')

        status = manager.status()

        assert status["installed"] is True
        assert status["running"] is True
        assert "running" in status["status"].lower()
