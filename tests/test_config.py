"""Tests for config module."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from ai_session_tracker_mcp.config import Config


class TestConfigConstants:
    """Tests for static configuration values."""

    @pytest.mark.parametrize(
        "attr_name,expected_value",
        [
            pytest.param("STORAGE_DIR", ".ai_sessions", id="storage_dir"),
            pytest.param("SESSIONS_FILE", "sessions.json", id="sessions_file"),
            pytest.param("INTERACTIONS_FILE", "interactions.json", id="interactions_file"),
            pytest.param("ISSUES_FILE", "issues.json", id="issues_file"),
            pytest.param("CHARTS_DIR", "charts", id="charts_dir"),
            pytest.param("HUMAN_HOURLY_RATE", 130.0, id="human_hourly_rate"),
            pytest.param("AI_MONTHLY_COST", 40.0, id="ai_monthly_cost"),
            pytest.param("WORKING_HOURS_PER_MONTH", 160.0, id="working_hours"),
            pytest.param("MCP_VERSION", "2024-11-05", id="mcp_version"),
            pytest.param("SERVER_NAME", "ai-session-tracker", id="server_name"),
        ],
    )
    def test_config_constant_value(self, attr_name: str, expected_value: object) -> None:
        """
        Verifies Config constants have expected values.

        Tests that configuration constants match expected values for
        storage paths, file names, and business parameters.

        Business context:
        Configuration constants are used throughout the codebase.
        Changing them would affect storage locations and ROI calculations.

        Arrangement:
        1. attr_name identifies which constant to verify from parametrize.
        2. expected_value is the value the constant should have.

        Action:
        Access getattr(Config, attr_name) to retrieve constant value.

        Assertion Strategy:
        Validates the retrieved constant equals expected_value, confirming
        configuration integrity.

        Testing Principle:
        Parameterized test validates all constant values efficiently.
        """
        assert getattr(Config, attr_name) == expected_value

    def test_server_version_is_semver(self) -> None:
        """Verifies SERVER_VERSION follows semver format.

        Tests that version string matches X.Y.Z pattern.
        """
        import re

        assert re.match(r"^\d+\.\d+\.\d+$", Config.SERVER_VERSION)

    def test_task_types_is_frozenset(self) -> None:
        """Verifies task types is a frozen set.

        Tests that task types are immutable for configuration safety.

        Business context:
        Task types should not change at runtime. Frozen set prevents
        accidental modification.

        Arrangement:
        None - tests constant type.

        Action:
        Check type of Config.TASK_TYPES.

        Assertion Strategy:
        Validates type is frozenset.

        Testing Principle:
        Validates immutability of configuration.
        """
        assert isinstance(Config.TASK_TYPES, frozenset)

    def test_task_types_contains_expected_values(self) -> None:
        """Verifies task types contains expected categories.

        Tests that all expected task type values are present.

        Business context:
        Task types categorize sessions for filtering and analysis.
        Missing types would prevent proper categorization.

        Arrangement:
        Define expected set of task types.

        Action:
        Compare Config.TASK_TYPES with expected set.

        Assertion Strategy:
        Validates exact set equality.

        Testing Principle:
        Validates complete set of valid values.
        """
        expected = {
            "code_generation",
            "documentation",
            "debugging",
            "refactoring",
            "testing",
            "analysis",
            "architecture_planning",
            "human_review",
        }
        assert expected == Config.TASK_TYPES

    def test_excluded_from_roi_contains_human_review(self) -> None:
        """Verifies human review is excluded from ROI.

        Tests that human_review task type is in the exclusion set.

        Business context:
        Human review sessions are overhead, not AI productivity.
        Excluding them gives accurate ROI calculations.

        Arrangement:
        None - tests set membership.

        Action:
        Check if 'human_review' is in EXCLUDED_FROM_ROI.

        Assertion Strategy:
        Validates membership in exclusion set.

        Testing Principle:
        Validates ROI calculation filter.
        """
        assert "human_review" in Config.EXCLUDED_FROM_ROI

    def test_severity_levels_is_frozenset(self) -> None:
        """Verifies severity levels is a frozen set.

        Tests that severity levels are immutable for configuration safety.

        Business context:
        Severity levels should not change at runtime. Frozen set
        prevents accidental modification.

        Arrangement:
        None - tests constant type.

        Action:
        Check type of Config.SEVERITY_LEVELS.

        Assertion Strategy:
        Validates type is frozenset.

        Testing Principle:
        Validates immutability of configuration.
        """
        assert isinstance(Config.SEVERITY_LEVELS, frozenset)

    def test_severity_levels_contains_expected_values(self) -> None:
        """Verifies severity levels contains expected categories.

        Tests that all expected severity level values are present.

        Business context:
        Severity levels categorize issues for prioritization. Standard
        levels enable consistent triage.

        Arrangement:
        Define expected set of severity levels.

        Action:
        Compare Config.SEVERITY_LEVELS with expected set.

        Assertion Strategy:
        Validates exact set equality.

        Testing Principle:
        Validates complete set of valid values.
        """
        expected = {"low", "medium", "high", "critical"}
        assert expected == Config.SEVERITY_LEVELS


class TestConfigComputedProperties:
    """Tests for computed configuration values."""

    def test_ai_hourly_rate_calculation(self) -> None:
        """Verifies AI hourly rate is correctly calculated.

        Tests that AI hourly rate derives from monthly cost and hours.

        Business context:
        AI hourly rate enables comparison with human hourly rate.
        $40/month ÷ 160 hours = $0.25/hour.

        Arrangement:
        Calculate expected rate from constants.

        Action:
        Call Config.ai_hourly_rate() method.

        Assertion Strategy:
        Validates formula and specific numeric result.

        Testing Principle:
        Validates derived calculation.
        """
        expected = Config.AI_MONTHLY_COST / Config.WORKING_HOURS_PER_MONTH
        assert Config.ai_hourly_rate() == expected
        assert Config.ai_hourly_rate() == 0.25

    def test_roi_multiplier_calculation(self) -> None:
        """Verifies ROI multiplier is correctly calculated.

        Tests that ROI multiplier derives from human/AI rate ratio.

        Business context:
        ROI multiplier shows cost savings ratio. $130 human ÷ $0.25 AI
        = 520x potential cost savings.

        Arrangement:
        Calculate expected multiplier from constants.

        Action:
        Call Config.roi_multiplier() method.

        Assertion Strategy:
        Validates formula and specific numeric result.

        Testing Principle:
        Validates derived calculation.
        """
        expected = Config.HUMAN_HOURLY_RATE / Config.ai_hourly_rate()
        assert Config.roi_multiplier() == expected
        assert Config.roi_multiplier() == 520.0


class TestConfigEnvironmentSettings:
    """Tests for environment-based configuration."""

    def setup_method(self) -> None:
        """Reset test overrides before each test.

        Ensures clean config state by clearing any test overrides
        from previous tests.

        Business context:
        Test isolation prevents config leakage between tests.
        Each test starts with default configuration.

        Args:
            self: Test class instance (implicit, no other args).

        Returns:
            None.

        Raises:
            No exceptions raised by this method.
        """
        Config.reset_test_overrides()

    def teardown_method(self) -> None:
        """Reset test overrides after each test.

        Cleans up any test overrides to prevent pollution
        of subsequent tests.

        Business context:
        Test isolation ensures reliable, reproducible results.
        Cleanup prevents false positives/negatives.

        Args:
            self: Test class instance (implicit, no other args).

        Returns:
            None.

        Raises:
            No exceptions raised by this method.
        """
        Config.reset_test_overrides()

    def test_s3_backup_disabled_by_default(self) -> None:
        """Verifies S3 backup is disabled by default.

        Tests that S3 backup requires explicit opt-in.

        Business context:
        S3 backup is optional feature requiring AWS credentials.
        Disabled by default for simpler setup.

        Arrangement:
        Clear environment variables.

        Action:
        Call Config.is_s3_backup_enabled() method.

        Assertion Strategy:
        Validates return value is False.

        Testing Principle:
        Validates secure default.
        """
        with patch.dict(os.environ, {}, clear=True):
            assert Config.is_s3_backup_enabled() is False

    def test_s3_backup_enabled_via_env_var(self) -> None:
        """Verifies S3 backup can be enabled via environment variable.

        Tests that AI_ENABLE_S3_BACKUP=true enables the feature.

        Business context:
        Environment variables are standard for deployment configuration.
        Allows enabling backup without code changes.

        Arrangement:
        Set AI_ENABLE_S3_BACKUP environment variable to 'true'.

        Action:
        Call Config.is_s3_backup_enabled() method.

        Assertion Strategy:
        Validates return value is True.

        Testing Principle:
        Validates environment variable configuration.
        """
        with patch.dict(os.environ, {"AI_ENABLE_S3_BACKUP": "true"}):
            assert Config.is_s3_backup_enabled() is True

    def test_s3_backup_env_var_case_insensitive(self) -> None:
        """Verifies S3 backup env var is case insensitive.

        Tests that 'TRUE' works the same as 'true'.

        Business context:
        Case-insensitive parsing is more user-friendly. Prevents
        confusion from case differences.

        Arrangement:
        Set AI_ENABLE_S3_BACKUP to uppercase 'TRUE'.

        Action:
        Call Config.is_s3_backup_enabled() method.

        Assertion Strategy:
        Validates return value is True.

        Testing Principle:
        Validates case-insensitive parsing.
        """
        with patch.dict(os.environ, {"AI_ENABLE_S3_BACKUP": "TRUE"}):
            assert Config.is_s3_backup_enabled() is True

    def test_s3_backup_false_for_other_values(self) -> None:
        """Verifies S3 backup false for non-true values.

        Tests that only 'true' enables the feature, not 'yes' etc.

        Business context:
        Strict parsing prevents accidental enablement. Only explicit
        'true' value activates the feature.

        Arrangement:
        Set AI_ENABLE_S3_BACKUP to 'yes' (not 'true').

        Action:
        Call Config.is_s3_backup_enabled() method.

        Assertion Strategy:
        Validates return value is False.

        Testing Principle:
        Validates strict boolean parsing.
        """
        with patch.dict(os.environ, {"AI_ENABLE_S3_BACKUP": "yes"}):
            assert Config.is_s3_backup_enabled() is False

    def test_s3_backup_test_override_true(self) -> None:
        """Verifies test override can enable S3 backup.

        Tests that test code can force S3 backup enabled.

        Business context:
        Test overrides allow testing S3 code paths without actual
        environment variables.

        Arrangement:
        Set test override for s3_enabled=True.

        Action:
        Call Config.is_s3_backup_enabled() method.

        Assertion Strategy:
        Validates return value is True.

        Testing Principle:
        Validates test override mechanism.
        """
        Config.set_test_overrides(s3_enabled=True)
        assert Config.is_s3_backup_enabled() is True

    def test_s3_backup_test_override_false(self) -> None:
        """Verifies test override can disable S3 backup.

        Tests that test code can force S3 backup disabled even when
        environment variable is set.

        Business context:
        Test overrides take precedence over environment. Enables
        testing both code paths regardless of environment.

        Arrangement:
        Set env var to 'true' but override to False.

        Action:
        Call Config.is_s3_backup_enabled() method.

        Assertion Strategy:
        Validates return value is False (override wins).

        Testing Principle:
        Validates test override precedence.
        """
        with patch.dict(os.environ, {"AI_ENABLE_S3_BACKUP": "true"}):
            Config.set_test_overrides(s3_enabled=False)
            assert Config.is_s3_backup_enabled() is False

    def test_project_id_uses_cwd_by_default(self) -> None:
        """Verifies project ID defaults to current directory name.

        Tests that project ID auto-derives from working directory.

        Business context:
        Project ID identifies sessions for multi-project environments.
        Deriving from directory is intuitive default.

        Arrangement:
        Clear environment variables.

        Action:
        Call Config.get_project_id() method.

        Assertion Strategy:
        Validates result matches current directory basename.

        Testing Principle:
        Validates sensible default.
        """
        with patch.dict(os.environ, {}, clear=True):
            expected = os.path.basename(os.getcwd())
            assert Config.get_project_id() == expected

    def test_project_id_from_env_var(self) -> None:
        """Verifies project ID can be set via environment variable.

        Tests that AI_PROJECT_ID environment variable overrides default.

        Business context:
        Explicit project ID enables custom naming. Useful when
        directory name doesn't match project identity.

        Arrangement:
        Set AI_PROJECT_ID environment variable.

        Action:
        Call Config.get_project_id() method.

        Assertion Strategy:
        Validates result matches environment variable value.

        Testing Principle:
        Validates environment variable override.
        """
        with patch.dict(os.environ, {"AI_PROJECT_ID": "my-project"}):
            assert Config.get_project_id() == "my-project"

    def test_project_id_test_override(self) -> None:
        """Verifies test override can set project ID.

        Tests that test code can force specific project ID.

        Business context:
        Test overrides allow deterministic testing without depending
        on working directory or environment.

        Arrangement:
        Set test override for project_id.

        Action:
        Call Config.get_project_id() method.

        Assertion Strategy:
        Validates result matches override value.

        Testing Principle:
        Validates test override mechanism.
        """
        Config.set_test_overrides(project_id="test-project")
        assert Config.get_project_id() == "test-project"

    def test_reset_test_overrides_clears_all(self) -> None:
        """Verifies reset clears all test overrides.

        Tests that reset_test_overrides restores default behavior.

        Business context:
        Test cleanup requires resetting overrides. Prevents test
        pollution between test methods.

        Arrangement:
        Set both s3 and project_id overrides.

        Action:
        Call Config.reset_test_overrides() method.

        Assertion Strategy:
        Validates both override fields are None.

        Testing Principle:
        Validates complete override reset.
        """
        Config.set_test_overrides(s3_enabled=True, project_id="test")
        Config.reset_test_overrides()
        assert Config._s3_backup_override is None
        assert Config._project_id_override is None

    def test_override_for_test_context_manager(self) -> None:
        """Verifies context manager sets and resets overrides.

        Tests that override_for_test provides cleaner test isolation.

        Business context:
        Context manager pattern ensures automatic cleanup even if
        test raises exception. Prevents test pollution.

        Arrangement:
        Confirm default state before context.

        Action:
        Use override_for_test context manager with test values.

        Assertion Strategy:
        Validates overrides active inside context, reset outside.

        Testing Principle:
        Validates context manager lifecycle.
        """
        # Before context: defaults apply
        with patch.dict(os.environ, {}, clear=True):
            assert Config.is_s3_backup_enabled() is False

        # Inside context: overrides active
        with Config.override_for_test(s3_enabled=True, project_id="ctx-test"):
            assert Config.is_s3_backup_enabled() is True
            assert Config.get_project_id() == "ctx-test"

        # After context: automatically reset
        assert Config._s3_backup_override is None
        assert Config._project_id_override is None

    def test_override_for_test_resets_on_exception(self) -> None:
        """Verifies context manager resets even on exception.

        Tests that cleanup occurs even if test code raises.

        Business context:
        Exception safety is critical for test isolation. A failing
        test should not pollute subsequent tests.

        Arrangement:
        Set up context manager with overrides.

        Action:
        Raise exception inside context.

        Assertion Strategy:
        Validates overrides are reset despite exception.

        Testing Principle:
        Validates exception-safe cleanup.
        """
        with (
            pytest.raises(ValueError),
            Config.override_for_test(s3_enabled=True, project_id="exc-test"),
        ):
            assert Config.is_s3_backup_enabled() is True
            raise ValueError("Simulated test failure")

        # Cleanup should still have occurred
        assert Config._s3_backup_override is None
        assert Config._project_id_override is None


class TestConfigFilterProductiveSessions:
    """Tests for session filtering."""

    def test_filter_empty_sessions(self) -> None:
        """Verifies filtering empty dict returns empty dict.

        Tests edge case of filtering with no sessions.

        Business context:
        Empty input should return empty output. Should not raise
        or return unexpected results.

        Arrangement:
        Create empty sessions dict.

        Action:
        Call Config.filter_productive_sessions() with empty dict.

        Assertion Strategy:
        Validates result is empty dict.

        Testing Principle:
        Validates empty input handling.
        """
        result = Config.filter_productive_sessions({})
        assert result == {}

    def test_filter_keeps_productive_sessions(self) -> None:
        """Verifies filtering keeps productive task types.

        Tests that non-excluded task types pass through filter.

        Business context:
        Productive sessions contribute to ROI. code_generation,
        debugging, testing are all counted.

        Arrangement:
        Create sessions with various productive task types.

        Action:
        Call Config.filter_productive_sessions() method.

        Assertion Strategy:
        Validates all sessions are retained.

        Testing Principle:
        Validates positive filter behavior.
        """
        sessions = {
            "s1": {"task_type": "code_generation"},
            "s2": {"task_type": "debugging"},
            "s3": {"task_type": "testing"},
        }
        result = Config.filter_productive_sessions(sessions)
        assert len(result) == 3
        assert "s1" in result
        assert "s2" in result
        assert "s3" in result

    def test_filter_removes_human_review(self) -> None:
        """Verifies filtering removes human_review sessions.

        Tests that excluded task types are filtered out.

        Business context:
        Human review is oversight, not AI productivity. Excluding
        it gives accurate ROI calculations.

        Arrangement:
        Create sessions with mix of productive and excluded types.

        Action:
        Call Config.filter_productive_sessions() method.

        Assertion Strategy:
        Validates productive session kept, human_review removed.

        Testing Principle:
        Validates negative filter behavior.
        """
        sessions = {
            "s1": {"task_type": "code_generation"},
            "s2": {"task_type": "human_review"},
        }
        result = Config.filter_productive_sessions(sessions)
        assert len(result) == 1
        assert "s1" in result
        assert "s2" not in result

    def test_filter_handles_missing_task_type(self) -> None:
        """Verifies filtering handles sessions without task_type.

        Tests graceful handling of malformed session data.

        Business context:
        Legacy or corrupt data may lack task_type. Include rather
        than exclude to avoid data loss.

        Arrangement:
        Create session without task_type field.

        Action:
        Call Config.filter_productive_sessions() method.

        Assertion Strategy:
        Validates session is included despite missing field.

        Testing Principle:
        Validates defensive coding for missing data.
        """
        sessions = {
            "s1": {"name": "test"},  # No task_type
        }
        result = Config.filter_productive_sessions(sessions)
        assert len(result) == 1
        assert "s1" in result


class TestMaxSessionDuration:
    """Tests for max session duration configuration."""

    def test_default_max_session_duration(self) -> None:
        """Verifies default max session duration is 4.0 hours."""
        Config.reset_test_overrides()
        assert Config.MAX_SESSION_DURATION_HOURS == 4.0

    def test_get_max_session_duration_returns_default(self) -> None:
        """Verifies get_max_session_duration_hours returns default when no override."""
        Config.reset_test_overrides()
        with patch.dict(os.environ, {}, clear=True):
            result = Config.get_max_session_duration_hours()
            assert result == 4.0

    def test_get_max_session_duration_uses_override(self) -> None:
        """Verifies test override takes precedence over default."""
        Config.set_test_overrides(max_session_duration=8.0)
        try:
            result = Config.get_max_session_duration_hours()
            assert result == 8.0
        finally:
            Config.reset_test_overrides()

    def test_get_max_session_duration_from_env_var(self) -> None:
        """Verifies environment variable is read when set."""
        Config.reset_test_overrides()
        with patch.dict(os.environ, {"AI_MAX_SESSION_DURATION_HOURS": "6.5"}):
            result = Config.get_max_session_duration_hours()
            assert result == 6.5

    def test_get_max_session_duration_invalid_env_var_falls_back(self) -> None:
        """Verifies invalid env var falls back to default."""
        Config.reset_test_overrides()
        with patch.dict(os.environ, {"AI_MAX_SESSION_DURATION_HOURS": "not-a-number"}):
            result = Config.get_max_session_duration_hours()
            assert result == 4.0

    def test_override_takes_precedence_over_env_var(self) -> None:
        """Verifies test override takes precedence over env var."""
        Config.set_test_overrides(max_session_duration=2.0)
        try:
            with patch.dict(os.environ, {"AI_MAX_SESSION_DURATION_HOURS": "10.0"}):
                result = Config.get_max_session_duration_hours()
                assert result == 2.0
        finally:
            Config.reset_test_overrides()

    def test_context_manager_sets_max_session_duration(self) -> None:
        """Verifies context manager properly sets max_session_duration."""
        with Config.override_for_test(max_session_duration=1.5):
            result = Config.get_max_session_duration_hours()
            assert result == 1.5
        # Verify reset after context
        Config.reset_test_overrides()
        assert Config._max_session_duration_override is None

    def test_env_var_name_constant(self) -> None:
        """Verifies environment variable name constant is correct."""
        assert Config.ENV_MAX_SESSION_DURATION == "AI_MAX_SESSION_DURATION_HOURS"
