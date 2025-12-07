"""Tests for server module."""

from __future__ import annotations

import os
import tempfile

import pytest

from ai_session_tracker_mcp.config import Config
from ai_session_tracker_mcp.server import SessionTrackerServer
from ai_session_tracker_mcp.storage import StorageManager


@pytest.fixture
def temp_storage_dir() -> str:
    """Create a temporary directory for test storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def storage(temp_storage_dir: str) -> StorageManager:
    """Create StorageManager with temporary directory."""
    return StorageManager(temp_storage_dir)


@pytest.fixture
def server(storage: StorageManager) -> SessionTrackerServer:
    """Create SessionTrackerServer with test storage."""
    return SessionTrackerServer(storage)


class TestServerInit:
    """Tests for server initialization."""

    def test_creates_storage_if_none(self) -> None:
        """Creates StorageManager if none provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            server = SessionTrackerServer()
            assert server.storage is not None

    def test_uses_provided_storage(self, storage: StorageManager) -> None:
        """Uses provided StorageManager."""
        server = SessionTrackerServer(storage)
        assert server.storage is storage

    def test_creates_stats_engine(self, server: SessionTrackerServer) -> None:
        """Creates StatisticsEngine."""
        assert server.stats_engine is not None

    def test_registers_all_tools(self, server: SessionTrackerServer) -> None:
        """Registers all expected tools."""
        expected_tools = [
            "start_ai_session",
            "log_ai_interaction",
            "end_ai_session",
            "flag_ai_issue",
            "log_code_metrics",
            "get_ai_observability",
        ]
        for tool in expected_tools:
            assert tool in server._tool_handlers
            assert tool in server.tools


class TestToolDefinitions:
    """Tests for tool definition schemas."""

    def test_all_tools_have_name(self, server: SessionTrackerServer) -> None:
        """All tools have a name field."""
        for name, tool in server.tools.items():
            assert tool["name"] == name

    def test_all_tools_have_description(self, server: SessionTrackerServer) -> None:
        """All tools have a description."""
        for tool in server.tools.values():
            assert "description" in tool
            assert len(tool["description"]) > 0

    def test_all_tools_have_input_schema(self, server: SessionTrackerServer) -> None:
        """All tools have an inputSchema."""
        for tool in server.tools.values():
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_start_session_schema(self, server: SessionTrackerServer) -> None:
        """start_ai_session has correct schema."""
        schema = server.tools["start_ai_session"]["inputSchema"]
        assert "session_name" in schema["properties"]
        assert "task_type" in schema["properties"]
        assert "session_name" in schema["required"]
        assert "task_type" in schema["required"]

    def test_log_interaction_schema(self, server: SessionTrackerServer) -> None:
        """log_ai_interaction has correct schema."""
        schema = server.tools["log_ai_interaction"]["inputSchema"]
        assert "session_id" in schema["properties"]
        assert "prompt" in schema["properties"]
        assert "effectiveness_rating" in schema["properties"]

    def test_task_type_enum_matches_config(self, server: SessionTrackerServer) -> None:
        """task_type enum matches Config.TASK_TYPES."""
        schema = server.tools["start_ai_session"]["inputSchema"]
        enum_values = set(schema["properties"]["task_type"]["enum"])
        assert enum_values == Config.TASK_TYPES


