"""Tests for filesystem module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add tests directory to path for conftest imports
sys.path.insert(0, str(Path(__file__).parent))

from ai_session_tracker_mcp.filesystem import RealFileSystem
from conftest import MockFileSystem


class TestMockFileSystemBasics:
    """Tests for MockFileSystem basic operations."""

    def test_initial_state_empty(self) -> None:
        """Verifies new MockFileSystem has no files or directories.

        Tests that the initial state is completely empty for isolation
        between tests.

        Business context:
        Test isolation requires clean slate. Each test starts fresh
        without artifacts from previous tests.

        Arrangement:
        Create new MockFileSystem instance.

        Action:
        Query list_files() and list_dirs().

        Assertion Strategy:
        Validates both return empty lists.

        Testing Principle:
        Validates initial state invariant.
        """
        fs = MockFileSystem()
        assert fs.list_files() == []
        assert fs.list_dirs() == []

    def test_exists_returns_false_for_nonexistent(self) -> None:
        """Verifies exists returns False for nonexistent paths.

        Tests that querying non-existent path returns False rather than
        raising an exception.

        Business context:
        Existence checks are common for conditional logic. Should be
        safe to call without try/except.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call exists() with path that was never created.

        Assertion Strategy:
        Validates return value is False.

        Testing Principle:
        Validates safe negative query.
        """
        fs = MockFileSystem()
        assert fs.exists("/nonexistent") is False

    def test_is_file_returns_false_for_nonexistent(self) -> None:
        """Verifies is_file returns False for nonexistent paths.

        Tests that file type check returns False for missing paths
        rather than raising an exception.

        Business context:
        File type checks are common before read operations. Should
        return False for missing rather than error.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call is_file() with path that was never created.

        Assertion Strategy:
        Validates return value is False.

        Testing Principle:
        Validates safe negative type check.
        """
        fs = MockFileSystem()
        assert fs.is_file("/nonexistent") is False

    def test_is_dir_returns_false_for_nonexistent(self) -> None:
        """Verifies is_dir returns False for nonexistent paths.

        Tests that directory type check returns False for missing paths
        rather than raising an exception.

        Business context:
        Directory checks are common before listing contents. Should
        return False for missing rather than error.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call is_dir() with path that was never created.

        Assertion Strategy:
        Validates return value is False.

        Testing Principle:
        Validates safe negative type check.
        """
        fs = MockFileSystem()
        assert fs.is_dir("/nonexistent") is False


class TestMockFileSystemDirectories:
    """Tests for MockFileSystem directory operations."""

    def test_makedirs_creates_directory(self) -> None:
        """Verifies makedirs creates directory at specified path.

        Tests basic directory creation functionality.

        Business context:
        Storage directories must exist before writing files. makedirs
        ensures path hierarchy exists.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call makedirs() with nested path.

        Assertion Strategy:
        Validates is_dir() returns True for created path.

        Testing Principle:
        Validates basic directory creation.
        """
        fs = MockFileSystem()
        fs.makedirs("/test/path")
        assert fs.is_dir("/test/path")

    def test_makedirs_creates_parents(self) -> None:
        """Verifies makedirs creates all parent directories.

        Tests that deeply nested paths create entire hierarchy.

        Business context:
        Deep paths require all ancestors to exist. makedirs behaves
        like 'mkdir -p' creating full tree.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call makedirs() with deeply nested path.

        Assertion Strategy:
        Validates each ancestor directory exists.

        Testing Principle:
        Validates recursive directory creation.
        """
        fs = MockFileSystem()
        fs.makedirs("/a/b/c/d")
        assert fs.is_dir("/a")
        assert fs.is_dir("/a/b")
        assert fs.is_dir("/a/b/c")
        assert fs.is_dir("/a/b/c/d")

    def test_makedirs_exist_ok_true(self) -> None:
        """Verifies makedirs with exist_ok=True doesn't raise for existing.

        Tests idempotent directory creation mode.

        Business context:
        Startup code often ensures directories exist. exist_ok=True
        allows safe re-runs without error handling.

        Arrangement:
        Create directory first.

        Action:
        Call makedirs() again with exist_ok=True.

        Assertion Strategy:
        Validates no exception raised and directory still exists.

        Testing Principle:
        Validates idempotent operation mode.
        """
        fs = MockFileSystem()
        fs.makedirs("/test")
        fs.makedirs("/test", exist_ok=True)  # Should not raise
        assert fs.is_dir("/test")

    def test_makedirs_exist_ok_false_raises(self) -> None:
        """Verifies makedirs with exist_ok=False raises for existing.

        Tests strict directory creation mode.

        Business context:
        Some workflows need to detect existing directories as errors.
        exist_ok=False enforces uniqueness.

        Arrangement:
        Create directory first.

        Action:
        Call makedirs() again with exist_ok=False.

        Assertion Strategy:
        Validates OSError is raised.

        Testing Principle:
        Validates error on conflict.
        """
        fs = MockFileSystem()
        fs.makedirs("/test")
        with pytest.raises(OSError):
            fs.makedirs("/test", exist_ok=False)

    def test_makedirs_raises_if_path_is_file(self) -> None:
        """Verifies makedirs raises if path is already a file.

        Tests that files cannot be overwritten with directories.

        Business context:
        Files and directories are mutually exclusive. Attempting to
        make a directory over a file is an error.

        Arrangement:
        Create file at path.

        Action:
        Call makedirs() with same path.

        Assertion Strategy:
        Validates OSError is raised.

        Testing Principle:
        Validates type conflict detection.
        """
        fs = MockFileSystem()
        fs.write_text("/test", "content")
        with pytest.raises(OSError):
            fs.makedirs("/test")

    def test_exists_returns_true_for_dir(self) -> None:
        """Verifies exists returns True for directories.

        Tests that exists() recognizes directories as existing.

        Business context:
        exists() is a general path check. Should return True for
        both files and directories.

        Arrangement:
        Create directory.

        Action:
        Call exists() with directory path.

        Assertion Strategy:
        Validates return value is True.

        Testing Principle:
        Validates exists includes directories.
        """
        fs = MockFileSystem()
        fs.makedirs("/test")
        assert fs.exists("/test") is True


class TestMockFileSystemFiles:
    """Tests for MockFileSystem file operations."""

    def test_write_text_creates_file(self) -> None:
        """Verifies write_text creates file with content.

        Tests basic file creation functionality.

        Business context:
        Persisting session data requires file writes. write_text is
        the primary method for storing JSON data.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call write_text() with path and content.

        Assertion Strategy:
        Validates file exists and content matches.

        Testing Principle:
        Validates basic file creation.
        """
        fs = MockFileSystem()
        fs.write_text("/test.txt", "hello")
        assert fs.is_file("/test.txt")
        assert fs.read_text("/test.txt") == "hello"

    def test_write_text_creates_parent_dirs(self) -> None:
        """Verifies write_text creates parent directories.

        Tests that writing to nested path auto-creates directory tree.

        Business context:
        Storage paths may be deeply nested. Automatic parent creation
        simplifies write operations.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call write_text() with deeply nested path.

        Assertion Strategy:
        Validates parent directory exists and file is created.

        Testing Principle:
        Validates automatic parent directory creation.
        """
        fs = MockFileSystem()
        fs.write_text("/a/b/c/test.txt", "content")
        assert fs.is_dir("/a/b/c")
        assert fs.is_file("/a/b/c/test.txt")

    def test_write_text_overwrites_existing(self) -> None:
        """Verifies write_text overwrites existing file.

        Tests that subsequent writes replace file content entirely.

        Business context:
        Updating stored data requires overwrite behavior. Sessions
        are updated in place after modifications.

        Arrangement:
        Create file with initial content.

        Action:
        Call write_text() again with different content.

        Assertion Strategy:
        Validates content is replaced, not appended.

        Testing Principle:
        Validates overwrite semantics.
        """
        fs = MockFileSystem()
        fs.write_text("/test.txt", "first")
        fs.write_text("/test.txt", "second")
        assert fs.read_text("/test.txt") == "second"

    def test_read_text_returns_content(self) -> None:
        """Verifies read_text returns file content.

        Tests basic file reading functionality.

        Business context:
        Loading session data requires file reads. read_text is the
        primary method for retrieving stored JSON.

        Arrangement:
        Create file with known content.

        Action:
        Call read_text() with file path.

        Assertion Strategy:
        Validates returned content matches original.

        Testing Principle:
        Validates basic file reading.
        """
        fs = MockFileSystem()
        fs.write_text("/test.txt", "hello world")
        assert fs.read_text("/test.txt") == "hello world"

    def test_read_text_raises_for_nonexistent(self) -> None:
        """Verifies read_text raises FileNotFoundError for missing file.

        Tests error behavior for reading non-existent files.

        Business context:
        Missing files indicate data corruption or initialization error.
        Exception enables proper error handling.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call read_text() with path that doesn't exist.

        Assertion Strategy:
        Validates FileNotFoundError is raised.

        Testing Principle:
        Validates error handling for missing data.
        """
        fs = MockFileSystem()
        with pytest.raises(FileNotFoundError):
            fs.read_text("/nonexistent")

    def test_exists_returns_true_for_file(self) -> None:
        """Verifies exists returns True for files.

        Tests that exists() recognizes files as existing.

        Business context:
        exists() is a general path check. Should return True for
        both files and directories.

        Arrangement:
        Create file with content.

        Action:
        Call exists() with file path.

        Assertion Strategy:
        Validates return value is True.

        Testing Principle:
        Validates exists includes files.
        """
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        assert fs.exists("/test.txt") is True

    def test_remove_deletes_file(self) -> None:
        """Verifies remove deletes a file.

        Tests file deletion functionality.

        Business context:
        Cleanup operations may need to delete files. remove enables
        test cleanup and data management.

        Arrangement:
        Create file with content.

        Action:
        Call remove() with file path.

        Assertion Strategy:
        Validates file no longer exists.

        Testing Principle:
        Validates file deletion.
        """
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        fs.remove("/test.txt")
        assert fs.exists("/test.txt") is False

    def test_remove_raises_for_nonexistent(self) -> None:
        """Verifies remove raises FileNotFoundError for missing file.

        Tests error behavior for removing non-existent files.

        Business context:
        Removing non-existent file indicates logic error. Exception
        helps catch programming mistakes.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call remove() with path that doesn't exist.

        Assertion Strategy:
        Validates FileNotFoundError is raised.

        Testing Principle:
        Validates error handling for missing path.
        """
        fs = MockFileSystem()
        with pytest.raises(FileNotFoundError):
            fs.remove("/nonexistent")


class TestMockFileSystemPermissions:
    """Tests for MockFileSystem permission simulation."""

    def test_chmod_sets_mode(self) -> None:
        """Verifies chmod sets file mode.

        Tests that permission mode can be set on files.

        Business context:
        Permission simulation enables testing error handling code
        for read-only files without actual filesystem changes.

        Arrangement:
        Create file with content.

        Action:
        Call chmod() with mode 0o644.

        Assertion Strategy:
        Method completes without error (mode is stored internally).

        Testing Principle:
        Validates permission setting capability.
        """
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        fs.chmod("/test.txt", 0o644)
        # Mode is stored but we mainly test read-only behavior

    def test_chmod_read_only_blocks_write(self) -> None:
        """Verifies chmod to read-only blocks write_text.

        Tests that read-only mode prevents file modifications.

        Business context:
        Simulating read-only files enables testing error handling
        for permission denied scenarios.

        Arrangement:
        Create file and set to read-only (0o444).

        Action:
        Attempt to write_text() to read-only file.

        Assertion Strategy:
        Validates PermissionError is raised.

        Testing Principle:
        Validates permission enforcement.
        """
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        fs.chmod("/test.txt", 0o444)  # Read-only
        with pytest.raises(PermissionError):
            fs.write_text("/test.txt", "new content")

    def test_chmod_restore_write_allows_write(self) -> None:
        """Verifies chmod to writable restores write_text capability.

        Tests that permissions can be changed back to allow writes.

        Business context:
        Permission changes should be reversible. Tests that restoring
        write permission enables file modification.

        Arrangement:
        Create file, set read-only, then restore writable.

        Action:
        Call write_text() after restoring permissions.

        Assertion Strategy:
        Validates write succeeds and content is updated.

        Testing Principle:
        Validates permission restoration.
        """
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        fs.chmod("/test.txt", 0o444)
        fs.chmod("/test.txt", 0o644)  # Restore write
        fs.write_text("/test.txt", "new content")  # Should not raise
        assert fs.read_text("/test.txt") == "new content"

    def test_chmod_raises_for_nonexistent(self) -> None:
        """Verifies chmod raises FileNotFoundError for missing path.

        Tests error behavior when setting permissions on non-existent path.

        Business context:
        Changing permissions on missing file is an error. Exception
        helps catch programming mistakes.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call chmod() with path that doesn't exist.

        Assertion Strategy:
        Validates FileNotFoundError is raised.

        Testing Principle:
        Validates error handling for missing path.
        """
        fs = MockFileSystem()
        with pytest.raises(FileNotFoundError):
            fs.chmod("/nonexistent", 0o644)


class TestMockFileSystemTestHelpers:
    """Tests for MockFileSystem test helper methods."""

    def test_get_file_returns_content(self) -> None:
        """Verifies get_file returns file content.

        Tests the test helper method for retrieving file content.

        Business context:
        Test helpers simplify assertions. get_file provides direct
        access without exception handling.

        Arrangement:
        Create file with known content.

        Action:
        Call get_file() with file path.

        Assertion Strategy:
        Validates returned content matches original.

        Testing Principle:
        Validates test helper functionality.
        """
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        assert fs.get_file("/test.txt") == "content"

    def test_get_file_returns_none_for_missing(self) -> None:
        """Verifies get_file returns None for missing file.

        Tests that get_file returns None instead of raising exception.

        Business context:
        Unlike read_text, get_file is for test assertions. None
        simplifies checking if file was not created.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call get_file() with non-existent path.

        Assertion Strategy:
        Validates return value is None.

        Testing Principle:
        Validates safe negative lookup.
        """
        fs = MockFileSystem()
        assert fs.get_file("/nonexistent") is None

    def test_set_file_creates_file(self) -> None:
        """Verifies set_file creates file with content.

        Tests the test helper method for creating files.

        Business context:
        Test setup often requires pre-existing files. set_file
        provides direct creation for test arrangement.

        Arrangement:
        Create empty MockFileSystem.

        Action:
        Call set_file() to create file.

        Assertion Strategy:
        Validates file is readable with expected content.

        Testing Principle:
        Validates test helper functionality.
        """
        fs = MockFileSystem()
        fs.set_file("/test.txt", "content")
        assert fs.read_text("/test.txt") == "content"

    def test_list_files_returns_all_files(self) -> None:
        """Verifies list_files returns all file paths.

        Tests the test helper method for listing all files.

        Business context:
        Test assertions may need to verify all files created.
        list_files enables comprehensive state inspection.

        Arrangement:
        Create multiple files at different paths.

        Action:
        Call list_files() to get all paths.

        Assertion Strategy:
        Validates all created file paths are in result.

        Testing Principle:
        Validates complete file enumeration.
        """
        fs = MockFileSystem()
        fs.write_text("/a.txt", "a")
        fs.write_text("/b/c.txt", "c")
        files = fs.list_files()
        assert "/a.txt" in files
        assert "/b/c.txt" in files

    def test_list_dirs_returns_all_dirs(self) -> None:
        """Verifies list_dirs returns all directory paths.

        Tests the test helper method for listing all directories.

        Business context:
        Test assertions may need to verify directory structure.
        list_dirs enables comprehensive state inspection.

        Arrangement:
        Create nested directory structure.

        Action:
        Call list_dirs() to get all paths.

        Assertion Strategy:
        Validates all created directory paths are in result.

        Testing Principle:
        Validates complete directory enumeration.
        """
        fs = MockFileSystem()
        fs.makedirs("/a/b/c")
        dirs = fs.list_dirs()
        assert "/a" in dirs
        assert "/a/b" in dirs
        assert "/a/b/c" in dirs

    def test_clear_removes_everything(self) -> None:
        """Verifies clear removes all files and directories.

        Tests the test helper method for resetting filesystem state.

        Business context:
        Tests may need to reset to initial state. clear enables
        mid-test cleanup without creating new instance.

        Arrangement:
        Create directories and files.

        Action:
        Call clear() to reset state.

        Assertion Strategy:
        Validates both files and dirs are empty.

        Testing Principle:
        Validates complete state reset.
        """
        fs = MockFileSystem()
        fs.makedirs("/test")
        fs.write_text("/test/file.txt", "content")
        fs.clear()
        assert fs.list_files() == []
        assert fs.list_dirs() == []


class TestRealFileSystem:
    """Tests for RealFileSystem.

    Note: These tests perform actual I/O so use temp files.
    """

    def test_implements_protocol_methods(self) -> None:
        """Verifies RealFileSystem has all protocol methods.

        Tests that RealFileSystem implements the FileSystem protocol
        interface for substitutability with MockFileSystem.

        Business context:
        Dependency injection requires consistent interfaces. Real and
        mock implementations must be interchangeable.

        Arrangement:
        Create RealFileSystem instance.

        Action:
        Check for presence of all protocol methods.

        Assertion Strategy:
        Validates each required method exists via hasattr.

        Testing Principle:
        Validates protocol compliance.
        """
        fs = RealFileSystem()
        assert hasattr(fs, "exists")
        assert hasattr(fs, "is_file")
        assert hasattr(fs, "is_dir")
        assert hasattr(fs, "makedirs")
        assert hasattr(fs, "read_text")
        assert hasattr(fs, "write_text")
        assert hasattr(fs, "chmod")
        assert hasattr(fs, "remove")

    def test_exists_for_current_dir(self) -> None:
        """Verifies exists returns True for root directory.

        Tests basic RealFileSystem functionality with known path.

        Business context:
        RealFileSystem wraps actual filesystem operations. Basic
        sanity check that it works on known good path.

        Arrangement:
        Create RealFileSystem instance.

        Action:
        Call exists() with root path.

        Assertion Strategy:
        Validates return value is True.

        Testing Principle:
        Validates basic real filesystem operation.
        """
        fs = RealFileSystem()
        assert fs.exists("/") is True

    def test_is_dir_for_current_dir(self) -> None:
        """Verifies is_dir returns True for root directory.

        Tests that is_dir correctly identifies directories.

        Business context:
        Directory type check is essential for storage operations.
        Root directory is guaranteed to exist and be a directory.

        Arrangement:
        Create RealFileSystem instance.

        Action:
        Call is_dir() with root path.

        Assertion Strategy:
        Validates return value is True.

        Testing Principle:
        Validates directory type detection.
        """
        fs = RealFileSystem()
        assert fs.is_dir("/") is True

    def test_is_file_for_nonexistent(self) -> None:
        """Verifies is_file returns False for nonexistent path.

        Tests that is_file returns False rather than raising for
        non-existent paths.

        Business context:
        File type checks must be safe for unknown paths. Returns
        False for missing rather than throwing exception.

        Arrangement:
        Create RealFileSystem instance.

        Action:
        Call is_file() with path unlikely to exist.

        Assertion Strategy:
        Validates return value is False.

        Testing Principle:
        Validates safe negative type check.
        """
        fs = RealFileSystem()
        assert fs.is_file("/nonexistent_file_12345.txt") is False

    def test_read_text_with_temp_file(self, tmp_path: object) -> None:
        """Verifies read_text reads actual file content.

        Tests that RealFileSystem can read text from a real file.

        Business context:
        Reading JSON session files is core functionality.
        """
        from pathlib import Path

        p = Path(str(tmp_path)) / "test.txt"
        p.write_text("Hello, World!")

        fs = RealFileSystem()
        content = fs.read_text(str(p))
        assert content == "Hello, World!"

    def test_write_text_creates_file(self, tmp_path: object) -> None:
        """Verifies write_text creates and writes to actual file.

        Tests that RealFileSystem can write text to a real file.

        Business context:
        Writing JSON session files is core functionality.
        """
        from pathlib import Path

        p = Path(str(tmp_path)) / "test.txt"

        fs = RealFileSystem()
        fs.write_text(str(p), "Test content")

        assert p.read_text() == "Test content"

    def test_chmod_changes_permissions(self, tmp_path: object) -> None:
        """Verifies chmod changes file permissions.

        Tests that RealFileSystem can modify file permissions.

        Business context:
        Permission management for secure storage files.
        """
        import os
        from pathlib import Path

        p = Path(str(tmp_path)) / "test.txt"
        p.write_text("test")

        fs = RealFileSystem()
        fs.chmod(str(p), 0o600)

        # Verify permissions changed (on Unix-like systems)
        mode = os.stat(str(p)).st_mode & 0o777
        assert mode == 0o600

    def test_remove_deletes_file(self, tmp_path: object) -> None:
        """Verifies remove deletes actual file.

        Tests that RealFileSystem can delete files.

        Business context:
        Cleaning up temporary or old session files.
        """
        from pathlib import Path

        p = Path(str(tmp_path)) / "test.txt"
        p.write_text("test")
        assert p.exists()

        fs = RealFileSystem()
        fs.remove(str(p))

        assert not p.exists()
