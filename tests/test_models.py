"""Tests for models module."""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from ai_session_tracker_mcp.models import (
    FunctionMetrics,
    Interaction,
    Issue,
    Session,
    _generate_session_id,
    _now_iso,
)


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_now_iso_returns_string(self) -> None:
        """Verifies _now_iso returns string type for JSON serialization.

        Tests that the timestamp helper produces a string value suitable
        for storage in JSON files.

        Business context:
        All timestamps must be strings for JSON storage. Native datetime
        objects are not JSON-serializable.

        Arrangement:
        None - tests function with no arguments.

        Action:
        Call _now_iso() helper function.

        Assertion Strategy:
        Validates return type is str.

        Testing Principle:
        Validates type contract for serialization compatibility.
        """
        result = _now_iso()
        assert isinstance(result, str)

    def test_now_iso_is_iso_format(self) -> None:
        """Verifies _now_iso returns valid ISO 8601 format.

        Tests that the timestamp string can be parsed back to datetime,
        confirming proper ISO format.

        Business context:
        ISO 8601 is the standard for timestamp interchange. All systems
        can parse this format reliably.

        Arrangement:
        None - tests function with no arguments.

        Action:
        Call _now_iso() and attempt to parse result.

        Assertion Strategy:
        Validates datetime.fromisoformat() succeeds without exception.

        Testing Principle:
        Validates format compliance for interoperability.
        """
        result = _now_iso()
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(result)
        assert parsed is not None

    def test_generate_session_id_format(self) -> None:
        """Verifies session ID follows expected format pattern.

        Tests that generated IDs match the format: {sanitized}_{YYYYMMDD}_{HHMMSS}
        for consistent, sortable, human-readable identifiers.

        Business context:
        Session IDs appear in logs and dashboards. Predictable format
        aids debugging and allows chronological sorting.

        Arrangement:
        None - tests function with sample input.

        Action:
        Call _generate_session_id() with test name.

        Assertion Strategy:
        Validates result matches regex pattern for format.

        Testing Principle:
        Validates identifier format for consistency.
        """
        result = _generate_session_id("Test Session")
        # Format: {sanitized}_{YYYYMMDD}_{HHMMSS}
        pattern = r"^[a-z0-9_]+_\d{8}_\d{6}$"
        assert re.match(pattern, result)

    @pytest.mark.parametrize(
        "input_name,expected_substring,forbidden_char",
        [
            pytest.param("hello world", "hello_world", " ", id="sanitizes_spaces"),
            pytest.param("hello-world", "hello_world", "-", id="sanitizes_hyphens"),
            pytest.param("HELLO World", "hello_world", None, id="lowercases"),
        ],
    )
    def test_generate_session_id_sanitization(
        self, input_name: str, expected_substring: str, forbidden_char: str | None
    ) -> None:
        """
        Verifies session ID sanitizes input names correctly.

        Tests that spaces become underscores, hyphens become underscores,
        and uppercase is converted to lowercase.

        Business context:
        IDs are used in filenames and URLs. Proper sanitization ensures
        filesystem safety and consistent word separation.

        Arrangement:
        1. input_name contains characters needing sanitization.
        2. expected_substring is what the name should contain after.
        3. forbidden_char is the character that should be removed.

        Action:
        Call _generate_session_id(input_name) to get sanitized result.

        Assertion Strategy:
        Validates expected_substring is present and forbidden_char is absent.
        For lowercase tests, verifies no uppercase characters remain.

        Testing Principle:
        Parameterized test validates sanitization rules.
        """
        result = _generate_session_id(input_name)
        assert expected_substring in result
        if forbidden_char:
            assert forbidden_char not in result
        else:
            # For lowercase test, verify no uppercase
            assert not any(c.isupper() for c in result)

    def test_generate_session_id_truncates_long_names(self) -> None:
        """
        Verifies session ID truncates names longer than 30 characters.

        Tests that excessively long names are truncated to prevent
        unwieldy identifiers.

        Business context:
        Long IDs are hard to read and may cause display issues. 30
        character limit balances readability with uniqueness.

        Arrangement:
        Create a test name with 50 characters (exceeds 30 char limit).

        Action:
        Call _generate_session_id() with the oversized name.

        Assertion Strategy:
        Validates that the first part of the ID (before timestamp) is
        at most 30 characters, confirming truncation.

        Testing Principle:
        Tests boundary condition for identifier length limits.
        """
        long_name = "a" * 50
        result = _generate_session_id(long_name)
        # Should have 30 chars + _ + date + _ + time
        parts = result.split("_")
        assert len(parts[0]) <= 30


