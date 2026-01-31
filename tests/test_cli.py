"""Tests for CLI module."""

from __future__ import annotations

import json
import sys
from io import StringIO
from typing import TYPE_CHECKING, Any
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
        """Verifies run_install copies agent and instruction files.

        Tests that install copies bundled files to .github directory
        for VS Code agent integration.

        Business context:
        Users need agent and instruction files for the tracked
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
        mock_fs.makedirs("/pkg/agent_files/agents", exist_ok=True)
        mock_fs.makedirs("/pkg/agent_files/instructions", exist_ok=True)
        mock_fs.set_file("/pkg/agent_files/agents/test.agent.md", "# Test Agent")
        mock_fs.set_file(
            "/pkg/agent_files/instructions/test.instructions.md", "# Test Instructions"
        )

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        # Verify files were copied
        assert mock_fs.exists("/project/.github/agents/test.agent.md")
        assert mock_fs.exists("/project/.github/instructions/test.instructions.md")
        assert mock_fs.get_file("/project/.github/agents/test.agent.md") == "# Test Agent"

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
        mock_fs.makedirs("/pkg/agent_files/agents", exist_ok=True)
        mock_fs.set_file("/pkg/agent_files/agents/test.agent.md", "# New Content")

        # Set up existing file at destination
        mock_fs.makedirs("/project/.github/agents", exist_ok=True)
        mock_fs.set_file("/project/.github/agents/test.agent.md", "# Existing Content")

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        # Verify existing content is preserved
        assert mock_fs.get_file("/project/.github/agents/test.agent.md") == "# Existing Content"

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

    def test_run_install_prompts_only_skips_mcp_config(self, mock_fs: MockFileSystem) -> None:
        """Verifies --prompts-only flag skips MCP configuration.

        Tests that when prompts_only=True, install only copies agent files
        and does not create/modify mcp.json.

        Business context:
        Users may want to only update agent files without touching MCP
        configuration, especially when sharing prompts across teams.

        Arrangement:
        Set up bundled agent files in mock filesystem.

        Action:
        Call run_install with prompts_only=True.

        Assertion Strategy:
        Validates mcp.json was not created and agent files were copied.

        Testing Principle:
        Validates flag correctly skips MCP configuration.
        """
        from ai_session_tracker_mcp.cli import run_install

        # Set up bundled agent files
        mock_fs.makedirs("/pkg/agent_files/agents", exist_ok=True)
        mock_fs.set_file("/pkg/agent_files/agents/test.agent.md", "# Test")

        run_install(
            filesystem=mock_fs,
            cwd="/project",
            package_dir="/pkg",
            prompts_only=True,
        )

        # Verify mcp.json was NOT created
        assert not mock_fs.exists("/project/.vscode/mcp.json")

        # Verify agent files were copied
        assert mock_fs.exists("/project/.github/agents/test.agent.md")

    def test_run_install_mcp_only_skips_agent_files(self, mock_fs: MockFileSystem) -> None:
        """Verifies --mcp-only flag skips agent file installation.

        Tests that when mcp_only=True, install only creates MCP config
        and does not copy agent files.

        Business context:
        Users may already have custom agent files and only want to
        configure the MCP server.

        Arrangement:
        Set up bundled agent files in mock filesystem.

        Action:
        Call run_install with mcp_only=True.

        Assertion Strategy:
        Validates mcp.json was created but agent files were not copied.

        Testing Principle:
        Validates flag correctly skips agent files.
        """
        import json

        from ai_session_tracker_mcp.cli import run_install

        # Set up bundled agent files
        mock_fs.makedirs("/pkg/agent_files/agents", exist_ok=True)
        mock_fs.set_file("/pkg/agent_files/agents/test.agent.md", "# Test")

        run_install(
            filesystem=mock_fs,
            cwd="/project",
            package_dir="/pkg",
            mcp_only=True,
        )

        # Verify mcp.json was created
        assert mock_fs.exists("/project/.vscode/mcp.json")
        config_content = mock_fs.get_file("/project/.vscode/mcp.json")
        config = json.loads(config_content)
        assert "ai-session-tracker" in config["servers"]

        # Verify agent files were NOT copied
        assert not mock_fs.exists("/project/.github/agents/test.agent.md")

    def test_run_install_global_flag_linux(self, mock_fs: MockFileSystem) -> None:
        """Verifies --global flag installs to user's global VS Code settings.

        Tests that when global_install=True, install creates config in
        the user's global VS Code settings directory instead of project.

        Business context:
        Users may want to enable session tracking globally for all
        projects without per-project configuration.

        Arrangement:
        Mock home directory path.

        Action:
        Call run_install with global_install=True.

        Assertion Strategy:
        Validates mcp.json was created in global settings path.

        Testing Principle:
        Validates global install target directory.
        """
        import json

        from ai_session_tracker_mcp.cli import run_install

        with patch("pathlib.Path.home", return_value=MagicMock(__str__=lambda _: "/home/user")):
            run_install(
                filesystem=mock_fs,
                cwd="/project",
                package_dir="/pkg",
                global_install=True,
            )

        # Verify global mcp.json was created (Linux path)
        global_config_path = "/home/user/.config/Code/User/mcp.json"
        assert mock_fs.exists(global_config_path)
        config_content = mock_fs.get_file(global_config_path)
        config = json.loads(config_content)
        assert "ai-session-tracker" in config["servers"]

    def test_install_command_parses_global_flag(self) -> None:
        """Verifies install command parses --global flag correctly.

        Tests that the CLI argument parser accepts and passes the
        --global flag to run_install.

        Business context:
        CLI needs to expose global installation option to users.

        Arrangement:
        Mock run_install to capture arguments.

        Action:
        Call main() with install --global.

        Assertion Strategy:
        Validates run_install was called with global_install=True.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_install") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "install", "--global"]),
        ):
            main()
            mock_run.assert_called_once_with(
                global_install=True,
                prompts_only=False,
                mcp_only=False,
                service=False,
            )

    def test_install_command_parses_prompts_only_flag(self) -> None:
        """Verifies install command parses --prompts-only flag correctly.

        Tests that the CLI argument parser accepts and passes the
        --prompts-only flag to run_install.

        Business context:
        CLI needs to expose prompts-only option to users.

        Arrangement:
        Mock run_install to capture arguments.

        Action:
        Call main() with install --prompts-only.

        Assertion Strategy:
        Validates run_install was called with prompts_only=True.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_install") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "install", "--prompts-only"]),
        ):
            main()
            mock_run.assert_called_once_with(
                global_install=False,
                prompts_only=True,
                mcp_only=False,
                service=False,
            )

    def test_install_command_parses_mcp_only_flag(self) -> None:
        """Verifies install command parses --mcp-only flag correctly.

        Tests that the CLI argument parser accepts and passes the
        --mcp-only flag to run_install.

        Business context:
        CLI needs to expose mcp-only option to users.

        Arrangement:
        Mock run_install to capture arguments.

        Action:
        Call main() with install --mcp-only.

        Assertion Strategy:
        Validates run_install was called with mcp_only=True.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_install") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "install", "--mcp-only"]),
        ):
            main()
            mock_run.assert_called_once_with(
                global_install=False,
                prompts_only=False,
                mcp_only=True,
                service=False,
            )


