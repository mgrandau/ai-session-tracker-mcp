"""Tests for web module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if FastAPI not installed
fastapi = pytest.importorskip("fastapi")

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

from ai_session_tracker_mcp.storage import StorageManager  # noqa: E402
from ai_session_tracker_mcp.web import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Create test client with mocked storage."""
    from fastapi.testclient import TestClient as TC

    app = create_app()
    return TC(app)


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create mock storage with sample data."""
    storage = MagicMock(spec=StorageManager)
    storage.load_sessions.return_value = {
        "session-1": {
            "project": "test-project",
            "status": "completed",
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T11:00:00Z",
        }
    }
    storage.load_interactions.return_value = [
        {"session_id": "session-1", "effectiveness_rating": 4}
    ]
    storage.load_issues.return_value = []
    return storage


class TestWebAppCreation:
    """Tests for web app factory."""

    def test_create_app_returns_fastapi(self) -> None:
        """create_app returns FastAPI instance."""
        from fastapi import FastAPI

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_has_routes(self) -> None:
        """App has expected routes registered."""
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/" in routes
        assert "/api/overview" in routes
        assert "/api/report" in routes


class TestDashboardPage:
    """Tests for main dashboard page."""

    def test_dashboard_page_returns_html(self, client: TestClient) -> None:
        """Dashboard page returns HTML."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_storage.load_issues.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]

    def test_dashboard_contains_title(self, client: TestClient) -> None:
        """Dashboard HTML contains title."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_storage.load_issues.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/")
            assert "AI Session Tracker" in response.text

    def test_dashboard_contains_htmx(self, client: TestClient) -> None:
        """Dashboard includes htmx script."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_storage.load_issues.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/")
            assert "htmx" in response.text


class TestPartialRoutes:
    """Tests for htmx partial routes."""

    def test_sessions_partial(self, client: TestClient) -> None:
        """Sessions partial returns HTML table."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/partials/sessions")
            assert response.status_code == 200
            assert "<table>" in response.text

    def test_roi_partial(self, client: TestClient) -> None:
        """ROI partial returns HTML."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/partials/roi")
            assert response.status_code == 200
            assert "ROI" in response.text

    def test_effectiveness_partial(self, client: TestClient) -> None:
        """Effectiveness partial returns HTML."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_interactions.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/partials/effectiveness")
            assert response.status_code == 200
            assert "Effectiveness" in response.text


class TestChartRoutes:
    """Tests for chart image routes."""

    def test_effectiveness_chart_route(self, client: TestClient) -> None:
        """Effectiveness chart returns image."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_interactions.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/charts/effectiveness.png")
            assert response.status_code == 200
            # Either PNG or SVG placeholder
            assert response.headers["content-type"] in [
                "image/png",
                "image/svg+xml",
            ]

    def test_roi_chart_route(self, client: TestClient) -> None:
        """ROI chart returns image."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/charts/roi.png")
            assert response.status_code == 200

    def test_timeline_chart_route(self, client: TestClient) -> None:
        """Timeline chart returns image."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_get.return_value = mock_storage

            response = client.get("/charts/timeline.png")
            assert response.status_code == 200


class TestAPIRoutes:
    """Tests for JSON API routes."""

    def test_api_overview(self, client: TestClient) -> None:
        """API overview returns JSON."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_storage.load_issues.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/api/overview")
            assert response.status_code == 200
            data = response.json()
            assert "sessions" in data
            assert "roi" in data
            assert "effectiveness" in data

    def test_api_overview_with_sessions(self, client: TestClient) -> None:
        """API overview includes session data."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {
                "s1": {
                    "project": "myproject",
                    "status": "completed",
                    "start_time": "2024-01-01T10:00:00Z",
                    "end_time": "2024-01-01T11:00:00Z",
                }
            }
            mock_storage.load_interactions.return_value = [
                {"session_id": "s1", "effectiveness_rating": 5}
            ]
            mock_storage.load_issues.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/api/overview")
            data = response.json()
            assert len(data["sessions"]) == 1
            assert data["sessions"][0]["project"] == "myproject"

    def test_api_report(self, client: TestClient) -> None:
        """API report returns text report."""
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_storage.load_issues.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/api/report")
            assert response.status_code == 200
            data = response.json()
            assert "report" in data
            assert "SESSION SUMMARY" in data["report"] or "ANALYTICS" in data["report"]


class TestRunDashboard:
    """Tests for run_dashboard function."""

    def test_run_dashboard_exists(self) -> None:
        """run_dashboard function exists."""
        from ai_session_tracker_mcp.web import run_dashboard

        assert callable(run_dashboard)

    def test_run_dashboard_calls_uvicorn(self) -> None:
        """run_dashboard calls uvicorn.run."""
        from ai_session_tracker_mcp.web.app import run_dashboard

        with patch("ai_session_tracker_mcp.web.app.uvicorn.run") as mock_run:
            run_dashboard(host="0.0.0.0", port=9000)
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["host"] == "0.0.0.0"
            assert call_kwargs["port"] == 9000
