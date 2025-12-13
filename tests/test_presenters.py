"""Tests for presenters module."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import MagicMock

import pytest

from ai_session_tracker_mcp.presenters import (
    ChartPresenter,
    DashboardOverview,
    DashboardPresenter,
    EffectivenessViewModel,
    IssueViewModel,
    ROIViewModel,
    SessionViewModel,
)
from ai_session_tracker_mcp.statistics import StatisticsEngine
from ai_session_tracker_mcp.storage import StorageManager


def _has_matplotlib() -> bool:
    """Check if matplotlib is available for chart tests.

    Tests requiring matplotlib are skipped when the library is not installed.
    This allows the test suite to run in environments without visualization
    dependencies.

    Business context:
    Chart generation is optional functionality. Skip decorator using this
    helper enables test suite to pass in minimal environments.

    Args:
        No arguments required for this function.

    Raises:
        No exceptions raised - import failures are caught internally.

    Returns:
        True if matplotlib can be imported, False otherwise.

    Example:
        @pytest.mark.skipif(not _has_matplotlib(), reason="matplotlib not installed")
        def test_chart(): ...
    """
    try:
        import matplotlib  # noqa: F401

        return True
    except ImportError:
        return False


class TestSessionViewModel:
    """Tests for SessionViewModel dataclass."""

    def test_creation(self) -> None:
        """Verifies SessionViewModel can be created with all fields.

        Tests that the view model dataclass accepts and stores all
        session display properties correctly.

        Business context:
        View models transform raw session data for UI display.
        All fields must be accessible for template rendering.

        Arrangement:
        Prepare all required field values.

        Action:
        Create SessionViewModel instance with all fields.

        Assertion Strategy:
        Validates key fields match provided values.

        Testing Principle:
        Validates dataclass creation and field storage.
        """
        vm = SessionViewModel(
            session_id="abc123",
            project="test-project",
            status="completed",
            duration_minutes=45.5,
            interaction_count=10,
            effectiveness_avg=4.2,
            start_time="2024-01-01T10:00:00Z",
            end_time="2024-01-01T10:45:30Z",
        )
        assert vm.session_id == "abc123"
        assert vm.project == "test-project"
        assert vm.status == "completed"

    def test_duration_display_minutes(self) -> None:
        """Verifies duration_display shows minutes for < 60 min.

        Tests that short sessions display in minutes format
        for better readability.

        Business context:
        Duration formatting improves dashboard readability. Short
        sessions shown in minutes, longer in hours.

        Arrangement:
        Create view model with 45 minute duration.

        Action:
        Access duration_display property.

        Assertion Strategy:
        Validates format shows '45m'.

        Testing Principle:
        Validates display formatting logic.
        """
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="active",
            duration_minutes=45.0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="",
            end_time=None,
        )
        assert vm.duration_display == "45m"

    def test_duration_display_hours(self) -> None:
        """Verifies duration_display shows hours for >= 60 min.

        Tests that longer sessions display in hours format
        for better readability.

        Business context:
        Duration formatting improves dashboard readability. Showing
        '1.5h' is clearer than '90m' for longer sessions.

        Arrangement:
        Create view model with 90 minute duration.

        Action:
        Access duration_display property.

        Assertion Strategy:
        Validates format shows '1.5h'.

        Testing Principle:
        Validates display formatting threshold.
        """
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="active",
            duration_minutes=90.0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="",
            end_time=None,
        )
        assert vm.duration_display == "1.5h"

    def test_effectiveness_stars(self) -> None:
        """Verifies effectiveness_stars returns star representation.

        Tests that effectiveness rating is displayed as visual star
        rating for quick assessment.

        Business context:
        Star ratings provide intuitive visual feedback. 3.5 rating
        shows 3 filled and 2 empty stars.

        Arrangement:
        Create view model with 3.5 effectiveness rating.

        Action:
        Access effectiveness_stars property.

        Assertion Strategy:
        Validates star string matches expected pattern.

        Testing Principle:
        Validates visual representation logic.
        """
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="active",
            duration_minutes=0,
            interaction_count=0,
            effectiveness_avg=3.5,
            start_time="",
            end_time=None,
        )
        assert vm.effectiveness_stars == "★★★☆☆"

    def test_effectiveness_stars_zero(self) -> None:
        """Verifies effectiveness_stars handles zero rating.

        Tests that sessions without ratings show dash instead of
        empty stars.

        Business context:
        Zero rating indicates no interactions logged. Dash is
        clearer than empty star row.

        Arrangement:
        Create view model with zero effectiveness.

        Action:
        Access effectiveness_stars property.

        Assertion Strategy:
        Validates result is em-dash character.

        Testing Principle:
        Validates edge case handling.
        """
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="active",
            duration_minutes=0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="",
            end_time=None,
        )
        assert vm.effectiveness_stars == "—"

    @pytest.mark.parametrize(
        "status,expected_class",
        [
            pytest.param("active", "status-active", id="active"),
            pytest.param("completed", "status-completed", id="completed"),
            pytest.param("abandoned", "status-abandoned", id="abandoned"),
        ],
    )
    def test_status_class(self, status: str, expected_class: str) -> None:
        """Verifies status_class returns correct CSS class for session status.

        Business context:
        Status classes enable color-coded status indicators in UI:
        - active: Blue/progress color (in-progress sessions)
        - completed: Green/success color (finished sessions)
        - abandoned: Red/warning color (incomplete work needing attention)

        Testing Principle:
        Parameterized test validates status to CSS mapping.
        """
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status=status,
            duration_minutes=0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="",
            end_time=None,
        )
        assert vm.status_class == expected_class


class TestROIViewModel:
    """Tests for ROIViewModel dataclass."""

    def test_creation(self) -> None:
        """Verifies ROIViewModel can be created with all fields.

        Tests that the ROI view model dataclass accepts and stores all
        return-on-investment display properties correctly.

        Business context:
        ROI view models present financial metrics for AI investment
        justification. All fields support dashboard ROI displays.

        Arrangement:
        Prepare ROI metrics including sessions, time, and costs.

        Action:
        Create ROIViewModel instance with all fields.

        Assertion Strategy:
        Validates key fields match provided values.

        Testing Principle:
        Validates dataclass creation and field storage.
        """
        vm = ROIViewModel(
            total_sessions=10,
            completed_sessions=8,
            total_ai_hours=5.0,
            estimated_human_hours=15.0,
            time_saved_hours=10.0,
            human_baseline_cost=1500.0,
            total_ai_cost=300.0,
            cost_saved=1200.0,
            roi_percentage=80.0,
        )
        assert vm.total_sessions == 10
        assert vm.roi_percentage == 80.0

    def test_time_saved_display_minutes(self) -> None:
        """Verifies time_saved_display shows minutes for < 1 hour.

        Tests that small time savings display in minutes format
        for precision.

        Business context:
        Time savings formatting helps stakeholders quickly understand
        ROI. Small savings shown precisely in minutes.

        Arrangement:
        Create ROI view model with 0.5 hours saved (30 min).

        Action:
        Access time_saved_display property.

        Assertion Strategy:
        Validates format shows '30 minutes'.

        Testing Principle:
        Validates display formatting threshold.
        """
        vm = ROIViewModel(
            total_sessions=0,
            completed_sessions=0,
            total_ai_hours=0,
            estimated_human_hours=0,
            time_saved_hours=0.5,
            human_baseline_cost=0,
            total_ai_cost=0,
            cost_saved=0,
            roi_percentage=0,
        )
        assert vm.time_saved_display == "30 minutes"

    def test_time_saved_display_hours(self) -> None:
        """Verifies time_saved_display shows hours for >= 1 hour.

        Tests that larger time savings display in hours format
        for readability.

        Business context:
        Large time savings more meaningful in hours. '2.5 hours'
        is clearer than '150 minutes' for executive summaries.

        Arrangement:
        Create ROI view model with 2.5 hours saved.

        Action:
        Access time_saved_display property.

        Assertion Strategy:
        Validates format shows '2.5 hours'.

        Testing Principle:
        Validates display formatting threshold.
        """
        vm = ROIViewModel(
            total_sessions=0,
            completed_sessions=0,
            total_ai_hours=0,
            estimated_human_hours=0,
            time_saved_hours=2.5,
            human_baseline_cost=0,
            total_ai_cost=0,
            cost_saved=0,
            roi_percentage=0,
        )
        assert vm.time_saved_display == "2.5 hours"

    def test_cost_saved_display(self) -> None:
        """Verifies cost_saved_display formats as currency.

        Tests that cost savings display with dollar sign, commas,
        and appropriate precision.

        Business context:
        Currency formatting essential for financial reporting.
        Shows exact dollar value saved through AI assistance.

        Arrangement:
        Create ROI view model with $1234.56 saved.

        Action:
        Access cost_saved_display property.

        Assertion Strategy:
        Validates format includes '$', commas, and numeric value.

        Testing Principle:
        Validates currency display formatting.
        """
        vm = ROIViewModel(
            total_sessions=0,
            completed_sessions=0,
            total_ai_hours=0,
            estimated_human_hours=0,
            time_saved_hours=0,
            human_baseline_cost=0,
            total_ai_cost=0,
            cost_saved=1234.56,
            roi_percentage=0,
        )
        assert vm.cost_saved_display == "$1,234.56"

    @pytest.mark.parametrize(
        "roi_percentage,expected_class",
        [
            pytest.param(60.0, "roi-excellent", id="excellent_ge_50"),
            pytest.param(50.0, "roi-excellent", id="excellent_at_50"),
            pytest.param(30.0, "roi-good", id="good_ge_25"),
            pytest.param(25.0, "roi-good", id="good_at_25"),
            pytest.param(10.0, "roi-neutral", id="neutral_ge_0"),
            pytest.param(0.0, "roi-neutral", id="neutral_at_0"),
            pytest.param(-10.0, "roi-negative", id="negative_lt_0"),
        ],
    )
    def test_roi_class(self, roi_percentage: float, expected_class: str) -> None:
        """Verifies roi_class returns correct CSS class for ROI thresholds.

        Business context:
        ROI classification enables color-coded metrics:
        - excellent (>=50%): Green, strong AI value
        - good (>=25%): Light green, positive returns
        - neutral (>=0%): Gray, break-even
        - negative (<0%): Red, loss on investment

        Testing Principle:
        Parameterized test validates threshold classification logic.
        """
        vm = ROIViewModel(
            total_sessions=0,
            completed_sessions=0,
            total_ai_hours=0,
            estimated_human_hours=0,
            time_saved_hours=0,
            human_baseline_cost=0,
            total_ai_cost=0,
            cost_saved=0,
            roi_percentage=roi_percentage,
        )
        assert vm.roi_class == expected_class


class TestEffectivenessViewModel:
    """Tests for EffectivenessViewModel dataclass."""

    def test_creation(self) -> None:
        """Verifies EffectivenessViewModel can be created with all fields.

        Tests that the effectiveness view model dataclass accepts
        distribution, average, and total correctly.

        Business context:
        Effectiveness view models display rating distributions
        for analyzing AI output quality patterns.

        Arrangement:
        Prepare distribution dict with counts per rating level.

        Action:
        Create EffectivenessViewModel instance with all fields.

        Assertion Strategy:
        Validates average and total match provided values.

        Testing Principle:
        Validates dataclass creation and field storage.
        """
        vm = EffectivenessViewModel(
            distribution={1: 2, 2: 3, 3: 10, 4: 15, 5: 20},
            average=4.0,
            total_interactions=50,
        )
        assert vm.average == 4.0
        assert vm.total_interactions == 50

    def test_bar_width(self) -> None:
        """Verifies bar_width calculates percentage correctly.

        Tests that bar width returns correct percentage for each
        rating level in histogram display.

        Business context:
        Bar width drives histogram visualization. Percentage ensures
        bars scale proportionally to rating distribution.

        Arrangement:
        Create view model with 50/50 split between ratings 4 and 5.

        Action:
        Call bar_width for each rating level.

        Assertion Strategy:
        Validates percentages: 50% for 5, 50% for 4, 0% for 3.

        Testing Principle:
        Validates calculation logic for UI rendering.
        """
        vm = EffectivenessViewModel(
            distribution={5: 10, 4: 10, 3: 0, 2: 0, 1: 0},
            average=4.5,
            total_interactions=20,
        )
        assert vm.bar_width(5) == 50
        assert vm.bar_width(4) == 50
        assert vm.bar_width(3) == 0

    def test_bar_width_zero_total(self) -> None:
        """Verifies bar_width returns 0 when no interactions.

        Tests division-by-zero protection when total interactions
        is zero.

        Business context:
        Empty sessions have no interactions. Returning 0 prevents
        division errors and renders empty histogram.

        Arrangement:
        Create view model with zero total interactions.

        Action:
        Call bar_width method.

        Assertion Strategy:
        Validates result is 0, not error.

        Testing Principle:
        Validates edge case and error prevention.
        """
        vm = EffectivenessViewModel(distribution={}, average=0, total_interactions=0)
        assert vm.bar_width(5) == 0


class TestIssueViewModel:
    """Tests for IssueViewModel dataclass."""

    def test_creation(self) -> None:
        """Verifies IssueViewModel can be created with all fields.

        Tests that the issue view model dataclass accepts total,
        type breakdown, and severity breakdown correctly.

        Business context:
        Issue view models aggregate problem reports for dashboard
        display. Supports filtering and prioritization.

        Arrangement:
        Prepare issue counts by type and severity.

        Action:
        Create IssueViewModel instance with all fields.

        Assertion Strategy:
        Validates total matches provided value.

        Testing Principle:
        Validates dataclass creation and field storage.
        """
        vm = IssueViewModel(
            total=5,
            by_type={"hallucination": 2, "incorrect_output": 3},
            by_severity={"critical": 1, "high": 2, "medium": 2},
        )
        assert vm.total == 5

    def test_severity_count(self) -> None:
        """Verifies severity_count returns correct count.

        Tests that severity_count method returns accurate counts
        for existing and non-existing severities.

        Business context:
        Severity counts enable filtering issues by urgency.
        Missing severities should return 0, not error.

        Arrangement:
        Create view model with critical and high severity counts.

        Action:
        Call severity_count for existing and missing severity.

        Assertion Strategy:
        Validates correct count for critical, 0 for missing low.

        Testing Principle:
        Validates method handles missing keys gracefully.
        """
        vm = IssueViewModel(
            total=5,
            by_type={},
            by_severity={"critical": 3, "high": 2},
        )
        assert vm.severity_count("critical") == 3
        assert vm.severity_count("low") == 0

    def test_critical_count(self) -> None:
        """Verifies critical_count property returns correct value.

        Tests the convenience property for accessing critical
        severity count.

        Business context:
        Critical issues need immediate attention. Property provides
        quick access for dashboard highlights.

        Arrangement:
        Create view model with critical severity count of 2.

        Action:
        Access critical_count property.

        Assertion Strategy:
        Validates property returns expected value.

        Testing Principle:
        Validates convenience property delegates correctly.
        """
        vm = IssueViewModel(
            total=5,
            by_type={},
            by_severity={"critical": 2},
        )
        assert vm.critical_count == 2

    def test_high_count(self) -> None:
        """Verifies high_count property returns correct value.

        Tests the convenience property for accessing high
        severity count.

        Business context:
        High severity issues are urgent. Property provides
        quick access for dashboard warnings.

        Arrangement:
        Create view model with high severity count of 4.

        Action:
        Access high_count property.

        Assertion Strategy:
        Validates property returns expected value.

        Testing Principle:
        Validates convenience property delegates correctly.
        """
        vm = IssueViewModel(
            total=5,
            by_type={},
            by_severity={"high": 4},
        )
        assert vm.high_count == 4


class TestDashboardOverview:
    """Tests for DashboardOverview dataclass."""

    def test_creation_defaults(self) -> None:
        """Verifies DashboardOverview has sensible defaults.

        Tests that creating DashboardOverview without arguments
        uses appropriate default values.

        Business context:
        Dashboard starts empty before data loads. Default values
        prevent null reference errors in templates.

        Arrangement:
        None - tests default constructor behavior.

        Action:
        Create DashboardOverview with no arguments.

        Assertion Strategy:
        Validates all fields have safe default values.

        Testing Principle:
        Validates dataclass default factory behavior.
        """
        overview = DashboardOverview()
        assert overview.sessions == []
        assert overview.roi is None
        assert overview.effectiveness is None
        assert overview.issues is None
        assert overview.report_text == ""


class TestDashboardPresenter:
    """Tests for DashboardPresenter class."""

    def test_get_overview(self) -> None:
        """Verifies get_overview returns DashboardOverview for empty data.

        Tests that presenter handles empty storage gracefully,
        returning valid empty overview.

        Business context:
        New installations have no session data. Dashboard should
        display empty state without errors.

        Arrangement:
        Create mock storage returning empty collections.

        Action:
        Call presenter's get_overview method.

        Assertion Strategy:
        Validates returned DashboardOverview with empty sessions.

        Testing Principle:
        Validates presenter handles edge case of no data.
        """
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_sessions.return_value = {}
        mock_storage.load_interactions.return_value = []
        mock_storage.load_issues.return_value = []

        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        overview = presenter.get_overview()
        assert isinstance(overview, DashboardOverview)
        assert overview.sessions == []

    def test_get_overview_with_data(self) -> None:
        """Verifies get_overview processes session data correctly.

        Tests that presenter transforms raw session data into
        properly structured view models.

        Business context:
        Presenter aggregates data from multiple sources into
        cohesive dashboard view. Must calculate metrics correctly.

        Arrangement:
        Create mock storage with sample session and interaction.

        Action:
        Call presenter's get_overview method.

        Assertion Strategy:
        Validates session count, project name, and calculated avg.

        Testing Principle:
        Validates data transformation and aggregation logic.
        """
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_sessions.return_value = {
            "s1": {
                "project": "test",
                "status": "completed",
                "start_time": "2024-01-01T10:00:00Z",
                "end_time": "2024-01-01T11:00:00Z",
            }
        }
        mock_storage.load_interactions.return_value = [
            {"session_id": "s1", "effectiveness_rating": 4}
        ]
        mock_storage.load_issues.return_value = []

        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        overview = presenter.get_overview()
        assert len(overview.sessions) == 1
        assert overview.sessions[0].project == "test"
        assert overview.sessions[0].effectiveness_avg == 4.0

    def test_get_sessions_list(self) -> None:
        """Verifies get_sessions_list returns session view models.

        Tests that presenter converts raw session data into
        list of SessionViewModel instances.

        Business context:
        Session list view displays all sessions with computed
        properties like duration and effectiveness.

        Arrangement:
        Create mock storage with one active session.

        Action:
        Call presenter's get_sessions_list method.

        Assertion Strategy:
        Validates list length and session_id mapping.

        Testing Principle:
        Validates list transformation logic.
        """
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_sessions.return_value = {
            "s1": {
                "project": "proj1",
                "status": "active",
                "start_time": "2024-01-01T10:00:00Z",
            }
        }
        mock_storage.load_interactions.return_value = []

        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        sessions = presenter.get_sessions_list()
        assert len(sessions) == 1
        assert sessions[0].session_id == "s1"

    def test_get_roi_summary(self) -> None:
        """Verifies get_roi_summary returns ROIViewModel.

        Tests that presenter computes ROI metrics and returns
        properly structured view model.

        Business context:
        ROI summary shows investment return metrics on dashboard.
        Essential for justifying AI tool adoption.

        Arrangement:
        Create mock storage with empty data.

        Action:
        Call presenter's get_roi_summary method.

        Assertion Strategy:
        Validates return type is ROIViewModel.

        Testing Principle:
        Validates method returns correct view model type.
        """
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_sessions.return_value = {}
        mock_storage.load_interactions.return_value = []

        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        roi = presenter.get_roi_summary()
        assert isinstance(roi, ROIViewModel)

    def test_get_effectiveness(self) -> None:
        """Verifies get_effectiveness returns EffectivenessViewModel.

        Tests that presenter aggregates interaction ratings into
        effectiveness view model with distribution data.

        Business context:
        Effectiveness distribution shows AI output quality patterns.
        Helps identify if AI is meeting quality expectations.

        Arrangement:
        Create mock storage with two rated interactions.

        Action:
        Call presenter's get_effectiveness method.

        Assertion Strategy:
        Validates return type and interaction count.

        Testing Principle:
        Validates aggregation of effectiveness ratings.
        """
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_interactions.return_value = [
            {"effectiveness_rating": 5},
            {"effectiveness_rating": 4},
        ]

        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        eff = presenter.get_effectiveness()
        assert isinstance(eff, EffectivenessViewModel)
        assert eff.total_interactions == 2


class TestChartPresenter:
    """Tests for ChartPresenter class."""

    def test_creation(self) -> None:
        """Verifies ChartPresenter can be created with dependencies.

        Tests that ChartPresenter stores storage and statistics
        engine references correctly.

        Business context:
        ChartPresenter generates visualization images for dashboard.
        Requires storage for data and statistics for computations.

        Arrangement:
        Create mock storage and statistics engine.

        Action:
        Create ChartPresenter instance.

        Assertion Strategy:
        Validates dependencies are stored correctly.

        Testing Principle:
        Validates constructor dependency injection.
        """
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)
        assert presenter.storage == mock_storage
        assert presenter.statistics == stats

    @pytest.mark.skipif(not _has_matplotlib(), reason="matplotlib not installed")
    def test_render_effectiveness_chart(self) -> None:
        """Verifies render_effectiveness_chart returns valid PNG.

        Tests that effectiveness chart renders as valid PNG image
        with correct magic bytes.

        Business context:
        Effectiveness chart visualizes rating distribution.
        PNG format enables embedding in web dashboard.

        Arrangement:
        Create mock storage with rated interactions.

        Action:
        Call render_effectiveness_chart method.

        Assertion Strategy:
        Validates bytes type and PNG magic header.

        Testing Principle:
        Validates image generation with integration test.
        """
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_interactions.return_value = [
            {"effectiveness_rating": 5},
            {"effectiveness_rating": 4},
        ]

        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        png = presenter.render_effectiveness_chart()
        assert isinstance(png, bytes)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes

    @pytest.mark.skipif(not _has_matplotlib(), reason="matplotlib not installed")
    def test_render_roi_chart(self) -> None:
        """Verifies render_roi_chart returns valid PNG.

        Tests that ROI chart renders as valid PNG image
        even with empty session data.

        Business context:
        ROI chart visualizes return on investment metrics.
        Must handle empty data gracefully.

        Arrangement:
        Create mock storage with empty session data.

        Action:
        Call render_roi_chart method.

        Assertion Strategy:
        Validates bytes type and PNG magic header.

        Testing Principle:
        Validates chart renders with empty data.
        """
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_sessions.return_value = {}
        mock_storage.load_interactions.return_value = []

        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        png = presenter.render_roi_chart()
        assert isinstance(png, bytes)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.skipif(not _has_matplotlib(), reason="matplotlib not installed")
    def test_render_sessions_timeline(self) -> None:
        """Verifies render_sessions_timeline returns valid PNG.

        Tests that timeline chart renders as valid PNG image
        showing session distribution over time.

        Business context:
        Timeline chart shows session activity patterns.
        Helps identify usage trends and busy periods.

        Arrangement:
        Create mock storage with empty session data.

        Action:
        Call render_sessions_timeline method.

        Assertion Strategy:
        Validates bytes type for PNG output.

        Testing Principle:
        Validates timeline renders with empty data.
        """
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_sessions.return_value = {}

        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        png = presenter.render_sessions_timeline()
        assert isinstance(png, bytes)

    @pytest.mark.skipif(not _has_matplotlib(), reason="matplotlib not installed")
    def test_render_sessions_timeline_with_data(self) -> None:
        """Verifies render_sessions_timeline renders session bars.

        Tests that timeline chart shows sessions when data exists,
        with bars colored by status.

        Business context:
        Timeline chart visualizes session duration over time.
        Must handle actual session data correctly.

        Arrangement:
        Create mock storage with two sessions (completed and active).

        Action:
        Call render_sessions_timeline method.

        Assertion Strategy:
        Validates bytes type and PNG magic header for valid output.

        Testing Principle:
        Validates timeline with actual data.
        """
        from datetime import datetime, timedelta

        mock_storage = MagicMock(spec=StorageManager)
        base = datetime.now(UTC)
        mock_storage.load_sessions.return_value = {
            "s1": {
                "start_time": base.isoformat(),
                "end_time": (base + timedelta(hours=1)).isoformat(),
                "status": "completed",
            },
            "s2": {
                "start_time": (base + timedelta(hours=2)).isoformat(),
                "end_time": (base + timedelta(hours=3)).isoformat(),
                "status": "active",
            },
        }

        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        png = presenter.render_sessions_timeline()
        assert isinstance(png, bytes)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.skipif(not _has_matplotlib(), reason="matplotlib not installed")
    def test_render_sessions_timeline_skips_invalid_timestamps(self) -> None:
        """Verifies timeline skips sessions with invalid timestamps.

        Tests that sessions with unparseable timestamps are silently
        skipped rather than causing errors.

        Business context:
        Corrupted data should not break chart rendering.
        """
        from datetime import datetime, timedelta

        mock_storage = MagicMock(spec=StorageManager)
        base = datetime.now(UTC)
        mock_storage.load_sessions.return_value = {
            "s1": {
                "start_time": "invalid-timestamp",
                "end_time": "also-invalid",
                "status": "completed",
            },
            "s2": {
                "start_time": base.isoformat(),
                "end_time": (base + timedelta(hours=1)).isoformat(),
                "status": "active",
            },
        }

        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        # Should not raise
        png = presenter.render_sessions_timeline()
        assert isinstance(png, bytes)


class TestSessionViewModelStartTimeDisplay:
    """Tests for SessionViewModel.start_time_display property."""

    def test_start_time_display_valid(self) -> None:
        """Verifies start_time_display formats valid ISO timestamp.

        Tests that valid ISO timestamps are converted to HH:MM:SS format.
        """
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="active",
            duration_minutes=0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="2024-01-15T14:30:45+00:00",
            end_time=None,
        )
        assert vm.start_time_display == "14:30:45"

    def test_start_time_display_empty(self) -> None:
        """Verifies start_time_display handles empty string.

        Tests that empty start_time returns em-dash placeholder.
        """
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="active",
            duration_minutes=0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="",
            end_time=None,
        )
        assert vm.start_time_display == "—"

    def test_start_time_display_invalid(self) -> None:
        """Verifies start_time_display handles invalid timestamp.

        Tests that invalid timestamps return em-dash placeholder.
        """
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="active",
            duration_minutes=0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="not-a-valid-timestamp",
            end_time=None,
        )
        assert vm.start_time_display == "—"

    def test_start_time_display_with_z_suffix(self) -> None:
        """Verifies start_time_display handles Z timezone suffix.

        Tests that ISO timestamps with Z suffix are parsed correctly.
        """
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="active",
            duration_minutes=0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="2024-01-15T14:30:45Z",
            end_time=None,
        )
        assert vm.start_time_display == "14:30:45"


class TestSessionGapViewModel:
    """Tests for SessionGapViewModel properties."""

    def test_duration_display_minutes(self) -> None:
        """Verifies duration_display shows minutes for gaps < 60min."""
        from ai_session_tracker_mcp.presenters import SessionGapViewModel

        vm = SessionGapViewModel(
            from_session="s1",
            to_session="s2",
            duration_minutes=45.0,
            classification="normal",
        )
        assert vm.duration_display == "45m"

    def test_duration_display_hours(self) -> None:
        """Verifies duration_display shows hours for gaps >= 60min."""
        from ai_session_tracker_mcp.presenters import SessionGapViewModel

        vm = SessionGapViewModel(
            from_session="s1",
            to_session="s2",
            duration_minutes=120.0,
            classification="extended",
        )
        assert vm.duration_display == "2.0h"

    def test_classification_emoji_quick(self) -> None:
        """Verifies classification_emoji for quick gaps."""
        from ai_session_tracker_mcp.presenters import SessionGapViewModel

        vm = SessionGapViewModel(
            from_session="s1",
            to_session="s2",
            duration_minutes=3.0,
            classification="quick",
        )
        assert vm.classification_emoji == "⚡"

    def test_classification_emoji_long_break(self) -> None:
        """Verifies classification_emoji for long breaks."""
        from ai_session_tracker_mcp.presenters import SessionGapViewModel

        vm = SessionGapViewModel(
            from_session="s1",
            to_session="s2",
            duration_minutes=180.0,
            classification="long_break",
        )
        assert vm.classification_emoji == "🔴"

    def test_classification_emoji_unknown(self) -> None:
        """Verifies classification_emoji returns default for unknown types."""
        from ai_session_tracker_mcp.presenters import SessionGapViewModel

        vm = SessionGapViewModel(
            from_session="s1",
            to_session="s2",
            duration_minutes=30.0,
            classification="unknown_type",
        )
        assert vm.classification_emoji == "•"

    def test_classification_class(self) -> None:
        """Verifies classification_class returns proper CSS class."""
        from ai_session_tracker_mcp.presenters import SessionGapViewModel

        vm = SessionGapViewModel(
            from_session="s1",
            to_session="s2",
            duration_minutes=180.0,
            classification="long_break",
        )
        assert vm.classification_class == "gap-long-break"


class TestSessionGapsViewModel:
    """Tests for SessionGapsViewModel properties and methods."""

    def test_average_display_minutes(self) -> None:
        """Verifies average_display shows minutes for < 60min."""
        from ai_session_tracker_mcp.presenters import SessionGapsViewModel

        vm = SessionGapsViewModel(
            gaps=[],
            total_gaps=3,
            average_gap_minutes=30.0,
            by_classification={"normal": 3},
            friction_indicators=[],
        )
        assert vm.average_display == "30m"

    def test_average_display_hours(self) -> None:
        """Verifies average_display shows hours for >= 60min."""
        from ai_session_tracker_mcp.presenters import SessionGapsViewModel

        vm = SessionGapsViewModel(
            gaps=[],
            total_gaps=3,
            average_gap_minutes=90.0,
            by_classification={"extended": 3},
            friction_indicators=[],
        )
        assert vm.average_display == "1.5h"

    def test_has_friction_true(self) -> None:
        """Verifies has_friction returns True when indicators exist."""
        from ai_session_tracker_mcp.presenters import SessionGapsViewModel

        vm = SessionGapsViewModel(
            gaps=[],
            total_gaps=5,
            average_gap_minutes=60.0,
            by_classification={"long_break": 3},
            friction_indicators=["High frequency of long breaks"],
        )
        assert vm.has_friction is True

    def test_has_friction_false(self) -> None:
        """Verifies has_friction returns False when no indicators."""
        from ai_session_tracker_mcp.presenters import SessionGapsViewModel

        vm = SessionGapsViewModel(
            gaps=[],
            total_gaps=3,
            average_gap_minutes=15.0,
            by_classification={"quick": 3},
            friction_indicators=[],
        )
        assert vm.has_friction is False

    def test_classification_count_existing(self) -> None:
        """Verifies classification_count returns correct count for known type."""
        from ai_session_tracker_mcp.presenters import SessionGapsViewModel

        vm = SessionGapsViewModel(
            gaps=[],
            total_gaps=10,
            average_gap_minutes=30.0,
            by_classification={"quick": 3, "normal": 5, "extended": 2},
            friction_indicators=[],
        )
        assert vm.classification_count("quick") == 3
        assert vm.classification_count("normal") == 5
        assert vm.classification_count("extended") == 2

    def test_classification_count_missing(self) -> None:
        """Verifies classification_count returns 0 for unknown type."""
        from ai_session_tracker_mcp.presenters import SessionGapsViewModel

        vm = SessionGapsViewModel(
            gaps=[],
            total_gaps=3,
            average_gap_minutes=30.0,
            by_classification={"normal": 3},
            friction_indicators=[],
        )
        assert vm.classification_count("long_break") == 0
        assert vm.classification_count("unknown_type") == 0


class TestFormatDuration:
    """Tests for _format_duration helper function."""

    def test_format_duration_minutes(self) -> None:
        """Verifies _format_duration shows minutes for < 60."""
        from ai_session_tracker_mcp.presenters import _format_duration

        assert _format_duration(0) == "0m"
        assert _format_duration(15) == "15m"
        assert _format_duration(45.5) == "46m"
        assert _format_duration(59) == "59m"

    def test_format_duration_hours(self) -> None:
        """Verifies _format_duration shows hours for >= 60."""
        from ai_session_tracker_mcp.presenters import _format_duration

        assert _format_duration(60) == "1.0h"
        assert _format_duration(90) == "1.5h"
        assert _format_duration(120) == "2.0h"
        assert _format_duration(150) == "2.5h"


class TestStatusColors:
    """Tests for STATUS_COLORS constant."""

    def test_status_colors_contains_expected_keys(self) -> None:
        """Verifies STATUS_COLORS has all expected status colors."""
        from ai_session_tracker_mcp.presenters import STATUS_COLORS

        assert "completed" in STATUS_COLORS
        assert "active" in STATUS_COLORS
        assert "default" in STATUS_COLORS

    def test_status_colors_values_are_hex(self) -> None:
        """Verifies STATUS_COLORS values are valid hex color codes."""
        from ai_session_tracker_mcp.presenters import STATUS_COLORS

        for color in STATUS_COLORS.values():
            assert color.startswith("#")
            assert len(color) == 7  # #RRGGBB format


class TestEffectivenessColors:
    """Tests for EFFECTIVENESS_COLORS constant."""

    def test_effectiveness_colors_contains_ratings(self) -> None:
        """Verifies EFFECTIVENESS_COLORS has all rating levels 1-5."""
        from ai_session_tracker_mcp.presenters import EFFECTIVENESS_COLORS

        for rating in range(1, 6):
            assert rating in EFFECTIVENESS_COLORS

    def test_effectiveness_colors_values_are_hex(self) -> None:
        """Verifies EFFECTIVENESS_COLORS values are valid hex color codes."""
        from ai_session_tracker_mcp.presenters import EFFECTIVENESS_COLORS

        for color in EFFECTIVENESS_COLORS.values():
            assert color.startswith("#")
            assert len(color) == 7


class TestChartPresenterHelpers:
    """Tests for ChartPresenter helper methods."""

    def test_status_to_color_completed(self) -> None:
        """Verifies _status_to_color maps completed status."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        from ai_session_tracker_mcp.presenters import STATUS_COLORS

        assert presenter._status_to_color("completed") == STATUS_COLORS["completed"]

    def test_status_to_color_active(self) -> None:
        """Verifies _status_to_color maps active status."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        from ai_session_tracker_mcp.presenters import STATUS_COLORS

        assert presenter._status_to_color("active") == STATUS_COLORS["active"]

    def test_status_to_color_unknown(self) -> None:
        """Verifies _status_to_color returns default for unknown status."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        from ai_session_tracker_mcp.presenters import STATUS_COLORS

        assert presenter._status_to_color("unknown") == STATUS_COLORS["default"]
        assert presenter._status_to_color("abandoned") == STATUS_COLORS["default"]

    def test_parse_session_for_timeline_valid(self) -> None:
        """Verifies _parse_session_for_timeline extracts valid data."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        session = {
            "start_time": "2024-01-15T10:00:00Z",
            "end_time": "2024-01-15T11:00:00Z",
            "status": "completed",
        }
        result = presenter._parse_session_for_timeline(session)
        assert result is not None
        start_dt, duration, status = result
        assert status == "completed"
        assert duration == 60.0  # 1 hour

    def test_parse_session_for_timeline_no_start(self) -> None:
        """Verifies _parse_session_for_timeline returns None without start_time."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        session = {"end_time": "2024-01-15T11:00:00Z", "status": "completed"}
        result = presenter._parse_session_for_timeline(session)
        assert result is None

    def test_parse_session_for_timeline_invalid_time(self) -> None:
        """Verifies _parse_session_for_timeline returns None for invalid timestamp."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        session = {
            "start_time": "invalid-timestamp",
            "status": "completed",
        }
        result = presenter._parse_session_for_timeline(session)
        assert result is None


class TestDashboardPresenterHelpers:
    """Tests for DashboardPresenter helper methods."""

    def test_group_interactions_by_session_empty(self) -> None:
        """Verifies _group_interactions_by_session handles empty list."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        result = presenter._group_interactions_by_session([])
        assert result == {}

    def test_group_interactions_by_session_multiple(self) -> None:
        """Verifies _group_interactions_by_session groups correctly."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        interactions = [
            {"session_id": "s1", "effectiveness_rating": 5},
            {"session_id": "s2", "effectiveness_rating": 4},
            {"session_id": "s1", "effectiveness_rating": 3},
        ]
        result = presenter._group_interactions_by_session(interactions)
        assert len(result["s1"]) == 2
        assert len(result["s2"]) == 1

    def test_calculate_session_effectiveness_empty(self) -> None:
        """Verifies _calculate_session_effectiveness returns 0 for empty list."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        result = presenter._calculate_session_effectiveness([])
        assert result == 0.0

    def test_calculate_session_effectiveness_average(self) -> None:
        """Verifies _calculate_session_effectiveness computes correct average."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        interactions = [
            {"effectiveness_rating": 5},
            {"effectiveness_rating": 4},
            {"effectiveness_rating": 3},
        ]
        result = presenter._calculate_session_effectiveness(interactions)
        assert result == 4.0  # (5+4+3)/3