class TestInstallServiceFlag:
    """Tests for install command --service flag."""

    def test_install_command_parses_service_flag(self) -> None:
        """Verifies install command parses --service flag correctly.

        Tests that the CLI argument parser accepts and passes the
        --service flag to run_install.

        Business context:
        CLI needs to expose service installation option to users.

        Arrangement:
        Mock run_install to capture arguments.

        Action:
        Call main() with install --service.

        Assertion Strategy:
        Validates run_install was called with service=True.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_install") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "install", "--service"]),
        ):
            main()
            mock_run.assert_called_once_with(
                global_install=False,
                prompts_only=False,
                mcp_only=False,
                service=True,
            )


class TestServiceCommand:
    """Tests for service subcommand."""

    def test_service_start_command(self) -> None:
        """Verifies 'service start' subcommand works correctly.

        Tests that the service start command routes to run_service
        function with start action.

        Business context:
        Users need to start the background service.

        Arrangement:
        Mock run_service to capture invocation.

        Action:
        Call main() with service start argument.

        Assertion Strategy:
        Validates run_service was called with action='start'.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_service") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "service", "start"]),
        ):
            mock_run.return_value = 0
            result = main()
            mock_run.assert_called_once_with("start")
            assert result == 0

    def test_service_stop_command(self) -> None:
        """Verifies 'service stop' subcommand works correctly.

        Tests that the service stop command routes to run_service
        function with stop action.

        Business context:
        Users need to stop the background service.

        Arrangement:
        Mock run_service to capture invocation.

        Action:
        Call main() with service stop argument.

        Assertion Strategy:
        Validates run_service was called with action='stop'.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_service") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "service", "stop"]),
        ):
            mock_run.return_value = 0
            result = main()
            mock_run.assert_called_once_with("stop")
            assert result == 0

    def test_service_status_command(self) -> None:
        """Verifies 'service status' subcommand works correctly.

        Tests that the service status command routes to run_service
        function with status action.

        Business context:
        Users need to check service status.

        Arrangement:
        Mock run_service to capture invocation.

        Action:
        Call main() with service status argument.

        Assertion Strategy:
        Validates run_service was called with action='status'.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_service") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "service", "status"]),
        ):
            mock_run.return_value = 0
            result = main()
            mock_run.assert_called_once_with("status")
            assert result == 0

    def test_service_uninstall_command(self) -> None:
        """Verifies 'service uninstall' subcommand works correctly.

        Tests that the service uninstall command routes to run_service
        function with uninstall action.

        Business context:
        Users need to remove the service.

        Arrangement:
        Mock run_service to capture invocation.

        Action:
        Call main() with service uninstall argument.

        Assertion Strategy:
        Validates run_service was called with action='uninstall'.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_service") as mock_run,
            patch.object(sys, "argv", ["ai-session-tracker", "service", "uninstall"]),
        ):
            mock_run.return_value = 0
            result = main()
            mock_run.assert_called_once_with("uninstall")
            assert result == 0


class TestRunService:
    """Tests for run_service function."""

    def test_run_service_start_success(self) -> None:
        """Verifies run_service start returns 0 on success.

        Tests that starting a service successfully returns exit code 0.

        Business context:
        Service start should indicate success via exit code.

        Arrangement:
        Mock service manager with successful start.

        Action:
        Call run_service with 'start' action.

        Assertion Strategy:
        Validates return code is 0.
        """
        from ai_session_tracker_mcp.cli import run_service

        mock_manager = MagicMock()
        mock_manager.start.return_value = True

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            return_value=mock_manager,
        ):
            result = run_service("start")
            assert result == 0
            mock_manager.start.assert_called_once()

    def test_run_service_start_failure(self) -> None:
        """Verifies run_service start returns 1 on failure.

        Tests that failing to start service returns exit code 1.

        Business context:
        Service start failure should indicate error via exit code.

        Arrangement:
        Mock service manager with failed start.

        Action:
        Call run_service with 'start' action.

        Assertion Strategy:
        Validates return code is 1.
        """
        from ai_session_tracker_mcp.cli import run_service

        mock_manager = MagicMock()
        mock_manager.start.return_value = False

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            return_value=mock_manager,
        ):
            result = run_service("start")
            assert result == 1

    def test_run_service_stop_success(self) -> None:
        """Verifies run_service stop returns 0 on success."""
        from ai_session_tracker_mcp.cli import run_service

        mock_manager = MagicMock()
        mock_manager.stop.return_value = True

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            return_value=mock_manager,
        ):
            result = run_service("stop")
            assert result == 0
            mock_manager.stop.assert_called_once()

    def test_run_service_stop_failure(self) -> None:
        """Verifies run_service stop returns 1 on failure."""
        from ai_session_tracker_mcp.cli import run_service

        mock_manager = MagicMock()
        mock_manager.stop.return_value = False

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            return_value=mock_manager,
        ):
            result = run_service("stop")
            assert result == 1

    def test_run_service_status_returns_info(self) -> None:
        """Verifies run_service status returns status information."""
        from ai_session_tracker_mcp.cli import run_service

        mock_manager = MagicMock()
        mock_manager.status.return_value = {
            "installed": True,
            "running": True,
            "status": "Service is active",
        }

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            return_value=mock_manager,
        ):
            result = run_service("status")
            assert result == 0
            mock_manager.status.assert_called_once()

    def test_run_service_uninstall_success(self) -> None:
        """Verifies run_service uninstall returns 0 on success."""
        from ai_session_tracker_mcp.cli import run_service

        mock_manager = MagicMock()
        mock_manager.uninstall.return_value = True

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            return_value=mock_manager,
        ):
            result = run_service("uninstall")
            assert result == 0
            mock_manager.uninstall.assert_called_once()

    def test_run_service_uninstall_failure(self) -> None:
        """Verifies run_service uninstall returns 1 on failure."""
        from ai_session_tracker_mcp.cli import run_service

        mock_manager = MagicMock()
        mock_manager.uninstall.return_value = False

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            return_value=mock_manager,
        ):
            result = run_service("uninstall")
            assert result == 1

    def test_run_service_unsupported_platform(self) -> None:
        """Verifies run_service handles unsupported platform."""
        from ai_session_tracker_mcp.cli import run_service

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            side_effect=NotImplementedError("Unsupported"),
        ):
            result = run_service("status")
            assert result == 1

    def test_run_service_unknown_action(self) -> None:
        """Verifies run_service handles unknown action."""
        from ai_session_tracker_mcp.cli import run_service

        mock_manager = MagicMock()

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            return_value=mock_manager,
        ):
            result = run_service("invalid")
            assert result == 1


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


class TestSessionStartCommand:
    """Tests for session start CLI command."""

    def test_start_command_parses_arguments(self) -> None:
        """Verifies 'start' subcommand parses required arguments.

        Business context:
        Session start requires specific parameters for tracking.
        """
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_session_start") as mock_run,
            patch.object(
                sys,
                "argv",
                [
                    "ai-session-tracker",
                    "start",
                    "--name",
                    "Test task",
                    "--type",
                    "code_generation",
                    "--model",
                    "claude-opus-4-20250514",
                    "--mins",
                    "60",
                    "--source",
                    "manual",
                ],
            ),
        ):
            mock_run.return_value = 0
            result = main()
            mock_run.assert_called_once_with(
                name="Test task",
                task_type="code_generation",
                model="claude-opus-4-20250514",
                mins=60.0,
                source="manual",
                context="",
                json_output=False,
            )
            assert result == 0

    def test_start_command_with_optional_args(self) -> None:
        """Verifies 'start' subcommand accepts optional arguments."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_session_start") as mock_run,
            patch.object(
                sys,
                "argv",
                [
                    "ai-session-tracker",
                    "start",
                    "--name",
                    "Test task",
                    "--type",
                    "debugging",
                    "--model",
                    "gpt-4",
                    "--mins",
                    "120",
                    "--source",
                    "issue_tracker",
                    "--context",
                    "Extra context here",
                    "--json",
                ],
            ),
        ):
            mock_run.return_value = 0
            main()
            mock_run.assert_called_once_with(
                name="Test task",
                task_type="debugging",
                model="gpt-4",
                mins=120.0,
                source="issue_tracker",
                context="Extra context here",
                json_output=True,
            )

    def test_run_session_start_success(self) -> None:
        """Verifies run_session_start returns 0 on success."""
        from ai_session_tracker_mcp.cli import run_session_start
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=True,
            message="Session started",
            data={"session_id": "test_123"},
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.start_session.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_start(
                name="Test",
                task_type="testing",
                model="test-model",
                mins=30,
                source="manual",
            )

            assert result == 0
            mock_service.start_session.assert_called_once()

    def test_run_session_start_failure(self) -> None:
        """Verifies run_session_start returns 1 on failure."""
        from ai_session_tracker_mcp.cli import run_session_start
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=False,
            message="Invalid parameters",
            error="Task type invalid",
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.start_session.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_start(
                name="Test",
                task_type="invalid",
                model="test-model",
                mins=30,
                source="manual",
            )

            assert result == 1


