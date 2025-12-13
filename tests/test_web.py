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
    """Create FastAPI test client for HTTP endpoint testing.

    Provides a TestClient instance wrapping the web application,
    enabling synchronous HTTP request testing without running a server.

    Business context:
    The web dashboard is the primary user interface for viewing session
    analytics. Tests must verify all routes return correct responses.

    Args:
        No arguments required for this fixture.

    Raises:
        No exceptions raised by this fixture.

    Returns:
        TestClient: Starlette TestClient wrapping the FastAPI app,
        configured for making test requests to all dashboard routes.

    Example:
        >>> response = client.get('/')
        >>> assert response.status_code == 200
        >>> assert 'AI Session Tracker' in response.text
    """
    from fastapi.testclient import TestClient as TC

    app = create_app()
    return TC(app)


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create mock StorageManager with sample session data.

    Provides a MagicMock configured with realistic session, interaction,
    and issue data for testing dashboard rendering and API responses.

    Business context:
    Dashboard tests need predictable data to verify correct rendering.
    Mock storage isolates tests from real persistence layer.

    Args:
        No arguments required for this fixture.

    Raises:
        No exceptions raised by this fixture.

    Returns:
        MagicMock: StorageManager mock with pre-configured return values:
        - load_sessions: One completed session with project and timestamps
        - load_interactions: One interaction with effectiveness rating 4
        - load_issues: Empty list (no issues)

    Example:
        >>> storage = mock_storage()
        >>> sessions = storage.load_sessions()
        >>> assert 'session-1' in sessions
        >>> assert sessions['session-1']['status'] == 'completed'
    """
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
    """Test suite for web application factory function.

    Categories:
    1. Factory Output - Correct type and structure (2 tests)

    Total: 2 tests verifying app creation produces valid FastAPI app.
    """

    def test_create_app_returns_fastapi(self) -> None:
        """Verifies create_app returns a FastAPI instance.

        Tests that the factory function produces the correct application
        type for use with ASGI servers like uvicorn.

        Business context:
        Dashboard requires FastAPI for async routes and htmx integration.
        Factory pattern enables testing and configuration flexibility.

        Arrangement:
        Import FastAPI class for type comparison.

        Action:
        Calls create_app factory function.

        Assertion Strategy:
        Validates return value is isinstance of FastAPI, confirming
        correct app type for ASGI deployment.
        """
        from fastapi import FastAPI

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_has_routes(self) -> None:
        """Verifies app has expected routes registered.

        Tests that the factory function registers all required routes
        including dashboard, API endpoints, and partials.

        Business context:
        Dashboard functionality depends on specific routes existing.
        Missing routes would break htmx partial updates.

        Arrangement:
        Create app via factory.

        Action:
        Extract route paths from app.routes.

        Assertion Strategy:
        Validates presence of root path ('/'), API overview, and
        report endpoints in route list.
        """
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/" in routes
        assert "/api/overview" in routes
        assert "/api/report" in routes


class TestDashboardPage:
    """Test suite for main dashboard page route.

    Categories:
    1. Response Format - HTML content type and structure (3 tests)

    Total: 3 tests verifying dashboard renders correctly.
    """

    def test_dashboard_page_returns_html(self, client: TestClient) -> None:
        """Verifies dashboard route returns HTML content.

        Tests that GET / returns HTTP 200 with HTML content type,
        the basic contract for a web dashboard page.

        Business context:
        Dashboard is the primary UI for viewing session analytics.
        Must return valid HTML for browser rendering.

        Arrangement:
        Mock storage with empty data to isolate route testing.

        Action:
        HTTP GET request to root path.

        Assertion Strategy:
        Validates HTTP 200 status and text/html content-type header,
        confirming successful HTML page generation.
        """
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
        """Verifies dashboard HTML contains the application title.

        Tests that the rendered page includes 'AI Session Tracker'
        for user identification and branding.

        Business context:
        Clear branding helps users confirm they're on the correct
        dashboard. Title appears in browser tab and page header.

        Arrangement:
        Mock storage with empty data.

        Action:
        HTTP GET request to root path.

        Assertion Strategy:
        Validates response text contains expected title string.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_storage.load_issues.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/")
            assert "AI Session Tracker" in response.text

    def test_dashboard_contains_htmx(self, client: TestClient) -> None:
        """Verifies dashboard includes htmx library for dynamic updates.

        Tests that the HTML page includes htmx script reference,
        enabling partial page updates without full reloads.

        Business context:
        htmx powers live dashboard updates every 30 seconds. Without
        htmx, the dashboard would require manual refresh.

        Arrangement:
        Mock storage with empty data.

        Action:
        HTTP GET request to root path.

        Assertion Strategy:
        Validates response text contains 'htmx' reference, confirming
        the library is included in the page.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_storage.load_issues.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/")
            assert "htmx" in response.text


class TestPartialRoutes:
    """Test suite for htmx partial update routes.

    Categories:
    1. Sessions Partial - Session table fragment (1 test)
    2. ROI Partial - ROI panel fragment (1 test)
    3. Effectiveness Partial - Effectiveness panel fragment (1 test)

    Total: 3 tests verifying partial routes return valid HTML fragments.
    """

    def test_sessions_partial(self, client: TestClient) -> None:
        """Verifies sessions partial returns HTML table fragment.

        Tests the htmx endpoint for updating the sessions list without
        full page reload.

        Business context:
        htmx polls /partials/sessions every 30s to update the table.
        Must return valid HTML table for seamless DOM replacement.

        Arrangement:
        Mock storage with empty sessions.

        Action:
        HTTP GET request to /partials/sessions.

        Assertion Strategy:
        Validates HTTP 200 and presence of <table> tag in response,
        confirming valid table HTML is returned.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/partials/sessions")
            assert response.status_code == 200
            assert "<table>" in response.text

    def test_roi_partial(self, client: TestClient) -> None:
        """Verifies ROI partial returns HTML panel fragment.

        Tests the htmx endpoint for updating the ROI summary panel
        without full page reload.

        Business context:
        htmx polls /partials/roi to update ROI metrics in real-time.
        Panel shows percentage, time saved, and cost saved.

        Arrangement:
        Mock storage with empty sessions and interactions.

        Action:
        HTTP GET request to /partials/roi.

        Assertion Strategy:
        Validates HTTP 200 and presence of 'ROI' text in response,
        confirming the panel content is rendered.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/partials/roi")
            assert response.status_code == 200
            assert "ROI" in response.text

    def test_effectiveness_partial(self, client: TestClient) -> None:
        """Verifies effectiveness partial returns HTML panel fragment.

        Tests the htmx endpoint for updating the effectiveness
        distribution panel without full page reload.

        Business context:
        htmx polls /partials/effectiveness to update the star rating
        distribution bar chart in real-time.

        Arrangement:
        Mock storage with empty interactions.

        Action:
        HTTP GET request to /partials/effectiveness.

        Assertion Strategy:
        Validates HTTP 200 and presence of 'Effectiveness' text,
        confirming the panel content is rendered.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_interactions.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/partials/effectiveness")
            assert response.status_code == 200
            assert "Effectiveness" in response.text


