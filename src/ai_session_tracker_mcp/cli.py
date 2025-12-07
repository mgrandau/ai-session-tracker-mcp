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
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def run_server() -> None:
    """Run the MCP server."""
    from .server import main

    asyncio.run(main())


def run_dashboard(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launch the web dashboard."""
    from .web import run_dashboard as start_web

    print(f"🚀 Starting dashboard at http://{host}:{port}")
    print("   Press Ctrl+C to stop")
    start_web(host=host, port=port)


def run_report() -> None:
    """Print text analytics report to stdout."""
    from .statistics import StatisticsEngine
    from .storage import StorageManager

    storage = StorageManager()
    engine = StatisticsEngine()

    sessions = storage.load_sessions()
    interactions = storage.load_interactions()
    issues = storage.load_issues()

    report = engine.generate_summary_report(sessions, interactions, issues)
    print(report)


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 for success).
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

    args = parser.parse_args()

    if args.command == "dashboard":
        run_dashboard(host=args.host, port=args.port)
    elif args.command == "report":
        run_report()
    else:
        # Default: run server (also handles explicit "server" command)
        run_server()

    return 0


if __name__ == "__main__":
    sys.exit(main())