class TestHandleMessage:
    """Tests for message routing."""

    @pytest.mark.asyncio
    async def test_initialize_returns_capabilities(self, server: SessionTrackerServer) -> None:
        """initialize method returns server capabilities."""
        message = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        result = await server.handle_message(message)

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result
        assert result["result"]["protocolVersion"] == Config.MCP_VERSION
        assert result["result"]["serverInfo"]["name"] == Config.SERVER_NAME

    @pytest.mark.asyncio
    async def test_tools_list_returns_all_tools(self, server: SessionTrackerServer) -> None:
        """tools/list returns all tool definitions."""
        message = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        result = await server.handle_message(message)

        assert "result" in result
        assert "tools" in result["result"]
        assert len(result["result"]["tools"]) == 6

    @pytest.mark.asyncio
    async def test_tools_call_routes_to_handler(self, server: SessionTrackerServer) -> None:
        """tools/call routes to correct handler."""
        message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "start_ai_session",
                "arguments": {
                    "session_name": "Test",
                    "task_type": "code_generation",
                },
            },
        }
        result = await server.handle_message(message)

        assert "result" in result
        assert "session_id" in result["result"]

    @pytest.mark.asyncio
    async def test_unknown_method_returns_error(self, server: SessionTrackerServer) -> None:
        """Unknown method returns error."""
        message = {"jsonrpc": "2.0", "id": 4, "method": "unknown/method"}
        result = await server.handle_message(message)

        assert "error" in result
        assert result["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, server: SessionTrackerServer) -> None:
        """Unknown tool returns error."""
        message = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        }
        result = await server.handle_message(message)

        assert "error" in result
        assert result["error"]["code"] == -32601


class TestStartSession:
    """Tests for start_ai_session handler."""

    @pytest.mark.asyncio
    async def test_creates_session(self, server: SessionTrackerServer) -> None:
        """Creates session in storage."""
        result = await server._handle_start_session(
            {"session_name": "Test", "task_type": "code_generation"}, 1
        )

        assert "result" in result
        session_id = result["result"]["session_id"]
        session = server.storage.get_session(session_id)
        assert session is not None
        assert session["session_name"] == "Test"
        assert session["task_type"] == "code_generation"

    @pytest.mark.asyncio
    async def test_returns_session_id(self, server: SessionTrackerServer) -> None:
        """Returns session_id in result."""
        result = await server._handle_start_session(
            {"session_name": "Test", "task_type": "debugging"}, 1
        )

        assert "session_id" in result["result"]
        assert len(result["result"]["session_id"]) > 0

    @pytest.mark.asyncio
    async def test_includes_context(self, server: SessionTrackerServer) -> None:
        """Includes context in session."""
        result = await server._handle_start_session(
            {
                "session_name": "Test",
                "task_type": "code_generation",
                "context": "Working on auth",
            },
            1,
        )

        session_id = result["result"]["session_id"]
        session = server.storage.get_session(session_id)
        assert session["context"] == "Working on auth"


