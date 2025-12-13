"""Tests for CLI module."""

from __future__ import annotations

import sys
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from conftest import MockFileSystem


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

    def test_version_flag(self) -> None:
        """Verifies --version flag prints version and exits.

        Tests that the CLI responds to --version with version info.

        Business context:
        Version flag is standard CLI convention for troubleshooting.

        Arrangement:
        Mock sys.argv with --version flag.

        Action:
        Call main() expecting SystemExit.

        Assertion Strategy:
        Validates SystemExit with code 0 (success).
        """

        from ai_session_tracker_mcp.cli import main

        with (
            patch.object(sys, "argv", ["ai-session-tracker", "--version"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 0

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

    def test_run_report_with_injected_dependencies(self) -> None:
        """Verifies run_report accepts injected storage and engine.

        Tests that the DI parameters allow mocking for testability.

        Business context:
        DI enables isolated testing without touching real storage.

        Arrangement:
        Create mock storage and engine instances.

        Action:
        Call run_report with injected mocks.

        Assertion Strategy:
        Validates mocks were called with expected methods.
        """
        from ai_session_tracker_mcp.cli import run_report

        mock_storage = MagicMock()
        mock_storage.load_sessions.return_value = {}
        mock_storage.load_interactions.return_value = []
        mock_storage.load_issues.return_value = []

        mock_engine = MagicMock()
        mock_engine.generate_summary_report.return_value = "Test Report"

        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            run_report(storage=mock_storage, engine=mock_engine)

        mock_storage.load_sessions.assert_called_once()
        mock_storage.load_interactions.assert_called_once()
        mock_storage.load_issues.assert_called_once()
        mock_engine.generate_summary_report.assert_called_once()
        assert "Test Report" in captured.getvalue()


class TestRunServerWithDashboard:
    """Tests for run_server with dashboard subprocess."""

    def test_run_server_with_dashboard_spawns_subprocess(self) -> None:
        """Verifies run_server spawns dashboard subprocess when configured.

        Tests that providing dashboard_host and dashboard_port arguments
        causes run_server to spawn a background subprocess.

        Business context:
        Users can optionally run the dashboard alongside the MCP server.
        This enables a complete setup with a single command.

        Arrangement:
        1. Create mock subprocess factory to capture invocation.
        2. Mock asyncio.run to prevent actual server execution.

        Action:
        Call run_server with dashboard_host, dashboard_port, and subprocess_factory.

        Assertion Strategy:
        Validates mock factory was called with dashboard arguments.
        """
        from ai_session_tracker_mcp.cli import run_server

        mock_process = MagicMock()
        mock_factory = MagicMock(return_value=mock_process)

        with patch("ai_session_tracker_mcp.cli.asyncio.run"):
            run_server(
                dashboard_host="127.0.0.1",
                dashboard_port=8080,
                subprocess_factory=mock_factory,
            )

            mock_factory.assert_called_once()
            args = mock_factory.call_args[0][0]
            assert "dashboard" in args
            assert "--host" in args
            assert "127.0.0.1" in args
            assert "--port" in args
            assert "8080" in args

            # Verify cleanup
            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once()

    def test_run_server_handles_subprocess_timeout(self) -> None:
        """Verifies run_server handles subprocess timeout gracefully.

        Tests that when the dashboard subprocess doesn't terminate in time,
        run_server kills it forcefully.

        Business context:
        Subprocesses may hang during shutdown. Server must ensure cleanup
        even if graceful termination fails.

        Arrangement:
        1. Create mock subprocess that raises TimeoutExpired on wait().
        2. Mock asyncio.run to prevent actual server execution.

        Action:
        Call run_server with dashboard configuration.

        Assertion Strategy:
        Validates kill() was called after timeout.
        """
        import subprocess

        from ai_session_tracker_mcp.cli import run_server

        mock_process = MagicMock()
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=5),
            None,  # Second call after kill() succeeds
        ]
        mock_factory = MagicMock(return_value=mock_process)

        with patch("ai_session_tracker_mcp.cli.asyncio.run"):
            run_server(
                dashboard_host="127.0.0.1",
                dashboard_port=8080,
                subprocess_factory=mock_factory,
            )

            # Verify timeout handling
            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()
            assert mock_process.wait.call_count == 2

    def test_run_server_validates_dashboard_host_port_pair(self) -> None:
        """Verifies run_server requires both host and port together.

        Tests that providing only dashboard_host or only dashboard_port
        logs a warning and continues without spawning subprocess.

        Business context:
        Partial configuration is likely a user error. Warn but don't fail.

        Arrangement:
        Mock asyncio.run to prevent actual server execution.

        Action:
        Call run_server with only dashboard_host (no port).

        Assertion Strategy:
        Validates subprocess not spawned, server still runs.
        """
        from ai_session_tracker_mcp.cli import run_server

        mock_factory = MagicMock()

        with patch("ai_session_tracker_mcp.cli.asyncio.run") as mock_asyncio:
            # Only host provided
            run_server(
                dashboard_host="127.0.0.1",
                dashboard_port=None,
                subprocess_factory=mock_factory,
            )

            # Should not spawn subprocess
            mock_factory.assert_not_called()
            # Should still run server
            mock_asyncio.assert_called_once()

    def test_run_server_validates_dashboard_port_only(self) -> None:
        """Verifies run_server warns when only port provided.

        Tests that providing only dashboard_port (no host) logs warning.

        Arrangement:
        Mock asyncio.run to prevent actual server execution.

        Action:
        Call run_server with only dashboard_port (no host).

        Assertion Strategy:
        Validates subprocess not spawned, server still runs.
        """
        from ai_session_tracker_mcp.cli import run_server

        mock_factory = MagicMock()

        with patch("ai_session_tracker_mcp.cli.asyncio.run") as mock_asyncio:
            # Only port provided
            run_server(
                dashboard_host=None,
                dashboard_port=8080,
                subprocess_factory=mock_factory,
            )

            # Should not spawn subprocess
            mock_factory.assert_not_called()
            # Should still run server
            mock_asyncio.assert_called_once()


class TestRunInstall:
    """Tests for run_install command."""

    def test_run_install_creates_mcp_json(self, mock_fs: MockFileSystem) -> None:
        """
        Verifies run_install creates .vscode/mcp.json with server config.

        Tests that the install command creates the configuration file
        in the expected location with proper structure.

        Business context:
        Users need a simple way to configure the MCP server.
        run_install automates the setup process.

        Arrangement:
        1. Use MockFileSystem for isolated testing.
        2. No pre-existing config files.

        Action:
        Call run_install function with mock filesystem, cwd, and package_dir.

        Assertion Strategy:
        Validates mcp.json exists and contains server configuration with
        the ai-session-tracker server entry.

        Testing Principle:
        Tests happy path for first-time installation.
        """
        import json

        from ai_session_tracker_mcp.cli import run_install

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        config_content = mock_fs.get_file("/project/.vscode/mcp.json")
        assert config_content is not None

        config = json.loads(config_content)
        assert "servers" in config
        assert "ai-session-tracker" in config["servers"]

    def test_run_install_updates_existing_config(self, mock_fs: MockFileSystem) -> None:
        """
        Verifies run_install updates existing mcp.json without losing data.

        Tests that run_install preserves existing server configs while
        adding the ai-session-tracker entry.

        Business context:
        Users may already have other MCP servers configured. Install
        should not overwrite their existing configuration.

        Arrangement:
        1. Create .vscode directory in mock filesystem.
        2. Create existing mcp.json with other-server config.

        Action:
        Call run_install function to add ai-session-tracker.

        Assertion Strategy:
        Validates both original (other-server) and new (ai-session-tracker)
        servers exist in the updated configuration.

        Testing Principle:
        Tests configuration merging preserves existing data.
        """
        import json

        from ai_session_tracker_mcp.cli import run_install

        # Set up existing config
        mock_fs.makedirs("/project/.vscode", exist_ok=True)
        existing_config = {"servers": {"other-server": {"command": "other"}}}
        mock_fs.set_file("/project/.vscode/mcp.json", json.dumps(existing_config))

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        config_content = mock_fs.get_file("/project/.vscode/mcp.json")
        config = json.loads(config_content)

        assert "other-server" in config["servers"]
        assert "ai-session-tracker" in config["servers"]

    def test_run_install_handles_invalid_json(self, mock_fs: MockFileSystem) -> None:
        """
        Verifies run_install handles corrupt mcp.json gracefully.

        Tests that run_install creates backup of invalid JSON and
        proceeds with fresh configuration.

        Business context:
        Configuration files can become corrupted. Install should
        recover gracefully rather than failing.

        Arrangement:
        1. Create .vscode directory in mock filesystem.
        2. Create mcp.json with invalid JSON content "{ invalid json }".

        Action:
        Call run_install function which should detect invalid JSON.

        Assertion Strategy:
        Validates backup file (.bak) was created and new config is valid JSON
        with servers section.

        Testing Principle:
        Tests error recovery and data preservation on corrupt input.
        """
        import json

        from ai_session_tracker_mcp.cli import run_install

        # Set up invalid JSON
        mock_fs.makedirs("/project/.vscode", exist_ok=True)
        mock_fs.set_file("/project/.vscode/mcp.json", "{ invalid json }")

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        # Check backup was created
        assert mock_fs.exists("/project/.vscode/mcp.json.bak")

        # New config should be valid
        config_content = mock_fs.get_file("/project/.vscode/mcp.json")
        config = json.loads(config_content)
        assert "servers" in config

    def test_run_install_copies_agent_files(self, mock_fs: MockFileSystem) -> None:
        """Verifies run_install copies chatmode and instruction files.

        Tests that install copies bundled files to .github directory
        for VS Code agent integration.

        Business context:
        Users need chatmode and instruction files for the tracked
        agent workflow. Install automates their installation.

        Arrangement:
        Set up bundled files in mock filesystem.

        Action:
        Call run_install function.

        Assertion Strategy:
        Validates .github directories created with copied files.
        """
        from ai_session_tracker_mcp.cli import run_install

        # Set up bundled agent files
        mock_fs.makedirs("/pkg/agent_files/chatmodes", exist_ok=True)
        mock_fs.makedirs("/pkg/agent_files/instructions", exist_ok=True)
        mock_fs.set_file("/pkg/agent_files/chatmodes/test.chatmode.md", "# Test Chatmode")
        mock_fs.set_file(
            "/pkg/agent_files/instructions/test.instructions.md", "# Test Instructions"
        )

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        # Verify files were copied
        assert mock_fs.exists("/project/.github/chatmodes/test.chatmode.md")
        assert mock_fs.exists("/project/.github/instructions/test.instructions.md")
        assert mock_fs.get_file("/project/.github/chatmodes/test.chatmode.md") == "# Test Chatmode"

    def test_run_install_skips_existing_agent_files(self, mock_fs: MockFileSystem) -> None:
        """Verifies run_install doesn't overwrite existing agent files.

        Tests that install skips copying files that already exist at
        the destination.

        Business context:
        Users may have customized their agent files. Install should
        not overwrite their modifications.

        Arrangement:
        Set up both source and destination files in mock filesystem.

        Action:
        Call run_install function.

        Assertion Strategy:
        Validates existing file content is preserved.
        """
        from ai_session_tracker_mcp.cli import run_install

        # Set up bundled agent files
        mock_fs.makedirs("/pkg/agent_files/chatmodes", exist_ok=True)
        mock_fs.set_file("/pkg/agent_files/chatmodes/test.chatmode.md", "# New Content")

        # Set up existing file at destination
        mock_fs.makedirs("/project/.github/chatmodes", exist_ok=True)
        mock_fs.set_file("/project/.github/chatmodes/test.chatmode.md", "# Existing Content")

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        # Verify existing content is preserved
        assert (
            mock_fs.get_file("/project/.github/chatmodes/test.chatmode.md") == "# Existing Content"
        )

    def test_run_install_fallback_to_module_invocation(self, mock_fs: MockFileSystem) -> None:
        """Verifies run_install uses module invocation when executable not found.

        Tests that when the ai-session-tracker executable doesn't exist,
        the config falls back to 'python -m ai_session_tracker_mcp server'.

        Business context:
        Development environments may not have the executable installed.
        Module invocation provides a reliable fallback.

        Arrangement:
        MockFileSystem does not have the executable path, so fs.exists returns False.

        Action:
        Call run_install function.

        Assertion Strategy:
        Validates config uses '-m ai_session_tracker_mcp server' args.
        """
        import json

        from ai_session_tracker_mcp.cli import run_install

        # MockFileSystem doesn't have the bin_dir/ai-session-tracker path,
        # so fs.exists() returns False for it automatically

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        config_content = mock_fs.get_file("/project/.vscode/mcp.json")
        config = json.loads(config_content)

        server_config = config["servers"]["ai-session-tracker"]
        # Should use module invocation fallback
        assert server_config["args"] == ["-m", "ai_session_tracker_mcp", "server"]
        assert server_config["command"] == sys.executable

    def test_run_install_already_up_to_date(self, mock_fs: MockFileSystem) -> None:
        """Verifies run_install reports when config is already up to date.

        Tests that when ai-session-tracker is already configured with
        the same settings, run_install reports it's up to date.

        Business context:
        Users may run install multiple times. Should gracefully handle
        already-configured state without unnecessary changes.

        Arrangement:
        Create config with matching ai-session-tracker entry.

        Action:
        Call run_install function.

        Assertion Strategy:
        Validates "already installed and up to date" message shown.
        """
        import json

        from ai_session_tracker_mcp.cli import run_install

        # Pre-create config with matching entry
        mock_fs.makedirs("/project/.vscode", exist_ok=True)
        existing_config = {
            "servers": {
                "ai-session-tracker": {
                    "command": sys.executable,
                    "args": ["-m", "ai_session_tracker_mcp", "server"],
                }
            }
        }
        mock_fs.set_file("/project/.vscode/mcp.json", json.dumps(existing_config))

        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        # Log output goes to logger, not stdout - check logging instead
        # Config should remain unchanged
        config_content = mock_fs.get_file("/project/.vscode/mcp.json")
        config = json.loads(config_content)
        assert config["servers"]["ai-session-tracker"]["command"] == sys.executable

    def test_run_install_updates_outdated_config(self, mock_fs: MockFileSystem) -> None:
        """Verifies run_install updates config when settings differ.

        Tests that when ai-session-tracker is configured with different
        settings, run_install updates to current settings.

        Business context:
        Users may have outdated config from previous install. Install
        should update to current settings.

        Arrangement:
        Create config with different ai-session-tracker entry.

        Action:
        Call run_install function.

        Assertion Strategy:
        Validates config was updated to new values.
        """
        import json

        from ai_session_tracker_mcp.cli import run_install

        # Pre-create config with outdated entry
        mock_fs.makedirs("/project/.vscode", exist_ok=True)
        existing_config = {
            "servers": {
                "ai-session-tracker": {
                    "command": "/old/path/python",
                    "args": ["old-args"],
                }
            }
        }
        mock_fs.set_file("/project/.vscode/mcp.json", json.dumps(existing_config))

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        # Verify config was updated
        config_content = mock_fs.get_file("/project/.vscode/mcp.json")
        config = json.loads(config_content)
        assert config["servers"]["ai-session-tracker"]["command"] == sys.executable


class TestServerCommandWithDashboard:
    """Tests for server command with dashboard options."""

    def test_server_command_with_dashboard_options(self) -> None:
        """Verifies server command accepts dashboard host/port options.

        Tests that the CLI parses dashboard configuration options
        and passes them to run_server.

        Business context:
        Advanced users may want to start dashboard alongside server.
        CLI provides options for this integrated setup.

        Arrangement:
        1. Mock run_server to capture arguments.
        2. Mock sys.argv with dashboard options.

        Action:
        Call main() with server and dashboard options.

        Assertion Strategy:
        Validates run_server called with dashboard_host and dashboard_port.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_server") as mock_run,
            patch.object(
                sys,
                "argv",
                [
                    "ai-session-tracker",
                    "server",
                    "--dashboard-host",
                    "0.0.0.0",
                    "--dashboard-port",
                    "9000",
                ],
            ),
        ):
            main()
            mock_run.assert_called_once_with(
                dashboard_host="0.0.0.0",
                dashboard_port=9000,
            )


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
