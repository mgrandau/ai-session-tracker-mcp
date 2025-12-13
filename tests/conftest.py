"""
Pytest configuration and shared fixtures for AI Session Tracker tests.

This module contains:
- MockFileSystem: In-memory filesystem for testing without actual I/O
- Shared fixtures available to all test modules
"""

from __future__ import annotations

import pytest


class MockFileSystem:
    """
    In-memory file system for testing.

    Simulates a file system using dictionaries:
    - _files: dict mapping path -> content (str)
    - _dirs: set of directory paths
    - _modes: dict mapping path -> permission mode (int)

    FEATURES:
    - No actual I/O operations
    - Fast test execution
    - Easy to inspect state
    - Supports permission simulation
    """

    def __init__(self) -> None:
        """
        Initialize empty mock file system.

        Creates empty internal storage structures for simulating
        files, directories, permissions, and read-only status.
        Takes no arguments - creates a blank slate filesystem.

        Business context: Mock filesystem enables testing storage
        operations without actual disk I/O, making tests fast and
        deterministic.

        Args:
            None. Creates empty mock filesystem.

        Returns:
            None. Initializes internal state.

        Raises:
            No exceptions raised. Always succeeds.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.list_files()
            []
        """
        self._files: dict[str, str] = {}
        self._dirs: set[str] = set()
        self._modes: dict[str, int] = {}
        self._read_only: set[str] = set()

    def exists(self, path: str) -> bool:
        """
        Check if path exists in mock filesystem.

        Checks both _files dict and _dirs set to determine if the
        path exists in the simulated filesystem.

        Business context: Used in storage layer to check for existing
        session files before loading. Mock enables fast unit tests.

        Args:
            path: Absolute path to check.

        Returns:
            True if path is in _files dict or _dirs set.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/sessions.json', '{}')
            >>> fs.exists('/data/sessions.json')
            True
        """
        return path in self._files or path in self._dirs

    def is_file(self, path: str) -> bool:
        """
        Check if path is a mock file.

        Checks only the _files dict, not directories.

        Business context: Storage layer uses this to verify path type
        before reading content.

        Args:
            path: Absolute path to check.

        Returns:
            True if path exists in _files dict.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/sessions.json', '{}')
            >>> fs.is_file('/data/sessions.json')
            True
            >>> fs.is_file('/data')  # directory
            False
        """
        return path in self._files

    def is_dir(self, path: str) -> bool:
        """
        Check if path is a mock directory.

        Checks only the _dirs set, not files.

        Business context: Storage layer uses this to check data
        directory existence before creating session files.

        Args:
            path: Absolute path to check.

        Returns:
            True if path exists in _dirs set.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.makedirs('/data', exist_ok=True)
            >>> fs.is_dir('/data')
            True
        """
        return path in self._dirs

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        """
        Create mock directory and parent directories.

        Simulates creating a directory tree by adding paths to the
        _dirs set. Creates all parent directories automatically by
        splitting the path and adding each component.

        Business context: Storage layer uses this to ensure data
        directories exist before writing files. Mock enables testing.

        Args:
            path: Absolute path of directory to create.
            exist_ok: If True, don't raise if directory exists.

        Returns:
            None. Adds directories to _dirs set as side effect.

        Raises:
            OSError: If directory exists and exist_ok is False,
                or if path is an existing file.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.makedirs('/data/backup', exist_ok=True)
            >>> fs.is_dir('/data')
            True
        """
        if path in self._dirs:
            if not exist_ok:
                raise OSError(f"Directory exists: {path}")
            return

        if path in self._files:
            raise OSError(f"Path is a file, not directory: {path}")

        # Create all parent directories
        parts = path.rstrip("/").split("/")
        for i in range(1, len(parts) + 1):
            parent = "/".join(parts[:i])
            if parent:
                self._dirs.add(parent)

    def read_text(self, path: str, _encoding: str = "utf-8") -> str:
        """
        Read mock file contents.

        Retrieves content stored in the _files dictionary. The encoding
        parameter is ignored since mock stores Python strings directly.

        Business context: Used by storage layer to load JSON session data.
        Mock enables testing without actual I/O operations.

        Args:
            path: Absolute path to file to read.
            _encoding: Ignored (mock stores strings directly).

        Returns:
            File contents as stored in _files dict.

        Raises:
            FileNotFoundError: If path not in _files.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/sessions.json', '{"sessions": []}')
            >>> fs.read_text('/data/sessions.json')
            '{"sessions": []}'
        """
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        return self._files[path]

    def write_text(self, path: str, content: str, _encoding: str = "utf-8") -> None:
        """
        Write text to mock file.

        Stores content in the _files dictionary. Automatically creates
        parent directories in _dirs set. Encoding parameter is ignored
        since mock stores Python strings directly.

        Business context: Used by storage layer to persist session data.
        Mock enables testing without actual disk writes.

        Args:
            path: Absolute path to file to write.
            content: String content to store.
            _encoding: Ignored (mock stores strings directly).

        Raises:
            PermissionError: If path is in _read_only set.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.write_text('/data/sessions.json', '{}')
            >>> fs.get_file('/data/sessions.json')
            '{}'
        """
        # Check if file is read-only
        if path in self._read_only:
            raise PermissionError(f"Permission denied: {path}")

        # Auto-create parent directories
        parent = "/".join(path.rstrip("/").split("/")[:-1])
        if parent and parent not in self._dirs:
            self.makedirs(parent, exist_ok=True)

        self._files[path] = content

    def chmod(self, path: str, mode: int) -> None:
        """
        Change mock file permissions.

        Stores permission mode and updates read-only status based on
        whether write bit (0o200) is set. Simulates Unix permission
        semantics for testing permission-related code paths.

        Business context: Storage layer may set restrictive permissions
        on sensitive config files. Mock enables testing this logic.

        Args:
            path: Absolute path to file or directory.
            mode: Permission mode as octal integer.

        Raises:
            FileNotFoundError: If path not in _files or _dirs.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/config.json', '{}')
            >>> fs.chmod('/data/config.json', 0o444)  # read-only
            >>> fs.write_text('/data/config.json', 'new')  # raises
            PermissionError: Permission denied: /data/config.json
        """
        if path not in self._files and path not in self._dirs:
            raise FileNotFoundError(f"No such file or directory: {path}")

        self._modes[path] = mode

        # Simulate read-only (mode 0o444 or less)
        if mode & 0o200 == 0:  # No write permission
            self._read_only.add(path)
        else:
            self._read_only.discard(path)

    def remove(self, path: str) -> None:
        """
        Remove a mock file.

        Removes file from _files dict and cleans up associated
        permissions and read-only status. Does not affect directories.

        Business context: Enables testing file cleanup scenarios without
        actual disk operations.

        Args:
            path: Absolute path to file to remove.

        Raises:
            FileNotFoundError: If path not in _files.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/old.json', '{}')
            >>> fs.remove('/data/old.json')
            >>> fs.exists('/data/old.json')
            False
        """
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        del self._files[path]
        self._modes.pop(path, None)
        self._read_only.discard(path)

    def iterdir(self, path: str) -> list[str]:
        """
        List contents of a mock directory.

        Returns paths of all files and directories that are direct
        children of the specified path.

        Business context: Used to iterate over files in a directory,
        such as when copying bundled agent files during init.

        Args:
            path: Absolute path to directory to list.

        Returns:
            List of absolute paths to files and directories in path.

        Raises:
            FileNotFoundError: If directory doesn't exist.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/a.json', '{}')
            >>> fs.iterdir('/data')
            ['/data/a.json']
        """
        if path not in self._dirs:
            raise FileNotFoundError(f"No such directory: {path}")

        # Normalize path
        path = path.rstrip("/")
        results = []

        # Find all files directly in this directory
        for file_path in self._files:
            parent = "/".join(file_path.rstrip("/").split("/")[:-1])
            if parent == path:
                results.append(file_path)

        # Find all directories directly in this directory
        for dir_path in self._dirs:
            if dir_path == path:
                continue
            parent = "/".join(dir_path.rstrip("/").split("/")[:-1])
            if parent == path:
                results.append(dir_path)

        return sorted(results)

    def copy_file(self, src: str, dst: str) -> None:
        """
        Copy a mock file from src to dst.

        Copies content from source to destination in the mock filesystem.

        Business context: Used to copy bundled agent files to the
        user's project directory during init.

        Args:
            src: Absolute path to source file.
            dst: Absolute path to destination file.

        Raises:
            FileNotFoundError: If source file doesn't exist.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/src/template.md', '# Template')
            >>> fs.copy_file('/src/template.md', '/dst/template.md')
            >>> fs.get_file('/dst/template.md')
            '# Template'
        """
        if src not in self._files:
            raise FileNotFoundError(f"No such file: {src}")
        self.write_text(dst, self._files[src])

    def rename(self, src: str, dst: str) -> None:
        """
        Rename/move a mock file.

        Moves file content from source to destination and removes source.

        Business context: Used to create backup files when config
        is corrupted.

        Args:
            src: Absolute path to source file.
            dst: Absolute path to destination.

        Raises:
            FileNotFoundError: If source doesn't exist.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/config.json', '{}')
            >>> fs.rename('/data/config.json', '/data/config.json.bak')
            >>> fs.exists('/data/config.json')
            False
            >>> fs.exists('/data/config.json.bak')
            True
        """
        if src not in self._files:
            raise FileNotFoundError(f"No such file: {src}")
        self._files[dst] = self._files[src]
        del self._files[src]
        # Move modes if present
        if src in self._modes:
            self._modes[dst] = self._modes[src]
            del self._modes[src]
        if src in self._read_only:
            self._read_only.discard(src)
            self._read_only.add(dst)

    # =========================================================================
    # TEST HELPERS
    # =========================================================================

    def get_file(self, path: str) -> str | None:
        """
        Get file content or None if not exists.

        Test helper for asserting file contents without raising exceptions.
        Unlike read_text(), returns None for missing files instead of raising.

        Business context: Simplifies test assertions by allowing direct
        content checks without try/except blocks.

        Args:
            path: Absolute path to file.

        Returns:
            File content string or None if file doesn't exist.
            Never raises exceptions.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.get_file('/nonexistent')
            None
            >>> fs.set_file('/data/test.json', '{}')
            >>> fs.get_file('/data/test.json')
            '{}'
        """
        return self._files.get(path)

    def set_file(self, path: str, content: str) -> None:
        """
        Set file content directly.

        Test helper for setting up initial file state. Delegates to
        write_text for consistent behavior including auto-creating
        parent directories.

        Business context: Simplifies test setup by providing a short
        method name for a common operation.

        Args:
            path: Absolute path to file.
            content: String content to store.

        Returns:
            None. Creates file as side effect.

        Raises:
            PermissionError: If path is marked read-only.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/sessions.json', '{"sessions": []}')
            >>> fs.exists('/data/sessions.json')
            True
        """
        self.write_text(path, content)

    def list_files(self) -> list[str]:
        """
        List all file paths in mock filesystem.

        Test helper for asserting which files exist. Returns sorted list
        for deterministic assertions. Takes no arguments since it returns
        all files in the mock filesystem.

        Business context: Enables tests to verify which files were created
        by storage operations.

        Args:
            None. Returns all files in the mock filesystem.

        Returns:
            Sorted list of all file paths. Empty list if no files.

        Raises:
            No exceptions raised. Always returns a list.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/a.json', '{}')
            >>> fs.set_file('/data/b.json', '{}')
            >>> fs.list_files()
            ['/data/a.json', '/data/b.json']
        """
        return sorted(self._files.keys())

    def list_dirs(self) -> list[str]:
        """
        List all directory paths in mock filesystem.

        Test helper for asserting which directories exist. Returns sorted
        list for deterministic assertions. Takes no arguments since it
        returns all directories in the mock filesystem.

        Business context: Enables tests to verify which directories were
        created by storage operations.

        Args:
            None. Returns all directories in the mock filesystem.

        Returns:
            Sorted list of all directory paths. Empty list if none.

        Raises:
            No exceptions raised. Always returns a list.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.makedirs('/data/backup', exist_ok=True)
            >>> fs.list_dirs()
            ['/data', '/data/backup']
        """
        return sorted(self._dirs)

    def clear(self) -> None:
        """
        Clear all files and directories from mock filesystem.

        Test helper for cleanup between tests. Resets all internal
        state to empty: _files, _dirs, _modes, and _read_only.
        Takes no arguments since it clears all state.

        Business context: Ensures test isolation by providing a clean
        slate for each test case. Call in test teardown or setup.

        Args:
            None. Clears all internal state.

        Returns:
            None. Clears all internal state as side effect.

        Raises:
            No exceptions raised. Always succeeds.

        Example:
            >>> fs = MockFileSystem()
            >>> fs.set_file('/data/test.json', '{}')
            >>> fs.clear()
            >>> fs.list_files()
            []
        """
        self._files.clear()
        self._dirs.clear()
        self._modes.clear()
        self._read_only.clear()


@pytest.fixture
def mock_fs() -> MockFileSystem:
    """
    Create a MockFileSystem for testing.

    Provides a fresh in-memory filesystem instance for each test,
    ensuring test isolation without actual disk I/O.

    Args:
        None. Pytest fixture takes no arguments.

    Returns:
        MockFileSystem: A fresh mock filesystem instance.

    Raises:
        No exceptions raised. Always returns a new instance.

    Example:
        >>> def test_storage(mock_fs):
        ...     mock_fs.set_file('/data/sessions.json', '{}')
        ...     # Test operations using mock_fs
    """
    return MockFileSystem()
