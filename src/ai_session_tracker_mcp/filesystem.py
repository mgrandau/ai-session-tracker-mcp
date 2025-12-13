"""
FileSystem abstraction for AI Session Tracker.

PURPOSE: Injectable file system interface for testability.
AI CONTEXT: Allows mocking file operations in unit tests without temp directories.

DESIGN:
- Protocol defines the interface
- RealFileSystem uses actual os/pathlib operations
- MockFileSystem in tests/conftest.py stores data in memory for tests

USAGE:
    # Production
    fs = RealFileSystem()
    storage = StorageManager(filesystem=fs)

    # Tests (MockFileSystem from conftest.py)
    storage = StorageManager(filesystem=mock_fs)  # pytest fixture
"""

from __future__ import annotations

import os
import shutil
from typing import Protocol

__all__ = ["FileSystem", "RealFileSystem"]


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
        """
        ...

    def chmod(self, path: str, mode: int) -> None:
        """
        Change file permissions.

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

    def iterdir(self, path: str) -> list[str]:
        """
        List contents of a directory.

        Business context: Used to iterate over files in a directory,
        such as when copying bundled agent files during init.

        Args:
            path: Absolute path to directory to list.

        Returns:
            List of absolute paths to files and directories in path.

        Raises:
            FileNotFoundError: If directory doesn't exist.

        Example:
            >>> fs.iterdir('/data')
            ['/data/sessions.json', '/data/issues.json']
        """
        ...

    def copy_file(self, src: str, dst: str) -> None:
        """
        Copy a file from src to dst.

        Business context: Used to copy bundled agent files to the
        user's project directory during init.

        Args:
            src: Absolute path to source file.
            dst: Absolute path to destination file.

        Returns:
            None. Creates destination file as side effect.

        Raises:
            FileNotFoundError: If source file doesn't exist.

        Example:
            >>> fs.copy_file('/pkg/template.md', '/project/.github/template.md')
        """
        ...

    def rename(self, src: str, dst: str) -> None:
        """
        Rename/move a file.

        Business context: Used to create backup files when config
        is corrupted.

        Args:
            src: Absolute path to source file.
            dst: Absolute path to destination.

        Returns:
            None. Moves file as side effect.

        Raises:
            FileNotFoundError: If source doesn't exist.

        Example:
            >>> fs.rename('/data/config.json', '/data/config.json.bak')
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

    def exists(self, path: str) -> bool:  # pragma: no cover
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
        return os.path.exists(path)

    def is_file(self, path: str) -> bool:  # pragma: no cover
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
        return os.path.isfile(path)

    def is_dir(self, path: str) -> bool:  # pragma: no cover
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
        return os.path.isdir(path)

    def makedirs(self, path: str, exist_ok: bool = False) -> None:  # pragma: no cover
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
        os.makedirs(path, exist_ok=exist_ok)

    def read_text(self, path: str, encoding: str = "utf-8") -> str:  # pragma: no cover
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

    def write_text(
        self, path: str, content: str, encoding: str = "utf-8"
    ) -> None:  # pragma: no cover
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

    def chmod(self, path: str, mode: int) -> None:  # pragma: no cover
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
        os.chmod(path, mode)

    def remove(self, path: str) -> None:  # pragma: no cover
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
        os.remove(path)

    def iterdir(self, path: str) -> list[str]:  # pragma: no cover
        """
        List contents of a directory on disk.

        Returns absolute paths to all files and directories in the
        specified directory.

        Args:
            path: Absolute path to directory to list.

        Returns:
            List of absolute paths.

        Raises:
            FileNotFoundError: If directory doesn't exist.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.iterdir('/tmp/data')
            ['/tmp/data/sessions.json']
        """
        return [os.path.join(path, name) for name in os.listdir(path)]

    def copy_file(self, src: str, dst: str) -> None:  # pragma: no cover
        """
        Copy a file from src to dst.

        Uses shutil.copy2 to preserve file metadata including modification
        times and permissions.

        Business context: Used by the setup command to copy agent files
        from the installed package to user projects, preserving file
        attributes for proper git tracking.

        Args:
            src: Absolute path to source file.
            dst: Absolute path to destination file.

        Returns:
            None. File is copied to destination.

        Raises:
            FileNotFoundError: If source file doesn't exist.
            PermissionError: If destination cannot be written.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.copy_file('/pkg/template.md', '/project/template.md')
        """
        shutil.copy2(src, dst)

    def rename(self, src: str, dst: str) -> None:  # pragma: no cover
        """
        Rename or move a file on disk.

        Performs an atomic rename operation when source and destination
        are on the same filesystem.

        Business context: Used by the setup command to create backup copies
        of corrupted config files before replacing them, ensuring users
        can recover their original configurations.

        Args:
            src: Absolute path to source file.
            dst: Absolute path to destination.

        Returns:
            None. File is renamed/moved to destination.

        Raises:
            FileNotFoundError: If source doesn't exist.
            PermissionError: If operation not permitted.

        Example:
            >>> fs = RealFileSystem()
            >>> fs.rename('/tmp/config.json', '/tmp/config.json.bak')
        """
        os.rename(src, dst)
