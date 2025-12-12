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
    ai-session-tracker init       # Create .vscode/mcp.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


def run_server() -> None:
    """
    Run the MCP server in stdio mode.

    Starts the AI Session Tracker MCP server which communicates via
    stdin/stdout using JSON-RPC 2.0 protocol. This is the default
    command and the mode used by VS Code for MCP integration.

    Business context: The MCP server is the core component that enables
    AI assistants in VS Code to track sessions, log interactions, and
    calculate ROI metrics during development workflows.

    Returns:
        None. Blocks until server shutdown (EOF on stdin).

    Raises:
        OSError: If storage directory cannot be created.

    Example:
        >>> # From command line:
        >>> # ai-session-tracker server
        >>> run_server()  # Blocks until Ctrl+C or client disconnect
    """
    from .server import main

    asyncio.run(main())


def run_dashboard(host: str = "127.0.0.1", port: int = 8000) -> None:
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

    print(f"🚀 Starting dashboard at http://{host}:{port}")
    print("   Press Ctrl+C to stop")
    start_web(host=host, port=port)


def run_report() -> None:
    """
    Print text analytics report to stdout.

    Generates and prints a comprehensive text report containing session
    summary, ROI metrics, effectiveness distribution, issue summary,
    and code quality metrics. Suitable for terminal viewing or piping.

    Business context: The text report provides a quick CLI-accessible
    summary for developers who want metrics without opening a browser.
    Can be redirected to files or used in scripts.

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
    from .statistics import StatisticsEngine
    from .storage import StorageManager

    storage = StorageManager()
    engine = StatisticsEngine()

    sessions = storage.load_sessions()
    interactions = storage.load_interactions()
    issues = storage.load_issues()

    report = engine.generate_summary_report(sessions, interactions, issues)
    print(report)


def run_init() -> None:
    """
    Initialize AI Session Tracker for the current project.

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

    Returns:
        None. Progress messages printed to stdout.

    Raises:
        PermissionError: If directory creation fails.
        JSONDecodeError: If existing mcp.json is invalid (creates backup).

    Example:
        >>> # From command line in project root:
        >>> # ai-session-tracker init
        >>> run_init()
        📄 Creating new config: .vscode/mcp.json
        ➕ Adding ai-session-tracker to MCP servers
        ✅ Successfully installed ai-session-tracker
    """
    import shutil

    vscode_dir = Path.cwd() / ".vscode"
    config_path = vscode_dir / "mcp.json"
    server_name = "ai-session-tracker"

    # Find package directory for bundled files
    package_dir = Path(__file__).parent
    bundled_vscode = package_dir / "agent_files"

    # Find the executable path
    executable = sys.executable
    # Get the directory containing python, then find our script
    bin_dir = Path(executable).parent
    server_cmd = bin_dir / "ai-session-tracker"

    if not server_cmd.exists():
        # Fallback to module invocation
        server_config = {
            "command": str(executable),
            "args": ["-m", "ai_session_tracker_mcp", "server"],
        }
    else:
        server_config = {
            "command": str(server_cmd),
            "args": ["server"],
        }

    # Load existing config or create new one
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
            print(f"📄 Found existing config: {config_path}")
        except json.JSONDecodeError:
            print(f"⚠️  Invalid JSON in {config_path}, creating backup")
            backup_path = config_path.with_suffix(".json.bak")
            config_path.rename(backup_path)
            config = {}
    else:
        config = {}
        print(f"📄 Creating new config: {config_path}")

    # Ensure servers section exists
    if "servers" not in config:
        config["servers"] = {}

    # Check if already installed
    if server_name in config["servers"]:
        existing = config["servers"][server_name]
        if existing == server_config:
            print(f"✅ {server_name} already installed and up to date")
        else:
            print(f"🔄 Updating {server_name} configuration")
            config["servers"][server_name] = server_config
    else:
        print(f"➕ Adding {server_name} to MCP servers")
        config["servers"][server_name] = server_config

    # Create .vscode directory if needed
    vscode_dir.mkdir(parents=True, exist_ok=True)

    # Write config
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    # Copy chatmodes and instructions to .github/ (where VS Code looks for them)
    github_dir = Path.cwd() / ".github"
    if bundled_vscode.exists():
        for subdir in ["chatmodes", "instructions"]:
            src_dir = bundled_vscode / subdir
            dst_dir = github_dir / subdir
            if src_dir.exists():
                dst_dir.mkdir(parents=True, exist_ok=True)
                for src_file in src_dir.iterdir():
                    if src_file.is_file():
                        dst_file = dst_dir / src_file.name
                        if not dst_file.exists():
                            shutil.copy2(src_file, dst_file)
                            print(f"📝 Created {dst_file.relative_to(Path.cwd())}")
                        else:
                            print(f"✓  {dst_file.relative_to(Path.cwd())} exists")

    print(f"✅ Successfully installed {server_name}")
    print(f"   Config: {config_path}")
    print(f"   Command: {server_config['command']} {' '.join(server_config['args'])}")


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
    - init: Initialize project with MCP configuration

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
    parser = argparse.ArgumentParser(
        prog="ai-session-tracker",
        description="AI Session Tracker MCP Server - Track AI coding sessions and ROI",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    subparsers.add_parser(
        "server",
        help="Run MCP server (stdio mode)",
    )

    # Dashboard command
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Launch web dashboard",
    )
    dashboard_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    dashboard_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number (default: 8000)",
    )

    # Report command
    subparsers.add_parser(
        "report",
        help="Print analytics report to stdout",
    )

    # Init command
    subparsers.add_parser(
        "init",
        help="Create .vscode/mcp.json for this project",
    )

    args = parser.parse_args()

    if args.command == "dashboard":
        run_dashboard(host=args.host, port=args.port)
    elif args.command == "report":
        run_report()
    elif args.command == "init":
        run_init()
    else:
        # Default: run server (also handles explicit "server" command)
        run_server()

    return 0


if __name__ == "__main__":
    sys.exit(main())