class TestLogInteraction:
    """Tests for log_ai_interaction handler."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Create a session and return its ID."""
        sessions = server.storage.load_sessions()
        session_data = {
            "id": "test_session",
            "session_name": "Test",
            "task_type": "code_generation",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        sessions["test_session"] = session_data
        server.storage.save_sessions(sessions)
        return "test_session"

    @pytest.mark.asyncio
    async def test_logs_interaction(self, server: SessionTrackerServer, session_id: str) -> None:
        """Logs interaction to storage."""
        await server._handle_log_interaction(
            {
                "session_id": session_id,
                "prompt": "test prompt",
                "response_summary": "test response",
                "effectiveness_rating": 4,
            },
            1,
        )

        interactions = server.storage.get_session_interactions(session_id)
        assert len(interactions) == 1
        assert interactions[0]["prompt"] == "test prompt"

    @pytest.mark.asyncio
    async def test_updates_session_stats(
        self, server: SessionTrackerServer, session_id: str
    ) -> None:
        """Updates session statistics."""
        await server._handle_log_interaction(
            {
                "session_id": session_id,
                "prompt": "test",
                "response_summary": "response",
                "effectiveness_rating": 4,
            },
            1,
        )

        session = server.storage.get_session(session_id)
        assert session["total_interactions"] == 1
        assert session["avg_effectiveness"] == 4.0

    @pytest.mark.asyncio
    async def test_session_not_found_error(self, server: SessionTrackerServer) -> None:
        """Returns error for non-existent session."""
        result = await server._handle_log_interaction(
            {
                "session_id": "nonexistent",
                "prompt": "test",
                "response_summary": "response",
                "effectiveness_rating": 4,
            },
            1,
        )

        assert "error" in result
        assert result["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_missing_param_error(self, server: SessionTrackerServer, session_id: str) -> None:
        """Returns error for missing parameter."""
        result = await server._handle_log_interaction({"session_id": session_id}, 1)

        assert "error" in result
        assert result["error"]["code"] == -32602


class TestEndSession:
    """Tests for end_ai_session handler."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Create a session and return its ID."""
        sessions = server.storage.load_sessions()
        session_data = {
            "id": "test_session",
            "session_name": "Test",
            "task_type": "code_generation",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        sessions["test_session"] = session_data
        server.storage.save_sessions(sessions)
        return "test_session"

    @pytest.mark.asyncio
    async def test_ends_session(self, server: SessionTrackerServer, session_id: str) -> None:
        """Marks session as completed."""
        await server._handle_end_session({"session_id": session_id, "outcome": "success"}, 1)

        session = server.storage.get_session(session_id)
        assert session["status"] == "completed"
        assert session["outcome"] == "success"
        assert session["end_time"] is not None

    @pytest.mark.asyncio
    async def test_session_not_found_error(self, server: SessionTrackerServer) -> None:
        """Returns error for non-existent session."""
        result = await server._handle_end_session(
            {"session_id": "nonexistent", "outcome": "success"}, 1
        )

        assert "error" in result


class TestFlagIssue:
    """Tests for flag_ai_issue handler."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Create a session and return its ID."""
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        server.storage.save_sessions(sessions)
        return "test_session"

    @pytest.mark.asyncio
    async def test_flags_issue(self, server: SessionTrackerServer, session_id: str) -> None:
        """Adds issue to storage."""
        await server._handle_flag_issue(
            {
                "session_id": session_id,
                "issue_type": "hallucination",
                "description": "AI made up API",
                "severity": "high",
            },
            1,
        )

        issues = server.storage.get_session_issues(session_id)
        assert len(issues) == 1
        assert issues[0]["issue_type"] == "hallucination"
        assert issues[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_session_not_found_error(self, server: SessionTrackerServer) -> None:
        """Returns error for non-existent session."""
        result = await server._handle_flag_issue(
            {
                "session_id": "nonexistent",
                "issue_type": "test",
                "description": "test",
                "severity": "low",
            },
            1,
        )

        assert "error" in result


class TestLogCodeMetrics:
    """Tests for log_code_metrics handler."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Create a session and return its ID."""
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        server.storage.save_sessions(sessions)
        return "test_session"

    @pytest.fixture
    def python_file(self, temp_storage_dir: str) -> str:
        """Create a Python file for testing."""
        file_path = os.path.join(temp_storage_dir, "test_file.py")
        code = '''
def simple_function():
    """A simple function."""
    return True

def complex_function(x: int, y: int) -> int:
    """
    A more complex function.

    Args:
        x: First number
        y: Second number

    Returns:
        Sum of x and y.
    """
    if x > 0:
        if y > 0:
            return x + y
        else:
            return x
    return 0
'''
        with open(file_path, "w") as f:
            f.write(code)
        return file_path

    @pytest.mark.asyncio
    async def test_analyzes_functions(
        self,
        server: SessionTrackerServer,
        session_id: str,
        python_file: str,
    ) -> None:
        """Analyzes functions and stores metrics."""
        result = await server._handle_log_code_metrics(
            {
                "session_id": session_id,
                "file_path": python_file,
                "functions_modified": [
                    {"name": "simple_function", "modification_type": "added"},
                    {"name": "complex_function", "modification_type": "added"},
                ],
            },
            1,
        )

        assert "result" in result
        assert result["result"]["functions_analyzed"] == 2

    @pytest.mark.asyncio
    async def test_calculates_complexity(
        self,
        server: SessionTrackerServer,
        session_id: str,
        python_file: str,
    ) -> None:
        """Calculates cyclomatic complexity."""
        result = await server._handle_log_code_metrics(
            {
                "session_id": session_id,
                "file_path": python_file,
                "functions_modified": [
                    {"name": "complex_function", "modification_type": "added"},
                ],
            },
            1,
        )

        # complex_function has if/if/else = complexity 3
        assert result["result"]["average_complexity"] >= 3

    @pytest.mark.asyncio
    async def test_calculates_doc_score(
        self,
        server: SessionTrackerServer,
        session_id: str,
        python_file: str,
    ) -> None:
        """Calculates documentation score."""
        result = await server._handle_log_code_metrics(
            {
                "session_id": session_id,
                "file_path": python_file,
                "functions_modified": [
                    {"name": "complex_function", "modification_type": "added"},
                ],
            },
            1,
        )

        # complex_function has docstring with Args and Returns
        assert result["result"]["average_doc_quality"] >= 70

    @pytest.mark.asyncio
    async def test_non_python_file_error(
        self, server: SessionTrackerServer, session_id: str
    ) -> None:
        """Returns error for non-Python files."""
        result = await server._handle_log_code_metrics(
            {
                "session_id": session_id,
                "file_path": "/path/to/file.js",
                "functions_modified": [],
            },
            1,
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_file_not_found_error(
        self, server: SessionTrackerServer, session_id: str
    ) -> None:
        """Returns error for missing file."""
        result = await server._handle_log_code_metrics(
            {
                "session_id": session_id,
                "file_path": "/nonexistent/file.py",
                "functions_modified": [],
            },
            1,
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_stores_metrics_in_session(
        self,
        server: SessionTrackerServer,
        session_id: str,
        python_file: str,
    ) -> None:
        """Stores metrics in session data."""
        await server._handle_log_code_metrics(
            {
                "session_id": session_id,
                "file_path": python_file,
                "functions_modified": [
                    {"name": "simple_function", "modification_type": "added"},
                ],
            },
            1,
        )

        session = server.storage.get_session(session_id)
        assert "code_metrics" in session
        assert len(session["code_metrics"]) == 1

    @pytest.mark.asyncio
    async def test_skips_missing_functions(
        self,
        server: SessionTrackerServer,
        session_id: str,
        python_file: str,
    ) -> None:
        """Skips functions not found in file."""
        result = await server._handle_log_code_metrics(
            {
                "session_id": session_id,
                "file_path": python_file,
                "functions_modified": [
                    {"name": "nonexistent_func", "modification_type": "added"},
                ],
            },
            1,
        )

        assert result["result"]["functions_analyzed"] == 0


class TestGetObservability:
    """Tests for get_ai_observability handler."""

    @pytest.mark.asyncio
    async def test_returns_report(self, server: SessionTrackerServer) -> None:
        """Returns analytics report."""
        result = await server._handle_get_observability({}, 1)

        assert "result" in result
        assert "content" in result["result"]

    @pytest.mark.asyncio
    async def test_filters_by_session_id(self, server: SessionTrackerServer) -> None:
        """Filters data by session_id if provided."""
        # Create two sessions
        sessions = server.storage.load_sessions()
        sessions["s1"] = {"id": "s1", "task_type": "code_generation"}
        sessions["s2"] = {"id": "s2", "task_type": "debugging"}
        server.storage.save_sessions(sessions)

        result = await server._handle_get_observability({"session_id": "s1"}, 1)

        assert "result" in result

    @pytest.mark.asyncio
    async def test_session_not_found_error(self, server: SessionTrackerServer) -> None:
        """Returns error for non-existent session_id."""
        result = await server._handle_get_observability({"session_id": "nonexistent"}, 1)

        assert "error" in result


class TestResponseHelpers:
    """Tests for response helper methods."""

    def test_success_response_structure(self, server: SessionTrackerServer) -> None:
        """_success_response has correct structure."""
        result = server._success_response(1, "Test message")

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result
        assert result["result"]["content"][0]["text"] == "Test message"

    def test_success_response_with_extra(self, server: SessionTrackerServer) -> None:
        """_success_response includes extra fields."""
        result = server._success_response(1, "Test", {"key": "value"})

        assert result["result"]["key"] == "value"

    def test_error_response_structure(self, server: SessionTrackerServer) -> None:
        """_error_response has correct structure."""
        result = server._error_response(1, -32600, "Invalid request")

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "error" in result
        assert result["error"]["code"] == -32600
        assert result["error"]["message"] == "Invalid request"
