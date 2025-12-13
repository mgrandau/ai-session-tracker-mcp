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

__all__ = [
    "SessionViewModel",
    "ROIViewModel",
    "EffectivenessViewModel",
    "IssueViewModel",
    "SessionGapViewModel",
    "SessionGapsViewModel",
    "DashboardOverview",
    "DashboardPresenter",
    "ChartPresenter",
]

# Chart color palette for consistent styling
STATUS_COLORS: dict[str, str] = {
    "completed": "#22c55e",
    "active": "#3b82f6",
    "default": "#94a3b8",
}

EFFECTIVENESS_COLORS: dict[int, str] = {
    5: "#22c55e",
    4: "#84cc16",
    3: "#eab308",
    2: "#f97316",
    1: "#ef4444",
}


def _format_duration(minutes: float) -> str:
    """
    Format duration as human-readable string.

    Args:
        minutes: Duration in minutes.

    Returns:
        String like "45m" or "1.5h".
    """
    if minutes < 60:
        return f"{minutes:.0f}m"
    return f"{minutes / 60:.1f}h"


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
        """
        Format duration as human-readable string.

        Converts raw duration_minutes to a compact display format.
        Durations under 60 minutes show as minutes (e.g., "45m"),
        longer durations show as hours (e.g., "2.5h").

        Business context: Compact duration format allows sessions to
        fit in narrow table columns while remaining readable at a glance.

        Args:
            None: Property method, accesses self.duration_minutes.

        Returns:
            String with duration. Examples: "45m", "1.5h", "8.0h".

        Raises:
            None: Pure calculation, never raises.

        Example:
            >>> session = SessionViewModel(..., duration_minutes=90, ...)
            >>> session.duration_display
            '1.5h'
        """
        return _format_duration(self.duration_minutes)

    @property
    def effectiveness_stars(self) -> str:
        """
        Convert effectiveness average to star representation.

        Renders the numeric effectiveness_avg (1-5) as a visual string
        of filled (★) and empty (☆) stars. Truncates to integer, so
        4.7 shows as "★★★★☆". Returns em-dash for zero/negative.

        Business context: Star ratings are universally understood and
        provide quick visual assessment of session quality without
        requiring interpretation of numbers.

        Args:
            None: Property method, accesses self.effectiveness_avg.

        Returns:
            String of 5 characters: filled and empty stars, or "—"
            if no effectiveness data.

        Raises:
            None: Pure calculation, never raises.

        Example:
            >>> session = SessionViewModel(..., effectiveness_avg=4.2, ...)
            >>> session.effectiveness_stars
            '★★★★☆'
        """
        if self.effectiveness_avg <= 0:
            return "—"
        full = int(self.effectiveness_avg)
        return "★" * full + "☆" * (5 - full)

    @property
    def status_class(self) -> str:
        """
        Get CSS class name for status badge styling.

        Maps session status strings to CSS class names for consistent
        color-coded status badges. Unknown statuses get a neutral style.

        Business context: Status badges provide instant visual
        identification of session state. Green for completed, blue
        for active, gray for abandoned or unknown.

        Args:
            None: Property method, accesses self.status.

        Returns:
            CSS class name string: "status-active", "status-completed",
            "status-abandoned", or "status-unknown".

        Raises:
            None: Dict lookup never raises.

        Example:
            >>> session = SessionViewModel(..., status="completed", ...)
            >>> session.status_class
            'status-completed'
        """
        return {
            "active": "status-active",
            "completed": "status-completed",
            "abandoned": "status-abandoned",
        }.get(self.status, "status-unknown")

    @property
    def start_time_display(self) -> str:
        """
        Format start time as local HH:MM:SS.

        Parses the ISO 8601 start_time and extracts just the time
        portion in hours:minutes:seconds format for compact display.

        Business context: Shows when the session started without
        cluttering the table with full datetime strings.

        Returns:
            String like "14:30:45" or "—" if no start time.

        Example:
            >>> session = SessionViewModel(..., start_time="2025-01-01T14:30:45+00:00", ...)
            >>> session.start_time_display
            '14:30:45'
        """
        if not self.start_time:
            return "—"
        try:
            from datetime import datetime

            start_str = self.start_time.replace("Z", "+00:00")
            dt = datetime.fromisoformat(start_str)
            return dt.strftime("%H:%M:%S")
        except (ValueError, TypeError):
            return "—"


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
        """
        Format time saved as human-readable string.

        Converts time_saved_hours to display format. Times under 1 hour
        show as minutes (e.g., "45 minutes"), longer times show as
        hours (e.g., "2.5 hours").

        Business context: Time savings is a key metric for demonstrating
        AI value. Human-readable format makes reports accessible to
        non-technical stakeholders.

        Args:
            None: Property method, accesses self.time_saved_hours.

        Returns:
            String with time and unit. Examples: "30 minutes", "8.0 hours".

        Raises:
            None: Pure calculation, never raises.

        Example:
            >>> roi = ROIViewModel(..., time_saved_hours=2.5, ...)
            >>> roi.time_saved_display
            '2.5 hours'
        """
        if self.time_saved_hours < 1:
            return f"{self.time_saved_hours * 60:.0f} minutes"
        return f"{self.time_saved_hours:.1f} hours"

    @property
    def cost_saved_display(self) -> str:
        """
        Format cost saved as currency string.

        Formats cost_saved as US dollars with comma separators and
        two decimal places for consistent display.

        Business context: Dollar amounts communicate ROI value directly
        to stakeholders and finance teams. Formatted for readability
        in reports and dashboards.

        Args:
            None: Property method, accesses self.cost_saved.

        Returns:
            String in format "$X,XXX.XX". Examples: "$0.00", "$1,234.56".

        Raises:
            None: String formatting never raises.

        Example:
            >>> roi = ROIViewModel(..., cost_saved=1500.50, ...)
            >>> roi.cost_saved_display
            '$1,500.50'
        """
        return f"${self.cost_saved:,.2f}"

    @property
    def roi_class(self) -> str:
        """
        Get CSS class name for ROI-based styling.

        Maps ROI percentage to semantic CSS classes for color-coded
        display. Thresholds: >=50% excellent (green), >=25% good,
        >=0% neutral, <0% negative (red).

        Business context: Color-coded ROI provides instant visual
        feedback on AI tool value. Executive dashboards use this
        for at-a-glance health checks.

        Args:
            None: Property method, accesses self.roi_percentage.

        Returns:
            CSS class name string: "roi-excellent", "roi-good",
            "roi-neutral", or "roi-negative".

        Raises:
            None: Numeric comparison never raises.

        Example:
            >>> roi = ROIViewModel(..., roi_percentage=66.7, ...)
            >>> roi.roi_class
            'roi-excellent'
        """
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
        """
        Calculate proportional bar width for chart display.

        Computes the percentage width for a horizontal bar representing
        the count of interactions at the given rating level. Width is
        proportional to total_interactions.

        Business context: Bar charts visualize effectiveness distribution.
        This method provides ready-to-use percentage widths for CSS
        width properties in HTML templates.

        Args:
            rating: Effectiveness rating (1-5) to get bar width for.

        Returns:
            Integer percentage 0-100 for bar width. Returns 0 if no
            interactions. Never raises exceptions.

        Example:
            >>> eff = EffectivenessViewModel(distribution={5: 10, 4: 5}, total_interactions=15)
            >>> eff.bar_width(5)
            66
        """
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
        """
        Get count of issues at specified severity level.

        Looks up the count for a severity level in the by_severity dict.
        Returns 0 for unknown or missing severity levels.

        Business context: Severity counts enable conditional display
        of warning badges and prioritization of issue investigation.

        Args:
            level: Severity level string ("low", "medium", "high", "critical").

        Returns:
            Integer count of issues at that severity. Returns 0 if level
            not found. Never raises exceptions.

        Example:
            >>> issues = IssueViewModel(total=5, by_severity={'critical': 2, 'high': 3})
            >>> issues.severity_count('critical')
            2
        """
        return self.by_severity.get(level, 0)

    @property
    def critical_count(self) -> int:
        """
        Get count of critical severity issues.

        Convenience property that calls severity_count("critical").
        Critical issues are those that blocked progress or caused bugs.

        Business context: Critical issues require immediate attention.
        This property enables easy access for conditional alerting
        and dashboard warning badges.

        Args:
            None: Property method, accesses self.by_severity.

        Returns:
            Integer count of critical issues. Returns 0 if none.

        Raises:
            None: Dict lookup with default never raises.

        Example:
            >>> issues = IssueViewModel(total=5, by_severity={'critical': 2})
            >>> issues.critical_count
            2
        """
        return self.severity_count("critical")

    @property
    def high_count(self) -> int:
        """
        Get count of high severity issues.

        Convenience property that calls severity_count("high").
        High issues caused substantial rework but didn't block progress.

        Business context: High severity issues indicate quality problems
        that should be investigated. Combined with critical_count, these
        determine overall health status.

        Args:
            None: Property method, accesses self.by_severity.

        Returns:
            Integer count of high severity issues. Returns 0 if none.

        Raises:
            None: Dict lookup with default never raises.

        Example:
            >>> issues = IssueViewModel(total=5, by_severity={'high': 3})
            >>> issues.high_count
            3
        """
        return self.severity_count("high")