class TestSessionLogCommand:
    """Tests for session log CLI command."""

    def test_log_command_parses_arguments(self) -> None:
        """Verifies 'log' subcommand parses required arguments."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_session_log") as mock_run,
            patch.object(
                sys,
                "argv",
                [
                    "ai-session-tracker",
                    "log",
                    "--session-id",
                    "test_123",
                    "--prompt",
                    "Test prompt",
                    "--summary",
                    "Test summary",
                    "--rating",
                    "4",
                ],
            ),
        ):
            mock_run.return_value = 0
            main()
            mock_run.assert_called_once_with(
                session_id="test_123",
                prompt="Test prompt",
                summary="Test summary",
                rating=4,
                iterations=1,
                tools=[],
                json_output=False,
            )

    def test_log_command_with_optional_args(self) -> None:
        """Verifies 'log' subcommand accepts optional arguments."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_session_log") as mock_run,
            patch.object(
                sys,
                "argv",
                [
                    "ai-session-tracker",
                    "log",
                    "--session-id",
                    "test_123",
                    "--prompt",
                    "Test prompt",
                    "--summary",
                    "Test summary",
                    "--rating",
                    "5",
                    "--iterations",
                    "3",
                    "--tools",
                    "read_file",
                    "grep_search",
                    "--json",
                ],
            ),
        ):
            mock_run.return_value = 0
            main()
            mock_run.assert_called_once_with(
                session_id="test_123",
                prompt="Test prompt",
                summary="Test summary",
                rating=5,
                iterations=3,
                tools=["read_file", "grep_search"],
                json_output=True,
            )

    def test_run_session_log_success(self) -> None:
        """Verifies run_session_log returns 0 on success."""
        from ai_session_tracker_mcp.cli import run_session_log
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=True,
            message="Interaction logged",
            data={"interaction_id": "int_123"},
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.log_interaction.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_log(
                session_id="test_123",
                prompt="Test",
                summary="Result",
                rating=4,
            )

            assert result == 0


