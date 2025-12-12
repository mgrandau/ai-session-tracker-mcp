"""
FileSystem abstraction for AI Session Tracker.

PURPOSE: Injectable file system interface for testability.
AI CONTEXT: Allows mocking file operations in unit tests without temp directories.

DESIGN:
- Protocol defines the interface
- RealFileSystem uses actual os/pathlib operations
- MockFileSystem stores data in memory for tests

USAGE:
    # Production
    fs = RealFileSystem()
    storage = StorageManager(filesystem=fs)

    # Tests
    fs = MockFileSystem()
    storage = StorageManager(filesystem=fs)
    # No temp directories needed!
"""

from __future__ import annotations

from typing import Protocol


class FileSystem(Protocol):
    """
    Protocol for file system operations.

    Defines the interface for file system operations used throughout the
    application. All paths are strings (absolute paths expected). Implementations
    include RealFileSystem for production and MockFileSystem for testing.

    Business context: This abstraction enables dependency injection for
    testability - tests can use MockFileSystem to avoid actual I/O while
    production uses RealFileSystem with real os/pathlib operations.
    """

    def exists(self, path: str) -> bool:
        """
        Check if path exists (file or directory).

        Business context: Used by storage layer to check for existing
        session files before loading. Abstract method - implementations
        use os.path.exists() or dict lookup.

        Args:
            path: Absolute path to check for existence.

        Returns:
            True if the path exists as either a file or directory,
            False otherwise. Never raises.

        Example:
            >>> fs.exists('/data/sessions.json')
            True
        """
        ...

    def is_file(self, path: str) -> bool:
        """
        Check if path is a regular file.

        Business context: Storage layer uses this to verify path type
        before reading content as JSON. Abstract method - implementations
        use os.path.isfile() or dict membership.

        Args:
            path: Absolute path to check.

        Returns:
            True if path exists and is a regular file, False if
            it doesn't exist or is a directory. Never raises.

        Example:
            >>> fs.is_file('/data/sessions.json')
            True
        """
        ...

    def is_dir(self, path: str) -> bool:
        """
        Check if path is a directory.

        Business context: Storage layer uses this to check data
        directory existence before creating session files. Abstract
        method - implementations use os.path.isdir() or set membership.

        Args:
            path: Absolute path to check.

        Returns:
            True if path exists and is a directory, False if
            it doesn't exist or is a file. Never raises.

        Example:
            >>> fs.is_dir('/data')
            True
        """
        ...

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        """
        Create directory and all parent directories.

        Business context: Storage layer uses this to ensure the data
        directory exists before writing session files. Equivalent to
        shell `mkdir -p` command.

        Args:
            path: Absolute path of directory to create.
            exist_ok: If True, don't raise if directory exists.
                If False, raise OSError when directory exists.

        Returns:
            None. Creates directory as side effect.

        Raises:
            OSError: If directory exists and exist_ok is False.

        Example:
            >>> fs.makedirs('/data/backup', exist_ok=True)
        """
        ...

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """
        Read file contents as text.

        Args:
            path: Absolute path to file to read.
            encoding: Text encoding (default utf-8).

        Returns:
            File contents as a string.

        Raises:
            FileNotFoundError: If file doesn't exist.

        Example:
            >>> content = fs.read_text('/data/sessions.json')
        """
        ...

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> None:
        """
        Write text to file.

        Creates parent directories if needed. Overwrites existing content.

        Business context: Used by storage layer to persist session data
        to JSON files. Implementations may auto-create parent directories.

        Args:
            path: Absolute path to file to write.
            content: String content to write to file.
            encoding: Text encoding (default utf-8).

        Returns:
            None. Creates/updates file as side effect.

        Raises:
            PermissionError: If file is read-only.

        Example:
            >>> fs.write_text('/data/sessions.json', '{}')

        Business context: Can be used to set restrictive permissions
        on sensitive configuration files. Mock implementation simulates
        read-only behavior.

        Args:
            path: Absolute path to file or directory.
            mode: Permission mode as octal integer (e.g., 0o644).

        Returns:
            None. Modifies permissions as side effect.

        Raises:
            FileNotFoundError: If path doesn't exist.

        Example:
            >>> fs.chmod('/data/config.json', 0o600)
        """
        ...

    def remove(self, path: str) -> None:
        """
        Remove a file.

        Business context: May be used for cleaning up old or temporary
        session data files. Does not work on directories.

        Args:
            path: Absolute path to file to remove.

        Returns:
            None. Deletes file as side effect.

        Raises:
            FileNotFoundError: If file doesn't exist.

        Example:
            >>> fs.remove('/data/old_sessions.json')
        """
        ...