@dataclass
class SessionGapViewModel:
    """View model for a single session gap."""

    from_session: str
    to_session: str
    duration_minutes: float
    classification: str

    @property
    def duration_display(self) -> str:
        """
        Format gap duration as human-readable string.

        Converts duration_minutes to compact display. Under 60 minutes shows
        as minutes, longer durations show as hours.

        Returns:
            String like "5m", "45m", "2.5h".
        """
        return _format_duration(self.duration_minutes)

    @property
    def classification_emoji(self) -> str:
        """
        Get emoji for gap classification.

        Returns:
            Emoji indicating gap type: ⚡ quick, ✓ normal, ⏸ extended, 🔴 long.
        """
        return {
            "quick": "⚡",
            "normal": "✓",
            "extended": "⏸",
            "long_break": "🔴",
        }.get(self.classification, "•")

    @property
    def classification_class(self) -> str:
        """
        Get CSS class for gap classification styling.

        Returns:
            CSS class name for color-coded display.
        """
        return f"gap-{self.classification.replace('_', '-')}"


@dataclass
class SessionGapsViewModel:
    """View model for session gaps analysis panel."""

    gaps: list[SessionGapViewModel] = field(default_factory=list)
    total_gaps: int = 0
    average_gap_minutes: float = 0.0
    by_classification: dict[str, int] = field(default_factory=dict)
    friction_indicators: list[str] = field(default_factory=list)

    @property
    def average_display(self) -> str:
        """
        Format average gap as human-readable string.

        Returns:
            String like "15m" or "1.5h".
        """
        return _format_duration(self.average_gap_minutes)

    @property
    def has_friction(self) -> bool:
        """
        Check if any friction indicators were detected.

        Returns:
            True if friction_indicators list is non-empty.
        """
        return len(self.friction_indicators) > 0

    def classification_count(self, classification: str) -> int:
        """
        Get count for a specific classification.

        Args:
            classification: One of 'quick', 'normal', 'extended', 'long_break'.

        Returns:
            Count of gaps with that classification.
        """
        return self.by_classification.get(classification, 0)