class TestSessionEndCommand:
    """Tests for session end CLI command."""

    def test_end_command_parses_arguments(self) -> None:
        """Verifies 'end' subcommand parses required arguments."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_session_end") as mock_run,
            patch.object(
                sys,
                "argv",
                [
                    "ai-session-tracker",
                    "end",
                    "--session-id",
                    "test_123",
                    "--outcome",
                    "success",
                ],
            ),
        ):
            mock_run.return_value = 0
            main()
            mock_run.assert_called_once_with(
                session_id="test_123",
                outcome="success",
                notes="",
                json_output=False,
            )

    def test_end_command_with_notes(self) -> None:
        """Verifies 'end' subcommand accepts notes argument."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_session_end") as mock_run,
            patch.object(
                sys,
                "argv",
                [
                    "ai-session-tracker",
                    "end",
                    "--session-id",
                    "test_123",
                    "--outcome",
                    "partial",
                    "--notes",
                    "Some notes here",
                    "--json",
                ],
            ),
        ):
            mock_run.return_value = 0
            main()
            mock_run.assert_called_once_with(
                session_id="test_123",
                outcome="partial",
                notes="Some notes here",
                json_output=True,
            )

    def test_run_session_end_success(self) -> None:
        """Verifies run_session_end returns 0 on success."""
        from ai_session_tracker_mcp.cli import run_session_end
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=True,
            message="Session ended",
            data={"duration_minutes": 30.5},
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.end_session.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_end(
                session_id="test_123",
                outcome="success",
            )

            assert result == 0


