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
        """Verifies SERVER_VERSION follows semantic versioning format.

        Tests that the version string conforms to the X.Y.Z pattern required
        by semantic versioning, ensuring compatibility with package managers
        and version comparison tools.

        Business context:
        Semantic versioning is critical for release management. An invalid
        version string would break pip packaging, MCP protocol negotiation,
        and automated deployment pipelines.

        Arrangement:
        1. Import re module for regex-based pattern matching.
        2. No additional setup needed; tests a static constant.

        Action:
        Match Config.SERVER_VERSION against the semver regex pattern
        ``^\\d+\\.\\d+\\.\\d+$`` to verify format compliance.

        Assertion Strategy:
        Validates the regex match is truthy, confirming:
        - Version contains exactly three numeric segments.
        - Segments are separated by dots with no extra characters.

        Testing Principle:
        Validates format constraint on a critical metadata constant,
        ensuring downstream consumers receive well-formed version strings.
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

    def test_reset_test_overrides_clears_all(self) -> None:
        """Verifies reset clears all test overrides.

        Tests that reset_test_overrides restores default behavior.

        Business context:
        Test cleanup requires resetting overrides. Prevents test
        pollution between test methods.

        Arrangement:
        Set max_session_duration override.

        Action:
        Call Config.reset_test_overrides() method.

        Assertion Strategy:
        Validates override fields are None.

        Testing Principle:
        Validates complete override reset.
        """
        Config.set_test_overrides(max_session_duration=2.0)
        Config.reset_test_overrides()
        assert Config._max_session_duration_override is None
        assert Config._output_dir_override is None

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
            assert Config.get_max_session_duration_hours() == Config.MAX_SESSION_DURATION_HOURS

        # Inside context: overrides active
        with Config.override_for_test(max_session_duration=1.0):
            assert Config.get_max_session_duration_hours() == 1.0

        # After context: automatically reset
        assert Config._max_session_duration_override is None
        assert Config._output_dir_override is None

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
            Config.override_for_test(max_session_duration=1.0),
        ):
            assert Config.get_max_session_duration_hours() == 1.0
            raise ValueError("Simulated test failure")

        # Cleanup should still have occurred
        assert Config._max_session_duration_override is None
        assert Config._output_dir_override is None


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
        """Verifies the default max session duration constant is 4.0 hours.

        Tests that the MAX_SESSION_DURATION_HOURS class constant holds the
        expected default value used when no override or environment variable
        is configured.

        Business context:
        The default duration caps how long a session can run before being
        considered stale. A 4-hour default balances realistic work sessions
        against runaway session detection.

        Arrangement:
        1. Reset test overrides to ensure clean state.
        2. No environment patching needed; testing the raw constant.

        Action:
        Access Config.MAX_SESSION_DURATION_HOURS to read the class-level
        default constant value.

        Assertion Strategy:
        Validates the constant equals exactly 4.0, confirming:
        - The default hasn't been accidentally changed.
        - The value is a float (not int) for consistent arithmetic.

        Testing Principle:
        Validates a critical default value that affects session lifecycle
        management across the entire application.
        """
        Config.reset_test_overrides()
        assert Config.MAX_SESSION_DURATION_HOURS == 4.0

    def test_get_max_session_duration_returns_default(self) -> None:
        """Verifies get_max_session_duration_hours returns the default when no override is set.

        Tests the accessor method's fallback behavior when neither a test
        override nor an environment variable provides a custom value.

        Business context:
        In production without any environment configuration, the system must
        fall back to a sensible default. This ensures the application works
        out-of-the-box without requiring explicit configuration.

        Arrangement:
        1. Reset test overrides to ensure no override is active.
        2. Clear environment variables via patch.dict to simulate a clean
           environment with no AI_MAX_SESSION_DURATION_HOURS set.

        Action:
        Call Config.get_max_session_duration_hours() in the clean environment
        to retrieve the effective session duration.

        Assertion Strategy:
        Validates the result equals 4.0, confirming:
        - The accessor correctly falls through override and env var checks.
        - The class-level default constant is returned as the final fallback.

        Testing Principle:
        Validates the default fallback path in the configuration resolution
        chain, ensuring zero-config deployments work correctly.
        """
        Config.reset_test_overrides()
        with patch.dict(os.environ, {}, clear=True):
            result = Config.get_max_session_duration_hours()
            assert result == 4.0

    def test_get_max_session_duration_uses_override(self) -> None:
        """Verifies test override takes precedence over the default value.

        Tests that set_test_overrides injects a custom max session duration
        that the accessor method returns instead of the class-level default.

        Business context:
        Test overrides allow controlled testing of duration-dependent logic
        without modifying environment variables. This is essential for
        testing timeout behavior, session expiry, and duration validation.

        Arrangement:
        1. Call set_test_overrides with max_session_duration=8.0 to inject
           a custom value that differs from the 4.0 default.
        2. Use try/finally to guarantee cleanup even if assertion fails.

        Action:
        Call Config.get_max_session_duration_hours() to retrieve the
        effective duration while the override is active.

        Assertion Strategy:
        Validates the result equals 8.0, confirming:
        - The override mechanism correctly intercepts the accessor.
        - The overridden value is returned instead of the default.
        - Cleanup via reset_test_overrides restores original state.

        Testing Principle:
        Validates the highest-priority configuration source in the
        resolution chain (override > env var > default).
        """
        Config.set_test_overrides(max_session_duration=8.0)
        try:
            result = Config.get_max_session_duration_hours()
            assert result == 8.0
        finally:
            Config.reset_test_overrides()

    def test_get_max_session_duration_from_env_var(self) -> None:
        """Verifies the accessor reads max session duration from the environment variable.

        Tests that AI_MAX_SESSION_DURATION_HOURS environment variable is
        correctly parsed as a float and returned by the accessor.

        Business context:
        Environment variables allow operators to customize session duration
        per deployment without code changes. This supports different team
        workflows (e.g., longer sessions for architecture work).

        Arrangement:
        1. Reset test overrides so the env var path is exercised.
        2. Patch environment with AI_MAX_SESSION_DURATION_HOURS="6.5"
           to simulate operator configuration.

        Action:
        Call Config.get_max_session_duration_hours() with the env var set
        to verify it reads and parses the environment value.

        Assertion Strategy:
        Validates the result equals 6.5, confirming:
        - The env var is read when no override is present.
        - String-to-float parsing works correctly for decimal values.

        Testing Principle:
        Validates environment-based configuration, ensuring the middle
        tier of the resolution chain (override > env var > default) works.
        """
        Config.reset_test_overrides()
        with patch.dict(os.environ, {"AI_MAX_SESSION_DURATION_HOURS": "6.5"}):
            result = Config.get_max_session_duration_hours()
            assert result == 6.5

    def test_get_max_session_duration_invalid_env_var_falls_back(self) -> None:
        """Verifies an invalid environment variable value falls back to the default.

        Tests graceful degradation when the environment variable contains a
        non-numeric string that cannot be parsed as a float.

        Business context:
        Operators may misconfigure environment variables. The system must
        degrade gracefully to the default rather than crashing, ensuring
        service availability despite configuration errors.

        Arrangement:
        1. Reset test overrides to isolate the env var path.
        2. Patch environment with AI_MAX_SESSION_DURATION_HOURS="not-a-number"
           to simulate a misconfiguration.

        Action:
        Call Config.get_max_session_duration_hours() with the invalid env var
        to verify the fallback behavior.

        Assertion Strategy:
        Validates the result equals 4.0 (the default), confirming:
        - ValueError from float() parsing is caught internally.
        - The default value is returned instead of raising an exception.

        Testing Principle:
        Validates defensive error handling in configuration parsing,
        ensuring robustness against malformed operator input.
        """
        Config.reset_test_overrides()
        with patch.dict(os.environ, {"AI_MAX_SESSION_DURATION_HOURS": "not-a-number"}):
            result = Config.get_max_session_duration_hours()
            assert result == 4.0

    def test_override_takes_precedence_over_env_var(self) -> None:
        """Verifies test override takes precedence over the environment variable.

        Tests the priority ordering of the configuration resolution chain
        when both an override and an environment variable are present.

        Business context:
        During testing, overrides must win over env vars to provide
        deterministic test behavior regardless of the host environment.
        This prevents flaky tests caused by lingering env vars.

        Arrangement:
        1. Set test override to max_session_duration=2.0 via set_test_overrides.
        2. Patch environment with AI_MAX_SESSION_DURATION_HOURS="10.0" to
           create a competing configuration source.
        3. Use try/finally to guarantee override cleanup.

        Action:
        Call Config.get_max_session_duration_hours() with both configuration
        sources active to test priority resolution.

        Assertion Strategy:
        Validates the result equals 2.0 (the override), confirming:
        - Override value (2.0) wins over env var value (10.0).
        - The resolution chain correctly prioritizes override > env var.

        Testing Principle:
        Validates configuration precedence rules, ensuring the override
        mechanism provides reliable test isolation.
        """
        Config.set_test_overrides(max_session_duration=2.0)
        try:
            with patch.dict(os.environ, {"AI_MAX_SESSION_DURATION_HOURS": "10.0"}):
                result = Config.get_max_session_duration_hours()
                assert result == 2.0
        finally:
            Config.reset_test_overrides()

    def test_context_manager_sets_max_session_duration(self) -> None:
        """Verifies the context manager properly sets and resets max_session_duration.

        Tests that override_for_test context manager applies the duration
        override within its scope and cleans up afterward.

        Business context:
        The context manager pattern provides RAII-style resource management
        for test overrides, ensuring automatic cleanup. This prevents test
        pollution even when tests are reordered or selectively run.

        Arrangement:
        1. No explicit setup needed; context manager handles its own lifecycle.

        Action:
        Enter Config.override_for_test with max_session_duration=1.5, then
        call the accessor inside the context, and verify cleanup afterward.

        Assertion Strategy:
        Validates behavior at two points, confirming:
        - Inside context: get_max_session_duration_hours() returns 1.5.
        - After context exit: _max_session_duration_override is None,
          confirming automatic cleanup occurred.

        Testing Principle:
        Validates context manager lifecycle for configuration overrides,
        ensuring both setup and teardown work correctly.
        """
        with Config.override_for_test(max_session_duration=1.5):
            result = Config.get_max_session_duration_hours()
            assert result == 1.5
        # Verify reset after context
        Config.reset_test_overrides()
        assert Config._max_session_duration_override is None

    def test_env_var_name_constant(self) -> None:
        """Verifies the environment variable name constant matches the expected string.

        Tests that ENV_MAX_SESSION_DURATION holds the correct environment
        variable name used for runtime configuration lookups.

        Business context:
        The env var name is a contract between the application and its
        deployment environment. Changing it would break existing deployments
        that rely on AI_MAX_SESSION_DURATION_HOURS for configuration.

        Arrangement:
        1. No setup needed; tests a static class constant.

        Action:
        Access Config.ENV_MAX_SESSION_DURATION to read the constant value.

        Assertion Strategy:
        Validates the constant equals "AI_MAX_SESSION_DURATION_HOURS", confirming:
        - The env var name hasn't been accidentally renamed.
        - Deployment documentation and scripts remain accurate.

        Testing Principle:
        Validates a contract constant that bridges code and infrastructure,
        preventing silent configuration breakage.
        """
        assert Config.ENV_MAX_SESSION_DURATION == "AI_MAX_SESSION_DURATION_HOURS"


class TestOutputDirConfig:
    """Tests for AI_OUTPUT_DIR configuration."""

    def setup_method(self) -> None:
        """Reset test overrides before each test for isolation.

        Clears any lingering configuration overrides to ensure each test
        starts with a clean, default configuration state.

        Business context:
        Output directory configuration affects where session data is written.
        Leaking an override between tests could cause false positives where
        a test passes due to state left by a previous test.

        Arrangement:
        1. Call Config.reset_test_overrides() to clear all override fields.

        Action:
        Resets _output_dir_override and _max_session_duration_override to None.

        Testing Principle:
        Ensures test isolation by establishing a known-clean state before
        each test method executes.

        Args:
            self: TestOutputDirConfig instance (implicit).

        Returns:
            None.

        Raises:
            No exceptions raised by this method.

        Example:
            Called automatically by pytest before each test method.
        """
        Config.reset_test_overrides()

    def teardown_method(self) -> None:
        """Reset test overrides after each test for cleanup.

        Ensures any overrides set during a test are cleared, preventing
        pollution of subsequent tests even if the test fails.

        Business context:
        Post-test cleanup is a safety net complementing setup_method. It
        handles cases where a test sets overrides but doesn't clean up,
        ensuring reliable test suite execution.

        Arrangement:
        1. Called automatically by pytest after each test method completes.

        Action:
        Calls Config.reset_test_overrides() to clear all override fields.

        Testing Principle:
        Provides belt-and-suspenders test isolation, guaranteeing cleanup
        even when tests fail or raise unexpected exceptions.

        Args:
            self: TestOutputDirConfig instance (implicit).

        Returns:
            None.

        Raises:
            No exceptions raised by this method.

        Example:
            Called automatically by pytest after each test method.
        """
        Config.reset_test_overrides()

    def test_output_dir_returns_none_by_default(self) -> None:
        """Verifies get_output_dir returns None when no environment variable is set.

        Tests the default behavior when AI_OUTPUT_DIR is absent from the
        environment, indicating no custom output directory is configured.

        Business context:
        When no output directory is configured, the application uses its
        default storage location. Returning None signals this default
        behavior to callers, who can then apply their own fallback logic.

        Arrangement:
        1. Patch environment to clear all variables, simulating a
           deployment with no AI_OUTPUT_DIR configured.

        Action:
        Call Config.get_output_dir() in the clean environment to test
        the default return value.

        Assertion Strategy:
        Validates the result is None, confirming:
        - Absence of the env var produces None, not empty string.
        - Callers can reliably use ``is None`` checks for default behavior.

        Testing Principle:
        Validates the zero-config default path, ensuring the application
        works without requiring AI_OUTPUT_DIR to be set.
        """
        with patch.dict(os.environ, {}, clear=True):
            assert Config.get_output_dir() is None

    def test_output_dir_from_env_var(self) -> None:
        """Verifies get_output_dir reads the AI_OUTPUT_DIR environment variable.

        Tests that a set AI_OUTPUT_DIR environment variable is correctly
        returned by the accessor, enabling deployment-specific output paths.

        Business context:
        Different deployments may store session data on shared drives,
        cloud mounts, or team-specific directories. The AI_OUTPUT_DIR
        env var enables this flexibility without code changes.

        Arrangement:
        1. Patch environment with AI_OUTPUT_DIR="/mnt/share/jsmith" to
           simulate a configured deployment.

        Action:
        Call Config.get_output_dir() to retrieve the configured path.

        Assertion Strategy:
        Validates the result equals "/mnt/share/jsmith", confirming:
        - The env var value is returned verbatim without modification.
        - Path strings are preserved exactly as configured.

        Testing Principle:
        Validates environment-based configuration for output directory,
        ensuring operator-specified paths are respected.
        """
        with patch.dict(os.environ, {"AI_OUTPUT_DIR": "/mnt/share/jsmith"}):
            assert Config.get_output_dir() == "/mnt/share/jsmith"

    def test_output_dir_empty_env_var_returns_none(self) -> None:
        """Verifies an empty AI_OUTPUT_DIR environment variable returns None.

        Tests that an empty string env var is treated as unset, producing
        the same None result as a completely absent variable.

        Business context:
        Operators may set AI_OUTPUT_DIR="" to explicitly disable custom
        output paths, or it may be empty due to misconfiguration. Either
        way, the system should treat it as unset and use defaults.

        Arrangement:
        1. Patch environment with AI_OUTPUT_DIR="" to simulate an empty
           but present environment variable.

        Action:
        Call Config.get_output_dir() with the empty env var to test
        the empty-string handling.

        Assertion Strategy:
        Validates the result is None, confirming:
        - Empty strings are normalized to None, not passed through.
        - Callers don't need to handle both None and "" cases.

        Testing Principle:
        Validates edge case handling for empty configuration values,
        ensuring consistent None semantics for unset/empty states.
        """
        with patch.dict(os.environ, {"AI_OUTPUT_DIR": ""}):
            assert Config.get_output_dir() is None

    def test_output_dir_test_override(self) -> None:
        """Verifies test override takes precedence over the AI_OUTPUT_DIR env var.

        Tests the configuration resolution priority when both a test override
        and an environment variable provide competing output directory values.

        Business context:
        During testing, overrides must win to provide deterministic behavior
        regardless of the CI/CD environment. This prevents flaky tests
        caused by environment variables set on build servers.

        Arrangement:
        1. Set test override to output_dir="/override/path" via set_test_overrides.
        2. Patch environment with AI_OUTPUT_DIR="/env/path" to create a
           competing configuration source.

        Action:
        Call Config.get_output_dir() with both sources active to verify
        the priority resolution.

        Assertion Strategy:
        Validates the result equals "/override/path", confirming:
        - Override value wins over env var value.
        - The resolution chain correctly prioritizes override > env var.

        Testing Principle:
        Validates configuration precedence rules for output directory,
        mirroring the same override > env var > default chain used by
        max_session_duration.
        """
        Config.set_test_overrides(output_dir="/override/path")
        with patch.dict(os.environ, {"AI_OUTPUT_DIR": "/env/path"}):
            assert Config.get_output_dir() == "/override/path"

    def test_output_dir_env_var_constant(self) -> None:
        """Verifies the output directory environment variable name constant is correct.

        Tests that ENV_OUTPUT_DIR holds the expected string "AI_OUTPUT_DIR",
        which is the contract between the application and deployment environment.

        Business context:
        The env var name is referenced in deployment documentation, Docker
        compose files, and CI/CD pipelines. Accidentally renaming it would
        break existing deployments that rely on AI_OUTPUT_DIR.

        Arrangement:
        1. No setup needed; tests a static class constant.

        Action:
        Access Config.ENV_OUTPUT_DIR to read the constant value.

        Assertion Strategy:
        Validates the constant equals "AI_OUTPUT_DIR", confirming:
        - The env var name hasn't been accidentally renamed.
        - Infrastructure configurations remain compatible.

        Testing Principle:
        Validates a contract constant that bridges code and infrastructure,
        preventing silent configuration breakage in deployments.
        """
        assert Config.ENV_OUTPUT_DIR == "AI_OUTPUT_DIR"

    def test_reset_clears_output_dir_override(self) -> None:
        """Verifies reset_test_overrides clears the output_dir override field.

        Tests that calling reset_test_overrides after setting an output_dir
        override correctly restores the field to None.

        Business context:
        The reset mechanism is fundamental to test isolation. If output_dir
        overrides leak between tests, subsequent tests may read/write session
        data to unexpected locations, causing false passes or failures.

        Arrangement:
        1. Set test override to output_dir="/some/path" to create state
           that needs to be cleaned up.

        Action:
        Call Config.reset_test_overrides() to clear all override fields.

        Assertion Strategy:
        Validates _output_dir_override is None after reset, confirming:
        - The reset method specifically clears the output_dir field.
        - The override is fully removed, not just set to empty string.

        Testing Principle:
        Validates the cleanup mechanism for output directory overrides,
        ensuring reliable test isolation across the test suite.
        """
        Config.set_test_overrides(output_dir="/some/path")
        Config.reset_test_overrides()
        assert Config._output_dir_override is None

    def test_context_manager_sets_output_dir(self) -> None:
        """Verifies the context manager sets and automatically resets output_dir.

        Tests that override_for_test context manager applies the output_dir
        override within its scope and performs automatic cleanup on exit.

        Business context:
        The context manager pattern ensures test overrides are always cleaned
        up, even if the test raises an exception. This is especially important
        for output_dir since a leaked override could direct file writes to
        unintended locations in subsequent tests.

        Arrangement:
        1. No explicit setup; context manager manages its own lifecycle.

        Action:
        Enter Config.override_for_test with output_dir="/ctx/path", verify
        the override is active inside, then verify cleanup after exit.

        Assertion Strategy:
        Validates behavior at two lifecycle points, confirming:
        - Inside context: get_output_dir() returns "/ctx/path".
        - After context exit: _output_dir_override is None, confirming
          automatic cleanup occurred.

        Testing Principle:
        Validates RAII-style resource management for output directory
        overrides, ensuring both application and cleanup phases work.
        """
        with Config.override_for_test(output_dir="/ctx/path"):
            assert Config.get_output_dir() == "/ctx/path"
        assert Config._output_dir_override is None