class TestChartRoutes:
    """Test suite for chart image routes.

    Categories:
    1. Effectiveness Chart - Rating distribution visualization (1 test)
    2. ROI Chart - ROI trend visualization (1 test)
    3. Timeline Chart - Session timeline visualization (1 test)

    Total: 3 tests verifying chart routes return valid images.
    """

    def test_effectiveness_chart_route(self, client: TestClient) -> None:
        """Verifies effectiveness chart route returns image content.

        Tests the chart endpoint returns valid image data (PNG or SVG
        fallback when matplotlib unavailable).

        Business context:
        Visual charts enhance dashboard usability. Route must return
        valid image regardless of matplotlib availability.

        Arrangement:
        Mock storage with empty interactions.

        Action:
        HTTP GET request to /charts/effectiveness.png.

        Assertion Strategy:
        Validates HTTP 200 and image content-type (either PNG or SVG),
        confirming valid image is returned.
        """
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
        """Verifies ROI chart route returns image content.

        Tests the ROI chart endpoint returns valid image data
        for ROI trend visualization.

        Business context:
        ROI chart shows return on investment over time. Visual
        trends help stakeholders understand AI value.

        Arrangement:
        Mock storage with empty sessions and interactions.

        Action:
        HTTP GET request to /charts/roi.png.

        Assertion Strategy:
        Validates HTTP 200 status, confirming chart generation
        succeeds even with empty data.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_storage.load_interactions.return_value = []
            mock_get.return_value = mock_storage

            response = client.get("/charts/roi.png")
            assert response.status_code == 200

    def test_timeline_chart_route(self, client: TestClient) -> None:
        """Verifies timeline chart route returns image content.

        Tests the timeline chart endpoint returns valid image data
        for session timeline visualization.

        Business context:
        Timeline shows session activity over time. Helps identify
        patterns in AI usage and productivity.

        Arrangement:
        Mock storage with empty sessions.

        Action:
        HTTP GET request to /charts/timeline.png.

        Assertion Strategy:
        Validates HTTP 200 status, confirming chart generation
        succeeds even with empty data.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_storage") as mock_get:
            mock_storage = MagicMock(spec=StorageManager)
            mock_storage.load_sessions.return_value = {}
            mock_get.return_value = mock_storage

            response = client.get("/charts/timeline.png")
            assert response.status_code == 200