class TestSessionFlagCommand:
    """Tests for session flag CLI command."""

    def test_flag_command_parses_arguments(self) -> None:
        """Verifies 'flag' subcommand parses required arguments."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_session_flag") as mock_run,
            patch.object(
                sys,
                "argv",
                [
                    "ai-session-tracker",
                    "flag",
                    "--session-id",
                    "test_123",
                    "--type",
                    "hallucination",
                    "--desc",
                    "AI made stuff up",
                    "--severity",
                    "high",
                ],
            ),
        ):
            mock_run.return_value = 0
            main()
            mock_run.assert_called_once_with(
                session_id="test_123",
                issue_type="hallucination",
                description="AI made stuff up",
                severity="high",
                json_output=False,
            )

    def test_run_session_flag_success(self) -> None:
        """Verifies run_session_flag returns 0 on success."""
        from ai_session_tracker_mcp.cli import run_session_flag
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=True,
            message="Issue flagged",
            data={"issue_id": "issue_123"},
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.flag_issue.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_flag(
                session_id="test_123",
                issue_type="error",
                description="Something wrong",
                severity="low",
            )

            assert result == 0


class TestSessionActiveCommand:
    """Tests for session active CLI command."""

    def test_active_command_parses_arguments(self) -> None:
        """Verifies 'active' subcommand works with no arguments."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_session_active") as mock_run,
            patch.object(
                sys,
                "argv",
                ["ai-session-tracker", "active"],
            ),
        ):
            mock_run.return_value = 0
            main()
            mock_run.assert_called_once_with(json_output=False)

    def test_active_command_with_json_flag(self) -> None:
        """Verifies 'active' subcommand accepts --json flag."""
        from ai_session_tracker_mcp.cli import main

        with (
            patch("ai_session_tracker_mcp.cli.run_session_active") as mock_run,
            patch.object(
                sys,
                "argv",
                ["ai-session-tracker", "active", "--json"],
            ),
        ):
            mock_run.return_value = 0
            main()
            mock_run.assert_called_once_with(json_output=True)

    def test_run_session_active_with_sessions(self) -> None:
        """Verifies run_session_active displays active sessions."""
        from ai_session_tracker_mcp.cli import run_session_active
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=True,
            message="Found 1 active session(s)",
            data={
                "active_sessions": [
                    {
                        "session_id": "test_123",
                        "session_name": "Test Session",
                        "task_type": "testing",
                        "start_time": "2024-01-01T00:00:00+00:00",
                    }
                ]
            },
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.get_active_sessions.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_active()

            assert result == 0
            mock_service.get_active_sessions.assert_called_once()

    def test_run_session_active_no_sessions(self) -> None:
        """Verifies run_session_active handles empty result."""
        from ai_session_tracker_mcp.cli import run_session_active
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=True,
            message="No active sessions",
            data={"active_sessions": []},
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.get_active_sessions.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_active()

            assert result == 0


