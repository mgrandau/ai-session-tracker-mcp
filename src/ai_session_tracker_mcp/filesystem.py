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

    All paths are strings (absolute paths expected).
    """

    def exists(self, path: str) -> bool:
        """Check if path exists (file or directory)."""
        ...

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        ...

    def is_dir(self, path: str) -> bool:
        """Check if path is a directory."""
        ...

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        """Create directory and parents. Raises OSError if exists and not exist_ok."""
        ...

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """Read file contents as text. Raises FileNotFoundError if missing."""
        ...

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> None:
        """Write text to file. Creates parent directories if needed."""
        ...

    def chmod(self, path: str, mode: int) -> None:
        """Change file permissions."""
        ...

    def remove(self, path: str) -> None:
        """Remove a file. Raises FileNotFoundError if missing."""
        ...


class RealFileSystem:
    """
    Real file system implementation using os and pathlib.

    This is the production implementation that performs actual I/O.
    """

    def exists(self, path: str) -> bool:
        """Check if path exists."""
        import os

        return os.path.exists(path)

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        import os

        return os.path.isfile(path)

    def is_dir(self, path: str) -> bool:
        """Check if path is a directory."""
        import os

        return os.path.isdir(path)

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        """Create directory and parents."""
        import os

        os.makedirs(path, exist_ok=exist_ok)

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """Read file contents."""
        with open(path, encoding=encoding) as f:
            return f.read()

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> None:
        """Write text to file."""
        with open(path, "w", encoding=encoding) as f:
            f.write(content)

    def chmod(self, path: str, mode: int) -> None:
        """Change file permissions."""
        import os

        os.chmod(path, mode)

    def remove(self, path: str) -> None:
        """Remove a file."""
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
        """Initialize empty mock file system."""
        self._files: dict[str, str] = {}
        self._dirs: set[str] = set()
        self._modes: dict[str, int] = {}
        self._read_only: set[str] = set()

    def exists(self, path: str) -> bool:
        """Check if path exists (file or directory)."""
        return path in self._files or path in self._dirs

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        return path in self._files

    def is_dir(self, path: str) -> bool:
        """Check if path is a directory."""
        return path in self._dirs

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        """Create directory and parents."""
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
        """Read file contents."""
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        return self._files[path]

    def write_text(self, path: str, content: str, _encoding: str = "utf-8") -> None:
        """Write text to file."""
        # Check if file is read-only
        if path in self._read_only:
            raise PermissionError(f"Permission denied: {path}")

        # Auto-create parent directories
        parent = "/".join(path.rstrip("/").split("/")[:-1])
        if parent and parent not in self._dirs:
            self.makedirs(parent, exist_ok=True)

        self._files[path] = content

    def chmod(self, path: str, mode: int) -> None:
        """Change file permissions."""
        if path not in self._files and path not in self._dirs:
            raise FileNotFoundError(f"No such file or directory: {path}")

        self._modes[path] = mode

        # Simulate read-only (mode 0o444 or less)
        if mode & 0o200 == 0:  # No write permission
            self._read_only.add(path)
        else:
            self._read_only.discard(path)

    def remove(self, path: str) -> None:
        """Remove a file."""
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        del self._files[path]
        self._modes.pop(path, None)
        self._read_only.discard(path)

    # =========================================================================
    # TEST HELPERS
    # =========================================================================

    def get_file(self, path: str) -> str | None:
        """Get file content or None if not exists. For test assertions."""
        return self._files.get(path)

    def set_file(self, path: str, content: str) -> None:
        """Set file content directly. For test setup."""
        self.write_text(path, content)

    def list_files(self) -> list[str]:
        """List all file paths. For test assertions."""
        return sorted(self._files.keys())

    def list_dirs(self) -> list[str]:
        """List all directory paths. For test assertions."""
        return sorted(self._dirs)

    def clear(self) -> None:
        """Clear all files and directories. For test cleanup."""
        self._files.clear()
        self._dirs.clear()
        self._modes.clear()
        self._read_only.clear()
