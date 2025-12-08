"""Tests for models module."""

from __future__ import annotations

import re
from datetime import datetime

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
        """_now_iso returns a string."""
        result = _now_iso()
        assert isinstance(result, str)

    def test_now_iso_is_iso_format(self) -> None:
        """_now_iso returns ISO 8601 format."""
        result = _now_iso()
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(result)
        assert parsed is not None

    def test_generate_session_id_format(self) -> None:
        """Session ID has expected format."""
        result = _generate_session_id("Test Session")
        # Format: {sanitized}_{YYYYMMDD}_{HHMMSS}
        pattern = r"^[a-z0-9_]+_\d{8}_\d{6}$"
        assert re.match(pattern, result)

    def test_generate_session_id_sanitizes_spaces(self) -> None:
        """Session ID replaces spaces with underscores."""
        result = _generate_session_id("hello world")
        assert "hello_world" in result
        assert " " not in result

    def test_generate_session_id_sanitizes_hyphens(self) -> None:
        """Session ID replaces hyphens with underscores."""
        result = _generate_session_id("hello-world")
        assert "hello_world" in result
        assert "-" not in result

    def test_generate_session_id_lowercases(self) -> None:
        """Session ID is lowercase."""
        result = _generate_session_id("HELLO World")
        assert "hello_world" in result
        assert not any(c.isupper() for c in result)

    def test_generate_session_id_truncates_long_names(self) -> None:
        """Session ID truncates names longer than 30 chars."""
        long_name = "a" * 50
        result = _generate_session_id(long_name)
        # Should have 30 chars + _ + date + _ + time
        parts = result.split("_")
        assert len(parts[0]) <= 30