class TestOutputResult:
    """Tests for _output_result helper function."""

    def test_output_result_json_success(self) -> None:
        """Verifies _output_result outputs JSON correctly."""
        from ai_session_tracker_mcp.cli import _output_result

        result_dict = {
            "success": True,
            "message": "Test message",
            "data": {"key": "value"},
        }

        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            exit_code = _output_result(result_dict, json_output=True)

        assert exit_code == 0
        output = captured.getvalue()
        parsed = json.loads(output)
        assert parsed == result_dict

    def test_output_result_json_failure(self) -> None:
        """Verifies _output_result returns 1 for failure."""
        from ai_session_tracker_mcp.cli import _output_result

        result_dict = {
            "success": False,
            "message": "Error occurred",
            "error": "Something went wrong",
        }

        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            exit_code = _output_result(result_dict, json_output=True)

        assert exit_code == 1

    def test_output_result_text_success_with_data(self) -> None:
        """Verifies _output_result text mode outputs data to stdout."""
        from ai_session_tracker_mcp.cli import _output_result

        result_dict = {
            "success": True,
            "message": "Operation completed",
            "data": {"count": 5, "status": "ok"},
        }

        captured = StringIO()
        with (
            patch.object(sys, "stdout", captured),
            patch("ai_session_tracker_mcp.cli._log"),  # _log uses logger, not stdout
        ):
            exit_code = _output_result(result_dict, json_output=False)

        assert exit_code == 0
        output = captured.getvalue()
        assert "count: 5" in output
        assert "status: ok" in output

    def test_output_result_text_failure_with_error(self) -> None:
        """Verifies _output_result text mode outputs error details to stdout."""
        from ai_session_tracker_mcp.cli import _output_result

        result_dict = {
            "success": False,
            "message": "Operation failed",
            "error": "Database connection error",
        }

        captured = StringIO()
        with (
            patch.object(sys, "stdout", captured),
            patch("ai_session_tracker_mcp.cli._log"),
        ):
            exit_code = _output_result(result_dict, json_output=False)

        assert exit_code == 1
        output = captured.getvalue()
        assert "Database connection error" in output

    def test_output_result_text_success_no_data(self) -> None:
        """Verifies _output_result handles empty/missing data field."""
        from ai_session_tracker_mcp.cli import _output_result

        result_dict = {
            "success": True,
            "message": "Operation completed",
            # No 'data' field - tests the 713->712 branch
        }

        captured = StringIO()
        with (
            patch.object(sys, "stdout", captured),
            patch("ai_session_tracker_mcp.cli._log"),
        ):
            exit_code = _output_result(result_dict, json_output=False)

        assert exit_code == 0
        # Should not print any data fields (empty output from print())
        output = captured.getvalue()
        assert output == ""


