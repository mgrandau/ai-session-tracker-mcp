"""Tests for filesystem module."""

from __future__ import annotations

import pytest

from ai_session_tracker_mcp.filesystem import MockFileSystem, RealFileSystem


class TestMockFileSystemBasics:
    """Tests for MockFileSystem basic operations."""

    def test_initial_state_empty(self) -> None:
        """New MockFileSystem has no files or directories."""
        fs = MockFileSystem()
        assert fs.list_files() == []
        assert fs.list_dirs() == []

    def test_exists_returns_false_for_nonexistent(self) -> None:
        """exists returns False for nonexistent paths."""
        fs = MockFileSystem()
        assert fs.exists("/nonexistent") is False

    def test_is_file_returns_false_for_nonexistent(self) -> None:
        """is_file returns False for nonexistent paths."""
        fs = MockFileSystem()
        assert fs.is_file("/nonexistent") is False

    def test_is_dir_returns_false_for_nonexistent(self) -> None:
        """is_dir returns False for nonexistent paths."""
        fs = MockFileSystem()
        assert fs.is_dir("/nonexistent") is False


class TestMockFileSystemDirectories:
    """Tests for MockFileSystem directory operations."""

    def test_makedirs_creates_directory(self) -> None:
        """makedirs creates directory."""
        fs = MockFileSystem()
        fs.makedirs("/test/path")
        assert fs.is_dir("/test/path")

    def test_makedirs_creates_parents(self) -> None:
        """makedirs creates parent directories."""
        fs = MockFileSystem()
        fs.makedirs("/a/b/c/d")
        assert fs.is_dir("/a")
        assert fs.is_dir("/a/b")
        assert fs.is_dir("/a/b/c")
        assert fs.is_dir("/a/b/c/d")

    def test_makedirs_exist_ok_true(self) -> None:
        """makedirs with exist_ok=True doesn't raise for existing."""
        fs = MockFileSystem()
        fs.makedirs("/test")
        fs.makedirs("/test", exist_ok=True)  # Should not raise
        assert fs.is_dir("/test")

    def test_makedirs_exist_ok_false_raises(self) -> None:
        """makedirs with exist_ok=False raises for existing."""
        fs = MockFileSystem()
        fs.makedirs("/test")
        with pytest.raises(OSError):
            fs.makedirs("/test", exist_ok=False)

    def test_makedirs_raises_if_path_is_file(self) -> None:
        """makedirs raises if path is already a file."""
        fs = MockFileSystem()
        fs.write_text("/test", "content")
        with pytest.raises(OSError):
            fs.makedirs("/test")

    def test_exists_returns_true_for_dir(self) -> None:
        """exists returns True for directories."""
        fs = MockFileSystem()
        fs.makedirs("/test")
        assert fs.exists("/test") is True


class TestMockFileSystemFiles:
    """Tests for MockFileSystem file operations."""

    def test_write_text_creates_file(self) -> None:
        """write_text creates file with content."""
        fs = MockFileSystem()
        fs.write_text("/test.txt", "hello")
        assert fs.is_file("/test.txt")
        assert fs.read_text("/test.txt") == "hello"

    def test_write_text_creates_parent_dirs(self) -> None:
        """write_text creates parent directories."""
        fs = MockFileSystem()
        fs.write_text("/a/b/c/test.txt", "content")
        assert fs.is_dir("/a/b/c")
        assert fs.is_file("/a/b/c/test.txt")

    def test_write_text_overwrites_existing(self) -> None:
        """write_text overwrites existing file."""
        fs = MockFileSystem()
        fs.write_text("/test.txt", "first")
        fs.write_text("/test.txt", "second")
        assert fs.read_text("/test.txt") == "second"

    def test_read_text_returns_content(self) -> None:
        """read_text returns file content."""
        fs = MockFileSystem()
        fs.write_text("/test.txt", "hello world")
        assert fs.read_text("/test.txt") == "hello world"

    def test_read_text_raises_for_nonexistent(self) -> None:
        """read_text raises FileNotFoundError for missing file."""
        fs = MockFileSystem()
        with pytest.raises(FileNotFoundError):
            fs.read_text("/nonexistent")

    def test_exists_returns_true_for_file(self) -> None:
        """exists returns True for files."""
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        assert fs.exists("/test.txt") is True

    def test_remove_deletes_file(self) -> None:
        """remove deletes a file."""
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        fs.remove("/test.txt")
        assert fs.exists("/test.txt") is False

    def test_remove_raises_for_nonexistent(self) -> None:
        """remove raises FileNotFoundError for missing file."""
        fs = MockFileSystem()
        with pytest.raises(FileNotFoundError):
            fs.remove("/nonexistent")


