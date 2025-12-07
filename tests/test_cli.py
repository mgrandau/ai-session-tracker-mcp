"""Tests for CLI module."""

from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import patch


class TestCLIParsing:
    """Tests for CLI argument parsing."""

    def test_main_returns_int(self) -> None:
        """main() returns an integer exit code."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch.object(sys, "argv", ["ai-session-tracker"]),
            patch("ai_session_tracker_mcp.cli.run_server"),
        ):
            result = main()
            assert isinstance(result, int)
            assert result == 0

    def test_server_command(self) -> None:
        """server command calls run_server."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_server") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "server"]),
        ):
            main()
            mock_run.assert_called_once()

    def test_dashboard_command(self) -> None:
        """dashboard command calls run_dashboard."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_dashboard") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "dashboard"]),
        ):
            main()
            mock_run.assert_called_once()

    def test_dashboard_with_host_port(self) -> None:
        """dashboard command accepts host and port."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_dashboard") as mock_run,
            patch.object(
                sys,
                "argv",
                ["ai-session-tracker", "dashboard", "--host", "0.0.0.0", "--port", "9000"],
            ),
        ):
            main()
            mock_run.assert_called_once_with(host="0.0.0.0", port=9000)

    def test_report_command(self) -> None:
        """report command calls run_report."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_report") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "report"]),
        ):
            main()
            mock_run.assert_called_once()

    def test_no_command_defaults_to_server(self) -> None:
        """No command defaults to running server."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_server") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker"]),
        ):
            main()
            mock_run.assert_called_once()


class TestRunServer:
    """Tests for run_server function."""

    def test_run_server_calls_asyncio_run(self) -> None:
        """run_server uses asyncio.run with main."""
        from ai_session_tracker_mcp.cli import run_server

        with patch("ai_session_tracker_mcp.cli.asyncio.run") as mock_asyncio:
            run_server()
            mock_asyncio.assert_called_once()


class TestRunDashboard:
    """Tests for run_dashboard function."""

    def test_run_dashboard_calls_web_module(self) -> None:
        """run_dashboard calls web.run_dashboard."""
        with patch("ai_session_tracker_mcp.web.run_dashboard") as mock_run:
            from ai_session_tracker_mcp.cli import run_dashboard

            run_dashboard()
            mock_run.assert_called_once_with(host="127.0.0.1", port=8000)


class TestRunReport:
    """Tests for run_report function."""

    def test_run_report_prints_output(self) -> None:
        """run_report prints report to stdout."""
        from ai_session_tracker_mcp.cli import run_report
        from ai_session_tracker_mcp.storage import StorageManager

        with (
            patch.object(StorageManager, "load_sessions", return_value={}),
            patch.object(StorageManager, "load_interactions", return_value=[]),
            patch.object(StorageManager, "load_issues", return_value=[]),
        ):
            captured = StringIO()
            with patch.object(sys, "stdout", captured):
                run_report()

            output = captured.getvalue()
            assert "SESSION SUMMARY" in output or "ANALYTICS REPORT" in output


class TestMainModule:
    """Tests for __main__.py entry point."""

    def test_main_module_imports(self) -> None:
        """__main__ module imports without error."""
        import ai_session_tracker_mcp.__main__  # noqa: F401

    def test_main_module_has_main(self) -> None:
        """__main__ module has main function."""
        from ai_session_tracker_mcp.__main__ import main

        assert callable(main)
