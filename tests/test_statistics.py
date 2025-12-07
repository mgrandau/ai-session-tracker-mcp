"""Tests for statistics module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ai_session_tracker_mcp.config import Config
from ai_session_tracker_mcp.statistics import StatisticsEngine


@pytest.fixture
def engine() -> StatisticsEngine:
    """Create StatisticsEngine with default config."""
    return StatisticsEngine()


@pytest.fixture
def custom_engine() -> StatisticsEngine:
    """Create StatisticsEngine with custom rates."""
    return StatisticsEngine(human_hourly_rate=100.0, ai_monthly_cost=20.0)


class TestStatisticsEngineInit:
    """Tests for StatisticsEngine initialization."""

    def test_default_human_hourly_rate(self, engine: StatisticsEngine) -> None:
        """Uses Config default for human_hourly_rate."""
        assert engine.human_hourly_rate == Config.HUMAN_HOURLY_RATE

    def test_default_ai_monthly_cost(self, engine: StatisticsEngine) -> None:
        """Uses Config default for ai_monthly_cost."""
        assert engine.ai_monthly_cost == Config.AI_MONTHLY_COST

    def test_custom_human_hourly_rate(self, custom_engine: StatisticsEngine) -> None:
        """Uses custom human_hourly_rate."""
        assert custom_engine.human_hourly_rate == 100.0

    def test_custom_ai_monthly_cost(self, custom_engine: StatisticsEngine) -> None:
        """Uses custom ai_monthly_cost."""
        assert custom_engine.ai_monthly_cost == 20.0

    def test_calculates_ai_hourly_rate(self, engine: StatisticsEngine) -> None:
        """Calculates ai_hourly_rate from monthly cost."""
        expected = Config.AI_MONTHLY_COST / Config.WORKING_HOURS_PER_MONTH
        assert engine.ai_hourly_rate == expected


class TestSessionDurationCalculation:
    """Tests for calculate_session_duration_minutes."""

    def test_valid_duration(self, engine: StatisticsEngine) -> None:
        """Calculates duration for valid start/end times."""
        start = datetime.now(UTC)
        end = start + timedelta(hours=2)
        session = {
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }
        result = engine.calculate_session_duration_minutes(session)
        assert result == 120.0

    def test_missing_start_time(self, engine: StatisticsEngine) -> None:
        """Returns 0 when start_time missing."""
        session = {"end_time": datetime.now(UTC).isoformat()}
        result = engine.calculate_session_duration_minutes(session)
        assert result == 0.0

    def test_missing_end_time(self, engine: StatisticsEngine) -> None:
        """Returns 0 when end_time missing."""
        session = {"start_time": datetime.now(UTC).isoformat()}
        result = engine.calculate_session_duration_minutes(session)
        assert result == 0.0

    def test_empty_strings(self, engine: StatisticsEngine) -> None:
        """Returns 0 for empty string times."""
        session = {"start_time": "", "end_time": ""}
        result = engine.calculate_session_duration_minutes(session)
        assert result == 0.0

    def test_invalid_format(self, engine: StatisticsEngine) -> None:
        """Returns 0 for invalid time format."""
        session = {"start_time": "not-a-date", "end_time": "also-not-a-date"}
        result = engine.calculate_session_duration_minutes(session)
        assert result == 0.0

    def test_handles_z_suffix(self, engine: StatisticsEngine) -> None:
        """Handles Z suffix in ISO format."""
        session = {
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-01T01:30:00Z",
        }
        result = engine.calculate_session_duration_minutes(session)
        assert result == 90.0


class TestEffectivenessDistribution:
    """Tests for calculate_effectiveness_distribution."""

    def test_empty_interactions(self, engine: StatisticsEngine) -> None:
        """Returns zeroes for empty list."""
        result = engine.calculate_effectiveness_distribution([])
        assert result == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    def test_counts_each_rating(self, engine: StatisticsEngine) -> None:
        """Counts interactions by rating."""
        interactions = [
            {"effectiveness_rating": 5},
            {"effectiveness_rating": 5},
            {"effectiveness_rating": 3},
            {"effectiveness_rating": 1},
        ]
        result = engine.calculate_effectiveness_distribution(interactions)
        assert result[5] == 2
        assert result[3] == 1
        assert result[1] == 1
        assert result[4] == 0
        assert result[2] == 0

    def test_ignores_invalid_ratings(self, engine: StatisticsEngine) -> None:
        """Ignores ratings outside 1-5 range."""
        interactions = [
            {"effectiveness_rating": 0},
            {"effectiveness_rating": 6},
            {"effectiveness_rating": -1},
            {"effectiveness_rating": 3},
        ]
        result = engine.calculate_effectiveness_distribution(interactions)
        assert result[3] == 1
        assert sum(result.values()) == 1

    def test_handles_missing_rating(self, engine: StatisticsEngine) -> None:
        """Handles missing effectiveness_rating field."""
        interactions = [{"prompt": "test"}]
        result = engine.calculate_effectiveness_distribution(interactions)
        assert sum(result.values()) == 0


class TestAverageEffectiveness:
    """Tests for calculate_average_effectiveness."""

    def test_empty_interactions(self, engine: StatisticsEngine) -> None:
        """Returns 0 for empty list."""
        result = engine.calculate_average_effectiveness([])
        assert result == 0.0

    def test_calculates_average(self, engine: StatisticsEngine) -> None:
        """Calculates correct average."""
        interactions = [
            {"effectiveness_rating": 5},
            {"effectiveness_rating": 3},
            {"effectiveness_rating": 4},
        ]
        result = engine.calculate_average_effectiveness(interactions)
        assert result == 4.0

    def test_handles_missing_rating(self, engine: StatisticsEngine) -> None:
        """Treats missing rating as 0."""
        interactions = [
            {"effectiveness_rating": 4},
            {"prompt": "no rating"},
        ]
        result = engine.calculate_average_effectiveness(interactions)
        assert result == 2.0


class TestIssueSummary:
    """Tests for calculate_issue_summary."""

    def test_empty_issues(self, engine: StatisticsEngine) -> None:
        """Returns zeroes for empty list."""
        result = engine.calculate_issue_summary([])
        assert result["total"] == 0
        assert result["by_type"] == {}
        assert result["by_severity"] == {}

    def test_counts_by_type(self, engine: StatisticsEngine) -> None:
        """Counts issues by type."""
        issues = [
            {"issue_type": "hallucination", "severity": "high"},
            {"issue_type": "hallucination", "severity": "low"},
            {"issue_type": "incorrect_output", "severity": "medium"},
        ]
        result = engine.calculate_issue_summary(issues)
        assert result["by_type"]["hallucination"] == 2
        assert result["by_type"]["incorrect_output"] == 1

    def test_counts_by_severity(self, engine: StatisticsEngine) -> None:
        """Counts issues by severity."""
        issues = [
            {"issue_type": "a", "severity": "high"},
            {"issue_type": "b", "severity": "high"},
            {"issue_type": "c", "severity": "low"},
        ]
        result = engine.calculate_issue_summary(issues)
        assert result["by_severity"]["high"] == 2
        assert result["by_severity"]["low"] == 1

    def test_total_count(self, engine: StatisticsEngine) -> None:
        """Returns total issue count."""
        issues = [{"issue_type": "a", "severity": "low"}] * 5
        result = engine.calculate_issue_summary(issues)
        assert result["total"] == 5

    def test_handles_missing_fields(self, engine: StatisticsEngine) -> None:
        """Handles missing issue_type and severity."""
        issues = [{"description": "something"}]
        result = engine.calculate_issue_summary(issues)
        assert result["total"] == 1
        assert result["by_type"]["unknown"] == 1
        assert result["by_severity"]["unknown"] == 1


class TestCodeMetricsSummary:
    """Tests for calculate_code_metrics_summary."""

    def test_empty_sessions(self, engine: StatisticsEngine) -> None:
        """Returns zeroes for empty sessions."""
        result = engine.calculate_code_metrics_summary({})
        assert result["total_functions"] == 0
        assert result["avg_complexity"] == 0
        assert result["avg_doc_score"] == 0

    def test_sessions_without_code_metrics(self, engine: StatisticsEngine) -> None:
        """Handles sessions without code_metrics field."""
        sessions = {"s1": {"name": "test"}}
        result = engine.calculate_code_metrics_summary(sessions)
        assert result["total_functions"] == 0

    def test_aggregates_metrics(self, engine: StatisticsEngine) -> None:
        """Aggregates metrics across sessions."""
        sessions = {
            "s1": {
                "code_metrics": [
                    {
                        "functions": [
                            {
                                "context": {"final_complexity": 5},
                                "documentation": {"quality_score": 80},
                                "value_metrics": {"effort_score": 10.0},
                                "ai_contribution": {"lines_added": 20, "lines_modified": 5},
                            },
                            {
                                "context": {"final_complexity": 3},
                                "documentation": {"quality_score": 60},
                                "value_metrics": {"effort_score": 5.0},
                                "ai_contribution": {"lines_added": 10, "lines_modified": 2},
                            },
                        ]
                    }
                ]
            }
        }
        result = engine.calculate_code_metrics_summary(sessions)

        assert result["total_functions"] == 2
        assert result["total_lines_added"] == 30
        assert result["total_lines_modified"] == 7
        assert result["avg_complexity"] == 4.0
        assert result["avg_doc_score"] == 70.0
        assert result["total_effort_score"] == 15.0


class TestROIMetrics:
    """Tests for calculate_roi_metrics."""

    def _make_session(
        self,
        session_id: str,
        task_type: str = "code_generation",
        status: str = "completed",
        duration_minutes: int = 60,
    ) -> dict[str, Any]:
        """Helper to create session dict."""
        start = datetime.now(UTC)
        end = start + timedelta(minutes=duration_minutes) if status == "completed" else None
        return {
            "id": session_id,
            "task_type": task_type,
            "status": status,
            "start_time": start.isoformat(),
            "end_time": end.isoformat() if end else None,
        }

    def test_empty_data(self, engine: StatisticsEngine) -> None:
        """Returns zeroes for empty data."""
        result = engine.calculate_roi_metrics({}, [])

        assert result["time_metrics"]["total_ai_minutes"] == 0
        assert result["time_metrics"]["completed_sessions"] == 0
        assert result["cost_metrics"]["cost_saved"] == 0

    def test_excludes_human_review_sessions(self, engine: StatisticsEngine) -> None:
        """Excludes human_review from productive time."""
        sessions = {
            "s1": self._make_session("s1", "code_generation", "completed", 60),
            "s2": self._make_session("s2", "human_review", "completed", 60),
        }
        result = engine.calculate_roi_metrics(sessions, [])

        # Only s1 should count (60 minutes)
        assert result["time_metrics"]["total_ai_minutes"] == pytest.approx(60.0, abs=0.1)
        assert result["time_metrics"]["completed_sessions"] == 1

    def test_excludes_active_sessions(self, engine: StatisticsEngine) -> None:
        """Excludes active (non-completed) sessions."""
        sessions = {
            "s1": self._make_session("s1", "code_generation", "completed", 60),
            "s2": self._make_session("s2", "code_generation", "active", 60),
        }
        result = engine.calculate_roi_metrics(sessions, [])

        assert result["time_metrics"]["completed_sessions"] == 1

    def test_calculates_human_baseline(self, engine: StatisticsEngine) -> None:
        """Estimates human baseline as 3x AI time."""
        sessions = {
            "s1": self._make_session("s1", "code_generation", "completed", 60),
        }
        result = engine.calculate_roi_metrics(sessions, [])

        ai_hours = 1.0  # 60 minutes
        expected_human_hours = ai_hours * 3.0
        assert result["time_metrics"]["estimated_human_hours"] == pytest.approx(
            expected_human_hours, abs=0.1
        )

    def test_calculates_cost_saved(self, engine: StatisticsEngine) -> None:
        """Calculates cost savings correctly."""
        sessions = {
            "s1": self._make_session("s1", "code_generation", "completed", 60),
        }
        result = engine.calculate_roi_metrics(sessions, [])

        # AI time: 1 hour
        # Human baseline: 3 hours
        # Human cost: 3 * $130 = $390
        # AI subscription: 1 * $0.25 = $0.25
        # Oversight: 0.2 * 1 * $130 = $26
        # Total AI cost: $26.25
        # Savings: $390 - $26.25 = $363.75

        assert result["cost_metrics"]["cost_saved"] > 0

    def test_calculates_roi_percentage(self, engine: StatisticsEngine) -> None:
        """Calculates ROI percentage."""
        sessions = {
            "s1": self._make_session("s1", "code_generation", "completed", 60),
        }
        result = engine.calculate_roi_metrics(sessions, [])

        assert result["cost_metrics"]["roi_percentage"] > 0

    def test_includes_productivity_metrics(self, engine: StatisticsEngine) -> None:
        """Includes productivity metrics from interactions."""
        sessions = {
            "s1": self._make_session("s1", "code_generation", "completed", 60),
        }
        interactions = [
            {"effectiveness_rating": 5},
            {"effectiveness_rating": 3},
        ]
        result = engine.calculate_roi_metrics(sessions, interactions)

        assert result["productivity_metrics"]["total_interactions"] == 2
        assert result["productivity_metrics"]["average_effectiveness"] == 4.0
        assert result["productivity_metrics"]["interactions_per_session"] == 2.0

    def test_includes_config_values(self, engine: StatisticsEngine) -> None:
        """Includes config values in result."""
        result = engine.calculate_roi_metrics({}, [])

        assert "config" in result
        assert result["config"]["human_hourly_rate"] == engine.human_hourly_rate
        assert result["config"]["ai_monthly_cost"] == engine.ai_monthly_cost


class TestSummaryReport:
    """Tests for generate_summary_report."""

    def test_returns_string(self, engine: StatisticsEngine) -> None:
        """Returns a string."""
        result = engine.generate_summary_report({}, [], [])
        assert isinstance(result, str)

    def test_includes_headers(self, engine: StatisticsEngine) -> None:
        """Includes section headers."""
        result = engine.generate_summary_report({}, [], [])

        assert "SESSION SUMMARY" in result
        assert "ROI METRICS" in result
        assert "EFFECTIVENESS DISTRIBUTION" in result
        assert "ISSUES SUMMARY" in result
        assert "CODE METRICS" in result

    def test_includes_session_count(self, engine: StatisticsEngine) -> None:
        """Includes session count."""
        sessions = {"s1": {}, "s2": {}}
        result = engine.generate_summary_report(sessions, [], [])

        assert "Total sessions: 2" in result

    def test_includes_effectiveness_stars(self, engine: StatisticsEngine) -> None:
        """Includes star ratings."""
        interactions = [{"effectiveness_rating": 5}]
        result = engine.generate_summary_report({}, interactions, [])

        assert "★★★★★: 1" in result

    def test_includes_issue_counts(self, engine: StatisticsEngine) -> None:
        """Includes issue counts by severity."""
        issues = [
            {"issue_type": "test", "severity": "high"},
            {"issue_type": "test", "severity": "high"},
        ]
        result = engine.generate_summary_report({}, [], issues)

        assert "High: 2" in result

    def test_formats_currency(self, engine: StatisticsEngine) -> None:
        """Formats currency values."""
        start = datetime.now(UTC)
        end = start + timedelta(hours=1)
        sessions = {
            "s1": {
                "task_type": "code_generation",
                "status": "completed",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }
        }
        result = engine.generate_summary_report(sessions, [], [])

        assert "$" in result
