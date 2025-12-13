"""Tests for storage module."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add tests directory to path for conftest imports
sys.path.insert(0, str(Path(__file__).parent))

from ai_session_tracker_mcp.storage import StorageManager
from conftest import MockFileSystem


@pytest.fixture
def storage(mock_fs: MockFileSystem) -> StorageManager:
    """Create StorageManager with mock filesystem for isolated testing.

    Initializes a fully functional StorageManager backed by MockFileSystem,
    enabling complete storage operation testing without disk I/O.

    Business context:
    StorageManager is the persistence layer for session tracking. Tests
    must verify CRUD operations work correctly without affecting real data.

    Args:
        mock_fs: MockFileSystem fixture providing in-memory storage.

    Returns:
        StorageManager: Initialized manager with /test/storage base path,
        including auto-created directories and empty data files.

    Example:
        >>> manager = storage
        >>> manager.save_sessions({'s1': {'name': 'test'}})
        >>> manager.load_sessions()
        {'s1': {'name': 'test'}}
    """
    return StorageManager(storage_dir="/test/storage", filesystem=mock_fs)


class TestStorageManagerInit:
    """Test suite for StorageManager initialization behavior.

    Categories:
    1. Directory Creation - Storage and charts directories (2 tests)
    2. File Initialization - Sessions, interactions, issues files (3 tests)
    3. Data Preservation - Existing data not overwritten (1 test)

    Total: 6 tests verifying correct initialization semantics.
    """

    def test_creates_storage_directory(self, mock_fs: MockFileSystem) -> None:
        """Verifies StorageManager creates the base storage directory.

        Tests that initialization creates the specified storage directory
        if it doesn't exist, establishing the persistence root.

        Business context:
        First-run experience must be seamless. Users shouldn't need to
        manually create directories before using the tracker.

        Arrangement:
        MockFileSystem starts with no directories created.

        Action:
        Initializes StorageManager with /test/storage path.

        Assertion Strategy:
        Validates directory existence using is_dir check on the mock
        filesystem to confirm mkdir was called.
        """
        StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_dir("/test/storage")

    def test_creates_charts_directory(self, mock_fs: MockFileSystem) -> None:
        """Verifies StorageManager creates the charts subdirectory.

        Tests that initialization creates a dedicated charts directory
        for storing generated visualization images.

        Business context:
        Chart images are separate from JSON data files. Dedicated
        directory keeps the storage structure organized.

        Arrangement:
        MockFileSystem starts empty; storage dir doesn't exist yet.

        Action:
        Initializes StorageManager and captures charts_dir path.

        Assertion Strategy:
        Validates charts directory exists as a subdirectory of the
        main storage directory.
        """
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_dir(storage.charts_dir)

    def test_creates_sessions_file(self, mock_fs: MockFileSystem) -> None:
        """Verifies initialization creates empty sessions.json file.

        Tests that a valid JSON file with empty dict is created for
        session storage if no file exists.

        Business context:
        Sessions file must exist with valid JSON before any read/write
        operations. Empty dict represents zero sessions state.

        Arrangement:
        MockFileSystem starts empty.

        Action:
        Initializes StorageManager and reads sessions file content.

        Assertion Strategy:
        Validates file exists, is valid JSON, and contains empty dict
        matching the expected initial state for sessions.

        Testing Principle:
        Validates file initialization for first-run experience.
        """
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_file(storage.sessions_file)
        content = json.loads(mock_fs.read_text(storage.sessions_file))
        assert content == {}

    def test_creates_interactions_file(self, mock_fs: MockFileSystem) -> None:
        """Verifies initialization creates empty interactions.json file.

        Tests that a valid JSON file with empty array is created for
        interaction storage if no file exists.

        Business context:
        Interactions file stores prompt/response pairs as a list.
        Empty array represents zero recorded interactions.

        Arrangement:
        MockFileSystem starts empty.

        Action:
        Initializes StorageManager and reads interactions file content.

        Assertion Strategy:
        Validates file exists, is valid JSON, and contains empty list
        matching the expected initial state for interactions.

        Testing Principle:
        Validates file initialization for first-run experience.
        """
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_file(storage.interactions_file)
        content = json.loads(mock_fs.read_text(storage.interactions_file))
        assert content == []

    def test_creates_issues_file(self, mock_fs: MockFileSystem) -> None:
        """Verifies initialization creates empty issues.json file.

        Tests that a valid JSON file with empty array is created for
        issue storage if no file exists.

        Business context:
        Issues file stores flagged AI problems as a list. Empty array
        represents no issues have been flagged.

        Arrangement:
        MockFileSystem starts empty.

        Action:
        Initializes StorageManager and reads issues file content.

        Assertion Strategy:
        Validates file exists, is valid JSON, and contains empty list
        matching the expected initial state for issues.

        Testing Principle:
        Validates file initialization for first-run experience.
        """
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_file(storage.issues_file)
        content = json.loads(mock_fs.read_text(storage.issues_file))
        assert content == []

    def test_preserves_existing_data(self, mock_fs: MockFileSystem) -> None:
        """Verifies initialization does not overwrite existing data files.

        Tests that pre-existing session data survives StorageManager
        initialization, preventing accidental data loss.

        Business context:
        Critical data safety check. Re-initialization (e.g., app restart)
        must never destroy existing tracking data.

        Arrangement:
        1. Manually create storage directory.
        2. Write sessions.json with existing data before init.

        Action:
        Initializes StorageManager pointing to pre-populated directory.

        Assertion Strategy:
        Validates that sessions file still contains original data,
        confirming init skips file creation when file exists.
        """
        # Pre-create the directory and file
        mock_fs.makedirs("/test/storage", exist_ok=True)
        mock_fs.write_text(
            "/test/storage/sessions.json",
            json.dumps({"existing": "data"}),
        )

        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        content = json.loads(mock_fs.read_text(storage.sessions_file))
        assert content == {"existing": "data"}


class TestSessionOperations:
    """Test suite for session CRUD operations.

    Categories:
    1. Read Operations - load_sessions, get_session (4 tests)
    2. Write Operations - save_sessions, update_session (4 tests)
    3. Return Values - Boolean success indicators (2 tests)

    Total: 10 tests covering complete session lifecycle.
    """

    def test_load_sessions_empty(self, storage: StorageManager) -> None:
        """Verifies load_sessions returns empty dict for new storage.

        Tests the initial state of session loading when no sessions
        have been created yet.

        Business context:
        Dashboard must handle empty state gracefully on first run.

        Arrangement:
        Fresh StorageManager with auto-initialized empty sessions file.

        Action:
        Calls load_sessions on virgin storage instance.

        Assertion Strategy:
        Validates empty dict is returned, matching expected initial
        state for dict-based session storage.
        """
        sessions = storage.load_sessions()
        assert sessions == {}

    def test_save_sessions_creates_file(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """Verifies save_sessions writes session data to JSON file.

        Tests the core persistence mechanism by saving a session dict
        and verifying the file contents match the saved data.

        Business context:
        Session persistence is critical for tracking AI coding sessions
        across restarts. Data must be written correctly to JSON format.

        Arrangement:
        1. StorageManager initialized with mock filesystem.
        2. Sessions file exists but is empty from initialization.

        Action:
        Calls save_sessions with a test session dictionary containing
        session ID as key and session metadata as value.

        Assertion Strategy:
        Validates persistence by reading raw file content and parsing
        JSON to confirm exact data match with saved session.

        Testing Principle:
        Validates data integrity, ensuring serialization preserves
        all session fields without corruption or data loss.
        """
        storage.save_sessions({"s1": {"name": "test"}})
        content = json.loads(mock_fs.read_text(storage.sessions_file))
        assert content == {"s1": {"name": "test"}}

    def test_save_sessions_returns_true(self, storage: StorageManager) -> None:
        """Verifies save_sessions returns True on successful write.

        Tests the return value contract for successful persistence,
        enabling callers to detect and handle write failures.

        Business context:
        MCP tools report success/failure. Storage operations must
        provide clear success indicators for error handling.

        Arrangement:
        Fresh StorageManager with writable mock filesystem.

        Action:
        Calls save_sessions with valid session data.

        Assertion Strategy:
        Validates boolean True return, confirming success indicator
        contract is maintained.
        """
        result = storage.save_sessions({"s1": {"name": "test"}})
        assert result is True

    def test_load_sessions_returns_saved_data(self, storage: StorageManager) -> None:
        """Verifies load_sessions returns previously saved session data.

        Tests the complete save/load roundtrip to ensure data integrity
        through the serialization and deserialization process.

        Business context:
        Session data must survive save/load cycles exactly. Lost or
        corrupted data would invalidate ROI metrics.

        Arrangement:
        Fresh StorageManager ready to accept session data.

        Action:
        1. Saves test data with multiple sessions.
        2. Immediately loads sessions back.

        Assertion Strategy:
        Validates loaded data exactly matches saved data, confirming
        JSON roundtrip preserves all session fields.
        """
        test_data = {"s1": {"name": "Session 1"}, "s2": {"name": "Session 2"}}
        storage.save_sessions(test_data)
        loaded = storage.load_sessions()
        assert loaded == test_data

    def test_get_session_existing(self, storage: StorageManager) -> None:
        """Verifies get_session returns session data for existing ID.

        Tests single-session retrieval by ID, the primary access pattern
        for session lookup during interactions and ending.

        Business context:
        log_ai_interaction and end_ai_session need to look up sessions
        by ID to add data. Must return exact session dict.

        Arrangement:
        StorageManager pre-populated with one session.

        Action:
        Calls get_session with the known session ID.

        Assertion Strategy:
        Validates returned dict matches the stored session data,
        confirming ID-based lookup works correctly.
        """
        storage.save_sessions({"s1": {"name": "Session 1"}})
        result = storage.get_session("s1")
        assert result == {"name": "Session 1"}

    def test_get_session_not_found(self, storage: StorageManager) -> None:
        """Verifies get_session returns None for non-existent ID.

        Tests lookup behavior when session ID doesn't exist, enabling
        callers to distinguish missing from found sessions.

        Business context:
        Invalid session IDs passed to MCP tools must be detected.
        None return allows proper error messaging to users.

        Arrangement:
        Fresh StorageManager with no sessions stored.

        Action:
        Calls get_session with an ID that was never created.

        Assertion Strategy:
        Validates None is returned rather than raising KeyError,
        confirming the null-object pattern for missing sessions.
        """
        result = storage.get_session("nonexistent")
        assert result is None

    def test_update_session_new(self, storage: StorageManager) -> None:
        """Verifies update_session creates new session when ID doesn't exist.

        Tests upsert semantics: update_session should insert if the
        session ID is not found in storage.

        Business context:
        start_ai_session creates new sessions. Single upsert method
        simplifies the API vs separate create/update methods.

        Arrangement:
        Fresh StorageManager with no sessions.

        Action:
        Calls update_session with a new session ID and data.

        Assertion Strategy:
        Validates session can be retrieved after update, confirming
        insert behavior when session didn't previously exist.
        """
        storage.update_session("s1", {"name": "New Session"})
        assert storage.get_session("s1") == {"name": "New Session"}

    def test_update_session_existing(self, storage: StorageManager) -> None:
        """Verifies update_session modifies existing session fields.

        Tests that update replaces the entire session dict for an
        existing ID, updating all fields to new values.

        Business context:
        end_ai_session updates status, end_time, and outcome. All
        fields must be updated atomically.

        Arrangement:
        StorageManager with existing session having 'active' status.

        Action:
        Calls update_session with same ID but different field values.

        Assertion Strategy:
        Validates both name and status fields reflect new values,
        confirming complete replacement semantics.
        """
        storage.save_sessions({"s1": {"name": "Old", "status": "active"}})
        storage.update_session("s1", {"name": "Updated", "status": "completed"})
        result = storage.get_session("s1")
        assert result["name"] == "Updated"
        assert result["status"] == "completed"

    def test_update_session_returns_true(self, storage: StorageManager) -> None:
        """Verifies update_session returns True on successful update.

        Tests the return value contract for session updates, enabling
        callers to detect write failures.

        Business context:
        MCP tools need to know if updates succeeded. Boolean return
        enables proper error handling and user feedback.

        Arrangement:
        Fresh StorageManager with writable filesystem.

        Action:
        Calls update_session with new session data.

        Assertion Strategy:
        Validates boolean True return, confirming success indicator
        contract is maintained for updates.
        """
        result = storage.update_session("s1", {"name": "test"})
        assert result is True


class TestInteractionOperations:
    """Test suite for interaction CRUD operations.

    Categories:
    1. Read Operations - load_interactions, get_session_interactions (3 tests)
    2. Write Operations - save_interactions, add_interaction (3 tests)
    3. Return Values - Boolean success indicators (2 tests)

    Total: 8 tests covering complete interaction lifecycle.
    """

    def test_load_interactions_empty(self, storage: StorageManager) -> None:
        """Verifies load_interactions returns empty list for new storage.

        Tests the initial state of interaction loading when no
        interactions have been recorded yet.

        Business context:
        Empty state is valid for new projects. Dashboard must render
        correctly with zero interactions.

        Arrangement:
        Fresh StorageManager with auto-initialized empty interactions file.

        Action:
        Calls load_interactions on virgin storage instance.

        Assertion Strategy:
        Validates empty list is returned, matching expected initial
        state for list-based interaction storage.
        """
        interactions = storage.load_interactions()
        assert interactions == []

    def test_save_interactions_creates_file(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """Verifies save_interactions writes interaction data to JSON file.

        Tests interaction persistence by saving a list of interactions
        and verifying file contents match the saved data exactly.

        Business context:
        Interactions capture AI prompt/response pairs and effectiveness
        ratings. Persistence enables historical analysis and ROI tracking.

        Arrangement:
        1. StorageManager initialized with mock filesystem.
        2. Interactions file exists but contains empty array.

        Action:
        Calls save_interactions with a list containing one interaction
        record with an id field.

        Assertion Strategy:
        Validates by reading raw file content and parsing JSON to
        confirm the array structure and content match saved data.

        Testing Principle:
        Validates list serialization, ensuring array format is preserved
        and individual interaction records remain intact.
        """
        storage.save_interactions([{"id": 1}])
        content = json.loads(mock_fs.read_text(storage.interactions_file))
        assert content == [{"id": 1}]

    def test_save_interactions_returns_true(self, storage: StorageManager) -> None:
        """Verifies save_interactions returns True on successful write.

        Tests the return value contract for successful interaction
        persistence, enabling callers to detect write failures.

        Business context:
        Interaction logging must confirm success. Failed writes could
        mean lost effectiveness data affecting ROI calculations.

        Arrangement:
        Fresh StorageManager with writable mock filesystem.

        Action:
        Calls save_interactions with empty list.

        Assertion Strategy:
        Validates boolean True return, confirming success indicator
        contract is maintained.
        """
        result = storage.save_interactions([])
        assert result is True

    def test_add_interaction_appends(self, storage: StorageManager) -> None:
        """Verifies add_interaction appends to existing interaction list.

        Tests that new interactions are added to the end of the list
        without overwriting previous interactions.

        Business context:
        Sessions have multiple interactions. Each log_ai_interaction
        call must append, not replace, previous interactions.

        Arrangement:
        Fresh StorageManager with empty interactions.

        Action:
        Calls add_interaction twice with different interaction data.

        Assertion Strategy:
        Validates list contains both interactions in order, confirming
        append semantics rather than replacement.
        """
        storage.add_interaction({"id": 1})
        storage.add_interaction({"id": 2})
        loaded = storage.load_interactions()
        assert len(loaded) == 2
        assert loaded[0]["id"] == 1
        assert loaded[1]["id"] == 2

    def test_add_interaction_returns_true(self, storage: StorageManager) -> None:
        """Verifies add_interaction returns True on successful append.

        Tests the return value contract for interaction addition,
        enabling MCP tools to report success to users.

        Business context:
        log_ai_interaction tool must confirm the interaction was
        saved. Users expect feedback on successful logging.

        Arrangement:
        Fresh StorageManager with writable filesystem.

        Action:
        Calls add_interaction with valid interaction data.

        Assertion Strategy:
        Validates boolean True return, confirming success indicator.
        """
        result = storage.add_interaction({"id": 1})
        assert result is True

    def test_get_session_interactions_filters(self, storage: StorageManager) -> None:
        """Verifies get_session_interactions filters by session_id.

        Tests that only interactions belonging to the specified session
        are returned, filtering out other sessions' interactions.

        Business context:
        Session-specific metrics require filtering. Effectiveness
        averages must be calculated per-session.

        Arrangement:
        StorageManager with interactions from multiple sessions.

        Action:
        Calls get_session_interactions for session 's1' only.

        Assertion Strategy:
        Validates returned list contains only s1's interactions and
        all of them have the correct session_id.
        """
        storage.save_interactions(
            [
                {"session_id": "s1", "data": 1},
                {"session_id": "s2", "data": 2},
                {"session_id": "s1", "data": 3},
            ]
        )
        result = storage.get_session_interactions("s1")
        assert len(result) == 2
        assert all(i["session_id"] == "s1" for i in result)

    def test_get_session_interactions_empty(self, storage: StorageManager) -> None:
        """Verifies get_session_interactions returns empty list when none match.

        Tests filtering behavior when no interactions exist for the
        specified session ID.

        Business context:
        Sessions may have zero interactions initially. API must handle
        this gracefully without errors.

        Arrangement:
        StorageManager with interactions from a different session.

        Action:
        Calls get_session_interactions for non-existent session.

        Assertion Strategy:
        Validates empty list is returned rather than None or error,
        enabling consistent list handling in callers.
        """
        storage.save_interactions([{"session_id": "s1", "data": 1}])
        result = storage.get_session_interactions("nonexistent")
        assert result == []


class TestIssueOperations:
    """Test suite for issue CRUD operations.

    Categories:
    1. Read Operations - load_issues, get_session_issues (3 tests)
    2. Write Operations - save_issues, add_issue (3 tests)
    3. Return Values - Boolean success indicators (2 tests)

    Total: 8 tests covering complete issue lifecycle.
    """

    def test_load_issues_empty(self, storage: StorageManager) -> None:
        """Verifies load_issues returns empty list for new storage.

        Tests the initial state of issue loading when no issues
        have been flagged yet.

        Business context:
        Clean projects have no AI issues. Empty state is the happy
        path indicating no problems flagged.

        Arrangement:
        Fresh StorageManager with auto-initialized empty issues file.

        Action:
        Calls load_issues on virgin storage instance.

        Assertion Strategy:
        Validates empty list is returned, matching expected initial
        state for list-based issue storage.
        """
        issues = storage.load_issues()
        assert issues == []

    def test_save_issues_creates_file(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """Verifies save_issues writes issue data to JSON file.

        Tests issue persistence by saving a list of issues and verifying
        file contents match the saved data exactly.

        Business context:
        Issues track AI failures and problems flagged during sessions.
        Persistence enables pattern analysis and workflow improvement.

        Arrangement:
        1. StorageManager initialized with mock filesystem.
        2. Issues file exists but contains empty array.

        Action:
        Calls save_issues with a list containing one issue record
        with an id field.

        Assertion Strategy:
        Validates by reading raw file content and parsing JSON to
        confirm the array structure and content match saved data.

        Testing Principle:
        Validates list serialization for issues, ensuring the storage
        format is consistent with interactions.
        """
        storage.save_issues([{"id": 1}])
        content = json.loads(mock_fs.read_text(storage.issues_file))
        assert content == [{"id": 1}]

    def test_save_issues_returns_true(self, storage: StorageManager) -> None:
        """Verifies save_issues returns True on successful write.

        Tests the return value contract for successful issue
        persistence, enabling callers to detect write failures.

        Business context:
        Issue flagging must confirm success. Lost issue reports
        would hide AI problems from analysis.

        Arrangement:
        Fresh StorageManager with writable mock filesystem.

        Action:
        Calls save_issues with empty list.

        Assertion Strategy:
        Validates boolean True return, confirming success indicator
        contract is maintained.
        """
        result = storage.save_issues([])
        assert result is True

    def test_add_issue_appends(self, storage: StorageManager) -> None:
        """Verifies add_issue appends to existing issue list.

        Tests that new issues are added to the end of the list
        without overwriting previous issues.

        Business context:
        Sessions may have multiple issues. Each flag_ai_issue call
        must append to the list, preserving issue history.

        Arrangement:
        Fresh StorageManager with empty issues.

        Action:
        Calls add_issue twice with different issue data.

        Assertion Strategy:
        Validates list contains both issues, confirming append
        semantics rather than replacement.
        """
        storage.add_issue({"id": 1})
        storage.add_issue({"id": 2})
        loaded = storage.load_issues()
        assert len(loaded) == 2

    def test_add_issue_returns_true(self, storage: StorageManager) -> None:
        """Verifies add_issue returns True on successful append.

        Tests the return value contract for issue addition, enabling
        MCP tools to report success to users.

        Business context:
        flag_ai_issue tool must confirm the issue was recorded.
        Users expect feedback on successful flagging.

        Arrangement:
        Fresh StorageManager with writable filesystem.

        Action:
        Calls add_issue with valid issue data.

        Assertion Strategy:
        Validates boolean True return, confirming success indicator.
        """
        result = storage.add_issue({"id": 1})
        assert result is True

    def test_get_session_issues_filters(self, storage: StorageManager) -> None:
        """Verifies get_session_issues filters by session_id.

        Tests that only issues belonging to the specified session
        are returned, filtering out other sessions' issues.

        Business context:
        Session-specific issue counts require filtering. Issue
        summaries must reflect per-session problems only.

        Arrangement:
        StorageManager with issues from multiple sessions.

        Action:
        Calls get_session_issues for session 's1' only.

        Assertion Strategy:
        Validates returned list contains only s1's issues and
        all of them have the correct session_id.
        """
        storage.save_issues(
            [
                {"session_id": "s1", "severity": "high"},
                {"session_id": "s2", "severity": "low"},
                {"session_id": "s1", "severity": "medium"},
            ]
        )
        result = storage.get_session_issues("s1")
        assert len(result) == 2
        assert all(i["session_id"] == "s1" for i in result)

    def test_get_session_issues_empty(self, storage: StorageManager) -> None:
        """Verifies get_session_issues returns empty list when none match.

        Tests filtering behavior when no issues exist for the
        specified session ID.

        Business context:
        Most sessions have zero issues. API must handle this
        gracefully without errors.

        Arrangement:
        StorageManager with issues from a different session.

        Action:
        Calls get_session_issues for non-existent session.

        Assertion Strategy:
        Validates empty list is returned rather than None or error,
        enabling consistent list handling in callers.
        """
        storage.save_issues([{"session_id": "s1"}])
        result = storage.get_session_issues("nonexistent")
        assert result == []


class TestMaintenanceOperations:
    """Test suite for maintenance and cleanup operations.

    Categories:
    1. Clear Operations - Reset all data stores (4 tests)

    Total: 4 tests verifying complete data reset functionality.
    """

    def test_clear_all_empties_sessions(self, storage: StorageManager) -> None:
        """Verifies clear_all empties the sessions storage.

        Tests that clear_all removes all session data, returning
        storage to its initial empty state.

        Business context:
        Testing and demos require data reset capability. Clear must
        remove all sessions without affecting structure.

        Arrangement:
        StorageManager with pre-existing session data.

        Action:
        Calls clear_all to reset all data stores.

        Assertion Strategy:
        Validates sessions load returns empty dict, confirming all
        session data was removed.
        """
        storage.save_sessions({"s1": {"name": "test"}})
        storage.clear_all()
        assert storage.load_sessions() == {}

    def test_clear_all_empties_interactions(self, storage: StorageManager) -> None:
        """Verifies clear_all empties the interactions storage.

        Tests that clear_all removes all interaction data, returning
        storage to its initial empty state.

        Business context:
        Interactions must be cleared along with sessions to maintain
        referential consistency. Orphan interactions would corrupt stats.

        Arrangement:
        StorageManager with pre-existing interaction data.

        Action:
        Calls clear_all to reset all data stores.

        Assertion Strategy:
        Validates interactions load returns empty list, confirming all
        interaction data was removed.
        """
        storage.add_interaction({"id": 1})
        storage.clear_all()
        assert storage.load_interactions() == []

    def test_clear_all_empties_issues(self, storage: StorageManager) -> None:
        """Verifies clear_all empties the issues storage.

        Tests that clear_all removes all issue data, returning
        storage to its initial empty state.

        Business context:
        Issues must be cleared along with sessions to maintain
        referential consistency. Orphan issues would corrupt stats.

        Arrangement:
        StorageManager with pre-existing issue data.

        Action:
        Calls clear_all to reset all data stores.

        Assertion Strategy:
        Validates issues load returns empty list, confirming all
        issue data was removed.
        """
        storage.add_issue({"id": 1})
        storage.clear_all()
        assert storage.load_issues() == []

    def test_clear_all_returns_true(self, storage: StorageManager) -> None:
        """Verifies clear_all returns True on successful reset.

        Tests the return value contract for data reset operation,
        enabling callers to detect failures.

        Business context:
        Admin tools need confirmation of successful reset. Boolean
        return enables proper error handling.

        Arrangement:
        Fresh StorageManager with writable filesystem.

        Action:
        Calls clear_all to reset storage.

        Assertion Strategy:
        Validates boolean True return, confirming success indicator
        contract is maintained for maintenance operations.
        """
        result = storage.clear_all()
        assert result is True


class TestErrorHandling:
    """Test suite for error handling in storage operations.

    Categories:
    1. Missing File Recovery - Handle deleted files (1 test)
    2. Corrupt Data Recovery - Handle invalid JSON (1 test)
    3. Serialization Edge Cases - Handle non-JSON types (1 test)
    4. Permission Errors - Handle write failures (1 test)

    Total: 4 tests covering resilience and error recovery.
    """

    def test_read_json_returns_default_on_missing_file(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """Verifies load_sessions returns empty dict when file is missing.

        Tests graceful degradation when the sessions file has been deleted
        or never existed, ensuring the system remains functional.

        Business context:
        Production resilience requires handling missing files gracefully.
        Users may delete storage files; the system should not crash.

        Arrangement:
        1. StorageManager initialized (creates sessions file).
        2. Sessions file deliberately removed to simulate missing file.

        Action:
        Calls load_sessions on storage with missing backing file.

        Assertion Strategy:
        Validates that empty dict (the default for sessions) is returned
        rather than raising FileNotFoundError or returning None.

        Testing Principle:
        Validates defensive programming, ensuring the storage layer
        handles filesystem edge cases without propagating errors.
        """
        mock_fs.remove(storage.sessions_file)
        result = storage.load_sessions()
        assert result == {}

    def test_read_json_returns_default_on_invalid_json(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """Verifies load_sessions returns empty dict for corrupted JSON.

        Tests graceful handling of malformed JSON files, ensuring the
        system recovers rather than crashing on parse errors.

        Business context:
        File corruption can occur from crashes, disk errors, or manual
        editing. The system must handle this without data loss panic.

        Arrangement:
        1. StorageManager initialized with valid empty sessions file.
        2. Sessions file overwritten with syntactically invalid JSON.

        Action:
        Calls load_sessions on storage with corrupted backing file.

        Assertion Strategy:
        Validates that empty dict (the safe default) is returned
        rather than raising JSONDecodeError or returning partial data.

        Testing Principle:
        Validates error recovery, ensuring parse failures result in
        safe defaults rather than exceptions propagating to callers.
        """
        mock_fs.write_text(storage.sessions_file, "not valid json {{{")
        result = storage.load_sessions()
        assert result == {}

    def test_write_json_handles_non_serializable(self, storage: StorageManager) -> None:
        """Verifies storage handles non-JSON-serializable types gracefully.

        Tests that datetime objects and other non-serializable types are
        converted to strings rather than raising TypeError.

        Business context:
        Session timestamps are datetime objects. Storage must serialize
        them without requiring callers to convert manually.

        Arrangement:
        Fresh StorageManager ready to accept session data.

        Action:
        Saves session containing datetime.now() value.

        Assertion Strategy:
        Validates no exception is raised during save, file contains
        valid JSON, and datetime was converted to string.
        """
        # datetime objects should be converted to strings
        storage.save_sessions({"time": datetime.now()})
        # Should not raise, and file should be valid JSON
        loaded = storage.load_sessions()
        assert "time" in loaded
        assert isinstance(loaded["time"], str)

    def test_write_json_returns_false_on_permission_error(self, mock_fs: MockFileSystem) -> None:
        """Verifies save returns False when file is read-only.

        Tests error handling when filesystem permissions prevent writing,
        ensuring graceful degradation rather than exception propagation.

        Business context:
        Production systems may have permission issues. Storage must
        handle failures gracefully and report via return value.

        Arrangement:
        1. StorageManager initialized with normal permissions.
        2. Sessions file chmod'd to read-only (0o444).

        Action:
        Attempts to save new session data to read-only file.

        Assertion Strategy:
        Validates False is returned rather than raising PermissionError,
        enabling callers to handle gracefully.
        """
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        # Make file read-only using MockFileSystem's chmod
        mock_fs.chmod(storage.sessions_file, 0o444)
        result = storage.save_sessions({"new": "data"})
        assert result is False


class TestReadJsonErrorHandling:
    """Tests for _read_json error handling paths."""

    def test_read_json_handles_os_error(self, mock_fs: MockFileSystem) -> None:
        """Verifies _read_json returns default on OSError.

        Tests that non-FileNotFoundError OSErrors (like permission denied)
        are caught and handled gracefully.

        Business context:
        Production may have intermittent I/O errors. Storage must
        continue operating with defaults rather than crashing.
        """
        from unittest.mock import patch

        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)

        # Patch read_text to raise OSError
        with patch.object(mock_fs, "read_text", side_effect=OSError("Disk error")):
            result = storage.load_sessions()
            assert result == {}

    def test_read_json_handles_invalid_json(self, mock_fs: MockFileSystem) -> None:
        """Verifies _read_json returns default on JSONDecodeError.

        Tests that corrupted JSON files are handled gracefully by
        returning the default value.

        Business context:
        File corruption can occur. Storage must not crash on bad data.
        """
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)

        # Write invalid JSON to sessions file
        mock_fs.write_text(storage.sessions_file, "{ invalid json }")

        result = storage.load_sessions()
        assert result == {}


class TestEnsureFilesExistErrorHandling:
    """Tests for _ensure_files_exist error handling."""

    def test_handles_os_error_during_init(self, mock_fs: MockFileSystem) -> None:
        """Verifies storage handles OSError during initialization gracefully.

        Tests that _ensure_files_exist catches and logs OSError when
        file initialization fails.

        Business context:
        Permission issues or disk full conditions during init should
        be logged but not crash the entire application.
        """
        from unittest.mock import patch

        # Make the filesystem raise OSError on makedirs
        with patch.object(mock_fs, "makedirs", side_effect=OSError("Permission denied")):
            # Should not raise - error is caught and logged
            storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
            # Storage is created but may have empty/default state
            assert storage is not None
