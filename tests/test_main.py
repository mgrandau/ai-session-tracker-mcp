"""Main test module for ai-session-tracker-mcp."""

import ai_session_tracker_mcp


class TestVersion:
    """Test version information."""

    def test_version_exists(self) -> None:
        """Test that version string exists."""
        assert ai_session_tracker_mcp.__version__ is not None

    def test_version_format(self) -> None:
        """Test that version follows semantic versioning format."""
        version = ai_session_tracker_mcp.__version__
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_title_exists(self) -> None:
        """Test that title exists."""
        assert ai_session_tracker_mcp.__title__ == "ai_session_tracker_mcp"

    def test_author_exists(self) -> None:
        """Test that author exists."""
        assert ai_session_tracker_mcp.__author__ == "Mark Grandau"