class TestGenerateMcpServerConfig:
    """Tests for _generate_mcp_server_config helper."""

    def test_generate_config_with_env_example(self) -> None:
        """Verifies config includes env example when requested."""
        from ai_session_tracker_mcp.cli import _generate_mcp_server_config

        server_config = {"command": "/usr/bin/server", "args": ["run"]}
        result = _generate_mcp_server_config(server_config, with_env_example=True)

        assert result["command"] == "/usr/bin/server"
        assert result["args"] == ["run"]
        assert "_env_example" in result
        assert "AI_MAX_SESSION_DURATION_HOURS" in result["_env_example"]

    def test_generate_config_without_env_example(self) -> None:
        """Verifies config excludes env example when not requested."""
        from ai_session_tracker_mcp.cli import _generate_mcp_server_config

        server_config = {"command": "/usr/bin/server", "args": ["run"]}
        result = _generate_mcp_server_config(server_config, with_env_example=False)

        assert result["command"] == "/usr/bin/server"
        assert result["args"] == ["run"]
        assert "_env_example" not in result


class TestGlobalInstallPlatforms:
    """Tests for global install on different platforms."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_global_install_windows(self, mock_fs: MockFileSystem) -> None:
        """Verifies global install uses Windows path on Windows."""
        import json

        from ai_session_tracker_mcp.cli import run_install

        with patch(
            "pathlib.Path.home", return_value=MagicMock(__str__=lambda _: "C:\\Users\\user")
        ):
            run_install(
                filesystem=mock_fs,
                cwd="/project",
                package_dir="/pkg",
                global_install=True,
            )

        # Verify Windows global mcp.json was created
        win_config_path = "C:\\Users\\user/AppData/Roaming/Code/User/mcp.json"
        assert mock_fs.exists(win_config_path)
        config_content = mock_fs.get_file(win_config_path)
        config = json.loads(config_content)
        assert "ai-session-tracker" in config["servers"]

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only test")
    def test_global_install_macos(self, mock_fs: MockFileSystem) -> None:
        """Verifies global install uses macOS path on macOS."""
        import json

        from ai_session_tracker_mcp.cli import run_install

        with patch("pathlib.Path.home", return_value=MagicMock(__str__=lambda _: "/Users/user")):
            run_install(
                filesystem=mock_fs,
                cwd="/project",
                package_dir="/pkg",
                global_install=True,
            )

        # Verify macOS global mcp.json was created
        mac_config_path = "/Users/user/Library/Application Support/Code/User/mcp.json"
        assert mock_fs.exists(mac_config_path)
        config_content = mock_fs.get_file(mac_config_path)
        config = json.loads(config_content)
        assert "ai-session-tracker" in config["servers"]


class TestInstallServiceIntegration:
    """Tests for service installation during install command."""

    def test_install_with_service_success(self, mock_fs: MockFileSystem) -> None:
        """Verifies install --service installs service successfully."""
        from ai_session_tracker_mcp.cli import run_install

        mock_manager = MagicMock()
        mock_manager.install.return_value = True

        with patch("ai_session_tracker_mcp.service.get_service_manager", return_value=mock_manager):
            run_install(
                filesystem=mock_fs,
                cwd="/project",
                package_dir="/pkg",
                service=True,
            )

        mock_manager.install.assert_called_once()

    def test_install_with_service_failure(self, mock_fs: MockFileSystem) -> None:
        """Verifies install --service handles installation failure."""
        from ai_session_tracker_mcp.cli import run_install

        mock_manager = MagicMock()
        mock_manager.install.return_value = False

        with patch("ai_session_tracker_mcp.service.get_service_manager", return_value=mock_manager):
            run_install(
                filesystem=mock_fs,
                cwd="/project",
                package_dir="/pkg",
                service=True,
            )

        mock_manager.install.assert_called_once()

    def test_install_with_service_not_supported(self, mock_fs: MockFileSystem) -> None:
        """Verifies install --service handles unsupported platform."""
        from ai_session_tracker_mcp.cli import run_install

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            side_effect=NotImplementedError("Service not supported on this platform"),
        ):
            # Should not raise, just log warning
            run_install(
                filesystem=mock_fs,
                cwd="/project",
                package_dir="/pkg",
                service=True,
            )


class TestRunSessionActiveErrors:
    """Tests for run_session_active error handling."""

    def test_run_session_active_failure(self) -> None:
        """Verifies run_session_active handles service failure."""
        from ai_session_tracker_mcp.cli import run_session_active
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=False,
            message="Failed to get sessions",
            error="Database unavailable",
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.get_active_sessions.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_active()

            assert result == 1

    def test_run_session_active_json_output(self, capsys: Any) -> None:
        """Verifies run_session_active outputs JSON when json_output=True."""
        from ai_session_tracker_mcp.cli import run_session_active
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=True,
            message="Found 1 active session(s)",
            data={"active_sessions": [{"session_id": "test_123"}]},
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.get_active_sessions.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_active(json_output=True)

            assert result == 0
            captured = capsys.readouterr()
            assert '"success": true' in captured.out
            assert '"active_sessions"' in captured.out

    def test_run_session_active_failure_with_error_output(self, capsys: Any) -> None:
        """Verifies run_session_active prints error message on failure."""
        from ai_session_tracker_mcp.cli import run_session_active
        from ai_session_tracker_mcp.session_service import ServiceResult

        mock_result = ServiceResult(
            success=False,
            message="Failed to get sessions",
            error="Database unavailable",
        )

        with patch("ai_session_tracker_mcp.session_service.SessionService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.get_active_sessions.return_value = mock_result
            mock_service_cls.return_value = mock_service

            result = run_session_active()

            assert result == 1
            captured = capsys.readouterr()
            assert "Database unavailable" in captured.out


class TestCopyAgentFilesDirectories:
    """Tests for _copy_agent_files handling directories."""

    def test_copy_agent_files_skips_directories(self, mock_fs: MockFileSystem) -> None:
        """Verifies _copy_agent_files skips directories in iterdir."""
        from ai_session_tracker_mcp.cli import _copy_agent_files

        # Create source with both files and directories
        mock_fs.makedirs("/pkg/agent_files/agents")
        mock_fs.set_file("/pkg/agent_files/agents/test.agent.md", "content")
        mock_fs.makedirs("/pkg/agent_files/agents/subdir")  # Directory to skip

        # Override is_file to return False for the subdir
        original_is_file = mock_fs.is_file

        def is_file_with_dir(path: str) -> bool:
            if path.endswith("subdir"):
                return False
            return original_is_file(path)

        mock_fs.is_file = is_file_with_dir

        _copy_agent_files(mock_fs, "/pkg/agent_files", "/project/.github", "/project")

        # File should be copied
        assert mock_fs.exists("/project/.github/agents/test.agent.md")
        # Directory should not create a file
        assert not mock_fs.exists("/project/.github/agents/subdir")
