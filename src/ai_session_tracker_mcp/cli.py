"""
CLI entry point for AI Session Tracker MCP.

PURPOSE: Command-line interface for running server and dashboard.
AI CONTEXT: Main entry points for package execution.

USAGE:
    # Run MCP server (default)
    python -m ai_session_tracker_mcp

    # Or via CLI command (after install)
    ai-session-tracker

    # Run with subcommands
    ai-session-tracker server     # Start MCP server
    ai-session-tracker dashboard  # Launch web dashboard
    ai-session-tracker report     # Print text report
    ai-session-tracker install    # Create .vscode/mcp.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess  # nosec B404
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .filesystem import FileSystem
    from .statistics import StatisticsEngine
    from .storage import StorageManager

# Constants
SERVER_NAME = "ai-session-tracker"
MODULE_NAME = "ai_session_tracker_mcp"
VSCODE_DIR = ".vscode"
GITHUB_DIR = ".github"
CONFIG_FILE = "mcp.json"
AGENT_FILES_DIR = "agent_files"
AGENT_SUBDIRS = ("agents", "instructions")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
SUBPROCESS_TIMEOUT = 5


@lru_cache(maxsize=1)
def _get_logger() -> logging.Logger:
    """
    Get module logger with cached initialization for thread safety.

    Creates and configures a logger for CLI operations on first call,
    then returns the cached instance on subsequent calls. Uses lru_cache
    to ensure thread-safe singleton behavior.

    Business context: CLI commands need consistent logging throughout
    their execution. Caching ensures handlers aren't duplicated and
    log configuration remains stable.

    Args:
        None.

    Returns:
        logging.Logger: Configured logger instance for the cli module.

    Example:
        >>> logger = _get_logger()
        >>> logger.info("Starting operation")
    """
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(__name__)


def _log(message: str, *, emoji: str = "") -> None:
    """
    Log message with optional emoji prefix for CLI output.

    Wraps the module logger with emoji support for user-friendly CLI
    feedback. Emojis provide visual status indicators (success, warning,
    error) without requiring color terminal support.

    Business context: The CLI setup command provides user feedback during
    configuration. Emoji prefixes make status clear without relying on
    terminal color support, ensuring accessibility.

    Args:
        message: The message to log. Should be human-readable.
        emoji: Optional emoji prefix for visual CLI feedback.
            Common values: "✅" success, "⚠️" warning, "❌" error.

    Returns:
        None. Message is written to log handlers.

    Raises:
        No exceptions raised. Logging errors are silently ignored.

    Example:
        >>> _log("Server started", emoji="✅")
        >>> _log("Config missing", emoji="⚠️")
    """
    prefix = f"{emoji} " if emoji else ""
    _get_logger().info(f"{prefix}{message}")


def run_server(
    dashboard_host: str | None = None,
    dashboard_port: int | None = None,
    *,
    subprocess_factory: Callable[..., Any] | None = None,
) -> None:
    """
    Run the MCP server in stdio mode.

    Starts the AI Session Tracker MCP server which communicates via
    stdin/stdout using JSON-RPC 2.0 protocol. This is the default
    command and the mode used by VS Code for MCP integration.

    Optionally starts the dashboard web server in a background process
    if dashboard_host and dashboard_port are provided.

    Business context: The MCP server is the core component that enables
    AI assistants in VS Code to track sessions, log interactions, and
    calculate ROI metrics during development workflows.

    Args:
        dashboard_host: If provided, start dashboard on this host.
        dashboard_port: If provided, start dashboard on this port.
        subprocess_factory: Optional factory for creating subprocesses.
            Defaults to subprocess.Popen. Used for testability.

    Returns:
        None. Blocks until server shutdown (EOF on stdin).

    Raises:
        OSError: If storage directory cannot be created.

    Example:
        >>> # From command line:
        >>> # ai-session-tracker server --dashboard-port 8000
        >>> run_server(dashboard_host="127.0.0.1", dashboard_port=8000)
    """
    popen = subprocess_factory or subprocess.Popen
    dashboard_process = None

    # Import server main once at function start
    from .server import main

    # Validate dashboard configuration - both host and port required, or neither
    if bool(dashboard_host) != bool(dashboard_port):
        _log("Both --dashboard-host and --dashboard-port are required together", emoji="⚠️")
        asyncio.run(main())
        return

    # Start dashboard in background if configured
    if dashboard_host and dashboard_port:
        _log(f"Starting dashboard at http://{dashboard_host}:{dashboard_port}")

        dashboard_process = popen(  # nosec B603
            [
                sys.executable,
                "-m",
                MODULE_NAME,
                "dashboard",
                "--host",
                dashboard_host,
                "--port",
                str(dashboard_port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    try:
        asyncio.run(main())
    finally:
        # Clean up dashboard process when server exits
        if dashboard_process:
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=SUBPROCESS_TIMEOUT)
            except subprocess.TimeoutExpired:
                _log("Dashboard process did not terminate gracefully, killing", emoji="⚠️")
                dashboard_process.kill()
                dashboard_process.wait()


def run_dashboard(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """
    Launch the web dashboard for visual analytics.

    Starts a FastAPI server hosting the AI Session Tracker dashboard.
    The dashboard provides real-time visualization of sessions, ROI
    metrics, and effectiveness charts using htmx for live updates.

    Business context: The dashboard is the primary interface for
    stakeholders to review AI productivity metrics. It provides
    visual ROI justification and helps identify patterns in usage.

    Args:
        host: Network interface to bind to. Default '127.0.0.1' for
            local-only access. Use '0.0.0.0' for network access.
        port: TCP port for the HTTP server. Default 8000.

    Returns:
        None. Blocks until server shutdown (Ctrl+C).

    Raises:
        OSError: If port is already in use.
        ImportError: If FastAPI/uvicorn are not installed.

    Example:
        >>> # From command line:
        >>> # ai-session-tracker dashboard --port 3000
        >>> run_dashboard(port=3000)
        🚀 Starting dashboard at http://127.0.0.1:3000
    """
    from .web import run_dashboard as start_web

    _log(f"Starting dashboard at http://{host}:{port}", emoji="🚀")
    _log("Press Ctrl+C to stop")
    start_web(host=host, port=port)


def run_report(
    storage: StorageManager | None = None,
    engine: StatisticsEngine | None = None,
) -> None:
    """
    Print text analytics report to stdout.

    Generates and prints a comprehensive text report containing session
    summary, ROI metrics, effectiveness distribution, issue summary,
    and code quality metrics. Suitable for terminal viewing or piping.

    Business context: The text report provides a quick CLI-accessible
    summary for developers who want metrics without opening a browser.
    Can be redirected to files or used in scripts.

    Args:
        storage: Optional StorageManager for testability. Defaults to
            new StorageManager instance.
        engine: Optional StatisticsEngine for testability. Defaults to
            new StatisticsEngine instance.

    Returns:
        None. Report is printed to stdout.

    Raises:
        OSError: If storage directory cannot be accessed.

    Example:
        >>> # From command line:
        >>> # ai-session-tracker report > metrics.txt
        >>> run_report()
        ==================================================
        AI SESSION TRACKER - ANALYTICS REPORT
        ...
    """
    from .statistics import StatisticsEngine as StatsEngine
    from .storage import StorageManager as StorageMgr

    storage = storage or StorageMgr()
    engine = engine or StatsEngine()

    sessions = storage.load_sessions()
    interactions = storage.load_interactions()
    issues = storage.load_issues()

    report = engine.generate_summary_report(sessions, interactions, issues)
    # Note: Using print() intentionally for stdout piping support
    print(report)


def _build_path(*parts: str) -> str:
    """
    Build path from parts using forward slash separator.

    Joins path components with forward slashes for virtual filesystem
    paths. These paths are used with the FileSystem abstraction layer,
    not native OS paths, ensuring cross-platform consistency.

    Business context: The CLI setup commands need to construct paths
    for MCP config files and agent files that work across different
    operating systems through the FileSystem abstraction.

    Args:
        *parts: Path components to join. Each component should be a
            single directory or file name without separators.

    Returns:
        str: Joined path string with forward slash separators.

    Example:
        >>> _build_path(".github", "instructions", "file.md")
        '.github/instructions/file.md'
        >>> _build_path("Users", "mark", ".vscode")
        'Users/mark/.vscode'
    """
    return "/".join(parts)


def _load_or_create_config(
    fs: FileSystem,
    config_path: str,
) -> dict[str, Any]:
    """
    Load existing MCP config or create empty one.

    Reads the mcp.json configuration file if it exists. If the file
    contains invalid JSON, creates a backup and returns an empty config.
    Ensures the returned config always has a 'servers' key.

    Business context: The setup command needs to modify existing MCP
    configs without losing user customizations. Backup on corruption
    prevents data loss while allowing recovery.

    Args:
        fs: FileSystem instance for file operations.
        config_path: Absolute path to mcp.json.

    Returns:
        dict[str, Any]: Config dictionary with at least a 'servers' key.
            Returns existing config if valid, or empty config with
            servers dict if file doesn't exist or is invalid.

    Raises:
        OSError: If filesystem operations fail unexpectedly.

    Example:
        >>> fs = RealFileSystem()
        >>> config = _load_or_create_config(fs, "/home/user/.vscode/mcp.json")
        >>> config["servers"]["ai-session-tracker"] = {...}
    """
    if fs.exists(config_path):
        try:
            content = fs.read_text(config_path)
            config: dict[str, Any] = json.loads(content)
            _log(f"Found existing config: {config_path}", emoji="📄")
        except json.JSONDecodeError:
            _log(f"Invalid JSON in {config_path}, creating backup", emoji="⚠️")
            backup_path = f"{config_path}.bak"
            fs.rename(config_path, backup_path)
            config = {}
    else:
        config = {}
        _log(f"Creating new config: {config_path}", emoji="📄")

    # Ensure servers section exists
    if "servers" not in config:
        config["servers"] = {}

    return config


def _copy_agent_files(
    fs: FileSystem,
    bundled_dir: str,
    github_dir: str,
    working_dir: str,
) -> None:
    """
    Copy bundled agent files to project's .github directory.

    Copies agent definitions and instruction files from the installed
    package to the user's project. Files that already exist are skipped
    to preserve user customizations.

    Business context: Agent files configure VS Code's AI assistant behavior
    for session tracking. Installing them to .github ensures they're
    version-controlled and shared with team members.

    Args:
        fs: FileSystem instance for file operations.
        bundled_dir: Path to bundled agent_files directory in the package.
        github_dir: Path to project's .github directory (destination).
        working_dir: Project root for relative path display in logs.

    Returns:
        None. Files are copied to the destination directory.

    Raises:
        OSError: If file copy operations fail.

    Example:
        >>> fs = RealFileSystem()
        >>> _copy_agent_files(
        ...     fs,
        ...     "/pkg/agent_files",
        ...     "/project/.github",
        ...     "/project"
        ... )
    """
    if not fs.exists(bundled_dir):
        return

    for subdir in AGENT_SUBDIRS:
        src_dir = _build_path(bundled_dir, subdir)
        dst_dir = _build_path(github_dir, subdir)
        if not fs.exists(src_dir):
            continue

        fs.makedirs(dst_dir, exist_ok=True)
        for src_file in fs.iterdir(src_dir):
            if not fs.is_file(src_file):
                continue

            filename = Path(src_file).name
            dst_file = _build_path(dst_dir, filename)
            rel_path = dst_file.replace(f"{working_dir}/", "")

            if not fs.exists(dst_file):
                fs.copy_file(src_file, dst_file)
                _log(f"Created {rel_path}", emoji="📝")
            else:
                _log(f"{rel_path} exists", emoji="✓")


def run_install(
    filesystem: FileSystem | None = None,
    cwd: str | None = None,
    package_dir: str | None = None,
    *,
    global_install: bool = False,
    prompts_only: bool = False,
    mcp_only: bool = False,
    service: bool = False,
) -> None:
    """
    Install AI Session Tracker for the current project.

    Creates or updates .vscode/mcp.json to include the ai-session-tracker
    MCP server configuration, and copies agent and instruction files
    to .github/ for VS Code agent integration.

    Business context: Initialization is the first step for new projects.
    It sets up the MCP configuration so VS Code recognizes the session
    tracker and provides the custom agent for tracked agent workflows.

    Files created/updated:
    - .vscode/mcp.json: MCP server configuration
    - .github/agents/: Session tracking custom agents
    - .github/instructions/: AI instruction files

    Args:
        filesystem: Optional FileSystem for testability. Defaults to
            RealFileSystem for production use.
        cwd: Optional working directory. Defaults to current directory.
        package_dir: Optional package directory for bundled files.
        global_install: If True, install to user's global VS Code settings
            instead of project .vscode directory.
        prompts_only: If True, only install agent files (agents/instructions),
            skip MCP configuration.
        mcp_only: If True, only install MCP configuration, skip agent files.
        service: If True, also install as a system service for auto-start.

    Returns:
        None. Progress messages printed to stdout.

    Raises:
        PermissionError: If directory creation fails.
        JSONDecodeError: If existing mcp.json is invalid (creates backup).

    Example:
        >>> # From command line in project root:
        >>> # ai-session-tracker install
        >>> run_install()
        📄 Creating new config: .vscode/mcp.json
        ➕ Adding ai-session-tracker to MCP servers
        ✅ Successfully installed ai-session-tracker
    """
    from .filesystem import RealFileSystem

    fs = filesystem or RealFileSystem()
    working_dir = cwd or str(Path.cwd())
    pkg_dir = package_dir or str(Path(__file__).parent)

    # Determine target directory for MCP config
    if global_install:
        # Use VS Code user settings directory
        home = str(Path.home())
        if os.name == "nt":  # Windows
            vscode_dir = _build_path(home, "AppData", "Roaming", "Code", "User")
        elif sys.platform == "darwin":  # macOS
            vscode_dir = _build_path(home, "Library", "Application Support", "Code", "User")
        else:  # Linux
            vscode_dir = _build_path(home, ".config", "Code", "User")
        _log(f"Installing globally to: {vscode_dir}", emoji="🌐")
    else:
        vscode_dir = _build_path(working_dir, VSCODE_DIR)

    config_path = _build_path(vscode_dir, CONFIG_FILE)
    bundled_dir = _build_path(pkg_dir, AGENT_FILES_DIR)
    github_dir = _build_path(working_dir, GITHUB_DIR)

    # Find the executable path using injected filesystem
    bin_dir = str(Path(sys.executable).parent)
    server_cmd_path = _build_path(bin_dir, SERVER_NAME)

    if not fs.exists(server_cmd_path):
        # Fallback to module invocation
        server_config = {
            "command": sys.executable,
            "args": ["-m", MODULE_NAME, "server"],
        }
    else:
        server_config = {
            "command": server_cmd_path,
            "args": ["server"],
        }

    # Install MCP configuration unless prompts_only is set
    if not prompts_only:
        # Load or create config
        config = _load_or_create_config(fs, config_path)

        # Check if already installed
        if SERVER_NAME in config["servers"]:
            existing = config["servers"][SERVER_NAME]
            if existing == server_config:
                _log(f"{SERVER_NAME} already installed and up to date", emoji="✅")
            else:
                _log(f"Updating {SERVER_NAME} configuration", emoji="🔄")
                config["servers"][SERVER_NAME] = server_config
        else:
            _log(f"Adding {SERVER_NAME} to MCP servers", emoji="➕")
            config["servers"][SERVER_NAME] = server_config

        # Create .vscode directory if needed
        fs.makedirs(vscode_dir, exist_ok=True)

        # Write config
        fs.write_text(config_path, json.dumps(config, indent=2))

    # Copy agent files to .github/ unless mcp_only is set
    if not mcp_only:
        _copy_agent_files(fs, bundled_dir, github_dir, working_dir)

    # Install as service if requested
    if service:
        _log("Installing as system service...", emoji="🔧")
        try:
            from .service import get_service_manager

            manager = get_service_manager(fs)
            if manager.install():
                _log("Service installed successfully", emoji="✅")
                _log("Service will start automatically on login")
                _log("Use 'ai-session-tracker service start' to start now")
            else:
                _log("Failed to install service", emoji="❌")
        except NotImplementedError as e:
            _log(f"Service installation not supported: {e}", emoji="⚠️")

    _log(f"Successfully installed {SERVER_NAME}", emoji="✅")
    if not prompts_only:
        _log(f"Config: {config_path}")
        _log(f"Command: {server_config['command']} {' '.join(server_config['args'])}")


def run_service(
    action: str,
    filesystem: FileSystem | None = None,
) -> int:
    """
    Manage AI Session Tracker system service.

    Controls the AI Session Tracker service that runs in the background.
    Supports start, stop, status, and uninstall operations.

    Business context: The service provides persistent background operation
    of the MCP server, enabling session tracking without requiring
    per-project setup or manual server starts.

    Args:
        action: Service action to perform. One of:
            - 'start': Start the service
            - 'stop': Stop the service
            - 'status': Show service status
            - 'uninstall': Remove the service
        filesystem: Optional FileSystem for testability.

    Returns:
        int: Exit code (0 for success, 1 for failure).

    Example:
        >>> run_service('status')
        🔍 Service Status:
        📦 Installed: Yes
        🟢 Running: Yes
        0
    """
    from .service import get_service_manager

    try:
        manager = get_service_manager(filesystem)
    except NotImplementedError as e:
        _log(f"Service management not supported: {e}", emoji="❌")
        return 1

    if action == "start":
        _log("Starting service...", emoji="🚀")
        if manager.start():
            _log("Service started successfully", emoji="✅")
            return 0
        else:
            _log("Failed to start service", emoji="❌")
            return 1

    elif action == "stop":
        _log("Stopping service...", emoji="🛑")
        if manager.stop():
            _log("Service stopped successfully", emoji="✅")
            return 0
        else:
            _log("Failed to stop service", emoji="❌")
            return 1

    elif action == "status":
        _log("Service Status:", emoji="🔍")
        status = manager.status()
        installed_icon = "✅" if status["installed"] else "❌"
        running_icon = "🟢" if status["running"] else "🔴"
        _log(f"Installed: {'Yes' if status['installed'] else 'No'}", emoji=installed_icon)
        _log(f"Running: {'Yes' if status['running'] else 'No'}", emoji=running_icon)
        _log(f"Status: {status['status']}")
        return 0

    elif action == "uninstall":
        _log("Uninstalling service...", emoji="🗑️")
        if manager.uninstall():
            _log("Service uninstalled successfully", emoji="✅")
            return 0
        else:
            _log("Failed to uninstall service", emoji="❌")
            return 1

    else:
        _log(f"Unknown action: {action}", emoji="❌")
        return 1


# =============================================================================
# SESSION TRACKING CLI COMMANDS
# =============================================================================


def _output_result(result: dict[str, Any], json_output: bool = False) -> int:
    """
    Output service result to stdout.

    Args:
        result: ServiceResult.to_dict() output.
        json_output: If True, output as JSON. Otherwise human-readable.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            _log(result["message"], emoji="✅")
            if result.get("data"):
                for key, value in result["data"].items():
                    if key not in ("report",):  # Skip large data
                        print(f"  {key}: {value}")
        else:
            _log(result["message"], emoji="❌")
            if result.get("error"):
                print(f"  Error: {result['error']}")

    return 0 if result["success"] else 1


