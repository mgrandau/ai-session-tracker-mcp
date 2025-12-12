"""Tests for CLI module."""

from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import patch


class TestCLIParsing:
    """Tests for CLI argument parsing."""

    def test_main_returns_int(self) -> None:
        """Verifies main() returns integer exit code for shell compatibility.

        Tests that the CLI entry point returns a numeric exit code that
        can be used by shell scripts and CI/CD pipelines.

        Business context:
        Exit codes enable automation. CI pipelines check exit codes to
        determine if commands succeeded or failed.

        Arrangement:
        1. Mock sys.argv with just the program name.
        2. Mock run_server to prevent actual execution.

        Action:
        Call main() and capture return value.

        Assertion Strategy:
        Validates return is int type and equals 0 (success).

        Testing Principle:
        Validates POSIX-compliant exit code contract.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch.object(sys, "argv", ["ai-session-tracker"]),
            patch("ai_session_tracker_mcp.cli.run_server"),
        ):
            result = main()
            assert isinstance(result, int)
            assert result == 0

    def test_server_command(self) -> None:
        """Verifies 'server' subcommand invokes MCP server.

        Tests that the explicit server command routes to run_server
        function for starting the MCP protocol server.

        Business context:
        Users may explicitly request server mode. Command routing
        must correctly dispatch to server startup.

        Arrangement:
        1. Mock run_server to capture invocation.
        2. Mock sys.argv with 'server' subcommand.

        Action:
        Call main() with server argument.

        Assertion Strategy:
        Validates run_server was called exactly once.

        Testing Principle:
        Validates command routing for explicit subcommand.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_server") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "server"]),
        ):
            main()
            mock_run.assert_called_once()

    def test_dashboard_command(self) -> None:
        """Verifies 'dashboard' subcommand invokes web dashboard.

        Tests that the dashboard command routes to run_dashboard
        function for starting the web analytics UI.

        Business context:
        Dashboard provides visual analytics. Users need a simple
        command to launch the web interface.

        Arrangement:
        1. Mock run_dashboard to capture invocation.
        2. Mock sys.argv with 'dashboard' subcommand.

        Action:
        Call main() with dashboard argument.

        Assertion Strategy:
        Validates run_dashboard was called exactly once.

        Testing Principle:
        Validates command routing for dashboard subcommand.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_dashboard") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "dashboard"]),
        ):
            main()
            mock_run.assert_called_once()

    def test_dashboard_with_host_port(self) -> None:
        """Verifies dashboard accepts host and port configuration.

        Tests that --host and --port flags are parsed and passed
        to run_dashboard for custom binding.

        Business context:
        Production deployments may need custom host/port. Flags
        enable flexible network configuration.

        Arrangement:
        1. Mock run_dashboard to capture arguments.
        2. Mock sys.argv with host/port flags.

        Action:
        Call main() with dashboard and network arguments.

        Assertion Strategy:
        Validates run_dashboard called with correct host='0.0.0.0'
        and port=9000 matching provided flags.

        Testing Principle:
        Validates argument parsing for optional parameters.
        """
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
        """Verifies 'report' subcommand invokes text report generator.

        Tests that the report command routes to run_report function
        for printing analytics summary to stdout.

        Business context:
        CLI report enables quick stats without browser. Users can
        pipe output or include in scripts.

        Arrangement:
        1. Mock run_report to capture invocation.
        2. Mock sys.argv with 'report' subcommand.

        Action:
        Call main() with report argument.

        Assertion Strategy:
        Validates run_report was called exactly once.

        Testing Principle:
        Validates command routing for report subcommand.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_report") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "report"]),
        ):
            main()
            mock_run.assert_called_once()

    def test_no_command_defaults_to_server(self) -> None:
        """Verifies no subcommand defaults to running MCP server.

        Tests that invoking the CLI without a subcommand automatically
        starts the MCP server for seamless integration.

        Business context:
        MCP client configs just specify the executable. Default to
        server mode enables simple configuration.

        Arrangement:
        1. Mock run_server to capture invocation.
        2. Mock sys.argv with only program name.

        Action:
        Call main() with no arguments.

        Assertion Strategy:
        Validates run_server was called, confirming server is the
        default action when no subcommand provided.

        Testing Principle:
        Validates sensible default behavior.
        """
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
        """Verifies run_server uses asyncio.run for async execution.

        Tests that the server function properly delegates to asyncio
        for running the async MCP server main loop.

        Business context:
        MCP server is async. Proper asyncio integration ensures
        correct event loop handling.

        Arrangement:
        Mock asyncio.run to capture invocation.

        Action:
        Call run_server function.

        Assertion Strategy:
        Validates asyncio.run was called exactly once.

        Testing Principle:
        Validates async runtime integration.
        """
        from ai_session_tracker_mcp.cli import run_server

        with patch("ai_session_tracker_mcp.cli.asyncio.run") as mock_asyncio:
            run_server()
            mock_asyncio.assert_called_once()


class TestRunDashboard:
    """Tests for run_dashboard function."""

    def test_run_dashboard_calls_web_module(self) -> None:
        """Verifies run_dashboard delegates to web.run_dashboard.

        Tests that the CLI dashboard function properly calls the web
        module's implementation with default host/port.

        Business context:
        Separation of concerns: CLI handles arguments, web module
        handles actual server startup.

        Arrangement:
        Mock web.run_dashboard to capture invocation.

        Action:
        Call run_dashboard function.

        Assertion Strategy:
        Validates web.run_dashboard called with defaults:
        host='127.0.0.1', port=8000.

        Testing Principle:
        Validates delegation with correct default parameters.
        """
        with patch("ai_session_tracker_mcp.web.run_dashboard") as mock_run:
            from ai_session_tracker_mcp.cli import run_dashboard

            run_dashboard()
            mock_run.assert_called_once_with(host="127.0.0.1", port=8000)


class TestRunReport:
    """Tests for run_report function."""

    def test_run_report_prints_output(self) -> None:
        """Verifies run_report outputs analytics to stdout.

        Tests that the report function generates and prints analytics
        content suitable for terminal display.

        Business context:
        CLI report enables quick stats check. Output must include
        recognizable sections for usability.

        Arrangement:
        1. Mock StorageManager methods to return empty data.
        2. Capture stdout using StringIO.

        Action:
        Call run_report with mocked storage.

        Assertion Strategy:
        Validates output contains expected headers like 'SESSION SUMMARY'
        or 'ANALYTICS REPORT'.

        Testing Principle:
        Validates user-visible output formatting.
        """
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
        """Verifies __main__ module imports without errors.

        Tests that the module entry point can be imported, validating
        the package structure and dependencies.

        Business context:
        'python -m ai_session_tracker_mcp' requires __main__.py.
        Import must succeed for module execution.

        Arrangement:
        None - tests import side effects.

        Action:
        Import __main__ module.

        Assertion Strategy:
        No exception during import indicates success.

        Testing Principle:
        Validates package structure for module execution.
        """
        import ai_session_tracker_mcp.__main__  # noqa: F401

    def test_main_module_has_main(self) -> None:
        """Verifies __main__ module exports callable main function.

        Tests that the main entry point exists and is callable,
        enabling direct module execution.

        Business context:
        Module execution requires exposed main(). Callable check
        ensures proper entry point definition.

        Arrangement:
        Import main from __main__ module.

        Action:
        Check main is callable.

        Assertion Strategy:
        Validates callable(main) returns True.

        Testing Principle:
        Validates entry point contract for module execution.
        """
        from ai_session_tracker_mcp.__main__ import main

        assert callable(main)