@dataclass
class DashboardOverview:
    """Complete view model for dashboard overview page."""

    sessions: list[SessionViewModel] = field(default_factory=list)
    roi: ROIViewModel | None = None
    effectiveness: EffectivenessViewModel | None = None
    issues: IssueViewModel | None = None
    session_gaps: SessionGapsViewModel | None = None
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
        Initialize dashboard presenter with data dependencies.

        Injects the storage manager for data access and statistics engine
        for metric calculations. The presenter uses these to transform
        raw data into display-ready view models.

        Business context: Dependency injection enables testing with mock
        storage and statistics, ensuring presenter logic can be verified
        independently of actual file I/O and calculations.

        Args:
            storage: StorageManager instance for loading sessions,
                interactions, and issues from persistent storage.
            statistics: StatisticsEngine instance for calculating
                durations, effectiveness averages, and ROI metrics.

        Raises:
            TypeError: If storage or statistics are not the expected types.

        Example:
            >>> storage = StorageManager()
            >>> stats = StatisticsEngine()
            >>> presenter = DashboardPresenter(storage, stats)
            >>> overview = presenter.get_overview()
        """
        self.storage = storage
        self.statistics = statistics

    def get_overview(self) -> DashboardOverview:
        """
        Get complete overview data for dashboard.

        Loads all data from storage (sessions, interactions, issues),
        builds view models for each dashboard panel, and generates
        a summary report text. Returns a complete view model ready
        for template rendering.

        Business context: The overview is the main dashboard entry point.
        It aggregates all metrics into a single request, enabling
        efficient page rendering with minimal I/O.

        Returns:
            DashboardOverview dataclass with sessions list, roi summary,
            effectiveness distribution, issues summary, and report text.
            All fields populated; empty data results in zero values.

        Raises:
            OSError: If storage files cannot be read (rare, handled by
            storage layer with empty defaults).

        Example:
            >>> presenter = DashboardPresenter(storage, stats)
            >>> overview = presenter.get_overview()
            >>> len(overview.sessions)
            5
        """
        sessions_data = self.storage.load_sessions()
        interactions_data = self.storage.load_interactions()
        issues_data = self.storage.load_issues()

        return DashboardOverview(
            sessions=self._build_session_list(sessions_data, interactions_data),
            roi=self._build_roi(sessions_data, interactions_data),
            effectiveness=self._build_effectiveness(interactions_data),
            issues=self._build_issues(issues_data),
            session_gaps=self._build_session_gaps(sessions_data),
            report_text=self.statistics.generate_summary_report(
                sessions_data, interactions_data, issues_data
            ),
        )

    def get_sessions_list(self) -> list[SessionViewModel]:
        """
        Retrieve sessions as view models for list display.

        Loads session and interaction data, transforms them into view models
        with computed display properties (duration, stars, status class),
        and returns sorted by start time (newest first).

        Business context: The sessions list is the primary navigation for
        the dashboard, showing all tracked work at a glance with key
        metrics for quick assessment.

        Returns:
            List of SessionViewModel objects sorted by start_time descending.
            Each contains computed properties like duration_display,
            effectiveness_stars, and status_class for template rendering.

        Raises:
            None - Storage errors result in empty list.

        Example:
            >>> presenter = DashboardPresenter(storage, stats)
            >>> sessions = presenter.get_sessions_list()
            >>> for s in sessions[:5]:
            ...     print(f"{s.session_id}: {s.status} ({s.duration_display})")
        """
        sessions_data = self.storage.load_sessions()
        interactions_data = self.storage.load_interactions()
        return self._build_session_list(sessions_data, interactions_data)

    def get_roi_summary(self) -> ROIViewModel:
        """
        Retrieve ROI metrics as a view model for display.

        Loads session and interaction data, calculates ROI metrics using
        the statistics engine, and transforms into a view model with
        computed display properties for currency and time formatting.

        Business context: ROI summary is the key executive metric showing
        the financial value of AI-assisted development. Used prominently
        in dashboards and reports for stakeholder communication.

        Returns:
            ROIViewModel with computed properties including cost_saved_display,
            time_saved_display, and roi_class for color-coded rendering.

        Raises:
            None - Calculation errors result in zero values.

        Example:
            >>> presenter = DashboardPresenter(storage, stats)
            >>> roi = presenter.get_roi_summary()
            >>> print(f"ROI: {roi.roi_percentage:.1f}% ({roi.cost_saved_display})")
            ROI: 66.7% ($1,234.00)
        """
        sessions_data = self.storage.load_sessions()
        interactions_data = self.storage.load_interactions()
        return self._build_roi(sessions_data, interactions_data)

    def get_effectiveness(self) -> EffectivenessViewModel:
        """
        Retrieve effectiveness distribution as a view model.

        Loads all interactions and calculates effectiveness distribution
        and average rating. Returns a view model with computed bar_width
        method for rendering proportional bar charts.

        Business context: Effectiveness distribution shows AI output
        quality trends. Stakeholders use this to assess whether AI
        tools are providing consistent value.

        Returns:
            EffectivenessViewModel with distribution dict, average score,
            total_interactions count, and bar_width() method for charts.

        Raises:
            None - Calculation errors result in zero values.

        Example:
            >>> presenter = DashboardPresenter(storage, stats)
            >>> eff = presenter.get_effectiveness()
            >>> print(f"Average: {eff.average:.1f}/5 ({eff.total_interactions} interactions)")
        """
        interactions_data = self.storage.load_interactions()
        return self._build_effectiveness(interactions_data)

    def get_session_gaps(self) -> SessionGapsViewModel:
        """
        Retrieve session gap analysis as a view model.

        Loads all sessions and calculates inter-session gaps to identify
        workflow patterns and potential friction points.

        Business context: Gap analysis reveals user engagement patterns.
        Long gaps may indicate tool friction or workflow interruptions
        that need investigation.

        Returns:
            SessionGapsViewModel with gaps list, summary statistics,
            and friction indicators.

        Example:
            >>> presenter = DashboardPresenter(storage, stats)
            >>> gaps = presenter.get_session_gaps()
            >>> print(f"Avg gap: {gaps.average_display}")
        """
        sessions_data = self.storage.load_sessions()
        return self._build_session_gaps(sessions_data)

    def _group_interactions_by_session(
        self,
        interactions: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Group interactions by their session_id.

        Args:
            interactions: List of interaction records.

        Returns:
            Dict mapping session_id to list of interactions.
        """
        grouped: dict[str, list[dict[str, Any]]] = {}
        for interaction in interactions:
            sid = interaction.get("session_id", "")
            if sid not in grouped:
                grouped[sid] = []
            grouped[sid].append(interaction)
        return grouped

    def _calculate_session_effectiveness(
        self,
        session_interactions: list[dict[str, Any]],
    ) -> float:
        """
        Calculate average effectiveness for a session's interactions.

        Args:
            session_interactions: List of interactions for one session.

        Returns:
            Average effectiveness rating, or 0.0 if no interactions.
        """
        if not session_interactions:
            return 0.0
        total: float = sum(float(i.get("effectiveness_rating", 0)) for i in session_interactions)
        return total / len(session_interactions)

    def _build_session_list(
        self,
        sessions: dict[str, Any],
        interactions: list[dict[str, Any]],
    ) -> list[SessionViewModel]:
        """
        Transform raw session data into display-ready view models.

        Groups interactions by session, calculates per-session statistics,
        creates SessionViewModel instances with computed properties, and
        sorts by start time descending for display.

        Business context: This transformation layer enables consistent
        formatting and computed display values (star ratings, duration
        formatting) without duplicating logic in templates.

        Args:
            sessions: Dict of session_id -> raw session data from storage.
            interactions: List of all interaction records for calculating
                per-session effectiveness averages.

        Returns:
            List of SessionViewModel sorted by start_time descending.
            Each model includes duration_display, effectiveness_stars,
            and status_class computed properties.

        Raises:
            TypeError: If sessions is not a dict or interactions not a list.

        Example:
            >>> sessions = storage.load_sessions()
            >>> interactions = storage.load_interactions()
            >>> models = presenter._build_session_list(sessions, interactions)
        """
        interactions_by_session = self._group_interactions_by_session(interactions)

        result: list[SessionViewModel] = []
        for session_id, session in sessions.items():
            session_interactions = interactions_by_session.get(session_id, [])
            result.append(
                SessionViewModel(
                    session_id=session_id,
                    project=session.get("project", "Unknown"),
                    status=session.get("status", "unknown"),
                    duration_minutes=self.statistics.calculate_session_duration_minutes(session),
                    interaction_count=len(session_interactions),
                    effectiveness_avg=self._calculate_session_effectiveness(session_interactions),
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
        """
        Transform raw metrics into ROI view model for display.

        Uses the statistics engine to calculate ROI metrics, then maps
        the nested result dict into a flat ROIViewModel with computed
        display properties for templates.

        Business context: ROI calculation involves complex cost comparisons.
        This method bridges the calculation layer and presentation layer,
        ensuring consistent data transformation.

        Args:
            sessions: Dict of session_id -> raw session data for ROI calculation.
            interactions: List of all interaction records for productivity metrics.

        Returns:
            ROIViewModel with all cost, time, and session metrics plus
            computed properties like time_saved_display and cost_saved_display.

        Raises:
            TypeError: If input types are incorrect.

        Example:
            >>> roi_model = presenter._build_roi(sessions, interactions)
            >>> print(roi_model.roi_percentage)
        """
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
        """
        Transform interaction data into effectiveness view model.

        Calculates effectiveness distribution and average using the
        statistics engine, then packages into a view model with
        computed bar_width method for chart rendering.

        Business context: Effectiveness metrics show AI quality trends.
        The view model provides template-ready data with computation
        methods for proportional bar widths in visualizations.

        Args:
            interactions: List of all interaction records containing
                effectiveness_rating values (1-5).

        Returns:
            EffectivenessViewModel with distribution dict (rating -> count),
            average score, total count, and bar_width(rating) method.

        Raises:
            TypeError: If interactions is not a list.

        Example:
            >>> eff = presenter._build_effectiveness(interactions)
            >>> print(f"5-star width: {eff.bar_width(5)}%")
        """
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
        """
        Transform issue data into summary view model.

        Aggregates issues by type and severity using the statistics
        engine, then packages into a view model with convenience
        methods for accessing severity counts.

        Business context: Issue summary helps identify patterns in
        AI failures. High severity counts may trigger investigation
        into prompting strategies or model selection.

        Args:
            issues: List of all issue records containing issue_type
                and severity fields.

        Returns:
            IssueViewModel with total count, by_type dict, by_severity dict,
            and convenience properties like critical_count and high_count.

        Raises:
            TypeError: If issues is not a list.

        Example:
            >>> issue_model = presenter._build_issues(issues)
            >>> print(f"Critical issues: {issue_model.critical_count}")
        """
        summary = self.statistics.calculate_issue_summary(issues)
        return IssueViewModel(
            total=summary["total"],
            by_type=summary["by_type"],
            by_severity=summary["by_severity"],
        )

    def _build_session_gaps(
        self,
        sessions: dict[str, Any],
    ) -> SessionGapsViewModel:
        """
        Transform session data into gap analysis view model.

        Calculates time gaps between consecutive sessions using the
        statistics engine, then packages into a view model with
        classification breakdowns and friction indicators.

        Business context: Gap analysis reveals workflow friction.
        Long or frequent gaps may indicate tool usability issues
        or user disengagement patterns.

        Args:
            sessions: Dict of session_id -> session_data with timestamps.

        Returns:
            SessionGapsViewModel with gaps list, averages, classification
            counts, and friction indicators.

        Example:
            >>> gaps_model = presenter._build_session_gaps(sessions)
            >>> print(f"Avg gap: {gaps_model.average_display}")
        """
        gap_data = self.statistics.calculate_session_gaps(sessions)

        gap_models = [
            SessionGapViewModel(
                from_session=g["from_session"],
                to_session=g["to_session"],
                duration_minutes=g["duration_minutes"],
                classification=g["classification"],
            )
            for g in gap_data["gaps"]
        ]

        return SessionGapsViewModel(
            gaps=gap_models,
            total_gaps=gap_data["summary"]["total_gaps"],
            average_gap_minutes=gap_data["summary"]["average_gap_minutes"],
            by_classification=gap_data["summary"]["by_classification"],
            friction_indicators=gap_data["friction_indicators"],
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
        """
        Initialize chart presenter with data dependencies.

        Injects storage manager for data access and statistics engine for
        metric calculations. Uses matplotlib for server-side chart rendering
        (lazy-imported to keep it optional).

        Business context: Server-side chart rendering ensures consistent
        appearance across all clients and enables chart caching. Charts
        can be embedded in emails, exported to PDFs, or refreshed via htmx.

        Args:
            storage: StorageManager instance for loading sessions,
                interactions, and issues from persistent storage.
            statistics: StatisticsEngine instance for calculating
                metrics displayed in charts.

        Raises:
            TypeError: If storage or statistics are not the expected types.

        Example:
            >>> storage = StorageManager()
            >>> stats = StatisticsEngine()
            >>> presenter = ChartPresenter(storage, stats)
            >>> png_bytes = presenter.render_roi_chart()
        """
        self.storage = storage
        self.statistics = statistics

    def render_effectiveness_chart(self) -> bytes:
        """
        Render effectiveness distribution as a horizontal bar chart PNG.

        Creates a matplotlib chart showing the count of interactions at
        each rating level (1-5 stars) with color-coded bars from red (1)
        to green (5). Uses a non-interactive backend for server-side rendering.

        Business context: Visual effectiveness distribution provides
        instant insight into AI quality patterns. A healthy distribution
        shows most ratings at 4-5 stars with few at 1-2.

        Returns:
            PNG image as bytes, suitable for HTTP response or file save.
            Image is 600x300 pixels at 100 DPI.

        Raises:
            ImportError: If matplotlib is not installed. Caller should
                catch this and provide fallback (e.g., placeholder SVG).

        Example:
            >>> presenter = ChartPresenter(storage, stats)
            >>> try:
            ...     png = presenter.render_effectiveness_chart()
            ...     with open('chart.png', 'wb') as f:
            ...         f.write(png)
            ... except ImportError:
            ...     print('matplotlib not available')
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
        colors = [EFFECTIVENESS_COLORS[r] for r in ratings]

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
        Render time comparison as a vertical bar chart PNG.

        Creates a matplotlib chart comparing three values: human baseline
        time estimate, AI actual time, and human oversight time. Bars are
        color-coded with value labels showing hours.

        Business context: The time chart shows at a glance how much time
        AI saves compared to human estimates, and the oversight required.

        Returns:
            PNG image as bytes, suitable for HTTP response or file save.
            Image is 600x400 pixels at 100 DPI with value labels on bars.

        Raises:
            ImportError: If matplotlib is not installed. Caller should
                catch this and provide fallback (e.g., placeholder SVG).

        Example:
            >>> presenter = ChartPresenter(storage, stats)
            >>> try:
            ...     png = presenter.render_roi_chart()
            ...     # Serve in HTTP response
            ... except ImportError:
            ...     # Return placeholder
        """
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        sessions = self.storage.load_sessions()
        interactions = self.storage.load_interactions()
        roi = self.statistics.calculate_roi_metrics(sessions, interactions)
        gaps = self.statistics.calculate_session_gaps(sessions)

        fig, ax = plt.subplots(figsize=(6, 4))

        # Time metrics: human estimate, AI actual, oversight
        human_hours = roi["time_metrics"]["estimated_human_hours"]
        ai_hours = roi["time_metrics"]["total_ai_hours"]

        # Oversight = AI time + quick/normal gaps (not extended or long_break)
        oversight_gap_minutes = sum(
            g["duration_minutes"]
            for g in gaps["gaps"]
            if g["classification"] in ("quick", "normal")
        )
        oversight_hours = ai_hours + (oversight_gap_minutes / 60.0)

        categories = ["Human\nEstimate", "AI\nActual", "Human\nOversight"]
        values = [human_hours, ai_hours, oversight_hours]
        colors = ["#64748b", "#3b82f6", "#f59e0b"]

        bars = ax.bar(categories, values, color=colors)

        # Add value labels on bars
        for bar, val in zip(bars, values, strict=True):
            label = f"{val:.1f}h" if val >= 1 else f"{val * 60:.0f}m"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                label,
                ha="center",
                va="bottom",
                fontsize=10,
            )

        ax.set_ylabel("Time (hours)")
        time_saved = human_hours - oversight_hours
        ax.set_title(f"Time Comparison (Saved: {time_saved:.1f}h)")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _parse_session_for_timeline(
        self,
        session: dict[str, Any],
    ) -> tuple[Any, float, str] | None:
        """
        Extract timeline data from a session.

        Args:
            session: Raw session data dict.

        Returns:
            Tuple of (datetime, duration_minutes, status) or None if invalid.
        """
        from datetime import datetime

        start_time = session.get("start_time")
        if not start_time:
            return None
        try:
            start_str = start_time.replace("Z", "+00:00")
            start = datetime.fromisoformat(start_str)
            duration = self.statistics.calculate_session_duration_minutes(session)
            return (start, duration, session.get("status", "unknown"))
        except (ValueError, TypeError):
            return None

    def _status_to_color(self, status: str) -> str:
        """
        Map session status to chart color.

        Args:
            status: Session status string.

        Returns:
            Hex color code from STATUS_COLORS.
        """
        return STATUS_COLORS.get(status, STATUS_COLORS["default"])

    def _render_empty_timeline(self) -> Any:
        """
        Render placeholder chart when no sessions exist.

        Returns:
            Matplotlib figure and axes.
        """
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "No sessions yet", ha="center", va="center", fontsize=14)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        return fig, ax

    def render_sessions_timeline(self) -> bytes:
        """
        Render sessions as a timeline bar chart PNG.

        Creates a matplotlib chart showing session durations over time.
        Bars are positioned chronologically with colors indicating status:
        green for completed, blue for active, gray for other. X-axis shows
        dates in MM/DD format.

        Business context: The timeline chart reveals work patterns over
        time, helping identify busy periods, session duration trends, and
        completion rates. Useful for capacity planning and retrospectives.

        Returns:
            PNG image as bytes, suitable for HTTP response or file save.
            Image is 800x300 pixels at 100 DPI. Shows placeholder text
            if no sessions exist.

        Raises:
            ImportError: If matplotlib is not installed. Caller should
                catch this and provide fallback (e.g., placeholder SVG).

        Example:
            >>> presenter = ChartPresenter(storage, stats)
            >>> try:
            ...     png = presenter.render_sessions_timeline()
            ...     # Serve in HTTP response or save to file
            ... except ImportError:
            ...     # Return placeholder
        """
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        sessions = self.storage.load_sessions()

        # Extract valid session data using helper
        session_list = [
            parsed
            for session in sessions.values()
            if (parsed := self._parse_session_for_timeline(session)) is not None
        ]

        if not session_list:
            fig, _ax = self._render_empty_timeline()
        else:
            session_list.sort(key=lambda x: x[0])
            fig, ax = plt.subplots(figsize=(8, 3))

            dates = [s[0] for s in session_list]
            durations = [s[1] for s in session_list]
            colors = [self._status_to_color(s[2]) for s in session_list]

            ax.bar(range(len(dates)), durations, color=colors)
            ax.set_ylabel("Duration (min)")
            ax.set_title("Session Timeline")
            ax.set_xticks(range(len(dates)))
            ax.set_xticklabels(
                [d.strftime("%H:%M:%S") for d in dates],
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