def run_session_start(
    name: str,
    task_type: str,
    model: str,
    mins: float,
    source: str,
    context: str = "",
    *,
    json_output: bool = False,
) -> int:
    """
    Start a new tracking session via CLI.

    Creates a new session with the specified parameters and outputs
    the session_id for use in subsequent commands.

    Business context: Enables session tracking from CLI agents,
    scripts, and CI/CD pipelines that cannot access MCP servers.

    Args:
        name: Descriptive name for the task.
        task_type: Category (code_generation, debugging, etc.).
        model: AI model being used.
        mins: Human time estimate in minutes.
        source: Estimate source (manual, issue_tracker, historical).
        context: Optional additional context.
        json_output: If True, output JSON instead of human-readable text.

    Returns:
        int: Exit code (0 for success, 1 for failure).

    Example:
        >>> # ai-session-tracker start --name "Add login" --type code_generation \\
        >>> #   --model claude-opus-4-20250514 --mins 60 --source manual
    """
    from .session_service import SessionService

    service = SessionService()
    result = service.start_session(
        name=name,
        task_type=task_type,
        model_name=model,
        human_time_estimate_minutes=mins,
        estimate_source=source,
        context=context,
    )
    return _output_result(result.to_dict(), json_output)


def run_session_log(
    session_id: str,
    prompt: str,
    summary: str,
    rating: int,
    iterations: int = 1,
    tools: list[str] | None = None,
    *,
    json_output: bool = False,
) -> int:
    """
    Log an interaction via CLI.

    Records a prompt/response exchange with effectiveness rating.

    Args:
        session_id: Parent session identifier.
        prompt: The prompt text sent to AI.
        summary: Brief description of AI response.
        rating: Effectiveness rating 1-5.
        iterations: Number of attempts.
        tools: List of tools used.
        json_output: If True, output JSON.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    from .session_service import SessionService

    service = SessionService()
    result = service.log_interaction(
        session_id=session_id,
        prompt=prompt,
        response_summary=summary,
        effectiveness_rating=rating,
        iteration_count=iterations,
        tools_used=tools or [],
    )
    return _output_result(result.to_dict(), json_output)


def run_session_end(
    session_id: str,
    outcome: str,
    notes: str = "",
    *,
    json_output: bool = False,
) -> int:
    """
    End a tracking session via CLI.

    Marks the session as completed with the specified outcome.

    Args:
        session_id: Session identifier to complete.
        outcome: 'success', 'partial', or 'failed'.
        notes: Optional summary notes.
        json_output: If True, output JSON.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    from .session_service import SessionService

    service = SessionService()
    result = service.end_session(
        session_id=session_id,
        outcome=outcome,
        notes=notes,
    )
    return _output_result(result.to_dict(), json_output)