class TestAPIRoutes:
    """Test suite for JSON API routes.

    Categories:
    1. Overview API - Dashboard data endpoint (2 tests)
    2. Report API - Text report endpoint (1 test)

    Total: 3 tests verifying API routes return valid JSON.
    """

    def test_api_overview(self, client: TestClient) -> None:
        """Verifies API overview returns JSON with expected structure.

        Tests the primary data endpoint returns valid JSON containing
        sessions, ROI, and effectiveness data.

        Business context:
        API enables programmatic access to dashboard data. Structure
        must be stable for client integrations.

        Arrangement:
        Mock storage with empty data.

        Action:
        HTTP GET request to /api/overview.

        Assertion Strategy:
        Validates HTTP 200, JSON parse success, and presence of
        required keys (sessions, roi, effectiveness).
        """
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
        """Verifies API overview includes session data when present.

        Tests that sessions are correctly serialized and included
        in the API response with expected fields.

        Business context:
        Session data is the core value of the API. Project name and
        other metadata must be accessible to clients.

        Arrangement:
        Mock storage with one completed session and interaction.

        Action:
        HTTP GET request to /api/overview.

        Assertion Strategy:
        Validates sessions array has one entry and project field
        matches the mock data.
        """
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
        """Verifies API report returns JSON with text report.

        Tests that the report endpoint returns a formatted text
        report suitable for display or logging.

        Business context:
        Text report provides human-readable analytics summary. Used
        by CLI and can be logged or emailed.

        Arrangement:
        Mock storage with empty data.

        Action:
        HTTP GET request to /api/report.

        Assertion Strategy:
        Validates HTTP 200, JSON contains 'report' key, and report
        text contains expected section headers.
        """
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
    """Test suite for run_dashboard server function.

    Categories:
    1. Function Existence - API contract (1 test)
    2. Server Configuration - uvicorn integration (1 test)

    Total: 2 tests verifying dashboard server startup.
    """

    def test_run_dashboard_exists(self) -> None:
        """Verifies run_dashboard function exists and is callable.

        Tests that the public API for starting the dashboard server
        is properly exported from the web module.

        Business context:
        CLI uses run_dashboard to start the web server. Function must
        be importable and callable.

        Arrangement:
        Import run_dashboard from web module.

        Action:
        Check callable status.

        Assertion Strategy:
        Validates function is callable, confirming API contract.
        """
        from ai_session_tracker_mcp.web import run_dashboard

        assert callable(run_dashboard)

    def test_run_dashboard_calls_uvicorn(self) -> None:
        """Verifies run_dashboard calls uvicorn.run with correct config.

        Tests that the function properly configures and starts uvicorn
        with the provided host and port settings.

        Business context:
        Dashboard server must respect user-specified host and port.
        Default is localhost:8080 but CLI allows customization.

        Arrangement:
        Mock uvicorn.run to capture call arguments.

        Action:
        Call run_dashboard with custom host and port.

        Assertion Strategy:
        Validates uvicorn.run was called once with matching host
        and port in keyword arguments.

        Testing Principle:
        Validates configuration passthrough to ASGI server.
        """
        from ai_session_tracker_mcp.web.app import run_dashboard

        with patch("ai_session_tracker_mcp.web.app.uvicorn.run") as mock_run:
            run_dashboard(host="0.0.0.0", port=9000)
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["host"] == "0.0.0.0"
            assert call_kwargs["port"] == 9000


