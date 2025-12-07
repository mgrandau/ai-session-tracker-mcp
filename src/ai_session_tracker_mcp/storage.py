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
from typing import TYPE_CHECKING, Any

from .config import Config
from .filesystem import RealFileSystem

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

    THREAD SAFETY:
    Not thread-safe. For multi-threaded use, wrap calls with locks.
    Single-writer assumed (one MCP server process).
    """

    def __init__(
        self,
        storage_dir: str | None = None,
        filesystem: FileSystem | None = None,
    ) -> None:
        """
        Initialize storage with directory structure.

        Args:
            storage_dir: Custom storage path. Default: Config.STORAGE_DIR
            filesystem: FileSystem implementation. Default: RealFileSystem

        Creates:
            - Main storage directory
            - Charts subdirectory
            - Empty JSON files (sessions, interactions, issues)
        """
        self.storage_dir = storage_dir or Config.STORAGE_DIR
        self._fs: FileSystem = filesystem or RealFileSystem()
        self.sessions_file = os.path.join(self.storage_dir, Config.SESSIONS_FILE)
        self.interactions_file = os.path.join(self.storage_dir, Config.INTERACTIONS_FILE)
        self.issues_file = os.path.join(self.storage_dir, Config.ISSUES_FILE)
        self.charts_dir = os.path.join(self.storage_dir, Config.CHARTS_DIR)

        self._initialize_storage()

    def _initialize_storage(self) -> None:
        """
        Create directory structure and initialize empty files.

        ERROR HANDLING:
        Logs errors but doesn't raise - allows degraded operation.
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

    def _read_json(self, file_path: str, default: Any) -> Any:
        """
        Read JSON file with error handling.

        Args:
            file_path: Absolute path to JSON file
            default: Value to return on any error

        Returns:
            Parsed JSON data or default value.
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
        Write JSON file with error handling.

        Args:
            file_path: Absolute path to JSON file
            data: Data to serialize

        Returns:
            True on success, False on failure.

        FORMATTING:
        - 2-space indent for readability
        - default=str for datetime/custom types
        - UTF-8 encoding
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
        Load all sessions.

        Returns:
            Dict of session_id -> session_data. Empty dict if unavailable.
        """
        result: dict[str, Any] = self._read_json(self.sessions_file, {})
        return result

    def save_sessions(self, sessions: dict[str, Any]) -> bool:
        """
        Save sessions to disk.

        Args:
            sessions: Dict of session_id -> session_data

        Returns:
            True on success.
        """
        return self._write_json(self.sessions_file, sessions)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Get single session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session data dict or None if not found.
        """
        sessions = self.load_sessions()
        return sessions.get(session_id)

    def update_session(self, session_id: str, data: dict[str, Any]) -> bool:
        """
        Update single session.

        Args:
            session_id: Session identifier
            data: Updated session data

        Returns:
            True on success.
        """
        sessions = self.load_sessions()
        sessions[session_id] = data
        return self.save_sessions(sessions)

    # =========================================================================
    # INTERACTION OPERATIONS
    # =========================================================================

    def load_interactions(self) -> list[dict[str, Any]]:
        """
        Load all interactions.

        Returns:
            List of interaction records. Empty list if unavailable.
        """
        result: list[dict[str, Any]] = self._read_json(self.interactions_file, [])
        return result

    def save_interactions(self, interactions: list[dict[str, Any]]) -> bool:
        """
        Save interactions to disk.

        Args:
            interactions: List of interaction records

        Returns:
            True on success.
        """
        return self._write_json(self.interactions_file, interactions)

    def add_interaction(self, interaction: dict[str, Any]) -> bool:
        """
        Append single interaction.

        Args:
            interaction: Interaction record to add

        Returns:
            True on success.
        """
        interactions = self.load_interactions()
        interactions.append(interaction)
        return self.save_interactions(interactions)

    def get_session_interactions(self, session_id: str) -> list[dict[str, Any]]:
        """
        Get all interactions for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of interactions for this session.
        """
        interactions = self.load_interactions()
        return [i for i in interactions if i.get("session_id") == session_id]

    # =========================================================================
    # ISSUE OPERATIONS
    # =========================================================================

    def load_issues(self) -> list[dict[str, Any]]:
        """
        Load all issues.

        Returns:
            List of issue records. Empty list if unavailable.
        """
        result: list[dict[str, Any]] = self._read_json(self.issues_file, [])
        return result

    def save_issues(self, issues: list[dict[str, Any]]) -> bool:
        """
        Save issues to disk.

        Args:
            issues: List of issue records

        Returns:
            True on success.
        """
        return self._write_json(self.issues_file, issues)

    def add_issue(self, issue: dict[str, Any]) -> bool:
        """
        Append single issue.

        Args:
            issue: Issue record to add

        Returns:
            True on success.
        """
        issues = self.load_issues()
        issues.append(issue)
        return self.save_issues(issues)

    def get_session_issues(self, session_id: str) -> list[dict[str, Any]]:
        """
        Get all issues for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of issues for this session.
        """
        issues = self.load_issues()
        return [i for i in issues if i.get("session_id") == session_id]

    # =========================================================================
    # MAINTENANCE OPERATIONS
    # =========================================================================

    def clear_all(self) -> bool:
        """
        Reset all data files to empty state.

        WARNING: Destroys all data. Use after S3 backup or for testing.

        Returns:
            True if all clears succeeded.
        """
        success = True
        success &= self._write_json(self.sessions_file, {})
        success &= self._write_json(self.interactions_file, [])
        success &= self._write_json(self.issues_file, [])
        if success:
            logger.info("All data files cleared")
        return success
