"""Main test module for ai-session-tracker-mcp."""

import ai_session_tracker_mcp


class TestVersion:
    """Test version information."""

    def test_version_exists(self) -> None:
        """Verifies that version string is defined in package.

        Tests that the __version__ attribute is set, ensuring the
        package can report its version.

        Business context:
        Version information is required for package distribution,
        dependency management, and user troubleshooting.

        Arrangement:
        None - tests package-level attribute.

        Action:
        Access __version__ attribute.

        Assertion Strategy:
        Validates version is not None.

        Testing Principle:
        Validates package metadata completeness.
        """
        assert ai_session_tracker_mcp.__version__ is not None

    def test_version_format(self) -> None:
        """Verifies version follows semantic versioning format.

        Tests that version string has MAJOR.MINOR.PATCH structure
        with numeric components.

        Business context:
        Semantic versioning communicates compatibility. MAJOR for
        breaking changes, MINOR for features, PATCH for fixes.

        Arrangement:
        None - tests package-level attribute.

        Action:
        Parse version string and validate components.

        Assertion Strategy:
        Validates 3 parts, all numeric.

        Testing Principle:
        Validates version convention compliance.
        """
        version = ai_session_tracker_mcp.__version__
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_title_exists(self) -> None:
        """Verifies that package title is defined.

        Tests that __title__ attribute matches expected package name.

        Business context:
        Title identifies the package in logs, error messages,
        and documentation.

        Arrangement:
        None - tests package-level attribute.

        Action:
        Access __title__ attribute.

        Assertion Strategy:
        Validates exact match with package name.

        Testing Principle:
        Validates package identity metadata.
        """
        assert ai_session_tracker_mcp.__title__ == "ai_session_tracker_mcp"

    def test_author_exists(self) -> None:
        """Verifies that package author is defined.

        Tests that __author__ attribute is set to expected value.

        Business context:
        Author information identifies maintainer for support,
        attribution, and licensing purposes.

        Arrangement:
        None - tests package-level attribute.

        Action:
        Access __author__ attribute.

        Assertion Strategy:
        Validates exact match with expected author.

        Testing Principle:
        Validates package attribution metadata.
        """
        assert ai_session_tracker_mcp.__author__ == "Mark Grandau"
