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
        """
        Initialize service manager with optional filesystem.

        Args:
            filesystem: FileSystem for file operations. Defaults to
                RealFileSystem for production use.
        """
        from .filesystem import RealFileSystem

        self._fs: FileSystem = filesystem or RealFileSystem()

    def install(self) -> bool:
        """
        Install the service for auto-start on login.

        Returns:
            bool: True if installation succeeded, False otherwise.
        """
        raise NotImplementedError

    def uninstall(self) -> bool:
        """
        Remove the service and disable auto-start.

        Returns:
            bool: True if uninstallation succeeded, False otherwise.
        """
        raise NotImplementedError

    def start(self) -> bool:
        """
        Start the service.

        Returns:
            bool: True if service started successfully, False otherwise.
        """
        raise NotImplementedError

    def stop(self) -> bool:
        """
        Stop the service.

        Returns:
            bool: True if service stopped successfully, False otherwise.
        """
        raise NotImplementedError

    def status(self) -> dict[str, str | bool]:
        """
        Get current service status.

        Returns:
            dict with keys:
                - 'installed': bool - whether service is installed
                - 'running': bool - whether service is currently running
                - 'status': str - human-readable status message
        """
        raise NotImplementedError

    def _get_executable_command(self) -> list[str]:
        """
        Get the command to run the MCP server.

        Returns:
            list[str]: Command arguments for running the server.
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
        """Initialize Linux service manager."""
        super().__init__(filesystem)
        self._service_dir = Path.home() / ".config" / "systemd" / "user"
        self._service_file = self._service_dir / f"{SERVICE_NAME}.service"

    def install(self) -> bool:
        """Install systemd user service."""
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
        """Remove systemd user service."""
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
        """Start systemd user service."""
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
        """Stop systemd user service."""
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
        """Get systemd user service status."""
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
        """Initialize macOS service manager."""
        super().__init__(filesystem)
        self._agents_dir = Path.home() / "Library" / "LaunchAgents"
        self._plist_file = self._agents_dir / "com.ai-session-tracker.mcp.plist"
        self._log_dir = Path.home() / "Library" / "Logs" / "ai-session-tracker"

    def install(self) -> bool:
        """Install launchd user agent."""
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
        """Remove launchd user agent."""
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
        """Start launchd user agent."""
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
        """Stop launchd user agent."""
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
        """Get launchd user agent status."""
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
        """Initialize Windows service manager."""
        super().__init__(filesystem)
        self._task_name = "AISessionTracker"

    def install(self) -> bool:
        """Install Windows scheduled task."""
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
        """Remove Windows scheduled task."""
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
        """Start Windows scheduled task."""
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
        """Stop Windows scheduled task."""
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
        """Get Windows scheduled task status."""
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
