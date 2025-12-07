"""
Presenters for AI Session Tracker dashboards.

PURPOSE: Testable business logic layer between data and UI.
AI CONTEXT: Pure data transformation - no I/O, no rendering.

DESIGN PRINCIPLES:
1. Presenters receive data, return view models (dicts/dataclasses)
2. No dependencies on specific UI framework
3. Fully unit-testable without mocking
4. Each presenter focuses on one dashboard view

USAGE:
    presenter = DashboardPresenter(storage, statistics)
    overview = presenter.get_overview()
    # overview is a dict ready for template rendering
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .statistics import StatisticsEngine
    from .storage import StorageManager


@dataclass
class SessionViewModel:
    """View model for a single session in the list."""

    session_id: str
    project: str
    status: str
    duration_minutes: float
    interaction_count: int
    effectiveness_avg: float
    start_time: str
    end_time: str | None

    @property
    def duration_display(self) -> str:
        """Human-readable duration."""
        if self.duration_minutes < 60:
            return f"{self.duration_minutes:.0f}m"
        hours = self.duration_minutes / 60
        return f"{hours:.1f}h"

    @property
    def effectiveness_stars(self) -> str:
        """Star representation of effectiveness."""
        if self.effectiveness_avg <= 0:
            return "—"
        full = int(self.effectiveness_avg)
        return "★" * full + "☆" * (5 - full)

    @property
    def status_class(self) -> str:
        """CSS class for status badge."""
        return {
            "active": "status-active",
            "completed": "status-completed",
            "abandoned": "status-abandoned",
        }.get(self.status, "status-unknown")


@dataclass
class ROIViewModel:
    """View model for ROI summary panel."""

    total_sessions: int
    completed_sessions: int
    total_ai_hours: float
    estimated_human_hours: float
    time_saved_hours: float
    human_baseline_cost: float
    total_ai_cost: float
    cost_saved: float
    roi_percentage: float

    @property
    def time_saved_display(self) -> str:
        """Human-readable time saved."""
        if self.time_saved_hours < 1:
            return f"{self.time_saved_hours * 60:.0f} minutes"
        return f"{self.time_saved_hours:.1f} hours"

    @property
    def cost_saved_display(self) -> str:
        """Formatted cost saved."""
        return f"${self.cost_saved:,.2f}"

    @property
    def roi_class(self) -> str:
        """CSS class based on ROI value."""
        if self.roi_percentage >= 50:
            return "roi-excellent"
        if self.roi_percentage >= 25:
            return "roi-good"
        if self.roi_percentage >= 0:
            return "roi-neutral"
        return "roi-negative"


@dataclass
class EffectivenessViewModel:
    """View model for effectiveness distribution."""

    distribution: dict[int, int] = field(default_factory=dict)
    average: float = 0.0
    total_interactions: int = 0

    def bar_width(self, rating: int) -> int:
        """Calculate bar width percentage for chart."""
        if self.total_interactions == 0:
            return 0
        count = self.distribution.get(rating, 0)
        return int((count / self.total_interactions) * 100)


@dataclass
class IssueViewModel:
    """View model for issues summary."""

    total: int
    by_type: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)

    def severity_count(self, level: str) -> int:
        """Get count for severity level."""
        return self.by_severity.get(level, 0)

    @property
    def critical_count(self) -> int:
        """Count of critical issues."""
        return self.severity_count("critical")

    @property
    def high_count(self) -> int:
        """Count of high severity issues."""
        return self.severity_count("high")


@dataclass
class DashboardOverview:
    """Complete view model for dashboard overview page."""

    sessions: list[SessionViewModel] = field(default_factory=list)
    roi: ROIViewModel | None = None
    effectiveness: EffectivenessViewModel | None = None
    issues: IssueViewModel | None = None
    report_text: str = ""


class DashboardPresenter:
    """
    Presenter for the main dashboard view.

    Transforms storage data into view models ready for rendering.
    All methods are pure - no side effects.
    """

    def __init__(
        self,
        storage: StorageManager,
        statistics: StatisticsEngine,
    ) -> None:
        """
        Initialize presenter with data sources.

        Args:
            storage: Storage manager for data access
            statistics: Statistics engine for calculations
        """
        self.storage = storage
        self.statistics = statistics

    def get_overview(self) -> DashboardOverview:
        """
        Get complete overview data for dashboard.

        Returns:
            DashboardOverview with all panels populated.
        """
        sessions_data = self.storage.load_sessions()
        interactions_data = self.storage.load_interactions()
        issues_data = self.storage.load_issues()

        return DashboardOverview(
            sessions=self._build_session_list(sessions_data, interactions_data),
            roi=self._build_roi(sessions_data, interactions_data),
            effectiveness=self._build_effectiveness(interactions_data),
            issues=self._build_issues(issues_data),
            report_text=self.statistics.generate_summary_report(
                sessions_data, interactions_data, issues_data
            ),
        )

    def get_sessions_list(self) -> list[SessionViewModel]:
        """Get just the sessions list."""
        sessions_data = self.storage.load_sessions()
        interactions_data = self.storage.load_interactions()
        return self._build_session_list(sessions_data, interactions_data)

    def get_roi_summary(self) -> ROIViewModel:
        """Get just the ROI summary."""
        sessions_data = self.storage.load_sessions()
        interactions_data = self.storage.load_interactions()
        return self._build_roi(sessions_data, interactions_data)

    def get_effectiveness(self) -> EffectivenessViewModel:
        """Get effectiveness distribution."""
        interactions_data = self.storage.load_interactions()
        return self._build_effectiveness(interactions_data)

    def _build_session_list(
        self,
        sessions: dict[str, Any],
        interactions: list[dict[str, Any]],
    ) -> list[SessionViewModel]:
        """Transform session data into view models."""
        # Group interactions by session
        interactions_by_session: dict[str, list[dict[str, Any]]] = {}
        for interaction in interactions:
            sid = interaction.get("session_id", "")
            if sid not in interactions_by_session:
                interactions_by_session[sid] = []
            interactions_by_session[sid].append(interaction)

        result: list[SessionViewModel] = []
        for session_id, session in sessions.items():
            session_interactions = interactions_by_session.get(session_id, [])

            # Calculate average effectiveness for this session
            if session_interactions:
                avg_eff = sum(i.get("effectiveness_rating", 0) for i in session_interactions) / len(
                    session_interactions
                )
            else:
                avg_eff = 0.0

            result.append(
                SessionViewModel(
                    session_id=session_id,
                    project=session.get("project", "Unknown"),
                    status=session.get("status", "unknown"),
                    duration_minutes=self.statistics.calculate_session_duration_minutes(session),
                    interaction_count=len(session_interactions),
                    effectiveness_avg=avg_eff,
                    start_time=session.get("start_time", ""),
                    end_time=session.get("end_time"),
                )
            )

        # Sort by start time descending (newest first)
        result.sort(key=lambda s: s.start_time, reverse=True)
        return result

    def _build_roi(
        self,
        sessions: dict[str, Any],
        interactions: list[dict[str, Any]],
    ) -> ROIViewModel:
        """Transform ROI metrics into view model."""
        roi = self.statistics.calculate_roi_metrics(sessions, interactions)
        return ROIViewModel(
            total_sessions=len(sessions),
            completed_sessions=roi["time_metrics"]["completed_sessions"],
            total_ai_hours=roi["time_metrics"]["total_ai_hours"],
            estimated_human_hours=roi["time_metrics"]["estimated_human_hours"],
            time_saved_hours=roi["time_metrics"]["time_saved_hours"],
            human_baseline_cost=roi["cost_metrics"]["human_baseline_cost"],
            total_ai_cost=roi["cost_metrics"]["total_ai_cost"],
            cost_saved=roi["cost_metrics"]["cost_saved"],
            roi_percentage=roi["cost_metrics"]["roi_percentage"],
        )

    def _build_effectiveness(
        self,
        interactions: list[dict[str, Any]],
    ) -> EffectivenessViewModel:
        """Transform effectiveness data into view model."""
        dist = self.statistics.calculate_effectiveness_distribution(interactions)
        avg = self.statistics.calculate_average_effectiveness(interactions)
        return EffectivenessViewModel(
            distribution=dist,
            average=avg,
            total_interactions=len(interactions),
        )

    def _build_issues(
        self,
        issues: list[dict[str, Any]],
    ) -> IssueViewModel:
        """Transform issues data into view model."""
        summary = self.statistics.calculate_issue_summary(issues)
        return IssueViewModel(
            total=summary["total"],
            by_type=summary["by_type"],
            by_severity=summary["by_severity"],
        )


class ChartPresenter:
    """
    Presenter for generating chart data and images.

    Uses matplotlib for server-side chart rendering.
    Returns PNG images as bytes for htmx refresh.
    """

    def __init__(
        self,
        storage: StorageManager,
        statistics: StatisticsEngine,
    ) -> None:
        """Initialize with data sources."""
        self.storage = storage
        self.statistics = statistics

    def render_effectiveness_chart(self) -> bytes:
        """
        Render effectiveness distribution as horizontal bar chart.

        Returns:
            PNG image bytes.
        """
        # Lazy import matplotlib to keep it optional
        import matplotlib

        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt

        interactions = self.storage.load_interactions()
        dist = self.statistics.calculate_effectiveness_distribution(interactions)

        fig, ax = plt.subplots(figsize=(6, 3))

        ratings = [5, 4, 3, 2, 1]
        counts = [dist.get(r, 0) for r in ratings]
        labels = ["★★★★★", "★★★★☆", "★★★☆☆", "★★☆☆☆", "★☆☆☆☆"]
        colors = ["#22c55e", "#84cc16", "#eab308", "#f97316", "#ef4444"]

        ax.barh(labels, counts, color=colors)
        ax.set_xlabel("Count")
        ax.set_title("Effectiveness Distribution")

        # Clean styling
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def render_roi_chart(self) -> bytes:
        """
        Render ROI comparison as bar chart.

        Returns:
            PNG image bytes.
        """
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        sessions = self.storage.load_sessions()
        interactions = self.storage.load_interactions()
        roi = self.statistics.calculate_roi_metrics(sessions, interactions)

        fig, ax = plt.subplots(figsize=(6, 4))

        categories = ["Human\nBaseline", "AI\nActual", "Savings"]
        values = [
            roi["cost_metrics"]["human_baseline_cost"],
            roi["cost_metrics"]["total_ai_cost"],
            roi["cost_metrics"]["cost_saved"],
        ]
        colors = ["#64748b", "#3b82f6", "#22c55e"]

        bars = ax.bar(categories, values, color=colors)

        # Add value labels on bars
        for bar, val in zip(bars, values, strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"${val:,.0f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )

        ax.set_ylabel("Cost ($)")
        ax.set_title(f"ROI Summary ({roi['cost_metrics']['roi_percentage']:.0f}%)")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def render_sessions_timeline(self) -> bytes:
        """
        Render sessions as timeline chart.

        Returns:
            PNG image bytes.
        """
        import matplotlib

        matplotlib.use("Agg")
        from datetime import datetime

        import matplotlib.pyplot as plt

        sessions = self.storage.load_sessions()

        # Extract session data
        session_list = []
        for _sid, session in sessions.items():
            if session.get("start_time"):
                try:
                    start_str = session["start_time"].replace("Z", "+00:00")
                    start = datetime.fromisoformat(start_str)
                    duration = self.statistics.calculate_session_duration_minutes(session)
                    session_list.append((start, duration, session.get("status", "unknown")))
                except (ValueError, TypeError):
                    continue

        if not session_list:
            # Empty chart
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.text(0.5, 0.5, "No sessions yet", ha="center", va="center", fontsize=14)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
        else:
            session_list.sort(key=lambda x: x[0])

            fig, ax = plt.subplots(figsize=(8, 3))

            dates = [s[0] for s in session_list]
            durations = [s[1] for s in session_list]
            colors = [
                "#22c55e" if s[2] == "completed" else "#3b82f6" if s[2] == "active" else "#94a3b8"
                for s in session_list
            ]

            ax.bar(range(len(dates)), durations, color=colors)
            ax.set_ylabel("Duration (min)")
            ax.set_title("Session Timeline")
            ax.set_xticks(range(len(dates)))
            ax.set_xticklabels(
                [d.strftime("%m/%d") for d in dates],
                rotation=45,
                ha="right",
            )
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
