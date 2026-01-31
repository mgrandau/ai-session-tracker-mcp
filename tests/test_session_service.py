"""
Tests for session_service module.

PURPOSE: Verify SessionService business logic and error handling.
AI CONTEXT: Tests for session tracking operations independent of MCP server.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from ai_session_tracker_mcp.config import Config
from ai_session_tracker_mcp.session_service import ServiceResult, SessionService


class MockStorage:
    """Mock storage for testing SessionService."""

    def __init__(self) -> None:
        """Initialize mock storage."""
        self.sessions: dict[str, dict] = {}
        self.interactions: list[dict] = []
        self.issues: list[dict] = []

    def load_sessions(self) -> dict:
        """Load sessions."""
        return self.sessions.copy()

    def save_sessions(self, sessions: dict) -> bool:
        """Save sessions."""
        self.sessions = sessions.copy()
        return True

    def get_session(self, session_id: str) -> dict | None:
        """Get single session."""
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, data: dict) -> bool:
        """Update session."""
        self.sessions[session_id] = data
        return True

    def load_interactions(self) -> list:
        """Load interactions."""
        return self.interactions.copy()

    def save_interaction(self, interaction: dict) -> bool:
        """Save interaction."""
        self.interactions.append(interaction)
        return True

    def load_issues(self) -> list:
        """Load issues."""
        return self.issues.copy()

    def save_issue(self, issue: dict) -> bool:
        """Save issue."""
        self.issues.append(issue)
        return True

    def get_session_issues(self, session_id: str) -> list:
        """Get issues for a session."""
        return [i for i in self.issues if i.get("session_id") == session_id]

    def get_session_interactions(self, session_id: str) -> list:
        """Get interactions for a session."""
        return [i for i in self.interactions if i.get("session_id") == session_id]

    def add_interaction(self, interaction: dict) -> bool:
        """Add an interaction."""
        self.interactions.append(interaction)
        return True


# ============================================================
# ServiceResult Tests
# ============================================================


class TestServiceResult:
    """Tests for ServiceResult dataclass."""

    def test_to_dict_success(self) -> None:
        """Test to_dict for successful result."""
        result = ServiceResult(
            success=True,
            message="Operation completed",
            data={"key": "value"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["message"] == "Operation completed"
        assert d["data"] == {"key": "value"}
        assert "error" not in d

    def test_to_dict_failure(self) -> None:
        """Test to_dict for failed result."""
        result = ServiceResult(
            success=False,
            message="Operation failed",
            error="Something went wrong",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["message"] == "Operation failed"
        assert d["error"] == "Something went wrong"


# ============================================================
# Calculate Capped End Time Tests
# ============================================================


class TestCalculateCappedEndTime:
    """Tests for _calculate_capped_end_time helper method."""

    def test_session_within_max_duration(self) -> None:
        """Test end_time is actual time when session is within limit."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Start time 1 hour ago (within 4h default)
        start_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

        end_time, notes = service._calculate_capped_end_time(start_time, "test close")

        # End time should be approximately now (within a few seconds)
        end_dt = datetime.fromisoformat(end_time)
        assert (datetime.now(UTC) - end_dt).total_seconds() < 5
        assert notes == "[Auto-closed: test close]"
        assert "exceeded" not in notes

    def test_session_exceeds_max_duration(self) -> None:
        """Test end_time is capped when session exceeds limit."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Start time 10 hours ago (exceeds 4h default)
        start_time = (datetime.now(UTC) - timedelta(hours=10)).isoformat()

        with Config.override_for_test(max_session_duration=4.0):
            end_time, notes = service._calculate_capped_end_time(start_time, "test close")

        # End time should be start + 4 hours
        end_dt = datetime.fromisoformat(end_time)
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        expected_end = start_dt + timedelta(hours=4)

        # Allow small tolerance for computation time
        assert abs((end_dt - expected_end).total_seconds()) < 2
        assert "exceeded 4.0h max" in notes
        assert "was 10.0h" in notes

    def test_invalid_start_time_uses_current_time(self) -> None:
        """Test invalid start_time falls back to current time."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        end_time, notes = service._calculate_capped_end_time("invalid-date", "test close")

        # Should return current time
        end_dt = datetime.fromisoformat(end_time)
        assert (datetime.now(UTC) - end_dt).total_seconds() < 5
        assert notes == "[Auto-closed: test close]"

    def test_start_time_without_timezone(self) -> None:
        """Test start_time without timezone is handled correctly."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Start time without explicit timezone
        start_time = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")

        end_time, notes = service._calculate_capped_end_time(start_time, "test close")

        # Should succeed
        assert end_time is not None
        assert "Auto-closed" in notes

    def test_start_time_with_z_suffix(self) -> None:
        """Test start_time with Z suffix is handled correctly."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        start_time = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        end_time, notes = service._calculate_capped_end_time(start_time, "test close")

        assert end_time is not None
        assert "Auto-closed" in notes


# ============================================================
# Auto Close Active Sessions Tests
# ============================================================


