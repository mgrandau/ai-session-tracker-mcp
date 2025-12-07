"""Tests for presenters module."""

from __future__ import annotations

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
    """Check if matplotlib is available."""
    try:
        import matplotlib  # noqa: F401

        return True
    except ImportError:
        return False


class TestSessionViewModel:
    """Tests for SessionViewModel dataclass."""

    def test_creation(self) -> None:
        """SessionViewModel can be created with all fields."""
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
        """duration_display shows minutes for < 60 min."""
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
        """duration_display shows hours for >= 60 min."""
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
        """effectiveness_stars returns star representation."""
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
        """effectiveness_stars handles zero rating."""
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

    def test_status_class_active(self) -> None:
        """status_class returns correct CSS class for active."""
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
        assert vm.status_class == "status-active"

    def test_status_class_completed(self) -> None:
        """status_class returns correct CSS class for completed."""
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="completed",
            duration_minutes=0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="",
            end_time=None,
        )
        assert vm.status_class == "status-completed"

    def test_status_class_abandoned(self) -> None:
        """status_class returns correct CSS class for abandoned."""
        vm = SessionViewModel(
            session_id="x",
            project="p",
            status="abandoned",
            duration_minutes=0,
            interaction_count=0,
            effectiveness_avg=0,
            start_time="",
            end_time=None,
        )
        assert vm.status_class == "status-abandoned"


class TestROIViewModel:
    """Tests for ROIViewModel dataclass."""

    def test_creation(self) -> None:
        """ROIViewModel can be created."""
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
        """time_saved_display shows minutes for < 1 hour."""
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
        """time_saved_display shows hours for >= 1 hour."""
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
        """cost_saved_display formats currency."""
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

    def test_roi_class_excellent(self) -> None:
        """roi_class returns excellent for >= 50%."""
        vm = ROIViewModel(
            total_sessions=0,
            completed_sessions=0,
            total_ai_hours=0,
            estimated_human_hours=0,
            time_saved_hours=0,
            human_baseline_cost=0,
            total_ai_cost=0,
            cost_saved=0,
            roi_percentage=60.0,
        )
        assert vm.roi_class == "roi-excellent"

    def test_roi_class_good(self) -> None:
        """roi_class returns good for >= 25%."""
        vm = ROIViewModel(
            total_sessions=0,
            completed_sessions=0,
            total_ai_hours=0,
            estimated_human_hours=0,
            time_saved_hours=0,
            human_baseline_cost=0,
            total_ai_cost=0,
            cost_saved=0,
            roi_percentage=30.0,
        )
        assert vm.roi_class == "roi-good"

    def test_roi_class_neutral(self) -> None:
        """roi_class returns neutral for >= 0%."""
        vm = ROIViewModel(
            total_sessions=0,
            completed_sessions=0,
            total_ai_hours=0,
            estimated_human_hours=0,
            time_saved_hours=0,
            human_baseline_cost=0,
            total_ai_cost=0,
            cost_saved=0,
            roi_percentage=10.0,
        )
        assert vm.roi_class == "roi-neutral"

    def test_roi_class_negative(self) -> None:
        """roi_class returns negative for < 0%."""
        vm = ROIViewModel(
            total_sessions=0,
            completed_sessions=0,
            total_ai_hours=0,
            estimated_human_hours=0,
            time_saved_hours=0,
            human_baseline_cost=0,
            total_ai_cost=0,
            cost_saved=0,
            roi_percentage=-10.0,
        )
        assert vm.roi_class == "roi-negative"


class TestEffectivenessViewModel:
    """Tests for EffectivenessViewModel dataclass."""

    def test_creation(self) -> None:
        """EffectivenessViewModel can be created."""
        vm = EffectivenessViewModel(
            distribution={1: 2, 2: 3, 3: 10, 4: 15, 5: 20},
            average=4.0,
            total_interactions=50,
        )
        assert vm.average == 4.0
        assert vm.total_interactions == 50

    def test_bar_width(self) -> None:
        """bar_width calculates percentage correctly."""
        vm = EffectivenessViewModel(
            distribution={5: 10, 4: 10, 3: 0, 2: 0, 1: 0},
            average=4.5,
            total_interactions=20,
        )
        assert vm.bar_width(5) == 50
        assert vm.bar_width(4) == 50
        assert vm.bar_width(3) == 0

    def test_bar_width_zero_total(self) -> None:
        """bar_width returns 0 when no interactions."""
        vm = EffectivenessViewModel(distribution={}, average=0, total_interactions=0)
        assert vm.bar_width(5) == 0


class TestIssueViewModel:
    """Tests for IssueViewModel dataclass."""

    def test_creation(self) -> None:
        """IssueViewModel can be created."""
        vm = IssueViewModel(
            total=5,
            by_type={"hallucination": 2, "incorrect_output": 3},
            by_severity={"critical": 1, "high": 2, "medium": 2},
        )
        assert vm.total == 5

    def test_severity_count(self) -> None:
        """severity_count returns correct count."""
        vm = IssueViewModel(
            total=5,
            by_type={},
            by_severity={"critical": 3, "high": 2},
        )
        assert vm.severity_count("critical") == 3
        assert vm.severity_count("low") == 0

    def test_critical_count(self) -> None:
        """critical_count property works."""
        vm = IssueViewModel(
            total=5,
            by_type={},
            by_severity={"critical": 2},
        )
        assert vm.critical_count == 2

    def test_high_count(self) -> None:
        """high_count property works."""
        vm = IssueViewModel(
            total=5,
            by_type={},
            by_severity={"high": 4},
        )
        assert vm.high_count == 4


class TestDashboardOverview:
    """Tests for DashboardOverview dataclass."""

    def test_creation_defaults(self) -> None:
        """DashboardOverview has sensible defaults."""
        overview = DashboardOverview()
        assert overview.sessions == []
        assert overview.roi is None
        assert overview.effectiveness is None
        assert overview.issues is None
        assert overview.report_text == ""


class TestDashboardPresenter:
    """Tests for DashboardPresenter class."""

    def test_get_overview(self) -> None:
        """get_overview returns DashboardOverview."""
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
        """get_overview processes session data correctly."""
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
        """get_sessions_list returns session view models."""
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
        """get_roi_summary returns ROIViewModel."""
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_sessions.return_value = {}
        mock_storage.load_interactions.return_value = []

        stats = StatisticsEngine()
        presenter = DashboardPresenter(mock_storage, stats)

        roi = presenter.get_roi_summary()
        assert isinstance(roi, ROIViewModel)

    def test_get_effectiveness(self) -> None:
        """get_effectiveness returns EffectivenessViewModel."""
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
        """ChartPresenter can be created."""
        mock_storage = MagicMock(spec=StorageManager)
        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)
        assert presenter.storage == mock_storage
        assert presenter.statistics == stats

    @pytest.mark.skipif(not _has_matplotlib(), reason="matplotlib not installed")
    def test_render_effectiveness_chart(self) -> None:
        """render_effectiveness_chart returns PNG bytes."""
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
        """render_roi_chart returns PNG bytes."""
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
        """render_sessions_timeline returns PNG bytes."""
        mock_storage = MagicMock(spec=StorageManager)
        mock_storage.load_sessions.return_value = {}

        stats = StatisticsEngine()
        presenter = ChartPresenter(mock_storage, stats)

        png = presenter.render_sessions_timeline()
        assert isinstance(png, bytes)
