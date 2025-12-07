"""Tests for config module."""

from __future__ import annotations

import os
from unittest.mock import patch

from ai_session_tracker_mcp.config import Config


class TestConfigConstants:
    """Tests for static configuration values."""

    def test_storage_dir_value(self) -> None:
        """Storage directory has expected value."""
        assert Config.STORAGE_DIR == ".ai_sessions"

    def test_sessions_file_value(self) -> None:
        """Sessions file has expected value."""
        assert Config.SESSIONS_FILE == "sessions.json"

    def test_interactions_file_value(self) -> None:
        """Interactions file has expected value."""
        assert Config.INTERACTIONS_FILE == "interactions.json"

    def test_issues_file_value(self) -> None:
        """Issues file has expected value."""
        assert Config.ISSUES_FILE == "issues.json"

    def test_charts_dir_value(self) -> None:
        """Charts directory has expected value."""
        assert Config.CHARTS_DIR == "charts"

    def test_human_hourly_rate_default(self) -> None:
        """Human hourly rate has default value."""
        assert Config.HUMAN_HOURLY_RATE == 130.0

    def test_ai_monthly_cost_default(self) -> None:
        """AI monthly cost has default value."""
        assert Config.AI_MONTHLY_COST == 40.0

    def test_working_hours_per_month_default(self) -> None:
        """Working hours per month has default value."""
        assert Config.WORKING_HOURS_PER_MONTH == 160.0

    def test_mcp_version_value(self) -> None:
        """MCP version has expected value."""
        assert Config.MCP_VERSION == "2024-11-05"

    def test_server_name_value(self) -> None:
        """Server name has expected value."""
        assert Config.SERVER_NAME == "ai-session-tracker"

    def test_server_version_value(self) -> None:
        """Server version has expected value."""
        assert Config.SERVER_VERSION == "0.1.0"

    def test_task_types_is_frozenset(self) -> None:
        """Task types is a frozen set."""
        assert isinstance(Config.TASK_TYPES, frozenset)

    def test_task_types_contains_expected_values(self) -> None:
        """Task types contains expected categories."""
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
        """Human review is excluded from ROI."""
        assert "human_review" in Config.EXCLUDED_FROM_ROI

    def test_severity_levels_is_frozenset(self) -> None:
        """Severity levels is a frozen set."""
        assert isinstance(Config.SEVERITY_LEVELS, frozenset)

    def test_severity_levels_contains_expected_values(self) -> None:
        """Severity levels contains expected categories."""
        expected = {"low", "medium", "high", "critical"}
        assert expected == Config.SEVERITY_LEVELS


class TestConfigComputedProperties:
    """Tests for computed configuration values."""

    def test_ai_hourly_rate_calculation(self) -> None:
        """AI hourly rate is correctly calculated."""
        expected = Config.AI_MONTHLY_COST / Config.WORKING_HOURS_PER_MONTH
        assert Config.ai_hourly_rate() == expected
        assert Config.ai_hourly_rate() == 0.25

    def test_roi_multiplier_calculation(self) -> None:
        """ROI multiplier is correctly calculated."""
        expected = Config.HUMAN_HOURLY_RATE / Config.ai_hourly_rate()
        assert Config.roi_multiplier() == expected
        assert Config.roi_multiplier() == 520.0


class TestConfigEnvironmentSettings:
    """Tests for environment-based configuration."""

    def setup_method(self) -> None:
        """Reset test overrides before each test."""
        Config.reset_test_overrides()

    def teardown_method(self) -> None:
        """Reset test overrides after each test."""
        Config.reset_test_overrides()

    def test_s3_backup_disabled_by_default(self) -> None:
        """S3 backup is disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            assert Config.is_s3_backup_enabled() is False

    def test_s3_backup_enabled_via_env_var(self) -> None:
        """S3 backup can be enabled via environment variable."""
        with patch.dict(os.environ, {"AI_ENABLE_S3_BACKUP": "true"}):
            assert Config.is_s3_backup_enabled() is True

    def test_s3_backup_env_var_case_insensitive(self) -> None:
        """S3 backup env var is case insensitive."""
        with patch.dict(os.environ, {"AI_ENABLE_S3_BACKUP": "TRUE"}):
            assert Config.is_s3_backup_enabled() is True

    def test_s3_backup_false_for_other_values(self) -> None:
        """S3 backup false for non-true values."""
        with patch.dict(os.environ, {"AI_ENABLE_S3_BACKUP": "yes"}):
            assert Config.is_s3_backup_enabled() is False

    def test_s3_backup_test_override_true(self) -> None:
        """Test override can enable S3 backup."""
        Config.set_test_overrides(s3_enabled=True)
        assert Config.is_s3_backup_enabled() is True

    def test_s3_backup_test_override_false(self) -> None:
        """Test override can disable S3 backup."""
        with patch.dict(os.environ, {"AI_ENABLE_S3_BACKUP": "true"}):
            Config.set_test_overrides(s3_enabled=False)
            assert Config.is_s3_backup_enabled() is False

    def test_project_id_uses_cwd_by_default(self) -> None:
        """Project ID defaults to current directory name."""
        with patch.dict(os.environ, {}, clear=True):
            expected = os.path.basename(os.getcwd())
            assert Config.get_project_id() == expected

    def test_project_id_from_env_var(self) -> None:
        """Project ID can be set via environment variable."""
        with patch.dict(os.environ, {"AI_PROJECT_ID": "my-project"}):
            assert Config.get_project_id() == "my-project"

    def test_project_id_test_override(self) -> None:
        """Test override can set project ID."""
        Config.set_test_overrides(project_id="test-project")
        assert Config.get_project_id() == "test-project"

    def test_reset_test_overrides_clears_all(self) -> None:
        """Reset clears all test overrides."""
        Config.set_test_overrides(s3_enabled=True, project_id="test")
        Config.reset_test_overrides()
        assert Config._s3_backup_override is None
        assert Config._project_id_override is None


class TestConfigFilterProductiveSessions:
    """Tests for session filtering."""

    def test_filter_empty_sessions(self) -> None:
        """Filtering empty dict returns empty dict."""
        result = Config.filter_productive_sessions({})
        assert result == {}

    def test_filter_keeps_productive_sessions(self) -> None:
        """Filtering keeps productive task types."""
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
        """Filtering removes human_review sessions."""
        sessions = {
            "s1": {"task_type": "code_generation"},
            "s2": {"task_type": "human_review"},
        }
        result = Config.filter_productive_sessions(sessions)
        assert len(result) == 1
        assert "s1" in result
        assert "s2" not in result

    def test_filter_handles_missing_task_type(self) -> None:
        """Filtering handles sessions without task_type."""
        sessions = {
            "s1": {"name": "test"},  # No task_type
        }
        result = Config.filter_productive_sessions(sessions)
        assert len(result) == 1
        assert "s1" in result
