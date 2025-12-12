"""Tests for statistics module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ai_session_tracker_mcp.config import Config
from ai_session_tracker_mcp.statistics import StatisticsEngine


@pytest.fixture
def engine() -> StatisticsEngine:
    """Create StatisticsEngine with default configuration.

    Provides a StatisticsEngine instance using Config defaults for
    human hourly rate and AI monthly cost. Standard fixture for
    testing calculation methods.

    Business context:
    Default config represents typical enterprise settings. Most tests
    use these values to verify core calculation logic.

    Args:
        No arguments required for this fixture.

    Raises:
        No exceptions raised by this fixture.

    Returns:
        StatisticsEngine: Instance configured with Config.HUMAN_HOURLY_RATE
        ($130/hr) and Config.AI_MONTHLY_COST ($40/mo).

    Example:
        def test_calc(engine):
            result = engine.calculate_roi_metrics(sessions, interactions)
    """
    return StatisticsEngine()


@pytest.fixture
def custom_engine() -> StatisticsEngine:
    """Create StatisticsEngine with custom rate configuration.

    Provides a StatisticsEngine with explicit rate values for testing
    configuration override behavior and custom rate calculations.

    Business context:
    Organizations have varying rates. Tests must verify the engine
    respects custom configurations for accurate ROI calculations.

    Args:
        No arguments required for this fixture.

    Raises:
        No exceptions raised by this fixture.

    Returns:
        StatisticsEngine: Instance with human_hourly_rate=$100 and
        ai_monthly_cost=$20, different from defaults for isolation.

    Example:
        def test_custom(custom_engine):
            assert custom_engine.human_hourly_rate == 100.0
    """
    return StatisticsEngine(human_hourly_rate=100.0, ai_monthly_cost=20.0)


class TestStatisticsEngineInit:
    """Test suite for StatisticsEngine initialization.

    Categories:
    1. Default Configuration - Uses Config values (3 tests)
    2. Custom Configuration - Respects overrides (2 tests)

    Total: 5 tests verifying initialization behavior.
    """

    def test_default_human_hourly_rate(self, engine: StatisticsEngine) -> None:
        """Verifies engine uses Config default for human hourly rate.

        Tests that the default constructor pulls rate from Config,
        ensuring consistent defaults across the system.

        Business context:
        Human hourly rate is critical for ROI calculations. Default
        should match the centralized Config value.

        Arrangement:
        Engine created via default fixture (no arguments).

        Action:
        Access human_hourly_rate property.

        Assertion Strategy:
        Validates value equals Config.HUMAN_HOURLY_RATE constant.
        """
        assert engine.human_hourly_rate == Config.HUMAN_HOURLY_RATE

    def test_default_ai_monthly_cost(self, engine: StatisticsEngine) -> None:
        """Verifies engine uses Config default for AI monthly cost.

        Tests that the default constructor pulls cost from Config,
        ensuring ROI calculations use consistent base values.

        Business context:
        AI subscription cost affects ROI calculations. Default should
        match Config for reproducible analytics.

        Arrangement:
        Engine created via default fixture.

        Action:
        Access ai_monthly_cost property.

        Assertion Strategy:
        Validates value equals Config.AI_MONTHLY_COST constant.
        """
        assert engine.ai_monthly_cost == Config.AI_MONTHLY_COST

    def test_custom_human_hourly_rate(self, custom_engine: StatisticsEngine) -> None:
        """Verifies engine respects custom human hourly rate.

        Tests that constructor arguments override Config defaults,
        enabling organization-specific rate configuration.

        Business context:
        Enterprises have varying developer costs. Custom rates
        enable accurate ROI for specific contexts.

        Arrangement:
        Engine created with human_hourly_rate=100.0.

        Action:
        Access human_hourly_rate property.

        Assertion Strategy:
        Validates value equals the custom 100.0 rate.
        """
        assert custom_engine.human_hourly_rate == 100.0

    def test_custom_ai_monthly_cost(self, custom_engine: StatisticsEngine) -> None:
        """Verifies engine respects custom AI monthly cost.

        Tests that constructor arguments override Config defaults
        for AI subscription cost.

        Business context:
        Different AI plans have different costs. Custom cost
        enables accurate ROI for specific subscriptions.

        Arrangement:
        Engine created with ai_monthly_cost=20.0.

        Action:
        Access ai_monthly_cost property.

        Assertion Strategy:
        Validates value equals the custom 20.0 cost.
        """
        assert custom_engine.ai_monthly_cost == 20.0

    def test_calculates_ai_hourly_rate(self, engine: StatisticsEngine) -> None:
        """Verifies engine calculates AI hourly rate from monthly cost.

        Tests the derived ai_hourly_rate property that converts monthly
        subscription to hourly cost for comparison.

        Business context:
        ROI calculations need hourly rates for comparison. Converting
        monthly AI cost to hourly enables apples-to-apples comparison.

        Arrangement:
        Engine with default monthly cost and working hours.

        Action:
        Access ai_hourly_rate property.

        Assertion Strategy:
        Validates calculation: monthly_cost / working_hours_per_month.
        """
        expected = Config.AI_MONTHLY_COST / Config.WORKING_HOURS_PER_MONTH
        assert engine.ai_hourly_rate == expected


class TestSessionDurationCalculation:
    """Test suite for calculate_session_duration_minutes method.

    Categories:
    1. Valid Calculations - Correct duration from timestamps (2 tests)
    2. Missing Fields - Handle missing start/end times (2 tests)
    3. Invalid Data - Handle empty strings and bad formats (2 tests)

    Total: 6 tests covering duration calculation edge cases.
    """

    def test_valid_duration(self, engine: StatisticsEngine) -> None:
        """Verifies correct duration calculation for valid timestamps.

        Tests the core duration calculation with properly formatted
        ISO timestamps that have a known time difference.

        Business context:
        Accurate duration is essential for ROI calculations. Session
        time directly impacts cost savings estimates.

        Arrangement:
        Create session with start and end times 2 hours apart.

        Action:
        Call calculate_session_duration_minutes.

        Assertion Strategy:
        Validates returned minutes equals 120 (2 hours).
        """
        start = datetime.now(UTC)
        end = start + timedelta(hours=2)
        session = {
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }
        result = engine.calculate_session_duration_minutes(session)
        assert result == 120.0

    def test_missing_start_time(self, engine: StatisticsEngine) -> None:
        """Verifies zero duration when start_time is missing.

        Tests graceful handling of incomplete session data where
        start_time was not recorded.

        Business context:
        Data corruption or partial sessions may lack start times.
        Zero duration prevents NaN in aggregate calculations.

        Arrangement:
        Create session with only end_time field.

        Action:
        Call calculate_session_duration_minutes.

        Assertion Strategy:
        Validates 0.0 returned rather than error or NaN.
        """
        session = {"end_time": datetime.now(UTC).isoformat()}
        result = engine.calculate_session_duration_minutes(session)
        assert result == 0.0

    def test_missing_end_time(self, engine: StatisticsEngine) -> None:
        """Verifies zero duration when end_time is missing.

        Tests graceful handling of active sessions that haven't
        been ended yet (end_time not set).

        Business context:
        Active sessions have no end_time. ROI should only count
        completed sessions with known durations.

        Arrangement:
        Create session with only start_time field.

        Action:
        Call calculate_session_duration_minutes.

        Assertion Strategy:
        Validates 0.0 returned for incomplete sessions.
        """
        session = {"start_time": datetime.now(UTC).isoformat()}
        result = engine.calculate_session_duration_minutes(session)
        assert result == 0.0

    def test_empty_strings(self, engine: StatisticsEngine) -> None:
        """Verifies zero duration for empty string timestamps.

        Tests handling of placeholder empty strings that may appear
        in corrupted or manually edited data.

        Business context:
        JSON files may contain empty strings instead of null.
        Engine must handle this gracefully.

        Arrangement:
        Create session with empty string timestamps.

        Action:
        Call calculate_session_duration_minutes.

        Assertion Strategy:
        Validates 0.0 returned rather than parse error.
        """
        session = {"start_time": "", "end_time": ""}
        result = engine.calculate_session_duration_minutes(session)
        assert result == 0.0

    def test_invalid_format(self, engine: StatisticsEngine) -> None:
        """Verifies zero duration for unparseable timestamp formats.

        Tests handling of malformed timestamps that can't be parsed
        as ISO format dates.

        Business context:
        Data corruption may produce garbage timestamps. Engine must
        not crash on invalid input.

        Arrangement:
        Create session with invalid timestamp strings.

        Action:
        Call calculate_session_duration_minutes.

        Assertion Strategy:
        Validates 0.0 returned rather than ValueError exception.
        """
        session = {"start_time": "not-a-date", "end_time": "also-not-a-date"}
        result = engine.calculate_session_duration_minutes(session)
        assert result == 0.0

    def test_handles_z_suffix(self, engine: StatisticsEngine) -> None:
        """Verifies Z suffix UTC timestamps are parsed correctly.

        Tests handling of ISO format with 'Z' suffix commonly used
        in JavaScript and web APIs.

        Business context:
        Different systems format UTC differently. 'Z' suffix is
        common and must be supported for interoperability.

        Arrangement:
        Create session with Z-suffix timestamps 90 minutes apart.

        Action:
        Call calculate_session_duration_minutes.

        Assertion Strategy:
        Validates 90 minutes returned, confirming Z is parsed.
        """
        session = {
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-01T01:30:00Z",
        }
        result = engine.calculate_session_duration_minutes(session)
        assert result == 90.0


class TestEffectivenessDistribution:
    """Test suite for calculate_effectiveness_distribution method.

    Categories:
    1. Empty State - Handle no interactions (1 test)
    2. Counting Logic - Proper rating aggregation (1 test)
    3. Edge Cases - Invalid ratings, missing fields (2 tests)

    Total: 4 tests covering effectiveness distribution calculation.
    """

    def test_empty_interactions(self, engine: StatisticsEngine) -> None:
        """Verifies zero counts for empty interaction list.

        Tests that empty input produces a valid distribution dict
        with all ratings at zero count.

        Business context:
        New projects have no interactions. Dashboard must display
        valid empty distribution without errors.

        Arrangement:
        Empty interaction list.

        Action:
        Call calculate_effectiveness_distribution.

        Assertion Strategy:
        Validates dict with keys 1-5 all having value 0.
        """
        result = engine.calculate_effectiveness_distribution([])
        assert result == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    def test_counts_each_rating(self, engine: StatisticsEngine) -> None:
        """Verifies correct counting of interactions by rating.

        Tests that each rating level is counted independently and
        the distribution accurately reflects input data.

        Business context:
        Effectiveness distribution drives the bar chart. Accurate
        counting is essential for meaningful visualization.

        Arrangement:
        Four interactions: two 5-star, one 3-star, one 1-star.

        Action:
        Call calculate_effectiveness_distribution.

        Assertion Strategy:
        Validates each rating count matches expected values,
        including zero counts for unused ratings.
        """
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
        """Verifies ratings outside 1-5 range are ignored.

        Tests that invalid ratings (0, 6, negative) don't corrupt
        the distribution or cause errors.

        Business context:
        Data validation may fail allowing bad ratings. Distribution
        must be robust against out-of-range values.

        Arrangement:
        Four interactions: three invalid (0, 6, -1), one valid (3).

        Action:
        Call calculate_effectiveness_distribution.

        Assertion Strategy:
        Validates only the valid rating is counted, total is 1.
        """
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
        """Verifies interactions without rating field are skipped.

        Tests graceful handling of malformed interaction records
        that don't have the effectiveness_rating field.

        Business context:
        Legacy or corrupted data may lack rating field. Engine
        must not crash on incomplete records.

        Arrangement:
        One interaction with only prompt field, no rating.

        Action:
        Call calculate_effectiveness_distribution.

        Assertion Strategy:
        Validates zero total count, confirming record was skipped.
        """
        interactions = [{"prompt": "test"}]
        result = engine.calculate_effectiveness_distribution(interactions)
        assert sum(result.values()) == 0


class TestAverageEffectiveness:
    """Test suite for calculate_average_effectiveness method.

    Categories:
    1. Empty State - Handle no interactions (1 test)
    2. Calculation Logic - Correct averaging (1 test)
    3. Missing Data - Handle missing rating field (1 test)

    Total: 3 tests covering average effectiveness calculation.
    """

    def test_empty_interactions(self, engine: StatisticsEngine) -> None:
        """Verifies zero average for empty interaction list.

        Tests that empty input returns 0.0 rather than NaN or error
        from division by zero.

        Business context:
        New sessions have no interactions yet. Average must be
        defined and displayable.

        Arrangement:
        Empty interaction list.

        Action:
        Call calculate_average_effectiveness.

        Assertion Strategy:
        Validates 0.0 returned as safe default.
        """
        result = engine.calculate_average_effectiveness([])
        assert result == 0.0

    def test_calculates_average(self, engine: StatisticsEngine) -> None:
        """Verifies correct average calculation across ratings.

        Tests the arithmetic mean calculation with known values
        to confirm accuracy.

        Business context:
        Average effectiveness is a key session metric. Accurate
        calculation is essential for session summaries.

        Arrangement:
        Three interactions with ratings 5, 3, 4 (sum=12, avg=4).

        Action:
        Call calculate_average_effectiveness.

        Assertion Strategy:
        Validates 4.0 returned as arithmetic mean.
        """
        interactions = [
            {"effectiveness_rating": 5},
            {"effectiveness_rating": 3},
            {"effectiveness_rating": 4},
        ]
        result = engine.calculate_average_effectiveness(interactions)
        assert result == 4.0

    def test_handles_missing_rating(self, engine: StatisticsEngine) -> None:
        """Verifies missing ratings are treated as zero in average.

        Tests that interactions without rating field contribute
        zero to the average, lowering overall effectiveness.

        Business context:
        Conservative counting ensures missing data doesn't inflate
        effectiveness scores artificially.

        Arrangement:
        Two interactions: one with rating 4, one without rating.

        Action:
        Call calculate_average_effectiveness.

        Assertion Strategy:
        Validates 2.0 returned (4+0)/2, confirming zero treatment.
        """
        interactions = [
            {"effectiveness_rating": 4},
            {"prompt": "no rating"},
        ]
        result = engine.calculate_average_effectiveness(interactions)
        assert result == 2.0


class TestIssueSummary:
    """Test suite for calculate_issue_summary method.

    Categories:
    1. Empty State - Handle no issues (1 test)
    2. Aggregation Logic - Count by type and severity (3 tests)
    3. Missing Data - Handle missing fields (1 test)

    Total: 5 tests covering issue summary calculation.
    """

    def test_empty_issues(self, engine: StatisticsEngine) -> None:
        """Verifies empty summary structure for no issues.

        Tests that empty input produces valid summary dict with
        zero total and empty type/severity dicts.

        Business context:
        Clean sessions have no issues. Summary must be well-formed
        for dashboard display.

        Arrangement:
        Empty issues list.

        Action:
        Call calculate_issue_summary.

        Assertion Strategy:
        Validates total=0 and empty by_type, by_severity dicts.
        """
        result = engine.calculate_issue_summary([])
        assert result["total"] == 0
        assert result["by_type"] == {}
        assert result["by_severity"] == {}

    def test_counts_by_type(self, engine: StatisticsEngine) -> None:
        """Verifies correct counting of issues by type.

        Tests that issues are properly grouped and counted by their
        issue_type field.

        Business context:
        Type breakdown helps identify recurring AI failure patterns
        (hallucination, incorrect output, etc.).

        Arrangement:
        Three issues: two hallucination, one incorrect_output.

        Action:
        Call calculate_issue_summary.

        Assertion Strategy:
        Validates by_type counts match expected grouping.
        """
        issues = [
            {"issue_type": "hallucination", "severity": "high"},
            {"issue_type": "hallucination", "severity": "low"},
            {"issue_type": "incorrect_output", "severity": "medium"},
        ]
        result = engine.calculate_issue_summary(issues)
        assert result["by_type"]["hallucination"] == 2
        assert result["by_type"]["incorrect_output"] == 1

    def test_counts_by_severity(self, engine: StatisticsEngine) -> None:
        """Verifies correct counting of issues by severity.

        Tests that issues are properly grouped and counted by their
        severity field.

        Business context:
        Severity breakdown helps prioritize issue resolution.
        High severity issues need immediate attention.

        Arrangement:
        Three issues: two high, one low severity.

        Action:
        Call calculate_issue_summary.

        Assertion Strategy:
        Validates by_severity counts match expected grouping.
        """
        issues = [
            {"issue_type": "a", "severity": "high"},
            {"issue_type": "b", "severity": "high"},
            {"issue_type": "c", "severity": "low"},
        ]
        result = engine.calculate_issue_summary(issues)
        assert result["by_severity"]["high"] == 2
        assert result["by_severity"]["low"] == 1

    def test_total_count(self, engine: StatisticsEngine) -> None:
        """Verifies total issue count is accurate.

        Tests that total field reflects the actual number of issues
        regardless of type or severity distribution.

        Business context:
        Total issue count is a key quality indicator. High counts
        may indicate prompting or workflow problems.

        Arrangement:
        Five identical issues.

        Action:
        Call calculate_issue_summary.

        Assertion Strategy:
        Validates total equals 5.
        """
        issues = [{"issue_type": "a", "severity": "low"}] * 5
        result = engine.calculate_issue_summary(issues)
        assert result["total"] == 5

    def test_handles_missing_fields(self, engine: StatisticsEngine) -> None:
        """Verifies missing type/severity are categorized as unknown.

        Tests graceful handling of incomplete issue records that
        lack type or severity fields.

        Business context:
        Legacy or malformed data may lack classification fields.
        'Unknown' category prevents data loss.

        Arrangement:
        One issue with only description, no type or severity.

        Action:
        Call calculate_issue_summary.

        Assertion Strategy:
        Validates issue counted in 'unknown' for both type and severity.
        """
        issues = [{"description": "something"}]
        result = engine.calculate_issue_summary(issues)
        assert result["total"] == 1
        assert result["by_type"]["unknown"] == 1
        assert result["by_severity"]["unknown"] == 1


class TestCodeMetricsSummary:
    """Test suite for calculate_code_metrics_summary method.

    Categories:
    1. Empty State - Handle no sessions (1 test)
    2. Missing Data - Handle sessions without metrics (1 test)
    3. Aggregation Logic - Correct metric totals (1 test)

    Total: 3 tests covering code metrics aggregation.
    """

    def test_empty_sessions(self, engine: StatisticsEngine) -> None:
        """Verifies zero metrics for empty session dict.

        Tests that empty input produces valid summary with all
        metrics at zero.

        Business context:
        New projects have no sessions. Summary must be well-formed
        for dashboard display.

        Arrangement:
        Empty sessions dict.

        Action:
        Call calculate_code_metrics_summary.

        Assertion Strategy:
        Validates all metric fields are zero.
        """
        result = engine.calculate_code_metrics_summary({})
        assert result["total_functions"] == 0
        assert result["avg_complexity"] == 0
        assert result["avg_doc_score"] == 0

    def test_sessions_without_code_metrics(self, engine: StatisticsEngine) -> None:
        """Verifies graceful handling of sessions lacking code_metrics.

        Tests that sessions without the optional code_metrics field
        don't cause errors.

        Business context:
        Not all sessions log code metrics. Summary must handle
        sessions with and without metrics.

        Arrangement:
        One session with only name field, no code_metrics.

        Action:
        Call calculate_code_metrics_summary.

        Assertion Strategy:
        Validates zero functions counted.
        """
        sessions = {"s1": {"name": "test"}}
        result = engine.calculate_code_metrics_summary(sessions)
        assert result["total_functions"] == 0

    def test_aggregates_metrics(self, engine: StatisticsEngine) -> None:
        """Verifies correct aggregation of code metrics across sessions.

        Tests that metrics are properly summed and averaged across
        all functions in all sessions.

        Business context:
        Code metrics provide insight into AI contribution quality.
        Aggregation enables project-wide productivity analysis.

        Arrangement:
        One session with two functions having different metrics.

        Action:
        Call calculate_code_metrics_summary.

        Assertion Strategy:
        Validates totals (functions, lines) and averages (complexity,
        doc score) are calculated correctly.
        """
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
        """Create a session dictionary for ROI metric testing.

        Factory method that generates session data with configurable
        parameters for testing various ROI calculation scenarios.

        Business context:
        ROI tests need sessions with specific characteristics to validate
        filtering, aggregation, and calculation logic.

        Args:
            session_id: Unique identifier for the session.
            task_type: Category of work (default: code_generation).
            status: Session state - 'completed' or 'active'.
            duration_minutes: Time span for completed sessions.

        Returns:
            dict: Session data with id, task_type, status, start_time,
                and end_time (None if status is not 'completed').

        Example:
            session = self._make_session("s1", "debugging", "completed", 30)
            # Creates 30-minute debugging session
        """
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
        """Verifies zero metrics returned for empty input data.

        Tests that ROI calculation handles empty sessions and interactions
        gracefully, returning valid zeroed structure.

        Business context:
        New projects have no data. Dashboard must display valid metrics
        without errors or NaN values.

        Arrangement:
        Empty sessions dict and interactions list.

        Action:
        Call calculate_roi_metrics with empty inputs.

        Assertion Strategy:
        Validates zero values in key metrics:
        - total_ai_minutes is 0
        - completed_sessions is 0
        - cost_saved is 0

        Testing Principle:
        Validates graceful handling of empty state.
        """
        result = engine.calculate_roi_metrics({}, [])

        assert result["time_metrics"]["total_ai_minutes"] == 0
        assert result["time_metrics"]["completed_sessions"] == 0
        assert result["cost_metrics"]["cost_saved"] == 0

    def test_excludes_human_review_sessions(self, engine: StatisticsEngine) -> None:
        """Verifies human_review sessions excluded from productive time.

        Tests that task_type 'human_review' is filtered out of ROI
        calculations since it represents oversight not productivity.

        Business context:
        Human review time is overhead, not AI productivity. Including
        it would inflate ROI metrics incorrectly.

        Arrangement:
        Two sessions: one code_generation, one human_review.

        Action:
        Call calculate_roi_metrics with mixed session types.

        Assertion Strategy:
        Validates only code_generation counted:
        - total_ai_minutes ~60 (only s1)
        - completed_sessions is 1

        Testing Principle:
        Validates business rule filtering in calculations.
        """
        sessions = {
            "s1": self._make_session("s1", "code_generation", "completed", 60),
            "s2": self._make_session("s2", "human_review", "completed", 60),
        }
        result = engine.calculate_roi_metrics(sessions, [])

        # Only s1 should count (60 minutes)
        assert result["time_metrics"]["total_ai_minutes"] == pytest.approx(60.0, abs=0.1)
        assert result["time_metrics"]["completed_sessions"] == 1

    def test_excludes_active_sessions(self, engine: StatisticsEngine) -> None:
        """Verifies active (non-completed) sessions excluded from ROI.

        Tests that sessions with status 'active' are filtered since
        duration cannot be calculated without end_time.

        Business context:
        Active sessions have no end_time. Including them would require
        estimation, reducing metric accuracy.

        Arrangement:
        Two sessions: one completed, one active.

        Action:
        Call calculate_roi_metrics with mixed statuses.

        Assertion Strategy:
        Validates only completed session counted.

        Testing Principle:
        Validates state-based filtering in calculations.
        """
        sessions = {
            "s1": self._make_session("s1", "code_generation", "completed", 60),
            "s2": self._make_session("s2", "code_generation", "active", 60),
        }
        result = engine.calculate_roi_metrics(sessions, [])

        assert result["time_metrics"]["completed_sessions"] == 1

    def test_calculates_human_baseline(self, engine: StatisticsEngine) -> None:
        """Verifies human baseline estimated as 3x AI time.

        Tests the productivity multiplier assumption that humans would
        take 3x longer than AI-assisted time.

        Business context:
        ROI depends on comparison to human baseline. 3x multiplier is
        conservative estimate based on productivity research.

        Arrangement:
        One 60-minute completed session.

        Action:
        Call calculate_roi_metrics and check estimated_human_hours.

        Assertion Strategy:
        Validates human hours = AI hours * 3:
        - 1 AI hour * 3 = 3 human hours expected

        Testing Principle:
        Validates productivity multiplier application.
        """
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
        """Verifies cost savings calculation is positive.

        Tests that the cost difference between human baseline and
        AI-assisted work produces positive savings.

        Business context:
        Cost savings is the primary ROI metric. Positive savings
        validates the value of AI assistance.

        Arrangement:
        One 60-minute completed session.

        Action:
        Call calculate_roi_metrics and check cost_saved.

        Assertion Strategy:
        Validates cost_saved > 0, confirming AI saves money.
        Formula: human_cost - (ai_subscription + oversight_cost)

        Testing Principle:
        Validates core ROI calculation produces expected result.
        """
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
        """Verifies ROI percentage is calculated and positive.

        Tests that return on investment is computed as a percentage
        of the AI cost investment.

        Business context:
        ROI percentage enables comparison across time periods and
        teams. High ROI validates AI investment.

        Arrangement:
        One 60-minute completed session.

        Action:
        Call calculate_roi_metrics and check roi_percentage.

        Assertion Strategy:
        Validates roi_percentage > 0, confirming positive return.
        Formula: (savings / ai_total_cost) * 100

        Testing Principle:
        Validates percentage calculation for investment analysis.
        """
        sessions = {
            "s1": self._make_session("s1", "code_generation", "completed", 60),
        }
        result = engine.calculate_roi_metrics(sessions, [])

        assert result["cost_metrics"]["roi_percentage"] > 0

    def test_includes_productivity_metrics(self, engine: StatisticsEngine) -> None:
        """Verifies productivity metrics derived from interactions.

        Tests that interaction data is aggregated into productivity
        metrics for session analysis.

        Business context:
        Productivity metrics show how effectively AI is being used.
        High interactions with good ratings indicate smooth workflow.

        Arrangement:
        One session with two interactions rated 5 and 3.

        Action:
        Call calculate_roi_metrics with session and interactions.

        Assertion Strategy:
        Validates productivity calculations:
        - total_interactions equals 2
        - average_effectiveness equals 4.0
        - interactions_per_session equals 2.0

        Testing Principle:
        Validates interaction aggregation into metrics.
        """
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
        """Verifies ROI result includes configuration values.

        Tests that the engine's rate configuration is included in
        results for transparency and validation.

        Business context:
        Showing config values helps users understand assumptions.
        Transparency builds trust in ROI calculations.

        Arrangement:
        Empty sessions (config included regardless of data).

        Action:
        Call calculate_roi_metrics and check config section.

        Assertion Strategy:
        Validates config section contains:
        - human_hourly_rate matching engine setting
        - ai_monthly_cost matching engine setting

        Testing Principle:
        Validates transparency in calculation assumptions.
        """
        result = engine.calculate_roi_metrics({}, [])

        assert "config" in result
        assert result["config"]["human_hourly_rate"] == engine.human_hourly_rate
        assert result["config"]["ai_monthly_cost"] == engine.ai_monthly_cost


class TestSummaryReport:
    """Tests for generate_summary_report."""

    def test_returns_string(self, engine: StatisticsEngine) -> None:
        """Verifies summary report returns string type.

        Tests that generate_summary_report produces a string suitable
        for display in CLI or dashboard.

        Business context:
        Report must be displayable as text. String type enables
        both terminal output and web rendering.

        Arrangement:
        Empty data inputs.

        Action:
        Call generate_summary_report with empty inputs.

        Assertion Strategy:
        Validates return type is str.

        Testing Principle:
        Validates output type contract.
        """
        result = engine.generate_summary_report({}, [], [])
        assert isinstance(result, str)

    def test_includes_headers(self, engine: StatisticsEngine) -> None:
        """Verifies summary report includes all section headers.

        Tests that the report structure contains expected sections
        for navigating analytics content.

        Business context:
        Headers organize report for readability. Users scan headers
        to find relevant metrics quickly.

        Arrangement:
        Empty data inputs.

        Action:
        Call generate_summary_report and inspect content.

        Assertion Strategy:
        Validates all five section headers present:
        - SESSION SUMMARY, ROI METRICS, EFFECTIVENESS DISTRIBUTION
        - ISSUES SUMMARY, CODE METRICS

        Testing Principle:
        Validates report structure completeness.
        """
        result = engine.generate_summary_report({}, [], [])

        assert "SESSION SUMMARY" in result
        assert "ROI METRICS" in result
        assert "EFFECTIVENESS DISTRIBUTION" in result
        assert "ISSUES SUMMARY" in result
        assert "CODE METRICS" in result

    def test_includes_session_count(self, engine: StatisticsEngine) -> None:
        """Verifies summary report shows total session count.

        Tests that session count is displayed in the report for
        quick overview of tracked activity.

        Business context:
        Session count shows adoption level. Low counts may indicate
        tracking not being used consistently.

        Arrangement:
        Two empty session dictionaries.

        Action:
        Call generate_summary_report with session data.

        Assertion Strategy:
        Validates "Total sessions: 2" appears in output.

        Testing Principle:
        Validates count display formatting.
        """
        sessions = {"s1": {}, "s2": {}}
        result = engine.generate_summary_report(sessions, [], [])

        assert "Total sessions: 2" in result

    def test_includes_effectiveness_stars(self, engine: StatisticsEngine) -> None:
        """Verifies summary report shows star rating distribution.

        Tests that effectiveness ratings are displayed as visual
        star symbols for intuitive understanding.

        Business context:
        Star ratings are universally understood. Visual representation
        makes effectiveness distribution immediately clear.

        Arrangement:
        One interaction with 5-star rating.

        Action:
        Call generate_summary_report with interaction data.

        Assertion Strategy:
        Validates "★★★★★: 1" appears showing count of 5-star ratings.

        Testing Principle:
        Validates visual formatting of rating data.
        """
        interactions = [{"effectiveness_rating": 5}]
        result = engine.generate_summary_report({}, interactions, [])

        assert "★★★★★: 1" in result

    def test_includes_issue_counts(self, engine: StatisticsEngine) -> None:
        """Verifies summary report shows issue counts by severity.

        Tests that issues are categorized and counted by severity
        level in the report.

        Business context:
        Issue severity breakdown prioritizes attention. High severity
        issues need immediate review.

        Arrangement:
        Two high-severity issues.

        Action:
        Call generate_summary_report with issue data.

        Assertion Strategy:
        Validates "High: 2" appears showing severity count.

        Testing Principle:
        Validates issue categorization display.
        """
        issues = [
            {"issue_type": "test", "severity": "high"},
            {"issue_type": "test", "severity": "high"},
        ]
        result = engine.generate_summary_report({}, [], issues)

        assert "High: 2" in result

    def test_formats_currency(self, engine: StatisticsEngine) -> None:
        """Verifies summary report uses currency symbols for costs.

        Tests that monetary values are formatted with dollar signs
        for clear financial presentation.

        Business context:
        Currency formatting makes costs immediately recognizable.
        Proper formatting is essential for executive summaries.

        Arrangement:
        One completed 1-hour session to generate cost metrics.

        Action:
        Call generate_summary_report with session data.

        Assertion Strategy:
        Validates "$" symbol appears in output.

        Testing Principle:
        Validates financial data formatting.
        """
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