class TestMockFileSystemPermissions:
    """Tests for MockFileSystem permission simulation."""

    def test_chmod_sets_mode(self) -> None:
        """chmod sets file mode."""
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        fs.chmod("/test.txt", 0o644)
        # Mode is stored but we mainly test read-only behavior

    def test_chmod_read_only_blocks_write(self) -> None:
        """chmod to read-only blocks write_text."""
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        fs.chmod("/test.txt", 0o444)  # Read-only
        with pytest.raises(PermissionError):
            fs.write_text("/test.txt", "new content")

    def test_chmod_restore_write_allows_write(self) -> None:
        """chmod to writable restores write_text."""
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        fs.chmod("/test.txt", 0o444)
        fs.chmod("/test.txt", 0o644)  # Restore write
        fs.write_text("/test.txt", "new content")  # Should not raise
        assert fs.read_text("/test.txt") == "new content"

    def test_chmod_raises_for_nonexistent(self) -> None:
        """chmod raises FileNotFoundError for missing path."""
        fs = MockFileSystem()
        with pytest.raises(FileNotFoundError):
            fs.chmod("/nonexistent", 0o644)


class TestMockFileSystemTestHelpers:
    """Tests for MockFileSystem test helper methods."""

    def test_get_file_returns_content(self) -> None:
        """get_file returns file content."""
        fs = MockFileSystem()
        fs.write_text("/test.txt", "content")
        assert fs.get_file("/test.txt") == "content"

    def test_get_file_returns_none_for_missing(self) -> None:
        """get_file returns None for missing file."""
        fs = MockFileSystem()
        assert fs.get_file("/nonexistent") is None

    def test_set_file_creates_file(self) -> None:
        """set_file creates file with content."""
        fs = MockFileSystem()
        fs.set_file("/test.txt", "content")
        assert fs.read_text("/test.txt") == "content"

    def test_list_files_returns_all_files(self) -> None:
        """list_files returns all file paths."""
        fs = MockFileSystem()
        fs.write_text("/a.txt", "a")
        fs.write_text("/b/c.txt", "c")
        files = fs.list_files()
        assert "/a.txt" in files
        assert "/b/c.txt" in files

    def test_list_dirs_returns_all_dirs(self) -> None:
        """list_dirs returns all directory paths."""
        fs = MockFileSystem()
        fs.makedirs("/a/b/c")
        dirs = fs.list_dirs()
        assert "/a" in dirs
        assert "/a/b" in dirs
        assert "/a/b/c" in dirs

    def test_clear_removes_everything(self) -> None:
        """clear removes all files and directories."""
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
        """RealFileSystem has all protocol methods."""
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
        """exists returns True for current directory."""
        fs = RealFileSystem()
        assert fs.exists("/") is True

    def test_is_dir_for_current_dir(self) -> None:
        """is_dir returns True for root."""
        fs = RealFileSystem()
        assert fs.is_dir("/") is True

    def test_is_file_for_nonexistent(self) -> None:
        """is_file returns False for nonexistent."""
        fs = RealFileSystem()
        assert fs.is_file("/nonexistent_file_12345.txt") is False
