"""
Data models for AI Session Tracker.

PURPOSE: Type-safe dataclasses representing core domain entities.
AI CONTEXT: These models define the data schema for sessions, interactions, and issues.

MODEL HIERARCHY:
- Session: Top-level workflow container (has many Interactions, Issues)
- Interaction: Individual prompt/response exchange within a Session
- Issue: Flagged problem within a Session
- CodeMetrics: Code quality data for functions modified in a Session

SERIALIZATION:
All models have to_dict() for JSON persistence and from_dict() for loading.
Timestamps use ISO 8601 format with UTC timezone.

USAGE:
    session = Session.create("Feature work", "code_generation", "Adding auth")
    interaction = Interaction.create(session.id, "Add login", "Created login()", 4)
    issue = Issue.create(session.id, "incorrect_output", "Wrong regex", "medium")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now_iso() -> str:
    """
    Get current UTC time as ISO 8601 formatted string.

    Returns the current timestamp in UTC timezone using ISO 8601 format
    with timezone offset. Used for all session, interaction, and issue
    timestamps to ensure consistent, timezone-aware dates.

    Business context: Consistent timestamp format enables reliable
    chronological sorting and duration calculations across sessions.

    Args:
        None: Pure function with no parameters.

    Returns:
        ISO 8601 formatted datetime string, e.g., '2025-12-01T10:30:00+00:00'.

    Raises:
        None: datetime.now() never raises.

    Example:
        >>> ts = _now_iso()
        >>> '+00:00' in ts or 'Z' in ts
        True
    """
    return datetime.now(UTC).isoformat()


def _generate_session_id(name: str) -> str:
    """
    Generate a unique session ID from name and current timestamp.

    Creates a human-readable, unique identifier by combining a sanitized
    version of the session name with a precise timestamp. The format
    ensures uniqueness while remaining identifiable.

    Business context: Session IDs need to be unique for data integrity
    while remaining somewhat meaningful for debugging. The name prefix
    helps identify sessions in logs and storage files.

    Args:
        name: Session name to incorporate (e.g., 'Add user authentication').
            Will be lowercase, space/dash converted to underscore, truncated
            to 30 characters.

    Returns:
        Session ID in format: {sanitized_name}_{YYYYMMDD}_{HHMMSS}.
        Example: 'add_user_authentication_20251201_143022'

    Example:
        >>> _generate_session_id('Add Login Feature')
        'add_login_feature_20251201_143022'
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    sanitized = name.lower().replace(" ", "_").replace("-", "_")[:30]
    return f"{sanitized}_{timestamp}"