class RealFileSystem:
    """
    Real file system implementation using os and pathlib.

    This is the production implementation that performs actual I/O.
    Uses standard library os module for all operations.

    Business context: Used in production to store session data to
    disk. Each method delegates directly to the corresponding os
    or built-in function.
    """

    def exists(self, path: str) -> bool:
        """
        Check if path exists on the real filesystem.

        Delegates to os.path.exists() to check for file or directory
        existence on the actual filesystem.

        Business context: Used in storage layer to check for existing
        session data files before attempting to load them.

        Args:
            path: Absolute path to check.

        Returns:
            True if path exists as file or directory.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.exists('/tmp/sessions.json')
            False
        """
        import os

        return os.path.exists(path)

    def is_file(self, path: str) -> bool:
        """
        Check if path is a regular file on disk.

        Delegates to os.path.isfile() to verify the path is an
        existing regular file, not a directory or special file.

        Business context: Storage layer uses this to verify path type
        before reading content as text.

        Args:
            path: Absolute path to check.

        Returns:
            True if path exists and is a regular file.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.is_file('/etc/passwd')
            True
        """
        import os

        return os.path.isfile(path)

    def is_dir(self, path: str) -> bool:
        """
        Check if path is a directory on disk.

        Delegates to os.path.isdir() to verify the path is an
        existing directory.

        Business context: Storage layer uses this to check data
        directory existence before creating session files.

        Args:
            path: Absolute path to check.

        Returns:
            True if path exists and is a directory.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.is_dir('/tmp')
            True
        """
        import os

        return os.path.isdir(path)

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        """
        Create directory and parent directories on disk.

        Delegates to os.makedirs() to recursively create all directories
        in the path. Like `mkdir -p` in shell.

        Business context: Storage layer uses this to ensure the data
        directory exists before writing session files.

        Args:
            path: Absolute path of directory to create.
            exist_ok: If True, don't raise if directory exists.

        Raises:
            OSError: If directory exists and exist_ok is False.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.makedirs('/tmp/data/sessions', exist_ok=True)
        """
        import os

        os.makedirs(path, exist_ok=exist_ok)

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """
        Read file contents from disk as text.

        Opens file in text mode with specified encoding and returns
        the complete contents as a string.

        Business context: Used by storage layer to load JSON session
        data from disk.

        Args:
            path: Absolute path to file to read.
            encoding: Text encoding (default utf-8).

        Returns:
            File contents as a string.

        Raises:
            FileNotFoundError: If file doesn't exist.

        Example:
            >>> fs = RealFileSystem()
            >>> content = fs.read_text('/tmp/sessions.json')
        """
        with open(path, encoding=encoding) as f:
            return f.read()

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> None:
        """
        Write text content to file on disk.

        Opens file in write mode with specified encoding and writes
        the complete content. Overwrites existing file content.

        Business context: Used by storage layer to persist session
        data to JSON files on disk.

        Args:
            path: Absolute path to file to write.
            content: String content to write.
            encoding: Text encoding (default utf-8).

        Raises:
            PermissionError: If file is read-only.
            OSError: If parent directory doesn't exist.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.write_text('/tmp/sessions.json', '{"sessions": []}')
        """
        with open(path, "w", encoding=encoding) as f:
            f.write(content)

    def chmod(self, path: str, mode: int) -> None:
        """
        Change file permissions on disk.

        Delegates to os.chmod() to modify the Unix permission bits
        on a file or directory.

        Business context: Can be used to set restrictive permissions
        on sensitive configuration files.

        Args:
            path: Absolute path to file or directory.
            mode: Permission mode as octal integer (e.g., 0o644).

        Raises:
            FileNotFoundError: If path doesn't exist.
            PermissionError: If caller lacks permission to chmod.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.chmod('/tmp/config.json', 0o600)
        """
        import os

        os.chmod(path, mode)

    def remove(self, path: str) -> None:
        """
        Remove a file from disk.

        Delegates to os.remove() to delete a file. Does not work on
        directories (use shutil.rmtree for that).

        Business context: May be used for cleaning up old or temporary
        session data files.

        Args:
            path: Absolute path to file to remove.

        Raises:
            FileNotFoundError: If file doesn't exist.
            IsADirectoryError: If path is a directory.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.remove('/tmp/old_sessions.json')
        """
        import os

        os.remove(path)


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

        Returns:
            None. Initializes internal state.

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

        Returns:
            Sorted list of all file paths. Empty list if no files.
            Never raises exceptions.

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

        Returns:
            Sorted list of all directory paths. Empty list if none.
            Never raises exceptions.

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

        Returns:
            None. Clears all internal state as side effect.
            Never raises exceptions.

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
