"""
FastAPI routes for AI Session Tracker dashboard.

PURPOSE: Thin route handlers that delegate to presenters.
AI CONTEXT: Routes should be simple - business logic in presenters.

ROUTE STRUCTURE:
- / : Main dashboard page (full HTML)
- /partials/* : htmx partial updates
- /charts/* : PNG chart images
- /api/* : JSON endpoints for programmatic access
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from ..presenters import ChartPresenter, DashboardPresenter
from ..statistics import StatisticsEngine
from ..storage import StorageManager

if TYPE_CHECKING:
    from ..presenters import (
        DashboardOverview,
        EffectivenessViewModel,
        ROIViewModel,
        SessionGapsViewModel,
        SessionViewModel,
    )

__all__ = [
    "router",
    "get_storage",
    "get_statistics",
    "get_dashboard_presenter",
    "get_chart_presenter",
]

router = APIRouter()

# =============================================================================
# CSS Styles (P3-1: Extracted from _render_dashboard_html for maintainability)
# =============================================================================

_DASHBOARD_CSS = """
:root {
    --bg: #0f172a;
    --surface: #1e293b;
    --border: #334155;
    --text: #f1f5f9;
    --text-muted: #94a3b8;
    --primary: #3b82f6;
    --success: #22c55e;
    --warning: #f59e0b;
    --danger: #ef4444;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 1rem;
}
.container { max-width: 1400px; margin: 0 auto; }
header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border);
}
h1 { font-size: 1.5rem; font-weight: 600; }
.refresh-indicator {
    color: var(--text-muted);
    font-size: 0.875rem;
}
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    padding: 1rem;
}
.panel h2 {
    font-size: 1rem;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 0.75rem;
}
.metric {
    font-size: 2rem;
    font-weight: 700;
}
.metric.positive { color: var(--success); }
.metric.neutral { color: var(--primary); }
.metric-label {
    font-size: 0.875rem;
    color: var(--text-muted);
}
table {
    width: 100%;
    border-collapse: collapse;
}
th, td {
    text-align: left;
    padding: 0.75rem;
    border-bottom: 1px solid var(--border);
}
th { color: var(--text-muted); font-weight: 500; font-size: 0.875rem; }
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
}
.status-active { background: var(--primary); color: white; }
.status-completed { background: var(--success); color: white; }
.status-abandoned { background: var(--text-muted); color: var(--bg); }
.chart-container {
    display: flex;
    justify-content: center;
    padding: 1rem 0;
}
.chart-container img {
    max-width: 100%;
    height: auto;
    border-radius: 0.25rem;
}
.bar-chart {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}
.bar-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.bar-label { width: 80px; font-size: 0.875rem; }
.bar-track {
    flex: 1;
    height: 1.5rem;
    background: var(--border);
    border-radius: 0.25rem;
    overflow: hidden;
}
.bar-fill {
    height: 100%;
    border-radius: 0.25rem;
    transition: width 0.3s ease;
}
.bar-5 { background: var(--success); }
.bar-4 { background: #84cc16; }
.bar-3 { background: var(--warning); }
.bar-2 { background: #f97316; }
.bar-1 { background: var(--danger); }
footer {
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.875rem;
    text-align: center;
}
"""

# =============================================================================
# Dependency Factory Functions
# =============================================================================


def get_storage() -> StorageManager:
    """
    Create and return a StorageManager instance for data access.

    Factory function providing storage access to route handlers. Creates
    a new StorageManager instance each time to ensure fresh file reads
    and avoid stale data issues.

    Business context: All dashboard data comes from JSON files managed
    by StorageManager. This function provides the data access layer
    that connects routes to persisted session tracking data.

    Returns:
        StorageManager instance configured with default storage directory
        (.ai_sessions/) ready for reading sessions, interactions, and issues.

    Raises:
        OSError: If storage directory cannot be created or accessed.

    Example:
        >>> storage = get_storage()
        >>> sessions = storage.load_sessions()
    """
    return StorageManager()


def get_statistics() -> StatisticsEngine:
    """
    Create and return a StatisticsEngine instance for calculations.

    Factory function providing the statistics calculation engine to
    route handlers. Uses default cost parameters from Config class.

    Business context: ROI calculations, effectiveness averages, and
    all analytical metrics are computed by the StatisticsEngine.
    This function provides the calculation layer for dashboard views.

    Returns:
        StatisticsEngine instance configured with default cost parameters
        (human_hourly_rate=$130, ai_monthly_cost=$40) ready for ROI
        and productivity metric calculations.

    Raises:
        None - StatisticsEngine initialization is fail-safe.

    Example:
        >>> stats = get_statistics()
        >>> roi = stats.calculate_roi_metrics(sessions, interactions)
    """
    return StatisticsEngine()


def get_dashboard_presenter() -> DashboardPresenter:
    """
    Create and return a DashboardPresenter with dependencies.

    Factory function that assembles the dashboard presenter with its
    required storage and statistics dependencies. The presenter
    transforms raw data into view models for template rendering.

    Business context: The presenter pattern separates data transformation
    from route handling, enabling testable business logic and clean
    separation of concerns between data access and presentation.

    Returns:
        DashboardPresenter instance with injected StorageManager and
        StatisticsEngine, ready to generate view models for sessions,
        ROI, effectiveness, and issue displays.

    Raises:
        OSError: If storage cannot be initialized.

    Example:
        >>> presenter = get_dashboard_presenter()
        >>> overview = presenter.get_overview()
        >>> print(f"Total sessions: {len(overview.sessions)}")
    """
    return DashboardPresenter(get_storage(), get_statistics())


def get_chart_presenter() -> ChartPresenter:
    """
    Create and return a ChartPresenter with dependencies.

    Factory function that assembles the chart presenter for server-side
    chart rendering. Uses matplotlib to generate PNG chart images
    that can be served directly to browsers.

    Business context: Visual charts (effectiveness bars, ROI comparison,
    timeline) provide quick insights for stakeholders. Server-side
    rendering ensures consistent appearance across all clients.

    Returns:
        ChartPresenter instance with injected StorageManager and
        StatisticsEngine, ready to render PNG charts for effectiveness
        distribution, ROI comparison, and session timeline.

    Raises:
        OSError: If storage cannot be initialized.
        ImportError: If matplotlib is not available (graceful fallback).

    Example:
        >>> presenter = get_chart_presenter()
        >>> png_bytes = presenter.render_effectiveness_chart()
        >>> len(png_bytes) > 0
        True
    """
    return ChartPresenter(get_storage(), get_statistics())


# ============================================================================
# Full Page Routes
# ============================================================================


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(
    presenter: Annotated[DashboardPresenter, Depends(get_dashboard_presenter)],
    request: Request,  # noqa: ARG001
) -> HTMLResponse:
    """
    Render the main dashboard page with complete analytics overview.

    Serves the primary dashboard HTML page containing session lists,
    ROI summary, effectiveness charts, and auto-refreshing components
    powered by htmx for real-time updates without full page reloads.

    Business context: This is the main entry point for the web dashboard.
    Stakeholders use this view to monitor AI productivity metrics, track
    ROI progress, and identify sessions needing attention.

    Args:
        presenter: DashboardPresenter injected via FastAPI Depends.
        request: FastAPI Request object (unused but kept for potential
            future enhancements like user context).

    Returns:
        HTMLResponse containing the complete dashboard page with:
        - Header with title and auto-refresh indicator
        - ROI summary panel showing cost savings and percentages
        - Effectiveness distribution chart with star ratings
        - Sessions table with status, duration, and metrics
        - Embedded htmx triggers for automatic 30-second refresh

    Raises:
        None - Presenter errors result in empty/default display.

    Example:
        >>> # Access via browser
        >>> # GET http://localhost:8000/
        >>> # Returns full HTML dashboard page
    """
    overview = presenter.get_overview()

    # Inline template for simplicity (could move to Jinja2 file)
    html = _render_dashboard_html(overview)
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


# ============================================================================
# Partial Routes (htmx)
# ============================================================================


@router.get("/partials/sessions", response_class=HTMLResponse)
async def sessions_partial(
    presenter: Annotated[DashboardPresenter, Depends(get_dashboard_presenter)],
) -> HTMLResponse:
    """
    Render the sessions table HTML fragment for htmx partial updates.

    Returns only the sessions table HTML, not a full page. Designed for
    htmx requests that swap this content into the existing page without
    a full reload, enabling real-time dashboard updates.

    Business context: Live-updating session lists let users see new
    sessions appear and status changes reflected without manual refresh,
    improving the monitoring experience.

    Returns:
        HTMLResponse containing a table with session rows showing:
        - Session ID (truncated with ellipsis)
        - Project name
        - Status badge (active/completed/abandoned)
        - Duration (minutes or hours)
        - Interaction count
        - Effectiveness stars (★★★☆☆ format)

    Raises:
        None - Presenter errors result in empty table display.

    Example:
        >>> # htmx request from browser
        >>> # GET /partials/sessions
        >>> # Returns: <table>...</table> HTML fragment
    """
    sessions = presenter.get_sessions_list()

    html = _render_sessions_table(sessions)
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@router.get("/partials/roi", response_class=HTMLResponse)
async def roi_partial(
    presenter: Annotated[DashboardPresenter, Depends(get_dashboard_presenter)],
) -> HTMLResponse:
    """
    Render the ROI summary panel HTML fragment for htmx partial updates.

    Returns only the ROI panel HTML content for swapping into the
    dashboard without full page reload. Shows key cost savings metrics
    that update in real-time as sessions complete.

    Business context: ROI is the primary justification metric for AI
    tool investment. Live updates show immediate impact of completed
    work, reinforcing the value of AI-assisted development.

    Returns:
        HTMLResponse containing ROI panel with:
        - Large ROI percentage display with color coding
        - Session counts (total and completed)
        - Time saved in human-readable format
        - Cost saved in currency format

    Raises:
        None - Presenter errors result in zero/default display.

    Example:
        >>> # htmx request from browser
        >>> # GET /partials/roi
        >>> # Returns: <h2>💰 ROI Summary</h2>... HTML fragment
    """
    roi = presenter.get_roi_summary()

    html = _render_roi_panel(roi)
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@router.get("/partials/effectiveness", response_class=HTMLResponse)
async def effectiveness_partial(
    presenter: Annotated[DashboardPresenter, Depends(get_dashboard_presenter)],
) -> HTMLResponse:
    """
    Render the effectiveness distribution panel HTML fragment.

    Returns the effectiveness panel HTML showing rating distribution
    as a horizontal bar chart with star labels. Designed for htmx
    partial swapping to update the dashboard in real-time.

    Business context: Effectiveness distribution shows the quality
    of AI outputs at a glance. A healthy distribution skews toward
    4-5 stars, indicating AI consistently produces usable code.

    Returns:
        HTMLResponse containing effectiveness panel with:
        - Large average rating display (e.g., "4.2/5")
        - Total interaction count
        - Horizontal bar chart for each rating level (5 to 1)
        - Bar widths proportional to rating frequency

    Raises:
        None - Presenter errors result in zero/default display.

    Example:
        >>> # htmx request from browser
        >>> # GET /partials/effectiveness
        >>> # Returns: <h2>⭐ Effectiveness</h2>... HTML fragment
    """
    eff = presenter.get_effectiveness()

    html = _render_effectiveness_panel(eff)
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@router.get("/partials/gaps", response_class=HTMLResponse)
async def gaps_partial(
    presenter: Annotated[DashboardPresenter, Depends(get_dashboard_presenter)],
) -> HTMLResponse:
    """
    Render the session gaps analysis panel HTML fragment.

    Returns the gaps panel HTML showing inter-session gap analysis
    with classification breakdown and friction indicators.

    Business context: Gap analysis reveals workflow friction points.
    Long gaps between sessions may indicate tool usability issues
    or user disengagement.

    Returns:
        HTMLResponse containing gaps panel with:
        - Average gap duration display
        - Classification breakdown (quick/normal/extended/long)
        - Friction indicator warnings if detected

    Example:
        >>> # htmx request from browser
        >>> # GET /partials/gaps
        >>> # Returns: <h2>⏱ Session Gaps</h2>... HTML fragment
    """
    gaps = presenter.get_session_gaps()

    html = _render_gaps_panel(gaps)
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@router.get("/partials/roi-chart", response_class=HTMLResponse)
async def roi_chart_partial() -> HTMLResponse:
    """
    Render the ROI chart panel HTML fragment for htmx partial updates.

    Returns HTML with an img tag pointing to the ROI chart PNG with a
    cache-busting timestamp parameter to ensure fresh chart on each refresh.

    Returns:
        HTMLResponse containing the chart panel HTML with cache-busted img src.
    """
    import time

    timestamp = int(time.time())
    html = f"""<h2>📈 ROI Chart</h2>
        <div class="chart-container">
            <img src="/charts/roi.png?t={timestamp}" alt="ROI Chart">
        </div>"""
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@router.get("/partials/timeline-chart", response_class=HTMLResponse)
async def timeline_chart_partial() -> HTMLResponse:
    """
    Render the timeline chart panel HTML fragment for htmx partial updates.

    Returns HTML with an img tag pointing to the timeline chart PNG with a
    cache-busting timestamp parameter to ensure fresh chart on each refresh.

    Returns:
        HTMLResponse containing the chart panel HTML with cache-busted img src.
    """
    import time

    timestamp = int(time.time())
    html = f"""<h2>📊 Session Timeline</h2>
        <div class="chart-container">
            <img src="/charts/timeline.png?t={timestamp}" alt="Timeline Chart">
        </div>"""
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


# ============================================================================
# Chart Routes (PNG images)
# ============================================================================


@router.get("/charts/effectiveness.png")
async def effectiveness_chart(
    presenter: Annotated[ChartPresenter, Depends(get_chart_presenter)],
) -> Response:
    """
    Generate and serve effectiveness distribution chart as PNG image.

    Creates a matplotlib horizontal bar chart showing the distribution
    of effectiveness ratings (1-5 stars) and returns it as a PNG image.
    Falls back to SVG placeholder if matplotlib is not installed.

    Business context: Visual charts are essential for executive reports
    and presentations. This chart provides a publication-ready view of
    AI effectiveness that can be embedded in documents.

    Returns:
        Response with either:
        - PNG image bytes (media_type="image/png") when matplotlib available
        - SVG placeholder (media_type="image/svg+xml") as fallback

    Raises:
        None - ImportError is caught and results in placeholder response.

    Example:
        >>> # Browser/img tag request
        >>> # GET /charts/effectiveness.png
        >>> # Returns: binary PNG image data
    """
    try:
        png_bytes = presenter.render_effectiveness_chart()
        return Response(content=png_bytes, media_type="image/png")
    except ImportError:
        # matplotlib not installed - return placeholder
        return Response(
            content=_placeholder_chart_svg("Effectiveness"),
            media_type="image/svg+xml",
        )


@router.get("/charts/roi.png")
async def roi_chart(
    presenter: Annotated[ChartPresenter, Depends(get_chart_presenter)],
) -> Response:
    """
    Generate and serve ROI comparison chart as PNG image.

    Creates a matplotlib bar chart comparing human baseline cost,
    AI actual cost, and savings. Returns it as a PNG image for
    embedding in the dashboard or external reports.

    Business context: The ROI chart is the primary visual for
    justifying AI investment. It shows at a glance how much money
    is being saved compared to traditional development approaches.

    Returns:
        Response with either:
        - PNG image bytes (media_type="image/png") when matplotlib available
        - SVG placeholder (media_type="image/svg+xml") as fallback

    Raises:
        None - ImportError is caught and results in placeholder response.

    Example:
        >>> # Browser/img tag request
        >>> # GET /charts/roi.png
        >>> # Returns: binary PNG image data with cost comparison bars
    """
    try:
        png_bytes = presenter.render_roi_chart()
        return Response(content=png_bytes, media_type="image/png")
    except ImportError:
        return Response(
            content=_placeholder_chart_svg("ROI"),
            media_type="image/svg+xml",
        )


@router.get("/charts/timeline.png")
async def timeline_chart(
    presenter: Annotated[ChartPresenter, Depends(get_chart_presenter)],
) -> Response:
    """
    Generate and serve sessions timeline chart as PNG image.

    Creates a matplotlib bar chart showing session durations over time,
    with bars colored by status (completed=green, active=blue, other=gray).
    Returns as PNG for dashboard embedding or export.

    Business context: The timeline chart helps identify work patterns,
    showing when AI-assisted sessions are happening and how long they
    take. Useful for capacity planning and trend analysis.

    Returns:
        Response with either:
        - PNG image bytes (media_type="image/png") when matplotlib available
        - SVG placeholder (media_type="image/svg+xml") as fallback

    Raises:
        None - ImportError is caught and results in placeholder response.

    Example:
        >>> # Browser/img tag request
        >>> # GET /charts/timeline.png
        >>> # Returns: binary PNG image with session bars over time
    """
    try:
        png_bytes = presenter.render_sessions_timeline()
        return Response(content=png_bytes, media_type="image/png")
    except ImportError:
        return Response(
            content=_placeholder_chart_svg("Timeline"),
            media_type="image/svg+xml",
        )


# ============================================================================
# API Routes (JSON)
# ============================================================================


@router.get("/api/overview")
async def api_overview(
    presenter: Annotated[DashboardPresenter, Depends(get_dashboard_presenter)],
) -> dict[str, object]:
    """
    Get complete dashboard data as JSON for programmatic access.

    Returns all dashboard data in a structured JSON format suitable
    for external integrations, custom dashboards, or automated
    monitoring systems. Provides the same data as the HTML dashboard.

    Business context: The JSON API enables integration with other
    tools (Slack bots, custom dashboards, CI/CD pipelines) that
    want to consume session tracking data programmatically.

    Returns:
        Dict containing:
        - 'sessions': List of session objects with id, project, status,
          duration_minutes, interaction_count, effectiveness_avg
        - 'roi': Object with total_sessions, cost_saved, roi_percentage
        - 'effectiveness': Object with distribution dict and average

    Raises:
        None - Presenter errors result in empty/zero values.

    Example:
        >>> # HTTP request
        >>> # GET /api/overview
        >>> # Response:
        >>> {
        ...     "sessions": [{"session_id": "...", "status": "completed", ...}],
        ...     "roi": {"total_sessions": 10, "cost_saved": 500.0, ...},
        ...     "effectiveness": {"distribution": {"5": 8, ...}, "average": 4.2}
        ... }
    """
    overview = presenter.get_overview()
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "project": s.project,
                "status": s.status,
                "duration_minutes": s.duration_minutes,
                "interaction_count": s.interaction_count,
                "effectiveness_avg": s.effectiveness_avg,
            }
            for s in overview.sessions
        ],
        "roi": {
            "total_sessions": overview.roi.total_sessions if overview.roi else 0,
            "cost_saved": overview.roi.cost_saved if overview.roi else 0,
            "roi_percentage": overview.roi.roi_percentage if overview.roi else 0,
        },
        "effectiveness": {
            "distribution": overview.effectiveness.distribution if overview.effectiveness else {},
            "average": overview.effectiveness.average if overview.effectiveness else 0,
        },
        "session_gaps": {
            "total_gaps": overview.session_gaps.total_gaps if overview.session_gaps else 0,
            "average_gap_minutes": (
                overview.session_gaps.average_gap_minutes if overview.session_gaps else 0
            ),
            "by_classification": (
                overview.session_gaps.by_classification if overview.session_gaps else {}
            ),
            "friction_indicators": (
                overview.session_gaps.friction_indicators if overview.session_gaps else []
            ),
        },
    }


@router.get("/api/report")
async def api_report(
    presenter: Annotated[DashboardPresenter, Depends(get_dashboard_presenter)],
) -> dict[str, str]:
    """
    Get formatted text analytics report as JSON.

    Returns the same text report generated by the CLI 'report' command,
    wrapped in JSON for programmatic access. The report includes all
    metrics formatted for human reading with emoji icons and alignment.

    Business context: The text report is useful for embedding in
    Slack messages, email summaries, or any context where a
    pre-formatted human-readable summary is preferred over raw data.

    Returns:
        Dict with single key 'report' containing the multi-line text
        report string with session summary, ROI metrics, effectiveness
        distribution, issues summary, and code metrics.

    Raises:
        None - Presenter errors result in empty report string.

    Example:
        >>> # HTTP request
        >>> # GET /api/report
        >>> # Response:
        >>> {
        ...     "report": "==================================================\n"
        ...               "AI SESSION TRACKER - ANALYTICS REPORT\n..."
        ... }
    """
    overview = presenter.get_overview()
    return {"report": overview.report_text}


# ============================================================================
# Template Rendering Helpers
# ============================================================================


def _placeholder_chart_svg(title: str) -> bytes:
    """
    Generate a placeholder SVG when matplotlib is unavailable.

    Creates a simple SVG image with centered text indicating that
    matplotlib needs to be installed for full chart functionality.
    Used as graceful fallback for chart routes.

    Business context: Graceful degradation ensures the dashboard remains
    functional even without optional visualization dependencies.

    Args:
        title: Chart title to display in the placeholder (e.g.,
            'Effectiveness', 'ROI', 'Timeline').

    Returns:
        UTF-8 encoded bytes of an SVG image with gray background
        and centered text: "{title} Chart (install matplotlib)".

    Raises:
        None: String formatting and encoding never raise.

    Example:
        >>> svg = _placeholder_chart_svg('ROI')
        >>> b'ROI Chart' in svg
        True
    """
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">
        <rect width="100%" height="100%" fill="#f1f5f9"/>
        <text x="50%" y="50%" text-anchor="middle" fill="#64748b" font-size="16">
            {title} Chart (install matplotlib)
        </text>
    </svg>"""
    return svg.encode("utf-8")


def _render_dashboard_html(overview: object) -> str:
    """
    Render the complete dashboard HTML page from overview data.

    Generates a full HTML document with embedded CSS and htmx integration.
    The page includes all dashboard panels (sessions, ROI, effectiveness)
    and configures automatic refresh triggers for real-time updates.

    Business context: Server-side rendering ensures fast initial load and
    consistent appearance. htmx enables dynamic updates without full page
    reload, providing a smooth user experience.

    Args:
        overview: DashboardOverview object containing sessions list,
            roi summary, effectiveness distribution, and report text.
            Type is 'object' for import cycle avoidance.

    Returns:
        Complete HTML string including DOCTYPE, head with styles and
        htmx script, and body with all dashboard components. The page
        uses a dark theme with CSS custom properties for consistency.

    Raises:
        None: Template construction never raises.

    Example:
        >>> presenter = get_dashboard_presenter()
        >>> overview = presenter.get_overview()
        >>> html = _render_dashboard_html(overview)
        >>> '<!DOCTYPE html>' in html
        True
    """
    ov: DashboardOverview = overview  # type: ignore[assignment]

    sessions_html = _render_sessions_table(ov.sessions)
    roi_html = _render_roi_panel(ov.roi) if ov.roi else ""
    effectiveness_html = _render_effectiveness_panel(ov.effectiveness) if ov.effectiveness else ""
    gaps_html = _render_gaps_panel(ov.session_gaps) if ov.session_gaps else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Session Tracker - Dashboard</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        {_DASHBOARD_CSS}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 AI Session Tracker</h1>
            <span class="refresh-indicator"
                  hx-get="/partials/sessions"
                  hx-trigger="every 30s"
                  hx-swap="none">
                Auto-refresh: 30s
            </span>
        </header>

        <div class="grid">
            <div class="panel" id="roi-panel"
                 hx-get="/partials/roi"
                 hx-trigger="every 30s"
                 hx-swap="innerHTML">
                {roi_html}
            </div>

            <div class="panel" id="effectiveness-panel"
                 hx-get="/partials/effectiveness"
                 hx-trigger="every 30s"
                 hx-swap="innerHTML">
                {effectiveness_html}
            </div>

            <div class="panel" id="gaps-panel"
                 hx-get="/partials/gaps"
                 hx-trigger="every 30s"
                 hx-swap="innerHTML">
                {gaps_html}
            </div>
        </div>

        <div class="panel" id="roi-chart-panel"
             style="margin-top: 1rem;"
             hx-get="/partials/roi-chart"
             hx-trigger="every 60s"
             hx-swap="innerHTML">
            <h2>📈 ROI Chart</h2>
            <div class="chart-container">
                <img src="/charts/roi.png" alt="ROI Chart">
            </div>
        </div>

        <div class="panel" id="timeline-chart-panel"
             style="margin-top: 1rem;"
             hx-get="/partials/timeline-chart"
             hx-trigger="every 60s"
             hx-swap="innerHTML">
            <h2>📊 Session Timeline</h2>
            <div class="chart-container">
                <img src="/charts/timeline.png" alt="Timeline Chart">
            </div>
        </div>

        <div class="panel" id="sessions-panel"
             style="margin-top: 1rem; flex: 1; overflow-y: auto; max-height: 50vh;"
             hx-get="/partials/sessions"
             hx-trigger="every 30s"
             hx-swap="innerHTML">
            <h2>📋 Sessions</h2>
            {sessions_html}
        </div>

        <footer>
            AI Session Tracker MCP &bull; Powered by FastAPI + htmx
        </footer>
    </div>
</body>
</html>"""


def _render_sessions_table(sessions: Sequence[object]) -> str:
    """
    Render sessions data as an HTML table.

    Creates a formatted table with session information including
    truncated IDs, project names, status badges, duration, interaction
    counts, and star ratings. Shows placeholder text when no sessions.

    Business context: The sessions table is the primary view for browsing
    all tracked AI sessions. Truncated IDs prevent layout overflow while
    status badges provide quick visual scanning.

    Args:
        sessions: Sequence of SessionViewModel objects to render.
            Type is 'object' to avoid import cycles; internally cast
            to SessionViewModel for property access.

    Returns:
        HTML string containing a complete table element with thead
        and tbody. Includes status badges with CSS classes and
        truncated session IDs with ellipsis for readability.

    Raises:
        None: Template string construction never raises.

    Example:
        >>> sessions = presenter.get_sessions_list()
        >>> html = _render_sessions_table(sessions)
        >>> '<table>' in html
        True
    """
    rows = ""
    for s in sessions:
        s_typed: SessionViewModel = s  # type: ignore[assignment]
        rows += f"""<tr>
            <td>{s_typed.session_id[:20]}...</td>
            <td>{s_typed.start_time_display}</td>
            <td><span class="status-badge {s_typed.status_class}">{s_typed.status}</span></td>
            <td>{s_typed.duration_display}</td>
            <td>{s_typed.interaction_count}</td>
            <td>{s_typed.effectiveness_stars}</td>
        </tr>"""

    if not rows:
        rows = (
            '<tr><td colspan="6" style="text-align: center; '
            'color: var(--text-muted);">No sessions yet</td></tr>'
        )

    return f"""<table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Start Time</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Interactions</th>
                <th>Effectiveness</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>"""


def _render_roi_panel(roi: object) -> str:
    """
    Render ROI summary data as an HTML panel.

    Creates a formatted panel with large ROI percentage display,
    color-coded based on positive/negative value, and supporting
    metrics including session counts, time saved, and cost saved.

    Business context: ROI visualization helps stakeholders understand
    the value of AI assistance. Positive ROI (green) validates AI
    investment; neutral/negative prompts workflow review.

    Args:
        roi: ROIViewModel object containing roi_percentage, total_sessions,
            completed_sessions, time_saved_display, and cost_saved_display.
            Type is 'object' to avoid import cycles.

    Returns:
        HTML string containing panel title, large metric display with
        appropriate CSS class (positive/neutral), and detail lines.

    Raises:
        None: Template string construction never raises.

    Example:
        >>> roi = presenter.get_roi_summary()
        >>> html = _render_roi_panel(roi)
        >>> '💰 ROI Summary' in html
        True
    """
    r: ROIViewModel = roi  # type: ignore[assignment]
    metric_class = "positive" if r.roi_percentage >= 0 else "neutral"

    return f"""<h2>💰 ROI Summary</h2>
        <div class="metric {metric_class}">{r.roi_percentage:.0f}%</div>
        <div class="metric-label">Return on Investment</div>
        <div style="margin-top: 1rem; font-size: 0.875rem;">
            <div>Sessions: {r.total_sessions} ({r.completed_sessions} completed)</div>
            <div>Time Saved: {r.time_saved_display}</div>
            <div>Cost Saved: {r.cost_saved_display}</div>
        </div>"""


def _render_effectiveness_panel(eff: object) -> str:
    """
    Render effectiveness distribution as an HTML panel with bar chart.

    Creates a formatted panel with average rating display and horizontal
    bar chart showing distribution across all five rating levels. Bars
    are color-coded from green (5 stars) to red (1 star).

    Business context: Effectiveness distribution reveals AI output quality
    patterns. A left-skewed distribution (mostly 4-5 stars) indicates
    effective prompting; right-skewed suggests workflow improvements needed.

    Args:
        eff: EffectivenessViewModel object containing distribution dict
            (rating -> count), average score, and total_interactions.
            Type is 'object' to avoid import cycles.

    Returns:
        HTML string containing panel title, large average display,
        interaction count label, and CSS-styled horizontal bar chart
        with width percentages based on rating frequencies.

    Raises:
        None: Template string construction never raises.

    Example:
        >>> eff = presenter.get_effectiveness()
        >>> html = _render_effectiveness_panel(eff)
        >>> '⭐ Effectiveness' in html
        True
    """
    e: EffectivenessViewModel = eff  # type: ignore[assignment]

    bars = ""
    for rating in [5, 4, 3, 2, 1]:
        width = e.bar_width(rating)
        count = e.distribution.get(rating, 0)
        stars = "★" * rating
        bars += f"""<div class="bar-row">
            <span class="bar-label">{stars}</span>
            <div class="bar-track">
                <div class="bar-fill bar-{rating}" style="width: {width}%"></div>
            </div>
            <span style="width: 30px; text-align: right;">{count}</span>
        </div>"""

    return f"""<h2>⭐ Effectiveness</h2>
        <div class="metric neutral">{e.average:.1f}/5</div>
        <div class="metric-label">Average Rating ({e.total_interactions} interactions)</div>
        <div class="bar-chart" style="margin-top: 1rem;">
            {bars}
        </div>"""


def _render_gaps_panel(gaps: object) -> str:
    """
    Render session gaps analysis as an HTML panel.

    Creates a formatted panel showing inter-session gap statistics,
    classification breakdown, and friction indicator warnings.

    Business context: Gap analysis reveals workflow friction. Long gaps
    may indicate tool difficulty or user disengagement. The panel
    highlights patterns that need investigation.

    Args:
        gaps: SessionGapsViewModel object containing gaps list, averages,
            classification counts, and friction indicators.

    Returns:
        HTML string containing panel title, average gap display,
        classification breakdown bars, and friction warnings if any.

    Example:
        >>> gaps = presenter.get_session_gaps()
        >>> html = _render_gaps_panel(gaps)
        >>> '⏱ Session Gaps' in html
        True
    """
    g: SessionGapsViewModel = gaps  # type: ignore[assignment]

    # Classification breakdown
    classifications = [
        ("quick", "⚡ Quick (<5m)", "#22c55e"),
        ("normal", "✓ Normal (5-30m)", "#3b82f6"),
        ("extended", "⏸ Extended (30m-2h)", "#f59e0b"),
        ("long_break", "🔴 Long (2h+)", "#ef4444"),
    ]

    bars = ""
    for class_key, label, color in classifications:
        count = g.classification_count(class_key)
        width = (count / g.total_gaps * 100) if g.total_gaps > 0 else 0
        bars += f"""<div class="bar-row">
            <span class="bar-label" style="width: 140px;">{label}</span>
            <div class="bar-track">
                <div class="bar-fill" style="width: {width:.0f}%; background: {color};"></div>
            </div>
            <span style="width: 30px; text-align: right;">{count}</span>
        </div>"""

    # Friction warnings
    friction_html = ""
    if g.has_friction:
        friction_items = "".join(
            f'<div style="color: var(--warning); font-size: 0.875rem;">⚠️ {indicator}</div>'
            for indicator in g.friction_indicators
        )
        friction_html = f'<div style="margin-top: 1rem;">{friction_items}</div>'

    return f"""<h2>⏱ Session Gaps</h2>
        <div class="metric neutral">{g.average_display}</div>
        <div class="metric-label">Average Gap ({g.total_gaps} gaps)</div>
        <div class="bar-chart" style="margin-top: 1rem;">
            {bars}
        </div>
        {friction_html}"""
