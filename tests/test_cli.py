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

    def test_run_install_overwrites_existing_agent_files(self, mock_fs: MockFileSystem) -> None:
        """Verifies run_install overwrites existing agent files with latest.

        Tests that install always copies the latest bundled files over
        existing ones — these are package-managed, not user-editable.

        Business context:
        Agent files define required params and protocols. When the package
        updates (e.g., making developer/project required), existing installs
        must get the new files to stay in sync.

        Arrangement:
        Set up both source and destination files in mock filesystem.

        Action:
        Call run_install function.

        Assertion Strategy:
        Validates existing file content is replaced with new content.
        """
        from ai_session_tracker_mcp.cli import run_install

        # Set up bundled agent files
        mock_fs.makedirs("/pkg/agent_files/agents", exist_ok=True)
        mock_fs.set_file("/pkg/agent_files/agents/test.agent.md", "# New Content")

        # Set up existing file at destination
        mock_fs.makedirs("/project/.github/agents", exist_ok=True)
        mock_fs.set_file("/project/.github/agents/test.agent.md", "# Existing Content")

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        # Verify content was updated to new version
        assert mock_fs.get_file("/project/.github/agents/test.agent.md") == "# New Content"

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
        assert server_config["args"] == [
            "-m",
            "ai_session_tracker_mcp",
            "server",
            "--dashboard-host",
            "127.0.0.1",
            "--dashboard-port",
            "8000",
        ]
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
                    "args": [
                        "-m",
                        "ai_session_tracker_mcp",
                        "server",
                        "--dashboard-host",
                        "127.0.0.1",
                        "--dashboard-port",
                        "8000",
                    ],
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

    def test_run_install_writes_ai_sessions_yaml(self, mock_fs: MockFileSystem) -> None:
        """Verifies run_install creates .ai_sessions.yaml with project name derived from cwd.

        Tests that the install command auto-generates a project configuration file
        using the current working directory's basename as the project identifier.

        Business context:
        .ai_sessions.yaml stores the project name so agents can auto-populate
        the project field in session metadata without manual input. This reduces
        friction for first-time users by providing sensible defaults.

        Arrangement:
        1. Use mock filesystem to isolate file operations.
        2. Set cwd to '/project/my-api' so basename 'my-api' becomes project name.

        Action:
        Call run_install with default parameters, letting it auto-create the yaml file.

        Assertion Strategy:
        Validates file creation and content by confirming:
        - The .ai_sessions.yaml file exists in the project root.
        - The file contains 'project: my-api' derived from the directory name.

        Testing Principle:
        Validates convention-over-configuration, ensuring zero-touch project setup.
        """
        from ai_session_tracker_mcp.cli import run_install

        run_install(filesystem=mock_fs, cwd="/project/my-api", package_dir="/pkg")

        yaml_content = mock_fs.get_file("/project/my-api/.ai_sessions.yaml")
        assert yaml_content is not None
        assert "project: my-api" in yaml_content

    def test_run_install_skips_existing_ai_sessions_yaml(self, mock_fs: MockFileSystem) -> None:
        """Verifies run_install preserves existing .ai_sessions.yaml without overwriting.

        Tests that re-running install on a project with a pre-existing configuration
        file leaves the user's customizations intact.

        Business context:
        Users may customize .ai_sessions.yaml (e.g., rename project, add settings).
        The install command must not overwrite manual customizations, as this would
        destroy user work and erode trust in the tool's non-destructive behavior.

        Arrangement:
        1. Pre-create .ai_sessions.yaml with custom content 'project: custom-name'.
        2. Use mock filesystem to track file state across the install operation.

        Action:
        Call run_install on the same project directory that already has the yaml file.

        Assertion Strategy:
        Validates idempotency by confirming:
        - The yaml file content remains exactly 'project: custom-name\\n'.
        - No truncation, append, or replacement occurred.

        Testing Principle:
        Validates non-destructive idempotency, ensuring repeated installs are safe.
        """
        from ai_session_tracker_mcp.cli import run_install

        # Pre-create a customized .ai_sessions.yaml
        mock_fs.write_text("/project/.ai_sessions.yaml", "project: custom-name\n")

        run_install(filesystem=mock_fs, cwd="/project", package_dir="/pkg")

        yaml_content = mock_fs.get_file("/project/.ai_sessions.yaml")
        assert yaml_content == "project: custom-name\n"

    def test_run_install_global_skips_ai_sessions_yaml(self, mock_fs: MockFileSystem) -> None:
        """Verifies global install does not create .ai_sessions.yaml in the project directory.

        Tests that when --global flag is used, the install targets shared VS Code
        settings rather than creating project-specific configuration files.

        Business context:
        Global installs target a shared VS Code settings directory, not any
        specific project root, so .ai_sessions.yaml is not applicable. Creating
        it would be misleading since global installs are project-agnostic.

        Arrangement:
        1. Mock Path.home() to control the home directory path.
        2. Use mock filesystem to verify no yaml file is created.

        Action:
        Call run_install with global_install=True to trigger global install path.

        Assertion Strategy:
        Validates scope separation by confirming:
        - No .ai_sessions.yaml exists in the project directory after global install.
        - Global install path diverges from local install behavior.

        Testing Principle:
        Validates install mode isolation, ensuring global installs don't leak
        project-level artifacts.
        """
        from ai_session_tracker_mcp.cli import run_install

        with patch("pathlib.Path.home", return_value=MagicMock(__str__=lambda _: "/home/user")):
            run_install(
                filesystem=mock_fs,
                cwd="/project",
                package_dir="/pkg",
                global_install=True,
            )

        assert not mock_fs.exists("/project/.ai_sessions.yaml")


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
        """Verifies run_service stop returns exit code 0 on successful service shutdown.

        Tests that the service stop action delegates to the service manager's stop
        method and translates a True result into a zero exit code.

        Business context:
        Service stop must communicate success clearly via exit codes so that
        shell scripts and automation tools can chain operations reliably.

        Arrangement:
        1. Create mock service manager with stop() returning True (success).
        2. Patch get_service_manager to return the mock.

        Action:
        Call run_service('stop') to trigger the stop action path.

        Assertion Strategy:
        Validates successful stop by confirming:
        - Return code is 0 (success).
        - mock_manager.stop() was called exactly once.

        Testing Principle:
        Validates exit code contract, ensuring success maps to zero exit.
        """
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
        """Verifies run_service stop returns exit code 1 when service fails to stop.

        Tests that the stop action translates a False result from the service
        manager into a non-zero exit code indicating failure.

        Business context:
        Service stop failure (e.g., permission denied, PID stale) must be
        communicated via exit code so callers can handle errors appropriately.

        Arrangement:
        1. Create mock service manager with stop() returning False (failure).
        2. Patch get_service_manager to return the mock.

        Action:
        Call run_service('stop') to trigger the stop action path.

        Assertion Strategy:
        Validates failure signaling by confirming:
        - Return code is 1 (failure).

        Testing Principle:
        Validates error propagation, ensuring failures are not silently swallowed.
        """
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
        """Verifies run_service status queries and returns service state information.

        Tests that the status action delegates to the service manager's status
        method and returns exit code 0 after successfully retrieving status info.

        Business context:
        Service status is critical for operational monitoring. Users and scripts
        need to query whether the background service is installed and running.

        Arrangement:
        1. Create mock service manager returning a status dict with installed,
           running, and status fields.
        2. Patch get_service_manager to return the mock.

        Action:
        Call run_service('status') to query the current service state.

        Assertion Strategy:
        Validates status retrieval by confirming:
        - Return code is 0 (successful query).
        - mock_manager.status() was called exactly once.

        Testing Principle:
        Validates query path, ensuring status checks complete without side effects.
        """
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
        """Verifies run_service uninstall returns exit code 0 on successful removal.

        Tests that the uninstall action delegates to the service manager's uninstall
        method and translates a True result into a zero exit code.

        Business context:
        Clean service removal is essential for users who want to switch to manual
        session tracking or uninstall the tool entirely without leaving orphan services.

        Arrangement:
        1. Create mock service manager with uninstall() returning True.
        2. Patch get_service_manager to return the mock.

        Action:
        Call run_service('uninstall') to trigger the uninstall path.

        Assertion Strategy:
        Validates successful uninstall by confirming:
        - Return code is 0 (success).
        - mock_manager.uninstall() was called exactly once.

        Testing Principle:
        Validates cleanup contract, ensuring uninstall completes and signals success.
        """
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
        """Verifies run_service uninstall returns exit code 1 on failure.

        Tests that a failed uninstall (e.g., service files locked, permission denied)
        is properly communicated through the exit code.

        Business context:
        Failed uninstalls can leave stale service configurations. Proper error
        signaling lets callers alert users or retry with elevated permissions.

        Arrangement:
        1. Create mock service manager with uninstall() returning False.
        2. Patch get_service_manager to return the mock.

        Action:
        Call run_service('uninstall') to trigger the uninstall failure path.

        Assertion Strategy:
        Validates failure signaling by confirming:
        - Return code is 1 (failure).

        Testing Principle:
        Validates error exit code contract for uninstall failures.
        """
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
        """Verifies run_service handles unsupported platform gracefully with exit code 1.

        Tests that when get_service_manager raises NotImplementedError (e.g., on an
        unsupported OS like FreeBSD), run_service catches it and returns a failure code.

        Business context:
        The service feature is platform-specific (Linux systemd, macOS launchd).
        Users on unsupported platforms need a clear error rather than a crash.

        Arrangement:
        1. Patch get_service_manager to raise NotImplementedError('Unsupported').
        2. This simulates running on a platform without service support.

        Action:
        Call run_service('status') which triggers the manager lookup.

        Assertion Strategy:
        Validates graceful degradation by confirming:
        - Return code is 1 (error, not exception propagation).
        - No unhandled exception escapes the function.

        Testing Principle:
        Validates defensive error handling for platform-dependent features.
        """
        from ai_session_tracker_mcp.cli import run_service

        with patch(
            "ai_session_tracker_mcp.service.get_service_manager",
            side_effect=NotImplementedError("Unsupported"),
        ):
            result = run_service("status")
            assert result == 1

    def test_run_service_unknown_action(self) -> None:
        """Verifies run_service returns exit code 1 for unrecognized action strings.

        Tests that passing an invalid action (not start/stop/status/uninstall) to
        run_service is handled as an error rather than causing attribute errors.

        Business context:
        The CLI validates actions at the argparse level, but run_service must
        also handle invalid actions defensively for direct callers and future
        refactoring safety.

        Arrangement:
        1. Create a mock service manager (no specific method expectations).
        2. Patch get_service_manager to return the mock.

        Action:
        Call run_service('invalid') with a non-existent action string.

        Assertion Strategy:
        Validates input validation by confirming:
        - Return code is 1 (error for unknown action).

        Testing Principle:
        Validates robustness against invalid inputs at the function boundary.
        """
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
        """Verifies 'start' subcommand correctly parses all required CLI arguments.

        Tests that the argparse configuration for the 'start' subcommand properly
        maps --name, --type, --model, --mins, and --source flags to the
        run_session_start function parameters.

        Business context:
        Session start requires specific parameters for tracking. Correct argument
        parsing ensures session metadata is captured accurately from the first
        interaction, which is critical for analytics and billing.

        Arrangement:
        1. Mock run_session_start to capture the parsed arguments.
        2. Set sys.argv with all required flags and values.

        Action:
        Call main() to trigger argparse and route to the start subcommand.

        Assertion Strategy:
        Validates argument parsing by confirming:
        - run_session_start called exactly once with correct keyword arguments.
        - Each flag maps to the expected parameter name and value.
        - Default values applied for optional args (context='', developer='', project='').

        Testing Principle:
        Validates CLI contract, ensuring user-facing flags match internal API parameters.
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
                developer="",
                project="",
                json_output=False,
            )
            assert result == 0

    def test_start_command_with_optional_args(self) -> None:
        """Verifies 'start' subcommand accepts and passes optional arguments correctly.

        Tests that optional flags like --context and --json are properly parsed
        and forwarded to run_session_start alongside required arguments.

        Business context:
        Optional context and JSON output mode enhance session tracking flexibility.
        Context provides additional metadata for analysis, while JSON output enables
        programmatic integration with other tools.

        Arrangement:
        1. Mock run_session_start to capture the parsed arguments.
        2. Set sys.argv with all required flags plus --context and --json.

        Action:
        Call main() to trigger argparse with the extended argument set.

        Assertion Strategy:
        Validates optional argument handling by confirming:
        - context parameter receives the provided string value.
        - json_output is True when --json flag is present.
        - Required arguments are still correctly parsed alongside optional ones.

        Testing Principle:
        Validates extensibility of CLI interface, ensuring optional args don't
        interfere with required argument parsing.
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
                developer="",
                project="",
                json_output=True,
            )

    def test_run_session_start_success(self) -> None:
        """Verifies run_session_start returns exit code 0 when session creation succeeds.

        Tests the happy path where the SessionService successfully creates a new
        session and the CLI function translates this into a zero exit code.

        Business context:
        Session start is the entry point for all tracking. A successful start
        means the session was persisted and can receive subsequent log/flag/end
        operations. Exit code 0 signals to callers that tracking is active.

        Arrangement:
        1. Create a ServiceResult with success=True and a session_id in data.
        2. Mock SessionService to return this result from start_session.

        Action:
        Call run_session_start with valid parameters to trigger session creation.

        Assertion Strategy:
        Validates successful creation by confirming:
        - Return code is 0 (success).
        - start_session was called exactly once on the service.

        Testing Principle:
        Validates happy-path exit code contract for session lifecycle operations.
        """
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
        """Verifies run_session_start returns exit code 1 when session creation fails.

        Tests the error path where the SessionService reports failure (e.g., invalid
        parameters) and the CLI function translates this into a non-zero exit code.

        Business context:
        Invalid session parameters (bad task type, missing fields) must be
        caught early and reported. A non-zero exit code allows automation to
        detect and handle failed session starts.

        Arrangement:
        1. Create a ServiceResult with success=False and error details.
        2. Mock SessionService to return this failure result.

        Action:
        Call run_session_start with parameters that trigger a service-level failure.

        Assertion Strategy:
        Validates failure propagation by confirming:
        - Return code is 1 (failure).

        Testing Principle:
        Validates error propagation from service layer to CLI exit code.
        """
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
        """Verifies 'log' subcommand correctly parses all required CLI arguments.

        Tests that the argparse configuration for the 'log' subcommand properly
        maps --session-id, --prompt, --summary, and --rating flags to the
        run_session_log function parameters.

        Business context:
        Interaction logging captures the details of each AI prompt/response cycle.
        Accurate argument parsing ensures session history is faithfully recorded
        for later analysis and quality assessment.

        Arrangement:
        1. Mock run_session_log to capture the parsed arguments.
        2. Set sys.argv with all required flags and values.

        Action:
        Call main() to trigger argparse and route to the log subcommand.

        Assertion Strategy:
        Validates argument parsing by confirming:
        - run_session_log called with correct keyword arguments.
        - Default values applied for optional args (iterations=1, tools=[]).

        Testing Principle:
        Validates CLI contract for the interaction logging interface.
        """
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
        """Verifies 'log' subcommand accepts optional arguments like --iterations, --tools, --json.

        Tests that extended flags for iteration count, tool list, and JSON output
        are properly parsed and forwarded alongside required arguments.

        Business context:
        Detailed interaction logs (iteration count, tools used) provide richer
        analytics on AI session patterns. JSON output enables machine-readable
        integration with dashboards and CI/CD pipelines.

        Arrangement:
        1. Mock run_session_log to capture all parsed arguments.
        2. Set sys.argv with required flags plus --iterations, --tools, and --json.

        Action:
        Call main() to trigger argparse with the extended argument set.

        Assertion Strategy:
        Validates optional argument handling by confirming:
        - iterations=3 parsed from --iterations flag.
        - tools=['read_file', 'grep_search'] parsed as a list from --tools.
        - json_output=True when --json flag is present.

        Testing Principle:
        Validates variadic argument parsing (--tools accepts multiple values).
        """
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
        """Verifies run_session_log returns exit code 0 when interaction logging succeeds.

        Tests the happy path where the SessionService successfully logs an
        interaction and the CLI function returns a zero exit code.

        Business context:
        Each logged interaction represents a prompt/response cycle. Successful
        logging ensures the session history is complete for post-session review
        and quality metrics.

        Arrangement:
        1. Create a ServiceResult with success=True and interaction_id in data.
        2. Mock SessionService to return this result from log_interaction.

        Action:
        Call run_session_log with valid session_id, prompt, summary, and rating.

        Assertion Strategy:
        Validates successful logging by confirming:
        - Return code is 0 (success).

        Testing Principle:
        Validates happy-path exit code for the interaction logging operation.
        """
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
        """Verifies 'end' subcommand correctly parses required --session-id and --outcome flags.

        Tests that the argparse configuration for the 'end' subcommand maps
        required flags to run_session_end parameters with correct defaults.

        Business context:
        Session end marks the completion of an AI work session. Accurate parsing
        of session ID and outcome is essential for duration calculation, outcome
        tracking, and session lifecycle integrity.

        Arrangement:
        1. Mock run_session_end to capture the parsed arguments.
        2. Set sys.argv with --session-id and --outcome flags.

        Action:
        Call main() to trigger argparse and route to the end subcommand.

        Assertion Strategy:
        Validates argument parsing by confirming:
        - session_id and outcome are correctly mapped.
        - Default values applied (notes='', final_estimate_minutes=None, json_output=False).

        Testing Principle:
        Validates CLI contract for session termination, ensuring clean lifecycle transitions.
        """
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
                final_estimate_minutes=None,
                json_output=False,
            )

    def test_end_command_with_notes(self) -> None:
        """Verifies 'end' subcommand accepts --notes and --json optional arguments.

        Tests that optional flags for session notes and JSON output are properly
        parsed and forwarded alongside the required session-id and outcome.

        Business context:
        Session notes capture developer retrospective comments about the AI session,
        which are valuable for qualitative analysis. JSON output supports automation
        that processes session completion events programmatically.

        Arrangement:
        1. Mock run_session_end to capture all parsed arguments.
        2. Set sys.argv with required flags plus --notes and --json.

        Action:
        Call main() to trigger argparse with the extended argument set.

        Assertion Strategy:
        Validates optional argument handling by confirming:
        - notes parameter receives the provided string value.
        - json_output is True when --json flag is present.
        - outcome is correctly parsed as 'partial'.

        Testing Principle:
        Validates optional argument coexistence with required arguments.
        """
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
                final_estimate_minutes=None,
                json_output=True,
            )

    def test_run_session_end_success(self) -> None:
        """Verifies run_session_end returns exit code 0 when session termination succeeds.

        Tests the happy path where the SessionService successfully ends a session,
        calculates duration, and the CLI function returns a zero exit code.

        Business context:
        Session end triggers duration calculation and outcome recording. A
        successful end means all session data is finalized and available for
        analytics dashboards and reports.

        Arrangement:
        1. Create a ServiceResult with success=True and duration_minutes in data.
        2. Mock SessionService to return this result from end_session.

        Action:
        Call run_session_end with valid session_id and outcome.

        Assertion Strategy:
        Validates successful termination by confirming:
        - Return code is 0 (success).

        Testing Principle:
        Validates happy-path exit code for session lifecycle completion.
        """
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
        """Verifies 'flag' subcommand correctly parses --session-id, --type, --desc, --severity.

        Tests that the argparse configuration for the 'flag' subcommand properly
        maps all required flags to run_session_flag function parameters.

        Business context:
        Issue flagging captures quality problems like hallucinations, incorrect code,
        or performance issues during AI sessions. Accurate parsing ensures each flag
        is categorized and attributed to the correct session for quality auditing.

        Arrangement:
        1. Mock run_session_flag to capture the parsed arguments.
        2. Set sys.argv with --session-id, --type, --desc, and --severity flags.

        Action:
        Call main() to trigger argparse and route to the flag subcommand.

        Assertion Strategy:
        Validates argument parsing by confirming:
        - All four required parameters are correctly mapped.
        - issue_type maps from --type flag (note the name remapping).
        - json_output defaults to False when --json is absent.

        Testing Principle:
        Validates CLI argument name mapping, especially --type to issue_type remapping.
        """
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
        """Verifies run_session_flag returns exit code 0 when issue flagging succeeds.

        Tests the happy path where the SessionService successfully records a quality
        issue against a session and the CLI function returns a zero exit code.

        Business context:
        Issue flags are the primary mechanism for tracking AI quality problems.
        Successful flagging ensures issues are persisted and can be aggregated
        for model quality scoring and regression detection.

        Arrangement:
        1. Create a ServiceResult with success=True and issue_id in data.
        2. Mock SessionService to return this result from flag_issue.

        Action:
        Call run_session_flag with valid session_id, issue_type, description, severity.

        Assertion Strategy:
        Validates successful flagging by confirming:
        - Return code is 0 (success).

        Testing Principle:
        Validates happy-path exit code for the quality flagging operation.
        """
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
        """Verifies 'active' subcommand works with no arguments using defaults.

        Tests that the 'active' subcommand can be invoked without any flags,
        using default values for json_output.

        Business context:
        Checking active sessions is a frequent developer operation. The command
        should work with zero arguments for quick status checks, lowering the
        barrier to session awareness.

        Arrangement:
        1. Mock run_session_active to capture the parsed arguments.
        2. Set sys.argv with only the 'active' subcommand (no flags).

        Action:
        Call main() to trigger argparse and route to the active subcommand.

        Assertion Strategy:
        Validates default argument handling by confirming:
        - run_session_active called with json_output=False (default).

        Testing Principle:
        Validates zero-argument usability for the most common query operation.
        """
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
        """Verifies 'active' subcommand accepts --json flag for machine-readable output.

        Tests that the --json flag is correctly parsed and forwarded to
        run_session_active for programmatic consumption of active session data.

        Business context:
        JSON output enables integration with monitoring dashboards, IDE extensions,
        and CI/CD pipelines that need to query active session state programmatically.

        Arrangement:
        1. Mock run_session_active to capture the parsed arguments.
        2. Set sys.argv with 'active' subcommand and --json flag.

        Action:
        Call main() to trigger argparse with the --json flag.

        Assertion Strategy:
        Validates JSON flag parsing by confirming:
        - run_session_active called with json_output=True.

        Testing Principle:
        Validates output format toggle for machine-readable integration support.
        """
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
        """Verifies run_session_active displays active sessions and returns exit code 0.

        Tests the happy path where active sessions exist and the function
        successfully retrieves and outputs them.

        Business context:
        Active session listing lets developers see what AI sessions are in progress,
        enabling them to resume tracking or detect orphaned sessions that need cleanup.

        Arrangement:
        1. Create a ServiceResult with one active session containing session_id,
           session_name, task_type, and start_time.
        2. Mock SessionService to return this result from get_active_sessions.

        Action:
        Call run_session_active with default parameters (text output mode).

        Assertion Strategy:
        Validates session retrieval by confirming:
        - Return code is 0 (success).
        - get_active_sessions was called exactly once on the service.

        Testing Principle:
        Validates query-and-display path for active session monitoring.
        """
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
        """Verifies run_session_active handles empty session list gracefully.

        Tests that when no active sessions exist, the function still returns
        success (exit code 0) with an empty result set.

        Business context:
        No active sessions is a normal state, not an error. The CLI must
        distinguish between 'no sessions found' (success with empty data) and
        'query failed' (error), as callers rely on exit codes for control flow.

        Arrangement:
        1. Create a ServiceResult with success=True and empty active_sessions list.
        2. Mock SessionService to return this result.

        Action:
        Call run_session_active with default parameters.

        Assertion Strategy:
        Validates empty-result handling by confirming:
        - Return code is 0 (success, not error).

        Testing Principle:
        Validates empty-set semantics, ensuring absence of data is not treated as failure.
        """
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
        """Verifies _output_result outputs well-formed JSON to stdout on success.

        Tests that when json_output=True, the result dict is serialized as valid
        JSON and the function returns exit code 0 for successful results.

        Business context:
        JSON output mode is used by IDE extensions, scripts, and CI/CD pipelines
        that parse CLI output programmatically. Malformed JSON would break all
        downstream integrations.

        Arrangement:
        1. Create a result dict with success=True, message, and data fields.
        2. Capture stdout via StringIO to inspect the JSON output.

        Action:
        Call _output_result with the result dict and json_output=True.

        Assertion Strategy:
        Validates JSON serialization by confirming:
        - Exit code is 0 (success).
        - Output is valid JSON (json.loads succeeds).
        - Parsed JSON matches the original result dict exactly.

        Testing Principle:
        Validates output format fidelity for machine-readable integration.
        """
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
        """Verifies _output_result returns exit code 1 for failed results in JSON mode.

        Tests that the JSON serialization still occurs for failed results but
        the function returns a non-zero exit code.

        Business context:
        Failed operations must still produce valid JSON output so that downstream
        tools can parse the error details. The exit code (not the output format)
        signals success vs. failure.

        Arrangement:
        1. Create a result dict with success=False and error details.
        2. Capture stdout via StringIO.

        Action:
        Call _output_result with the failure result and json_output=True.

        Assertion Strategy:
        Validates failure exit code by confirming:
        - Exit code is 1 (failure), independent of output format.

        Testing Principle:
        Validates separation of output format from exit code semantics.
        """
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
        """Verifies _output_result text mode outputs key-value data to stdout.

        Tests that in text mode, successful results with data are formatted as
        human-readable key-value pairs on stdout.

        Business context:
        Text mode is the default for interactive CLI usage. Developers expect
        readable output showing the operation result and relevant data fields
        without needing to parse JSON.

        Arrangement:
        1. Create a result dict with success=True and data containing count and status.
        2. Capture stdout and mock _log to isolate stdout output.

        Action:
        Call _output_result with the result and json_output=False (text mode).

        Assertion Strategy:
        Validates text formatting by confirming:
        - Exit code is 0 (success).
        - Output contains 'count: 5' as a formatted key-value pair.
        - Output contains 'status: ok' as a formatted key-value pair.

        Testing Principle:
        Validates human-readable output format for interactive CLI usage.
        """
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
        """Verifies _output_result text mode outputs error details to stdout on failure.

        Tests that failed results in text mode include the error message in the
        output so users can understand what went wrong.

        Business context:
        Error messages provide actionable feedback to users. When a CLI operation
        fails, the error detail (e.g., 'Database connection error') helps users
        diagnose and resolve the issue without needing --json mode.

        Arrangement:
        1. Create a result dict with success=False and an error field.
        2. Capture stdout and mock _log to isolate output.

        Action:
        Call _output_result with the failure result and json_output=False.

        Assertion Strategy:
        Validates error output by confirming:
        - Exit code is 1 (failure).
        - Output contains the specific error message 'Database connection error'.

        Testing Principle:
        Validates user-facing error messaging for CLI troubleshooting.
        """
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
        """Verifies _output_result text mode handles missing data field gracefully.

        Tests the edge case where a successful result has no 'data' field,
        ensuring no crash or spurious output occurs.

        Business context:
        Some operations (like session end) may succeed without returning data
        beyond the success message. The output function must handle this without
        printing empty or malformed data sections.

        Arrangement:
        1. Create a result dict with success=True but no 'data' key.
        2. Capture stdout and mock _log to isolate output.

        Action:
        Call _output_result with the data-less result and json_output=False.

        Assertion Strategy:
        Validates empty-data handling by confirming:
        - Exit code is 0 (success).
        - Stdout is completely empty (no data fields to print).

        Testing Principle:
        Validates graceful handling of optional/absent response fields.
        """
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
        """Verifies _generate_mcp_server_config includes env block.

        Confirms environment variable block is present when requested.

        Tests that with_env_example=True adds the 'env' key containing
        environment variables that the MCP host will inject into the
        spawned server process.

        Business context:
        Environment variables control runtime behavior (e.g., max session duration,
        output directory). The env block must use the key 'env' (not '_env_example')
        because MCP hosts only inject variables from the 'env' key. See Issue #19.

        Arrangement:
        1. Create a basic server_config dict with command and args.

        Action:
        Call _generate_mcp_server_config with with_env_example=True.

        Assertion Strategy:
        Validates config generation by confirming:
        - Command and args are preserved in the output.
        - 'env' key is present in the result.
        - Known env vars appear in the env block.
        - No '_env_example' key exists (removed in #19 fix).

        Testing Principle:
        Validates configuration enrichment for MCP host compatibility.
        """
        from ai_session_tracker_mcp.cli import _generate_mcp_server_config

        server_config = {"command": "/usr/bin/server", "args": ["run"]}
        result = _generate_mcp_server_config(server_config, with_env_example=True)

        assert result["command"] == "/usr/bin/server"
        assert result["args"] == ["run"]
        assert "env" in result
        assert "AI_MAX_SESSION_DURATION_HOURS" in result["env"]
        assert "AI_OUTPUT_DIR" in result["env"]
        assert "_env_example" not in result

    def test_generate_config_without_env_example(self) -> None:
        """Verifies _generate_mcp_server_config excludes env block.

        Confirms environment variable block is omitted when not requested.

        Tests that with_env_example=False produces a clean config without
        the env key, suitable for minimal deployment.

        Business context:
        Some deployment contexts want a minimal config without default
        env vars. The env block is useful during setup but optional
        for users who configure env vars at the system level.

        Arrangement:
        1. Create a basic server_config dict with command and args.

        Action:
        Call _generate_mcp_server_config with with_env_example=False.

        Assertion Strategy:
        Validates minimal config by confirming:
        - Command and args are preserved in the output.
        - 'env' key is absent from the result.

        Testing Principle:
        Validates conditional config generation for different deployment contexts.
        """
        from ai_session_tracker_mcp.cli import _generate_mcp_server_config

        server_config = {"command": "/usr/bin/server", "args": ["run"]}
        result = _generate_mcp_server_config(server_config, with_env_example=False)

        assert result["command"] == "/usr/bin/server"
        assert result["args"] == ["run"]
        assert "env" not in result


