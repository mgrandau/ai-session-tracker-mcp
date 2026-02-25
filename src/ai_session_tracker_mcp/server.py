"""
AI Session Tracker MCP Server.

PURPOSE: Model Context Protocol server for tracking AI coding sessions.
AI CONTEXT: This is the main entry point - all MCP tools are defined and handled here.

MCP PROTOCOL OVERVIEW:
The Model Context Protocol enables AI assistants to access external tools.
Communication uses JSON-RPC 2.0 over stdin/stdout.

AVAILABLE TOOLS:
1. start_ai_session    - Begin tracking a new coding session
2. log_ai_interaction  - Record prompt/response with effectiveness rating
3. end_ai_session      - Complete session with outcome and metrics
4. flag_ai_issue       - Report problematic AI interaction
5. log_code_metrics    - Calculate and store code quality metrics
6. get_ai_observability - Retrieve analytics and reports

MESSAGE FLOW:
    Client → stdin  → Server (parse JSON-RPC)
    Server → handle → Execute tool
    Server → stdout → Client (JSON-RPC response)

USAGE:
    # Direct execution (stdio mode)
    python -m ai_session_tracker_mcp.server

    # VS Code MCP configuration
    {
        "mcpServers": {
            "ai-session-tracker": {
                "command": "python",
                "args": ["-m", "ai_session_tracker_mcp.server"]
            }
        }
    }
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any, cast

from .config import Config
from .filesystem import FileSystem, RealFileSystem
from .models import FunctionMetrics
from .session_service import SessionService
from .statistics import StatisticsEngine
from .storage import StorageManager

__all__ = [
    "SessionTrackerServer",
    "main",
]

# Tool name constants
TOOL_START_SESSION = "start_ai_session"
TOOL_LOG_INTERACTION = "log_ai_interaction"
TOOL_END_SESSION = "end_ai_session"
TOOL_FLAG_ISSUE = "flag_ai_issue"
TOOL_LOG_CODE_METRICS = "log_code_metrics"
TOOL_GET_OBSERVABILITY = "get_ai_observability"
TOOL_GET_ACTIVE_SESSIONS = "get_active_sessions"

# Documentation scoring constants
DOC_SCORE_HAS_DOCSTRING = 30
DOC_SCORE_MIN_LENGTH = 10
DOC_SCORE_HAS_ARGS = 20
DOC_SCORE_HAS_RETURNS = 20
DOC_SCORE_HAS_EXAMPLES = 10
DOC_SCORE_HAS_RAISES = 5
DOC_SCORE_HAS_TYPE_HINTS = 5
DOC_SCORE_MAX = 100

# Severity level emoji mapping
SEVERITY_EMOJI: dict[str, str] = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SessionTrackerServer:
    """
    MCP Server for AI session tracking and analytics.

    ARCHITECTURE:
    - Tool Registry: Defines available tools with JSON schemas
    - Message Handler: Routes JSON-RPC messages to tool executors
    - Tool Executors: Business logic for each tool
    - Storage: JSON file persistence via StorageManager
    - Statistics: ROI and productivity calculations

    TOOL DISPATCH:
    Uses _tool_handlers dict to map tool names to executor methods.
    Each executor returns a JSON-RPC compliant response dict.

    ERROR CODES (JSON-RPC 2.0):
    - -32600: Invalid request
    - -32601: Method not found
    - -32602: Invalid params
    - -32603: Internal error
    - -32700: Parse error
    """

    def __init__(
        self,
        storage: StorageManager | None = None,
        filesystem: FileSystem | None = None,
    ) -> None:
        """
        Initialize the MCP server with storage and tool registry.

        Sets up the session tracker server with storage backend, statistics
        engine, and tool definitions. Can accept a custom storage manager
        and filesystem for testing with mock filesystems.

        Business context: The server is the core component that handles
        all MCP tool requests from VS Code. Proper initialization ensures
        reliable session tracking throughout development workflows.

        Args:
            storage: Optional StorageManager instance. If None, creates a
                new StorageManager with default configuration. Pass a custom
                instance for testing or custom storage paths.
            filesystem: Optional FileSystem instance for file I/O. If None,
                uses RealFileSystem. Pass MockFileSystem for testing.

        Raises:
            OSError: If storage initialization fails (directory creation).

        Example:
            >>> # Default initialization
            >>> server = SessionTrackerServer()
            >>> # With custom storage for testing
            >>> from .filesystem import MockFileSystem
            >>> mock_storage = StorageManager(filesystem=MockFileSystem())
            >>> server = SessionTrackerServer(storage=mock_storage)
        """
        self.storage = storage or StorageManager()
        self.filesystem = filesystem or RealFileSystem()
        self.stats_engine = StatisticsEngine()

        # Session service for shared business logic
        self.session_service = SessionService(
            storage=self.storage,
            stats_engine=self.stats_engine,
        )

        # Tool name -> executor method mapping (using constants)
        self._tool_handlers = {
            TOOL_START_SESSION: self._handle_start_session,
            TOOL_LOG_INTERACTION: self._handle_log_interaction,
            TOOL_END_SESSION: self._handle_end_session,
            TOOL_FLAG_ISSUE: self._handle_flag_issue,
            TOOL_LOG_CODE_METRICS: self._handle_log_code_metrics,
            TOOL_GET_OBSERVABILITY: self._handle_get_observability,
            TOOL_GET_ACTIVE_SESSIONS: self._handle_get_active_sessions,
        }

        # Tool definitions for tools/list response
        self.tools = self._build_tool_definitions()

    def _build_tool_definitions(self) -> dict[str, dict[str, Any]]:
        """
        Build the MCP tool registry with JSON schemas for all available tools.

        Constructs the tool definitions that are returned by the tools/list
        MCP method. Each tool includes a name, description, and JSON schema
        defining its input parameters.

        Business context: Tool definitions guide the AI assistant on how to
        use each tool. Clear descriptions and well-designed schemas ensure
        the AI calls tools correctly with valid parameters.

        Returns:
            Dict mapping tool names to their definitions. Each definition
            includes 'name', 'description', and 'inputSchema' with JSON
            Schema format parameter specifications.

        Raises:
            None - This is a pure data construction method.

        Example:
            >>> tools = server._build_tool_definitions()
            >>> 'start_ai_session' in tools
            True
            >>> tools['start_ai_session']['inputSchema']['required']
            ['session_name', 'task_type', 'model_name', ...]
        """
        return {
            TOOL_START_SESSION: {
                "name": TOOL_START_SESSION,
                "description": (
                    "Start a new AI coding session for tracking workflow metrics. "
                    "CALL THIS FIRST at the start of every coding task. "
                    "Returns session_id for subsequent tool calls."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_name": {
                            "type": "string",
                            "description": "Descriptive name for this session",
                        },
                        "task_type": {
                            "type": "string",
                            "description": "Task category",
                            "enum": list(Config.TASK_TYPES),
                        },
                        "model_name": {
                            "type": "string",
                            "description": "AI model being used (e.g., 'claude-opus-4-20250514')",
                        },
                        "initial_estimate_minutes": {
                            "type": "number",
                            "description": "Estimated minutes for a human to complete this task",
                        },
                        "estimate_source": {
                            "type": "string",
                            "description": "Where the time estimate came from",
                            "enum": ["manual", "issue_tracker", "historical"],
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context about the work",
                            "default": "",
                        },
                        "developer": {
                            "type": "string",
                            "description": "Developer name (from git config user.name)",
                            "default": "",
                        },
                        "project": {
                            "type": "string",
                            "description": "Project name (from .ai_sessions.yaml)",
                            "default": "",
                        },
                    },
                    "required": [
                        "session_name",
                        "task_type",
                        "model_name",
                        "initial_estimate_minutes",
                        "estimate_source",
                        "developer",
                        "project",
                    ],
                },
            },
            TOOL_LOG_INTERACTION: {
                "name": TOOL_LOG_INTERACTION,
                "description": (
                    "Log an AI prompt/response interaction within an active session. "
                    "Call after significant AI exchanges to track effectiveness."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "ID from start_ai_session",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "The prompt sent to AI",
                        },
                        "response_summary": {
                            "type": "string",
                            "description": "Brief summary of what AI produced",
                        },
                        "effectiveness_rating": {
                            "type": "integer",
                            "description": "Rating 1-5: 1=failed, 3=partial, 5=perfect",
                            "minimum": 1,
                            "maximum": 5,
                        },
                        "iteration_count": {
                            "type": "integer",
                            "description": "Number of attempts to achieve goal",
                            "default": 1,
                        },
                        "tools_used": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "MCP tools used in this interaction",
                            "default": [],
                        },
                    },
                    "required": [
                        "session_id",
                        "prompt",
                        "response_summary",
                        "effectiveness_rating",
                    ],
                },
            },
            TOOL_END_SESSION: {
                "name": TOOL_END_SESSION,
                "description": (
                    "End an AI session and calculate final metrics. "
                    "Call when coding task is complete."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "ID from start_ai_session",
                        },
                        "outcome": {
                            "type": "string",
                            "description": "Session result",
                            "enum": ["success", "partial", "failed"],
                        },
                        "notes": {
                            "type": "string",
                            "description": "Summary notes about the session",
                            "default": "",
                        },
                        "final_estimate_minutes": {
                            "type": "number",
                            "description": "Revised estimate: (insertions + deletions) × 10 ÷ 50,"
                            " rounded up to nearest bucket",
                        },
                    },
                    "required": ["session_id", "outcome", "final_estimate_minutes"],
                },
            },
            TOOL_FLAG_ISSUE: {
                "name": TOOL_FLAG_ISSUE,
                "description": (
                    "Flag a problematic AI interaction for analysis. "
                    "Use when AI produces incorrect output or approach needs changing."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "ID from start_ai_session",
                        },
                        "issue_type": {
                            "type": "string",
                            "description": (
                                "Issue category (e.g., 'incorrect_output', 'hallucination')"
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of what went wrong",
                        },
                        "severity": {
                            "type": "string",
                            "description": "Impact level",
                            "enum": list(Config.SEVERITY_LEVELS),
                        },
                    },
                    "required": ["session_id", "issue_type", "description", "severity"],
                },
            },
            TOOL_LOG_CODE_METRICS: {
                "name": TOOL_LOG_CODE_METRICS,
                "description": (
                    "Calculate and log code quality metrics for modified functions. "
                    "Uses AST analysis for complexity and documentation scoring. "
                    "Python files only."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "ID from start_ai_session",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to the Python file modified",
                        },
                        "functions_modified": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Function/method name",
                                    },
                                    "modification_type": {
                                        "type": "string",
                                        "enum": ["added", "modified", "refactored", "deleted"],
                                    },
                                    "lines_added": {"type": "integer", "default": 0},
                                    "lines_modified": {"type": "integer", "default": 0},
                                    "lines_deleted": {"type": "integer", "default": 0},
                                },
                                "required": ["name", "modification_type"],
                            },
                            "description": "Functions that were modified",
                        },
                    },
                    "required": ["session_id", "file_path", "functions_modified"],
                },
            },
            TOOL_GET_OBSERVABILITY: {
                "name": TOOL_GET_OBSERVABILITY,
                "description": (
                    "Retrieve AI session analytics and ROI metrics. "
                    "Returns summary statistics, effectiveness trends, and cost analysis."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Specific session to analyze (optional, omit for all)",
                        },
                        "time_range": {
                            "type": "string",
                            "description": "Time filter",
                            "enum": ["last_day", "last_week", "all"],
                            "default": "all",
                        },
                    },
                    "required": [],
                },
            },
            TOOL_GET_ACTIVE_SESSIONS: {
                "name": TOOL_GET_ACTIVE_SESSIONS,
                "description": (
                    "Get list of currently active (not ended) sessions. "
                    "Use this to find sessions to end when session_id is lost."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }

    # =========================================================================
    # TOOL HANDLERS
    # =========================================================================

    async def _handle_start_session(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle start_ai_session tool to begin a new tracking session.

        Delegates to SessionService for business logic and formats the
        result as an MCP response.

        Args:
            args: Tool arguments containing session parameters.
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC success response with session_id, or error response.

        Raises:
            No exceptions are raised directly.

        Example:
            >>> response = await server._handle_start_session(
            ...     {"session_name": "refactor", "task_type": "coding", "model_name": "gpt-4"},
            ...     msg_id=1,
            ... )
            >>> response["result"]["content"][0]["text"]
            '...Session Started...'
        """
        result = self.session_service.start_session(
            name=args.get("session_name", ""),
            task_type=args.get("task_type", ""),
            model_name=args.get("model_name", ""),
            human_time_estimate_minutes=float(args.get("initial_estimate_minutes", 0)),
            estimate_source=args.get("estimate_source", ""),
            context=args.get("context", ""),
            execution_context="foreground",
            developer=args.get("developer", ""),
            project=args.get("project", ""),
        )

        if not result.success:
            return self._error_response(msg_id, -32603, result.error or result.message)

        data = result.data or {}
        session_id = data.get("session_id", "")
        auto_closed = data.get("auto_closed_sessions", [])

        # Build response with optional auto-close notice
        auto_close_notice = ""
        if auto_closed:
            closed_ids = ", ".join(auto_closed)
            auto_close_notice = (
                f"\n⚠️ Auto-closed {len(auto_closed)} previous session(s): {closed_ids}\n"
            )

        response_text = f"""
✅ Session Started: {session_id}
Type: {data.get("task_type")} | Model: {data.get("model_name")}
Estimate: {data.get("initial_estimate_minutes", 0):.0f}min ({data.get("estimate_source")})
{auto_close_notice}
⚠️ Log interactions! Call log_ai_interaction(session_id, prompt, rating 1-5) after responses.
"""
        return self._success_response(
            msg_id,
            response_text,
            {"session_id": session_id, "auto_closed_sessions": auto_closed},
        )

    async def _handle_log_interaction(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle log_ai_interaction tool to record a prompt/response exchange.

        Delegates to SessionService for business logic and formats the
        result as an MCP response.

        Args:
            args: Tool arguments containing interaction parameters.
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC success response with rating visualization, or error response.

        Raises:
            KeyError: If required parameters (session_id, prompt,
                response_summary, effectiveness_rating) are missing from args.
            Exception: Any unexpected error during interaction logging is caught
                and returned as a JSON-RPC error response.

        Example:
            >>> response = await server._handle_log_interaction(
            ...     {
            ...         "session_id": "abc123",
            ...         "prompt": "Refactor module",
            ...         "response_summary": "Extracted helper function",
            ...         "effectiveness_rating": 4,
            ...     },
            ...     msg_id=2,
            ... )
            >>> "Logged" in response["result"]["content"][0]["text"]
            True
        """
        try:
            result = self.session_service.log_interaction(
                session_id=args["session_id"],
                prompt=args["prompt"],
                response_summary=args["response_summary"],
                effectiveness_rating=args["effectiveness_rating"],
                iteration_count=args.get("iteration_count", 1),
                tools_used=args.get("tools_used", []),
            )

            if not result.success:
                return self._error_response(msg_id, -32602, result.error or result.message)

            data = result.data or {}
            rating = data.get("effectiveness_rating", 0)
            iterations = data.get("iteration_count", 1)
            total = data.get("total_interactions", 0)
            avg_eff = data.get("avg_effectiveness", 0)

            stars = "★" * rating + "☆" * (5 - rating)
            response_text = f"""
📝 Logged: {stars} ({rating}/5) | Iterations: {iterations}
Session: {total} interactions, avg {avg_eff:.1f}/5
"""
            return self._success_response(msg_id, response_text)

        except KeyError as e:
            return self._error_response(msg_id, -32602, f"Missing required parameter: {e}")
        except Exception as e:
            logger.error(f"Error logging interaction: {e}")
            return self._error_response(msg_id, -32603, f"Failed to log interaction: {e}")

    async def _handle_end_session(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle end_ai_session tool to complete a tracking session.

        Delegates to SessionService for business logic and formats the
        result as an MCP response.

        Args:
            args: Tool arguments containing session_id and outcome.
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC success response with session summary, or error response.

        Raises:
            KeyError: If required parameters (session_id, outcome) are missing
                from args.
            Exception: Any unexpected error during session ending is caught and
                returned as a JSON-RPC error response.

        Example:
            >>> response = await server._handle_end_session(
            ...     {"session_id": "abc123", "outcome": "completed"},
            ...     msg_id=3,
            ... )
            >>> "Session Ended" in response["result"]["content"][0]["text"]
            True
        """
        try:
            result = self.session_service.end_session(
                session_id=args["session_id"],
                outcome=args["outcome"],
                notes=args.get("notes", ""),
                final_estimate_minutes=args.get("final_estimate_minutes"),
            )

            if not result.success:
                return self._error_response(msg_id, -32602, result.error or result.message)

            data = result.data or {}
            session_id = data.get("session_id", "")
            duration = data.get("duration_minutes", 0)
            outcome = data.get("outcome", "")
            interactions = data.get("total_interactions", 0)
            avg_eff = data.get("avg_effectiveness", 0)
            issues_count = data.get("issues_count", 0)

            response_text = f"""
✅ Session Ended: {session_id}
Duration: {duration:.1f}min | Outcome: {outcome}
Metrics: {interactions} interactions, {avg_eff:.1f}/5 avg, {issues_count} issues
"""
            return self._success_response(msg_id, response_text)

        except KeyError as e:
            return self._error_response(msg_id, -32602, f"Missing required parameter: {e}")
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return self._error_response(msg_id, -32603, f"Failed to end session: {e}")

    async def _handle_flag_issue(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle flag_ai_issue tool to record problematic AI interactions.

        Delegates to SessionService for business logic and formats the
        result as an MCP response.

        Args:
            args: Tool arguments containing issue parameters.
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC success response with issue confirmation, or error response.

        Raises:
            KeyError: If required parameters (session_id, issue_type,
                description, severity) are missing from args.
            Exception: Any unexpected error during issue flagging is caught and
                returned as a JSON-RPC error response.

        Example:
            >>> response = await server._handle_flag_issue(
            ...     {
            ...         "session_id": "abc123",
            ...         "issue_type": "hallucination",
            ...         "description": "Generated non-existent API",
            ...         "severity": "high",
            ...     },
            ...     msg_id=4,
            ... )
            >>> "Issue Flagged" in response["result"]["content"][0]["text"]
            True
        """
        try:
            result = self.session_service.flag_issue(
                session_id=args["session_id"],
                issue_type=args["issue_type"],
                description=args["description"],
                severity=args["severity"],
            )

            if not result.success:
                return self._error_response(msg_id, -32602, result.error or result.message)

            data = result.data or {}
            issue_type = data.get("issue_type", "")
            severity = data.get("severity", "")
            session_id = data.get("session_id", "")

            emoji = SEVERITY_EMOJI.get(severity, "⚪")

            response_text = f"""
{emoji} Issue Flagged: {issue_type} ({severity.upper()})
Session: {session_id}
📋 Next: log_ai_interaction() or end_ai_session()
"""
            return self._success_response(msg_id, response_text)

        except KeyError as e:
            return self._error_response(msg_id, -32602, f"Missing required parameter: {e}")
        except Exception as e:
            logger.error(f"Error flagging issue: {e}")
            return self._error_response(msg_id, -32603, f"Failed to flag issue: {e}")

    # =========================================================================
    # CODE METRICS HELPERS (P1-1 refactoring)
    # =========================================================================

    def _read_and_parse_python_file(
        self, file_path: str
    ) -> tuple[ast.Module, None] | tuple[None, str]:
        """
        Read and parse a Python file into an AST.

        Reads the file content and parses it using Python's ast module.
        Returns a tuple pattern for error handling without exceptions.

        Business context: Code metrics require AST analysis. This method
        provides safe file reading with clear error reporting for the
        log_code_metrics tool.

        Args:
            file_path: Path to the Python file to parse.

        Returns:
            tuple[ast.Module, None] | tuple[None, str]: On success,
                returns (parsed AST, None). On failure, returns
                (None, error message describing the issue).

        Example:
            >>> tree, error = server._read_and_parse_python_file("/path/to/file.py")
            >>> if error:
            ...     print(f"Parse failed: {error}")
            >>> # Use tree for analysis
        """
        try:
            code = self.filesystem.read_text(file_path)
            tree = ast.parse(code)
            return tree, None
        except FileNotFoundError:
            return None, f"File not found: {file_path}"
        except SyntaxError as e:
            return None, f"Syntax error in file: {e}"

    def _find_function_in_ast(
        self, tree: ast.Module, func_name: str
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        """
        Find a function or async function definition by name in the AST.

        Walks the entire AST tree to find a function matching the given
        name. Supports both sync and async function definitions.

        Business context: Code metrics need to locate specific functions
        modified during a session. This enables targeted complexity and
        documentation analysis.

        Args:
            tree: Parsed AST module from ast.parse().
            func_name: Name of the function to find.

        Returns:
            ast.FunctionDef | ast.AsyncFunctionDef | None: The function
                node if found, None otherwise.

        Example:
            >>> tree = ast.parse("def foo(): pass")
            >>> node = server._find_function_in_ast(tree, "foo")
            >>> node.name
            'foo'
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == func_name:
                return node
        return None

    def _calculate_cyclomatic_complexity(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> int:
        """
        Calculate cyclomatic complexity for a function AST node.

        Complexity starts at 1 and increases for each branch/decision point.
        Higher values indicate more complex control flow.

        Business context: Complexity metrics help identify functions that
        may need refactoring. High complexity correlates with maintenance
        difficulty and bug risk.

        Counted elements:
        - if, while, for, except, with, assert statements (+1 each)
        - Boolean operators (and, or): +1 per additional operand

        Args:
            func_node: AST node for the function to analyze.

        Returns:
            int: Cyclomatic complexity score (minimum 1). Values 1-5 are
                low, 6-10 moderate, 11+ high complexity.

        Example:
            >>> tree = ast.parse("def foo(x): return x if x else 0")
            >>> func = tree.body[0]
            >>> server._calculate_cyclomatic_complexity(func)
            2
        """
        complexity = 1
        complexity_nodes = (
            ast.If,
            ast.While,
            ast.For,
            ast.ExceptHandler,
            ast.With,
            ast.Assert,
        )
        for child in ast.walk(func_node):
            if isinstance(child, complexity_nodes):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _calculate_documentation_score(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> tuple[int, bool, bool]:
        """
        Calculate documentation quality score for a function.

        Analyzes the function's docstring and type hints to produce a
        quality score. Higher scores indicate better documentation.

        Business context: Documentation quality is a key code health metric.
        Well-documented functions are easier to maintain and onboard new
        developers. Score thresholds: 0-30 poor, 31-60 basic, 61-100 good.

        Scoring breakdown (module constants):
        - DOC_SCORE_HAS_DOCSTRING (30): Has any docstring
        - DOC_SCORE_MIN_LENGTH (10): Docstring > 50 chars
        - DOC_SCORE_HAS_ARGS (20): Contains Args/Parameters section
        - DOC_SCORE_HAS_RETURNS (20): Contains Returns section
        - DOC_SCORE_HAS_EXAMPLES (10): Contains Examples/Usage section
        - DOC_SCORE_HAS_RAISES (5): Contains Raises section
        - DOC_SCORE_HAS_TYPE_HINTS (5): Has type annotations

        Args:
            func_node: AST node for the function to analyze.

        Returns:
            tuple[int, bool, bool]: Tuple of (score 0-100, has_docstring,
                has_type_hints).

        Example:
            >>> code = 'def foo(x: int) -> int: \"\"\"Doc.\"\"\"'
            >>> tree = ast.parse(code)
            >>> score, has_doc, has_hints = server._calculate_documentation_score(tree.body[0])
        """
        docstring = ast.get_docstring(func_node)
        doc_score = 0
        has_docstring = docstring is not None

        if docstring:
            doc_score += DOC_SCORE_HAS_DOCSTRING
            if len(docstring) > 50:
                doc_score += DOC_SCORE_MIN_LENGTH
            if re.search(r"(Args?|Parameters?):", docstring, re.IGNORECASE):
                doc_score += DOC_SCORE_HAS_ARGS
            if re.search(r"Returns?:", docstring, re.IGNORECASE):
                doc_score += DOC_SCORE_HAS_RETURNS
            if re.search(r"(Examples?|Usage):", docstring, re.IGNORECASE):
                doc_score += DOC_SCORE_HAS_EXAMPLES
            if re.search(r"Raises?:", docstring, re.IGNORECASE):
                doc_score += DOC_SCORE_HAS_RAISES

        has_type_hints = bool(
            func_node.returns or any(arg.annotation for arg in func_node.args.args)
        )
        if has_type_hints:
            doc_score += DOC_SCORE_HAS_TYPE_HINTS

        return min(doc_score, DOC_SCORE_MAX), has_docstring, has_type_hints

    def _analyze_function(
        self,
        tree: ast.Module,
        func_info: dict[str, Any],
    ) -> FunctionMetrics | None:
        """
        Analyze a single function and return its metrics.

        Locates the function in the AST and calculates complexity,
        documentation score, and line change metrics.

        Business context: Per-function metrics enable granular tracking
        of AI contributions. Combined with line counts, this shows
        exactly what was modified and the quality of those changes.

        Args:
            tree: Parsed AST module containing the function.
            func_info: Dict with function details:
                - 'name': Function name to find
                - 'modification_type': 'added', 'modified', 'refactored', 'deleted'
                - 'lines_added': Optional int of lines added
                - 'lines_modified': Optional int of lines changed
                - 'lines_deleted': Optional int of lines removed

        Returns:
            FunctionMetrics | None: Metrics dataclass if function found,
                None if the function doesn't exist in the AST.

        Example:
            >>> func_info = {"name": "my_func", "modification_type": "added"}
            >>> metrics = server._analyze_function(tree, func_info)
        """
        func_name = func_info["name"]
        func_node = self._find_function_in_ast(tree, func_name)

        if not func_node:
            logger.debug(f"Function '{func_name}' not found in AST, skipping")
            return None

        complexity = self._calculate_cyclomatic_complexity(func_node)
        doc_score, has_docstring, has_type_hints = self._calculate_documentation_score(func_node)

        return FunctionMetrics(
            function_name=func_name,
            modification_type=func_info["modification_type"],
            lines_added=func_info.get("lines_added", 0),
            lines_modified=func_info.get("lines_modified", 0),
            lines_deleted=func_info.get("lines_deleted", 0),
            complexity=complexity,
            documentation_score=doc_score,
            has_docstring=has_docstring,
            has_type_hints=has_type_hints,
        )

    def _calculate_metrics_summary(
        self, function_metrics: list[dict[str, Any]]
    ) -> tuple[float, float, float]:
        """
        Calculate summary statistics from function metrics.

        Aggregates individual function metrics into session-level summaries
        for complexity, documentation quality, and total effort.

        Business context: Summary statistics enable session-level comparison
        and trend analysis. Effort scores contribute to ROI calculations.

        Args:
            function_metrics: List of function metric dicts, each containing:
                - context.final_complexity: int
                - documentation.quality_score: int
                - value_metrics.effort_score: float

        Returns:
            tuple[float, float, float]: Tuple of (average_complexity,
                average_documentation_score, total_effort_score).
                Returns (0.0, 0.0, 0.0) if list is empty.

        Example:
            >>> metrics = [{"context": {"final_complexity": 5}, ...}]
            >>> avg_cx, avg_doc, effort = server._calculate_metrics_summary(metrics)
        """
        if not function_metrics:
            return 0.0, 0.0, 0.0

        complexity_sum = sum(m["context"]["final_complexity"] for m in function_metrics)
        doc_sum = sum(m["documentation"]["quality_score"] for m in function_metrics)
        total_effort = sum(m["value_metrics"]["effort_score"] for m in function_metrics)

        count = len(function_metrics)
        return complexity_sum / count, doc_sum / count, total_effort

    async def _handle_log_code_metrics(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle log_code_metrics tool for Python code analysis.

        Parses the specified Python file using AST analysis to calculate
        complexity metrics, documentation quality scores, and effort values
        for each modified function. Stores metrics with the session for
        ROI tracking.

        Business context: Code metrics quantify AI contribution beyond just
        time tracking. Complexity and documentation scores help assess code
        quality, while effort scores contribute to ROI calculations.

        Metrics calculated per function:
        - Cyclomatic complexity (branches, loops, exception handlers)
        - Documentation score (0-100 based on docstring completeness)
        - Effort score (lines + complexity-weighted contribution)

        Args:
            args: Tool arguments containing:
                - session_id: Parent session identifier
                - file_path: Absolute path to Python file
                - functions_modified: List of {name, modification_type, lines_*}
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC response with metrics summary including functions_analyzed,
            average_complexity, average_doc_quality, and total_effort_score.

        Raises:
            None - Returns error response for invalid file, syntax errors,
            or missing session.

        Example:
            >>> response = await server._handle_log_code_metrics({
            ...     'session_id': 'abc123',
            ...     'file_path': '/path/to/module.py',
            ...     'functions_modified': [{'name': 'my_func', 'modification_type': 'added'}]
            ... }, msg_id=1)
        """
        try:
            session_id = args["session_id"]
            file_path = args["file_path"]
            functions_modified = args["functions_modified"]

            session_data, error = self._require_session(session_id, msg_id)
            if error:
                return error
            session_data = cast(dict[str, Any], session_data)  # Narrowed by error check

            # Validate file type
            if not file_path.endswith(".py"):
                return self._error_response(
                    msg_id,
                    -32602,
                    f"Unsupported file type: {file_path}. Only Python (.py) files supported.",
                )

            # Read and parse file using helper
            tree, parse_error = self._read_and_parse_python_file(file_path)
            if parse_error:
                return self._error_response(msg_id, -32602, parse_error)
            tree = cast(ast.Module, tree)  # Narrowed by parse_error check

            # Analyze each function using helper
            function_metrics: list[dict[str, Any]] = []
            for func_info in functions_modified:
                metrics = self._analyze_function(tree, func_info)
                if metrics:
                    function_metrics.append(metrics.to_dict())

            # Store metrics with session
            metrics_data = {
                "file_path": file_path,
                "timestamp": datetime.now(UTC).isoformat(),
                "functions": function_metrics,
            }

            if "code_metrics" not in session_data:
                session_data["code_metrics"] = []
            session_data["code_metrics"].append(metrics_data)
            self.storage.update_session(session_id, session_data)

            # Calculate summary using helper
            avg_complexity, avg_doc, total_effort = self._calculate_metrics_summary(
                function_metrics
            )

            logger.info(f"Logged code metrics for {len(function_metrics)} functions in {file_path}")

            response_text = f"""
📊 Code Metrics Logged
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
File: {file_path}
Functions: {len(function_metrics)}

SUMMARY:
• Avg Complexity: {avg_complexity:.1f}
• Avg Doc Score: {avg_doc:.0f}/100
• Total Effort: {total_effort:.1f}

Session: {session_id}
"""
            return self._success_response(
                msg_id,
                response_text,
                {
                    "functions_analyzed": len(function_metrics),
                    "average_complexity": round(avg_complexity, 2),
                    "average_doc_quality": round(avg_doc, 2),
                    "total_effort_score": round(total_effort, 2),
                },
            )

        except KeyError as e:
            return self._error_response(msg_id, -32602, f"Missing required parameter: {e}")
        except Exception as e:
            logger.error(f"Error calculating code metrics: {e}")
            return self._error_response(msg_id, -32603, f"Failed to calculate metrics: {e}")

    async def _handle_get_observability(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle get_ai_observability tool for analytics retrieval.

        Generates a comprehensive text report containing all session metrics,
        ROI calculations, effectiveness distribution, and issue summaries.
        Optionally filters to a specific session.

        Business context: The observability report provides stakeholders
        with complete visibility into AI-assisted development. Used for
        periodic reviews, ROI justification, and trend analysis.

        Args:
            args: Tool arguments containing:
                - session_id: (optional) Filter to specific session
                - time_range: (optional) 'last_day', 'last_week', or 'all'
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC response with formatted text report including session
            summary, ROI metrics, effectiveness distribution, issue counts,
            and code metrics summary.

        Raises:
            None - Returns error response if specified session not found.

        Example:
            >>> response = await server._handle_get_observability(
            ...     {'session_id': 'abc123'},
            ...     msg_id=1
            ... )
            >>> # Returns comprehensive analytics report text
        """
        try:
            sessions = self.storage.load_sessions()
            interactions = self.storage.load_interactions()
            issues = self.storage.load_issues()

            # Filter by session if specified
            session_id = args.get("session_id")
            if session_id:
                if session_id not in sessions:
                    return self._error_response(msg_id, -32602, f"Session not found: {session_id}")
                sessions = {session_id: sessions[session_id]}
                interactions = [i for i in interactions if i.get("session_id") == session_id]
                issues = [i for i in issues if i.get("session_id") == session_id]

            # Generate report
            report = self.stats_engine.generate_summary_report(sessions, interactions, issues)

            return self._success_response(msg_id, report)

        except Exception as e:
            logger.error(f"Error generating observability report: {e}")
            return self._error_response(msg_id, -32603, f"Failed to generate report: {e}")

    async def _handle_get_active_sessions(
        self, _args: dict[str, Any], msg_id: Any
    ) -> dict[str, Any]:
        """
        Handle get_active_sessions tool to list sessions that haven't ended.

        Returns a list of currently active sessions (status != 'completed')
        with their IDs and names. Useful when session_id is lost due to
        context summarization.

        Business context: AI agents may lose track of their session_id
        during long conversations. This tool enables recovery by listing
        active sessions that can then be ended properly.

        Args:
            args: Tool arguments (currently none required).
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            Success response with list of active sessions including:
            - session_id: The ID needed for end_ai_session
            - session_name: Human-readable name
            - task_type: The type of task
            - start_time: When the session started

        Example:
            >>> response = await server._handle_get_active_sessions({}, 1)
            >>> # Response lists sessions that can be ended
        """
        try:
            sessions = self.storage.load_sessions()
            active_sessions = []

            for session_id, session in sessions.items():
                if session.get("status") != "completed":
                    active_sessions.append(
                        {
                            "session_id": session_id,
                            "session_name": session.get("session_name", "Unknown"),
                            "task_type": session.get("task_type", "Unknown"),
                            "start_time": session.get("start_time", "Unknown"),
                        }
                    )

            if not active_sessions:
                return self._success_response(msg_id, "No active sessions found.")

            response_text = f"Found {len(active_sessions)} active session(s):\n\n"
            for s in active_sessions:
                response_text += (
                    f"• **{s['session_name']}**\n"
                    f"  - ID: `{s['session_id']}`\n"
                    f"  - Type: {s['task_type']}\n"
                    f"  - Started: {s['start_time']}\n\n"
                )

            return self._success_response(
                msg_id,
                response_text,
                {"active_sessions": active_sessions},
            )

        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return self._error_response(msg_id, -32603, f"Failed to get active sessions: {e}")

    # =========================================================================
    # RESPONSE HELPERS
    # =========================================================================

    def _success_response(
        self,
        msg_id: Any,
        text: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build a successful JSON-RPC 2.0 response with text content.

        Constructs a properly formatted MCP response containing text content
        for display to the user, plus optional extra data fields that can
        be used by the client for further processing.

        Business context: MCP responses are displayed in VS Code's chat
        panel. The text content appears to the user while extra fields
        can be used for programmatic purposes (e.g., session_id for chaining).

        Args:
            msg_id: JSON-RPC message ID from the request. Must be echoed
                back unchanged for proper request/response correlation.
            text: Human-readable text content to display. Supports markdown
                formatting in most MCP clients.
            extra: Optional additional fields to include in the result.
                Commonly used to return values like session_id, counts, etc.

        Returns:
            Dict with JSON-RPC 2.0 structure:
            {'jsonrpc': '2.0', 'id': msg_id, 'result': {'content': [...], ...}}

        Raises:
            None - This is a pure data construction function.

        Example:
            >>> response = server._success_response(
            ...     msg_id=1,
            ...     text="Session started!",
            ...     extra={'session_id': 'abc123'}
            ... )
            >>> response['result']['session_id']
            'abc123'
        """
        result: dict[str, Any] = {
            "content": [{"type": "text", "text": text}],
        }
        if extra:
            result.update(extra)
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _error_response(self, msg_id: Any, code: int, message: str) -> dict[str, Any]:
        """
        Build a JSON-RPC 2.0 error response.

        Constructs a properly formatted error response following the
        JSON-RPC 2.0 specification. Used when tool execution fails due
        to validation errors, missing data, or internal exceptions.

        Business context: Error responses are displayed to users in VS Code
        and should include actionable messages explaining what went wrong
        and how to fix it.

        Args:
            msg_id: JSON-RPC message ID from the request. Must be echoed
                back unchanged for proper request/response correlation.
            code: Standard JSON-RPC 2.0 error code:
                -32700: Parse error
                -32600: Invalid request
                -32601: Method not found
                -32602: Invalid params
                -32603: Internal error
            message: Human-readable error message describing the failure.

        Returns:
            Dict with JSON-RPC 2.0 error structure:
            {'jsonrpc': '2.0', 'id': msg_id, 'error': {'code': ..., 'message': ...}}

        Raises:
            None - This is a pure data construction function.

        Example:
            >>> response = server._error_response(
            ...     msg_id=1,
            ...     code=-32602,
            ...     message="Session not found: xyz"
            ... )
            >>> response['error']['code']
            -32602
        """
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": code, "message": message},
        }

    def _require_session(
        self, session_id: str, msg_id: Any
    ) -> tuple[dict[str, Any], None] | tuple[None, dict[str, Any]]:
        """
        Validate session exists and return data or error response.

        Consolidates the repeated pattern of fetching a session and
        returning an error response if not found. Reduces duplication
        across tool handlers that require an active session.

        Business context: Most MCP tools require a valid session context.
        This helper provides consistent error handling and reduces
        boilerplate in tool handlers.

        Args:
            session_id: Session identifier to look up in storage.
            msg_id: JSON-RPC message ID for error response formatting.

        Returns:
            tuple[dict[str, Any], None] | tuple[None, dict[str, Any]]:
                On success: (session_data dict, None)
                On failure: (None, JSON-RPC error response dict)

        Raises:
            No exceptions raised. Returns error response tuple on failure.

        Example:
            >>> session_data, error = server._require_session("abc123", msg_id=1)
            >>> if error:
            ...     return error
            >>> # Use session_data...
        """
        session_data = self.storage.get_session(session_id)
        if not session_data:
            return None, self._error_response(msg_id, -32602, f"Session not found: {session_id}")
        return session_data, None

    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Route incoming MCP JSON-RPC message to appropriate handler.

        Parses the JSON-RPC method and dispatches to the corresponding
        handler: initialize for capability exchange, tools/list for
        discovery, or tools/call for actual tool execution.

        Business context: This is the core message router for the MCP
        server. Every interaction from VS Code passes through here,
        making it critical for server reliability.

        Supported methods:
        - 'initialize': Returns server capabilities and protocol version
        - 'tools/list': Returns available tool definitions with schemas
        - 'tools/call': Executes requested tool and returns result

        Args:
            message: Parsed JSON-RPC message dict containing:
                - 'method': str - RPC method name
                - 'id': Any - Request ID for response correlation
                - 'params': dict - Method parameters (for tools/call)

        Returns:
            JSON-RPC response dict, either success or error format
            depending on method validity and execution result.

        Raises:
            None - All exceptions are caught and returned as error responses.

        Example:
            >>> message = {'method': 'tools/list', 'id': 1, 'params': {}}
            >>> response = await server.handle_message(message)
            >>> 'tools' in response['result']
            True
        """
        method = message.get("method", "")
        msg_id = message.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": Config.MCP_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": Config.SERVER_NAME,
                        "version": Config.SERVER_VERSION,
                    },
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": list(self.tools.values())},
            }

        if method == "tools/call":
            params = message.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            handler = self._tool_handlers.get(tool_name)
            if handler:
                return await handler(arguments, msg_id)
            else:
                return self._error_response(msg_id, -32601, f"Unknown tool: {tool_name}")

        return self._error_response(msg_id, -32601, f"Unknown method: {method}")

    async def run(self) -> None:  # pragma: no cover
        """
        Run the MCP server event loop in stdio mode.

        Continuously reads JSON-RPC messages from stdin, processes them
        through handle_message, and writes responses to stdout. Runs until
        EOF on stdin (client disconnect) or unrecoverable error.

        Business context: This is the main entry point for MCP server
        operation. VS Code spawns this process and communicates via stdin/stdout,
        making this the bridge between the editor and tracking functionality.

        Protocol flow:
        1. Read line from stdin
        2. Parse as JSON
        3. Dispatch to handle_message
        4. Serialize response as JSON
        5. Write to stdout with flush
        6. Repeat until EOF

        Returns:
            None. This method blocks until the server shuts down.

        Raises:
            None - All exceptions are caught and logged. Parse errors
            result in JSON-RPC error responses. Other errors cause shutdown.

        Example:
            >>> server = SessionTrackerServer()
            >>> await server.run()  # Blocks until stdin EOF
        """
        logger.info(f"Starting {Config.SERVER_NAME} v{Config.SERVER_VERSION}...")

        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    message = json.loads(line)
                    logger.debug(f"Received: {message}")

                    response = await self.handle_message(message)

                    response_json = json.dumps(response)
                    print(response_json, flush=True)
                    logger.debug(f"Sent: {response}")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "Parse error"},
                    }
                    print(json.dumps(error_response), flush=True)

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                break

        # Close any active sessions on shutdown
        await self._close_active_sessions()
        logger.info("Server shutting down")

    async def _close_active_sessions(self) -> None:
        """
        Close all active sessions on server shutdown.

        Delegates to SessionService to find any sessions with status 'active'
        and mark them as completed with outcome 'partial' and a note indicating
        server shutdown. This ensures no sessions are left orphaned when the
        server stops.

        Business context: Active sessions left open when the server stops
        would show incorrect metrics (infinite duration). Auto-closing
        ensures data integrity and accurate tracking.

        Args:
            None.

        Returns:
            None. Sessions are updated in storage.

        Raises:
            Exception: Logs but does not propagate storage errors to allow
                graceful shutdown to continue.

        Example:
            >>> await server._close_active_sessions()
            # All active sessions now marked completed
        """
        self.session_service.close_active_sessions_on_shutdown()


async def main() -> None:  # pragma: no cover
    """
    Entry point for the AI Session Tracker MCP server.

    Creates a new SessionTrackerServer instance with default storage
    configuration and starts the main event loop. This function is
    called when the module is run directly or via the CLI.

    Business context: This is the primary server startup path used by
    VS Code when it spawns the MCP server process based on mcp.json
    configuration.

    Returns:
        None. This function blocks until the server shuts down.

    Raises:
        OSError: If storage directory cannot be created or accessed.
        Other exceptions are caught and logged by the server.

    Example:
        >>> # From command line:
        >>> # python -m ai_session_tracker_mcp.server
        >>> # Or programmatically:
        >>> import asyncio
        >>> asyncio.run(main())
    """
    server = SessionTrackerServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
