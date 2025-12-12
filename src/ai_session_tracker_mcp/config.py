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
- AI_ENABLE_S3_BACKUP: "true" to enable S3 backup (default: disabled)
- AI_PROJECT_ID: Project identifier for S3 paths (default: current directory name)

USAGE:
    from ai_session_tracker_mcp.config import Config
    storage_dir = Config.STORAGE_DIR
    hourly_rate = Config.HUMAN_HOURLY_RATE
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, ClassVar


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
    SERVER_VERSION: ClassVar[str] = "0.1.0"

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
    _s3_backup_override: ClassVar[bool | None] = None
    _project_id_override: ClassVar[str | None] = None

    @classmethod
    def is_s3_backup_enabled(cls) -> bool:
        """
        Check if S3 backup functionality is enabled.

        Checks for S3 backup enablement using a priority system: test
        overrides take precedence, then environment variable, then defaults
        to False (disabled).

        Business context: S3 backup provides off-site storage for session
        data. Disabled by default to avoid unexpected cloud costs; enable
        via environment variable for production deployments.

        Args:
            None: Class method, accesses class variable and env var.

        Returns:
            True if S3 backup is enabled, False otherwise.

        Raises:
            None: Environment lookup never raises.

        Example:
            >>> # With env var: AI_ENABLE_S3_BACKUP=true
            >>> Config.is_s3_backup_enabled()
            True
        """
        if cls._s3_backup_override is not None:
            return cls._s3_backup_override
        return os.environ.get("AI_ENABLE_S3_BACKUP", "").lower() == "true"

    @classmethod
    def get_project_id(cls) -> str:
        """
        Get the project identifier for organizing S3 backup paths.

        Uses a priority system: test overrides first, then environment
        variable, then falls back to the current directory name. Used to
        partition S3 storage by project.

        Business context: Project IDs keep session data organized when
        backing up multiple projects to the same S3 bucket. Defaults to
        directory name for zero-configuration setup.

        Args:
            None: Class method, accesses class variable and env var.

        Returns:
            Project identifier string, typically the project directory name.

        Raises:
            None: Environment and path operations never raise.

        Example:
            >>> # In /home/user/my-project:
            >>> Config.get_project_id()
            'my-project'
        """
        if cls._project_id_override is not None:
            return cls._project_id_override
        return os.environ.get("AI_PROJECT_ID", os.path.basename(os.getcwd()))

    @classmethod
    def set_test_overrides(
        cls,
        s3_enabled: bool | None = None,
        project_id: str | None = None,
    ) -> None:
        """
        Set test overrides for environment-based settings.

        Allows tests to control S3 and project ID settings without
        modifying environment variables. Must call reset_test_overrides()
        in test teardown to avoid affecting other tests.

        Business context: Test isolation requires deterministic configuration.
        This method enables testing S3 backup logic without requiring actual
        AWS credentials or environment variable manipulation.

        Args:
            s3_enabled: Override for S3 backup enabled flag. None to clear.
            project_id: Override for project identifier. None to clear.

        Returns:
            None. Modifies class-level state.

        Example:
            >>> Config.set_test_overrides(s3_enabled=True, project_id='test-project')
            >>> Config.is_s3_backup_enabled()
            True
            >>> Config.reset_test_overrides()  # Clean up
        """
        cls._s3_backup_override = s3_enabled
        cls._project_id_override = project_id

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
            >>> Config.set_test_overrides(s3_enabled=True)
            >>> # ... run tests ...
            >>> Config.reset_test_overrides()  # Always in teardown
        """
        cls._s3_backup_override = None
        cls._project_id_override = None

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
