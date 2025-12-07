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
        Calculate AI cost per hour.
        Formula: monthly_cost / working_hours = $40 / 160 = $0.25/hour
        """
        return cls.AI_MONTHLY_COST / cls.WORKING_HOURS_PER_MONTH

    @classmethod
    def roi_multiplier(cls) -> float:
        """
        Calculate cost advantage of AI vs human labor.
        Formula: human_rate / ai_rate = $130 / $0.25 = 520x
        Interpretation: AI is 520x cheaper per hour than human developer.
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
        Check if S3 backup is enabled.
        Priority: test override > AI_ENABLE_S3_BACKUP env var > False
        """
        if cls._s3_backup_override is not None:
            return cls._s3_backup_override
        return os.environ.get("AI_ENABLE_S3_BACKUP", "").lower() == "true"

    @classmethod
    def get_project_id(cls) -> str:
        """
        Get project identifier for S3 path organization.
        Priority: test override > AI_PROJECT_ID env var > current directory name
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
        Call reset_test_overrides() in test teardown.
        """
        cls._s3_backup_override = s3_enabled
        cls._project_id_override = project_id

    @classmethod
    def reset_test_overrides(cls) -> None:
        """Reset all test overrides to use environment variables."""
        cls._s3_backup_override = None
        cls._project_id_override = None

    @classmethod
    def filter_productive_sessions(
        cls, sessions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Filter sessions to include only those counting toward ROI.
        Excludes: human_review sessions (oversight time, not AI work).

        Args:
            sessions: Dict of session_id -> session_data

        Returns:
            Filtered dict with non-productive sessions removed.
        """
        return {
            sid: data
            for sid, data in sessions.items()
            if data.get("task_type") not in cls.EXCLUDED_FROM_ROI
        }
