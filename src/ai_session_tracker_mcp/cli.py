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
AGENT_SUBDIRS = ("chatmodes", "instructions")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
SUBPROCESS_TIMEOUT = 5


@lru_cache(maxsize=1)
def _get_logger() -> logging.Logger:
    """Get module logger (cached for thread safety)."""
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(__name__)


def _log(message: str, *, emoji: str = "") -> None:
    """Log message with optional emoji prefix for CLI output.

    Args:
        message: The message to log.
        emoji: Optional emoji prefix for visual CLI feedback.
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
    """Build path from parts using forward slash separator.

    Note: Uses forward slashes for virtual filesystem paths. These paths
    are used with the FileSystem abstraction, not native OS paths.

    Args:
        *parts: Path components to join.

    Returns:
        Joined path string with forward slash separators.
    """
    return "/".join(parts)


def _load_or_create_config(
    fs: FileSystem,
    config_path: str,
) -> dict[str, Any]:
    """Load existing MCP config or create empty one.

    If the config file exists but contains invalid JSON, creates a backup
    and returns an empty config.

    Args:
        fs: FileSystem instance for file operations.
        config_path: Absolute path to mcp.json.

    Returns:
        Config dictionary with at least a 'servers' key.
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
    """Copy bundled agent files to project's .github directory.

    Copies chatmodes and instruction files from the package to the
    user's project, skipping files that already exist.

    Args:
        fs: FileSystem instance for file operations.
        bundled_dir: Path to bundled agent_files directory.
        github_dir: Path to project's .github directory.
        working_dir: Project root for relative path display.
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
) -> None:
    """
    Install AI Session Tracker for the current project.

    Creates or updates .vscode/mcp.json to include the ai-session-tracker
    MCP server configuration, and copies chatmode and instruction files
    to .github/ for VS Code agent integration.

    Business context: Initialization is the first step for new projects.
    It sets up the MCP configuration so VS Code recognizes the session
    tracker and provides the chatmode for tracked agent workflows.

    Files created/updated:
    - .vscode/mcp.json: MCP server configuration
    - .github/chatmodes/: Session tracking chat modes
    - .github/instructions/: AI instruction files

    Args:
        filesystem: Optional FileSystem for testability. Defaults to
            RealFileSystem for production use.
        cwd: Optional working directory. Defaults to current directory.
        package_dir: Optional package directory for bundled files.

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

    # Build paths using constants
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

    # Copy agent files to .github/
    _copy_agent_files(fs, bundled_dir, github_dir, working_dir)

    _log(f"Successfully installed {SERVER_NAME}", emoji="✅")
    _log(f"Config: {config_path}")
    _log(f"Command: {server_config['command']} {' '.join(server_config['args'])}")


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
    subparsers.add_parser(
        "install",
        help="Create .vscode/mcp.json for this project",
    )

    args = parser.parse_args()

    if args.command == "dashboard":
        run_dashboard(host=args.host, port=args.port)
    elif args.command == "report":
        run_report()
    elif args.command == "install":
        run_install()
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