@dataclass
class Session:
    """
    AI workflow session container.

    LIFECYCLE:
    1. Created via start_ai_session tool
    2. Accumulates interactions and issues during work
    3. Finalized via end_ai_session tool with outcome

    METRICS TRACKED:
    - Duration (start_time to end_time)
    - Interaction count and effectiveness average
    - Code metrics (complexity, documentation quality)
    - Human time estimate for ROI comparison

    STATUS VALUES:
    - "active": Session in progress
    - "completed": Session ended normally
    - "abandoned": Session ended without explicit close

    ESTIMATE SOURCES:
    - "manual": User provided estimate
    - "issue_tracker": From linked issue/ticket estimate
    - "historical": Based on similar past tasks
    """

    id: str
    name: str
    task_type: str
    context: str
    start_time: str
    model_name: str
    human_time_estimate_minutes: float
    estimate_source: str
    status: str = "active"
    end_time: str | None = None
    outcome: str | None = None
    notes: str = ""
    total_interactions: int = 0
    avg_effectiveness: float = 0.0
    code_metrics: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        task_type: str,
        model_name: str,
        human_time_estimate_minutes: float,
        estimate_source: str,
        context: str = "",
    ) -> Session:
        """
        Factory method to create new session with generated ID and timestamp.

        Business context: Factory pattern ensures consistent ID generation
        and timestamp assignment for all new sessions.

        Args:
            name: Descriptive session name (e.g., "Add user authentication")
            task_type: Category from Config.TASK_TYPES
            model_name: AI model being used (e.g., "claude-opus-4-20250514", "gpt-4o")
            human_time_estimate_minutes: Estimated time for human to complete task
            estimate_source: Where estimate came from ("manual", "issue_tracker", "historical")
            context: Optional additional context about the work

        Returns:
            New Session instance with unique ID and start_time set.

        Raises:
            None: Pure construction, never raises.

        Example:
            >>> session = Session.create('Add login', 'code_generation', 'opus', 60, 'manual')
            >>> session.status
            'active'
        """
        return cls(
            id=_generate_session_id(name),
            name=name,
            task_type=task_type,
            context=context,
            start_time=_now_iso(),
            model_name=model_name,
            human_time_estimate_minutes=human_time_estimate_minutes,
            estimate_source=estimate_source,
        )

    def end(self, outcome: str, notes: str = "") -> None:
        """
        Mark this session as completed with outcome and timestamp.

        Updates the session status to 'completed', records the end timestamp,
        and stores the outcome and any notes. This method should be called
        when the tracked task is finished.

        Business context: Session completion triggers final metric calculation.
        The end_time enables duration calculation for ROI comparison against
        the original human time estimate.

        Args:
            outcome: Result of the session - 'success' (task completed as
                intended), 'partial' (some goals achieved), or 'failed'
                (task abandoned or unsuccessful).
            notes: Optional summary notes describing what was accomplished
                or any relevant observations.

        Returns:
            None. Modifies instance state in place.

        Example:
            >>> session = Session.create('Add login', 'code_generation', 'opus', 60, 'manual')
            >>> session.end('success', 'Implemented OAuth2 login flow')
            >>> session.status
            'completed'
        """
        self.status = "completed"
        self.end_time = _now_iso()
        self.outcome = outcome
        self.notes = notes

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize session to dictionary for JSON storage.

        Converts all session fields to a JSON-compatible dictionary format.
        The dictionary can be directly serialized with json.dumps() for
        persistent storage.

        Business context: Sessions are stored as JSON files for simplicity
        and human readability. The dict format uses consistent key names
        that match the storage schema.

        Args:
            None: Instance method, accesses self attributes.

        Returns:
            Dict containing all session fields with string keys. Includes
            id, session_name, task_type, context, timestamps, model info,
            estimates, status, outcome, notes, and metrics.

        Raises:
            None: Dict construction never raises.

        Example:
            >>> session = Session.create('Add login', 'code_generation', 'opus', 60, 'manual')
            >>> data = session.to_dict()
            >>> data['session_name']
            'Add login'
        """
        return {
            "id": self.id,
            "session_name": self.name,
            "task_type": self.task_type,
            "context": self.context,
            "start_time": self.start_time,
            "model_name": self.model_name,
            "human_time_estimate_minutes": self.human_time_estimate_minutes,
            "estimate_source": self.estimate_source,
            "status": self.status,
            "end_time": self.end_time,
            "outcome": self.outcome,
            "notes": self.notes,
            "total_interactions": self.total_interactions,
            "avg_effectiveness": self.avg_effectiveness,
            "code_metrics": self.code_metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """
        Deserialize session from dictionary.

        Reconstructs a Session instance from a stored dictionary,
        handling both current and legacy key names for backwards
        compatibility with older storage formats.

        Business context: Loading sessions from storage enables
        continuation of tracking across server restarts and provides
        access to historical data for analytics.

        Args:
            data: Dict containing session fields as stored by to_dict().
                Supports both 'session_name' and legacy 'name' keys.

        Returns:
            Session instance with all fields populated from the dict.

        Raises:
            KeyError: If required field 'id' is missing.

        Example:
            >>> data = {'id': 'test_123', 'session_name': 'Test', ...}
            >>> session = Session.from_dict(data)
            >>> session.name
            'Test'
        """
        return cls(
            id=data["id"],
            name=data.get("session_name", data.get("name", "")),
            task_type=data.get("task_type", ""),
            context=data.get("context", ""),
            start_time=data.get("start_time", ""),
            model_name=data.get("model_name", "unknown"),
            human_time_estimate_minutes=data.get("human_time_estimate_minutes", 0.0),
            estimate_source=data.get("estimate_source", "unknown"),
            status=data.get("status", "active"),
            end_time=data.get("end_time"),
            outcome=data.get("outcome"),
            notes=data.get("notes", ""),
            total_interactions=data.get("total_interactions", 0),
            avg_effectiveness=data.get("avg_effectiveness", 0.0),
            code_metrics=data.get("code_metrics", []),
        )


@dataclass
class Interaction:
    """
    Single AI prompt/response exchange.

    TRACKED DATA:
    - Prompt text and response summary
    - Effectiveness rating (1-5 scale)
    - Iteration count (how many attempts to achieve goal)
    - Tools used during this interaction

    EFFECTIVENESS SCALE:
    1: Failed completely, had to redo manually
    2: Mostly wrong, significant corrections needed
    3: Partially correct, some adjustments required
    4: Good result, minor tweaks only
    5: Perfect, used as-is
    """

    session_id: str
    timestamp: str
    prompt: str
    response_summary: str
    effectiveness_rating: int
    iteration_count: int = 1
    tools_used: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        session_id: str,
        prompt: str,
        response_summary: str,
        effectiveness_rating: int,
        iteration_count: int = 1,
        tools_used: list[str] | None = None,
    ) -> Interaction:
        """
        Factory method to create interaction with current timestamp.

        Clamps effectiveness_rating to 1-5 range and iteration_count to
        minimum of 1 for data integrity.

        Business context: Each interaction represents a prompt/response
        exchange. Tracking these enables effectiveness analysis over time.

        Args:
            session_id: Parent session identifier
            prompt: The prompt sent to AI
            response_summary: Brief description of AI response
            effectiveness_rating: 1-5 scale rating
            iteration_count: Number of attempts (default 1)
            tools_used: List of MCP tools used

        Returns:
            New Interaction instance.

        Raises:
            None: Pure construction with clamping, never raises.

        Example:
            >>> interaction = Interaction.create('s1', 'Add tests', 'Added unit tests', 5)
            >>> interaction.effectiveness_rating
            5
        """
        return cls(
            session_id=session_id,
            timestamp=_now_iso(),
            prompt=prompt,
            response_summary=response_summary,
            effectiveness_rating=max(1, min(5, effectiveness_rating)),
            iteration_count=max(1, iteration_count),
            tools_used=tools_used or [],
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize interaction to dictionary for JSON storage.

        Converts all interaction fields to a JSON-compatible dictionary.
        Used for persisting interactions to the JSON file storage.

        Business context: Interactions are stored as JSON for persistence
        and analysis. This format enables easy loading and processing.

        Args:
            None: Instance method, accesses self attributes.

        Returns:
            Dict with session_id, timestamp, prompt, response_summary,
            effectiveness_rating, iteration_count, and tools_used.

        Raises:
            None: Dict construction never raises.

        Example:
            >>> interaction = Interaction.create('s1', 'prompt', 'summary', 5)
            >>> data = interaction.to_dict()
            >>> data['effectiveness_rating']
            5
        """
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "prompt": self.prompt,
            "response_summary": self.response_summary,
            "effectiveness_rating": self.effectiveness_rating,
            "iteration_count": self.iteration_count,
            "tools_used": self.tools_used,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Interaction:
        """
        Deserialize interaction from dictionary.

        Reconstructs an Interaction instance from stored data. Handles
        optional fields with sensible defaults for backwards compatibility.

        Business context: Loading interactions from storage enables
        calculation of effectiveness metrics across sessions.

        Args:
            data: Dict containing interaction fields as stored by to_dict().

        Returns:
            Interaction instance with all fields populated.

        Raises:
            KeyError: If required fields are missing.

        Example:
            >>> data = {'session_id': 's1', 'timestamp': '...', 'prompt': '...', ...}
            >>> interaction = Interaction.from_dict(data)
        """
        return cls(
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            prompt=data["prompt"],
            response_summary=data["response_summary"],
            effectiveness_rating=data["effectiveness_rating"],
            iteration_count=data.get("iteration_count", 1),
            tools_used=data.get("tools_used", []),
        )


