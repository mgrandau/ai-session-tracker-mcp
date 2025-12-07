"""Tests for storage module."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from ai_session_tracker_mcp.filesystem import MockFileSystem
from ai_session_tracker_mcp.storage import StorageManager


@pytest.fixture
def mock_fs() -> MockFileSystem:
    """Create a MockFileSystem for testing."""
    return MockFileSystem()


@pytest.fixture
def storage(mock_fs: MockFileSystem) -> StorageManager:
    """Create StorageManager with mock file system."""
    return StorageManager(storage_dir="/test/storage", filesystem=mock_fs)


class TestStorageManagerInit:
    """Tests for StorageManager initialization."""

    def test_creates_storage_directory(self, mock_fs: MockFileSystem) -> None:
        """Init creates storage directory."""
        StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_dir("/test/storage")

    def test_creates_charts_directory(self, mock_fs: MockFileSystem) -> None:
        """Init creates charts subdirectory."""
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_dir(storage.charts_dir)

    def test_creates_sessions_file(self, mock_fs: MockFileSystem) -> None:
        """Init creates empty sessions.json."""
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_file(storage.sessions_file)
        content = json.loads(mock_fs.read_text(storage.sessions_file))
        assert content == {}

    def test_creates_interactions_file(self, mock_fs: MockFileSystem) -> None:
        """Init creates empty interactions.json."""
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_file(storage.interactions_file)
        content = json.loads(mock_fs.read_text(storage.interactions_file))
        assert content == []

    def test_creates_issues_file(self, mock_fs: MockFileSystem) -> None:
        """Init creates empty issues.json."""
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        assert mock_fs.is_file(storage.issues_file)
        content = json.loads(mock_fs.read_text(storage.issues_file))
        assert content == []

    def test_preserves_existing_data(self, mock_fs: MockFileSystem) -> None:
        """Init doesn't overwrite existing data files."""
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
    """Tests for session CRUD operations."""

    def test_load_sessions_empty(self, storage: StorageManager) -> None:
        """load_sessions returns empty dict for new storage."""
        sessions = storage.load_sessions()
        assert sessions == {}

    def test_save_sessions_creates_file(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """save_sessions writes to file."""
        storage.save_sessions({"s1": {"name": "test"}})
        content = json.loads(mock_fs.read_text(storage.sessions_file))
        assert content == {"s1": {"name": "test"}}

    def test_save_sessions_returns_true(self, storage: StorageManager) -> None:
        """save_sessions returns True on success."""
        result = storage.save_sessions({"s1": {"name": "test"}})
        assert result is True

    def test_load_sessions_returns_saved_data(self, storage: StorageManager) -> None:
        """load_sessions returns previously saved data."""
        test_data = {"s1": {"name": "Session 1"}, "s2": {"name": "Session 2"}}
        storage.save_sessions(test_data)
        loaded = storage.load_sessions()
        assert loaded == test_data

    def test_get_session_existing(self, storage: StorageManager) -> None:
        """get_session returns session data for existing ID."""
        storage.save_sessions({"s1": {"name": "Session 1"}})
        result = storage.get_session("s1")
        assert result == {"name": "Session 1"}

    def test_get_session_not_found(self, storage: StorageManager) -> None:
        """get_session returns None for non-existent ID."""
        result = storage.get_session("nonexistent")
        assert result is None

    def test_update_session_new(self, storage: StorageManager) -> None:
        """update_session adds new session."""
        storage.update_session("s1", {"name": "New Session"})
        assert storage.get_session("s1") == {"name": "New Session"}

    def test_update_session_existing(self, storage: StorageManager) -> None:
        """update_session modifies existing session."""
        storage.save_sessions({"s1": {"name": "Old", "status": "active"}})
        storage.update_session("s1", {"name": "Updated", "status": "completed"})
        result = storage.get_session("s1")
        assert result["name"] == "Updated"
        assert result["status"] == "completed"

    def test_update_session_returns_true(self, storage: StorageManager) -> None:
        """update_session returns True on success."""
        result = storage.update_session("s1", {"name": "test"})
        assert result is True


class TestInteractionOperations:
    """Tests for interaction CRUD operations."""

    def test_load_interactions_empty(self, storage: StorageManager) -> None:
        """load_interactions returns empty list for new storage."""
        interactions = storage.load_interactions()
        assert interactions == []

    def test_save_interactions_creates_file(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """save_interactions writes to file."""
        storage.save_interactions([{"id": 1}])
        content = json.loads(mock_fs.read_text(storage.interactions_file))
        assert content == [{"id": 1}]

    def test_save_interactions_returns_true(self, storage: StorageManager) -> None:
        """save_interactions returns True on success."""
        result = storage.save_interactions([])
        assert result is True

    def test_add_interaction_appends(self, storage: StorageManager) -> None:
        """add_interaction appends to list."""
        storage.add_interaction({"id": 1})
        storage.add_interaction({"id": 2})
        loaded = storage.load_interactions()
        assert len(loaded) == 2
        assert loaded[0]["id"] == 1
        assert loaded[1]["id"] == 2

    def test_add_interaction_returns_true(self, storage: StorageManager) -> None:
        """add_interaction returns True on success."""
        result = storage.add_interaction({"id": 1})
        assert result is True

    def test_get_session_interactions_filters(self, storage: StorageManager) -> None:
        """get_session_interactions filters by session_id."""
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
        """get_session_interactions returns empty list when none match."""
        storage.save_interactions([{"session_id": "s1", "data": 1}])
        result = storage.get_session_interactions("nonexistent")
        assert result == []


class TestIssueOperations:
    """Tests for issue CRUD operations."""

    def test_load_issues_empty(self, storage: StorageManager) -> None:
        """load_issues returns empty list for new storage."""
        issues = storage.load_issues()
        assert issues == []

    def test_save_issues_creates_file(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """save_issues writes to file."""
        storage.save_issues([{"id": 1}])
        content = json.loads(mock_fs.read_text(storage.issues_file))
        assert content == [{"id": 1}]

    def test_save_issues_returns_true(self, storage: StorageManager) -> None:
        """save_issues returns True on success."""
        result = storage.save_issues([])
        assert result is True

    def test_add_issue_appends(self, storage: StorageManager) -> None:
        """add_issue appends to list."""
        storage.add_issue({"id": 1})
        storage.add_issue({"id": 2})
        loaded = storage.load_issues()
        assert len(loaded) == 2

    def test_add_issue_returns_true(self, storage: StorageManager) -> None:
        """add_issue returns True on success."""
        result = storage.add_issue({"id": 1})
        assert result is True

    def test_get_session_issues_filters(self, storage: StorageManager) -> None:
        """get_session_issues filters by session_id."""
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
        """get_session_issues returns empty list when none match."""
        storage.save_issues([{"session_id": "s1"}])
        result = storage.get_session_issues("nonexistent")
        assert result == []


class TestMaintenanceOperations:
    """Tests for maintenance operations."""

    def test_clear_all_empties_sessions(self, storage: StorageManager) -> None:
        """clear_all empties sessions file."""
        storage.save_sessions({"s1": {"name": "test"}})
        storage.clear_all()
        assert storage.load_sessions() == {}

    def test_clear_all_empties_interactions(self, storage: StorageManager) -> None:
        """clear_all empties interactions file."""
        storage.add_interaction({"id": 1})
        storage.clear_all()
        assert storage.load_interactions() == []

    def test_clear_all_empties_issues(self, storage: StorageManager) -> None:
        """clear_all empties issues file."""
        storage.add_issue({"id": 1})
        storage.clear_all()
        assert storage.load_issues() == []

    def test_clear_all_returns_true(self, storage: StorageManager) -> None:
        """clear_all returns True on success."""
        result = storage.clear_all()
        assert result is True


class TestErrorHandling:
    """Tests for error handling in storage operations."""

    def test_read_json_returns_default_on_missing_file(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """_read_json returns default when file missing."""
        mock_fs.remove(storage.sessions_file)
        result = storage.load_sessions()
        assert result == {}

    def test_read_json_returns_default_on_invalid_json(
        self, storage: StorageManager, mock_fs: MockFileSystem
    ) -> None:
        """_read_json returns default on invalid JSON."""
        mock_fs.write_text(storage.sessions_file, "not valid json {{{")
        result = storage.load_sessions()
        assert result == {}

    def test_write_json_handles_non_serializable(self, storage: StorageManager) -> None:
        """_write_json uses default=str for non-serializable types."""
        # datetime objects should be converted to strings
        storage.save_sessions({"time": datetime.now()})
        # Should not raise, and file should be valid JSON
        loaded = storage.load_sessions()
        assert "time" in loaded
        assert isinstance(loaded["time"], str)

    def test_write_json_returns_false_on_permission_error(self, mock_fs: MockFileSystem) -> None:
        """_write_json returns False on write failure."""
        storage = StorageManager(storage_dir="/test/storage", filesystem=mock_fs)
        # Make file read-only using MockFileSystem's chmod
        mock_fs.chmod(storage.sessions_file, 0o444)
        result = storage.save_sessions({"new": "data"})
        assert result is False
