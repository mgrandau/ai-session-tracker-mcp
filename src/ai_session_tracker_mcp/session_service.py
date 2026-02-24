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
from datetime import UTC, datetime, timedelta
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
        """Convert this ServiceResult to a JSON-serializable dictionary.

        Produces a minimal dict suitable for MCP protocol responses and CLI
        JSON output. Fields with None/empty values (data, error) are omitted
        to keep payloads compact.

        Args:
            No arguments (self only).

        Returns:
            Dict with keys 'success' (bool) and 'message' (str), plus
            optional 'data' (dict) and 'error' (str) when present.

        Raises:
            No exceptions are raised directly.

        Example:
            >>> result = ServiceResult(success=True, message="Done", data={"id": "abc"})
            >>> result.to_dict()
            {'success': True, 'message': 'Done', 'data': {'id': 'abc'}}
        """
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
        """Initialize the session service with storage and analytics dependencies.

        Creates a ready-to-use service instance. Both dependencies are optional
        to support easy testing (inject mocks) and simple bootstrapping (use
        defaults for production). When omitted, default instances are created
        that read/write to the standard JSON file paths defined in Config.

        This provides the single entry point for all session tracking logic,
        ensuring consistent state management regardless of whether calls
        originate from MCP handlers or CLI commands.

        Args:
            storage: StorageManager handling JSON persistence for sessions,
                interactions, and issues. Defaults to a new StorageManager()
                using Config paths. Pass a custom instance for testing or
                alternative storage backends.
            stats_engine: StatisticsEngine for computing ROI, duration, and
                effectiveness metrics. Defaults to a new StatisticsEngine().
                Pass a custom instance to override calculation behavior.

        Returns:
            None (constructor).

        Raises:
            No exceptions are raised directly. StorageManager and
            StatisticsEngine constructors may raise if underlying file
            system access or configuration is invalid.

        Example:
            >>> service = SessionService()  # production defaults
            >>> service = SessionService(storage=mock_storage)  # testing
        """
        self.storage = storage or StorageManager()
        self.stats_engine = stats_engine or StatisticsEngine()

    def _calculate_capped_end_time(self, start_time_iso: str, note_suffix: str) -> tuple[str, str]:
        """
        Calculate end_time, capping at max duration if exceeded.

        Prevents overnight sessions from skewing metrics by limiting
        the end_time to start_time + max_duration_hours. The purpose of this
        cap is accurate ROI calculations — without it, a developer who
        forgets to close a Friday session would show 60+ hours of AI time.

        Args:
            start_time_iso: Session start time in ISO format.
            note_suffix: Base note to append to (e.g., "new session started").

        Returns:
            Tuple of (end_time_iso, notes) where notes includes duration
            info if session exceeded max duration.

        Raises:
            No exceptions are raised directly. Parsing failures for
            start_time_iso are caught internally and fall back to the
            current UTC time.

        Example:
            >>> end_time, notes = service._calculate_capped_end_time(
            ...     "2025-01-15T08:00:00+00:00", "new session started"
            ... )
            >>> print(notes)
            '[Auto-closed: new session started]'
        """
        now = datetime.now(UTC)
        max_duration_hours = Config.get_max_session_duration_hours()
        max_duration = timedelta(hours=max_duration_hours)

        try:
            # Parse start time - handle both with and without timezone
            start_time = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=UTC)

            max_end_time = start_time + max_duration
            elapsed_hours = (now - start_time).total_seconds() / 3600

            if now > max_end_time:
                # Session exceeded max duration - cap the end_time
                end_time = max_end_time
                notes = (
                    f"[Auto-closed: {note_suffix}, exceeded {max_duration_hours}h max "
                    f"duration (was {elapsed_hours:.1f}h)]"
                )
                logger.info(
                    f"Capped session end_time: actual {elapsed_hours:.1f}h -> {max_duration_hours}h"
                )
            else:
                # Session within limit - use actual time
                end_time = now
                notes = f"[Auto-closed: {note_suffix}]"

            return end_time.isoformat(), notes

        except (ValueError, TypeError) as e:
            # If parsing fails, use current time
            logger.warning(f"Could not parse start_time '{start_time_iso}': {e}")
            return now.isoformat(), f"[Auto-closed: {note_suffix}]"

    def _auto_close_active_sessions(self, execution_context: str) -> list[str]:
        """
        Auto-close any active sessions before starting a new one.

        Finds all sessions with status 'active' and matching execution_context,
        then closes them with outcome 'partial' and a note indicating they
        were auto-closed. Sessions with different execution_context are not
        affected (e.g., foreground sessions won't close background sessions).

        End times are capped at start_time + max_duration_hours to prevent
        overnight sessions from skewing ROI metrics.

        Args:
            execution_context: The context of the new session ('foreground' or
                'background'). Only sessions with matching context are closed.

        Returns:
            list[str]: List of session IDs that were auto-closed.

        Raises:
            No exceptions are raised directly. Storage errors are caught
            internally and logged; an empty list is returned on failure.

        Example:
            >>> closed_ids = service._auto_close_active_sessions("foreground")
            >>> print(f"Auto-closed {len(closed_ids)} session(s)")
        """
        closed_sessions = []
        try:
            sessions = self.storage.load_sessions()
            for session_id, session_data in sessions.items():
                if (
                    session_data.get("status") == "active"
                    and session_data.get("execution_context") == execution_context
                ):
                    start_time = session_data.get("start_time", "")
                    end_time, auto_note = self._calculate_capped_end_time(
                        start_time, "new session started"
                    )

                    session_data["status"] = "completed"
                    session_data["end_time"] = end_time
                    session_data["outcome"] = "partial"
                    session_data["notes"] = (
                        session_data.get("notes", "") + " " + auto_note
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
        execution_context: str = "foreground",
        developer: str = "",
        project: str = "",
    ) -> ServiceResult:
        """
        Start a new tracking session.

        Creates a new session with a unique ID and persists it to storage.
        Automatically closes any previously active sessions with the same
        execution_context.

        Args:
            name: Descriptive name for the task.
            task_type: Category from Config.TASK_TYPES.
            model_name: AI model being used.
            human_time_estimate_minutes: Baseline time estimate.
            estimate_source: 'manual', 'issue_tracker', or 'historical'.
            context: Optional additional context string.
            execution_context: 'foreground' (MCP) or 'background' (CLI).

        Returns:
            ServiceResult with session_id in data on success.

        Raises:
            No exceptions are raised directly. All errors are caught and
            returned as a failed ServiceResult with an error message.

        Example:
            >>> result = service.start_session(
            ...     name="Fix login bug",
            ...     task_type="bug_fix",
            ...     model_name="claude-opus-4-20250514",
            ...     human_time_estimate_minutes=30,
            ...     estimate_source="manual",
            ... )
            >>> print(result.data["session_id"])
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

            # Validate execution_context
            if execution_context not in Config.EXECUTION_CONTEXTS:
                valid_contexts = ", ".join(sorted(Config.EXECUTION_CONTEXTS))
                return ServiceResult(
                    success=False,
                    message="Invalid execution context",
                    error=f"execution_context must be one of: {valid_contexts}",
                )

            # Auto-close any active sessions with same execution_context
            auto_closed = self._auto_close_active_sessions(execution_context)

            session = Session.create(
                name=name,
                task_type=task_type,
                model_name=model_name,
                initial_estimate_minutes=float(human_time_estimate_minutes),
                estimate_source=estimate_source,
                context=context,
                execution_context=execution_context,
                developer=developer,
                project=project,
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
                    "initial_estimate_minutes": session.initial_estimate_minutes,
                    "estimate_source": session.estimate_source,
                    "execution_context": session.execution_context,
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

        Records the interaction and updates session statistics. This provides
        the data pipeline for effectiveness tracking — each logged interaction
        contributes to the session's running average, which drives the ROI
        and quality metrics in observability reports.

        Args:
            session_id: Parent session identifier.
            prompt: The prompt text sent to AI.
            response_summary: Brief description of AI response.
            effectiveness_rating: Integer 1-5.
            iteration_count: Number of attempts, default 1.
            tools_used: List of MCP tools used.

        Returns:
            ServiceResult with interaction stats on success.

        Raises:
            No exceptions are raised directly. All errors are caught and
            returned as a failed ServiceResult with an error message.

        Example:
            >>> result = service.log_interaction(
            ...     session_id="abc-123",
            ...     prompt="Refactor the auth module",
            ...     response_summary="Extracted middleware into separate file",
            ...     effectiveness_rating=4,
            ... )
            >>> print(result.data["avg_effectiveness"])
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
        final_estimate_minutes: float | None = None,
    ) -> ServiceResult:
        """
        End a tracking session.

        Marks the session as completed with end timestamp and outcome. The
        purpose of ending sessions promptly is to ensure accurate duration
        calculations and prevent auto-close from marking them as 'partial'.

        Args:
            session_id: Session identifier to complete.
            outcome: 'success', 'partial', or 'failed'.
            notes: Optional summary notes.
            final_estimate_minutes: Optional revised time estimate after
                completing the task, used to improve future estimates.

        Returns:
            ServiceResult with session summary on success.

        Raises:
            No exceptions are raised directly. All errors are caught and
            returned as a failed ServiceResult with an error message.

        Example:
            >>> result = service.end_session(
            ...     session_id="abc-123",
            ...     outcome="success",
            ...     notes="Completed ahead of estimate",
            ... )
            >>> print(result.data["duration_minutes"])
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
            if final_estimate_minutes is not None:
                session_data["final_estimate_minutes"] = final_estimate_minutes

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

        Records an issue with type and severity for later analysis. This
        provides the feedback loop for identifying systemic AI failure
        patterns — repeated hallucinations or high-severity errors signal
        the need to change models, prompts, or workflows.

        Args:
            session_id: Parent session identifier.
            issue_type: Category (e.g., 'hallucination', 'incorrect_output').
            description: Detailed description of the problem.
            severity: 'low', 'medium', 'high', or 'critical'.

        Returns:
            ServiceResult on success.

        Raises:
            No exceptions are raised directly. All errors are caught and
            returned as a failed ServiceResult with an error message.

        Example:
            >>> result = service.flag_issue(
            ...     session_id="abc-123",
            ...     issue_type="hallucination",
            ...     description="Model invented a non-existent API method",
            ...     severity="high",
            ... )
            >>> print(result.message)
            'Issue flagged: hallucination (high)'
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
        """Retrieve all currently active (non-completed) tracking sessions.

        Queries storage for sessions whose status is not 'completed' and
        returns a summary of each. This is used by the CLI ``status`` command
        and MCP ``get_active_sessions`` tool to show what's currently being
        tracked, helping users decide whether to start a new session or
        resume an existing one.

        The purpose of this view is to prevent duplicate tracking and give
        developers a quick dashboard of in-progress AI work.

        Each returned session dict contains only the fields needed for
        display: session_id, session_name, task_type, and start_time.
        Fields missing from storage default to 'Unknown'.

        Args:
            No arguments (self only).

        Returns:
            ServiceResult where ``data["active_sessions"]`` is a list of dicts,
            each with keys 'session_id' (str), 'session_name' (str),
            'task_type' (str), and 'start_time' (str, ISO format). The list
            is empty when no sessions are active. On storage errors, returns
            a failure result with the error message.

        Raises:
            No exceptions are raised directly. Storage errors are caught
            internally and returned as a failed ServiceResult.

        Example:
            >>> result = service.get_active_sessions()
            >>> for s in result.data["active_sessions"]:
            ...     print(f"{s['session_name']} started at {s['start_time']}")
        """
        try:
            sessions = self.storage.load_sessions()
            active_sessions = [
                {
                    "session_id": session_id,
                    "session_name": session.get("session_name", "Unknown"),
                    "task_type": session.get("task_type", "Unknown"),
                    "start_time": session.get("start_time", "Unknown"),
                }
                for session_id, session in sessions.items()
                if session.get("status") != "completed"
            ]

            return ServiceResult(
                success=True,
                message=f"Found {len(active_sessions)} active session(s)",
                data={"active_sessions": active_sessions},
            )

        except Exception as e:  # pragma: no cover - defensive
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
        and issue summaries. This provides the primary way teams measure
        whether AI tooling is saving time — the report quantifies the
        return on investment for each session and across the full history.

        Args:
            session_id: Optional filter to specific session.
            time_range: Time filter ('last_day', 'last_week', 'all').

        Returns:
            ServiceResult with report text.

        Raises:
            No exceptions are raised directly. All errors are caught and
            returned as a failed ServiceResult with an error message.

        Example:
            >>> result = service.get_observability(session_id="abc-123")
            >>> print(result.data["report"])
        """
        try:
            sessions = self.storage.load_sessions()
            interactions = self.storage.load_interactions()
            issues = self.storage.load_issues()

            # Filter by session if specified
            if session_id:
                if session_id not in sessions:  # pragma: no cover - defensive
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
        """Close all active sessions during server or CLI shutdown.

        Iterates every stored session and marks any with status 'active' as
        'completed' with outcome 'partial', since a graceful ending wasn't
        recorded. This prevents zombie sessions from accumulating across
        restarts and ensures ROI metrics reflect actual usage.

        The purpose of this cleanup is to prevent orphaned sessions — without
        it, restarting the server would leave zombie sessions that skew
        active-session counts and duration calculations indefinitely.

        End times are capped at ``start_time + max_duration_hours`` (from
        Config) to prevent overnight or forgotten sessions from inflating
        duration metrics. If a session's elapsed time exceeds the cap, the
        end_time is set to the cap boundary and a note is appended.

        All closures are persisted in a single ``save_sessions`` call for
        atomicity. On any storage error, returns 0 and logs the exception
        rather than propagating it (shutdown must not raise).

        Args:
            No arguments (self only).

        Returns:
            Number of sessions that were closed (0 if none were active or
            if an error occurred during processing).

        Raises:
            No exceptions are raised directly. All errors are caught
            internally, logged, and 0 is returned to ensure shutdown
            proceeds safely.

        Example:
            >>> closed = service.close_active_sessions_on_shutdown()
            >>> print(f"Cleaned up {closed} session(s)")
        """
        try:
            sessions = self.storage.load_sessions()
            active_count = 0

            for session_id, session_data in sessions.items():
                if session_data.get("status") == "active":
                    start_time = session_data.get("start_time", "")
                    end_time, auto_note = self._calculate_capped_end_time(
                        start_time, "server shutdown"
                    )

                    session_data["status"] = "completed"
                    session_data["end_time"] = end_time
                    session_data["outcome"] = "partial"
                    session_data["notes"] = (
                        session_data.get("notes", "") + " " + auto_note
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
