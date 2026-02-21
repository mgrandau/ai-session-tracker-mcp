"""
Configuration for AI Session Tracker MCP Server.

PURPOSE: Centralized configuration constants and runtime settings.
AI CONTEXT: All configurable values live here - modify this file to change behavior.

CONFIGURATION CATEGORIES:
- Storage: File paths and directory structure
- ROI Calculation: Cost parameters for human vs AI comparison
- MCP Protocol: Server identity and protocol version
- Session Types: Valid task categories and exclusion rules

ENVIRONMENT VARIABLES:
- AI_MAX_SESSION_DURATION_HOURS: Cap session duration in hours (default: 4.0)
- AI_OUTPUT_DIR: Redirect session data to a custom directory

USAGE:
    from ai_session_tracker_mcp.config import Config
    storage_dir = Config.STORAGE_DIR
    hourly_rate = Config.HUMAN_HOURLY_RATE
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, ClassVar

from ai_session_tracker_mcp.__version__ import __version__


@dataclass(frozen=True)
class Config:
    """
    Immutable configuration container for AI Session Tracker.

    DESIGN: Frozen dataclass ensures configuration immutability at runtime.
    All values are class-level constants - no instance creation needed.

    COST MODEL ASSUMPTIONS:
    - Human hourly rate includes: salary + benefits (30%) + overhead (40%)
    - AI cost assumes 160 working hours/month (40hr/week * 4 weeks)
    - ROI multiplier = human_rate / ai_rate ≈ 520x with defaults

    STORAGE STRUCTURE:
        .ai_sessions/
        ├── sessions.json      # Session registry {id: metadata}
        ├── interactions.json  # Interaction log [entries]
        ├── issues.json        # Flagged issues [entries]
        └── charts/            # Generated visualizations
    """

    # =========================================================================
    # STORAGE CONFIGURATION
    # =========================================================================
    STORAGE_DIR: ClassVar[str] = ".ai_sessions"
    SESSIONS_FILE: ClassVar[str] = "sessions.json"
    INTERACTIONS_FILE: ClassVar[str] = "interactions.json"
    ISSUES_FILE: ClassVar[str] = "issues.json"
    CHARTS_DIR: ClassVar[str] = "charts"

    # =========================================================================
    # ROI CALCULATION PARAMETERS
    # =========================================================================
    HUMAN_HOURLY_RATE: ClassVar[float] = 130.0
    """
    Fully-burdened developer cost (USD/hour).
    Components: base salary ($50) + benefits ($15) + overhead ($40) + training ($25)
    Adjust for: geographic region, experience level, organization costs.
    """

    AI_MONTHLY_COST: ClassVar[float] = 40.0
    """
    Monthly AI subscription cost (USD).
    Assumes: Copilot ($20) + ChatGPT/Claude ($20) = $40 baseline.
    Adjust for: enterprise tiers, additional AI tools.
    """

    WORKING_HOURS_PER_MONTH: ClassVar[float] = 160.0
    """Standard FTE hours: 40 hours/week * 4 weeks."""

    # =========================================================================
    # MCP PROTOCOL CONFIGURATION
    # =========================================================================
    MCP_VERSION: ClassVar[str] = "2024-11-05"
    SERVER_NAME: ClassVar[str] = "ai-session-tracker"
    SERVER_VERSION: ClassVar[str] = __version__

    # =========================================================================
    # SESSION TYPE CONSTANTS
    # =========================================================================
    TASK_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "code_generation",
            "documentation",
            "debugging",
            "refactoring",
            "testing",
            "analysis",
            "architecture_planning",
            "human_review",  # Excluded from productivity metrics
        }
    )

    EXCLUDED_FROM_ROI: ClassVar[frozenset[str]] = frozenset({"human_review"})
    """
    Task types excluded from productivity calculations.
    human_review: Represents oversight time, not AI productivity.
    """

    # =========================================================================
    # SESSION DURATION LIMITS
    # =========================================================================
    MAX_SESSION_DURATION_HOURS: ClassVar[float] = 4.0
    """
    Maximum session duration in hours for auto-close capping.
    When a session exceeds this duration, end_time is capped at
    start_time + max_duration instead of actual close time.
    Prevents overnight sessions from skewing ROI metrics.
    """

    # =========================================================================
    # ISSUE SEVERITY LEVELS
    # =========================================================================
    SEVERITY_LEVELS: ClassVar[frozenset[str]] = frozenset(
        {
            "low",
            "medium",
            "high",
            "critical",
        }
    )

    # =========================================================================
    # EXECUTION CONTEXT CONSTANTS
    # =========================================================================
    EXECUTION_CONTEXTS: ClassVar[frozenset[str]] = frozenset(
        {
            "foreground",  # Interactive IDE session (VS Code MCP)
            "background",  # CLI/automated agent
        }
    )
    """
    Execution context identifies how/where the AI session is running:
    - foreground: Interactive IDE session via MCP server
    - background: CLI commands, scripts, or automation
    """

    # =========================================================================
    # ENVIRONMENT VARIABLE NAMES
    # =========================================================================
    ENV_MAX_SESSION_DURATION: ClassVar[str] = "AI_MAX_SESSION_DURATION_HOURS"
    """Environment variable to override max session duration (hours)."""

    ENV_OUTPUT_DIR: ClassVar[str] = "AI_OUTPUT_DIR"
    """
    Environment variable to redirect session data to a custom directory.

    When set, StorageManager writes all data to this path instead of
    the default '.ai_sessions' directory. Enables centralized aggregation
    across developers and projects by pointing to a shared location such
    as a synced folder (OneDrive, Dropbox), network share, or git repo.

    Examples:
        AI_OUTPUT_DIR=/mnt/team-share/jsmith/ai-session-tracker-mcp
        AI_OUTPUT_DIR=/home/jsmith/OneDrive/ai-metrics/my-project
    """

    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================
    @classmethod
    def ai_hourly_rate(cls) -> float:
        """
        Calculate the effective hourly cost of AI tools.

        Derives an hourly rate from monthly subscription cost divided by
        standard working hours. Used in ROI calculations to compare AI
        cost against human developer cost.

        Business context: While AI subscriptions are monthly flat fees,
        expressing them as hourly rates enables direct comparison with
        human labor costs for ROI calculations.

        Args:
            None: Class method, accesses class constants only.

        Returns:
            AI cost per hour in USD. With defaults ($40/160h = $0.25/hour).

        Raises:
            None: Division of constants never raises.

        Example:
            >>> Config.ai_hourly_rate()
            0.25
        """
        return cls.AI_MONTHLY_COST / cls.WORKING_HOURS_PER_MONTH

    @classmethod
    def roi_multiplier(cls) -> float:
        """
        Calculate the theoretical cost multiplier of AI vs human labor.

        Computes how many times cheaper AI assistance is compared to human
        developers on a pure hourly cost basis. This is a theoretical
        maximum - actual ROI depends on effectiveness and oversight needs.

        Business context: The multiplier demonstrates the potential value
        of AI tools. With defaults (human=$130/h, AI=$0.25/h), AI is
        theoretically 520x cheaper per hour - though real savings depend
        on AI output quality and required human review time.

        Args:
            None: Class method, accesses class constants only.

        Returns:
            Ratio of human hourly rate to AI hourly rate. Default: 520x.

        Raises:
            None: Division of constants never raises.

        Example:
            >>> Config.roi_multiplier()
            520.0
        """
        return cls.HUMAN_HOURLY_RATE / cls.ai_hourly_rate()

    # =========================================================================
    # ENVIRONMENT-BASED SETTINGS (runtime configurable)
    # =========================================================================
    # NOTE: These ClassVar attributes are intentionally mutable for test injection.
    # ClassVar fields are class-level, not instance-level, so frozen=True doesn't
    # apply to them. This enables deterministic testing without environment variables.
    _max_session_duration_override: ClassVar[float | None] = None
    _output_dir_override: ClassVar[str | None] = None

    @classmethod
    def get_max_session_duration_hours(cls) -> float:
        """
        Get the maximum session duration in hours for auto-close capping.

        Uses a priority system: test overrides first, then environment
        variable, then falls back to the default constant. When sessions
        exceed this duration, their end_time is capped at start_time + max
        to prevent overnight sessions from skewing metrics.

        Business context: Sessions left open overnight would show inflated
        durations (12+ hours). Capping ensures ROI metrics reflect actual
        work time, not idle time.

        Args:
            None: Class method, accesses class variable and env var.

        Returns:
            Maximum session duration in hours. Default: 4.0.

        Example:
            >>> Config.get_max_session_duration_hours()
            4.0
        """
        if cls._max_session_duration_override is not None:
            return cls._max_session_duration_override
        env_value = os.environ.get(cls.ENV_MAX_SESSION_DURATION, "")
        if env_value:
            try:
                return float(env_value)
            except ValueError:
                pass
        return cls.MAX_SESSION_DURATION_HOURS

    @classmethod
    def get_output_dir(cls) -> str | None:
        """
        Get the configured output directory for session data.

        Uses a priority system: test overrides first, then environment
        variable AI_OUTPUT_DIR, then returns None (use default STORAGE_DIR).

        When a non-None value is returned, StorageManager uses it as the
        storage directory instead of '.ai_sessions'.

        Returns:
            Configured output directory path string, or None if not set.

        Example:
            >>> # With env var: AI_OUTPUT_DIR=/mnt/share/jsmith
            >>> Config.get_output_dir()
            '/mnt/share/jsmith'
        """
        if cls._output_dir_override is not None:
            return cls._output_dir_override
        return os.environ.get(cls.ENV_OUTPUT_DIR) or None

    @classmethod
    def set_test_overrides(
        cls,
        max_session_duration: float | None = None,
        output_dir: str | None = None,
    ) -> None:
        """
        Set test overrides for environment-based settings.

        Allows tests to control max session duration and output directory
        without modifying environment variables. Must call
        reset_test_overrides() in test teardown to avoid affecting other tests.

        Business context: Test isolation requires deterministic configuration.
        This method enables testing configuration-dependent logic without
        requiring environment variable manipulation.

        Args:
            max_session_duration: Override for max session duration (hours). None to clear.
            output_dir: Override for output directory path. None to clear.

        Returns:
            None. Modifies class-level state.

        Example:
            >>> Config.set_test_overrides(max_session_duration=2.0)
            >>> Config.get_max_session_duration_hours()
            2.0
            >>> Config.reset_test_overrides()  # Clean up
        """
        cls._max_session_duration_override = max_session_duration
        cls._output_dir_override = output_dir

    @classmethod
    def reset_test_overrides(cls) -> None:
        """
        Reset all test overrides to use environment variables.

        Clears any test overrides set via set_test_overrides(), returning
        configuration methods to their normal behavior of checking
        environment variables. Call this in test teardown.

        Business context: Test cleanup is essential for isolation. This
        method ensures configuration changes in one test don't leak to
        other tests or production code.

        Args:
            None: Class method, modifies class variables.

        Returns:
            None. Modifies class-level state.

        Raises:
            None: Assignment never raises.

        Example:
            >>> Config.set_test_overrides(max_session_duration=2.0)
            >>> # ... run tests ...
            >>> Config.reset_test_overrides()  # Always in teardown
        """
        cls._max_session_duration_override = None
        cls._output_dir_override = None

    @classmethod
    @contextmanager
    def override_for_test(
        cls,
        max_session_duration: float | None = None,
        output_dir: str | None = None,
    ) -> Generator[None]:
        """
        Context manager for test overrides with automatic cleanup.

        Provides a cleaner alternative to set_test_overrides/reset_test_overrides
        for test isolation. Automatically resets overrides on context exit,
        even if an exception occurs.

        Args:
            max_session_duration: Override for max session duration (hours). None to not override.
            output_dir: Override for output directory path. None to not override.

        Yields:
            None. Configuration is modified for the duration of the context.

        Raises:
            No exceptions are raised by this method. Any exceptions from code
            within the context block are propagated after cleanup.

        Example:
            >>> with Config.override_for_test(max_session_duration=2.0):
            ...     assert Config.get_max_session_duration_hours() == 2.0
            >>> # Automatically reset after context exit
        """
        try:
            cls.set_test_overrides(max_session_duration, output_dir)
            yield
        finally:
            cls.reset_test_overrides()

    @classmethod
    def filter_productive_sessions(
        cls, sessions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Filter sessions to include only those counting toward ROI.

        Removes sessions with task types that shouldn't be counted in
        productivity calculations (e.g., 'human_review' which represents
        oversight time, not AI-generated work).

        Business context: ROI calculations should only include actual
        AI-assisted work. Human review sessions track oversight time but
        including them would inflate the 'AI time' metric unfairly.

        Args:
            sessions: Dict of session_id -> session_data containing
                task_type field for each session.

        Returns:
            Filtered dict containing only sessions with productive task types.
            Sessions with task_type in EXCLUDED_FROM_ROI are removed.

        Example:
            >>> sessions = {
            ...     's1': {'task_type': 'code_generation'},
            ...     's2': {'task_type': 'human_review'}
            ... }
            >>> productive = Config.filter_productive_sessions(sessions)
            >>> 's2' in productive
            False
        """
        return {
            sid: data
            for sid, data in sessions.items()
            if data.get("task_type") not in cls.EXCLUDED_FROM_ROI
        }