class TestAutoCloseActiveSessions:
    """Tests for _auto_close_active_sessions method."""

    def test_auto_close_with_capped_duration(self) -> None:
        """Test auto-close caps duration for old sessions."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Create an old active session (12 hours ago)
        old_time = (datetime.now(UTC) - timedelta(hours=12)).isoformat()
        storage.sessions["old_session"] = {
            "id": "old_session",
            "status": "active",
            "execution_context": "foreground",
            "start_time": old_time,
            "notes": "",
        }

        with Config.override_for_test(max_session_duration=4.0):
            closed = service._auto_close_active_sessions("foreground")

        assert "old_session" in closed
        session = storage.sessions["old_session"]
        assert session["status"] == "completed"
        assert "exceeded 4.0h max" in session["notes"]

    def test_auto_close_exception_handling(self) -> None:
        """Test exception in auto_close is handled gracefully."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Make load_sessions raise an exception
        storage.load_sessions = MagicMock(side_effect=Exception("Storage error"))

        closed = service._auto_close_active_sessions("foreground")

        # Should return empty list, not raise
        assert closed == []


# ============================================================
# Start Session Error Handling Tests
# ============================================================


class TestStartSessionErrors:
    """Tests for start_session error handling."""

    def test_invalid_task_type(self) -> None:
        """Test start_session rejects invalid task_type."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.start_session(
            name="Test",
            task_type="invalid_type",
            model_name="test-model",
            human_time_estimate_minutes=30,
            estimate_source="manual",
        )

        assert result.success is False
        assert "task_type must be one of" in result.error

    def test_invalid_estimate_source(self) -> None:
        """Test start_session rejects invalid estimate_source."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.start_session(
            name="Test",
            task_type="code_generation",
            model_name="test-model",
            human_time_estimate_minutes=30,
            estimate_source="invalid_source",
        )

        assert result.success is False
        assert "estimate_source must be one of" in result.error

    def test_invalid_execution_context(self) -> None:
        """Test start_session rejects invalid execution_context."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.start_session(
            name="Test",
            task_type="code_generation",
            model_name="test-model",
            human_time_estimate_minutes=30,
            estimate_source="manual",
            execution_context="invalid_context",
        )

        assert result.success is False
        assert "execution_context must be one of" in result.error

    def test_storage_exception_handling(self) -> None:
        """Test start_session handles storage exceptions."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Make save_sessions raise an exception
        storage.save_sessions = MagicMock(side_effect=Exception("Storage failed"))

        result = service.start_session(
            name="Test",
            task_type="code_generation",
            model_name="test-model",
            human_time_estimate_minutes=30,
            estimate_source="manual",
        )

        assert result.success is False
        assert "Failed to start session" in result.message


# ============================================================
# Log Interaction Error Handling Tests
# ============================================================


class TestLogInteractionErrors:
    """Tests for log_interaction error handling."""

    def test_session_not_found(self) -> None:
        """Test log_interaction fails when session doesn't exist."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.log_interaction(
            session_id="nonexistent",
            prompt="Test prompt",
            response_summary="Test response",
            effectiveness_rating=4,
        )

        assert result.success is False
        assert "Session not found" in result.message

    def test_high_effectiveness_rating_accepted(self) -> None:
        """Test log_interaction accepts ratings outside 1-5 (no validation)."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Create a valid session first
        storage.sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "total_interactions": 0,
            "avg_effectiveness": 0,
        }

        result = service.log_interaction(
            session_id="test_session",
            prompt="Test prompt",
            response_summary="Test response",
            effectiveness_rating=10,  # No validation - accepted
        )

        # Service currently accepts any rating value
        assert result.success is True
        assert result.data["effectiveness_rating"] == 10

    def test_exception_handling(self) -> None:
        """Test log_interaction handles exceptions."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        storage.sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "total_interactions": 0,
            "avg_effectiveness": 0,
        }

        # Make add_interaction raise an exception
        storage.add_interaction = MagicMock(side_effect=Exception("Save failed"))

        result = service.log_interaction(
            session_id="test_session",
            prompt="Test prompt",
            response_summary="Test response",
            effectiveness_rating=4,
        )

        assert result.success is False
        assert "Failed to log interaction" in result.message


# ============================================================
# End Session Error Handling Tests
# ============================================================


class TestEndSessionErrors:
    """Tests for end_session error handling."""

    def test_invalid_outcome(self) -> None:
        """Test end_session rejects invalid outcome."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.end_session(
            session_id="test",
            outcome="invalid_outcome",
        )

        assert result.success is False
        assert "Invalid outcome" in result.message

    def test_session_not_found(self) -> None:
        """Test end_session fails when session doesn't exist."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.end_session(
            session_id="nonexistent",
            outcome="success",
        )

        assert result.success is False
        assert "Session not found" in result.message

    def test_exception_handling(self) -> None:
        """Test end_session handles exceptions."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        storage.sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": datetime.now(UTC).isoformat(),
        }

        # Make update_session raise an exception
        storage.update_session = MagicMock(side_effect=Exception("Update failed"))

        result = service.end_session(
            session_id="test_session",
            outcome="success",
        )

        assert result.success is False
        assert "Failed to end session" in result.message