def run_session_flag(
    session_id: str,
    issue_type: str,
    description: str,
    severity: str,
    *,
    json_output: bool = False,
) -> int:
    """
    Flag an issue via CLI.

    Records a problematic AI interaction for analysis.

    Args:
        session_id: Parent session identifier.
        issue_type: Issue category.
        description: Detailed description.
        severity: 'low', 'medium', 'high', or 'critical'.
        json_output: If True, output JSON.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    from .session_service import SessionService

    service = SessionService()
    result = service.flag_issue(
        session_id=session_id,
        issue_type=issue_type,
        description=description,
        severity=severity,
    )
    return _output_result(result.to_dict(), json_output)


def run_session_active(*, json_output: bool = False) -> int:
    """
    List active sessions via CLI.

    Returns sessions that haven't been ended yet.

    Args:
        json_output: If True, output JSON.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    from .session_service import SessionService

    service = SessionService()
    result = service.get_active_sessions()

    if json_output:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            sessions = result.data.get("active_sessions", []) if result.data else []
            if not sessions:
                _log("No active sessions found", emoji="📋")
            else:
                _log(f"Found {len(sessions)} active session(s):", emoji="📋")
                for s in sessions:
                    print(f"\n  {s['session_name']}")
                    print(f"    ID: {s['session_id']}")
                    print(f"    Type: {s['task_type']}")
                    print(f"    Started: {s['start_time']}")
        else:
            _log(result.message, emoji="❌")
            if result.error:
                print(f"  Error: {result.error}")

    return 0 if result.success else 1


