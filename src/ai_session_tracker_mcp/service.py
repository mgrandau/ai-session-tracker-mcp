"""
Service management for AI Session Tracker.

PURPOSE: Install and manage AI Session Tracker as a system service.
AI CONTEXT: Enables persistent background operation without per-project setup.

SUPPORTED PLATFORMS:
- Linux: systemd user service (~/.config/systemd/user/)
- macOS: launchd user agent (~/Library/LaunchAgents/)
- Windows: Task Scheduler (runs at user login)

USAGE:
    # Install as service
    ai-session-tracker install --service

    # Manage service
    ai-session-tracker service start
    ai-session-tracker service stop
    ai-session-tracker service status
    ai-session-tracker service uninstall
"""

from __future__ import annotations

import logging
import os
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .filesystem import FileSystem

__all__ = [
    "ServiceManager",
    "get_service_manager",
]

logger = logging.getLogger(__name__)

# Service configuration
SERVICE_NAME = "ai-session-tracker"
SERVICE_DESCRIPTION = "AI Session Tracker MCP Server"

# Systemd service template for Linux
SYSTEMD_SERVICE_TEMPLATE = """[Unit]
Description={description}
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
Environment=HOME={home}

[Install]
WantedBy=default.target
"""

# launchd plist template for macOS
LAUNCHD_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ai-session-tracker.mcp</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>ai_session_tracker_mcp</string>
        <string>server</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/ai-session-tracker.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/ai-session-tracker.error.log</string>
