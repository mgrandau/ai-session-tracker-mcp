"""
Storage management for AI Session Tracker.

PURPOSE: Centralized JSON file I/O with error handling and data integrity.
AI CONTEXT: All persistence operations go through this module.

STORAGE STRUCTURE:
    .ai_sessions/
    ├── sessions.json      # Dict: session_id -> session_data
    ├── interactions.json  # List: interaction records
    ├── issues.json        # List: issue records
    └── charts/            # Generated visualization files

ERROR HANDLING STRATEGY:
- File not found: Return empty structure (dict or list)
- JSON corruption: Log error, return empty structure
- Write failure: Log error, don't crash server
- Server continues in degraded mode if storage fails

USAGE:
    # Production
    storage = StorageManager()

    # Testing with MockFileSystem
    from .filesystem import MockFileSystem
    fs = MockFileSystem()
    storage = StorageManager(storage_dir="/test", filesystem=fs)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import Config
from .filesystem import RealFileSystem

__all__ = ["StorageManager"]

if TYPE_CHECKING:
    from .filesystem import FileSystem

logger = logging.getLogger(__name__)


class StorageManager:
    """
    JSON file I/O manager with comprehensive error handling.

    DESIGN PRINCIPLES:
    1. Fail-safe: Never crash server on I/O errors
    2. Predictable: Always return valid data structures
    3. Idempotent: Safe to initialize multiple times
    4. Logged: All errors recorded for debugging
    5. Testable: FileSystem can be injected for mocking

    INITIALIZATION:
    Creates directory structure and empty JSON files if missing.
    Uses exist_ok=True for safe concurrent initialization.

    THREAD SAFETY WARNING:
    NOT THREAD-SAFE. For multi-threaded use, wrap ALL calls with locks.
    Single-writer assumed (one MCP server process). Concurrent writes
    may cause data loss or corruption.
    """

    def __init__(
        self,
        storage_dir: str | None = None,
        filesystem: FileSystem | None = None,
    ) -> None:
        """
        Initialize storage manager with directory structure and files.

        Sets up the storage directory, creates any missing subdirectories,
        and initializes empty JSON files if they don't exist. Uses
        dependency injection for the filesystem to enable testing.

        Business context: Storage initialization ensures the server can
        start cleanly even on first run. The directory structure provides
        organized persistence for sessions, interactions, and issues.

        Args:
            storage_dir: Absolute path to storage directory. Defaults to
                Config.STORAGE_DIR ('.ai_sessions' in current directory).
            filesystem: FileSystem implementation for I/O operations.
                Defaults to RealFileSystem. Pass MockFileSystem for testing.

        Raises:
            OSError: Logged but not raised - allows degraded operation.

        Example:
            >>> # Default production usage
            >>> storage = StorageManager()
            >>> # Testing with mock filesystem
            >>> from .filesystem import MockFileSystem
            >>> storage = StorageManager(filesystem=MockFileSystem())
            >>> # Custom storage path
            >>> storage = StorageManager(storage_dir='/data/sessions')
        """
        # Resolve storage directory with full diagnostic logging
        env_val = os.environ.get(Config.ENV_OUTPUT_DIR)
        config_val = Config.get_output_dir()
        resolved = storage_dir or config_val or Config.STORAGE_DIR

        # Log the resolution chain so operators can diagnose path issues
        if storage_dir:
            logger.info("Storage directory: %s (explicit argument)", resolved)
        elif config_val:
            logger.info(
                "Storage directory: %s (from %s env var)",
                resolved,
                Config.ENV_OUTPUT_DIR,
            )
        else:
            logger.info(
                "Storage directory: %s (default — %s not set)",
                resolved,
                Config.ENV_OUTPUT_DIR,
            )

        if env_val is not None and not env_val:
            logger.warning(
                "%s is set but empty — falling back to default '%s'. "
                "Set a valid path or remove the variable.",
                Config.ENV_OUTPUT_DIR,
                Config.STORAGE_DIR,
            )

        self.storage_dir = resolved
        self._fs: FileSystem = filesystem or RealFileSystem()
        storage_path = Path(self.storage_dir)
        self.sessions_file = str(storage_path / Config.SESSIONS_FILE)
        self.interactions_file = str(storage_path / Config.INTERACTIONS_FILE)
        self.issues_file = str(storage_path / Config.ISSUES_FILE)
        self.charts_dir = str(storage_path / Config.CHARTS_DIR)

        self._initialize_storage()

    def _initialize_storage(self) -> None:
        """
        Create directory structure and initialize empty data files.

        Creates the main storage directory, charts subdirectory, and
        initializes empty JSON files (sessions.json, interactions.json,
        issues.json) if they don't already exist. Uses exist_ok=True
        for safe concurrent initialization.

        Business context: Idempotent initialization allows multiple
        StorageManager instances or server restarts without data loss.
        Missing files are created with valid empty structures.

        Error handling:
        Errors are logged but not raised, allowing the server to continue
        in degraded mode (memory-only) if storage is temporarily unavailable.

        Returns:
            None - Side effects only (directory/file creation).

        Raises:
            None - OSError is caught and logged.

        Example:
            >>> storage = StorageManager()
            >>> # _initialize_storage called automatically
            >>> # Directories and files now exist
        """
        try:
            self._fs.makedirs(self.storage_dir, exist_ok=True)
            self._fs.makedirs(self.charts_dir, exist_ok=True)

            # Initialize with empty structures if files don't exist
            if not self._fs.exists(self.sessions_file):
                self._write_json(self.sessions_file, {})
            if not self._fs.exists(self.interactions_file):
                self._write_json(self.interactions_file, [])
            if not self._fs.exists(self.issues_file):
                self._write_json(self.issues_file, [])

            logger.info(f"Storage initialized: {self.storage_dir}")
        except OSError as e:
            logger.error(f"Failed to initialize storage: {e}")

    def _filter_by_session(
        self, items: list[dict[str, Any]], session_id: str
    ) -> list[dict[str, Any]]:
        """
        Filter a list of items by session_id.

        Extracts records belonging to a specific session from a list of
        items (typically interactions or issues).

        Business context: Many queries need session-scoped data. This
        helper enables efficient filtering when loading interactions or
        issues for a specific session context.

        Args:
            items: List of dicts, each containing a 'session_id' key.
            session_id: The session identifier to filter by.

        Returns:
            list[dict[str, Any]]: Filtered list containing only items
                where item['session_id'] matches the provided session_id.
                Returns empty list if no matches.

        Example:
            >>> items = [{"session_id": "a", "data": 1}, {"session_id": "b", "data": 2}]
            >>> storage._filter_by_session(items, "a")
            [{'session_id': 'a', 'data': 1}]
        """
        return [item for item in items if item.get("session_id") == session_id]

    def _read_json(self, file_path: str, default: Any) -> Any:
        """
        Read and parse a JSON file with comprehensive error handling.

        Attempts to read the specified file and parse its contents as JSON.
        Returns the provided default value on any error to ensure callers
        always receive a valid data structure.

        Business context: This is the core file read operation. Graceful
        error handling ensures the MCP server continues operating even
        when storage files are missing or corrupted.

        Args:
            file_path: Absolute path to the JSON file to read.
            default: Value to return if file doesn't exist, is empty,
                or contains invalid JSON. Typically {} for dicts or [] for lists.

        Returns:
            Parsed JSON data (dict, list, or other JSON-compatible type)
            on success. Returns the default value if:
            - File doesn't exist (FileNotFoundError)
            - File contains invalid JSON (JSONDecodeError)
            - Any other I/O error occurs (OSError)

        Raises:
            None - All exceptions are caught, logged, and result in default return.

        Example:
            >>> storage = StorageManager()
            >>> data = storage._read_json('/path/to/sessions.json', {})
            >>> isinstance(data, dict)
            True
        """
        try:
            content = self._fs.read_text(file_path)
            return json.loads(content)
        except FileNotFoundError:
            return default
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            return default
        except OSError as e:
            logger.error(f"Error reading {file_path}: {e}")
            return default

    def _write_json(self, file_path: str, data: Any) -> bool:
        """
        Serialize data and write to a JSON file with error handling.

        Converts the provided data to JSON format with pretty-printing
        (2-space indent) and writes to the specified file path. Uses
        default=str serializer to handle datetime and other non-JSON types.

        Business context: This is the core persistence operation. Write
        failures are logged but don't crash the server, allowing degraded
        operation when storage is temporarily unavailable.

        Args:
            file_path: Absolute path to the JSON file to write.
            data: Python data structure to serialize. Must be JSON-compatible
                (dict, list, str, int, float, bool, None). Non-serializable
                types are converted using str().

        Returns:
            True if data was successfully serialized and written.
            False if any error occurred (permissions, disk full, etc).

        Raises:
            None - Errors are caught and logged; returns False on failure.

        Example:
            >>> storage = StorageManager()
            >>> storage._write_json('/path/to/data.json', {'key': 'value'})
            True
        """
        try:
            content = json.dumps(data, indent=2, default=str)
            self._fs.write_text(file_path, content)
            return True
        except (OSError, PermissionError) as e:
            logger.error(f"Error writing {file_path}: {e}")
            return False

    # =========================================================================
    # SESSION OPERATIONS
    # =========================================================================

    def load_sessions(self) -> dict[str, Any]:
        """
        Load all sessions from persistent JSON storage.

        Reads and parses the sessions.json file, returning the complete
        sessions registry. Handles missing files and JSON errors gracefully
        by returning an empty dictionary to allow the server to continue.

        Business context: Sessions are the core data structure for tracking.
        This method is called frequently by handlers and statistics engine
        to access session data for display, updates, and calculations.

        Returns:
            Dict mapping session_id (str) to session_data (dict). Each session
            contains keys like 'session_name', 'task_type', 'status', 'start_time',
            'end_time', 'total_interactions', etc. Returns empty dict {} if
            file doesn't exist or contains invalid JSON.

        Raises:
            None - All exceptions are caught and logged; returns {} on error.

        Example:
            >>> storage = StorageManager()
            >>> sessions = storage.load_sessions()
            >>> for session_id, data in sessions.items():
            ...     print(f"{session_id}: {data['status']}")
            feature_auth_20251201_100000: completed
        """
        result: dict[str, Any] = self._read_json(self.sessions_file, {})
        return result

    def save_sessions(self, sessions: dict[str, Any]) -> bool:
        """
        Persist all sessions to JSON storage.

        Serializes the complete sessions dictionary to JSON and writes it
        to disk atomically. Uses 2-space indentation for human readability
        and UTF-8 encoding for international character support.

        Business context: Session persistence ensures data survives server
        restarts. All session mutations must call this method to be durable.

        Args:
            sessions: Complete dict of session_id -> session_data to persist.
                This replaces the entire sessions file - caller must include
                all sessions, not just modified ones.

        Returns:
            True if successfully written to disk.
            False if write failed (permissions, disk full, etc). Check logs.

        Raises:
            TypeError: If sessions is not a dict (caught internally, returns False).

        Example:
            >>> storage = StorageManager()
            >>> sessions = storage.load_sessions()
            >>> sessions['new_session'] = {'status': 'active', ...}
            >>> storage.save_sessions(sessions)
            True
        """
        return self._write_json(self.sessions_file, sessions)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Retrieve a single session by its unique identifier.

        Loads the sessions file and returns the matching session data.
        This is a convenience method that avoids loading all sessions
        when only one is needed.

        Business context: Individual session lookup is the most common
        operation during active tracking - every interaction, issue, and
        code metrics update requires validating the session exists.

        Args:
            session_id: The unique session identifier returned by
                start_ai_session, e.g., 'feature_auth_20251201_100000'.

        Returns:
            Session data dict if found, containing all session fields.
            None if no session exists with the given ID.

        Raises:
            TypeError: If session_id is not a string.

        Example:
            >>> storage = StorageManager()
            >>> session = storage.get_session('feature_auth_20251201_100000')
            >>> if session:
            ...     print(f"Status: {session['status']}")
            ... else:
            ...     print("Session not found")
            Status: active
        """
        sessions = self.load_sessions()
        return sessions.get(session_id)

    def update_session(self, session_id: str, data: dict[str, Any]) -> bool:
        """
        Update a single session's data in persistent storage.

        Loads all sessions, updates the specified session, and persists the
        complete sessions dictionary back to disk. This is an atomic operation
        from the caller's perspective - either the entire update succeeds or
        the original data remains unchanged.

        Business context: Sessions are updated frequently during active work
        (incrementing interaction counts, updating effectiveness averages,
        adding code metrics). Reliable updates are critical for accurate tracking.

        Args:
            session_id: Unique identifier for the session to update.
                Must be an existing key in the sessions dictionary.
            data: Complete session data dict to store. Replaces any existing
                data for this session_id entirely (not a merge).

        Returns:
            True if the session was successfully updated and persisted.
            False if the write operation failed (see logs for details).

        Raises:
            TypeError: If session_id is not a string or data is not a dict.

        Example:
            >>> storage = StorageManager()
            >>> session_data = storage.get_session('session_123')
            >>> session_data['total_interactions'] += 1
            >>> storage.update_session('session_123', session_data)
            True
        """
        sessions = self.load_sessions()
        sessions[session_id] = data
        return self.save_sessions(sessions)

    # =========================================================================
    # INTERACTION OPERATIONS
    # =========================================================================

    def load_interactions(self) -> list[dict[str, Any]]:
        """
        Load all AI interactions from persistent JSON storage.

        Reads and parses the interactions.json file, returning all recorded
        prompt/response exchanges across all sessions. Handles missing files
        and JSON errors gracefully by returning an empty list.

        Business context: Interactions are the granular record of AI usage.
        They contain effectiveness ratings essential for calculating average
        performance and identifying patterns in AI assistance quality.

        Returns:
            List of interaction dicts, each containing 'session_id', 'timestamp',
            'prompt', 'response_summary', 'effectiveness_rating', 'iteration_count',
            and 'tools_used'. Returns empty list [] if file doesn't exist or
            contains invalid JSON.

        Raises:
            None - All exceptions are caught and logged; returns [] on error.

        Example:
            >>> storage = StorageManager()
            >>> interactions = storage.load_interactions()
            >>> high_rated = [i for i in interactions if i['effectiveness_rating'] >= 4]
            >>> print(f"{len(high_rated)} highly effective interactions")
        """
        result: list[dict[str, Any]] = self._read_json(self.interactions_file, [])
        return result

    def save_interactions(self, interactions: list[dict[str, Any]]) -> bool:
        """
        Persist all interactions to JSON storage.

        Serializes the complete interactions list to JSON and writes it
        to disk. Uses 2-space indentation for human readability and
        UTF-8 encoding for international character support.

        Business context: Interaction history is valuable for retrospective
        analysis, identifying prompting patterns that work well, and
        training future AI usage strategies.

        Args:
            interactions: Complete list of interaction dicts to persist.
                This replaces the entire interactions file - caller must
                include all interactions, not just new ones.

        Returns:
            True if successfully written to disk.
            False if write failed (permissions, disk full, etc). Check logs.

        Raises:
            TypeError: If interactions is not a list (caught internally).

        Example:
            >>> storage = StorageManager()
            >>> interactions = storage.load_interactions()
            >>> interactions.append({'session_id': 's1', 'effectiveness_rating': 5, ...})
            >>> storage.save_interactions(interactions)
            True
        """
        return self._write_json(self.interactions_file, interactions)

    def add_interaction(self, interaction: dict[str, Any]) -> bool:
        """
        Append a single interaction to persistent storage.

        Convenience method that loads existing interactions, appends the
        new one, and persists the updated list. More efficient than manually
        loading, modifying, and saving for single additions.

        Business context: Each log_ai_interaction tool call adds one
        interaction record. This is the primary write path for tracking
        AI prompt/response effectiveness during active work.

        Args:
            interaction: Interaction dict containing required keys:
                - 'session_id': Parent session identifier
                - 'timestamp': ISO 8601 datetime string
                - 'prompt': The prompt text sent to AI
                - 'response_summary': Brief summary of AI response
                - 'effectiveness_rating': Integer 1-5
                Optional: 'iteration_count', 'tools_used'

        Returns:
            True if interaction was successfully appended and persisted.
            False if the save operation failed.

        Raises:
            TypeError: If interaction is not a dict.

        Example:
            >>> storage = StorageManager()
            >>> storage.add_interaction({
            ...     'session_id': 'feature_auth_20251201_100000',
            ...     'timestamp': '2025-12-01T10:30:00+00:00',
            ...     'prompt': 'Add login validation',
            ...     'response_summary': 'Created validate_login() function',
            ...     'effectiveness_rating': 4
            ... })
            True
        """
        interactions = self.load_interactions()
        interactions.append(interaction)
        return self.save_interactions(interactions)

    def get_session_interactions(self, session_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all interactions belonging to a specific session.

        Filters the complete interactions list to return only those
        associated with the given session. Used to calculate per-session
        statistics and display session detail views.

        Business context: Per-session interaction counts and effectiveness
        averages are key metrics displayed in session summaries and used
        for session-level ROI calculations.

        Args:
            session_id: The session identifier to filter by.

        Returns:
            List of interaction dicts where 'session_id' matches the
            provided value. Empty list if no matching interactions found
            or if the session doesn't exist.

        Raises:
            TypeError: If session_id is not a string.

        Example:
            >>> storage = StorageManager()
            >>> interactions = storage.get_session_interactions('feature_auth_20251201_100000')
            >>> print(f"Session has {len(interactions)} interactions")
            >>> avg = sum(i['effectiveness_rating'] for i in interactions) / len(interactions)
        """
        return self._filter_by_session(self.load_interactions(), session_id)

    # =========================================================================
    # ISSUE OPERATIONS
    # =========================================================================

    def load_issues(self) -> list[dict[str, Any]]:
        """
        Load all flagged issues from persistent JSON storage.

        Reads and parses the issues.json file, returning all recorded
        AI problems across all sessions. Handles missing files and JSON
        errors gracefully by returning an empty list.

        Business context: Issues track when AI produces incorrect or
        problematic output. Analyzing issue patterns helps improve
        prompting strategies and identify model limitations.

        Returns:
            List of issue dicts, each containing 'session_id', 'timestamp',
            'issue_type', 'description', 'severity', 'resolved', and
            'resolution_notes'. Returns empty list [] if file doesn't
            exist or contains invalid JSON.

        Raises:
            None - All exceptions are caught and logged; returns [] on error.

        Example:
            >>> storage = StorageManager()
            >>> issues = storage.load_issues()
            >>> critical = [i for i in issues if i['severity'] == 'critical']
            >>> print(f"{len(critical)} critical issues found")
        """
        result: list[dict[str, Any]] = self._read_json(self.issues_file, [])
        return result

    def save_issues(self, issues: list[dict[str, Any]]) -> bool:
        """
        Persist all issues to JSON storage.

        Serializes the complete issues list to JSON and writes it to disk.
        Uses 2-space indentation for human readability and UTF-8 encoding.

        Business context: Issue history enables trend analysis over time.
        Teams can identify recurring problem categories and measure whether
        mitigation strategies (better prompts, different models) are working.

        Args:
            issues: Complete list of issue dicts to persist. This replaces
                the entire issues file - caller must include all issues.

        Returns:
            True if successfully written to disk.
            False if write failed (permissions, disk full, etc). Check logs.

        Raises:
            TypeError: If issues is not a list (caught internally).

        Example:
            >>> storage = StorageManager()
            >>> issues = storage.load_issues()
            >>> issues[0]['resolved'] = True
            >>> issues[0]['resolution_notes'] = 'Fixed with better prompt'
            >>> storage.save_issues(issues)
            True
        """
        return self._write_json(self.issues_file, issues)

    def add_issue(self, issue: dict[str, Any]) -> bool:
        """
        Append a single issue to persistent storage.

        Convenience method that loads existing issues, appends the new one,
        and persists the updated list. Provides atomic append semantics.

        Business context: Each flag_ai_issue tool call adds one issue record.
        Flagging issues during work creates a real-time log of AI problems
        that can be analyzed for patterns and improvement opportunities.

        Args:
            issue: Issue dict containing required keys:
                - 'session_id': Parent session identifier
                - 'timestamp': ISO 8601 datetime string
                - 'issue_type': Category (e.g., 'hallucination', 'incorrect_output')
                - 'description': Detailed description of the problem
                - 'severity': 'low', 'medium', 'high', or 'critical'
                Optional: 'resolved', 'resolution_notes'

        Returns:
            True if issue was successfully appended and persisted.
            False if the save operation failed.

        Raises:
            TypeError: If issue is not a dict.

        Example:
            >>> storage = StorageManager()
            >>> storage.add_issue({
            ...     'session_id': 'feature_auth_20251201_100000',
            ...     'timestamp': '2025-12-01T10:35:00+00:00',
            ...     'issue_type': 'hallucination',
            ...     'description': 'AI referenced non-existent library function',
            ...     'severity': 'medium'
            ... })
            True
        """
        issues = self.load_issues()
        issues.append(issue)
        return self.save_issues(issues)

    def get_session_issues(self, session_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all issues belonging to a specific session.

        Filters the complete issues list to return only those associated
        with the given session. Used to display session-level problem
        summaries and calculate per-session issue counts.

        Business context: Per-session issue counts help identify
        problematic sessions that may need review. High issue counts
        in specific task types may indicate need for different approaches.

        Args:
            session_id: The session identifier to filter by.

        Returns:
            List of issue dicts where 'session_id' matches the provided
            value. Empty list if no matching issues found.

        Raises:
            TypeError: If session_id is not a string.

        Example:
            >>> storage = StorageManager()
            >>> issues = storage.get_session_issues('feature_auth_20251201_100000')
            >>> print(f"Session has {len(issues)} flagged issues")
            >>> for issue in issues:
            ...     print(f"  [{issue['severity']}] {issue['issue_type']}")
        """
        return self._filter_by_session(self.load_issues(), session_id)

    # =========================================================================
    # MAINTENANCE OPERATIONS
    # =========================================================================

    def clear_all(self) -> bool:
        """
        Reset all data files to empty state.

        Clears sessions, interactions, and issues by writing empty
        structures to their respective JSON files. This is a destructive
        operation that cannot be undone.

        Business context: Used primarily in testing and after data has
        been backed up to external storage (S3). May also be used when
        starting fresh tracking for a new project phase.

        Warning: Destroys all tracked data permanently. Ensure data is
        backed up before calling in production contexts.

        Returns:
            True if all three files (sessions, interactions, issues)
            were successfully cleared. False if any write operation failed.

        Raises:
            None - Errors are logged but not raised.

        Example:
            >>> storage = StorageManager()
            >>> # Backup data first!
            >>> storage.clear_all()
            True
            >>> len(storage.load_sessions())
            0
        """
        success = self._write_json(self.sessions_file, {})
        success = success and self._write_json(self.interactions_file, [])
        success = success and self._write_json(self.issues_file, [])
        if success:  # pragma: no cover - logging only
            logger.info("All data files cleared")
        return success
