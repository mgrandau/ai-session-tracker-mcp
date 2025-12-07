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

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from ..presenters import ChartPresenter, DashboardPresenter
from ..statistics import StatisticsEngine
from ..storage import StorageManager

router = APIRouter()


def get_storage() -> StorageManager:
    """Get storage manager instance."""
    return StorageManager()


def get_statistics() -> StatisticsEngine:
    """Get statistics engine instance."""
    return StatisticsEngine()


def get_dashboard_presenter() -> DashboardPresenter:
    """Get dashboard presenter with dependencies."""
    return DashboardPresenter(get_storage(), get_statistics())


def get_chart_presenter() -> ChartPresenter:
    """Get chart presenter with dependencies."""
    return ChartPresenter(get_storage(), get_statistics())


# ============================================================================
# Full Page Routes
# ============================================================================


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> HTMLResponse:  # noqa: ARG001
    """
    Main dashboard page.

    Returns full HTML page with htmx-enabled components.
    """
    presenter = get_dashboard_presenter()
    overview = presenter.get_overview()

    # Inline template for simplicity (could move to Jinja2 file)
    html = _render_dashboard_html(overview)
    return HTMLResponse(content=html)


# ============================================================================
# Partial Routes (htmx)
# ============================================================================


@router.get("/partials/sessions", response_class=HTMLResponse)
async def sessions_partial() -> HTMLResponse:
    """Sessions list partial for htmx refresh."""
    presenter = get_dashboard_presenter()
    sessions = presenter.get_sessions_list()

    html = _render_sessions_table(sessions)
    return HTMLResponse(content=html)


@router.get("/partials/roi", response_class=HTMLResponse)
async def roi_partial() -> HTMLResponse:
    """ROI summary partial for htmx refresh."""
    presenter = get_dashboard_presenter()
    roi = presenter.get_roi_summary()

    html = _render_roi_panel(roi)
    return HTMLResponse(content=html)


@router.get("/partials/effectiveness", response_class=HTMLResponse)
async def effectiveness_partial() -> HTMLResponse:
    """Effectiveness distribution partial."""
    presenter = get_dashboard_presenter()
    eff = presenter.get_effectiveness()

    html = _render_effectiveness_panel(eff)
    return HTMLResponse(content=html)


# ============================================================================
# Chart Routes (PNG images)
# ============================================================================


@router.get("/charts/effectiveness.png")
async def effectiveness_chart() -> Response:
    """Effectiveness distribution chart as PNG."""
    presenter = get_chart_presenter()
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
async def roi_chart() -> Response:
    """ROI comparison chart as PNG."""
    presenter = get_chart_presenter()
    try:
        png_bytes = presenter.render_roi_chart()
        return Response(content=png_bytes, media_type="image/png")
    except ImportError:
        return Response(
            content=_placeholder_chart_svg("ROI"),
            media_type="image/svg+xml",
        )


@router.get("/charts/timeline.png")
async def timeline_chart() -> Response:
    """Sessions timeline chart as PNG."""
    presenter = get_chart_presenter()
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
async def api_overview() -> dict[str, object]:
    """Get complete dashboard data as JSON."""
    presenter = get_dashboard_presenter()
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
    }


@router.get("/api/report")
async def api_report() -> dict[str, str]:
    """Get text report as JSON."""
    presenter = get_dashboard_presenter()
    overview = presenter.get_overview()
    return {"report": overview.report_text}


# ============================================================================
# Template Rendering Helpers
# ============================================================================


def _placeholder_chart_svg(title: str) -> bytes:
    """Generate placeholder SVG when matplotlib unavailable."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">
        <rect width="100%" height="100%" fill="#f1f5f9"/>
        <text x="50%" y="50%" text-anchor="middle" fill="#64748b" font-size="16">
            {title} Chart (install matplotlib)
        </text>
    </svg>"""
    return svg.encode("utf-8")