</dict>
</plist>
"""


class ServiceManager:
    """
    Base class for platform-specific service management.

    Provides a unified interface for installing, starting, stopping,
    and checking status of the AI Session Tracker as a system service.

    Business context: Running as a service enables the MCP server to
    be globally available without per-project configuration, improving
    user experience for developers who use session tracking across
    multiple projects.
    """

    def __init__(self, filesystem: FileSystem | None = None) -> None:
        """Initialize the service manager with an optional filesystem abstraction.

        Sets up the filesystem dependency used for all file operations
        (creating directories, writing config files, checking existence).
        Defaults to ``RealFileSystem`` for production; accepts a mock or
        in-memory implementation for testing. Business context: dependency
        injection here enables comprehensive unit testing of service
        management without touching the real filesystem.

        Args:
            filesystem: FileSystem instance for file I/O operations. When
                ``None`` (default), a ``RealFileSystem`` is created
                automatically. Pass a custom implementation (e.g.,
                ``FakeFileSystem``) in tests to avoid touching the real
                filesystem.

        Returns:
            None.

        Raises:
            No exceptions are raised directly.

        Attributes:
            _fs: The resolved FileSystem instance used by all methods.

        Example:
            >>> from ai_session_tracker_mcp.filesystem import RealFileSystem
            >>> manager = ServiceManager(filesystem=RealFileSystem())
        """
        from .filesystem import RealFileSystem

        self._fs: FileSystem = filesystem or RealFileSystem()

    def install(self) -> bool:
        """Install the service for auto-start on user login.

        Creates platform-specific service configuration files and registers
        the service with the operating system's service manager. Must be
        implemented by platform-specific subclasses.

        Business context: Enables zero-configuration startup so developers
        don't need to manually launch the tracker for each coding session.

        Returns:
            True if the service was installed and registered successfully,
            False if any step failed (partial installs are possible).

        Raises:
            NotImplementedError: Always, unless overridden by a subclass.

        Example:
            >>> manager = get_service_manager()
            >>> manager.install()
            True
        """
        raise NotImplementedError

    def uninstall(self) -> bool:
        """Remove the service and disable auto-start on login.

        Stops the running service (if active), removes configuration files,
        and unregisters from the platform's service manager. Must be
        implemented by platform-specific subclasses.

        Business context: Provides clean removal so the tracker can be
        fully decommissioned without leaving orphaned service entries.

        Returns:
            True if the service was fully removed, False if removal
            encountered errors (partial cleanup may have occurred).

        Raises:
            NotImplementedError: Always, unless overridden by a subclass.

        Example:
            >>> manager = get_service_manager()
            >>> manager.uninstall()
            True
        """
        raise NotImplementedError

    def start(self) -> bool:
        """Start the MCP server service.

        Sends a start command to the platform's service manager. The service
        must already be installed via ``install()``. Must be implemented by
        platform-specific subclasses. Business context: provides a unified
        interface for starting the tracker across all supported operating
        systems, so CLI consumers don't need platform-specific logic.

        Args:
            self: The ServiceManager instance.

        Returns:
            True if the service started successfully, False if the start
            command failed (e.g., service not installed or already running).

        Raises:
            NotImplementedError: Always, unless overridden by a subclass.

        Example:
            >>> manager = get_service_manager()
            >>> manager.start()
            True
        """
        raise NotImplementedError

    def stop(self) -> bool:
        """Stop the running MCP server service.

        Sends a stop command to the platform's service manager. Safe to call
        even if the service is not currently running on some platforms. Must
        be implemented by platform-specific subclasses. Business context:
        allows graceful shutdown of the tracker to flush pending session data
        and release system resources cleanly.

        Args:
            self: The ServiceManager instance.

        Returns:
            True if the service was stopped successfully, False if the stop
            command failed.

        Raises:
            NotImplementedError: Always, unless overridden by a subclass.

        Example:
            >>> manager = get_service_manager()
            >>> manager.stop()
            True
        """
        raise NotImplementedError

    def status(self) -> dict[str, str | bool]:
        """Get current service installation and runtime status.

        Checks both whether the service is installed (configuration files
        exist) and whether it is currently running. Must be implemented by
        platform-specific subclasses. Business context: enables diagnostic
        tools and CLI commands to report whether the tracker is operational,
        helping users troubleshoot connectivity issues.

        Args:
            self: The ServiceManager instance.

        Returns:
            Dictionary with the following keys:
                - ``'installed'`` (bool): Whether service config files exist.
                - ``'running'`` (bool): Whether the service process is active.
                - ``'status'`` (str): Human-readable status message, e.g.
                  ``"Service is active"`` or ``"Service not installed"``.

        Raises:
            NotImplementedError: Always, unless overridden by a subclass.

        Example:
            >>> manager = get_service_manager()
            >>> manager.status()
            {'installed': True, 'running': True, 'status': 'Service is active'}
        """
        raise NotImplementedError

    def _get_executable_command(self) -> list[str]:
        """Build the command-line invocation for running the MCP server.

        Determines the best way to launch the server by checking whether
        a dedicated ``ai-session-tracker`` entry-point script exists in the
        Python environment's bin directory. Falls back to running the
        package module directly via ``python -m``. Business context: ensures
        the service configuration uses the correct executable path regardless
        of how the package was installed (pip, pipx, editable, etc.).

        Args:
            self: The ServiceManager instance.

        Returns:
            List of command-line arguments suitable for ``subprocess.run()``.
            Either ``['/path/to/ai-session-tracker', 'server']`` if the
            entry-point exists, or ``['/path/to/python', '-m',
            'ai_session_tracker_mcp', 'server']`` as fallback.

        Raises:
            No exceptions are raised directly.

        Example:
            >>> manager = ServiceManager()
            >>> cmd = manager._get_executable_command()
            >>> cmd[-1]
            'server'
        """
        bin_dir = Path(sys.executable).parent
        server_cmd = bin_dir / SERVICE_NAME

        if server_cmd.exists():
            return [str(server_cmd), "server"]
        else:
            return [sys.executable, "-m", "ai_session_tracker_mcp", "server"]


class LinuxServiceManager(ServiceManager):
    """
    Linux systemd user service manager.

    Creates a systemd user service that runs at user login without
    requiring root privileges.
    """

    def __init__(self, filesystem: FileSystem | None = None) -> None:
        """Initialize the Linux systemd service manager.

        Sets up paths for the systemd user service directory and unit file.
        Uses ``~/.config/systemd/user/`` which does not require root privileges.
        Business context: user-level systemd services allow developers to
        run the tracker persistently without administrator access, lowering
        the barrier to adoption on shared Linux machines.

        Args:
            filesystem: Optional FileSystem for file I/O operations.
                Defaults to RealFileSystem for production use.

        Returns:
            None.

        Raises:
            No exceptions are raised directly.

        Attributes:
            _service_dir: Path to the systemd user service directory
                (``~/.config/systemd/user/``).
            _service_file: Path to the service unit file
                (``ai-session-tracker.service``).

        Example:
            >>> manager = LinuxServiceManager()
        """
        super().__init__(filesystem)
        self._service_dir = Path.home() / ".config" / "systemd" / "user"
        self._service_file = self._service_dir / f"{SERVICE_NAME}.service"

    def install(self) -> bool:
        """Install the AI Session Tracker as a systemd user service.

        Creates the systemd user service directory if needed, writes a
        ``.service`` unit file from ``SYSTEMD_SERVICE_TEMPLATE``, then
        reloads the systemd daemon and enables the service for auto-start
        on login. Business context: automating service installation removes
        manual configuration steps and ensures consistent setup across
        Linux development environments.

        The service is configured with ``Restart=on-failure`` and a 5-second
        restart delay for resilience.

        Args:
            self: The LinuxServiceManager instance.

        Returns:
            True if the unit file was written and the service was enabled
            successfully. False if any step failed (file write, daemon-reload,
            or enable command).

        Raises:
            OSError: If the service directory cannot be created or the unit
                file cannot be written (caught internally, returns False).
            subprocess.CalledProcessError: If ``systemctl`` commands fail
                (caught internally, returns False).

        Example:
            >>> manager = LinuxServiceManager()
            >>> manager.install()
            True
        """
        try:
            # Create service directory
            self._fs.makedirs(str(self._service_dir), exist_ok=True)

            # Generate service file content
            exec_cmd = self._get_executable_command()
            service_content = SYSTEMD_SERVICE_TEMPLATE.format(
                description=SERVICE_DESCRIPTION,
                exec_start=" ".join(exec_cmd),
                home=str(Path.home()),
            )

            # Write service file
            self._fs.write_text(str(self._service_file), service_content)
            logger.info(f"Created service file: {self._service_file}")

            # Reload systemd and enable service
            subprocess.run(  # nosec B603, B607
                ["systemctl", "--user", "daemon-reload"],
                check=True,
                capture_output=True,
            )
            subprocess.run(  # nosec B603, B607
                ["systemctl", "--user", "enable", SERVICE_NAME],
                check=True,
                capture_output=True,
            )
            logger.info(f"Enabled service: {SERVICE_NAME}")

            return True

        except (OSError, subprocess.CalledProcessError) as e:
            logger.error(f"Failed to install service: {e}")
            return False

    def uninstall(self) -> bool:
        """Remove the systemd user service and clean up configuration.

        Stops the running service (ignoring errors if not running), disables
        auto-start, deletes the ``.service`` unit file, and reloads the
        systemd daemon to clear cached state. Business context: clean
        uninstallation prevents orphaned systemd units from consuming
        resources or causing confusing error messages after removal.

        Args:
            self: The LinuxServiceManager instance.

        Returns:
            True if uninstallation completed (even if service wasn't running).
            False if a critical operation like file removal failed.

        Raises:
            OSError: If the service file cannot be deleted (caught internally,
                returns False).
            subprocess.CalledProcessError: If ``systemctl`` commands fail
                (caught internally, returns False).

        Example:
            >>> manager = LinuxServiceManager()
            >>> manager.uninstall()
            True
        """
        try:
            # Stop and disable service
            subprocess.run(  # nosec B603, B607
                ["systemctl", "--user", "stop", SERVICE_NAME],
                capture_output=True,
            )
            subprocess.run(  # nosec B603, B607
                ["systemctl", "--user", "disable", SERVICE_NAME],
                capture_output=True,
            )

            # Remove service file
            if self._fs.exists(str(self._service_file)):
                self._fs.remove(str(self._service_file))
                logger.info(f"Removed service file: {self._service_file}")

            # Reload systemd
            subprocess.run(  # nosec B603, B607
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
            )

            return True

        except (OSError, subprocess.CalledProcessError) as e:
            logger.error(f"Failed to uninstall service: {e}")
            return False

    def start(self) -> bool:
        """Start the systemd user service via ``systemctl --user start``.

        Requires the service to be already installed. The service will be
        managed by systemd and automatically restarted on failure per the
        unit file configuration. Business context: enables on-demand
        activation of the tracker after installation or manual stop,
        supporting workflows where developers pause tracking temporarily.

        Args:
            self: The LinuxServiceManager instance.

        Returns:
            True if ``systemctl start`` succeeded (exit code 0).
            False if the command failed (e.g., service not installed).

        Raises:
            subprocess.CalledProcessError: If ``systemctl`` fails (caught
                internally, returns False).

        Example:
            >>> manager = LinuxServiceManager()
            >>> manager.start()
            True
        """
        try:
            subprocess.run(  # nosec B603, B607
                ["systemctl", "--user", "start", SERVICE_NAME],
                check=True,
                capture_output=True,
            )
            logger.info(f"Started service: {SERVICE_NAME}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start service: {e}")
            return False

    def stop(self) -> bool:
        """Stop the systemd user service via ``systemctl --user stop``.

        Sends a stop signal to the running service process. If the service
        is not currently running, ``systemctl`` will return a non-zero exit
        code and this method returns False. Business context: allows
        developers to gracefully halt session tracking when not needed,
        reducing resource usage on constrained systems.

        Args:
            self: The LinuxServiceManager instance.

        Returns:
            True if ``systemctl stop`` succeeded (exit code 0).
            False if the command failed (e.g., service not running).

        Raises:
            subprocess.CalledProcessError: If ``systemctl`` fails (caught
                internally, returns False).

        Example:
            >>> manager = LinuxServiceManager()
            >>> manager.stop()
            True
        """
        try:
            subprocess.run(  # nosec B603, B607
                ["systemctl", "--user", "stop", SERVICE_NAME],
                check=True,
                capture_output=True,
            )
            logger.info(f"Stopped service: {SERVICE_NAME}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop service: {e}")
            return False

    def status(self) -> dict[str, str | bool]:
        """Get the current status of the systemd user service.

        Checks whether the ``.service`` unit file exists on disk (installed)
        and queries ``systemctl --user is-active`` to determine if the
        service process is running. Business context: status checks power
        the CLI's ``service status`` command and health-check integrations,
        giving developers immediate visibility into tracker availability.

        Args:
            self: The LinuxServiceManager instance.

        Returns:
            Dictionary with keys:
                - ``'installed'`` (bool): True if the unit file exists.
                - ``'running'`` (bool): True if ``is-active`` returns 0.
                - ``'status'`` (str): Human-readable description, e.g.
                  ``"Service is active"``, ``"Service is inactive"``, or
                  ``"Service not installed"``.

        Raises:
            subprocess.CalledProcessError: If ``systemctl`` fails
                unexpectedly (caught internally, returns a status dict
                with ``running=False``).

        Example:
            >>> manager = LinuxServiceManager()
            >>> result = manager.status()
            >>> result['installed']
            True
        """
        installed = self._fs.exists(str(self._service_file))

        if not installed:
            return {
                "installed": False,
                "running": False,
                "status": "Service not installed",
            }

        try:
            result = subprocess.run(  # nosec B603, B607
                ["systemctl", "--user", "is-active", SERVICE_NAME],
                capture_output=True,
                text=True,
            )
            running = result.returncode == 0
            status_text = result.stdout.strip() if result.stdout else "unknown"

            return {
                "installed": True,
                "running": running,
                "status": f"Service is {status_text}",
            }
        except subprocess.CalledProcessError:
            return {
                "installed": True,
                "running": False,
                "status": "Unable to determine status",
            }


class MacOSServiceManager(ServiceManager):
    """
    macOS launchd user agent manager.

    Creates a launchd user agent that runs at user login.
    """

    def __init__(self, filesystem: FileSystem | None = None) -> None:
        """Initialize the macOS launchd service manager.

        Sets up paths for the LaunchAgents directory, the plist configuration
        file, and the log output directory. All paths are in the current
        user's home directory and do not require root privileges. Business
        context: user-level launchd agents enable persistent tracker
        operation on macOS without requiring administrator credentials,
        aligning with Apple's sandboxing philosophy.

        Args:
            filesystem: Optional FileSystem for file I/O operations.
                Defaults to RealFileSystem for production use.

        Returns:
            None.

        Raises:
            No exceptions are raised directly.

        Attributes:
            _agents_dir: Path to ``~/Library/LaunchAgents/``.
            _plist_file: Path to the service plist file
                (``com.ai-session-tracker.mcp.plist``).
            _log_dir: Path to ``~/Library/Logs/ai-session-tracker/`` for
                stdout and stderr output.

        Example:
            >>> manager = MacOSServiceManager()
        """
        super().__init__(filesystem)
        self._agents_dir = Path.home() / "Library" / "LaunchAgents"
        self._plist_file = self._agents_dir / "com.ai-session-tracker.mcp.plist"
        self._log_dir = Path.home() / "Library" / "Logs" / "ai-session-tracker"

    def install(self) -> bool:
        """Install the AI Session Tracker as a macOS launchd user agent.

        Creates the LaunchAgents and log directories, writes a plist file
        from ``LAUNCHD_PLIST_TEMPLATE`` configured with ``RunAtLoad`` and
        ``KeepAlive`` for persistent operation, then loads the agent via
        ``launchctl load``. Business context: automatic installation as a
        launchd agent ensures the tracker starts on login without manual
        intervention, providing seamless session tracking for macOS developers.

        Args:
            self: The MacOSServiceManager instance.

        Returns:
            True if the plist was written and the agent loaded successfully.
            False if any step failed.

        Raises:
            OSError: If directories or plist file cannot be created (caught
                internally, returns False).
            subprocess.CalledProcessError: If ``launchctl load`` fails
                (caught internally, returns False).

        Example:
            >>> manager = MacOSServiceManager()
            >>> manager.install()
            True
        """
        try:
            # Create directories
            self._fs.makedirs(str(self._agents_dir), exist_ok=True)
            self._fs.makedirs(str(self._log_dir), exist_ok=True)

            # Generate plist content
            plist_content = LAUNCHD_PLIST_TEMPLATE.format(
                python_path=sys.executable,
                log_dir=str(self._log_dir),
            )

            # Write plist file
            self._fs.write_text(str(self._plist_file), plist_content)
            logger.info(f"Created plist file: {self._plist_file}")

            # Load the agent
            subprocess.run(  # nosec B603, B607
                ["launchctl", "load", str(self._plist_file)],
                check=True,
                capture_output=True,
            )
            logger.info("Loaded launchd agent")

            return True

        except (OSError, subprocess.CalledProcessError) as e:
            logger.error(f"Failed to install service: {e}")
            return False

    def uninstall(self) -> bool:
        """Remove the launchd user agent and delete its plist file.

        Unloads the agent via ``launchctl unload`` (ignoring errors if not
        currently loaded), then removes the plist file from disk. Business
        context: clean removal of the launchd agent prevents stale entries
        in ``launchctl list`` and avoids confusing startup errors after the
        tracker is no longer needed.

        Args:
            self: The MacOSServiceManager instance.

        Returns:
            True if the agent was unloaded and the plist was removed.
            False if a critical step failed.

        Raises:
            OSError: If the plist file cannot be deleted (caught internally,
                returns False).
            subprocess.CalledProcessError: If ``launchctl`` fails (caught
                internally, returns False).

        Example:
            >>> manager = MacOSServiceManager()
            >>> manager.uninstall()
            True
        """
        try:
            # Unload the agent
            subprocess.run(  # nosec B603, B607
                ["launchctl", "unload", str(self._plist_file)],
                capture_output=True,
            )

            # Remove plist file
            if self._fs.exists(str(self._plist_file)):
                self._fs.remove(str(self._plist_file))
                logger.info(f"Removed plist file: {self._plist_file}")

            return True

        except (OSError, subprocess.CalledProcessError) as e:
            logger.error(f"Failed to uninstall service: {e}")
            return False

    def start(self) -> bool:
        """Start the launchd user agent via ``launchctl start``.

        Sends a start signal to the already-loaded agent. The agent must
        have been previously installed and loaded via ``install()``.
        Business context: supports on-demand activation after the agent
        has been manually stopped, letting developers control when session
        tracking is active on macOS.

        Args:
            self: The MacOSServiceManager instance.

        Returns:
            True if ``launchctl start`` succeeded (exit code 0).
            False if the command failed (e.g., agent not loaded).

        Raises:
            subprocess.CalledProcessError: If ``launchctl`` fails (caught
                internally, returns False).

        Example:
            >>> manager = MacOSServiceManager()
            >>> manager.start()
            True
        """
        try:
            subprocess.run(  # nosec B603, B607
                ["launchctl", "start", "com.ai-session-tracker.mcp"],
                check=True,
                capture_output=True,
            )
            logger.info("Started launchd agent")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start service: {e}")
            return False

    def stop(self) -> bool:
        """Stop the launchd user agent via ``launchctl stop``.

        Sends a stop signal to the running agent process. Note that if
        ``KeepAlive`` is enabled in the plist, launchd may automatically
        restart the agent after stopping it. Business context: allows
        temporary suspension of session tracking on macOS, though
        ``KeepAlive`` behavior means uninstall is needed for permanent
        removal.

        Args:
            self: The MacOSServiceManager instance.

        Returns:
            True if ``launchctl stop`` succeeded (exit code 0).
            False if the command failed.

        Raises:
            subprocess.CalledProcessError: If ``launchctl`` fails (caught
                internally, returns False).

        Example:
            >>> manager = MacOSServiceManager()
            >>> manager.stop()
            True
        """
        try:
            subprocess.run(  # nosec B603, B607
                ["launchctl", "stop", "com.ai-session-tracker.mcp"],
                check=True,
                capture_output=True,
            )
            logger.info("Stopped launchd agent")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop service: {e}")
            return False

    def status(self) -> dict[str, str | bool]:
        """Get the current status of the launchd user agent.

        Checks whether the plist file exists on disk (installed) and queries
        ``launchctl list`` to determine whether the agent is currently loaded
        and running. Business context: status reporting is essential for the
        CLI diagnostics workflow, enabling developers to verify the tracker
        is operational before starting a coding session.

        Args:
            self: The MacOSServiceManager instance.

        Returns:
            Dictionary with keys:
                - ``'installed'`` (bool): True if the plist file exists.
                - ``'running'`` (bool): True if ``launchctl list`` returns 0
                  for the agent label.
                - ``'status'`` (str): ``"Service is running"``,
                  ``"Service is stopped"``, or ``"Service not installed"``.

        Raises:
            subprocess.CalledProcessError: If ``launchctl`` fails
                unexpectedly (caught internally, returns a status dict
                with ``running=False``).

        Example:
            >>> manager = MacOSServiceManager()
            >>> result = manager.status()
            >>> 'installed' in result
            True
        """
        installed = self._fs.exists(str(self._plist_file))

        if not installed:
            return {
                "installed": False,
                "running": False,
                "status": "Service not installed",
            }

        try:
            result = subprocess.run(  # nosec B603, B607
                ["launchctl", "list", "com.ai-session-tracker.mcp"],
                capture_output=True,
                text=True,
            )
            running = result.returncode == 0

            return {
                "installed": True,
                "running": running,
                "status": "Service is running" if running else "Service is stopped",
            }
        except subprocess.CalledProcessError:
            return {
                "installed": True,
                "running": False,
                "status": "Unable to determine status",
            }


class WindowsServiceManager(ServiceManager):
    """
    Windows Task Scheduler manager.

    Creates a scheduled task that runs at user login.
    """

    def __init__(self, filesystem: FileSystem | None = None) -> None:
        """Initialize the Windows Task Scheduler service manager.

        Configures the scheduled task name used for registration with the
        Windows Task Scheduler. No files are created until ``install()``
        is called. Business context: Task Scheduler integration provides
        Windows developers with the same persistent tracking experience
        available on Linux and macOS, ensuring cross-platform feature parity.

        Args:
            filesystem: Optional FileSystem for file I/O operations.
                Defaults to RealFileSystem for production use.

        Returns:
            None.

        Raises:
            No exceptions are raised directly.

        Attributes:
            _task_name: The Task Scheduler task name
                (``"AISessionTracker"``).

        Example:
            >>> manager = WindowsServiceManager()
        """
        super().__init__(filesystem)
        self._task_name = "AISessionTracker"

    def install(self) -> bool:
        """Install the AI Session Tracker as a Windows scheduled task.

        Creates a Task Scheduler entry configured to run at user logon with
        limited privileges using ``schtasks /create``. The ``/f`` flag forces
        overwrite of any existing task with the same name. Business context:
        scheduled task registration provides Windows developers with automatic
        tracker startup, matching the Linux systemd and macOS launchd
        experience for cross-platform consistency.

        Args:
            self: The WindowsServiceManager instance.

        Returns:
            True if the scheduled task was created successfully.
            False if ``schtasks`` returned a non-zero exit code.

        Raises:
            subprocess.CalledProcessError: If ``schtasks /create`` fails
                (caught internally, returns False).

        Example:
            >>> manager = WindowsServiceManager()
            >>> manager.install()
            True
        """
        try:
            exec_cmd = self._get_executable_command()
            command = exec_cmd[0]
            args = " ".join(exec_cmd[1:]) if len(exec_cmd) > 1 else ""

            # Create scheduled task that runs at logon
            subprocess.run(  # nosec B603, B607
                [
                    "schtasks",
                    "/create",
                    "/tn",
                    self._task_name,
                    "/tr",
                    f'"{command}" {args}',
                    "/sc",
                    "onlogon",
                    "/rl",
                    "limited",
                    "/f",
                ],
                check=True,
                capture_output=True,
            )
            logger.info(f"Created scheduled task: {self._task_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install service: {e}")
            return False

    def uninstall(self) -> bool:
        """Remove the Windows scheduled task.

        First attempts to end the running task (ignoring errors if not
        running), then deletes the task definition from Task Scheduler
        using ``schtasks /delete /f``. Business context: proper task
        removal prevents the tracker from restarting at next login after
        a user decides to stop using session tracking.

        Args:
            self: The WindowsServiceManager instance.

        Returns:
            True if the task was deleted successfully.
            False if ``schtasks /delete`` failed.

        Raises:
            subprocess.CalledProcessError: If ``schtasks`` fails (caught
                internally, returns False).

        Example:
            >>> manager = WindowsServiceManager()
            >>> manager.uninstall()
            True
        """
        try:
            # Stop the task if running
            subprocess.run(  # nosec B603, B607
                ["schtasks", "/end", "/tn", self._task_name],
                capture_output=True,
            )

            # Delete the task
            subprocess.run(  # nosec B603, B607
                ["schtasks", "/delete", "/tn", self._task_name, "/f"],
                check=True,
                capture_output=True,
            )
            logger.info(f"Removed scheduled task: {self._task_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to uninstall service: {e}")
            return False

    def start(self) -> bool:
        """Start the Windows scheduled task via ``schtasks /run``.

        Triggers immediate execution of the registered task. The task must
        have been previously created via ``install()``. Business context:
        allows developers to manually activate session tracking on demand
        without waiting for the next login trigger.

        Args:
            self: The WindowsServiceManager instance.

        Returns:
            True if ``schtasks /run`` succeeded (exit code 0).
            False if the command failed (e.g., task not registered).

        Raises:
            subprocess.CalledProcessError: If ``schtasks`` fails (caught
                internally, returns False).

        Example:
            >>> manager = WindowsServiceManager()
            >>> manager.start()
            True
        """
        try:
            subprocess.run(  # nosec B603, B607
                ["schtasks", "/run", "/tn", self._task_name],
                check=True,
                capture_output=True,
            )
            logger.info(f"Started task: {self._task_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start service: {e}")
            return False

    def stop(self) -> bool:
        """Stop the running Windows scheduled task via ``schtasks /end``.

        Terminates the task process if it is currently running. If the task
        is not running, ``schtasks /end`` returns a non-zero exit code and
        this method returns False. Business context: enables developers to
        pause session tracking without fully uninstalling the scheduled task,
        preserving the registration for easy restart later.

        Args:
            self: The WindowsServiceManager instance.

        Returns:
            True if ``schtasks /end`` succeeded (exit code 0).
            False if the command failed (e.g., task not running).

        Raises:
            subprocess.CalledProcessError: If ``schtasks`` fails (caught
                internally, returns False).

        Example:
            >>> manager = WindowsServiceManager()
            >>> manager.stop()
            True
        """
        try:
            subprocess.run(  # nosec B603, B607
                ["schtasks", "/end", "/tn", self._task_name],
                check=True,
                capture_output=True,
            )
            logger.info(f"Stopped task: {self._task_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop service: {e}")
            return False

    def status(self) -> dict[str, str | bool]:
        """Get the current status of the Windows scheduled task.

        Queries Task Scheduler via ``schtasks /query`` with CSV output
        format. Parses the output to determine whether the task exists
        (installed) and whether it is currently in a "Running" state.
        Business context: provides the same status introspection on Windows
        as on Linux and macOS, enabling cross-platform tooling to uniformly
        report tracker health.

        Args:
            self: The WindowsServiceManager instance.

        Returns:
            Dictionary with keys:
                - ``'installed'`` (bool): True if the task exists in
                  Task Scheduler.
                - ``'running'`` (bool): True if the CSV output contains
                  ``"Running"``.
                - ``'status'`` (str): ``"Service is running"``,
                  ``"Service is stopped"``, ``"Service not installed"``,
                  or ``"Unable to determine status"``.

        Raises:
            subprocess.CalledProcessError: If ``schtasks`` fails
                unexpectedly (caught internally, returns a status dict
                with ``installed=False``).

        Example:
            >>> manager = WindowsServiceManager()
            >>> result = manager.status()
            >>> 'running' in result
            True
        """
        try:
            result = subprocess.run(  # nosec B603, B607
                ["schtasks", "/query", "/tn", self._task_name, "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return {
                    "installed": False,
                    "running": False,
                    "status": "Service not installed",
                }

            # Parse CSV output to check status
            output = result.stdout.strip()
            running = "Running" in output

            return {
                "installed": True,
                "running": running,
                "status": "Service is running" if running else "Service is stopped",
            }

        except subprocess.CalledProcessError:
            return {
                "installed": False,
                "running": False,
                "status": "Unable to determine status",
            }


def get_service_manager(filesystem: FileSystem | None = None) -> ServiceManager:
    """
    Get the appropriate service manager for the current platform.

    Factory function that returns the correct ServiceManager subclass
    based on the operating system.

    Args:
        filesystem: Optional FileSystem for file operations.

    Returns:
        ServiceManager: Platform-appropriate service manager instance.

    Raises:
        NotImplementedError: If running on an unsupported platform.

    Example:
        >>> manager = get_service_manager()
        >>> manager.install()
        True
    """
    if sys.platform == "linux":
        return LinuxServiceManager(filesystem)
    elif sys.platform == "darwin":
        return MacOSServiceManager(filesystem)
    elif os.name == "nt":
        return WindowsServiceManager(filesystem)
    else:
        raise NotImplementedError(f"Unsupported platform: {sys.platform}")
