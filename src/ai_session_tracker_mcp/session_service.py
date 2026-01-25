"""
Session Service - shared business logic for session tracking.

PURPOSE: Extract core session operations from MCP server for reuse by CLI.
AI CONTEXT: This is the shared service layer used by both server.py and cli.py.

ARCHITECTURE:
    CLI commands ──┐
                   ├──► SessionService ◄── StorageManager
    MCP handlers ──┘

USAGE:
    from .session_service import SessionService
    service = SessionService()
    result = service.start_session(name="task", ...)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .config import Config
from .models import Interaction, Issue, Session
from .statistics import StatisticsEngine
from .storage import StorageManager

__all__ = [
    "SessionService",
    "ServiceResult",
]

logger = logging.getLogger(__name__)


@dataclass
class ServiceResult:
    """
    Result from a service operation.

    Provides a consistent return type for all service methods with
    success/failure status and optional data or error message.

    Attributes:
        success: Whether the operation completed successfully.
        message: Human-readable result message.
        data: Optional dict with operation-specific data.
        error: Optional error message if success is False.
    """

    success: bool
    message: str
    data: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {
            "success": self.success,
            "message": self.message,
        }
        if self.data:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        return result


class SessionService:
    """
    Core session tracking service.

    Provides all session tracking operations as pure business logic,
    separated from both MCP protocol handling and CLI argument parsing.
    Used by both server.py (MCP handlers) and cli.py (CLI commands).

    OPERATIONS:
    - start_session: Create a new tracking session
    - log_interaction: Record a prompt/response exchange
    - end_session: Complete a session with outcome
    - flag_issue: Record a problematic interaction
    - get_active_sessions: List sessions that haven't ended
    - get_observability: Generate analytics report

    Example:
        >>> service = SessionService()
        >>> result = service.start_session(
        ...     name="Add login feature",
        ...     task_type="code_generation",
        ...     model_name="claude-opus-4-20250514",
        ...     human_time_estimate_minutes=60,
        ...     estimate_source="manual",
        ... )
        >>> print(result.data["session_id"])
    """

    def __init__(
        self,
        storage: StorageManager | None = None,
        stats_engine: StatisticsEngine | None = None,
    ) -> None:
        """
        Initialize the session service.

        Args:
            storage: Optional StorageManager for persistence. Creates
                new instance with defaults if not provided.
            stats_engine: Optional StatisticsEngine for metrics. Creates
                new instance with defaults if not provided.
        """
        self.storage = storage or StorageManager()
        self.stats_engine = stats_engine or StatisticsEngine()

    def _auto_close_active_sessions(self) -> list[str]:
        """
        Auto-close any active sessions before starting a new one.

        Finds all sessions with status 'active' and closes them with
        outcome 'partial' and a note indicating they were auto-closed.

        Returns:
            list[str]: List of session IDs that were auto-closed.
        """
        closed_sessions = []
        try:
            sessions = self.storage.load_sessions()
            for session_id, session_data in sessions.items():
                if session_data.get("status") == "active":
                    session_data["status"] = "completed"
                    session_data["end_time"] = datetime.now(UTC).isoformat()
                    session_data["outcome"] = "partial"
                    session_data["notes"] = (
                        session_data.get("notes", "") + " [Auto-closed: new session started]"
                    ).strip()
                    sessions[session_id] = session_data
                    closed_sessions.append(session_id)
                    logger.warning(f"Auto-closed active session: {session_id}")

            if closed_sessions:
                self.storage.save_sessions(sessions)

        except Exception as e:
            logger.error(f"Error auto-closing sessions: {e}")

        return closed_sessions

    def start_session(
        self,
        name: str,
        task_type: str,
        model_name: str,
        human_time_estimate_minutes: float,
        estimate_source: str,
        context: str = "",
    ) -> ServiceResult:
        """
        Start a new tracking session.

        Creates a new session with a unique ID and persists it to storage.
        Automatically closes any previously active sessions.

        Args:
            name: Descriptive name for the task.
            task_type: Category from Config.TASK_TYPES.
            model_name: AI model being used.
            human_time_estimate_minutes: Baseline time estimate.
            estimate_source: 'manual', 'issue_tracker', or 'historical'.
            context: Optional additional context string.

        Returns:
            ServiceResult with session_id in data on success.
        """
        try:
            # Validate task_type
            if task_type not in Config.TASK_TYPES:
                return ServiceResult(
                    success=False,
                    message="Invalid task type",
                    error=f"task_type must be one of: {', '.join(sorted(Config.TASK_TYPES))}",
                )

            # Validate estimate_source
            valid_sources = {"manual", "issue_tracker", "historical"}
            if estimate_source not in valid_sources:
                return ServiceResult(
                    success=False,
                    message="Invalid estimate source",
                    error=f"estimate_source must be one of: {', '.join(sorted(valid_sources))}",
                )

            # Auto-close any active sessions first
            auto_closed = self._auto_close_active_sessions()

            session = Session.create(
                name=name,
                task_type=task_type,
                model_name=model_name,
                human_time_estimate_minutes=float(human_time_estimate_minutes),
                estimate_source=estimate_source,
                context=context,
            )

            sessions = self.storage.load_sessions()
            sessions[session.id] = session.to_dict()
            self.storage.save_sessions(sessions)

            logger.info(f"Started session: {session.id}")

            return ServiceResult(
                success=True,
                message=f"Session started: {session.id}",
                data={
                    "session_id": session.id,
                    "task_type": session.task_type,
                    "model_name": session.model_name,
                    "human_time_estimate_minutes": session.human_time_estimate_minutes,
                    "estimate_source": session.estimate_source,
                    "auto_closed_sessions": auto_closed,
                },
            )

        except Exception as e:
            logger.error(f"Error starting session: {e}")
            return ServiceResult(
                success=False,
                message="Failed to start session",
                error=str(e),
            )

    def log_interaction(
        self,
        session_id: str,
        prompt: str,
        response_summary: str,
        effectiveness_rating: int,
        iteration_count: int = 1,
        tools_used: list[str] | None = None,
    ) -> ServiceResult:
        """
        Log an AI prompt/response interaction.

        Records the interaction and updates session statistics.

        Args:
            session_id: Parent session identifier.
            prompt: The prompt text sent to AI.
            response_summary: Brief description of AI response.
            effectiveness_rating: Integer 1-5.
            iteration_count: Number of attempts, default 1.
            tools_used: List of MCP tools used.

        Returns:
            ServiceResult with interaction stats on success.
        """
        try:
            session_data = self.storage.get_session(session_id)
            if not session_data:
                return ServiceResult(
                    success=False,
                    message="Session not found",
                    error=f"No session with ID: {session_id}",
                )

            interaction = Interaction.create(
                session_id=session_id,
                prompt=prompt,
                response_summary=response_summary,
                effectiveness_rating=effectiveness_rating,
                iteration_count=iteration_count,
                tools_used=tools_used or [],
            )

            self.storage.add_interaction(interaction.to_dict())

            # Update session statistics
            session_interactions = self.storage.get_session_interactions(session_id)
            total = len(session_interactions)
            avg_eff = sum(i["effectiveness_rating"] for i in session_interactions) / total

            session_data["total_interactions"] = total
            session_data["avg_effectiveness"] = round(avg_eff, 2)
            self.storage.update_session(session_id, session_data)

            logger.info(
                f"Logged interaction for session {session_id}, "
                f"rating: {interaction.effectiveness_rating}"
            )

            return ServiceResult(
                success=True,
                message=f"Interaction logged (rating: {effectiveness_rating}/5)",
                data={
                    "effectiveness_rating": effectiveness_rating,
                    "iteration_count": iteration_count,
                    "total_interactions": total,
                    "avg_effectiveness": round(avg_eff, 2),
                },
            )

        except Exception as e:
            logger.error(f"Error logging interaction: {e}")
            return ServiceResult(
                success=False,
                message="Failed to log interaction",
                error=str(e),
            )

    def end_session(
        self,
        session_id: str,
        outcome: str,
        notes: str = "",
    ) -> ServiceResult:
        """
        End a tracking session.

        Marks the session as completed with end timestamp and outcome.

        Args:
            session_id: Session identifier to complete.
            outcome: 'success', 'partial', or 'failed'.
            notes: Optional summary notes.

        Returns:
            ServiceResult with session summary on success.
        """
        try:
            # Validate outcome
            valid_outcomes = {"success", "partial", "failed"}
            if outcome not in valid_outcomes:
                return ServiceResult(
                    success=False,
                    message="Invalid outcome",
                    error=f"outcome must be one of: {', '.join(sorted(valid_outcomes))}",
                )

            session_data = self.storage.get_session(session_id)
            if not session_data:
                return ServiceResult(
                    success=False,
                    message="Session not found",
                    error=f"No session with ID: {session_id}",
                )

            # Update session
            session_data["status"] = "completed"
            session_data["end_time"] = datetime.now(UTC).isoformat()
            session_data["outcome"] = outcome
            session_data["notes"] = notes

            self.storage.update_session(session_id, session_data)

            # Calculate duration
            duration = self.stats_engine.calculate_session_duration_minutes(session_data)

            # Get session issues
            issues = self.storage.get_session_issues(session_id)

            logger.info(f"Ended session {session_id}, outcome: {outcome}")

            return ServiceResult(
                success=True,
                message=f"Session ended: {session_id}",
                data={
                    "session_id": session_id,
                    "outcome": outcome,
                    "duration_minutes": round(duration, 1),
                    "total_interactions": session_data.get("total_interactions", 0),
                    "avg_effectiveness": session_data.get("avg_effectiveness", 0),
                    "issues_count": len(issues),
                },
            )

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return ServiceResult(
                success=False,
                message="Failed to end session",
                error=str(e),
            )

    def flag_issue(
        self,
        session_id: str,
        issue_type: str,
        description: str,
        severity: str,
    ) -> ServiceResult:
        """
        Flag a problematic AI interaction.

        Records an issue with type and severity for later analysis.

        Args:
            session_id: Parent session identifier.
            issue_type: Category (e.g., 'hallucination', 'incorrect_output').
            description: Detailed description of the problem.
            severity: 'low', 'medium', 'high', or 'critical'.

        Returns:
            ServiceResult on success.
        """
        try:
            # Validate severity
            if severity not in Config.SEVERITY_LEVELS:
                return ServiceResult(
                    success=False,
                    message="Invalid severity",
                    error=f"severity must be one of: {', '.join(sorted(Config.SEVERITY_LEVELS))}",
                )

            session_data = self.storage.get_session(session_id)
            if not session_data:
                return ServiceResult(
                    success=False,
                    message="Session not found",
                    error=f"No session with ID: {session_id}",
                )

            issue = Issue.create(
                session_id=session_id,
                issue_type=issue_type,
                description=description,
                severity=severity,
            )

            self.storage.add_issue(issue.to_dict())

            logger.info(f"Flagged issue for session {session_id}: {issue_type} ({severity})")

            return ServiceResult(
                success=True,
                message=f"Issue flagged: {issue_type} ({severity})",
                data={
                    "issue_type": issue_type,
                    "severity": severity,
                    "session_id": session_id,
                },
            )

        except Exception as e:
            logger.error(f"Error flagging issue: {e}")
            return ServiceResult(
                success=False,
                message="Failed to flag issue",
                error=str(e),
            )

    def get_active_sessions(self) -> ServiceResult:
        """
        Get list of currently active sessions.

        Returns sessions that haven't been ended yet.

        Returns:
            ServiceResult with list of active sessions.
        """
        try:
            sessions = self.storage.load_sessions()
            active_sessions = []

            for session_id, session in sessions.items():
                if session.get("status") != "completed":
                    active_sessions.append(
                        {
                            "session_id": session_id,
                            "session_name": session.get("session_name", "Unknown"),
                            "task_type": session.get("task_type", "Unknown"),
                            "start_time": session.get("start_time", "Unknown"),
                        }
                    )

            return ServiceResult(
                success=True,
                message=f"Found {len(active_sessions)} active session(s)",
                data={"active_sessions": active_sessions},
            )

        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return ServiceResult(
                success=False,
                message="Failed to get active sessions",
                error=str(e),
            )

    def get_observability(
        self,
        session_id: str | None = None,
        time_range: str = "all",  # noqa: ARG002 - reserved for future time filtering
    ) -> ServiceResult:
        """
        Generate analytics report.

        Returns comprehensive metrics including ROI, effectiveness,
        and issue summaries.

        Args:
            session_id: Optional filter to specific session.
            time_range: Time filter ('last_day', 'last_week', 'all').

        Returns:
            ServiceResult with report text.
        """
        try:
            sessions = self.storage.load_sessions()
            interactions = self.storage.load_interactions()
            issues = self.storage.load_issues()

            # Filter by session if specified
            if session_id:
                if session_id not in sessions:
                    return ServiceResult(
                        success=False,
                        message="Session not found",
                        error=f"No session with ID: {session_id}",
                    )
                sessions = {session_id: sessions[session_id]}
                interactions = [i for i in interactions if i.get("session_id") == session_id]
                issues = [i for i in issues if i.get("session_id") == session_id]

            # Generate report
            report = self.stats_engine.generate_summary_report(sessions, interactions, issues)

            return ServiceResult(
                success=True,
                message="Report generated",
                data={"report": report},
            )

        except Exception as e:
            logger.error(f"Error generating observability report: {e}")
            return ServiceResult(
                success=False,
                message="Failed to generate report",
                error=str(e),
            )

    def close_active_sessions_on_shutdown(self) -> int:
        """
        Close all active sessions on shutdown.

        Marks active sessions as completed with outcome 'partial'.

        Returns:
            int: Number of sessions closed.
        """
        try:
            sessions = self.storage.load_sessions()
            active_count = 0

            for session_id, session_data in sessions.items():
                if session_data.get("status") == "active":
                    session_data["status"] = "completed"
                    session_data["end_time"] = datetime.now(UTC).isoformat()
                    session_data["outcome"] = "partial"
                    session_data["notes"] = (
                        session_data.get("notes", "") + " [Auto-closed on server shutdown]"
                    ).strip()
                    sessions[session_id] = session_data
                    active_count += 1
                    logger.info(f"Auto-closed active session: {session_id}")

            if active_count > 0:
                self.storage.save_sessions(sessions)
                logger.info(f"Auto-closed {active_count} active session(s) on shutdown")

            return active_count

        except Exception as e:
            logger.error(f"Error closing active sessions: {e}")
            return 0
