"""
Web dashboard module for AI Session Tracker.

PURPOSE: FastAPI-based web UI with htmx for dynamic updates.
AI CONTEXT: Optional module - requires 'web' extras to be installed.

FEATURES:
- Real-time dashboard with auto-refresh
- Server-side chart rendering (matplotlib)
- htmx for dynamic updates without JavaScript
- REST-like API endpoints for MCP client access

USAGE:
    # Via CLI
    ai-session-tracker dashboard

    # Programmatically
    from ai_session_tracker_mcp.web import create_app
    app = create_app()
    # Run with uvicorn
"""

from .app import create_app, run_dashboard

__all__ = ["create_app", "run_dashboard"]