# ============================================================
# Flag Issue Error Handling Tests
# ============================================================


class TestFlagIssueErrors:
    """Tests for flag_issue error handling."""

    def test_session_not_found(self) -> None:
        """Test flag_issue fails when session doesn't exist."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.flag_issue(
            session_id="nonexistent",
            issue_type="hallucination",
            description="Test issue",
            severity="high",
        )

        assert result.success is False
        assert "Session not found" in result.message

    def test_invalid_severity(self) -> None:
        """Test flag_issue rejects invalid severity."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        storage.sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
        }

        result = service.flag_issue(
            session_id="test_session",
            issue_type="hallucination",
            description="Test issue",
            severity="invalid_severity",
        )

        assert result.success is False
        assert "severity must be one of" in result.error

    def test_exception_handling(self) -> None:
        """Test flag_issue handles exceptions."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        storage.sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
        }

        # Make save_issue raise an exception
        storage.save_issue = MagicMock(side_effect=Exception("Save failed"))

        result = service.flag_issue(
            session_id="test_session",
            issue_type="hallucination",
            description="Test issue",
            severity="high",
        )

        assert result.success is False
        assert "Failed to flag issue" in result.message


# ============================================================
# Get Active Sessions Error Handling Tests
# ============================================================


class TestGetActiveSessionsErrors:
    """Tests for get_active_sessions error handling."""

    def test_success_returns_active_sessions(self) -> None:
        """Test get_active_sessions returns active sessions."""
        storage = MockStorage()
        storage.sessions = {
            "active1": {
                "session_name": "Session 1",
                "task_type": "debugging",
                "start_time": "2024-01-01",
                "status": "in_progress",
            },
            "active2": {
                "session_name": "Session 2",
                "task_type": "testing",
                "start_time": "2024-01-02",
                "status": "in_progress",
            },
            "completed": {
                "session_name": "Done",
                "task_type": "docs",
                "start_time": "2024-01-03",
                "status": "completed",
            },
        }
        service = SessionService(storage=storage)

        result = service.get_active_sessions()

        assert result.success is True
        assert len(result.data["active_sessions"]) == 2

    def test_exception_handling(self) -> None:
        """Test get_active_sessions handles exceptions."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Make load_sessions raise an exception
        storage.load_sessions = MagicMock(side_effect=Exception("Load failed"))

        result = service.get_active_sessions()

        assert result.success is False
        assert "Failed to get active sessions" in result.message


# ============================================================
# Get Observability Error Handling Tests
# ============================================================


class TestGetObservabilityErrors:
    """Tests for get_observability error handling."""

    def test_success_with_valid_session_id(self) -> None:
        """Test get_observability succeeds with valid session_id filter."""
        storage = MockStorage()
        storage.sessions = {
            "session1": {
                "session_name": "Test Session",
                "task_type": "debugging",
                "start_time": "2024-01-01T10:00:00",
                "status": "completed",
                "outcome": "success",
                "human_time_estimate_minutes": 30,
                "actual_duration_minutes": 25,
            }
        }
        storage.interactions = [
            {"session_id": "session1", "prompt_summary": "Test", "rating": 4},
            {"session_id": "other", "prompt_summary": "Other", "rating": 3},
        ]
        storage.issues = []
        service = SessionService(storage=storage)

        result = service.get_observability(session_id="session1")

        assert result.success is True
        assert "report" in result.data

    def test_session_not_found_filter(self) -> None:
        """Test get_observability fails when filtered session doesn't exist."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.get_observability(session_id="nonexistent")

        assert result.success is False
        assert "Session not found" in result.message

    def test_exception_handling(self) -> None:
        """Test get_observability handles exceptions."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Make load_sessions raise an exception
        storage.load_sessions = MagicMock(side_effect=Exception("Load failed"))

        result = service.get_observability()

        assert result.success is False
        assert "Failed to generate report" in result.message


# ============================================================
# Close Active Sessions On Shutdown Tests
# ============================================================


class TestCloseActiveSessionsOnShutdown:
    """Tests for close_active_sessions_on_shutdown method."""

    def test_closes_active_sessions_with_capped_duration(self) -> None:
        """Test shutdown closes sessions with capped duration."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Create an old active session (12 hours ago)
        old_time = (datetime.now(UTC) - timedelta(hours=12)).isoformat()
        storage.sessions["old_session"] = {
            "id": "old_session",
            "status": "active",
            "start_time": old_time,
            "notes": "",
        }

        with Config.override_for_test(max_session_duration=4.0):
            count = service.close_active_sessions_on_shutdown()

        assert count == 1
        session = storage.sessions["old_session"]
        assert session["status"] == "completed"
        assert "exceeded 4.0h max" in session["notes"]
        assert "server shutdown" in session["notes"]

    def test_exception_handling(self) -> None:
        """Test shutdown handles exceptions."""
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Make load_sessions raise an exception
        storage.load_sessions = MagicMock(side_effect=Exception("Load failed"))

        count = service.close_active_sessions_on_shutdown()

        # Should return 0, not raise
        assert count == 0