class TestGlobalInstallPlatforms:
    """Tests for global install on different platforms."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_global_install_windows(self, mock_fs: MockFileSystem) -> None:
        """Verifies global install writes MCP config to the Windows-specific VS Code path.

        Tests platform-aware path resolution by running run_install with global_install=True
        on a Windows host and confirming the config lands under AppData/Roaming.

        Business context:
        Users on Windows expect global MCP configuration to follow Windows conventions
        (AppData/Roaming/Code/User); incorrect paths leave VS Code unable to discover the server.

        Arrangement:
        1. Patch Path.home to return a synthetic Windows home directory so the path
           resolver computes the expected AppData location.

        Action:
        Calls run_install with global_install=True, triggering platform detection and
        config file creation.

        Assertion Strategy:
        Validates correct platform routing by confirming:
        - The mcp.json file exists at the Windows-specific global path.
        - The written JSON contains the 'ai-session-tracker' server entry.

        Testing Principle:
        Validates platform-specific behavior isolation, ensuring Windows users receive
        correctly placed configuration without cross-platform path leakage.
        """
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
        """Verifies global install writes MCP config to the macOS-specific VS Code path.

        Tests platform-aware path resolution by running run_install with global_install=True
        on a macOS host and confirming the config lands under Library/Application Support.

        Business context:
        macOS users expect global VS Code configuration under ~/Library/Application Support;
        using the wrong path renders the MCP server invisible to VS Code on Mac.

        Arrangement:
        1. Patch Path.home to return a synthetic macOS home directory so the path
           resolver computes the expected Library/Application Support location.

        Action:
        Calls run_install with global_install=True, triggering platform detection and
        config file creation on macOS.

        Assertion Strategy:
        Validates correct platform routing by confirming:
        - The mcp.json file exists at the macOS-specific global path.
        - The written JSON contains the 'ai-session-tracker' server entry.

        Testing Principle:
        Validates platform-specific behavior isolation, ensuring macOS users receive
        correctly placed configuration distinct from Windows or Linux paths.
        """
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
        """Verifies install --service delegates to the service manager and succeeds.

        Tests the happy-path integration between the install command and the system
        service manager by mocking a successful service installation.

        Business context:
        The --service flag enables automatic background-service registration during
        install; confirming it calls the service manager ensures one-command setup works
        end-to-end for users who want persistent session tracking.

        Arrangement:
        1. Create a mock service manager whose install() returns True (success).
        2. Patch get_service_manager to return this mock.

        Action:
        Calls run_install with service=True, which should detect the flag, obtain a
        service manager, and invoke its install method.

        Assertion Strategy:
        Validates service integration by confirming:
        - The service manager's install method was called exactly once.

        Testing Principle:
        Validates delegation correctness, ensuring the install command properly wires
        through to the platform service layer on success.
        """
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
        """Verifies install --service handles a service installation failure gracefully.

        Tests the failure path where the service manager's install returns False,
        ensuring the install command does not crash or propagate an unhandled error.

        Business context:
        Service installation can fail for many reasons (permissions, missing systemd,
        etc.); the CLI must degrade gracefully so the rest of the install (config files,
        agent files) is not lost.

        Arrangement:
        1. Create a mock service manager whose install() returns False (failure).
        2. Patch get_service_manager to return this mock.

        Action:
        Calls run_install with service=True, triggering the service installation path
        that will encounter the simulated failure.

        Assertion Strategy:
        Validates graceful degradation by confirming:
        - The service manager's install method was called exactly once.
        - No exception propagated to the caller.

        Testing Principle:
        Validates fault tolerance, ensuring partial failures in optional features do not
        abort the overall install workflow.
        """
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
        """Verifies install --service handles an unsupported platform without crashing.

        Tests the edge case where get_service_manager raises NotImplementedError,
        simulating a platform (e.g., BSD, container) that has no service integration.

        Business context:
        Not every OS supports system-service registration; the CLI must warn users
        rather than crash, so the install can still complete its primary purpose of
        writing configuration and agent files.

        Arrangement:
        1. Patch get_service_manager to raise NotImplementedError with a descriptive
           message, simulating an unsupported platform.

        Action:
        Calls run_install with service=True on the simulated unsupported platform.

        Assertion Strategy:
        Validates resilience by confirming:
        - No exception propagates to the caller (implicit: test passes without error).
        - The install continues despite the unsupported service backend.

        Testing Principle:
        Validates defensive error handling, ensuring optional feature failures on
        unsupported platforms are caught and logged rather than raised.
        """
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
        """Verifies run_session_active returns exit code 1 when the service reports failure.

        Tests the error-path return code by supplying a ServiceResult with success=False
        and confirming the CLI function signals failure to the caller.

        Business context:
        Callers (shell scripts, CI pipelines) rely on non-zero exit codes to detect
        failures; returning 0 on error would silently mask database or service issues.

        Arrangement:
        1. Create a ServiceResult with success=False and an error message simulating
           a database-unavailable scenario.
        2. Patch SessionService so get_active_sessions returns this failure result.

        Action:
        Calls run_session_active with default arguments, which delegates to the mocked
        service and receives the failure result.

        Assertion Strategy:
        Validates error signaling by confirming:
        - The return value is 1 (non-zero exit code indicating failure).

        Testing Principle:
        Validates exit-code contract fidelity, ensuring service-layer failures are
        faithfully propagated as CLI error codes.
        """
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
        """Verifies run_session_active emits structured JSON when json_output=True.

        Tests the JSON output mode by supplying a successful ServiceResult with session
        data and confirming the stdout contains valid, expected JSON fields.

        Business context:
        Machine-readable JSON output enables scripting and tool integration (e.g.,
        dashboards, CI checks); malformed or missing JSON breaks downstream consumers.

        Arrangement:
        1. Create a ServiceResult with success=True and a data payload containing one
           active session, simulating a normal query response.
        2. Patch SessionService so get_active_sessions returns this result.

        Action:
        Calls run_session_active with json_output=True, requesting structured output
        to stdout instead of human-readable text.

        Assertion Strategy:
        Validates JSON serialization by confirming:
        - The return value is 0 (success).
        - Captured stdout contains '"success": true' indicating correct serialization.
        - Captured stdout contains '"active_sessions"' proving the data payload is included.

        Testing Principle:
        Validates output format contract, ensuring the JSON mode produces parseable,
        complete output that downstream tooling can rely on.
        """
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
        """Verifies run_session_active prints the error detail to stdout on failure.

        Tests the user-facing error reporting by supplying a failed ServiceResult with
        an error string and confirming it appears in captured stdout.

        Business context:
        When session queries fail, users need actionable error messages (e.g.,
        'Database unavailable') to diagnose the issue; silent failures lead to
        confusion and support burden.

        Arrangement:
        1. Create a ServiceResult with success=False and error='Database unavailable',
           simulating a backend failure with a diagnostic message.
        2. Patch SessionService so get_active_sessions returns this failure result.

        Action:
        Calls run_session_active with default arguments, which receives the failure
        and should print the error detail to stdout.

        Assertion Strategy:
        Validates error reporting by confirming:
        - The return value is 1 (failure exit code).
        - Captured stdout contains 'Database unavailable', proving the error message
          reaches the user.

        Testing Principle:
        Validates user-facing error transparency, ensuring backend errors surface as
        readable messages rather than being swallowed silently.
        """
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
        """Verifies _copy_agent_files copies regular files but skips subdirectories.

        Tests the file-vs-directory discrimination logic by placing both a file and a
        subdirectory in the source tree and confirming only the file is copied.

        Business context:
        Agent file bundles may contain nested directories (e.g., for organization);
        blindly copying directories as if they were files would create corrupt entries
        or crash on read. Only regular files should be transferred.

        Arrangement:
        1. Create a source directory with one regular file (test.agent.md) and one
           subdirectory (subdir) under /pkg/agent_files/agents.
        2. Override mock_fs.is_file to return False for paths ending in 'subdir',
           simulating filesystem directory detection.

        Action:
        Calls _copy_agent_files, which iterates the source directory and should copy
        only entries that pass the is_file check.

        Assertion Strategy:
        Validates selective copying by confirming:
        - The regular file exists at the destination (.github/agents/test.agent.md).
        - The subdirectory was NOT created as a file at the destination.

        Testing Principle:
        Validates input filtering, ensuring the copy operation discriminates between
        files and directories to prevent corrupted or unexpected output.
        """
        from ai_session_tracker_mcp.cli import _copy_agent_files

        # Create source with both files and directories
        mock_fs.makedirs("/pkg/agent_files/agents")
        mock_fs.set_file("/pkg/agent_files/agents/test.agent.md", "content")
        mock_fs.makedirs("/pkg/agent_files/agents/subdir")  # Directory to skip

        # Override is_file to return False for the subdir
        original_is_file = mock_fs.is_file

        def is_file_with_dir(path: str) -> bool:
            """Returns False for paths ending in 'subdir' to simulate directory detection.

            Acts as a test double for mock_fs.is_file, enabling the test to verify that
            _copy_agent_files correctly skips non-file entries during iteration. Delegates
            to the original is_file for all other paths to preserve normal behavior.

            Business context:
            Real filesystems distinguish files from directories; this helper injects that
            distinction into the mock filesystem so the copy logic can be tested for
            correct filtering without touching a real disk.

            Args:
                path: The filesystem path to check. Paths ending in 'subdir' are treated
                    as directories (returns False); all others delegate to the original
                    mock_fs.is_file implementation.

            Returns:
                False if the path ends with 'subdir' (simulating a directory entry),
                otherwise the result of the original mock_fs.is_file(path).

            Raises:
                No exceptions raised directly; delegates to original_is_file which may
                raise if the path is invalid in the mock filesystem.

            Example:
                >>> is_file_with_dir('/pkg/agent_files/agents/subdir')
                False
                >>> is_file_with_dir('/pkg/agent_files/agents/test.agent.md')
                True  # assuming original_is_file returns True
            """
            if path.endswith("subdir"):
                return False
            return original_is_file(path)

        mock_fs.is_file = is_file_with_dir

        _copy_agent_files(mock_fs, "/pkg/agent_files", "/project/.github", "/project")

        # File should be copied
        assert mock_fs.exists("/project/.github/agents/test.agent.md")
        # Directory should not create a file
        assert not mock_fs.exists("/project/.github/agents/subdir")
