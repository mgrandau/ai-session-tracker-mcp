"""Tests for the SessionService business logic layer.

PURPOSE: Verify SessionService input validation, error handling, duration
capping, auto-close behavior, and observability report generation — all
independent of the MCP transport layer.

AI CONTEXT: These tests use a MockStorage backend to isolate business logic
from persistence concerns. Each test class covers a single public method
or private helper, organized by: ServiceResult serialization, capped end-time
calculations, auto-close lifecycle, start/log/end/flag operations, active
session queries, observability reporting, and graceful shutdown.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from ai_session_tracker_mcp.config import Config
from ai_session_tracker_mcp.session_service import ServiceResult, SessionService


class MockStorage:
    """In-memory mock storage backend for testing SessionService in isolation.

    Implements the same interface as the real storage layer (load/save/get/update
    for sessions, interactions, and issues) but keeps everything in dictionaries
    and lists so tests run without filesystem or database dependencies.

    Business context:
    SessionService delegates all persistence to a storage object. By substituting
    this mock, tests verify pure business logic without I/O side-effects, enabling
    fast, deterministic, and repeatable test execution.
    """

    def __init__(self) -> None:
        """Initialize mock storage with empty in-memory collections.

        Sets up three collections that mirror the real storage schema:
        sessions (dict), interactions (list), and issues (list). Each collection
        starts empty so tests can populate exactly the state they need.

        Business context:
        Test isolation requires a clean slate for each test. By starting empty,
        tests declare their own preconditions explicitly, avoiding hidden
        coupling between tests.

        Args:
            None — uses no constructor parameters; all state is internal.

        Returns:
            None — initializes instance attributes only.

        Raises:
            No exceptions — pure in-memory initialization.

        Example:
            storage = MockStorage()
            assert storage.sessions == {}
            assert storage.interactions == []
            assert storage.issues == []

        Implementation details:
        Uses a dict for sessions (O(1) lookup by ID) and flat lists for
        interactions/issues (append-only, filtered by session_id on read).
        """
        self.sessions: dict[str, dict] = {}
        self.interactions: list[dict] = []
        self.issues: list[dict] = []

    def load_sessions(self) -> dict:
        """Return a shallow copy of all stored sessions for test isolation.

        Provides the same read semantics as the real storage layer: callers
        get a copy so that mutations don't affect the mock's internal state
        unless explicitly written back via save_sessions.

        Business context:
        SessionService calls load_sessions to enumerate all tracked sessions.
        Returning a copy prevents accidental state leakage between service
        operations within the same test.

        Args:
            None — reads from internal self.sessions.

        Returns:
            dict: Shallow copy of the sessions dictionary, keyed by session_id.

        Raises:
            No exceptions in normal operation. Tests may replace this method
            with a MagicMock that raises to simulate storage failures.

        Example:
            storage = MockStorage()
            storage.sessions["s1"] = {"id": "s1", "status": "active"}
            loaded = storage.load_sessions()
            assert loaded == {"s1": {"id": "s1", "status": "active"}}

        Implementation details:
        Uses dict.copy() for a shallow copy. Nested dicts (session data) are
        shared references, which is acceptable for test isolation since tests
        typically don't mutate loaded data in place.
        """
        return self.sessions.copy()

    def save_sessions(self, sessions: dict) -> bool:
        """Persist a full sessions dictionary, replacing current state.

        Replaces the entire internal sessions dict with a shallow copy of the
        provided data, simulating the real storage's atomic write semantics.

        Business context:
        SessionService calls save_sessions after creating or modifying sessions.
        The mock's replace-all semantics match the real JSON file storage, which
        overwrites the entire file on each save.

        Args:
            sessions: Complete sessions dict to store. Keys are session_id strings,
                values are session data dicts.

        Returns:
            bool: Always True, indicating successful persistence.

        Raises:
            No exceptions in normal operation. Tests may replace this method
            with a MagicMock that raises to simulate storage failures (e.g.,
            disk full, permission denied).

        Example:
            storage = MockStorage()
            storage.save_sessions({"s1": {"status": "active"}})
            assert "s1" in storage.sessions
        """
        self.sessions = sessions.copy()
        return True

    def get_session(self, session_id: str) -> dict | None:
        """Retrieve a single session by its ID, or None if not found.

        Provides O(1) lookup by session_id, matching the real storage layer's
        indexed access pattern.

        Business context:
        Most SessionService operations (log_interaction, end_session, flag_issue)
        start by looking up the target session. Returning None for missing IDs
        allows the service to produce clear "Session not found" errors.

        Args:
            session_id: Unique identifier of the session to look up.

        Returns:
            dict | None: The session data dict if found, otherwise None.

        Raises:
            No exceptions — dict.get never raises for missing keys.

        Example:
            storage = MockStorage()
            storage.sessions["s1"] = {"id": "s1", "status": "active"}
            assert storage.get_session("s1") is not None
            assert storage.get_session("missing") is None
        """
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, data: dict) -> bool:
        """Overwrite a session's data by ID.

        Replaces the entire session dict for the given ID, simulating an
        atomic update in the real storage layer.

        Business context:
        SessionService calls update_session when ending sessions or auto-closing
        stale ones. The mock stores the updated data directly, allowing tests
        to inspect the final session state after service operations.

        Args:
            session_id: The session to update (must already exist for the test
                scenario to be meaningful, but no existence check is enforced).
            data: Complete session dict to store under this ID.

        Returns:
            bool: Always True, indicating successful persistence.

        Raises:
            No exceptions in normal operation. Tests may replace this method
            with a MagicMock that raises to simulate storage failures.

        Example:
            storage = MockStorage()
            storage.update_session("s1", {"id": "s1", "status": "completed"})
            assert storage.sessions["s1"]["status"] == "completed"
        """
        self.sessions[session_id] = data
        return True

    def load_interactions(self) -> list:
        """Return a shallow copy of all stored interactions for test isolation.

        Provides the same read semantics as the real storage layer: callers
        get a copy so that mutations don't affect the mock's internal state
        unless explicitly written via save_interaction or add_interaction.

        Business context:
        SessionService calls load_interactions to build observability reports
        and compute per-session metrics. The copy prevents test-internal
        mutations from corrupting subsequent assertions.

        Args:
            None — reads from internal self.interactions.

        Returns:
            list: Shallow copy of the interactions list (each item is a dict).

        Raises:
            No exceptions in normal operation. Tests may replace this method
            with a MagicMock that raises to simulate storage failures.

        Example:
            storage = MockStorage()
            storage.interactions.append({"session_id": "s1", "rating": 4})
            loaded = storage.load_interactions()
            assert len(loaded) == 1

        Implementation details:
        Uses list.copy() for a shallow copy. Individual interaction dicts are
        shared references, which is acceptable for test scenarios.
        """
        return self.interactions.copy()

    def save_interaction(self, interaction: dict) -> bool:
        """Append a single interaction record to the interactions list.

        Mirrors the real storage's append-only interaction persistence: each
        call adds one interaction dict to the internal list.

        Business context:
        Interactions capture each prompt/response pair within a session. The
        mock's append semantics let tests verify that log_interaction correctly
        persists interaction records without overwriting previous ones.

        Args:
            interaction: Interaction dict containing session_id, prompt,
                response_summary, effectiveness_rating, and timestamp fields.

        Returns:
            bool: Always True, indicating successful persistence.

        Raises:
            No exceptions in normal operation. Tests may replace this method
            with a MagicMock that raises to simulate storage failures.

        Example:
            storage = MockStorage()
            storage.save_interaction({"session_id": "s1", "rating": 4})
            assert len(storage.interactions) == 1
        """
        self.interactions.append(interaction)
        return True

    def load_issues(self) -> list:
        """Return a shallow copy of all stored issues for test isolation.

        Provides the same read semantics as the real storage layer: callers
        get a copy so that mutations don't affect the mock's internal state
        unless explicitly written via save_issue.

        Business context:
        SessionService calls load_issues to build observability reports and
        compute quality metrics. The copy prevents accidental cross-test
        state contamination.

        Args:
            None — reads from internal self.issues.

        Returns:
            list: Shallow copy of the issues list (each item is a dict).

        Raises:
            No exceptions in normal operation. Tests may replace this method
            with a MagicMock that raises to simulate storage failures.

        Example:
            storage = MockStorage()
            storage.issues.append({"session_id": "s1", "severity": "high"})
            loaded = storage.load_issues()
            assert len(loaded) == 1

        Implementation details:
        Uses list.copy() for a shallow copy. Individual issue dicts are
        shared references, which is acceptable for test scenarios.
        """
        return self.issues.copy()

    def save_issue(self, issue: dict) -> bool:
        """Append a single issue record to the issues list.

        Mirrors the real storage's append-only issue persistence: each call
        adds one issue dict to the internal list.

        Business context:
        Issues track quality problems (hallucinations, incorrect code, etc.)
        per session. The mock's append semantics ensure tests can verify
        that flag_issue correctly persists issue records.

        Args:
            issue: Issue dict containing session_id, issue_type, description,
                severity, and timestamp fields.

        Returns:
            bool: Always True, indicating successful persistence.

        Raises:
            No exceptions in normal operation. Tests may replace this method
            with a MagicMock that raises to simulate storage failures.

        Example:
            storage = MockStorage()
            storage.save_issue({"session_id": "s1", "severity": "high"})
            assert len(storage.issues) == 1

        Implementation details:
        Simple list.append — no deduplication or validation, matching the
        real storage layer's contract of unconditional persistence.
        """
        self.issues.append(issue)
        return True

    def get_session_issues(self, session_id: str) -> list:
        """Return all issues associated with a given session ID.

        Filters the internal issues list by session_id, matching the real
        storage layer's per-session query behavior.

        Business context:
        SessionService uses per-session issue counts in observability reports
        and quality dashboards. The mock's filtering logic must match the real
        storage to produce accurate test results.

        Args:
            session_id: The session whose issues to retrieve.

        Returns:
            list: Filtered list of issue dicts where issue["session_id"] matches.

        Raises:
            No exceptions — returns an empty list if no issues match.

        Example:
            storage = MockStorage()
            storage.issues = [{"session_id": "s1"}, {"session_id": "s2"}]
            assert len(storage.get_session_issues("s1")) == 1
        """
        return [i for i in self.issues if i.get("session_id") == session_id]

    def get_session_interactions(self, session_id: str) -> list:
        """Return all interactions associated with a given session ID.

        Filters the internal interactions list by session_id, matching the
        real storage layer's per-session query behavior.

        Business context:
        SessionService uses per-session interaction data in observability
        reports to compute effectiveness averages and interaction counts.
        The mock must filter correctly for reports to test accurately.

        Args:
            session_id: The session whose interactions to retrieve.

        Returns:
            list: Filtered list of interaction dicts where
                interaction["session_id"] matches.

        Raises:
            No exceptions — returns an empty list if no interactions match.

        Example:
            storage = MockStorage()
            storage.interactions = [{"session_id": "s1"}, {"session_id": "s2"}]
            assert len(storage.get_session_interactions("s1")) == 1
        """
        return [i for i in self.interactions if i.get("session_id") == session_id]

    def add_interaction(self, interaction: dict) -> bool:
        """Append an interaction record (alias for save_interaction).

        Some SessionService methods call add_interaction instead of
        save_interaction; this method ensures mock compatibility with both
        call patterns in the service layer.

        Business context:
        The dual naming (save_interaction vs add_interaction) exists because
        different service operations use different storage method names. The
        mock must support both to avoid false test failures from method-name
        mismatches.

        Args:
            interaction: Interaction dict to persist, containing session_id,
                prompt, response_summary, and effectiveness_rating fields.

        Returns:
            bool: Always True, indicating successful persistence.

        Raises:
            No exceptions in normal operation. Tests may replace this method
            with a MagicMock that raises to simulate storage failures.

        Example:
            storage = MockStorage()
            storage.add_interaction({"session_id": "s1", "rating": 5})
            assert len(storage.interactions) == 1
        """
        self.interactions.append(interaction)
        return True


# ============================================================
# ServiceResult Tests
# ============================================================


class TestServiceResult:
    """Tests for ServiceResult dataclass serialization.

    ServiceResult is the uniform return type for all SessionService operations.
    These tests verify that to_dict() produces the correct wire format for both
    success and failure cases, which is critical for MCP response serialization.
    """

    def test_to_dict_success(self) -> None:
        """Verifies to_dict produces correct structure for a successful result.

        Tests the happy-path serialization where success=True and data is present
        but no error field exists.

        Business context:
        MCP tool responses are built from ServiceResult.to_dict(). A malformed
        success dict would break client-side parsing and display.

        Arrangement:
        1. Create a ServiceResult with success=True, a message, and data payload.

        Action:
        Call to_dict() to serialize the result into a plain dictionary.

        Assertion Strategy:
        Validates correct serialization by confirming:
        - success flag is True (boolean, not truthy).
        - message text is preserved verbatim.
        - data payload round-trips without modification.
        - error key is absent (success results must not include it).

        Testing Principle:
        Validates contract conformance, ensuring the success wire format matches
        what MCP clients expect.
        """
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
        """Verifies to_dict produces correct structure for a failed result.

        Tests the error-path serialization where success=False and the error
        field carries diagnostic information.

        Business context:
        Failure results must include an error string so that MCP clients can
        display meaningful diagnostics to the user.

        Arrangement:
        1. Create a ServiceResult with success=False, a message, and an error string.

        Action:
        Call to_dict() to serialize the result into a plain dictionary.

        Assertion Strategy:
        Validates correct serialization by confirming:
        - success flag is False (boolean, not falsy).
        - message text is preserved verbatim.
        - error string is included and matches the original.

        Testing Principle:
        Validates error contract conformance, ensuring failure results carry
        actionable error details for downstream consumers.
        """
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
    """Tests for _calculate_capped_end_time helper method.

    This private helper computes the effective end time when auto-closing a
    session. If a session's elapsed time exceeds the configured maximum, the
    end time is capped at start + max_duration rather than using wall-clock
    time. This prevents inflated duration metrics from abandoned sessions.
    """

    def test_session_within_max_duration(self) -> None:
        """Verifies end_time equals wall-clock time when session is within the limit.

        Tests the normal case where a session is closed before reaching the
        configured maximum duration, so no capping is applied.

        Business context:
        Most sessions are closed promptly. The end time should reflect actual
        wall-clock time to produce accurate duration metrics for analytics.

        Arrangement:
        1. Create a SessionService with default config (4h max).
        2. Set start_time to 1 hour ago (well within 4h limit).

        Action:
        Call _calculate_capped_end_time with the recent start_time.

        Assertion Strategy:
        Validates uncapped behavior by confirming:
        - Returned end_time is approximately now (within 5 seconds).
        - Notes contain the auto-close reason but no "exceeded" warning.

        Testing Principle:
        Validates the happy-path branch, ensuring normal sessions get accurate
        timestamps without unnecessary capping.
        """
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
        """Verifies end_time is capped at start + max_duration for stale sessions.

        Tests the capping logic where a session has been running far longer than
        the configured maximum, triggering duration truncation.

        Business context:
        Abandoned sessions (e.g., developer forgot to close) would skew duration
        metrics if recorded at wall-clock time. Capping preserves data integrity
        for analytics dashboards and time-tracking reports.

        Arrangement:
        1. Create a SessionService with default storage.
        2. Set start_time to 10 hours ago (exceeds 4h max).
        3. Override config with max_session_duration=4.0.

        Action:
        Call _calculate_capped_end_time under the 4h config override.

        Assertion Strategy:
        Validates capping logic by confirming:
        - end_time ≈ start_time + 4 hours (within 2 seconds tolerance).
        - Notes mention "exceeded 4.0h max" for auditability.
        - Notes include original duration ("was 10.0h") for diagnostics.

        Testing Principle:
        Validates boundary enforcement, ensuring abandoned sessions cannot
        inflate duration metrics beyond the configured ceiling.
        """
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
        """Verifies graceful fallback to current time when start_time is unparseable.

        Tests the defensive parsing path where an invalid ISO string cannot be
        converted, so the method falls back to datetime.now(UTC).

        Business context:
        Corrupted or manually-edited session data may contain invalid timestamps.
        The auto-close mechanism must not crash; it should degrade gracefully and
        still produce a valid end_time for the session record.

        Arrangement:
        1. Create a SessionService with default storage.
        2. Provide a clearly invalid date string ("invalid-date").

        Action:
        Call _calculate_capped_end_time with the invalid start_time.

        Assertion Strategy:
        Validates fallback behavior by confirming:
        - end_time is approximately now (within 5 seconds), not an error.
        - Notes still contain the standard auto-close marker.

        Testing Principle:
        Validates defensive parsing, ensuring corrupt input doesn't propagate
        failures through the auto-close pipeline.
        """
        storage = MockStorage()
        service = SessionService(storage=storage)

        end_time, notes = service._calculate_capped_end_time("invalid-date", "test close")

        # Should return current time
        end_dt = datetime.fromisoformat(end_time)
        assert (datetime.now(UTC) - end_dt).total_seconds() < 5
        assert notes == "[Auto-closed: test close]"

    def test_start_time_without_timezone(self) -> None:
        """Verifies start_time without explicit timezone info is handled correctly.

        Tests timezone-naive ISO strings, which can occur when sessions are
        created by code that omits the UTC offset.

        Business context:
        Python's datetime.fromisoformat behaves differently for naive vs aware
        datetimes. The helper must handle both to avoid crashes during auto-close
        of sessions created with varying datetime serialization approaches.

        Arrangement:
        1. Create a SessionService with default storage.
        2. Format start_time without timezone suffix (e.g., "2024-01-01T10:00:00").

        Action:
        Call _calculate_capped_end_time with the timezone-naive start_time.

        Assertion Strategy:
        Validates timezone handling by confirming:
        - end_time is not None (no parsing crash).
        - Notes contain the "Auto-closed" marker.

        Testing Principle:
        Validates input normalization, ensuring timezone-naive timestamps don't
        break the capping calculation.
        """
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Start time without explicit timezone
        start_time = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")

        end_time, notes = service._calculate_capped_end_time(start_time, "test close")

        # Should succeed
        assert end_time is not None
        assert "Auto-closed" in notes

    def test_start_time_with_z_suffix(self) -> None:
        """Verifies start_time with 'Z' UTC suffix is parsed correctly.

        Tests the ISO 8601 'Z' suffix convention (common in JavaScript/JSON APIs)
        which Python's fromisoformat historically didn't support before 3.11.

        Business context:
        Sessions created via MCP clients (often JavaScript-based) may serialize
        timestamps with 'Z' instead of '+00:00'. The helper must accept both
        formats to maintain cross-platform compatibility.

        Arrangement:
        1. Create a SessionService with default storage.
        2. Format start_time with trailing 'Z' (e.g., "2024-01-01T10:00:00Z").

        Action:
        Call _calculate_capped_end_time with the Z-suffixed start_time.

        Assertion Strategy:
        Validates Z-suffix parsing by confirming:
        - end_time is not None (no parsing crash).
        - Notes contain the "Auto-closed" marker.

        Testing Principle:
        Validates cross-platform timestamp compatibility, ensuring JavaScript-
        originated timestamps are accepted without error.
        """
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
    """Tests for _auto_close_active_sessions method.

    When a new session starts, any existing active sessions in the same
    execution context are automatically closed. These tests verify both
    the happy-path (sessions are closed with capped durations) and the
    error-handling path (storage failures are swallowed gracefully).
    """

    def test_auto_close_with_capped_duration(self) -> None:
        """Verifies auto-close caps duration for sessions exceeding max duration.

        Tests that an old active session (12h elapsed, 4h max) gets closed with
        a capped end_time and appropriate audit notes.

        Business context:
        When a developer starts a new session, stale sessions from previous work
        must be cleaned up automatically. Duration capping prevents abandoned
        sessions from inflating time-tracking metrics.

        Arrangement:
        1. Create a SessionService with default mock storage.
        2. Insert an active session started 12 hours ago (well past 4h max).
        3. Override config with max_session_duration=4.0.

        Action:
        Call _auto_close_active_sessions for the "foreground" execution context.

        Assertion Strategy:
        Validates capped auto-close by confirming:
        - The old session ID appears in the returned closed-list.
        - Session status is updated to "completed".
        - Notes contain "exceeded 4.0h max" for audit trail.

        Testing Principle:
        Validates automatic cleanup with duration capping, ensuring stale
        sessions are closed without corrupting duration analytics.
        """
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
        """Verifies auto-close swallows storage exceptions without crashing.

        Tests that when the storage layer throws during load_sessions, the
        method returns an empty list rather than propagating the exception.

        Business context:
        Auto-close is a side-effect of starting a new session. A storage failure
        during cleanup must not prevent the new session from being created. The
        method degrades gracefully by returning an empty list.

        Arrangement:
        1. Create a SessionService with default mock storage.
        2. Replace load_sessions with a MagicMock that raises Exception.

        Action:
        Call _auto_close_active_sessions for the "foreground" context.

        Assertion Strategy:
        Validates graceful degradation by confirming:
        - Return value is an empty list (not an exception).
        - No unhandled exception propagates to the caller.

        Testing Principle:
        Validates fault isolation, ensuring storage layer failures in cleanup
        don't cascade into session creation failures.
        """
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
    """Tests for start_session input validation and error handling.

    start_session is the entry point for creating new tracking sessions. These
    tests verify that invalid enum values are rejected with descriptive errors
    and that storage-layer exceptions produce graceful failure results rather
    than unhandled crashes.
    """

    def test_invalid_task_type(self) -> None:
        """Verifies start_session rejects an unrecognized task_type value.

        Tests the enum validation gate that prevents sessions from being created
        with task types outside the allowed set.

        Business context:
        Task type drives analytics categorization (code_generation, debugging,
        etc.). Accepting arbitrary values would corrupt downstream reports and
        make cross-session comparisons meaningless.

        Arrangement:
        1. Create a SessionService with default mock storage.

        Action:
        Call start_session with task_type="invalid_type" (not in the allowed enum).

        Assertion Strategy:
        Validates input rejection by confirming:
        - result.success is False.
        - result.error mentions "task_type must be one of" with the allowed values.

        Testing Principle:
        Validates input validation at the API boundary, ensuring garbage-in
        produces a clear error rather than garbage-out.
        """
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
        """Verifies start_session rejects an unrecognized estimate_source value.

        Tests the enum validation gate for the estimate_source parameter, which
        indicates how the time estimate was derived.

        Business context:
        Estimate source (manual, ai_suggested, historical) is used to weight
        accuracy metrics in analytics. Invalid sources would undermine estimate
        calibration tracking.

        Arrangement:
        1. Create a SessionService with default mock storage.

        Action:
        Call start_session with estimate_source="invalid_source".

        Assertion Strategy:
        Validates input rejection by confirming:
        - result.success is False.
        - result.error mentions "estimate_source must be one of".

        Testing Principle:
        Validates enum boundary checking, ensuring only known estimate sources
        are accepted into the session record.
        """
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
        """Verifies start_session rejects an unrecognized execution_context value.

        Tests the enum validation gate for execution_context, which controls
        session isolation (foreground vs background).

        Business context:
        Execution context determines auto-close scoping: starting a new
        foreground session auto-closes other foreground sessions but not
        background ones. An invalid context would break this isolation logic.

        Arrangement:
        1. Create a SessionService with default mock storage.

        Action:
        Call start_session with execution_context="invalid_context".

        Assertion Strategy:
        Validates input rejection by confirming:
        - result.success is False.
        - result.error mentions "execution_context must be one of".

        Testing Principle:
        Validates execution context validation, ensuring the auto-close scoping
        mechanism cannot be bypassed with arbitrary context strings.
        """
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
        """Verifies start_session catches and wraps storage-layer exceptions.

        Tests that when the underlying storage raises during save_sessions,
        the exception is caught and returned as a structured failure result.

        Business context:
        Storage failures (disk full, permission denied, etc.) must not crash
        the MCP server. Users should receive a clear error message that can
        be retried or escalated.

        Arrangement:
        1. Create a SessionService with default mock storage.
        2. Replace save_sessions with a MagicMock that raises Exception.

        Action:
        Call start_session with valid parameters (all validation passes,
        failure occurs only at persistence time).

        Assertion Strategy:
        Validates exception wrapping by confirming:
        - result.success is False (not an unhandled exception).
        - result.message contains "Failed to start session" for user-facing context.

        Testing Principle:
        Validates fault containment, ensuring storage-layer failures are
        wrapped into structured error results rather than propagating as
        unhandled exceptions.
        """
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
    """Tests for log_interaction error handling and edge cases.

    log_interaction records a prompt/response pair against an active session.
    These tests cover session-not-found errors, boundary rating values, and
    storage exception handling.
    """

    def test_session_not_found(self) -> None:
        """Verifies log_interaction fails gracefully for a nonexistent session ID.

        Tests the lookup validation that prevents interactions from being
        recorded against sessions that don't exist.

        Business context:
        Orphaned interactions (pointing to nonexistent sessions) would corrupt
        analytics aggregations and make it impossible to reconcile interaction
        counts with session records.

        Arrangement:
        1. Create a SessionService with empty mock storage (no sessions).

        Action:
        Call log_interaction with session_id="nonexistent".

        Assertion Strategy:
        Validates lookup failure by confirming:
        - result.success is False.
        - result.message contains "Session not found".

        Testing Principle:
        Validates referential integrity enforcement, ensuring interactions
        cannot be created without a valid parent session.
        """
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
        """Verifies log_interaction accepts effectiveness ratings outside the 1-5 range.

        Tests that the service does not currently enforce a rating range,
        documenting this as intentional (or a known gap) in validation.

        Business context:
        While effectiveness ratings are conventionally 1-5, the service layer
        currently delegates validation to the MCP schema layer. This test
        documents the current permissive behavior so that if rating validation
        is added later, this test will catch the behavioral change.

        Arrangement:
        1. Create a SessionService with mock storage.
        2. Insert a valid active session with initial interaction counters.

        Action:
        Call log_interaction with effectiveness_rating=10 (outside 1-5 range).

        Assertion Strategy:
        Validates permissive acceptance by confirming:
        - result.success is True (rating is not rejected).
        - result.data preserves the rating value of 10 exactly.

        Testing Principle:
        Validates behavioral documentation — this test serves as a living
        specification of current validation boundaries, alerting developers
        if rating constraints are inadvertently introduced or changed.
        """
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
        """Verifies log_interaction catches and wraps storage exceptions.

        Tests that when add_interaction raises, the exception is caught and
        returned as a structured failure result.

        Business context:
        Interaction logging happens during active sessions. A storage failure
        must not crash the MCP server mid-session; the user should receive
        a clear error and be able to continue working.

        Arrangement:
        1. Create a SessionService with mock storage.
        2. Insert a valid active session.
        3. Replace add_interaction with a MagicMock that raises Exception.

        Action:
        Call log_interaction with valid parameters (failure occurs at persistence).

        Assertion Strategy:
        Validates exception wrapping by confirming:
        - result.success is False (not an unhandled exception).
        - result.message contains "Failed to log interaction".

        Testing Principle:
        Validates fault containment, ensuring storage failures during
        interaction logging don't crash the session or the MCP server.
        """
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
    """Tests for end_session input validation and error handling.

    end_session closes an active session with an outcome and optional summary.
    These tests verify that invalid outcomes are rejected, nonexistent sessions
    produce clear errors, and storage exceptions are caught gracefully.
    """

    def test_invalid_outcome(self) -> None:
        """Verifies end_session rejects an unrecognized outcome value.

        Tests the enum validation gate that ensures only known outcome values
        (success, partial, failure, abandoned) are accepted.

        Business context:
        Session outcomes feed directly into success-rate dashboards and
        retrospective reports. Arbitrary outcome strings would make aggregation
        and filtering impossible.

        Arrangement:
        1. Create a SessionService with default mock storage.

        Action:
        Call end_session with outcome="invalid_outcome".

        Assertion Strategy:
        Validates input rejection by confirming:
        - result.success is False.
        - result.message contains "Invalid outcome".

        Testing Principle:
        Validates enum boundary enforcement, ensuring only semantically
        meaningful outcomes enter the session record.
        """
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.end_session(
            session_id="test",
            outcome="invalid_outcome",
        )

        assert result.success is False
        assert "Invalid outcome" in result.message

    def test_session_not_found(self) -> None:
        """Verifies end_session fails gracefully when the session doesn't exist.

        Tests the lookup validation that prevents closing nonexistent sessions.

        Business context:
        Attempting to close a nonexistent session (typo, stale reference, race
        condition) should produce a clear error rather than a silent no-op or
        crash, enabling the caller to take corrective action.

        Arrangement:
        1. Create a SessionService with empty mock storage.

        Action:
        Call end_session with session_id="nonexistent" and a valid outcome.

        Assertion Strategy:
        Validates lookup failure by confirming:
        - result.success is False.
        - result.message contains "Session not found".

        Testing Principle:
        Validates referential integrity, ensuring only existing sessions can
        be transitioned to a closed state.
        """
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.end_session(
            session_id="nonexistent",
            outcome="success",
        )

        assert result.success is False
        assert "Session not found" in result.message

    def test_exception_handling(self) -> None:
        """Verifies end_session catches and wraps storage exceptions.

        Tests that when update_session raises, the exception is caught and
        returned as a structured failure result.

        Business context:
        Ending a session is a critical operation — the user has completed
        their work and expects the session to be finalized. A storage crash
        must not lose the session's open state; the user should be informed
        so they can retry.

        Arrangement:
        1. Create a SessionService with mock storage.
        2. Insert a valid active session with a start_time.
        3. Replace update_session with a MagicMock that raises Exception.

        Action:
        Call end_session with valid parameters.

        Assertion Strategy:
        Validates exception wrapping by confirming:
        - result.success is False.
        - result.message contains "Failed to end session".

        Testing Principle:
        Validates fault containment, ensuring storage failures during session
        finalization produce structured errors rather than unhandled crashes.
        """
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
    """Tests for flag_issue input validation and error handling.

    flag_issue records a quality issue (hallucination, incorrect code, etc.)
    against an active session. These tests cover session lookup validation,
    severity enum validation, and storage exception handling.
    """

    def test_session_not_found(self) -> None:
        """Verifies flag_issue fails gracefully when the session doesn't exist.

        Tests the lookup validation that prevents issues from being recorded
        against nonexistent sessions.

        Business context:
        Issues are keyed to sessions for traceability. An orphaned issue
        pointing to a nonexistent session would be impossible to investigate
        or correlate with session context during quality reviews.

        Arrangement:
        1. Create a SessionService with empty mock storage.

        Action:
        Call flag_issue with session_id="nonexistent".

        Assertion Strategy:
        Validates lookup failure by confirming:
        - result.success is False.
        - result.message contains "Session not found".

        Testing Principle:
        Validates referential integrity, ensuring issues always link to
        real sessions for end-to-end traceability.
        """
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
        """Verifies flag_issue rejects an unrecognized severity level.

        Tests the enum validation gate that ensures only known severity values
        (low, medium, high, critical) are accepted.

        Business context:
        Issue severity drives triage priority and alert thresholds. Invalid
        severity levels would bypass priority routing and make it impossible
        to filter or sort issues in quality dashboards.

        Arrangement:
        1. Create a SessionService with mock storage.
        2. Insert a valid active session.

        Action:
        Call flag_issue with severity="invalid_severity".

        Assertion Strategy:
        Validates input rejection by confirming:
        - result.success is False.
        - result.error mentions "severity must be one of".

        Testing Principle:
        Validates severity enum enforcement, ensuring only meaningful
        severity levels enter the issue tracking system.
        """
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
        """Verifies flag_issue catches and wraps storage exceptions.

        Tests that when save_issue raises, the exception is caught and
        returned as a structured failure result.

        Business context:
        Issue flagging is a critical feedback loop — users report quality
        problems in real time. A storage failure must not discard the report
        silently; the user needs to know the flag wasn't saved so they can
        retry or record it elsewhere.

        Arrangement:
        1. Create a SessionService with mock storage.
        2. Insert a valid active session.
        3. Replace save_issue with a MagicMock that raises Exception.

        Action:
        Call flag_issue with valid parameters.

        Assertion Strategy:
        Validates exception wrapping by confirming:
        - result.success is False.
        - result.message contains "Failed to flag issue".

        Testing Principle:
        Validates fault containment, ensuring storage failures during issue
        flagging produce actionable error messages.
        """
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
    """Tests for get_active_sessions retrieval and error handling.

    get_active_sessions returns all sessions with non-completed status. These
    tests verify correct filtering of active vs completed sessions and graceful
    handling of storage exceptions.
    """

    def test_success_returns_active_sessions(self) -> None:
        """Verifies get_active_sessions filters out completed sessions.

        Tests that only sessions with non-completed status (e.g., "in_progress")
        are returned, while completed sessions are excluded.

        Business context:
        The active sessions view is the primary dashboard for developers to see
        what's currently being tracked. Including completed sessions would clutter
        the view and cause confusion about which sessions are still open.

        Arrangement:
        1. Create mock storage with three sessions:
           - Two active ("in_progress") sessions.
           - One completed session.

        Action:
        Call get_active_sessions to retrieve the filtered list.

        Assertion Strategy:
        Validates status filtering by confirming:
        - result.success is True.
        - Exactly 2 sessions are returned (the completed one is excluded).

        Testing Principle:
        Validates query filtering logic, ensuring the active sessions view
        accurately reflects only in-progress work.
        """
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
        """Verifies get_active_sessions catches and wraps storage exceptions.

        Tests that when load_sessions raises, the exception is caught and
        returned as a structured failure result.

        Business context:
        The active sessions query is a read-only operation that may be called
        frequently (dashboards, heartbeats). Storage failures must not crash
        the server; they should produce clear error responses.

        Arrangement:
        1. Create a SessionService with mock storage.
        2. Replace load_sessions with a MagicMock that raises Exception.

        Action:
        Call get_active_sessions.

        Assertion Strategy:
        Validates exception wrapping by confirming:
        - result.success is False.
        - result.message contains "Failed to get active sessions".

        Testing Principle:
        Validates read-path fault containment, ensuring storage failures in
        query operations produce structured errors.
        """
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
    """Tests for get_observability report generation and error handling.

    get_observability generates analytics reports across sessions, interactions,
    and issues. These tests verify session-filtered reports, nonexistent session
    handling, and storage exception recovery.
    """

    def test_success_with_valid_session_id(self) -> None:
        """Verifies get_observability generates a report filtered to a specific session.

        Tests that when a valid session_id is provided, the report is scoped to
        that session's data only.

        Business context:
        Per-session observability reports allow developers to review the
        effectiveness and issues of a specific work session, supporting targeted
        retrospectives and quality improvement.

        Arrangement:
        1. Create mock storage with one completed session.
        2. Add two interactions: one for the target session, one for another.
        3. Leave issues empty.

        Action:
        Call get_observability with session_id="session1".

        Assertion Strategy:
        Validates filtered report generation by confirming:
        - result.success is True.
        - result.data contains a "report" key (report was generated).

        Testing Principle:
        Validates per-session report scoping, ensuring the observability
        report respects the session_id filter.
        """
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
        """Verifies get_observability fails when the filtered session doesn't exist.

        Tests that requesting a report for a nonexistent session produces a clear
        error rather than an empty or misleading report.

        Business context:
        Users may pass stale or mistyped session IDs. A clear "not found" error
        is more helpful than generating an empty report that might be mistaken
        for a session with no activity.

        Arrangement:
        1. Create a SessionService with empty mock storage.

        Action:
        Call get_observability with session_id="nonexistent".

        Assertion Strategy:
        Validates lookup failure by confirming:
        - result.success is False.
        - result.message contains "Session not found".

        Testing Principle:
        Validates explicit failure over silent emptiness, ensuring users get
        unambiguous feedback when a session ID doesn't exist.
        """
        storage = MockStorage()
        service = SessionService(storage=storage)

        result = service.get_observability(session_id="nonexistent")

        assert result.success is False
        assert "Session not found" in result.message

    def test_exception_handling(self) -> None:
        """Verifies get_observability catches and wraps storage exceptions.

        Tests that when load_sessions raises during report generation, the
        exception is caught and returned as a structured failure result.

        Business context:
        Observability reports may be queried by automated dashboards or health
        checks. Storage failures must produce structured errors so that upstream
        systems can detect and handle the failure appropriately.

        Arrangement:
        1. Create a SessionService with mock storage.
        2. Replace load_sessions with a MagicMock that raises Exception.

        Action:
        Call get_observability without a session filter (triggers load_sessions).

        Assertion Strategy:
        Validates exception wrapping by confirming:
        - result.success is False.
        - result.message contains "Failed to generate report".

        Testing Principle:
        Validates fault containment in read-heavy operations, ensuring report
        generation failures are structured and recoverable.
        """
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
    """Tests for close_active_sessions_on_shutdown method.

    This method is called during MCP server shutdown to cleanly close all
    active sessions. It uses duration capping for stale sessions, similar
    to _auto_close_active_sessions but across all execution contexts.
    """

    def test_closes_active_sessions_with_capped_duration(self) -> None:
        """Verifies shutdown closes stale sessions with capped duration and audit notes.

        Tests the complete shutdown cleanup flow: finding active sessions,
        applying duration capping, updating status, and annotating notes.

        Business context:
        When the MCP server shuts down (deployment, crash recovery, etc.), all
        active sessions must be closed to prevent orphaned "active" records from
        accumulating. Duration capping ensures abandoned sessions don't inflate
        time-tracking metrics in post-shutdown analytics.

        Arrangement:
        1. Create a SessionService with mock storage.
        2. Insert an active session started 12 hours ago (exceeds 4h max).
        3. Override config with max_session_duration=4.0.

        Action:
        Call close_active_sessions_on_shutdown under the 4h config override.

        Assertion Strategy:
        Validates shutdown cleanup by confirming:
        - Return count is 1 (one session was closed).
        - Session status is updated to "completed".
        - Notes contain "exceeded 4.0h max" for duration capping audit trail.
        - Notes contain "server shutdown" to distinguish from normal closes.

        Testing Principle:
        Validates graceful shutdown behavior, ensuring all active sessions are
        properly finalized with accurate metadata before the server exits.
        """
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
        """Verifies shutdown handles storage exceptions without crashing the server.

        Tests that when load_sessions raises during shutdown, the method returns
        0 rather than propagating the exception.

        Business context:
        The shutdown handler runs during process termination. An unhandled
        exception here could cause a dirty exit, leave resources unreleased,
        or trigger error alerts that mask the real shutdown reason. The method
        must degrade gracefully.

        Arrangement:
        1. Create a SessionService with mock storage.
        2. Replace load_sessions with a MagicMock that raises Exception.

        Action:
        Call close_active_sessions_on_shutdown.

        Assertion Strategy:
        Validates graceful degradation by confirming:
        - Return value is 0 (not an exception).
        - No unhandled exception propagates.

        Testing Principle:
        Validates shutdown resilience, ensuring the server can exit cleanly
        even when the storage layer is unavailable.
        """
        storage = MockStorage()
        service = SessionService(storage=storage)

        # Make load_sessions raise an exception
        storage.load_sessions = MagicMock(side_effect=Exception("Load failed"))

        count = service.close_active_sessions_on_shutdown()

        # Should return 0, not raise
        assert count == 0