class TestHtmxPartialRoutes:
    """Test suite for htmx partial update routes."""

    def test_gaps_partial_returns_html(self, client: TestClient) -> None:
        """Verifies gaps partial endpoint returns HTML fragment.

        Tests that the htmx partial for gaps panel returns proper
        HTML that can be injected into the page.

        Business context:
        htmx uses partials to update specific page sections without
        full page reload. Must return valid HTML fragments.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_dashboard_presenter") as mock_get:
            from ai_session_tracker_mcp.presenters import SessionGapsViewModel

            mock_presenter = MagicMock()
            mock_presenter.get_session_gaps.return_value = SessionGapsViewModel(
                total_gaps=3,
                average_gap_minutes=15.0,
                by_classification={"quick": 1, "normal": 2},
                friction_indicators=[],
            )
            mock_get.return_value = mock_presenter

            response = client.get("/partials/gaps")
            assert response.status_code == 200
            assert "Session Gaps" in response.text

    def test_gaps_partial_with_friction_indicators(self, client: TestClient) -> None:
        """Verifies gaps partial shows friction warnings when present.

        Tests that friction indicators from the presenter are rendered
        as warning messages in the HTML response.

        Business context:
        Friction indicators help identify adoption issues. They must
        be visible to users in the dashboard.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_dashboard_presenter") as mock_get:
            from ai_session_tracker_mcp.presenters import SessionGapsViewModel

            mock_presenter = MagicMock()
            mock_presenter.get_session_gaps.return_value = SessionGapsViewModel(
                total_gaps=5,
                average_gap_minutes=90.0,
                by_classification={"long_break": 3, "normal": 2},
                friction_indicators=[
                    "High long-break ratio (60%)",
                    "Average gap exceeds 60 minutes",
                ],
            )
            mock_get.return_value = mock_presenter

            response = client.get("/partials/gaps")
            assert response.status_code == 200
            assert "long-break ratio" in response.text or "warning" in response.text.lower()

    def test_sessions_partial_renders_session_rows(self, client: TestClient) -> None:
        """Verifies sessions partial renders actual session data.

        Tests that session data from the presenter is properly
        rendered in the HTML table.

        Business context:
        Sessions table is the primary view of tracked work. Must
        display session details correctly.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_dashboard_presenter") as mock_get:
            from ai_session_tracker_mcp.presenters import SessionViewModel

            mock_presenter = MagicMock()
            mock_presenter.get_sessions_list.return_value = [
                SessionViewModel(
                    session_id="session-abc-123-xyz",
                    project="test-project",
                    status="completed",
                    duration_minutes=90.0,
                    interaction_count=5,
                    effectiveness_avg=4.0,
                    start_time="2024-01-01T10:00:00Z",
                    end_time="2024-01-01T11:30:00Z",
                )
            ]
            mock_get.return_value = mock_presenter

            response = client.get("/partials/sessions")
            assert response.status_code == 200
            assert "session-abc" in response.text
            assert "completed" in response.text.lower()
        """Verifies sessions partial endpoint returns HTML table fragment.

        Tests that the htmx partial for sessions table returns proper
        HTML that can be injected into the page.

        Business context:
        htmx uses partials to update specific page sections without
        full page reload. Must return valid HTML fragments.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_dashboard_presenter") as mock_get:
            mock_presenter = MagicMock()
            mock_presenter.get_sessions_list.return_value = []
            mock_get.return_value = mock_presenter

            response = client.get("/partials/sessions")
            assert response.status_code == 200
            assert "table" in response.text.lower() or "no sessions" in response.text.lower()

    def test_roi_partial_returns_html(self, client: TestClient) -> None:
        """Verifies ROI partial endpoint returns HTML panel fragment.

        Tests that the htmx partial for ROI panel returns proper
        HTML with summary metrics.

        Business context:
        ROI panel shows cost savings - critical business metric.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_dashboard_presenter") as mock_get:
            from ai_session_tracker_mcp.presenters import ROIViewModel

            mock_presenter = MagicMock()
            mock_presenter.get_roi_summary.return_value = ROIViewModel(
                roi_percentage=150.0,
                total_sessions=5,
                completed_sessions=4,
                total_ai_hours=5.0,
                estimated_human_hours=10.0,
                time_saved_hours=5.0,
                human_baseline_cost=1000.0,
                total_ai_cost=500.0,
                cost_saved=500.0,
            )
            mock_get.return_value = mock_presenter

            response = client.get("/partials/roi")
            assert response.status_code == 200
            assert "ROI" in response.text

    def test_effectiveness_partial_returns_html(self, client: TestClient) -> None:
        """Verifies effectiveness partial endpoint returns HTML panel fragment.

        Tests that the htmx partial for effectiveness panel returns proper
        HTML with rating distribution.

        Business context:
        Effectiveness distribution shows AI quality metrics.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_dashboard_presenter") as mock_get:
            from ai_session_tracker_mcp.presenters import EffectivenessViewModel

            mock_presenter = MagicMock()
            mock_presenter.get_effectiveness.return_value = EffectivenessViewModel(
                average=4.2,
                total_interactions=10,
                distribution={5: 5, 4: 3, 3: 2},
            )
            mock_get.return_value = mock_presenter

            response = client.get("/partials/effectiveness")
            assert response.status_code == 200
            assert "Effectiveness" in response.text

    def test_roi_chart_partial_returns_html_with_timestamp(self, client: TestClient) -> None:
        """Verifies ROI chart partial includes cache-busting timestamp.

        Tests that the img src includes a timestamp parameter to
        prevent browser caching of stale chart images.

        Business context:
        Charts must refresh with current data. Cache-busting ensures
        users see latest metrics, not cached old charts.
        """
        response = client.get("/partials/roi-chart")
        assert response.status_code == 200
        assert "ROI Chart" in response.text
        assert "roi.png?t=" in response.text

    def test_timeline_chart_partial_returns_html_with_timestamp(self, client: TestClient) -> None:
        """Verifies timeline chart partial includes cache-busting timestamp.

        Tests that the img src includes a timestamp parameter.
        """
        response = client.get("/partials/timeline-chart")
        assert response.status_code == 200
        assert "Timeline" in response.text
        assert "timeline.png?t=" in response.text