class TestSession:
    """Tests for Session dataclass."""

    def test_create_sets_id(self) -> None:
        """create() generates a session ID."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.id is not None
        assert len(session.id) > 0

    def test_create_sets_name(self) -> None:
        """create() sets the session name."""
        session = Session.create(
            "Test Session",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.name == "Test Session"

    def test_create_sets_task_type(self) -> None:
        """create() sets the task type."""
        session = Session.create(
            "Test",
            "debugging",
            model_name="gpt-4o",
            human_time_estimate_minutes=60.0,
            estimate_source="issue_tracker",
        )
        assert session.task_type == "debugging"

    def test_create_sets_model_name(self) -> None:
        """create() sets the model name."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.model_name == "claude-opus-4-20250514"

    def test_create_sets_human_time_estimate(self) -> None:
        """create() sets the human time estimate."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=45.5,
            estimate_source="manual",
        )
        assert session.human_time_estimate_minutes == 45.5

    def test_create_sets_estimate_source(self) -> None:
        """create() sets the estimate source."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="issue_tracker",
        )
        assert session.estimate_source == "issue_tracker"

    def test_create_sets_context(self) -> None:
        """create() sets the context."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
            context="Some context",
        )
        assert session.context == "Some context"

    def test_create_defaults_context_empty(self) -> None:
        """create() defaults context to empty string."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.context == ""

    def test_create_sets_start_time(self) -> None:
        """create() sets start_time to current time."""
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

    def test_create_defaults_status_active(self) -> None:
        """create() defaults status to active."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.status == "active"

    def test_create_defaults_end_time_none(self) -> None:
        """create() defaults end_time to None."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.end_time is None

    def test_create_defaults_outcome_none(self) -> None:
        """create() defaults outcome to None."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.outcome is None

    def test_create_defaults_notes_empty(self) -> None:
        """create() defaults notes to empty string."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.notes == ""

    def test_create_defaults_total_interactions_zero(self) -> None:
        """create() defaults total_interactions to 0."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.total_interactions == 0

    def test_create_defaults_avg_effectiveness_zero(self) -> None:
        """create() defaults avg_effectiveness to 0.0."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.avg_effectiveness == 0.0

    def test_create_defaults_code_metrics_empty(self) -> None:
        """create() defaults code_metrics to empty list."""
        session = Session.create(
            "Test",
            "code_generation",
            model_name="claude-opus-4-20250514",
            human_time_estimate_minutes=30.0,
            estimate_source="manual",
        )
        assert session.code_metrics == []

    def test_end_sets_status_completed(self) -> None:
        """end() sets status to completed."""
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
        """end() sets end_time."""
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
        """end() sets outcome."""
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
        """end() sets notes."""
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
        """to_dict() includes all session fields."""
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

    def test_to_dict_values_match(self) -> None:
        """to_dict() values match session attributes."""
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
        """from_dict() creates session from dict."""
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
        """from_dict() handles 'name' instead of 'session_name'."""
        data = {
            "id": "test_123",
            "name": "Legacy Name",  # Old field name
            "task_type": "debugging",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        session = Session.from_dict(data)
        assert session.name == "Legacy Name"

    def test_roundtrip_serialization(self) -> None:
        """to_dict() and from_dict() are inverse operations."""
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
        """create() sets session_id."""
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.session_id == "sess_123"

    def test_create_sets_timestamp(self) -> None:
        """create() sets timestamp."""
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.timestamp is not None
        datetime.fromisoformat(interaction.timestamp)

    def test_create_sets_prompt(self) -> None:
        """create() sets prompt."""
        interaction = Interaction.create("sess_123", "my prompt", "response", 4)
        assert interaction.prompt == "my prompt"

    def test_create_sets_response_summary(self) -> None:
        """create() sets response_summary."""
        interaction = Interaction.create("sess_123", "prompt", "my response", 4)
        assert interaction.response_summary == "my response"

    def test_create_sets_effectiveness_rating(self) -> None:
        """create() sets effectiveness_rating."""
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.effectiveness_rating == 4

    def test_create_clamps_rating_min(self) -> None:
        """create() clamps rating to minimum 1."""
        interaction = Interaction.create("sess_123", "prompt", "response", 0)
        assert interaction.effectiveness_rating == 1

    def test_create_clamps_rating_max(self) -> None:
        """create() clamps rating to maximum 5."""
        interaction = Interaction.create("sess_123", "prompt", "response", 10)
        assert interaction.effectiveness_rating == 5

    def test_create_defaults_iteration_count(self) -> None:
        """create() defaults iteration_count to 1."""
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.iteration_count == 1

    def test_create_sets_iteration_count(self) -> None:
        """create() sets iteration_count."""
        interaction = Interaction.create("sess_123", "prompt", "response", 4, 3)
        assert interaction.iteration_count == 3

    def test_create_clamps_iteration_count_min(self) -> None:
        """create() clamps iteration_count to minimum 1."""
        interaction = Interaction.create("sess_123", "prompt", "response", 4, 0)
        assert interaction.iteration_count == 1

    def test_create_defaults_tools_used_empty(self) -> None:
        """create() defaults tools_used to empty list."""
        interaction = Interaction.create("sess_123", "prompt", "response", 4)
        assert interaction.tools_used == []

    def test_create_sets_tools_used(self) -> None:
        """create() sets tools_used."""
        tools = ["read_file", "grep_search"]
        interaction = Interaction.create("sess_123", "prompt", "response", 4, 1, tools)
        assert interaction.tools_used == tools

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict() includes all fields."""
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
        """from_dict() creates interaction from dict."""
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
        """to_dict() and from_dict() are inverse operations."""
        original = Interaction.create("sess_123", "prompt", "response", 4, 2, ["tool1"])
        data = original.to_dict()
        restored = Interaction.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.prompt == original.prompt
        assert restored.effectiveness_rating == original.effectiveness_rating


class TestIssue:
    """Tests for Issue dataclass."""

    def test_create_sets_session_id(self) -> None:
        """create() sets session_id."""
        issue = Issue.create("sess_123", "incorrect_output", "desc", "high")
        assert issue.session_id == "sess_123"

    def test_create_sets_timestamp(self) -> None:
        """create() sets timestamp."""
        issue = Issue.create("sess_123", "incorrect_output", "desc", "high")
        assert issue.timestamp is not None
        datetime.fromisoformat(issue.timestamp)

    def test_create_sets_issue_type(self) -> None:
        """create() sets issue_type."""
        issue = Issue.create("sess_123", "hallucination", "desc", "high")
        assert issue.issue_type == "hallucination"

    def test_create_sets_description(self) -> None:
        """create() sets description."""
        issue = Issue.create("sess_123", "type", "my description", "high")
        assert issue.description == "my description"

    def test_create_sets_severity(self) -> None:
        """create() sets severity."""
        issue = Issue.create("sess_123", "type", "desc", "critical")
        assert issue.severity == "critical"

    def test_create_defaults_resolved_false(self) -> None:
        """create() defaults resolved to False."""
        issue = Issue.create("sess_123", "type", "desc", "high")
        assert issue.resolved is False

    def test_create_defaults_resolution_notes_empty(self) -> None:
        """create() defaults resolution_notes to empty string."""
        issue = Issue.create("sess_123", "type", "desc", "high")
        assert issue.resolution_notes == ""

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict() includes all fields."""
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
        """from_dict() creates issue from dict."""
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
        """to_dict() and from_dict() are inverse operations."""
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
        """Default values are set correctly."""
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
        """effort_score counts lines_added * 1.0."""
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="added",
            lines_added=10,
        )
        assert metrics.effort_score() == 10.0

    def test_effort_score_lines_modified(self) -> None:
        """effort_score counts lines_modified * 0.5."""
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="modified",
            lines_modified=10,
        )
        # 10 * 0.5 + complexity(1) * 0.1 = 5.0 + 0.1 = 5.1
        assert metrics.effort_score() == 5.1

    def test_effort_score_context_complexity_for_modified(self) -> None:
        """effort_score includes context complexity for modified functions."""
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="modified",
            complexity=5,
        )
        # 0 * 1.0 + 0 * 0.5 + 5 * 0.1 = 0.5
        assert metrics.effort_score() == 0.5

    def test_effort_score_no_context_for_added(self) -> None:
        """effort_score excludes context complexity for added functions."""
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="added",
            complexity=5,
        )
        # Context complexity is 0 for added
        assert metrics.effort_score() == 0.0

    def test_effort_score_combined(self) -> None:
        """effort_score combines all factors."""
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
        """to_dict() has expected nested structure."""
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
        """complexity_added equals complexity for 'added' modification type."""
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="added",
            complexity=5,
        )
        result = metrics.to_dict()
        assert result["ai_contribution"]["complexity_added"] == 5

    def test_to_dict_complexity_added_zero_for_modified(self) -> None:
        """complexity_added is 0 for non-added modification types."""
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="modified",
            complexity=5,
        )
        result = metrics.to_dict()
        assert result["ai_contribution"]["complexity_added"] == 0

    def test_to_dict_cognitive_load_zero_for_added(self) -> None:
        """cognitive_load is 0 for 'added' modification type."""
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="added",
            complexity=5,
        )
        result = metrics.to_dict()
        assert result["context"]["cognitive_load"] == 0

    def test_to_dict_cognitive_load_equals_complexity_for_modified(self) -> None:
        """cognitive_load equals complexity for non-added types."""
        metrics = FunctionMetrics(
            function_name="func",
            modification_type="modified",
            complexity=5,
        )
        result = metrics.to_dict()
        assert result["context"]["cognitive_load"] == 5