def _render_dashboard_html(overview: object) -> str:
    """Render full dashboard HTML."""
    from ..presenters import DashboardOverview

    ov: DashboardOverview = overview  # type: ignore[assignment]

    sessions_html = _render_sessions_table(ov.sessions)
    roi_html = _render_roi_panel(ov.roi) if ov.roi else ""
    effectiveness_html = _render_effectiveness_panel(ov.effectiveness) if ov.effectiveness else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Session Tracker - Dashboard</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --border: #334155;
            --text: #f1f5f9;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 1rem;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        h1 {{ font-size: 1.5rem; font-weight: 600; }}
        .refresh-indicator {{
            color: var(--text-muted);
            font-size: 0.875rem;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        .panel {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 0.5rem;
            padding: 1rem;
        }}
        .panel h2 {{
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
        }}
        .metric {{
            font-size: 2rem;
            font-weight: 700;
        }}
        .metric.positive {{ color: var(--success); }}
        .metric.neutral {{ color: var(--primary); }}
        .metric-label {{
            font-size: 0.875rem;
            color: var(--text-muted);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            text-align: left;
            padding: 0.75rem;
            border-bottom: 1px solid var(--border);
        }}
        th {{ color: var(--text-muted); font-weight: 500; font-size: 0.875rem; }}
        .status-badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        .status-active {{ background: var(--primary); color: white; }}
        .status-completed {{ background: var(--success); color: white; }}
        .status-abandoned {{ background: var(--text-muted); color: var(--bg); }}
        .chart-container {{
            display: flex;
            justify-content: center;
            padding: 1rem 0;
        }}
        .chart-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 0.25rem;
        }}
        .bar-chart {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}
        .bar-row {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .bar-label {{ width: 80px; font-size: 0.875rem; }}
        .bar-track {{
            flex: 1;
            height: 1.5rem;
            background: var(--border);
            border-radius: 0.25rem;
            overflow: hidden;
        }}
        .bar-fill {{
            height: 100%;
            border-radius: 0.25rem;
            transition: width 0.3s ease;
        }}
        .bar-5 {{ background: var(--success); }}
        .bar-4 {{ background: #84cc16; }}
        .bar-3 {{ background: var(--warning); }}
        .bar-2 {{ background: #f97316; }}
        .bar-1 {{ background: var(--danger); }}
        footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.875rem;
            text-align: center;
        }}
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

            <div class="panel">
                <h2>📈 ROI Chart</h2>
                <div class="chart-container">
                    <img src="/charts/roi.png"
                         alt="ROI Chart"
                         hx-get="/charts/roi.png"
                         hx-trigger="every 60s"
                         hx-swap="outerHTML">
                </div>
            </div>
        </div>

        <div class="panel" id="sessions-panel"
             hx-get="/partials/sessions"
             hx-trigger="every 30s"
             hx-swap="innerHTML">
            <h2>📋 Sessions</h2>
            {sessions_html}
        </div>

        <div class="panel" style="margin-top: 1rem;">
            <h2>📊 Session Timeline</h2>
            <div class="chart-container">
                <img src="/charts/timeline.png"
                     alt="Timeline Chart"
                     hx-get="/charts/timeline.png"
                     hx-trigger="every 60s"
                     hx-swap="outerHTML">
            </div>
        </div>

        <footer>
            AI Session Tracker MCP &bull; Powered by FastAPI + htmx
        </footer>
    </div>
</body>
</html>"""


def _render_sessions_table(sessions: Sequence[object]) -> str:
    """Render sessions table HTML."""
    from ..presenters import SessionViewModel

    rows = ""
    for s in sessions:
        s_typed: SessionViewModel = s  # type: ignore[assignment]
        rows += f"""<tr>
            <td>{s_typed.session_id[:8]}...</td>
            <td>{s_typed.project}</td>
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
                <th>Project</th>
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
    """Render ROI summary panel HTML."""
    from ..presenters import ROIViewModel

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
    """Render effectiveness distribution panel HTML."""
    from ..presenters import EffectivenessViewModel

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
