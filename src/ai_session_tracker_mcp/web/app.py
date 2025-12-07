"""
FastAPI application for AI Session Tracker dashboard.

PURPOSE: Main application factory and server runner.
AI CONTEXT: Creates app with all routes registered.
"""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import router


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title="AI Session Tracker",
        description="Dashboard for tracking AI coding sessions and ROI",
        version="0.1.0",
    )

    # Include routes
    app.include_router(router)

    # Mount static files if they exist
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return app


def run_dashboard(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """
    Run the dashboard server.

    Args:
        host: Bind address
        port: Port number
        reload: Enable auto-reload for development
    """
    uvicorn.run(
        "ai_session_tracker_mcp.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


# For direct execution
if __name__ == "__main__":
    run_dashboard()