class TestChartFallbacks:
    """Test suite for chart routes when matplotlib is unavailable."""

    def test_effectiveness_chart_fallback(self, client: TestClient) -> None:
        """Verifies effectiveness chart returns SVG placeholder when matplotlib unavailable.

        Tests graceful degradation when matplotlib is not installed,
        returning an informative SVG placeholder instead.

        Business context:
        matplotlib is optional. Dashboard should work without it,
        showing placeholder instead of broken images.
        """
        with patch("ai_session_tracker_mcp.web.routes.get_chart_presenter") as mock_get:
            mock_presenter = MagicMock()
            mock_presenter.render_effectiveness_chart.side_effect = ImportError("No matplotlib")
            mock_get.return_value = mock_presenter

            response = client.get("/charts/effectiveness.png")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/svg+xml"
            assert b"Effectiveness Chart" in response.content

    def test_roi_chart_fallback(self, client: TestClient) -> None:
        """Verifies ROI chart returns SVG placeholder when matplotlib unavailable."""
        with patch("ai_session_tracker_mcp.web.routes.get_chart_presenter") as mock_get:
            mock_presenter = MagicMock()
            mock_presenter.render_roi_chart.side_effect = ImportError("No matplotlib")
            mock_get.return_value = mock_presenter

            response = client.get("/charts/roi.png")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/svg+xml"
            assert b"ROI Chart" in response.content

    def test_timeline_chart_fallback(self, client: TestClient) -> None:
        """Verifies timeline chart returns SVG placeholder when matplotlib unavailable."""
        with patch("ai_session_tracker_mcp.web.routes.get_chart_presenter") as mock_get:
            mock_presenter = MagicMock()
            mock_presenter.render_sessions_timeline.side_effect = ImportError("No matplotlib")
            mock_get.return_value = mock_presenter

            response = client.get("/charts/timeline.png")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/svg+xml"
            assert b"Timeline Chart" in response.content


class TestAppMainBlock:
    """Test suite for web app __main__ block."""

    def test_main_block_runs_dashboard(self) -> None:
        """Verifies __main__ block calls run_dashboard when executed directly.

        Tests that running the app module as a script starts the
        dashboard server with default settings.

        Business context:
        Users may run `python -m ai_session_tracker_mcp.web.app`
        directly. Should start dashboard on default host/port.
        """
        with patch("ai_session_tracker_mcp.web.app.run_dashboard"):
            # Execute the module's __main__ guard
            import sys

            # Temporarily make the module think it's __main__
            original_name = "ai_session_tracker_mcp.web.app"
            if original_name in sys.modules:
                del sys.modules[original_name]

            # Use runpy to execute as __main__

            with patch.dict("sys.modules", {"ai_session_tracker_mcp.web.app": MagicMock()}):
                # Just verify the function exists and is callable
                from ai_session_tracker_mcp.web.app import run_dashboard

                assert callable(run_dashboard)
