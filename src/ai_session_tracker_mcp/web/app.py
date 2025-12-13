"""
FastAPI application for AI Session Tracker dashboard.

PURPOSE: Main application factory and server runner.
AI CONTEXT: Creates app with all routes registered.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..__version__ import __version__
from .routes import router

__all__ = ["create_app", "run_dashboard"]

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
    """
    Manage application lifecycle with startup/shutdown hooks.

    Context manager that runs setup code before the application starts
    accepting requests and cleanup code after the last request completes.

    Business context: Provides observability into dashboard server state
    changes. Startup logging confirms successful initialization, while
    shutdown logging aids debugging of unexpected terminations.

    Args:
        app: The FastAPI application instance (provided by FastAPI).

    Yields:
        None. Control returns to FastAPI to handle requests.

    Example:
        >>> # Used automatically by create_app()
        >>> app = create_app()  # lifespan hooks registered
    """
    # Startup
    logger.info("AI Session Tracker dashboard starting (v%s)", __version__)
    yield
    # Shutdown
    logger.info("AI Session Tracker dashboard shutting down")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI dashboard application.

    Factory function that creates a new FastAPI instance with all routes
    registered and static files mounted. Uses the application factory
    pattern for testability and flexibility.

    Business context: The FastAPI app serves the web dashboard, providing
    both HTML pages for human viewing and JSON APIs for programmatic access
    to session tracking data and analytics.

    Returns:
        Configured FastAPI application instance with:
        - All dashboard routes registered (/, /partials/*, /charts/*, /api/*)
        - Static files mounted at /static if the static directory exists
        - OpenAPI documentation available at /docs
        - Metadata including title, description, and version

    Raises:
        ImportError: If FastAPI or required dependencies are not installed.

    Example:
        >>> app = create_app()
        >>> # Use with uvicorn programmatically
        >>> import uvicorn
        >>> uvicorn.run(app, host='127.0.0.1', port=8000)

        >>> # Or for testing
        >>> from fastapi.testclient import TestClient
        >>> client = TestClient(create_app())
        >>> response = client.get('/')
        >>> response.status_code
        200
    """
    app = FastAPI(
        title="AI Session Tracker",
        description="Dashboard for tracking AI coding sessions and ROI",
        version=__version__,
        lifespan=lifespan,
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
    log_level: str = "info",
) -> None:
    """
    Launch the AI Session Tracker web dashboard server.

    Starts a uvicorn ASGI server hosting the FastAPI dashboard application.
    The dashboard provides real-time visualization of session metrics, ROI
    calculations, and effectiveness charts via an htmx-powered interface.

    Business context: The web dashboard is the primary interface for
    stakeholders to monitor AI productivity. It provides visual ROI
    justification and helps identify patterns in AI effectiveness.

    Args:
        host: Network interface to bind the server to. Use '127.0.0.1'
            for local-only access (default) or '0.0.0.0' for network access.
        port: TCP port number for the HTTP server. Default 8000.
            Common alternatives: 3000, 5000, 8080.
        reload: Enable auto-reload on code changes for development.
            Should be False in production for stability.
        log_level: Uvicorn logging verbosity. One of 'critical', 'error',
            'warning', 'info' (default), 'debug', or 'trace'.

    Returns:
        None. This function blocks until the server is stopped (Ctrl+C).

    Raises:
        OSError: If the port is already in use or host is invalid.
        ImportError: If uvicorn is not installed.

    Example:
        >>> # Start development server
        >>> run_dashboard(host='127.0.0.1', port=8000, reload=True)
        # Server runs at http://127.0.0.1:8000

        >>> # Start production server (accessible on network)
        >>> run_dashboard(host='0.0.0.0', port=80)
    """
    uvicorn.run(
        "ai_session_tracker_mcp.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


# For direct execution
if __name__ == "__main__":
    run_dashboard()
