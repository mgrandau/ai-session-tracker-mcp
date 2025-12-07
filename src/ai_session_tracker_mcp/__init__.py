"""
AI Session Tracker MCP Server.

PURPOSE: Track AI coding sessions and measure developer productivity via MCP.
AI CONTEXT: This package provides an MCP server for session tracking and analytics.

PACKAGE STRUCTURE:
- server.py: MCP server with tool handlers
- storage.py: JSON file persistence
- models.py: Data models (Session, Interaction, Issue)
- statistics.py: ROI and productivity calculations
- dashboard.py: Tkinter GUI for visualization
- config.py: Configuration constants

QUICK START:
    # Run MCP server
    python -m ai_session_tracker_mcp.server

    # Launch dashboard
    python -m ai_session_tracker_mcp.dashboard

MCP TOOLS:
1. start_ai_session - Begin tracking session
2. log_ai_interaction - Record prompt/response
3. end_ai_session - Complete session
4. flag_ai_issue - Report problems
5. log_code_metrics - Analyze code quality
6. get_ai_observability - View analytics
"""

from ai_session_tracker_mcp.__version__ import (
    __author__,
    __copyright__,
    __description__,
    __license__,
    __title__,
    __url__,
    __version__,
    __version_date__,
)

__all__ = [
    "__version__",
    "__version_date__",
    "__title__",
    "__description__",
    "__url__",
    "__author__",
    "__license__",
    "__copyright__",
]