def main() -> int:
    """
    Main CLI entry point for AI Session Tracker.

    Parses command-line arguments and dispatches to the appropriate
    subcommand handler: server, dashboard, report, or init. If no
    subcommand is specified, defaults to running the MCP server.

    Business context: This is the entry point installed as the
    'ai-session-tracker' console script. It provides a unified
    interface for all tracker functionality.

    Subcommands:
    - server: Run MCP server (default)
    - dashboard [--host HOST] [--port PORT]: Launch web dashboard
    - report: Print text analytics report
    - install: Install project with MCP configuration

    Returns:
        Exit code 0 for success. Non-zero codes reserved for future
        error handling.

    Raises:
        SystemExit: On --help or argument parsing errors.

    Example:
        >>> # From command line:
        >>> # ai-session-tracker dashboard --port 8080
        >>> sys.exit(main())  # Typical usage pattern
    """
    from .__version__ import __version__

    parser = argparse.ArgumentParser(
        prog="ai-session-tracker",
        description="AI Session Tracker MCP Server - Track AI coding sessions and ROI",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser(
        "server",
        help="Run MCP server (stdio mode)",
    )
    server_parser.add_argument(
        "--dashboard-host",
        default=None,
        help="Start dashboard on this host (e.g., 127.0.0.1)",
    )
    server_parser.add_argument(
        "--dashboard-port",
        type=int,
        default=None,
        help="Start dashboard on this port (e.g., 8000)",
    )

    # Dashboard command
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Launch web dashboard",
    )
    dashboard_parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Bind address (default: {DEFAULT_HOST})",
    )
    dashboard_parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port number (default: {DEFAULT_PORT})",
    )

    # Report command
    subparsers.add_parser(
        "report",
        help="Print analytics report to stdout",
    )

    # Install command
    install_parser = subparsers.add_parser(
        "install",
        help="Create .vscode/mcp.json for this project",
    )
    install_parser.add_argument(
        "--global",
        dest="global_install",
        action="store_true",
        help="Install to user's global VS Code settings instead of project",
    )
    install_parser.add_argument(
        "--prompts-only",
        action="store_true",
        help="Only install agent files (agents/instructions), skip MCP config",
    )
    install_parser.add_argument(
        "--mcp-only",
        action="store_true",
        help="Only install MCP configuration, skip agent files",
    )
    install_parser.add_argument(
        "--service",
        action="store_true",
        help="Install as a system service for auto-start on login",
    )

    # Service command
    service_parser = subparsers.add_parser(
        "service",
        help="Manage AI Session Tracker service",
    )
    service_parser.add_argument(
        "action",
        choices=["start", "stop", "status", "uninstall"],
        help="Service action to perform",
    )

    # =========================================================================
    # SESSION TRACKING CLI COMMANDS
    # =========================================================================

    # Start session command
    start_parser = subparsers.add_parser(
        "start",
        help="Start a new tracking session",
    )
    start_parser.add_argument(
        "--name",
        required=True,
        help="Descriptive name for the session",
    )
    start_parser.add_argument(
        "--type",
        dest="task_type",
        required=True,
        choices=[
            "code_generation",
            "debugging",
            "refactoring",
            "testing",
            "documentation",
            "analysis",
            "architecture_planning",
            "human_review",
        ],
        help="Task category",
    )
    start_parser.add_argument(
        "--model",
        required=True,
        help="AI model being used (e.g., 'claude-opus-4-20250514')",
    )
    start_parser.add_argument(
        "--mins",
        type=float,
        required=True,
        help="Human time estimate in minutes",
    )
    start_parser.add_argument(
        "--source",
        required=True,
        choices=["manual", "issue_tracker", "historical"],
        help="Where the time estimate came from",
    )
    start_parser.add_argument(
        "--context",
        default="",
        help="Additional context about the work",
    )
    start_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )

    # Log interaction command
    log_parser = subparsers.add_parser(
        "log",
        help="Log an AI interaction",
    )
    log_parser.add_argument(
        "--session-id",
        required=True,
        help="Session ID from start command",
    )
    log_parser.add_argument(
        "--prompt",
        required=True,
        help="The prompt sent to AI",
    )
    log_parser.add_argument(
        "--summary",
        required=True,
        help="Brief summary of AI response",
    )
    log_parser.add_argument(
        "--rating",
        type=int,
        required=True,
        choices=[1, 2, 3, 4, 5],
        help="Effectiveness rating (1=failed, 3=partial, 5=perfect)",
    )
    log_parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of attempts (default: 1)",
    )
    log_parser.add_argument(
        "--tools",
        nargs="*",
        default=[],
        help="Tools used in this interaction",
    )
    log_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )

    # End session command
    end_parser = subparsers.add_parser(
        "end",
        help="End a tracking session",
    )
    end_parser.add_argument(
        "--session-id",
        required=True,
        help="Session ID to end",
    )
    end_parser.add_argument(
        "--outcome",
        required=True,
        choices=["success", "partial", "failed"],
        help="Session result",
    )
    end_parser.add_argument(
        "--notes",
        default="",
        help="Summary notes about the session",
    )
    end_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )

    # Flag issue command
    flag_parser = subparsers.add_parser(
        "flag",
        help="Flag a problematic AI interaction",
    )
    flag_parser.add_argument(
        "--session-id",
        required=True,
        help="Session ID for the issue",
    )
    flag_parser.add_argument(
        "--type",
        dest="issue_type",
        required=True,
        help="Issue category (e.g., 'hallucination', 'incorrect_output')",
    )
    flag_parser.add_argument(
        "--desc",
        dest="description",
        required=True,
        help="Detailed description of what went wrong",
    )
    flag_parser.add_argument(
        "--severity",
        required=True,
        choices=["low", "medium", "high", "critical"],
        help="Impact level",
    )
    flag_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )

    # Active sessions command
    active_parser = subparsers.add_parser(
        "active",
        help="List active (not ended) sessions",
    )
    active_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    if args.command == "dashboard":
        run_dashboard(host=args.host, port=args.port)
    elif args.command == "report":
        run_report()
    elif args.command == "install":
        run_install(
            global_install=args.global_install,
            prompts_only=args.prompts_only,
            mcp_only=args.mcp_only,
            service=args.service,
        )
    elif args.command == "service":
        return run_service(args.action)
    elif args.command == "start":
        return run_session_start(
            name=args.name,
            task_type=args.task_type,
            model=args.model,
            mins=args.mins,
            source=args.source,
            context=args.context,
            json_output=args.json_output,
        )
    elif args.command == "log":
        return run_session_log(
            session_id=args.session_id,
            prompt=args.prompt,
            summary=args.summary,
            rating=args.rating,
            iterations=args.iterations,
            tools=args.tools,
            json_output=args.json_output,
        )
    elif args.command == "end":
        return run_session_end(
            session_id=args.session_id,
            outcome=args.outcome,
            notes=args.notes,
            json_output=args.json_output,
        )
    elif args.command == "flag":
        return run_session_flag(
            session_id=args.session_id,
            issue_type=args.issue_type,
            description=args.description,
            severity=args.severity,
            json_output=args.json_output,
        )
    elif args.command == "active":
        return run_session_active(json_output=args.json_output)
    elif args.command == "server":
        run_server(
            dashboard_host=args.dashboard_host,
            dashboard_port=args.dashboard_port,
        )
    else:
        # Default: run server without dashboard
        run_server()

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
