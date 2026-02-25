"""Tests for server module."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Add tests directory to path for conftest imports
sys.path.insert(0, str(Path(__file__).parent))

from ai_session_tracker_mcp.config import Config
from ai_session_tracker_mcp.server import SessionTrackerServer
from ai_session_tracker_mcp.storage import StorageManager
from conftest import MockFileSystem


@pytest.fixture
def storage(mock_fs: MockFileSystem) -> StorageManager:
    """Create StorageManager with mock file system.

    Provides isolated storage for testing server operations without
    touching real filesystem.

    Args:
        mock_fs: MockFileSystem fixture for in-memory storage.

    Returns:
        StorageManager: Storage instance backed by mock filesystem,
            configured with test storage directory.

    Example:
        def test_storage_ops(storage):
            storage.save_session("s1", session_data)
    """
    return StorageManager(storage_dir="/test/storage", filesystem=mock_fs)


@pytest.fixture
def server(storage: StorageManager) -> SessionTrackerServer:
    """Create SessionTrackerServer with test storage.

    Provides server instance configured with mock-backed storage
    for testing MCP tool operations.

    Args:
        storage: StorageManager fixture with mock filesystem.

    Returns:
        SessionTrackerServer: Server instance ready for testing
            all MCP tools without side effects.

    Example:
        async def test_start_session(server):
            result = await server.start_ai_session(...)
    """
    return SessionTrackerServer(storage)


class TestServerInit:
    """Tests for server initialization."""

    def test_creates_storage_if_none(self, mock_fs: MockFileSystem) -> None:
        """Verifies server accepts and uses provided StorageManager.

        Tests that when a StorageManager is explicitly provided, the server
        uses that instance rather than creating its own.

        Business context:
        Dependency injection enables testing with mock storage and allows
        custom storage configurations in production.

        Arrangement:
        1. Create StorageManager with mock filesystem.
        2. Pass storage to SessionTrackerServer constructor.

        Action:
        Access server.storage property.

        Assertion Strategy:
        Validates server.storage is the exact same instance that was
        provided, confirming proper dependency injection.

        Testing Principle:
        Validates dependency injection pattern for testability.
        """
        # When no storage provided, server creates its own with RealFileSystem
        # We test that it accepts a provided storage instead
        storage = StorageManager(storage_dir="/test", filesystem=mock_fs)
        server = SessionTrackerServer(storage)
        assert server.storage is storage

    def test_uses_provided_storage(self, storage: StorageManager) -> None:
        """Verifies server preserves reference to injected StorageManager.

        Tests that the storage fixture's manager is correctly wired into
        the server instance.

        Business context:
        Storage manager contains all session data. Server must use the
        provided instance to ensure data consistency.

        Arrangement:
        Storage fixture provides pre-configured StorageManager.

        Action:
        Create server with storage, then access server.storage.

        Assertion Strategy:
        Validates identity comparison (is) confirms same object.

        Testing Principle:
        Validates reference preservation in dependency injection.
        """
        server = SessionTrackerServer(storage)
        assert server.storage is storage

    def test_creates_stats_engine(self, server: SessionTrackerServer) -> None:
        """Verifies server initializes StatisticsEngine during construction.

        Tests that the server creates a stats engine for analytics calculations
        as part of its initialization sequence.

        Business context:
        StatisticsEngine handles ROI and effectiveness calculations. Server
        must have this component for get_ai_observability to function.

        Arrangement:
        Server fixture provides fully initialized server.

        Action:
        Access server.stats_engine property.

        Assertion Strategy:
        Validates stats_engine is not None, confirming initialization.

        Testing Principle:
        Validates required component initialization.
        """
        assert server.stats_engine is not None

    def test_registers_all_tools(self, server: SessionTrackerServer) -> None:
        """Verifies all expected MCP tools are registered during init.

        Tests that the server registers handlers and definitions for each
        tool in the AI session tracking API.

        Business context:
        MCP protocol requires tool registration. Missing tools would cause
        AI agents to fail when attempting to use session tracking.

        Arrangement:
        Define expected tool names matching the API specification.

        Action:
        Check server._tool_handlers and server.tools dictionaries.

        Assertion Strategy:
        Validates each expected tool exists in both:
        - _tool_handlers (callable implementations)
        - tools (JSON schema definitions)

        Testing Principle:
        Validates complete API surface registration.
        """
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
        """Verifies each tool definition includes matching name field.

        Tests MCP protocol compliance by ensuring tool definitions have
        name field matching their dictionary key.

        Business context:
        MCP clients use tool name for invocation. Mismatch between key
        and name field would cause routing failures.

        Arrangement:
        Server fixture provides fully registered tool set.

        Action:
        Iterate all tools, compare dict key to name field.

        Assertion Strategy:
        Validates tool["name"] == key for every registered tool.

        Testing Principle:
        Validates protocol compliance for tool identification.
        """
        for name, tool in server.tools.items():
            assert tool["name"] == name

    def test_all_tools_have_description(self, server: SessionTrackerServer) -> None:
        """Verifies each tool has non-empty description for AI agents.

        Tests that tool definitions include descriptions that help AI
        agents understand when and how to use each tool.

        Business context:
        AI agents use descriptions to select appropriate tools. Empty
        or missing descriptions impair tool selection accuracy.

        Arrangement:
        Server fixture provides complete tool definitions.

        Action:
        Check each tool for description presence and length.

        Assertion Strategy:
        Validates description exists and has non-zero length.

        Testing Principle:
        Validates discoverability metadata for AI tool selection.
        """
        for tool in server.tools.values():
            assert "description" in tool
            assert len(tool["description"]) > 0

    def test_all_tools_have_input_schema(self, server: SessionTrackerServer) -> None:
        """Verifies each tool has valid JSON Schema for input validation.

        Tests MCP protocol compliance by ensuring all tools define input
        schema with required structure for parameter validation.

        Business context:
        Input schemas enable request validation and AI prompt generation.
        Missing schemas prevent proper parameter handling.

        Arrangement:
        Server fixture provides complete tool definitions.

        Action:
        Check each tool for inputSchema with type="object".

        Assertion Strategy:
        Validates inputSchema exists with object type, confirming
        proper JSON Schema structure.

        Testing Principle:
        Validates schema compliance for input validation.
        """
        for tool in server.tools.values():
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_start_session_schema(self, server: SessionTrackerServer) -> None:
        """Verifies start_ai_session has complete parameter schema.

        Tests that the session start tool defines all required parameters
        with correct required field designations.

        Business context:
        Session creation requires specific fields for tracking. Schema
        ensures AI agents provide complete session metadata.

        Arrangement:
        Extract schema from start_ai_session tool definition.

        Action:
        Check properties and required arrays for expected fields.

        Assertion Strategy:
        Validates all seven required parameters are defined:
        - session_name, task_type, model_name in properties
        - initial_estimate_minutes, estimate_source in properties
        - developer, project in properties
        - All seven in required array

        Testing Principle:
        Validates API contract for mandatory parameters.
        """
        schema = server.tools["start_ai_session"]["inputSchema"]
        assert "session_name" in schema["properties"]
        assert "task_type" in schema["properties"]
        assert "model_name" in schema["properties"]
        assert "initial_estimate_minutes" in schema["properties"]
        assert "estimate_source" in schema["properties"]
        assert "session_name" in schema["required"]
        assert "task_type" in schema["required"]
        assert "model_name" in schema["required"]
        assert "initial_estimate_minutes" in schema["required"]
        assert "estimate_source" in schema["required"]
        assert "developer" in schema["properties"]
        assert "project" in schema["properties"]
        assert "developer" in schema["required"]
        assert "project" in schema["required"]

    def test_log_interaction_schema(self, server: SessionTrackerServer) -> None:
        """Verifies log_ai_interaction has required parameter schema.

        Tests that the interaction logging tool defines essential parameters
        for capturing AI exchange data.

        Business context:
        Interaction data drives effectiveness analysis. Schema ensures
        AI agents provide session context and rating data.

        Arrangement:
        Extract schema from log_ai_interaction tool definition.

        Action:
        Check properties for required interaction fields.

        Assertion Strategy:
        Validates core parameters are defined:
        - session_id for session association
        - prompt for capturing the request
        - effectiveness_rating for quality assessment

        Testing Principle:
        Validates API contract for interaction tracking.
        """
        schema = server.tools["log_ai_interaction"]["inputSchema"]
        assert "session_id" in schema["properties"]
        assert "prompt" in schema["properties"]
        assert "effectiveness_rating" in schema["properties"]

    def test_end_session_schema(self, server: SessionTrackerServer) -> None:
        """Verifies end_ai_session requires session_id, outcome, and final_estimate_minutes.

        Tests that the end session tool schema enforces all three
        parameters as required — session_id for lookup, outcome for
        status, and final_estimate_minutes for the adjusted human
        time estimate (the core ROI metric).

        Business context:
        The final_estimate_minutes is the adjusted human baseline that
        drives ROI calculation. Without it, we can't compute time saved.
        Making it required ensures every session has a complete ROI picture.

        Arrangement:
        Extract schema from end_ai_session tool definition.

        Action:
        Check properties and required arrays for expected fields.

        Assertion Strategy:
        - session_id, outcome, final_estimate_minutes in properties
        - All three in required array
        - notes remains optional (not in required)
        """
        schema = server.tools["end_ai_session"]["inputSchema"]
        assert "session_id" in schema["properties"]
        assert "outcome" in schema["properties"]
        assert "final_estimate_minutes" in schema["properties"]
        assert "notes" in schema["properties"]
        assert "session_id" in schema["required"]
        assert "outcome" in schema["required"]
        assert "final_estimate_minutes" in schema["required"]
        assert "notes" not in schema["required"]

    def test_task_type_enum_matches_config(self, server: SessionTrackerServer) -> None:
        """Verifies task_type enum values match Config.TASK_TYPES.

        Tests schema consistency by ensuring the tool schema enum matches
        the centralized configuration definition.

        Business context:
        Task types enable workflow categorization. Mismatch between schema
        and config would cause validation failures or data inconsistency.

        Arrangement:
        Extract task_type enum from start_ai_session schema.

        Action:
        Compare schema enum set to Config.TASK_TYPES set.

        Assertion Strategy:
        Validates exact set equality between schema and config.

        Testing Principle:
        Validates configuration consistency across layers.
        """
        schema = server.tools["start_ai_session"]["inputSchema"]
        enum_values = set(schema["properties"]["task_type"]["enum"])
        assert enum_values == Config.TASK_TYPES


class TestHandleMessage:
    """Tests for message routing."""

    @pytest.mark.asyncio
    async def test_initialize_returns_capabilities(self, server: SessionTrackerServer) -> None:
        """Verifies initialize method returns MCP server capabilities.

        Tests the MCP handshake by sending initialize message and confirming
        the response contains proper protocol version and server info.

        Business context:
        MCP clients call initialize first. Proper response enables client
        to understand server capabilities and version compatibility.

        Arrangement:
        Create JSON-RPC initialize message with id=1.

        Action:
        Call handle_message with initialize request.

        Assertion Strategy:
        Validates response structure and values:
        - JSON-RPC envelope with matching id
        - protocolVersion matches Config.MCP_VERSION
        - serverInfo.name matches Config.SERVER_NAME

        Testing Principle:
        Validates MCP protocol handshake compliance.
        """
        message = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        result = await server.handle_message(message)

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result
        assert result["result"]["protocolVersion"] == Config.MCP_VERSION
        assert result["result"]["serverInfo"]["name"] == Config.SERVER_NAME

    @pytest.mark.asyncio
    async def test_tools_list_returns_all_tools(self, server: SessionTrackerServer) -> None:
        """Verifies tools/list returns complete tool definitions.

        Tests the MCP tool discovery by requesting tool list and confirming
        all seven session tracking tools are returned.

        Business context:
        AI agents discover available tools via tools/list. Missing tools
        would prevent agents from using session tracking features.

        Arrangement:
        Create JSON-RPC tools/list message.

        Action:
        Call handle_message with tools/list request.

        Assertion Strategy:
        Validates response contains exactly 7 tools, confirming
        complete API surface is discoverable.

        Testing Principle:
        Validates MCP tool discovery protocol.
        """
        message = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        result = await server.handle_message(message)

        assert "result" in result
        assert "tools" in result["result"]
        assert len(result["result"]["tools"]) == 7

    @pytest.mark.asyncio
    async def test_tools_call_routes_to_handler(self, server: SessionTrackerServer) -> None:
        """Verifies tools/call correctly routes to tool handler.

        Tests the MCP tool invocation by calling start_ai_session and
        confirming the handler executes and returns session_id.

        Business context:
        Tool routing is the core MCP functionality. Incorrect routing
        would break all session tracking operations.

        Arrangement:
        Create tools/call message with start_ai_session and valid arguments.

        Action:
        Call handle_message with tool invocation request.

        Assertion Strategy:
        Validates successful execution by confirming:
        - Result contains session_id (handler executed)
        - No error in response

        Testing Principle:
        Validates request routing to correct handler.
        """
        message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "start_ai_session",
                "arguments": {
                    "session_name": "Test",
                    "task_type": "code_generation",
                    "model_name": "claude-opus-4-20250514",
                    "initial_estimate_minutes": 30,
                    "estimate_source": "manual",
                },
            },
        }
        result = await server.handle_message(message)

        assert "result" in result
        assert "session_id" in result["result"]

    @pytest.mark.asyncio
    async def test_unknown_method_returns_error(self, server: SessionTrackerServer) -> None:
        """Verifies unknown method produces JSON-RPC method not found error.

        Tests error handling for unsupported MCP methods by sending an
        unknown method and confirming proper error response.

        Business context:
        MCP clients may send methods this server doesn't support. Proper
        error response enables graceful degradation.

        Arrangement:
        Create message with unknown method "unknown/method".

        Action:
        Call handle_message with unsupported method.

        Assertion Strategy:
        Validates JSON-RPC error response:
        - Contains 'error' key
        - Error code is -32601 (Method not found per spec)

        Testing Principle:
        Validates protocol-compliant error handling.
        """
        message = {"jsonrpc": "2.0", "id": 4, "method": "unknown/method"}
        result = await server.handle_message(message)

        assert "error" in result
        assert result["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, server: SessionTrackerServer) -> None:
        """Verifies unknown tool name produces JSON-RPC error.

        Tests error handling for invalid tool names by calling a
        nonexistent tool and confirming error response.

        Business context:
        AI agents may request tools that don't exist. Clear error
        response helps agents recover and try alternatives.

        Arrangement:
        Create tools/call message with name "nonexistent_tool".

        Action:
        Call handle_message with invalid tool name.

        Assertion Strategy:
        Validates JSON-RPC error response:
        - Contains 'error' key indicating failure
        - Error code is -32601 (Method not found)

        Testing Principle:
        Validates graceful handling of invalid tool requests.
        """
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
        """Verifies start_ai_session creates and persists session data.

        Tests the complete session creation flow including storage
        persistence and field population.

        Business context:
        Session creation is the entry point for all tracking. Proper
        storage ensures data survives across requests.

        Arrangement:
        Prepare complete session creation arguments.

        Action:
        Call _handle_start_session with all required fields.

        Assertion Strategy:
        Validates persistence by retrieving session and confirming:
        - Session exists in storage with returned ID
        - All provided fields match stored values
        - session_name, task_type, model_name correctly stored
        - initial_estimate_minutes and estimate_source persisted

        Testing Principle:
        Validates end-to-end data flow for session creation.
        """
        result = await server._handle_start_session(
            {
                "session_name": "Test",
                "task_type": "code_generation",
                "model_name": "claude-opus-4-20250514",
                "initial_estimate_minutes": 30,
                "estimate_source": "manual",
            },
            1,
        )

        assert "result" in result
        session_id = result["result"]["session_id"]
        session = server.storage.get_session(session_id)
        assert session is not None
        assert session["session_name"] == "Test"
        assert session["task_type"] == "code_generation"
        assert session["model_name"] == "claude-opus-4-20250514"
        assert session["initial_estimate_minutes"] == 30
        assert session["estimate_source"] == "manual"

    @pytest.mark.asyncio
    async def test_returns_session_id(self, server: SessionTrackerServer) -> None:
        """Verifies start_ai_session returns usable session identifier.

        Tests that the response includes a non-empty session_id that
        can be used for subsequent operations.

        Business context:
        Session ID is required for all follow-up calls (log_interaction,
        end_session). Response must include actionable ID.

        Arrangement:
        Prepare session creation arguments with different task type.

        Action:
        Call _handle_start_session and extract result.

        Assertion Strategy:
        Validates session_id is present and non-empty:
        - Key exists in result dictionary
        - Value has length > 0 (usable identifier)

        Testing Principle:
        Validates response contract for client workflow.
        """
        result = await server._handle_start_session(
            {
                "session_name": "Test",
                "task_type": "debugging",
                "model_name": "gpt-4o",
                "initial_estimate_minutes": 60,
                "estimate_source": "issue_tracker",
            },
            1,
        )

        assert "session_id" in result["result"]
        assert len(result["result"]["session_id"]) > 0

    @pytest.mark.asyncio
    async def test_includes_context(self, server: SessionTrackerServer) -> None:
        """Verifies optional context field is persisted in session.

        Tests that the optional context parameter is stored when provided,
        enabling richer session metadata.

        Business context:
        Context describes what work is being done. Storing it enables
        better filtering and understanding of session purpose.

        Arrangement:
        Prepare session arguments including optional context field.

        Action:
        Call _handle_start_session with context="Working on auth".

        Assertion Strategy:
        Validates context persistence by retrieving session and
        confirming context field matches provided value.

        Testing Principle:
        Validates optional parameter handling.
        """
        result = await server._handle_start_session(
            {
                "session_name": "Test",
                "task_type": "code_generation",
                "model_name": "claude-sonnet-4-20250514",
                "initial_estimate_minutes": 45,
                "estimate_source": "historical",
                "context": "Working on auth",
            },
            1,
        )

        session_id = result["result"]["session_id"]
        session = server.storage.get_session(session_id)
        assert session["context"] == "Working on auth"

    @pytest.mark.asyncio
    async def test_auto_closes_previous_active_session(self, server: SessionTrackerServer) -> None:
        """Verifies start_ai_session auto-closes previous active sessions.

        Tests that when a new session starts, any existing active sessions
        are automatically closed with outcome 'partial'.

        Business context:
        Users may forget to end sessions or sessions may not be closed due
        to errors/crashes. Auto-closing ensures only one session is active
        at a time, preventing confusion and incorrect metrics.

        Arrangement:
        Create an active session directly in storage.

        Action:
        Call _handle_start_session to create a new session.

        Assertion Strategy:
        Validates the previous session is:
        - Status changed to 'completed'
        - Outcome set to 'partial'
        - Notes include '[Auto-closed: new session started]'
        And the new session is created with active status.

        Testing Principle:
        Validates automatic cleanup of orphaned sessions.
        """
        # Create an existing active session
        sessions = server.storage.load_sessions()
        sessions["old_session"] = {
            "id": "old_session",
            "session_name": "Previous Session",
            "task_type": "code_generation",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
            "execution_context": "foreground",
            "notes": "",
        }
        server.storage.save_sessions(sessions)

        # Start a new session
        result = await server._handle_start_session(
            {
                "session_name": "New Session",
                "task_type": "debugging",
                "model_name": "claude-opus-4-20250514",
                "initial_estimate_minutes": 30,
                "estimate_source": "manual",
            },
            1,
        )

        # Verify the old session was auto-closed
        old_session = server.storage.get_session("old_session")
        assert old_session is not None
        assert old_session["status"] == "completed"
        assert old_session["outcome"] == "partial"
        assert "Auto-closed: new session started" in old_session["notes"]
        assert "end_time" in old_session

        # Verify the new session was created
        new_session_id = result["result"]["session_id"]
        new_session = server.storage.get_session(new_session_id)
        assert new_session is not None
        assert new_session["status"] == "active"

        # Verify response includes auto_closed_sessions
        assert "auto_closed_sessions" in result["result"]
        assert "old_session" in result["result"]["auto_closed_sessions"]

    @pytest.mark.asyncio
    async def test_auto_close_multiple_active_sessions(self, server: SessionTrackerServer) -> None:
        """Verifies start_ai_session auto-closes all active sessions.

        Tests that multiple orphaned active sessions are all closed when
        a new session starts.

        Business context:
        Edge case where multiple sessions were left active due to
        repeated failures or bugs. All must be cleaned up.

        Arrangement:
        Create two active sessions directly in storage.

        Action:
        Call _handle_start_session to create a new session.

        Assertion Strategy:
        Validates both previous sessions are closed with appropriate
        status, outcome, and notes.

        Testing Principle:
        Validates bulk cleanup of multiple orphaned sessions.
        """
        # Create multiple active sessions
        sessions = server.storage.load_sessions()
        sessions["session_1"] = {
            "id": "session_1",
            "session_name": "Session 1",
            "task_type": "code_generation",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
            "execution_context": "foreground",
            "notes": "",
        }
        sessions["session_2"] = {
            "id": "session_2",
            "session_name": "Session 2",
            "task_type": "debugging",
            "status": "active",
            "start_time": "2024-01-02T00:00:00+00:00",
            "execution_context": "foreground",
            "notes": "Some existing notes",
        }
        server.storage.save_sessions(sessions)

        # Start a new session
        result = await server._handle_start_session(
            {
                "session_name": "New Session",
                "task_type": "testing",
                "model_name": "claude-opus-4-20250514",
                "initial_estimate_minutes": 60,
                "estimate_source": "issue_tracker",
            },
            1,
        )

        # Verify both old sessions were auto-closed
        session_1 = server.storage.get_session("session_1")
        session_2 = server.storage.get_session("session_2")

        assert session_1["status"] == "completed"
        assert session_1["outcome"] == "partial"
        assert "Auto-closed: new session started" in session_1["notes"]

        assert session_2["status"] == "completed"
        assert session_2["outcome"] == "partial"
        assert "Some existing notes" in session_2["notes"]
        assert "Auto-closed: new session started" in session_2["notes"]

        # Verify response includes both auto-closed sessions
        auto_closed = result["result"]["auto_closed_sessions"]
        assert len(auto_closed) == 2
        assert "session_1" in auto_closed
        assert "session_2" in auto_closed

    @pytest.mark.asyncio
    async def test_auto_close_respects_execution_context(
        self, server: SessionTrackerServer
    ) -> None:
        """Verifies start_ai_session only auto-closes sessions with matching execution_context.

        Tests that foreground sessions don't auto-close background sessions
        and vice versa. MCP server creates foreground sessions, CLI creates
        background sessions.

        Business context:
        Users may run background batch processes via CLI while interactively
        using MCP. These should operate independently - a new MCP session
        shouldn't close an active CLI session.

        Arrangement:
        Create an active session with 'background' execution_context.

        Action:
        Call _handle_start_session (which creates 'foreground' sessions).

        Assertion Strategy:
        Validates the background session remains active and is NOT auto-closed.

        Testing Principle:
        Validates execution_context isolation for session auto-close.
        """
        # Create an active background session (as if from CLI)
        sessions = server.storage.load_sessions()
        sessions["background_session"] = {
            "id": "background_session",
            "session_name": "CLI Session",
            "task_type": "code_generation",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
            "execution_context": "background",
            "notes": "",
        }
        server.storage.save_sessions(sessions)

        # Start a new foreground session via MCP
        result = await server._handle_start_session(
            {
                "session_name": "MCP Session",
                "task_type": "debugging",
                "model_name": "claude-opus-4-20250514",
                "initial_estimate_minutes": 30,
                "estimate_source": "manual",
            },
            1,
        )

        # Verify the background session was NOT auto-closed
        background_session = server.storage.get_session("background_session")
        assert background_session is not None
        assert background_session["status"] == "active"
        assert background_session.get("outcome") is None

        # Verify the response shows no auto-closed sessions
        auto_closed = result["result"]["auto_closed_sessions"]
        assert len(auto_closed) == 0

        # Verify the new foreground session was created
        new_session_id = result["result"]["session_id"]
        new_session = server.storage.get_session(new_session_id)
        assert new_session["execution_context"] == "foreground"

    @pytest.mark.asyncio
    async def test_auto_close_only_matches_same_context(self, server: SessionTrackerServer) -> None:
        """Verifies start_ai_session auto-closes only sessions with matching context.

        Tests mixed scenario with both foreground and background active sessions.
        Only foreground sessions should be auto-closed by a new foreground session.

        Business context:
        Ensures correct isolation when both MCP and CLI sessions are active
        simultaneously, targeting the same storage.

        Arrangement:
        Create both a foreground and background active session.

        Action:
        Call _handle_start_session (foreground).

        Assertion Strategy:
        Validates foreground session is closed, background remains active.

        Testing Principle:
        Validates selective auto-close based on execution_context.
        """
        # Create both foreground and background active sessions
        sessions = server.storage.load_sessions()
        sessions["foreground_session"] = {
            "id": "foreground_session",
            "session_name": "MCP Old Session",
            "task_type": "testing",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
            "execution_context": "foreground",
            "notes": "",
        }
        sessions["background_session"] = {
            "id": "background_session",
            "session_name": "CLI Session",
            "task_type": "code_generation",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
            "execution_context": "background",
            "notes": "",
        }
        server.storage.save_sessions(sessions)

        # Start a new foreground session
        result = await server._handle_start_session(
            {
                "session_name": "New MCP Session",
                "task_type": "debugging",
                "model_name": "claude-opus-4-20250514",
                "initial_estimate_minutes": 30,
                "estimate_source": "manual",
            },
            1,
        )

        # Verify only the foreground session was auto-closed
        foreground_session = server.storage.get_session("foreground_session")
        background_session = server.storage.get_session("background_session")

        assert foreground_session["status"] == "completed"
        assert foreground_session["outcome"] == "partial"
        assert "Auto-closed: new session started" in foreground_session["notes"]

        assert background_session["status"] == "active"
        assert background_session.get("outcome") is None

        # Verify response only shows foreground session as auto-closed
        auto_closed = result["result"]["auto_closed_sessions"]
        assert len(auto_closed) == 1
        assert "foreground_session" in auto_closed
        assert "background_session" not in auto_closed

    @pytest.mark.asyncio
    async def test_no_auto_close_when_no_active_sessions(
        self, server: SessionTrackerServer
    ) -> None:
        """Verifies start_ai_session works when no active sessions exist.

        Tests the normal case where there are no orphaned sessions to close.

        Business context:
        Common case after proper session management. Should not show
        auto-close warnings when none are needed.

        Arrangement:
        Ensure storage is empty or only has completed sessions.

        Action:
        Call _handle_start_session to create a new session.

        Assertion Strategy:
        Validates auto_closed_sessions is an empty list.

        Testing Principle:
        Validates normal operation without false positives.
        """
        result = await server._handle_start_session(
            {
                "session_name": "First Session",
                "task_type": "code_generation",
                "model_name": "claude-opus-4-20250514",
                "initial_estimate_minutes": 30,
                "estimate_source": "manual",
            },
            1,
        )

        # Verify no sessions were auto-closed
        assert result["result"]["auto_closed_sessions"] == []


class TestLogInteraction:
    """Tests for log_ai_interaction handler."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Create a session and return its ID for interaction tests.

        Sets up prerequisite session required for logging interactions.
        Interactions must reference an existing session.

        Business context:
        Interactions track AI exchanges for effectiveness analysis.
        Tests need sessions to validate referential integrity.

        Args:
            server: SessionTrackerServer fixture with mock storage.

        Returns:
            str: Session ID "test_session" for use in interaction tests.

        Example:
            async def test_log(server, session_id):
                await server._handle_log_interaction({"session_id": session_id, ...})
        """
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
        """Verifies interaction logging persists prompt data to storage.

        Tests the core interaction tracking functionality by logging an AI
        exchange and confirming it's retrievable from storage.

        Business context:
        Interaction logging enables ROI analysis by capturing AI exchanges
        for effectiveness measurement and pattern identification.

        Arrangement:
        1. Session fixture provides an active session with known ID.
        2. Server is configured with mock storage for isolation.

        Action:
        Calls _handle_log_interaction with complete interaction data
        including prompt, response summary, and effectiveness rating.

        Assertion Strategy:
        Validates persistence by retrieving interactions and confirming:
        - Exactly one interaction exists for the session.
        - The stored prompt matches the submitted content.

        Testing Principle:
        Validates data integrity for audit trail functionality.
        """
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
        """Verifies interaction logging updates aggregate session statistics.

        Tests that logging an interaction automatically recalculates session
        metrics including interaction count and average effectiveness.

        Business context:
        Running statistics enable real-time session health monitoring and
        inform decisions about when to end or escalate sessions.

        Arrangement:
        1. Session fixture creates an active session with no prior interactions.
        2. Server configured with isolated storage.

        Action:
        Logs a single interaction with effectiveness rating of 4.

        Assertion Strategy:
        Validates statistic updates by confirming:
        - total_interactions increments to 1.
        - avg_effectiveness equals the single rating (4.0).

        Testing Principle:
        Validates derived data calculation for analytics accuracy.
        """
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
        """Verifies log_interaction rejects non-existent session ID.

        Tests error handling when attempting to log interaction for a
        session that doesn't exist in storage.

        Business context:
        Session IDs may become stale or be typos. Clear error response
        helps AI agents recover and request correct session.

        Arrangement:
        Use session_id "nonexistent" which is not in storage.

        Action:
        Call _handle_log_interaction with invalid session_id.

        Assertion Strategy:
        Validates error response:
        - Contains 'error' key
        - Error code is -32602 (Invalid params)

        Testing Principle:
        Validates referential integrity enforcement.
        """
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
        """Verifies missing required parameters produce appropriate error.

        Tests input validation by omitting required fields and confirming
        the handler returns a properly structured JSON-RPC error.

        Business context:
        Robust parameter validation prevents data corruption and provides
        clear feedback to AI agents about API contract requirements.

        Arrangement:
        1. Session fixture provides valid session_id.
        2. Request payload intentionally omits prompt/response/rating fields.

        Action:
        Calls _handle_log_interaction with only session_id provided.

        Assertion Strategy:
        Validates error handling by confirming:
        - Response contains 'error' key indicating failure.
        - Error code is -32602 (Invalid params per JSON-RPC spec).

        Testing Principle:
        Validates fail-fast behavior for malformed requests.
        """
        result = await server._handle_log_interaction({"session_id": session_id}, 1)

        assert "error" in result
        assert result["error"]["code"] == -32602


class TestEndSession:
    """Tests for end_ai_session handler."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Create a session and return its ID for end session tests.

        Sets up active session required for testing end_session handler.
        Only active sessions can be properly ended.

        Business context:
        Session completion triggers duration calculation and ROI metrics.
        Tests need active sessions to verify lifecycle transitions.

        Args:
            server: SessionTrackerServer fixture with mock storage.

        Returns:
            str: Session ID "test_session" for use in end session tests.

        Example:
            async def test_end(server, session_id):
                await server._handle_end_session({"session_id": session_id, ...})
        """
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
        """Verifies ending a session updates status and records completion time.

        Tests the session lifecycle transition from active to completed,
        ensuring all completion metadata is properly recorded.

        Business context:
        Session completion triggers duration calculation for ROI metrics
        and marks data as ready for analytics aggregation.

        Arrangement:
        1. Session fixture creates an active session with known start_time.
        2. Session has status 'active' before operation.

        Action:
        Calls _handle_end_session with 'success' outcome.

        Assertion Strategy:
        Validates lifecycle transition by confirming:
        - status changes from 'active' to 'completed'.
        - outcome field records the success status.
        - end_time is populated for duration calculation.

        Testing Principle:
        Validates state machine transitions for session lifecycle.
        """
        await server._handle_end_session({"session_id": session_id, "outcome": "success"}, 1)

        session = server.storage.get_session(session_id)
        assert session["status"] == "completed"
        assert session["outcome"] == "success"
        assert session["end_time"] is not None

    @pytest.mark.asyncio
    async def test_session_not_found_error(self, server: SessionTrackerServer) -> None:
        """Verifies end_session rejects non-existent session ID.

        Tests error handling when attempting to end a session that
        doesn't exist in storage.

        Business context:
        Attempting to end non-existent session indicates workflow error.
        Clear error helps diagnose session management issues.

        Arrangement:
        Use session_id "nonexistent" which is not in storage.

        Action:
        Call _handle_end_session with invalid session_id.

        Assertion Strategy:
        Validates error response contains 'error' key.

        Testing Principle:
        Validates existence check before state mutation.
        """
        result = await server._handle_end_session(
            {"session_id": "nonexistent", "outcome": "success"}, 1
        )

        assert "error" in result


class TestFlagIssue:
    """Tests for flag_ai_issue handler."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Create a session and return its ID for issue flagging tests.

        Sets up active session required for flagging issues.
        Issues must reference an existing session.

        Business context:
        Issue tracking enables AI quality improvement by capturing
        problems for analysis. Tests need sessions to associate issues.

        Args:
            server: SessionTrackerServer fixture with mock storage.

        Returns:
            str: Session ID "test_session" for use in issue tests.

        Example:
            async def test_flag(server, session_id):
                await server._handle_flag_issue({"session_id": session_id, ...})
        """
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
        """Verifies issue flagging persists problem details to storage.

        Tests the issue reporting functionality by flagging a hallucination
        and confirming all metadata is correctly stored.

        Business context:
        Issue tracking enables identification of AI failure patterns,
        informing model selection and prompt engineering improvements.

        Arrangement:
        1. Session fixture provides an active session for issue association.
        2. Issue data includes type, description, and severity classification.

        Action:
        Calls _handle_flag_issue with a 'hallucination' issue at 'high' severity.

        Assertion Strategy:
        Validates persistence by retrieving issues and confirming:
        - Exactly one issue exists for the session.
        - issue_type correctly identifies the problem category.
        - severity accurately reflects the impact level.

        Testing Principle:
        Validates audit trail for AI failure analysis.
        """
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
        """Verifies flag_issue rejects non-existent session ID.

        Tests error handling when attempting to flag an issue for a
        session that doesn't exist.

        Business context:
        Issues must be associated with real sessions for meaningful
        analysis. Rejecting invalid sessions maintains data integrity.

        Arrangement:
        Use session_id "nonexistent" which is not in storage.

        Action:
        Call _handle_flag_issue with invalid session_id.

        Assertion Strategy:
        Validates error response contains 'error' key.

        Testing Principle:
        Validates foreign key constraint on issue->session.
        """
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
        """Create a session and return its ID for code metrics tests.

        Sets up active session required for logging code metrics.
        Code metrics must be associated with an existing session.

        Business context:
        Code metrics track AI output quality (complexity, docs).
        Tests need sessions to validate metrics association.

        Args:
            server: SessionTrackerServer fixture with mock storage.

        Returns:
            str: Session ID "test_session" for use in metrics tests.

        Example:
            async def test_metrics(server, session_id):
                await server._handle_log_code_metrics({"session_id": session_id, ...})
        """
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        server.storage.save_sessions(sessions)
        return "test_session"

    @pytest.fixture
    def python_file(self) -> str:
        """Create a temporary Python file containing analyzable functions.

        Provides a real filesystem file for code metrics analysis, which
        requires actual file I/O through Python's AST module.

        Args:
            self: Test class instance (implicit, no other args).

        Raises:
            OSError: If temporary file creation fails (extremely unlikely).

        Returns:
            str: Absolute path to a temporary .py file containing two
                functions with varying complexity and documentation levels.

        Example:
            def test_metrics(python_file):
                # python_file is path like '/tmp/tmpXXX.py'
                result = analyze_code(python_file)
        """
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
        # Use NamedTemporaryFile with delete=False so file persists for test
        import os

        fd, path = tempfile.mkstemp(suffix=".py")
        os.write(fd, code.encode())
        os.close(fd)
        yield path
        # Cleanup after test
        os.unlink(path)

    @pytest.mark.asyncio
    async def test_analyzes_functions(
        self,
        server: SessionTrackerServer,
        session_id: str,
        python_file: str,
    ) -> None:
        """Verifies code metrics handler analyzes functions.

        Tests that the handler parses Python file and counts
        functions successfully analyzed.

        Business context:
        Code metrics track AI output quality. Function count
        confirms all specified functions were processed.

        Arrangement:
        1. Session fixture provides active session.
        2. Python file fixture provides analyzable code.

        Action:
        Call _handle_log_code_metrics with two functions.

        Assertion Strategy:
        Validates result shows 2 functions analyzed.

        Testing Principle:
        Validates core analysis functionality.
        """
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
        """Verifies cyclomatic complexity calculation.

        Tests that the handler correctly calculates complexity
        based on branching in the analyzed function.

        Business context:
        Complexity metrics indicate maintainability. High complexity
        may signal AI-generated code needing simplification.

        Arrangement:
        1. Session and python_file fixtures ready.
        2. complex_function has if/if/else structure.

        Action:
        Call _handle_log_code_metrics for complex_function.

        Assertion Strategy:
        Validates complexity calculation matches expected.

        Testing Principle:
        Validates metric accuracy.
        """
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
        """Verifies documentation score calculation.

        Tests that the handler calculates doc quality score
        based on docstring presence and completeness.

        Business context:
        Documentation score tracks AI-generated code quality.
        Good documentation indicates maintainable output.

        Arrangement:
        1. Session and python_file fixtures ready.
        2. complex_function has comprehensive docstring.

        Action:
        Call _handle_log_code_metrics for complex_function.

        Assertion Strategy:
        Validates doc_score > 0 indicating docs found.

        Testing Principle:
        Validates documentation analysis.
        """
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
    async def test_calculates_doc_score_with_all_sections(
        self,
        server: SessionTrackerServer,
        session_id: str,
    ) -> None:
        """Verifies documentation score includes all docstring sections.

        Tests that the handler awards points for Examples and Raises
        sections in addition to Args and Returns.

        Business context:
            Comprehensive documentation including examples and error handling
            documentation indicates high-quality AI output.

        Arrangement:
            Create temporary Python file with fully documented function.

        Action:
            Call _handle_log_code_metrics with the complete docstring file.

        Assertion Strategy:
            Validates average_doc_quality >= 90 (max points for all sections).
        """
        import os

        code = '''
def fully_documented_function(x: int) -> str:
    """
    A fully documented function with all sections.

    This is a comprehensive docstring that includes all possible
    sections to maximize the documentation score.

    Args:
        x: The input integer to process.

    Returns:
        A string representation of the input.

    Raises:
        ValueError: If x is negative.

    Examples:
        >>> fully_documented_function(42)
        '42'
    """
    if x < 0:
        raise ValueError("x cannot be negative")
    return str(x)
'''
        fd, path = tempfile.mkstemp(suffix=".py")
        os.write(fd, code.encode())
        os.close(fd)

        try:
            result = await server._handle_log_code_metrics(
                {
                    "session_id": session_id,
                    "file_path": path,
                    "functions_modified": [
                        {"name": "fully_documented_function", "modification_type": "added"},
                    ],
                },
                1,
            )

            # Should have high doc score: 30 (has docstring) + 10 (>50 chars)
            # + 20 (Args) + 20 (Returns) + 10 (Examples) + 5 (Raises) + 5 (type hints) = 100
            assert result["result"]["average_doc_quality"] >= 90
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_non_python_file_error(
        self, server: SessionTrackerServer, session_id: str
    ) -> None:
        """Verifies code metrics rejects non-Python file extensions.

        Tests input validation by providing a JavaScript file path,
        confirming the handler enforces Python-only analysis.

        Business context:
        The code metrics feature uses Python AST parsing, which only
        works with .py files. Clear errors prevent confusion.

        Arrangement:
        1. Session fixture provides a valid session context.
        2. File path has .js extension instead of .py.

        Action:
        Calls _handle_log_code_metrics with a JavaScript file path.

        Assertion Strategy:
        Validates file type enforcement by confirming:
        - Response contains 'error' key indicating rejection.

        Testing Principle:
        Validates input constraints for type-specific operations.
        """
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
        """Verifies code metrics handles missing files gracefully.

        Tests error handling when the specified Python file does not exist,
        confirming clear feedback rather than unhandled exceptions.

        Business context:
        Files may be deleted between request and processing. Graceful
        handling prevents session corruption and aids debugging.

        Arrangement:
        1. Session fixture provides a valid session context.
        2. File path points to a non-existent location.

        Action:
        Calls _handle_log_code_metrics with path to missing file.

        Assertion Strategy:
        Validates error handling by confirming:
        - Response contains 'error' key with descriptive message.

        Testing Principle:
        Validates resilience to filesystem race conditions.
        """
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
        """Verifies code metrics are persisted in session data structure.

        Tests that analyzed function metrics are stored within the session
        record for later aggregation in analytics reports.

        Business context:
        Storing metrics per-session enables tracking code quality trends
        across AI interactions and correlating with effectiveness ratings.

        Arrangement:
        1. Session fixture provides an active session.
        2. python_file fixture provides analyzable code.
        3. Function modification specifies 'simple_function' as added.

        Action:
        Calls _handle_log_code_metrics to analyze and store function metrics.

        Assertion Strategy:
        Validates persistence by confirming:
        - Session contains 'code_metrics' key after operation.
        - Metrics list has exactly one entry for the analyzed function.

        Testing Principle:
        Validates data aggregation for session-level analytics.
        """
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
        """Verifies graceful handling when specified function not found in file.

        Tests that the handler completes successfully when a requested function
        doesn't exist, rather than failing the entire operation.

        Business context:
        Functions may be renamed or removed during refactoring. Graceful
        skipping allows partial analysis while reporting what was processed.

        Arrangement:
        1. Session and python_file fixtures provide valid context.
        2. Function name 'nonexistent_func' does not exist in the file.

        Action:
        Calls _handle_log_code_metrics requesting analysis of missing function.

        Assertion Strategy:
        Validates graceful degradation by confirming:
        - Operation completes without error.
        - functions_analyzed count is 0, indicating skip occurred.

        Testing Principle:
        Validates partial success behavior for resilient operations.
        """
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
        """Verifies get_ai_observability returns analytics report content.

        Tests that the observability handler produces a result with
        displayable content for AI agents.

        Business context:
        Observability provides session analytics. Response must include
        content that agents can present to users.

        Arrangement:
        Empty arguments (no filtering).

        Action:
        Call _handle_get_observability with empty params.

        Assertion Strategy:
        Validates response structure:
        - Contains 'result' key
        - Result contains 'content' with report data

        Testing Principle:
        Validates response contract for analytics endpoint.
        """
        result = await server._handle_get_observability({}, 1)

        assert "result" in result
        assert "content" in result["result"]

    @pytest.mark.asyncio
    async def test_filters_by_session_id(self, server: SessionTrackerServer) -> None:
        """Verifies observability can filter to specific session.

        Tests that providing session_id parameter limits analytics
        to that specific session's data.

        Business context:
        Single-session analysis helps debug specific interactions.
        Filtering enables focused troubleshooting.

        Arrangement:
        Create two sessions with different IDs and task types.

        Action:
        Call _handle_get_observability with session_id="s1".

        Assertion Strategy:
        Validates response contains result (filtering applied).

        Testing Principle:
        Validates parameter-based data scoping.
        """
        # Create two sessions
        sessions = server.storage.load_sessions()
        sessions["s1"] = {"id": "s1", "task_type": "code_generation"}
        sessions["s2"] = {"id": "s2", "task_type": "debugging"}
        server.storage.save_sessions(sessions)

        result = await server._handle_get_observability({"session_id": "s1"}, 1)

        assert "result" in result

    @pytest.mark.asyncio
    async def test_session_not_found_error(self, server: SessionTrackerServer) -> None:
        """Verifies observability rejects non-existent session filter.

        Tests error handling when requesting analytics for a session
        that doesn't exist.

        Business context:
        Filtering by invalid session would return empty/misleading data.
        Explicit error helps users identify typos in session ID.

        Arrangement:
        Use session_id "nonexistent" which is not in storage.

        Action:
        Call _handle_get_observability with invalid session_id filter.

        Assertion Strategy:
        Validates error response contains 'error' key.

        Testing Principle:
        Validates existence check for filter parameters.
        """
        result = await server._handle_get_observability({"session_id": "nonexistent"}, 1)

        assert "error" in result


class TestHandleGetActiveSessions:
    """Tests for _handle_get_active_sessions handler."""

    @pytest.mark.asyncio
    async def test_returns_active_sessions(self, server: SessionTrackerServer) -> None:
        """Verifies handler returns list of active sessions.

        Tests that sessions with status != 'completed' are returned
        with their identifying information.

        Business context:
        When session_id is lost (e.g., after context summarization),
        AI agents need to recover it to properly end their session.
        This handler enables that recovery workflow.

        Arrangement:
        Create two sessions - one active, one completed.

        Action:
        Call _handle_get_active_sessions.

        Assertion Strategy:
        - Response is successful
        - Only active session is returned
        - Response includes session_id, name, type, start_time
        """
        # Create one active and one completed session
        sessions = server.storage.load_sessions()
        sessions["ses_active"] = {
            "session_name": "Active Session",
            "task_type": "testing",
            "start_time": "2024-01-15T10:00:00",
            "status": "active",
        }
        sessions["ses_completed"] = {
            "session_name": "Completed Session",
            "task_type": "debugging",
            "start_time": "2024-01-15T09:00:00",
            "status": "completed",
        }
        server.storage.save_sessions(sessions)

        result = await server._handle_get_active_sessions({}, 1)

        assert "result" in result
        assert "active_sessions" in result["result"]
        active = result["result"]["active_sessions"]
        assert len(active) == 1
        assert active[0]["session_id"] == "ses_active"
        assert active[0]["session_name"] == "Active Session"
        assert active[0]["task_type"] == "testing"

    @pytest.mark.asyncio
    async def test_returns_message_when_no_active_sessions(
        self, server: SessionTrackerServer
    ) -> None:
        """Verifies handler returns message when no active sessions exist.

        Tests graceful handling when all sessions are completed.

        Business context:
        Clean state indication helps AI agents understand they
        don't have a session to recover.

        Arrangement:
        Create only completed sessions.

        Action:
        Call _handle_get_active_sessions.

        Assertion Strategy:
        - Response is successful
        - Message indicates no active sessions
        """
        sessions = server.storage.load_sessions()
        sessions["ses_done"] = {"session_name": "Done", "status": "completed"}
        server.storage.save_sessions(sessions)

        result = await server._handle_get_active_sessions({}, 1)

        assert "result" in result
        assert "No active sessions found" in result["result"]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_handles_empty_storage(self, server: SessionTrackerServer) -> None:
        """Verifies handler works with no sessions in storage.

        Tests boundary condition of completely empty storage.

        Business context:
        First-time users or clean storage should work gracefully.

        Arrangement:
        No sessions created (empty storage).

        Action:
        Call _handle_get_active_sessions.

        Assertion Strategy:
        - Response is successful
        - Message indicates no active sessions
        """
        result = await server._handle_get_active_sessions({}, 1)

        assert "result" in result
        assert "No active sessions found" in result["result"]["content"][0]["text"]


class TestResponseHelpers:
    """Tests for response helper methods."""

    def test_success_response_structure(self, server: SessionTrackerServer) -> None:
        """Verifies _success_response produces valid JSON-RPC structure.

        Tests the helper method that formats successful responses,
        ensuring MCP protocol compliance.

        Business context:
        Consistent response format enables reliable client parsing.
        Helper ensures all success responses follow same structure.

        Arrangement:
        Call helper with id=1 and message="Test message".

        Action:
        Invoke _success_response directly.

        Assertion Strategy:
        Validates JSON-RPC envelope:
        - jsonrpc version is "2.0"
        - id matches provided value
        - result contains content array with text

        Testing Principle:
        Validates response format helper for protocol compliance.
        """
        result = server._success_response(1, "Test message")

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result
        assert result["result"]["content"][0]["text"] == "Test message"

    def test_success_response_with_extra(self, server: SessionTrackerServer) -> None:
        """Verifies _success_response includes additional fields.

        Tests that extra dictionary parameter merges into result,
        enabling rich response data beyond the message.

        Business context:
        Many responses need structured data (session_id, metrics).
        Extra fields enable returning actionable data.

        Arrangement:
        Call helper with message and extra={"key": "value"}.

        Action:
        Invoke _success_response with extra parameter.

        Assertion Strategy:
        Validates extra field appears in result dict.

        Testing Principle:
        Validates extensible response format.
        """
        result = server._success_response(1, "Test", {"key": "value"})

        assert result["result"]["key"] == "value"

    def test_error_response_structure(self, server: SessionTrackerServer) -> None:
        """Verifies _error_response produces valid JSON-RPC error structure.

        Tests the helper method that formats error responses,
        ensuring MCP protocol compliance.

        Business context:
        Consistent error format enables reliable error handling.
        Clients depend on standard error structure for recovery.

        Arrangement:
        Call helper with id=1, code=-32600, message="Invalid request".

        Action:
        Invoke _error_response directly.

        Assertion Strategy:
        Validates JSON-RPC error envelope:
        - jsonrpc version is "2.0"
        - id matches provided value
        - error contains code and message fields

        Testing Principle:
        Validates error format helper for protocol compliance.
        """
        result = server._error_response(1, -32600, "Invalid request")

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "error" in result
        assert result["error"]["code"] == -32600
        assert result["error"]["message"] == "Invalid request"


class TestCloseActiveSessions:
    """Tests for _close_active_sessions method."""

    @pytest.mark.asyncio
    async def test_closes_active_sessions(self, server: SessionTrackerServer) -> None:
        """Verifies active sessions are closed on server shutdown.

        Tests that all sessions with status 'active' are marked as
        completed with 'partial' outcome.

        Business context:
        Active sessions left open when server stops would have
        incorrect metrics. Auto-closing ensures data integrity.

        Arrangement:
        Create two sessions: one active, one completed.

        Action:
        Call _close_active_sessions.

        Assertion Strategy:
        Validates active session is now completed with partial outcome.
        """
        sessions = server.storage.load_sessions()
        sessions["active_session"] = {
            "id": "active_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        sessions["completed_session"] = {
            "id": "completed_session",
            "status": "completed",
        }
        server.storage.save_sessions(sessions)

        await server._close_active_sessions()

        updated = server.storage.get_session("active_session")
        assert updated["status"] == "completed"
        assert updated["outcome"] == "partial"
        assert "Auto-closed" in updated["notes"]
        assert updated["end_time"] is not None

    @pytest.mark.asyncio
    async def test_close_active_sessions_no_active(self, server: SessionTrackerServer) -> None:
        """Verifies no changes when no active sessions exist.

        Tests that _close_active_sessions is safe to call when
        there are no active sessions.

        Business context:
        Method may be called during normal shutdown with all
        sessions already completed. Should be no-op.

        Arrangement:
        Create only completed sessions.

        Action:
        Call _close_active_sessions.

        Assertion Strategy:
        Validates completed sessions remain unchanged.
        """
        sessions = server.storage.load_sessions()
        sessions["completed"] = {
            "id": "completed",
            "status": "completed",
            "outcome": "success",
        }
        server.storage.save_sessions(sessions)

        await server._close_active_sessions()

        updated = server.storage.get_session("completed")
        assert updated["status"] == "completed"
        assert updated["outcome"] == "success"


class TestLogInteractionExceptionHandling:
    """Tests for exception handling in log_interaction."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Provide active session for log_interaction exception tests.

        Creates a minimal active session with task_type and session_name
        to satisfy log_interaction requirements before exception injection.

        Args:
            server: Server fixture with storage backend.

        Returns:
            Session ID string "test_session" for use in test assertions.

        Raises:
            None: Fixture creates session without validation.

        Example:
            >>> session_id = "test_session"
            >>> result = await server._handle_log_interaction({...}, 1)

        Business context:
            Tests require pre-existing session to exercise exception paths.

        Testing Principle:
            Fixture isolation - each test gets fresh session state.
        """
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "session_name": "Test",
            "task_type": "code_generation",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        server.storage.save_sessions(sessions)
        return "test_session"

    @pytest.mark.asyncio
    async def test_handles_general_exception(
        self, server: SessionTrackerServer, session_id: str
    ) -> None:
        """Verifies log_interaction handles unexpected exceptions.

        Tests that the handler catches and returns proper error
        response for unexpected errors during processing.

        Business context:
        Server must be resilient to unexpected failures. Proper
        error responses allow clients to recover gracefully.

        Arrangement:
        Mock session_service to raise exception during log.

        Action:
        Call _handle_log_interaction with valid data.

        Assertion Strategy:
        Validates error response with -32603 code (internal error).
        """
        from unittest.mock import patch

        with patch.object(
            server.session_service, "log_interaction", side_effect=Exception("Unexpected error")
        ):
            result = await server._handle_log_interaction(
                {
                    "session_id": session_id,
                    "prompt": "test",
                    "response_summary": "test",
                    "effectiveness_rating": 4,
                },
                1,
            )

            assert "error" in result
            assert result["error"]["code"] == -32603


class TestEndSessionExceptionHandling:
    """Tests for exception handling in end_session."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Provide active session for end_session exception tests.

        Creates minimal active session state required for end_session
        handler to process before exception injection.

        Args:
            server: Server fixture with storage backend.

        Returns:
            Session ID string "test_session" for termination tests.

        Raises:
            None: Fixture creates session without validation.

        Example:
            >>> session_id = "test_session"
            >>> result = await server._handle_end_session({...}, 1)

        Business context:
            Tests require pre-existing session to exercise exception paths.

        Testing Principle:
            Fixture isolation - each test gets independent session.
        """
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        server.storage.save_sessions(sessions)
        return "test_session"

    @pytest.mark.asyncio
    async def test_handles_general_exception(
        self, server: SessionTrackerServer, session_id: str
    ) -> None:
        """Verifies end_session handles unexpected exceptions.

        Tests that the handler catches and returns proper error
        response for unexpected errors.

        Business context:
        Server must handle storage failures gracefully.

        Arrangement:
        Mock session_service to raise exception during end.

        Action:
        Call _handle_end_session with valid data.

        Assertion Strategy:
        Validates error response with -32603 code (internal error).
        """
        from unittest.mock import patch

        with patch.object(
            server.session_service, "end_session", side_effect=Exception("Unexpected error")
        ):
            result = await server._handle_end_session(
                {"session_id": session_id, "outcome": "success"},
                1,
            )

            assert "error" in result
            assert result["error"]["code"] == -32603


class TestFlagIssueExceptionHandling:
    """Tests for exception handling in flag_issue."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Provide active session for flag_issue exception tests.

        Creates minimal active session state required for flag_issue
        handler to validate before exception injection.

        Args:
            server: Server fixture with storage backend.

        Returns:
            Session ID string "test_session" for issue flagging tests.

        Raises:
            None: Fixture creates session without validation.

        Example:
            >>> session_id = "test_session"
            >>> result = await server._handle_flag_issue({...}, 1)

        Business context:
            Tests require pre-existing session to exercise exception paths.

        Testing Principle:
            Fixture isolation - each test gets clean session state.
        """
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        server.storage.save_sessions(sessions)
        return "test_session"

    @pytest.mark.asyncio
    async def test_handles_general_exception(
        self, server: SessionTrackerServer, session_id: str
    ) -> None:
        """Verifies flag_issue handles unexpected exceptions.

        Tests proper error response for unexpected errors.

        Business context:
        Issue flagging failures should not crash server.

        Arrangement:
        Mock session_service to raise exception during flag.

        Action:
        Call _handle_flag_issue with valid data.

        Assertion Strategy:
        Validates error response with -32603 code (internal error).
        """
        from unittest.mock import patch

        with patch.object(
            server.session_service, "flag_issue", side_effect=Exception("Unexpected error")
        ):
            result = await server._handle_flag_issue(
                {
                    "session_id": session_id,
                    "issue_type": "test",
                    "description": "test",
                    "severity": "low",
                },
                1,
            )

            assert "error" in result
            assert result["error"]["code"] == -32603


class TestGetObservabilityExceptionHandling:
    """Tests for exception handling in get_observability."""

    @pytest.mark.asyncio
    async def test_handles_general_exception(self, server: SessionTrackerServer) -> None:
        """Verifies get_observability handles unexpected exceptions.

        Tests proper error response for unexpected errors during
        report generation.

        Business context:
        Analytics failures should return proper error, not crash.

        Arrangement:
        Mock storage to raise exception during load.

        Action:
        Call _handle_get_observability.

        Assertion Strategy:
        Validates error response with -32603 code.
        """
        from unittest.mock import patch

        with patch.object(
            server.storage, "load_sessions", side_effect=Exception("Unexpected error")
        ):
            result = await server._handle_get_observability({}, 1)

            assert "error" in result
            assert result["error"]["code"] == -32603


class TestLogCodeMetricsExceptionHandling:
    """Tests for additional exception handling in log_code_metrics."""

    @pytest.fixture
    def session_id(self, server: SessionTrackerServer) -> str:
        """Provide active session for code metrics exception tests.

        Creates minimal active session state required for code metrics
        handler to process before exception injection.

        Args:
            server: Server fixture with storage backend.

        Returns:
            Session ID string "test_session" for metrics association.

        Raises:
            None: Fixture creates session without validation.

        Example:
            >>> session_id = "test_session"
            >>> result = await server._handle_log_code_metrics({...}, 1)

        Business context:
            Tests require pre-existing session to exercise exception paths.

        Testing Principle:
            Fixture isolation - each test gets independent session.
        """
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        server.storage.save_sessions(sessions)
        return "test_session"

    @pytest.fixture
    def python_file_with_syntax_error(self) -> str:
        """Create a Python file with syntax error for code metrics testing.

        Creates a temporary Python file containing intentionally invalid
        syntax to test error handling in code metrics analysis.

        Args:
            self: Test class instance (implicit).

        Returns:
            Temporary file path string to the malformed Python file.

        Yields:
            Temporary file path to the malformed Python file.

        Raises:
            None: File creation does not raise in normal operation.

        Example:
            >>> python_file_with_syntax_error  # fixture usage
            '/tmp/tmpXXXX.py'  # contains invalid syntax

        Business context:
            AI may generate code with syntax errors; metrics must handle.

        Testing Principle:
            Fixture cleanup - file is automatically deleted after test.
        """
        import os

        fd, path = tempfile.mkstemp(suffix=".py")
        os.write(fd, b"def broken(\n  invalid syntax here")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.mark.asyncio
    async def test_handles_syntax_error(
        self, server: SessionTrackerServer, session_id: str, python_file_with_syntax_error: str
    ) -> None:
        """Verifies code metrics handles Python syntax errors.

        Tests that files with syntax errors produce appropriate
        error response rather than crashing.

        Business context:
        AI may generate code with syntax errors. Metrics should
        fail gracefully with clear error message.

        Arrangement:
        1. Create Python file with syntax error.
        2. Session exists for association.

        Action:
        Call _handle_log_code_metrics with invalid file.

        Assertion Strategy:
        Validates error response mentions syntax error.
        """
        result = await server._handle_log_code_metrics(
            {
                "session_id": session_id,
                "file_path": python_file_with_syntax_error,
                "functions_modified": [],
            },
            1,
        )

        assert "error" in result
        assert "syntax" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handles_general_exception(
        self, server: SessionTrackerServer, session_id: str
    ) -> None:
        """Verifies code metrics handles unexpected exceptions.

        Tests proper error response for unexpected errors.

        Business context:
        Unexpected failures should not crash the server.

        Arrangement:
        Mock open() to raise exception.

        Action:
        Call _handle_log_code_metrics.

        Assertion Strategy:
        Validates error response with -32603 code.
        """
        from unittest.mock import patch

        with patch("builtins.open", side_effect=Exception("Unexpected error")):
            result = await server._handle_log_code_metrics(
                {
                    "session_id": session_id,
                    "file_path": "/some/file.py",
                    "functions_modified": [],
                },
                1,
            )

            assert "error" in result
            assert result["error"]["code"] == -32603


class TestStartSessionExceptionHandling:
    """Tests for exception handling in start_session."""

    @pytest.mark.asyncio
    async def test_handles_general_exception(self, server: SessionTrackerServer) -> None:
        """Verifies start_session handles unexpected exceptions.

        Tests proper error response for unexpected errors during
        session creation.

        Business context:
        Session start failures should return proper error.

        Arrangement:
        Mock storage to raise exception during save.

        Action:
        Call _handle_start_session with valid data.

        Assertion Strategy:
        Validates error response with -32603 code.
        """
        from unittest.mock import patch

        with patch.object(
            server.storage, "save_sessions", side_effect=Exception("Unexpected error")
        ):
            result = await server._handle_start_session(
                {
                    "session_name": "Test",
                    "task_type": "code_generation",
                    "model_name": "test",
                    "initial_estimate_minutes": 30,
                    "estimate_source": "manual",
                },
                1,
            )

            assert "error" in result
            assert result["error"]["code"] == -32603


class TestMissingParameterErrors:
    """Tests for missing required parameters in tool handlers."""

    @pytest.mark.asyncio
    async def test_end_session_missing_session_id(self, server: SessionTrackerServer) -> None:
        """Verifies end_session returns error for missing session_id.

        Tests that the KeyError handler properly catches missing required
        parameters and returns appropriate JSON-RPC error.

        Business context:
            Clear error messages help agents correct their tool calls.

        Arrangement:
            Server fixture provides handler with storage backend.

        Action:
            Call _handle_end_session without session_id parameter.

        Assertion Strategy:
            Validates -32602 error code and "session_id" in message.

        Testing Principle:
            Input validation - verifies required parameter enforcement.
        """
        result = await server._handle_end_session(
            {"outcome": "success"},  # Missing session_id
            1,
        )

        assert "error" in result
        assert result["error"]["code"] == -32602
        assert "session_id" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_flag_issue_missing_session_id(self, server: SessionTrackerServer) -> None:
        """Verifies flag_issue returns error for missing session_id.

        Tests that missing required parameters return proper error.

        Arrangement:
            Server fixture provides handler with storage backend.

        Action:
            Call _handle_flag_issue without session_id parameter.

        Assertion Strategy:
            Validates -32602 invalid params error code.

        Testing Principle:
            Input validation - verifies required parameter enforcement.
        """
        result = await server._handle_flag_issue(
            {
                "issue_type": "test",
                "description": "test",
                "severity": "low",
            },  # Missing session_id
            1,
        )

        assert "error" in result
        assert result["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_log_code_metrics_missing_file_path(self, server: SessionTrackerServer) -> None:
        """Verifies log_code_metrics returns error for missing file_path.

        Tests that missing required parameters return proper error.

        Arrangement:
            Create active session for metrics association.

        Action:
            Call _handle_log_code_metrics without file_path parameter.

        Assertion Strategy:
            Validates -32602 invalid params error code.
        """
        # First create a session
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
        }
        server.storage.save_sessions(sessions)

        result = await server._handle_log_code_metrics(
            {
                "session_id": "test_session",
                # Missing file_path
                "functions_modified": [],
            },
            1,
        )

        assert "error" in result
        assert result["error"]["code"] == -32602


class TestAdditionalCoverage:
    """Tests for additional coverage of edge cases."""

    @pytest.mark.asyncio
    async def test_boolop_complexity_calculation(self, server: SessionTrackerServer) -> None:
        """Verifies complexity calculation includes BoolOp nodes (and/or).

        Tests that boolean operators (and/or) correctly contribute to cyclomatic
        complexity calculations, ensuring the AST visitor accounts for compound
        boolean expressions rather than treating them as single conditions.

        Business context:
        Accurate cyclomatic complexity scoring is critical for code quality metrics.
        Boolean operators like `and`/`or` introduce additional execution paths that
        must be reflected in complexity counts; otherwise, developers receive
        misleadingly low complexity scores for heavily conditional code.

        Arrangement:
        1. Creates an active session to associate metrics with a tracked workflow.
        2. Writes a temporary Python file containing a function with multiple
           `and`/`or` boolean operators to exercise BoolOp AST node handling.

        Action:
        Invokes _handle_log_code_metrics on the temporary file, triggering the
        AST-based complexity analyzer to parse and score the boolean expressions.

        Assertion Strategy:
        Validates correct BoolOp contribution by confirming:
        - Result contains a successful "result" key (no error).
        - average_complexity is at least 4, reflecting the base complexity (1)
          plus if-statements (2) plus BoolOp contributions from compound
          boolean expressions.

        Testing Principle:
        Validates completeness of the cyclomatic complexity algorithm, ensuring
        all control-flow-affecting constructs are accounted for.
        """
        import os
        import tempfile

        # Create a session
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {"id": "test_session", "status": "active"}
        server.storage.save_sessions(sessions)

        # Code with BoolOp (and/or operators)
        code = '''
def func_with_boolops(x, y, z):
    """Function with boolean operators."""
    if x > 0 and y > 0 and z > 0:  # BoolOp with 3 values adds 2
        return True
    if x < 0 or y < 0:  # BoolOp with 2 values adds 1
        return False
    return None
'''
        fd, path = tempfile.mkstemp(suffix=".py")
        os.write(fd, code.encode())
        os.close(fd)

        try:
            result = await server._handle_log_code_metrics(
                {
                    "session_id": "test_session",
                    "file_path": path,
                    "functions_modified": [
                        {"name": "func_with_boolops", "modification_type": "added"}
                    ],
                },
                1,
            )
            assert "result" in result
            # Complexity: 1 (base) + 2 (if-statements) + BoolOp contributions
            # average_complexity should reflect the BoolOp additions
            assert result["result"]["average_complexity"] >= 4  # At least base + if + boolops
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_log_code_metrics_session_not_found(self, server: SessionTrackerServer) -> None:
        """Verifies log_code_metrics returns error for non-existent session.

        Tests the session validation guard clause in the code metrics handler,
        ensuring that attempts to log metrics against a session that does not
        exist are gracefully rejected with an appropriate error response.

        Business context:
        Session integrity is essential for accurate tracking. If metrics could be
        logged against non-existent sessions, orphaned data would accumulate and
        corrupt reporting. This guard ensures every metric entry traces back to a
        valid session.

        Arrangement:
        1. Creates a valid temporary Python file so the file-path validation
           does not interfere with the session-not-found check under test.
        2. Does NOT create any session in storage, ensuring the session lookup
           will fail.

        Action:
        Calls _handle_log_code_metrics with a valid file but a session_id
        ("nonexistent_session") that has no corresponding storage entry.

        Assertion Strategy:
        Validates proper error propagation by confirming:
        - The result dictionary contains an "error" key, indicating the handler
          correctly identified the missing session and returned a structured
          error rather than raising an unhandled exception.

        Testing Principle:
        Validates defensive input validation, ensuring the system fails fast
        with clear error feedback when preconditions are not met.
        """
        import os
        import tempfile

        # Create a valid Python file
        code = "def foo(): pass"
        fd, path = tempfile.mkstemp(suffix=".py")
        os.write(fd, code.encode())
        os.close(fd)

        try:
            result = await server._handle_log_code_metrics(
                {
                    "session_id": "nonexistent_session",
                    "file_path": path,
                    "functions_modified": [{"name": "foo", "modification_type": "added"}],
                },
                1,
            )
            assert "error" in result
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_get_active_sessions_exception_handling(
        self, server: SessionTrackerServer
    ) -> None:
        """Verifies get_active_sessions handles storage exceptions gracefully.

        Tests the error-handling path in the active sessions handler when the
        underlying storage layer raises an unexpected exception, ensuring the
        server returns a structured MCP error rather than crashing.

        Business context:
        Storage failures (disk errors, corruption, permission issues) can occur
        in production. The MCP server must remain operational and return
        meaningful error responses so that connected AI clients can handle the
        failure gracefully instead of receiving an opaque transport error.

        Arrangement:
        1. Replaces the storage's load_sessions method with a MagicMock that
           raises a generic Exception("Storage error"), simulating a storage
           layer failure without requiring actual disk corruption.

        Action:
        Calls _handle_get_active_sessions with an empty params dict, triggering
        the mocked storage to raise an exception during session retrieval.

        Assertion Strategy:
        Validates graceful degradation by confirming:
        - The result contains an "error" key rather than propagating the
          exception to the caller.
        - The error message includes "Failed to get active sessions", verifying
          the handler wraps the low-level exception with a user-friendly message.

        Testing Principle:
        Validates fault tolerance and error boundary isolation, ensuring storage
        layer failures are caught and translated into structured error responses.
        """
        from unittest.mock import MagicMock

        # Make storage raise exception
        server.storage.load_sessions = MagicMock(side_effect=Exception("Storage error"))

        result = await server._handle_get_active_sessions({}, 1)

        assert "error" in result
        assert "Failed to get active sessions" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_log_code_metrics_initializes_code_metrics_list(
        self, server: SessionTrackerServer
    ) -> None:
        """Verifies log_code_metrics creates code_metrics list when absent.

        Tests the lazy initialization path where a session exists but does not
        yet have a code_metrics field, ensuring the handler creates the list
        on first use rather than failing with a KeyError.

        Business context:
        Sessions created before the code metrics feature was added (or sessions
        that simply haven't logged any metrics yet) will lack the code_metrics
        key. The handler must transparently initialize this field to maintain
        backward compatibility and avoid requiring migration scripts.

        Arrangement:
        1. Creates an active session explicitly WITHOUT a "code_metrics" key,
           simulating a legacy or newly-created session.
        2. Writes a minimal Python file with a single function to provide
           valid input for the metrics analyzer.

        Action:
        Calls _handle_log_code_metrics targeting the session that lacks the
        code_metrics field, triggering the lazy initialization code path.

        Assertion Strategy:
        Validates correct field initialization by confirming:
        - The handler returns a successful "result" (no error).
        - The updated session now contains a "code_metrics" key.
        - The code_metrics list has exactly 1 entry, proving the field was
          created and the new metric was appended in a single operation.

        Testing Principle:
        Validates backward compatibility and defensive coding, ensuring the
        system handles missing optional fields gracefully via lazy initialization.
        """
        import os
        import tempfile

        # Create session without code_metrics field
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
            # No "code_metrics" key initially
        }
        server.storage.save_sessions(sessions)

        # Create a Python file to analyze
        code = "def simple(): pass"
        fd, path = tempfile.mkstemp(suffix=".py")
        os.write(fd, code.encode())
        os.close(fd)

        try:
            result = await server._handle_log_code_metrics(
                {
                    "session_id": "test_session",
                    "file_path": path,
                    "functions_modified": [{"name": "simple", "modification_type": "added"}],
                },
                1,
            )
            assert "result" in result

            # Check that code_metrics was initialized and populated
            updated_session = server.storage.get_session("test_session")
            assert "code_metrics" in updated_session
            assert len(updated_session["code_metrics"]) == 1
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_log_code_metrics_appends_to_existing_list(
        self, server: SessionTrackerServer
    ) -> None:
        """Verifies log_code_metrics appends to existing code_metrics list.

        Tests the append path where a session already has prior code_metrics
        entries, ensuring new metrics are added without overwriting or
        discarding previously recorded data.

        Business context:
        During a typical AI coding session, multiple files are modified and
        metrics are logged incrementally. Each call to log_code_metrics must
        append to the existing list so that the full history of code changes
        is preserved for session summaries and quality trend analysis.

        Arrangement:
        1. Creates an active session with a pre-existing code_metrics list
           containing one entry ({"existing": "metric"}), simulating a
           session that has already logged metrics from prior file changes.
        2. Writes a minimal Python file to provide valid analyzer input.

        Action:
        Calls _handle_log_code_metrics targeting the session with pre-existing
        metrics, triggering the append (not overwrite) code path.

        Assertion Strategy:
        Validates non-destructive append behavior by confirming:
        - The handler returns a successful "result" (no error).
        - The session's code_metrics list now has exactly 2 entries.
        - The first entry is the original {"existing": "metric"}, proving
          prior data was preserved and the new metric was appended at the end.

        Testing Principle:
        Validates data integrity and accumulation semantics, ensuring that
        repeated operations build upon prior state without data loss.
        """
        import os
        import tempfile

        # Create session WITH pre-existing code_metrics
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {
            "id": "test_session",
            "status": "active",
            "start_time": "2024-01-01T00:00:00+00:00",
            "code_metrics": [{"existing": "metric"}],  # Pre-existing entry
        }
        server.storage.save_sessions(sessions)

        # Create a Python file to analyze
        code = "def another(): pass"
        fd, path = tempfile.mkstemp(suffix=".py")
        os.write(fd, code.encode())
        os.close(fd)

        try:
            result = await server._handle_log_code_metrics(
                {
                    "session_id": "test_session",
                    "file_path": path,
                    "functions_modified": [{"name": "another", "modification_type": "added"}],
                },
                1,
            )
            assert "result" in result

            # Check that code_metrics now has 2 entries (existing + new)
            updated_session = server.storage.get_session("test_session")
            assert len(updated_session["code_metrics"]) == 2
            assert updated_session["code_metrics"][0] == {"existing": "metric"}
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_docstring_parsing_full_coverage(self, server: SessionTrackerServer) -> None:
        """Verifies documentation score calculation with full docstring.

        Tests the documentation quality scoring branch where a function has a
        comprehensive docstring containing all recognized sections (summary,
        extended description, Args, Returns, Raises, Examples), ensuring the
        scorer awards maximum or near-maximum points for complete documentation.

        Business context:
        The doc quality metric incentivizes developers to write thorough
        documentation. This test ensures that well-documented functions are
        correctly recognized and scored highly, validating the positive
        feedback loop that the scoring system creates.

        Arrangement:
        1. Creates an active session to associate the metrics with.
        2. Writes a temporary Python file containing a function with a
           comprehensive docstring that includes: summary line, extended
           description exceeding 50 characters, Args, Returns, Raises,
           and Examples sections — triggering all doc score branches.

        Action:
        Calls _handle_log_code_metrics on the file with the fully-documented
        function, exercising every branch of the docstring quality parser.

        Assertion Strategy:
        Validates accurate documentation scoring by confirming:
        - The handler returns a successful "result" (no error).
        - average_doc_quality is at least 50 (on a 0-100 scale), reflecting
          that all documentation sections were detected and scored.

        Testing Principle:
        Validates scoring algorithm completeness, ensuring that exemplary
        documentation receives proportionally high quality scores.
        """
        import os
        import tempfile

        # Create session
        sessions = server.storage.load_sessions()
        sessions["test_session"] = {"id": "test_session", "status": "active"}
        server.storage.save_sessions(sessions)

        # Code with comprehensive docstring that triggers all doc score branches
        code = '''
def well_documented(x: int, y: str) -> bool:
    """
    A well-documented function that does something important.

    This is a longer description that exceeds the 50 character minimum
    for a good docstring length.

    Args:
        x: An integer parameter
        y: A string parameter

    Returns:
        A boolean indicating success.

    Raises:
        ValueError: If x is negative.

    Examples:
        >>> well_documented(1, "hello")
        True
    """
    if x < 0:
        raise ValueError("x must be positive")
    return True
'''
        fd, path = tempfile.mkstemp(suffix=".py")
        os.write(fd, code.encode())
        os.close(fd)

        try:
            result = await server._handle_log_code_metrics(
                {
                    "session_id": "test_session",
                    "file_path": path,
                    "functions_modified": [
                        {"name": "well_documented", "modification_type": "added"}
                    ],
                },
                1,
            )
            assert "result" in result
            # Should have high doc score due to all sections present
            # average_doc_quality tracks percentage (0-100 scale)
            assert result["result"]["average_doc_quality"] >= 50
        finally:
            os.unlink(path)