@dataclass
class Issue:
    """
    Flagged problem during AI session.

    ISSUE TYPES (common categories):
    - incorrect_output: AI produced wrong code/content
    - poor_prompt: Prompt was ambiguous or misleading
    - tool_failure: MCP tool didn't work as expected
    - context_missing: AI lacked necessary context
    - hallucination: AI invented non-existent APIs/features

    SEVERITY LEVELS:
    - low: Minor inconvenience, easy workaround
    - medium: Required significant correction
    - high: Caused substantial rework
    - critical: Blocked progress or caused bugs
    """

    session_id: str
    timestamp: str
    issue_type: str
    description: str
    severity: str
    resolved: bool = False
    resolution_notes: str = ""

    @classmethod
    def create(
        cls,
        session_id: str,
        issue_type: str,
        description: str,
        severity: str,
    ) -> Issue:
        """
        Factory method to create issue with current timestamp.

        Creates a new unresolved issue with automatic timestamp. Used
        to flag problems encountered during AI-assisted development.

        Business context: Tracking issues enables pattern analysis to
        improve prompting strategies and identify model limitations.

        Args:
            session_id: Parent session identifier
            issue_type: Category of issue
            description: Detailed description of what went wrong
            severity: One of "low", "medium", "high", "critical"

        Returns:
            New Issue instance with resolved=False.

        Raises:
            None: Pure construction, never raises.

        Example:
            >>> issue = Issue.create('s1', 'hallucination', 'Made up API', 'high')
            >>> issue.resolved
            False
        """
        return cls(
            session_id=session_id,
            timestamp=_now_iso(),
            issue_type=issue_type,
            description=description,
            severity=severity,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize issue to dictionary for JSON storage.

        Converts all issue fields to a JSON-compatible dictionary.
        Used for persisting flagged issues to the JSON file storage.

        Business context: Issues are stored as JSON for persistence
        and pattern analysis across sessions.

        Args:
            None: Instance method, accesses self attributes.

        Returns:
            Dict with session_id, timestamp, issue_type, description,
            severity, resolved flag, and resolution_notes.

        Raises:
            None: Dict construction never raises.

        Example:
            >>> issue = Issue.create('s1', 'hallucination', 'desc', 'high')
            >>> data = issue.to_dict()
            >>> data['severity']
            'high'
        """
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "issue_type": self.issue_type,
            "description": self.description,
            "severity": self.severity,
            "resolved": self.resolved,
            "resolution_notes": self.resolution_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Issue:
        """
        Deserialize issue from dictionary.

        Reconstructs an Issue instance from stored data. Handles optional
        fields (resolved, resolution_notes) with defaults.

        Business context: Loading issues from storage enables analysis
        of AI problem patterns over time.

        Args:
            data: Dict containing issue fields as stored by to_dict().

        Returns:
            Issue instance with all fields populated.

        Raises:
            KeyError: If required fields are missing.

        Example:
            >>> data = {'session_id': 's1', 'issue_type': 'hallucination', ...}
            >>> issue = Issue.from_dict(data)
        """
        return cls(
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            issue_type=data["issue_type"],
            description=data["description"],
            severity=data["severity"],
            resolved=data.get("resolved", False),
            resolution_notes=data.get("resolution_notes", ""),
        )


@dataclass
class FunctionMetrics:
    """
    Code metrics for a single function modified during session.

    METRIC CATEGORIES:
    1. AI Contribution: What AI added (lines, complexity)
    2. Context: Existing code complexity AI had to understand
    3. Documentation: Docstring quality and completeness
    4. Value: Combined effort score for ROI calculation

    COMPLEXITY CALCULATION:
    Uses cyclomatic complexity via AST analysis:
    - Base: 1
    - +1 for each: if, while, for, except, with, assert
    - +1 for each boolean operator (and, or)

    DOCUMENTATION SCORING (0-100):
    - Has docstring: +30
    - Substantial content (>50 chars): +10
    - Args section: +20
    - Returns section: +20
    - Examples section: +10
    - Raises section: +5
    - Type hints: +5
    """

    function_name: str
    modification_type: str  # "added", "modified", "refactored", "deleted"
    lines_added: int = 0
    lines_modified: int = 0
    lines_deleted: int = 0
    complexity: int = 1
    documentation_score: int = 0
    has_docstring: bool = False
    has_type_hints: bool = False

    def effort_score(self) -> float:
        """
        Calculate weighted effort score for ROI tracking.

        Computes a composite score representing the AI contribution effort
        based on lines of code changed and existing code complexity. Used
        to quantify the volume of work AI performed.

        Business context: Effort scores provide a code-based metric for
        AI contribution, complementing time-based ROI calculations with
        tangible output measurement.

        Formula:
            lines_added * 1.0 + lines_modified * 0.5 + context_complexity * 0.1

        For new functions (modification_type='added'), context complexity is 0.
        For modified functions, existing complexity represents cognitive load.

        Args:
            None: Instance method, accesses self attributes.

        Returns:
            Float score where higher values indicate more AI effort.
            Typical range: 5-100 for individual functions.

        Raises:
            None: Arithmetic operations never raise.

        Example:
            >>> metrics = FunctionMetrics('my_func', 'added', lines_added=50, complexity=5)
            >>> metrics.effort_score()
            50.0
        """
        context_complexity = 0 if self.modification_type == "added" else self.complexity
        return self.lines_added * 1.0 + self.lines_modified * 0.5 + context_complexity * 0.1

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize function metrics to dictionary for JSON storage.

        Converts metrics into a structured nested dictionary with categories
        for AI contribution, context complexity, documentation quality,
        and computed value metrics.

        Business context: Code metrics are stored with sessions to enable
        detailed analysis of AI contribution patterns and code quality.

        Args:
            None: Instance method, accesses self attributes.

        Returns:
            Nested dict with function_name, modification_type, and sub-dicts
            for ai_contribution, context, documentation, and value_metrics.

        Raises:
            None: Dict construction never raises.

        Example:
            >>> metrics = FunctionMetrics('my_func', 'added', lines_added=10)
            >>> data = metrics.to_dict()
            >>> data['ai_contribution']['lines_added']
            10
        """
        return {
            "function_name": self.function_name,
            "modification_type": self.modification_type,
            "ai_contribution": {
                "lines_added": self.lines_added,
                "lines_modified": self.lines_modified,
                "lines_deleted": self.lines_deleted,
                "complexity_added": self.complexity if self.modification_type == "added" else 0,
            },
            "context": {
                "final_complexity": self.complexity,
                "cognitive_load": 0 if self.modification_type == "added" else self.complexity,
            },
            "documentation": {
                "has_docstring": self.has_docstring,
                "quality_score": self.documentation_score,
                "has_type_hints": self.has_type_hints,
            },
            "value_metrics": {
                "effort_score": round(self.effort_score(), 2),
            },
        }