class TestSession:
    """Tests for Session dataclass."""

    def test_create_sets_id(self) -> None:
        """Verifies Session.create() generates unique session ID.

        Tests that the factory method produces a non-empty ID for
        identifying the session across operations.

        Business context:
        Session ID is the primary key for all session operations.
        Every session must have a unique, non-empty identifier.

        Arrangement:
        Prepare complete session creation arguments.

        Action:
        Call Session.create() factory method.

        Assertion Strategy:
        Validates id is not None and has length > 0.

        Testing Principle:
        Validates primary key generation.
        """
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.id is not None
        assert len(session.id) > 0

    @pytest.mark.parametrize(
        "session_kwargs,attr_name,expected_value",
        [
            pytest.param(
                {
                    "name": "Test Session",
                    "task_type": "code_generation",
                    "model_name": "claude-opus-4-20250514",
                    "human_time_estimate_minutes": 30.0,
                    "estimate_source": "manual",
                },
                "name",
                "Test Session",
                id="name",
            ),
            pytest.param(
                {
                    "name": "Test",
                    "task_type": "debugging",
                    "model_name": "gpt-4o",
                    "human_time_estimate_minutes": 60.0,
                    "estimate_source": "issue_tracker",
                },
                "task_type",
                "debugging",
                id="task_type",
            ),
            pytest.param(
                {
                    "name": "Test",
                    "task_type": "code_generation",
                    "model_name": "claude-opus-4-20250514",
                    "human_time_estimate_minutes": 30.0,
                    "estimate_source": "manual",
                },
                "model_name",
                "claude-opus-4-20250514",
                id="model_name",
            ),
            pytest.param(
                {
                    "name": "Test",
                    "task_type": "code_generation",
                    "model_name": "claude-opus-4-20250514",
                    "human_time_estimate_minutes": 45.5,
                    "estimate_source": "manual",
                },
                "human_time_estimate_minutes",
                45.5,
                id="human_time_estimate",
            ),
            pytest.param(
                {
                    "name": "Test",
                    "task_type": "code_generation",
                    "model_name": "claude-opus-4-20250514",
                    "human_time_estimate_minutes": 30.0,
                    "estimate_source": "issue_tracker",
                },
                "estimate_source",
                "issue_tracker",
                id="estimate_source",
            ),
            pytest.param(
                {
                    "name": "Test",
                    "task_type": "code_generation",
                    "model_name": "claude-opus-4-20250514",
                    "human_time_estimate_minutes": 30.0,
                    "estimate_source": "manual",
                    "context": "Some context",
                },
                "context",
                "Some context",
                id="context",
            ),
        ],
    )
    def test_create_sets_field(
        self, session_kwargs: dict, attr_name: str, expected_value: object
    ) -> None:
        """
        Verifies Session.create() correctly sets various fields.

        Tests that each field provided to the factory method is stored
        correctly in the session object.

        Business context:
        Session fields are used for display, filtering, and ROI calculations.
        All fields must be accurately stored.

        Arrangement:
        1. Prepare session_kwargs dict with field values from parametrize.
        2. attr_name identifies which field to verify.
        3. expected_value is the value that should be stored.

        Action:
        Call Session.create() with the kwargs and access the named attribute.

        Assertion Strategy:
        Validates that getattr(session, attr_name) equals expected_value,
        confirming the factory correctly assigns each field.

        Testing Principle:
        Parameterized test validates field assignment from factory.
        """
        session = Session.create(
            session_kwargs["name"],
            session_kwargs["task_type"],
            model_name=session_kwargs["model_name"],
            human_time_estimate_minutes=session_kwargs["human_time_estimate_minutes"],
            estimate_source=session_kwargs["estimate_source"],
            context=session_kwargs.get("context", ""),
        )
        assert getattr(session, attr_name) == expected_value

    @pytest.mark.parametrize(
        "attr_name,expected_value",
        [
            pytest.param("context", "", id="context_empty"),
            pytest.param("status", "active", id="status_active"),
            pytest.param("end_time", None, id="end_time_none"),
            pytest.param("outcome", None, id="outcome_none"),
            pytest.param("notes", "", id="notes_empty"),
            pytest.param("total_interactions", 0, id="total_interactions_zero"),
            pytest.param("avg_effectiveness", 0.0, id="avg_effectiveness_zero"),
            pytest.param("code_metrics", [], id="code_metrics_empty"),
            pytest.param("developer", "", id="developer_empty"),
            pytest.param("project", "", id="project_empty"),
        ],
    )
    def test_create_defaults(self, attr_name: str, expected_value: object) -> None:
        """
        Verifies Session.create() sets sensible default values.

        Tests that optional fields default to appropriate values when
        not explicitly provided.

        Business context:
        Default values enable creating sessions with minimal required
        fields. Empty/zero defaults prevent None handling issues.

        Arrangement:
        1. attr_name identifies which default field to verify.
        2. expected_value is the expected default (empty string, 0, None, etc.).

        Action:
        Call Session.create() with only required fields, omitting optional ones.

        Assertion Strategy:
        Validates that getattr(session, attr_name) equals expected_value,
        confirming default assignment.

        Testing Principle:
        Parameterized test validates default value assignment.
        """
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert getattr(session, attr_name) == expected_value

    def test_create_sets_start_time(self) -> None:
        """Verifies Session.create() sets start_time to current timestamp.

        Tests that session creation captures the current timestamp in ISO
        format for duration calculations.

        Business context:
        Start time is used with end_time to calculate session duration
        for productivity metrics and cost analysis.

        Arrangement:
        None - tests factory method directly.

        Action:
        Call Session.create() and access start_time property.

        Assertion Strategy:
        Validates start_time is not None and parses as valid datetime.

        Testing Principle:
        Validates timestamp capture and format compliance.
        """
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.start_time is not None
        # Should be parseable
        datetime.fromisoformat(session.start_time)

    def test_end_sets_status_completed(self) -> None:
        """Verifies Session.end() sets status to completed.

        Tests that ending a session transitions status from 'active'
        to 'completed'.

        Business context:
        Completed status indicates session is done. Active sessions
        are excluded from some statistics.

        Arrangement:
        Create an active session.

        Action:
        Call session.end() with any outcome.

        Assertion Strategy:
        Validates status equals 'completed'.

        Testing Principle:
        Validates state machine transition.
        """
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        session.end("success")
        assert session.status == "completed"

    def test_end_sets_end_time(self) -> None:
        """Verifies Session.end() sets end_time to current timestamp.

        Tests that ending a session captures the completion timestamp
        for duration calculation.

        Business context:
        End time enables duration calculation. Duration is key metric
        for productivity and cost analysis.

        Arrangement:
        Create an active session.

        Action:
        Call session.end() with outcome.

        Assertion Strategy:
        Validates end_time is not None after ending.

        Testing Principle:
        Validates state transition timestamp capture.
        """
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        session.end("success")
        assert session.end_time is not None

    def test_end_sets_outcome(self) -> None:
        """Verifies Session.end() sets outcome value.

        Tests that ending a session stores the provided outcome
        (success/partial/failed).

        Business context:
        Outcome indicates how well the session went. Used for filtering,
        quality analysis, and success rate calculations.

        Arrangement:
        Create an active session.

        Action:
        Call session.end() with 'partial' outcome.

        Assertion Strategy:
        Validates outcome matches provided value.

        Testing Principle:
        Validates state transition parameter storage.
        """
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        session.end("partial")
        assert session.outcome == "partial"

    def test_end_sets_notes(self) -> None:
        """Verifies Session.end() sets notes when provided.

        Tests that optional notes parameter is stored on session end
        for additional documentation.

        Business context:
        Notes capture details about what was done or learned. Useful
        for retrospective analysis and knowledge sharing.

        Arrangement:
        Create an active session.

        Action:
        Call session.end() with notes parameter.

        Assertion Strategy:
        Validates notes matches provided value.

        Testing Principle:
        Validates optional parameter handling.
        """
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        session.end("success", "All tests passing")
        assert session.notes == "All tests passing"

    def test_to_dict_includes_all_fields(self) -> None:
        """Verifies Session.to_dict() includes all session fields.

        Tests that serialization produces dictionary with all required
        keys for JSON storage.

        Business context:
        Complete serialization is essential for persistence. Missing
        fields would cause data loss or deserialization errors.

        Arrangement:
        Create session with context set.

        Action:
        Call session.to_dict() method.

        Assertion Strategy:
        Validates all expected field keys exist in result dict.

        Testing Principle:
        Validates serialization completeness.
        """
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
            context="ctx",
        )
        result = session.to_dict()

        assert "id" in result
        assert "session_name" in result
        assert "task_type" in result
        assert "context" in result
        assert "start_time" in result
        assert "model_name" in result
        assert "human_time_estimate_minutes" in result
        assert "estimate_source" in result
        assert "status" in result
        assert "end_time" in result
        assert "outcome" in result
        assert "notes" in result
        assert "total_interactions" in result
        assert "avg_effectiveness" in result
        assert "code_metrics" in result
        assert "developer" in result
        assert "project" in result

    def test_to_dict_values_match(self) -> None:
        """Verifies Session.to_dict() values match session attributes.

        Tests that serialized values accurately reflect the session's
        current state.

        Business context:
        Value accuracy is critical for data integrity. Incorrect
        serialization would corrupt persisted data.

        Arrangement:
        Create session with various non-default values.

        Action:
        Call session.to_dict() method.

        Assertion Strategy:
        Validates each dict value matches corresponding attribute.

        Testing Principle:
        Validates serialization accuracy.
        """
        session = Session.create(
            "Test Session",
            "debugging",
            model_name="gpt-4o",
            human_time_estimate_minutes=60.0,
            estimate_source="issue_tracker",
            context="context",
        )
        result = session.to_dict()

        assert result["id"] == session.id
        assert result["session_name"] == session.name
        assert result["task_type"] == "debugging"
        assert result["context"] == "context"
        assert result["model_name"] == "gpt-4o"
        assert result["human_time_estimate_minutes"] == 60.0
        assert result["estimate_source"] == "issue_tracker"

    def test_from_dict_creates_session(self) -> None:
        """Verifies Session.from_dict() creates session from dictionary.

        Tests that deserialization reconstructs a valid Session object
        with all field values preserved.

        Business context:
        Loading sessions from storage requires accurate reconstruction.
        All fields must be correctly mapped from dict keys.

        Arrangement:
        Create dict with all required session fields.

        Action:
        Call Session.from_dict() with the dict.

        Assertion Strategy:
        Validates all session attributes match dict values.

        Testing Principle:
        Validates deserialization correctness.
        """
        data = {
            "id": "test_123",
            "session_name": "Test",
            "task_type": "debugging",
            "context": "ctx",
            "start_time": "2024-01-01T00:00:00+00:00",
            "model_name": "claude-opus-4-20250514",
            "human_time_estimate_minutes": 45.0,
            "estimate_source": "manual",
            "status": "active",
            "end_time": None,
            "outcome": None,
            "notes": "",
            "total_interactions": 5,
            "avg_effectiveness": 4.2,
            "code_metrics": [],
        }
        session = Session.from_dict(data)

        assert session.id == "test_123"
        assert session.name == "Test"
        assert session.task_type == "debugging"
        assert session.model_name == "claude-opus-4-20250514"
        assert session.human_time_estimate_minutes == 45.0
        assert session.estimate_source == "manual"
        assert session.total_interactions == 5
        assert session.avg_effectiveness == 4.2

    def test_from_dict_handles_legacy_name_field(self) -> None:
        """Verifies Session.from_dict() handles 'name' instead of 'session_name'.

        Tests backward compatibility with older data format that used
        'name' field instead of 'session_name'.

        Business context:
        Existing session data may use old field names. Migration must
        be seamless to avoid breaking historical data.

        Arrangement:
        Create dict with 'name' field (legacy format).

        Action:
        Call Session.from_dict() with legacy dict.

        Assertion Strategy:
        Validates session.name contains the legacy field value.

        Testing Principle:
        Validates backward compatibility.
        """
        data = {
            "id": "test_123",
            "name": "Legacy Name",  # Old field name
            "task_type": "debugging",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        session = Session.from_dict(data)
        assert session.name == "Legacy Name"

    def test_roundtrip_serialization(self) -> None:
        """Verifies to_dict() and from_dict() are inverse operations.

        Tests that serializing and deserializing produces an equivalent
        session with all values preserved.

        Business context:
        Data integrity across storage cycles is critical. Sessions must
        survive save/load without data loss.

        Arrangement:
        Create session with various values including ended state.

        Action:
        Call to_dict() then from_dict() on the result.

        Assertion Strategy:
        Validates all restored attributes match original values.

        Testing Principle:
        Validates roundtrip data integrity.
        """
        original = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
            context="ctx",
        )
        original.end("success", "notes")
        original.total_interactions = 10
        original.avg_effectiveness = 4.5

        data = original.to_dict()
        restored = Session.from_dict(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.task_type == original.task_type
        assert restored.model_name == original.model_name
        assert restored.human_time_estimate_minutes == original.human_time_estimate_minutes
        assert restored.estimate_source == original.estimate_source
        assert restored.status == original.status
        assert restored.outcome == original.outcome
        assert restored.total_interactions == original.total_interactions


class TestInteraction:
    """Tests for Interaction dataclass."""

    def test_create_sets_session_id(self) -> None:
        """Verifies Interaction.create() sets session_id.

        Tests that the interaction is linked to its parent session
        for retrieval and aggregation.

        Business context:
        Session ID links interactions to sessions. Required for
        calculating session-level effectiveness metrics.

        Arrangement:
        Prepare session ID and interaction parameters.

        Action:
        Call Interaction.create() factory method.

        Assertion Strategy:
        Validates session_id matches provided value.

        Testing Principle:
        Validates foreign key assignment.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.session_id == "sess_123"

    def test_create_sets_timestamp(self) -> None:
        """Verifies Interaction.create() sets timestamp.

        Tests that interaction creation captures the current time
        in ISO format for chronological ordering.

        Business context:
        Timestamps enable interaction timeline display and analysis
        of interaction patterns over session duration.

        Arrangement:
        None - tests factory method directly.

        Action:
        Call Interaction.create() and access timestamp.

        Assertion Strategy:
        Validates timestamp is not None and parses as datetime.

        Testing Principle:
        Validates automatic timestamp generation.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.timestamp is not None
        datetime.fromisoformat(interaction.timestamp)

    def test_create_sets_prompt(self) -> None:
        """Verifies Interaction.create() sets prompt.

        Tests that the user's prompt text is stored for analysis
        and display purposes.

        Business context:
        Prompt text shows what was asked of the AI. Useful for
        analyzing interaction patterns and debugging issues.

        Arrangement:
        Prepare prompt string.

        Action:
        Call Interaction.create() with prompt.

        Assertion Strategy:
        Validates prompt matches provided value.

        Testing Principle:
        Validates field assignment from factory.
        """
        interaction = Interaction.create("sess_123", "my prompt", "response", 4)
        assert interaction.prompt == "my prompt"

    def test_create_sets_response_summary(self) -> None:
        """Verifies Interaction.create() sets response_summary.

        Tests that the AI response summary is stored for review
        and analysis.

        Business context:
        Response summary captures what the AI provided. Kept brief
        to avoid storing full responses which could be large.

        Arrangement:
        Prepare response summary string.

        Action:
        Call Interaction.create() with response_summary.

        Assertion Strategy:
        Validates response_summary matches provided value.

        Testing Principle:
        Validates field assignment from factory.
        """
        interaction = Interaction.create("sess_123", "prompt", "my response", 4)
        assert interaction.response_summary == "my response"

    def test_create_sets_effectiveness_rating(self) -> None:
        """Verifies Interaction.create() sets effectiveness_rating.

        Tests that the user's rating of AI helpfulness is stored
        for quality metrics.

        Business context:
        Effectiveness rating (1-5) indicates how helpful the AI was.
        Aggregated into session avg_effectiveness for ROI reporting.

        Arrangement:
        Prepare rating value (4 out of 5).

        Action:
        Call Interaction.create() with rating.

        Assertion Strategy:
        Validates rating matches provided value.

        Testing Principle:
        Validates numeric field assignment.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.effectiveness_rating == 4

    def test_create_clamps_rating_min(self) -> None:
        """Verifies Interaction.create() clamps rating to minimum 1.

        Tests that ratings below valid range are clamped to 1 rather
        than stored as invalid values.

        Business context:
        Rating scale is 1-5. Values outside range would skew metrics.
        Clamping ensures data validity without raising errors.

        Arrangement:
        Prepare invalid rating (0).

        Action:
        Call Interaction.create() with below-range rating.

        Assertion Strategy:
        Validates rating is clamped to 1.

        Testing Principle:
        Validates input boundary enforcement.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 0)
        assert interaction.effectiveness_rating == 1

    def test_create_clamps_rating_max(self) -> None:
        """Verifies Interaction.create() clamps rating to maximum 5.

        Tests that ratings above valid range are clamped to 5 rather
        than stored as invalid values.

        Business context:
        Rating scale is 1-5. Values outside range would skew metrics.
        Clamping ensures data validity without raising errors.

        Arrangement:
        Prepare invalid rating (10).

        Action:
        Call Interaction.create() with above-range rating.

        Assertion Strategy:
        Validates rating is clamped to 5.

        Testing Principle:
        Validates input boundary enforcement.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 10)
        assert interaction.effectiveness_rating == 5

    def test_create_defaults_iteration_count(self) -> None:
        """Verifies Interaction.create() defaults iteration_count to 1.

        Tests that interactions default to 1 iteration when not
        specified.

        Business context:
        Iteration count tracks back-and-forth refinements. Most
        interactions succeed on first try, so 1 is sensible default.

        Arrangement:
        Create interaction without iteration_count parameter.

        Action:
        Call Interaction.create() with required params only.

        Assertion Strategy:
        Validates iteration_count equals 1.

        Testing Principle:
        Validates sensible default value.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.iteration_count == 1

    def test_create_sets_iteration_count(self) -> None:
        """Verifies Interaction.create() sets iteration_count when provided.

        Tests that explicit iteration count is stored for tracking
        refinement attempts.

        Business context:
        Higher iteration counts indicate more complex interactions
        requiring multiple refinement rounds.

        Arrangement:
        Prepare iteration_count value (3).

        Action:
        Call Interaction.create() with iteration_count.

        Assertion Strategy:
        Validates iteration_count matches provided value.

        Testing Principle:
        Validates optional parameter handling.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 4, 3)
        assert interaction.iteration_count == 3

    def test_create_clamps_iteration_count_min(self) -> None:
        """Verifies Interaction.create() clamps iteration_count to minimum 1.

        Tests that zero or negative iteration counts are clamped to 1
        since there's always at least one interaction.

        Business context:
        Iteration count must be positive. Zero would be invalid since
        logging an interaction implies at least one occurred.

        Arrangement:
        Prepare invalid iteration_count (0).

        Action:
        Call Interaction.create() with below-range count.

        Assertion Strategy:
        Validates iteration_count is clamped to 1.

        Testing Principle:
        Validates input boundary enforcement.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 4, 0)
        assert interaction.iteration_count == 1

    def test_create_defaults_tools_used_empty(self) -> None:
        """Verifies Interaction.create() defaults tools_used to empty list.

        Tests that interactions start with no tools tracked when not
        specified.

        Business context:
        Tools used is optional tracking of MCP tools invoked. Empty
        list when not provided for consistent collection handling.

        Arrangement:
        Create interaction without tools_used parameter.

        Action:
        Call Interaction.create() with required params only.

        Assertion Strategy:
        Validates tools_used equals empty list.

        Testing Principle:
        Validates collection field default.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.tools_used == []

    def test_create_sets_tools_used(self) -> None:
        """Verifies Interaction.create() sets tools_used when provided.

        Tests that list of tool names is stored for tracking which
        MCP tools were invoked.

        Business context:
        Tool usage patterns help understand AI behavior. Popular tools
        may need optimization or better documentation.

        Arrangement:
        Prepare list of tool names.

        Action:
        Call Interaction.create() with tools_used list.

        Assertion Strategy:
        Validates tools_used matches provided list.

        Testing Principle:
        Validates collection field assignment.
        """
        tools = ["read_file", "grep_search"]
        interaction = Interaction.create("sess_123", "prompt", "response", 4, 1, tools)
        assert interaction.tools_used == tools

    def test_to_dict_includes_all_fields(self) -> None:
        """Verifies Interaction.to_dict() includes all fields.

        Tests that serialization produces dictionary with all required
        keys for JSON storage.

        Business context:
        Complete serialization is essential for persistence. Missing
        fields would cause data loss or deserialization errors.

        Arrangement:
        Create interaction with all optional fields set.

        Action:
        Call interaction.to_dict() method.

        Assertion Strategy:
        Validates all expected field keys exist in result dict.

        Testing Principle:
        Validates serialization completeness.
        """
        interaction = Interaction.create("sess_123", "prompt", "response", 4, 2, ["tool1"])
        result = interaction.to_dict()

        assert "session_id" in result
        assert "timestamp" in result
        assert "prompt" in result
        assert "response_summary" in result
        assert "effectiveness_rating" in result
        assert "iteration_count" in result
        assert "tools_used" in result

    def test_from_dict_creates_interaction(self) -> None:
        """Verifies Interaction.from_dict() creates interaction from dict.

        Tests that deserialization reconstructs a valid Interaction
        object with all field values preserved.

        Business context:
        Loading interactions from storage requires accurate
        reconstruction for display and analysis.

        Arrangement:
        Create dict with all interaction fields.

        Action:
        Call Interaction.from_dict() with the dict.

        Assertion Strategy:
        Validates all interaction attributes match dict values.

        Testing Principle:
        Validates deserialization correctness.
        """
        data = {
            "session_id": "sess_123",
            "timestamp": "2024-01-01T00:00:00+00:00",
            "prompt": "test prompt",
            "response_summary": "test response",
            "effectiveness_rating": 5,
            "iteration_count": 2,
            "tools_used": ["tool1", "tool2"],
        }
        interaction = Interaction.from_dict(data)

        assert interaction.session_id == "sess_123"
        assert interaction.prompt == "test prompt"
        assert interaction.effectiveness_rating == 5
        assert interaction.tools_used == ["tool1", "tool2"]

    def test_roundtrip_serialization(self) -> None:
        """Verifies to_dict() and from_dict() are inverse operations.

        Tests that serializing and deserializing produces an equivalent
        interaction with all values preserved.

        Business context:
        Data integrity across storage cycles is critical. Interactions
        must survive save/load without data loss.

        Arrangement:
        Create interaction with all optional fields.

        Action:
        Call to_dict() then from_dict() on the result.

        Assertion Strategy:
        Validates key restored attributes match original values.

        Testing Principle:
        Validates roundtrip data integrity.
        """
        original = Interaction.create("sess_123", "prompt", "response", 4, 2, ["tool1"])
        data = original.to_dict()
        restored = Interaction.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.prompt == original.prompt
        assert restored.effectiveness_rating == original.effectiveness_rating


class TestIssue:
    """Tests for Issue dataclass."""

    def test_create_sets_session_id(self) -> None:
        """Verifies Issue.create() sets session_id.

        Tests that the issue is linked to its parent session for
        retrieval and aggregation.

        Business context:
        Session ID links issues to sessions. Required for tracking
        which sessions had problems.

        Arrangement:
        Prepare session ID and issue parameters.

        Action:
        Call Issue.create() factory method.

        Assertion Strategy:
        Validates session_id matches provided value.

        Testing Principle:
        Validates foreign key assignment.
        """
        issue = Issue.create("sess_123", "incorrect_output", "desc", "high")
        assert issue.session_id == "sess_123"

    def test_create_sets_timestamp(self) -> None:
        """Verifies Issue.create() sets timestamp.

        Tests that issue creation captures the current time in ISO
        format for chronological tracking.

        Business context:
        Timestamps show when issues occurred for timeline analysis
        and correlation with session events.

        Arrangement:
        None - tests factory method directly.

        Action:
        Call Issue.create() and access timestamp.

        Assertion Strategy:
        Validates timestamp is not None and parses as datetime.

        Testing Principle:
        Validates automatic timestamp generation.
        """
        issue = Issue.create("sess_123", "incorrect_output", "desc", "high")
        assert issue.timestamp is not None
        datetime.fromisoformat(issue.timestamp)

    def test_create_sets_issue_type(self) -> None:
        """Verifies Issue.create() sets issue_type.

        Tests that the issue type is stored for categorization and
        pattern analysis.

        Business context:
        Issue types (hallucination, incorrect_output, etc.) enable
        analysis of common failure modes.

        Arrangement:
        Prepare issue type string.

        Action:
        Call Issue.create() with issue_type.

        Assertion Strategy:
        Validates issue_type matches provided value.

        Testing Principle:
        Validates field assignment from factory.
        """
        issue = Issue.create("sess_123", "hallucination", "desc", "high")
        assert issue.issue_type == "hallucination"

    def test_create_sets_description(self) -> None:
        """Verifies Issue.create() sets description.

        Tests that the issue description is stored for documentation
        and troubleshooting.

        Business context:
        Description provides details about what went wrong. Essential
        for understanding and addressing the issue.

        Arrangement:
        Prepare description string.

        Action:
        Call Issue.create() with description.

        Assertion Strategy:
        Validates description matches provided value.

        Testing Principle:
        Validates field assignment from factory.
        """
        issue = Issue.create("sess_123", "type", "my description", "high")
        assert issue.description == "my description"

    def test_create_sets_severity(self) -> None:
        """Verifies Issue.create() sets severity.

        Tests that the severity level is stored for prioritization
        and impact assessment.

        Business context:
        Severity (critical/high/medium/low) enables prioritization
        and filtering of issues by importance.

        Arrangement:
        Prepare severity string.

        Action:
        Call Issue.create() with severity.

        Assertion Strategy:
        Validates severity matches provided value.

        Testing Principle:
        Validates field assignment from factory.
        """
        issue = Issue.create("sess_123", "type", "desc", "critical")
        assert issue.severity == "critical"

    def test_create_defaults_resolved_false(self) -> None:
        """Verifies Issue.create() defaults resolved to False.

        Tests that new issues are marked as unresolved by default.

        Business context:
        New issues start as unresolved. Resolved flag is set later
        when the issue is addressed.

        Arrangement:
        Create issue without resolved parameter.

        Action:
        Call Issue.create() and access resolved property.

        Assertion Strategy:
        Validates resolved equals False.

        Testing Principle:
        Validates sensible default value.
        """
        issue = Issue.create("sess_123", "type", "desc", "high")
        assert issue.resolved is False

    def test_create_defaults_resolution_notes_empty(self) -> None:
        """Verifies Issue.create() defaults resolution_notes to empty string.

        Tests that new issues have empty resolution notes since they
        haven't been resolved yet.

        Business context:
        Resolution notes are added when issue is resolved. Empty string
        for consistent string handling.

        Arrangement:
        Create issue without resolution_notes parameter.

        Action:
        Call Issue.create() and access resolution_notes property.

        Assertion Strategy:
        Validates resolution_notes equals empty string.

        Testing Principle:
        Validates sensible default value.
        """
        issue = Issue.create("sess_123", "type", "desc", "high")
        assert issue.resolution_notes == ""

    def test_to_dict_includes_all_fields(self) -> None:
        """Verifies Issue.to_dict() includes all fields.

        Tests that serialization produces dictionary with all required
        keys for JSON storage.

        Business context:
        Complete serialization is essential for persistence. Missing
        fields would cause data loss or deserialization errors.

        Arrangement:
        Create issue with default values.

        Action:
        Call issue.to_dict() method.

        Assertion Strategy:
        Validates all expected field keys exist in result dict.

        Testing Principle:
        Validates serialization completeness.
        """
        issue = Issue.create("sess_123", "type", "desc", "high")
        result = issue.to_dict()

        assert "session_id" in result
        assert "timestamp" in result
        assert "issue_type" in result
        assert "description" in result
        assert "severity" in result
        assert "resolved" in result
        assert "resolution_notes" in result

    def test_from_dict_creates_issue(self) -> None:
        """Verifies Issue.from_dict() creates issue from dict.

        Tests that deserialization reconstructs a valid Issue object
        with all field values preserved.

        Business context:
        Loading issues from storage requires accurate reconstruction
        for display, filtering, and analysis.

        Arrangement:
        Create dict with all issue fields including resolved state.

        Action:
        Call Issue.from_dict() with the dict.

        Assertion Strategy:
        Validates all issue attributes match dict values.

        Testing Principle:
        Validates deserialization correctness.
        """
        data = {
            "session_id": "sess_123",
            "timestamp": "2024-01-01T00:00:00+00:00",
            "issue_type": "hallucination",
            "description": "AI invented API",
            "severity": "high",
            "resolved": True,
            "resolution_notes": "Fixed manually",
        }
        issue = Issue.from_dict(data)

        assert issue.session_id == "sess_123"
        assert issue.issue_type == "hallucination"
        assert issue.severity == "high"
        assert issue.resolved is True
        assert issue.resolution_notes == "Fixed manually"

    def test_roundtrip_serialization(self) -> None:
        """Verifies to_dict() and from_dict() are inverse operations.

        Tests that serializing and deserializing produces an equivalent
        issue with all values preserved.

        Business context:
        Data integrity across storage cycles is critical. Issues must
        survive save/load without data loss.

        Arrangement:
        Create issue with resolved state and notes.

        Action:
        Call to_dict() then from_dict() on the result.

        Assertion Strategy:
        Validates key restored attributes match original values.

        Testing Principle:
        Validates roundtrip data integrity.
        """
        original = Issue.create("sess_123", "type", "desc", "medium")
        original.resolved = True
        original.resolution_notes = "notes"

        data = original.to_dict()
        restored = Issue.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.issue_type == original.issue_type
        assert restored.resolved == original.resolved


class TestFunctionMetrics:
    """Tests for FunctionMetrics dataclass."""

    def test_defaults(self) -> None:
        """Verifies FunctionMetrics default values are set correctly.

        Tests that optional fields have sensible defaults when creating
        a minimal FunctionMetrics instance.

        Business context:
        Default values enable creating metrics with minimal required
        fields. Sensible defaults prevent invalid calculations.

        Arrangement:
        Create FunctionMetrics with only required fields.

        Action:
        Access all optional field values.

        Assertion Strategy:
        Validates each default matches expected value.

        Testing Principle:
        Validates dataclass field defaults.
        """
        metrics = FunctionMetrics(
            function_name="test_func",
            modification_type="added",
        )
        assert metrics.lines_added == 0
        assert metrics.lines_modified == 0
        assert metrics.lines_deleted == 0
        assert metrics.complexity == 1
        assert metrics.documentation_score == 0
        assert metrics.has_docstring is False
        assert metrics.has_type_hints is False

    def test_effort_score_lines_added(self) -> None:
        """Verifies effort_score counts lines_added * 1.0.

        Tests that added lines contribute full weight to effort score.

        Business context:
        New code requires most effort to write from scratch. Full
        weight (1.0x) reflects this higher effort.

        Arrangement:
        Create metrics with only lines_added set.

        Action:
        Call effort_score() method.

        Assertion Strategy:
        Validates result equals lines_added * 1.0.

        Testing Principle:
        Validates calculation component isolation.
        """
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="added",
            lines_added=10,
        )
        assert metrics.effort_score() == 10.0

    def test_effort_score_lines_modified(self) -> None:
        """Verifies effort_score counts lines_modified * 0.5.

        Tests that modified lines contribute half weight plus complexity.

        Business context:
        Modifications require less effort than new code since context
        exists. Half weight (0.5x) plus context complexity.

        Arrangement:
        Create metrics with lines_modified for 'modified' type.

        Action:
        Call effort_score() method.

        Assertion Strategy:
        Validates result equals 10 * 0.5 + 1 * 0.1 = 5.1.

        Testing Principle:
        Validates calculation with default complexity.
        """
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="modified",
            lines_modified=10,
        )
        # 10 * 0.5 + complexity(1) * 0.1 = 5.0 + 0.1 = 5.1
        assert metrics.effort_score() == 5.1

    def test_effort_score_context_complexity_for_modified(self) -> None:
        """Verifies effort_score includes context complexity for modified.

        Tests that complexity adds to effort for modified functions
        since understanding existing code takes effort.

        Business context:
        Complex existing code is harder to modify. Context complexity
        factor (0.1x) rewards working with complex code.

        Arrangement:
        Create metrics with high complexity for 'modified' type.

        Action:
        Call effort_score() method.

        Assertion Strategy:
        Validates result includes complexity * 0.1.

        Testing Principle:
        Validates context complexity factor.
        """
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="modified",
            complexity=5,
        )
        # 0 * 1.0 + 0 * 0.5 + 5 * 0.1 = 0.5
        assert metrics.effort_score() == 0.5

    def test_effort_score_no_context_for_added(self) -> None:
        """Verifies effort_score excludes context complexity for added.

        Tests that complexity does not add to effort for new functions
        since there's no existing code to understand.

        Business context:
        New functions have no prior context to understand. Context
        complexity only applies to modifications.

        Arrangement:
        Create metrics with high complexity for 'added' type.

        Action:
        Call effort_score() method.

        Assertion Strategy:
        Validates result is 0 (no lines, no context factor).

        Testing Principle:
        Validates modification type affects calculation.
        """
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="added",
            complexity=5,
        )
        # Context complexity is 0 for added
        assert metrics.effort_score() == 0.0

    def test_effort_score_combined(self) -> None:
        """Verifies effort_score combines all factors correctly.

        Tests that lines_added, lines_modified, and complexity all
        contribute to the final effort score.

        Business context:
        Real refactoring involves multiple types of changes. Combined
        score reflects total effort for mixed modifications.

        Arrangement:
        Create metrics with all line types and complexity.

        Action:
        Call effort_score() method.

        Assertion Strategy:
        Validates result matches expected combined formula.

        Testing Principle:
        Validates complete calculation formula.
        """
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="refactored",
            lines_added=10,
            lines_modified=4,
            complexity=3,
        )
        # 10 * 1.0 + 4 * 0.5 + 3 * 0.1 = 10 + 2 + 0.3 = 12.3
        assert metrics.effort_score() == 12.3

    def test_to_dict_structure(self) -> None:
        """Verifies to_dict() has expected nested structure.

        Tests that serialization produces properly nested dictionary
        with ai_contribution, context, documentation, and value_metrics.

        Business context:
        Nested structure organizes metrics by category for clearer
        presentation and easier access in reports.

        Arrangement:
        Create metrics with all fields populated.

        Action:
        Call to_dict() method.

        Assertion Strategy:
        Validates nested structure and all field values.

        Testing Principle:
        Validates serialization schema.
        """
        metrics = FunctionMetrics(
            function_name="my_func",
            modification_type="added",
            lines_added=20,
            lines_modified=5,
            lines_deleted=2,
            complexity=3,
            documentation_score=75,
            has_docstring=True,
            has_type_hints=True,
        )
        result = metrics.to_dict()

        assert result["function_name"] == "my_func"
        assert result["modification_type"] == "added"

        assert "ai_contribution" in result
        assert result["ai_contribution"]["lines_added"] == 20
        assert result["ai_contribution"]["lines_modified"] == 5
        assert result["ai_contribution"]["lines_deleted"] == 2
        assert result["ai_contribution"]["complexity_added"] == 3  # added type

        assert "context" in result
        assert result["context"]["final_complexity"] == 3
        assert result["context"]["cognitive_load"] == 0  # added type

        assert "documentation" in result
        assert result["documentation"]["has_docstring"] is True
        assert result["documentation"]["quality_score"] == 75
        assert result["documentation"]["has_type_hints"] is True

        assert "value_metrics" in result
        assert "effort_score" in result["value_metrics"]

    def test_to_dict_complexity_added_for_added_type(self) -> None:
        """Verifies complexity_added equals complexity for 'added' type.

        Tests that new functions report their full complexity as
        complexity_added since all complexity is new.

        Business context:
        When adding new code, all complexity is attributed to AI.
        Distinguishes new complexity from existing complexity.

        Arrangement:
        Create metrics with 'added' modification type.

        Action:
        Call to_dict() and check ai_contribution.complexity_added.

        Assertion Strategy:
        Validates complexity_added equals complexity value.

        Testing Principle:
        Validates modification type affects serialization.
        """
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="added",
            complexity=5,
        )
        result = metrics.to_dict()
        assert result["ai_contribution"]["complexity_added"] == 5

    def test_to_dict_complexity_added_zero_for_modified(self) -> None:
        """Verifies complexity_added is 0 for non-added modification types.

        Tests that modified functions report zero complexity_added since
        existing complexity isn't newly introduced.

        Business context:
        When modifying existing code, complexity already existed. Only
        newly added functions contribute new complexity.

        Arrangement:
        Create metrics with 'modified' modification type.

        Action:
        Call to_dict() and check ai_contribution.complexity_added.

        Assertion Strategy:
        Validates complexity_added equals 0.

        Testing Principle:
        Validates modification type affects serialization.
        """
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="modified",
            complexity=5,
        )
        result = metrics.to_dict()
        assert result["ai_contribution"]["complexity_added"] == 0

    def test_to_dict_cognitive_load_zero_for_added(self) -> None:
        """Verifies cognitive_load is 0 for 'added' modification type.

        Tests that new functions have no cognitive load since there's
        no existing code to understand.

        Business context:
        Cognitive load represents effort to understand existing code.
        New functions start fresh with no prior context.

        Arrangement:
        Create metrics with 'added' modification type.

        Action:
        Call to_dict() and check context.cognitive_load.

        Assertion Strategy:
        Validates cognitive_load equals 0.

        Testing Principle:
        Validates modification type affects serialization.
        """
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="added",
            complexity=5,
        )
        result = metrics.to_dict()
        assert result["context"]["cognitive_load"] == 0

    def test_to_dict_cognitive_load_equals_complexity_for_modified(self) -> None:
        """Verifies cognitive_load equals complexity for non-added types.

        Tests that modified functions report complexity as cognitive load
        since understanding existing code requires effort.

        Business context:
        Modifying complex code requires understanding it first. Cognitive
        load captures this comprehension effort.

        Arrangement:
        Create metrics with 'modified' modification type.

        Action:
        Call to_dict() and check context.cognitive_load.

        Assertion Strategy:
        Validates cognitive_load equals complexity value.

        Testing Principle:
        Validates modification type affects serialization.
        """
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="modified",
            complexity=5,
        )
        result = metrics.to_dict()
        assert result["context"]["cognitive_load"] == 5

    def test_from_dict_reconstructs_metrics(self) -> None:
        """Verifies from_dict() reconstructs FunctionMetrics from to_dict() output.

        Tests round-trip serialization/deserialization for data integrity.

        Business context:
        Code metrics must survive storage/load cycle for historical
        analysis and session restoration.

        Arrangement:
        Create FunctionMetrics and serialize to dict via to_dict().

        Action:
        Deserialize with from_dict() and compare key fields.

        Assertion Strategy:
        Validates all fields match original values.

        Testing Principle:
        Validates serialization round-trip.
        """
        original = FunctionMetrics(
            function_name="test_func",
            modification_type="added",
            lines_added=50,
            lines_modified=10,
            lines_deleted=5,
            complexity=8,
            documentation_score=75,
            has_docstring=True,
            has_type_hints=True,
        )
        data = original.to_dict()
        restored = FunctionMetrics.from_dict(data)

        assert restored.function_name == "test_func"
        assert restored.modification_type == "added"
        assert restored.lines_added == 50
        assert restored.lines_modified == 10
        assert restored.lines_deleted == 5
        assert restored.complexity == 8
        assert restored.documentation_score == 75
        assert restored.has_docstring is True
        assert restored.has_type_hints is True

    def test_from_dict_handles_minimal_data(self) -> None:
        """Verifies from_dict() handles minimal dict with defaults.

        Tests that missing optional nested fields get sensible defaults.

        Business context:
        Legacy data may lack some fields. Defaults ensure backwards
        compatibility without data loss.

        Arrangement:
        Create minimal dict with only required fields.

        Action:
        Call from_dict() with minimal data.

        Assertion Strategy:
        Validates defaults are applied for missing fields.

        Testing Principle:
        Validates graceful degradation for incomplete data.
        """
        data = {
            "function_name": "minimal_func",
            "modification_type": "modified",
        }
        metrics = FunctionMetrics.from_dict(data)

        assert metrics.function_name == "minimal_func"
        assert metrics.modification_type == "modified"
        assert metrics.lines_added == 0
        assert metrics.lines_modified == 0
        assert metrics.lines_deleted == 0
        assert metrics.complexity == 1
        assert metrics.documentation_score == 0
        assert metrics.has_docstring is False
        assert metrics.has_type_hints is False
