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
from typing import Any

from .config import Config
from .models import FunctionMetrics, Interaction, Issue, Session
from .statistics import StatisticsEngine
from .storage import StorageManager

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

    def __init__(self, storage: StorageManager | None = None) -> None:
        """
        Initialize the MCP server with storage and tool registry.

        Sets up the session tracker server with storage backend, statistics
        engine, and tool definitions. Can accept a custom storage manager
        for testing with mock filesystems.

        Business context: The server is the core component that handles
        all MCP tool requests from VS Code. Proper initialization ensures
        reliable session tracking throughout development workflows.

        Args:
            storage: Optional StorageManager instance. If None, creates a
                new StorageManager with default configuration. Pass a custom
                instance for testing or custom storage paths.

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
        self.stats_engine = StatisticsEngine()

        # Tool name -> executor method mapping
        self._tool_handlers = {
            "start_ai_session": self._handle_start_session,
            "log_ai_interaction": self._handle_log_interaction,
            "end_ai_session": self._handle_end_session,
            "flag_ai_issue": self._handle_flag_issue,
            "log_code_metrics": self._handle_log_code_metrics,
            "get_ai_observability": self._handle_get_observability,
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
            "start_ai_session": {
                "name": "start_ai_session",
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
                        "human_time_estimate_minutes": {
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
                    },
                    "required": [
                        "session_name",
                        "task_type",
                        "model_name",
                        "human_time_estimate_minutes",
                        "estimate_source",
                    ],
                },
            },
            "log_ai_interaction": {
                "name": "log_ai_interaction",
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
            "end_ai_session": {
                "name": "end_ai_session",
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
                    },
                    "required": ["session_id", "outcome"],
                },
            },
            "flag_ai_issue": {
                "name": "flag_ai_issue",
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
                                "Issue category " "(e.g., 'incorrect_output', 'hallucination')"
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
            "log_code_metrics": {
                "name": "log_code_metrics",
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
            "get_ai_observability": {
                "name": "get_ai_observability",
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
        }

    # =========================================================================
    # TOOL HANDLERS
    # =========================================================================

    async def _handle_start_session(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle start_ai_session tool to begin a new tracking session.

        Creates a new session with a unique generated ID, persists it to
        storage, and returns a formatted response with the session ID and
        workflow reminder. This should be the first tool called in any
        AI-assisted task.

        Business context: Session creation is the entry point for all
        tracking. The generated session_id is used in all subsequent
        tool calls to associate interactions and issues with this work.

        Args:
            args: Tool arguments containing:
                - session_name: Descriptive name for the task
                - task_type: Category from Config.TASK_TYPES
                - model_name: AI model being used (e.g., 'claude-opus-4-20250514')
                - human_time_estimate_minutes: Baseline time estimate
                - estimate_source: 'manual', 'issue_tracker', or 'historical'
                - context: (optional) Additional context string
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC success response with session_id in both text
            content and result metadata, or error response on failure.

        Raises:
            None - Returns error response on exception.

        Example:
            >>> response = await server._handle_start_session({
            ...     'session_name': 'Add login',
            ...     'task_type': 'code_generation',
            ...     'model_name': 'claude-opus-4-20250514',
            ...     'human_time_estimate_minutes': 60,
            ...     'estimate_source': 'manual'
            ... }, msg_id=1)
        """
        try:
            session = Session.create(
                name=args["session_name"],
                task_type=args["task_type"],
                model_name=args["model_name"],
                human_time_estimate_minutes=float(args["human_time_estimate_minutes"]),
                estimate_source=args["estimate_source"],
                context=args.get("context", ""),
            )

            sessions = self.storage.load_sessions()
            sessions[session.id] = session.to_dict()
            self.storage.save_sessions(sessions)

            logger.info(f"Started session: {session.id}")

            response_text = f"""
✅ Session Started: {session.id}
Type: {session.task_type} | Model: {session.model_name}
Estimate: {session.human_time_estimate_minutes:.0f}min ({session.estimate_source})

⚠️ Log interactions! Call log_ai_interaction(session_id, prompt, rating 1-5) after responses.
"""
            return self._success_response(msg_id, response_text, {"session_id": session.id})

        except Exception as e:
            logger.error(f"Error starting session: {e}")
            return self._error_response(msg_id, -32603, f"Failed to start session: {e}")

    async def _handle_log_interaction(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle log_ai_interaction tool to record a prompt/response exchange.

        Records an AI interaction with effectiveness rating, updates the
        parent session's running statistics (total interactions, average
        effectiveness), and persists both to storage.

        Business context: Interaction logging captures the granular quality
        data needed for effectiveness analysis. The rating (1-5) reflects
        how useful the AI output was, building the dataset for ROI metrics.

        Args:
            args: Tool arguments containing:
                - session_id: Parent session identifier
                - prompt: The prompt text sent to AI
                - response_summary: Brief description of AI response
                - effectiveness_rating: Integer 1-5 (1=failed, 5=perfect)
                - iteration_count: (optional) Number of attempts, default 1
                - tools_used: (optional) List of MCP tools used
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC success response with rating visualization and
            session statistics, or error response on failure.

        Raises:
            None - Returns error response on exception or missing session.

        Example:
            >>> response = await server._handle_log_interaction({
            ...     'session_id': 'abc123',
            ...     'prompt': 'Add user validation',
            ...     'response_summary': 'Created validate_user function',
            ...     'effectiveness_rating': 4
            ... }, msg_id=1)
        """
        try:
            session_id = args["session_id"]
            session_data = self.storage.get_session(session_id)

            if not session_data:
                return self._error_response(msg_id, -32602, f"Session not found: {session_id}")

            interaction = Interaction.create(
                session_id=session_id,
                prompt=args["prompt"],
                response_summary=args["response_summary"],
                effectiveness_rating=args["effectiveness_rating"],
                iteration_count=args.get("iteration_count", 1),
                tools_used=args.get("tools_used", []),
            )

            self.storage.add_interaction(interaction.to_dict())

            # Update session statistics
            session_interactions = self.storage.get_session_interactions(session_id)
            total = len(session_interactions)
            avg_eff = sum(i["effectiveness_rating"] for i in session_interactions) / total

            session_data["total_interactions"] = total
            session_data["avg_effectiveness"] = round(avg_eff, 2)
            self.storage.update_session(session_id, session_data)

            logger.info(
                f"Logged interaction for session {session_id}, "
                f"rating: {interaction.effectiveness_rating}"
            )

            rating = interaction.effectiveness_rating
            stars = "★" * rating + "☆" * (5 - rating)
            response_text = f"""
📝 Logged: {stars} ({rating}/5) | Iterations: {interaction.iteration_count}
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

        Marks the session as completed with end timestamp and outcome,
        calculates final duration metrics, and persists the updated
        session. Returns a summary of session performance.

        Business context: Session completion triggers final metric
        calculation. The duration becomes the actual AI time used for
        ROI comparison against the human baseline estimate.

        Args:
            args: Tool arguments containing:
                - session_id: Session identifier to complete
                - outcome: 'success', 'partial', or 'failed'
                - notes: (optional) Summary notes about the session
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC success response with session summary including
            duration, interaction count, and effectiveness average,
            or error response on failure.

        Raises:
            None - Returns error response on exception or missing session.

        Example:
            >>> response = await server._handle_end_session({
            ...     'session_id': 'abc123',
            ...     'outcome': 'success',
            ...     'notes': 'Completed login feature'
            ... }, msg_id=1)
        """
        try:
            session_id = args["session_id"]
            session_data = self.storage.get_session(session_id)

            if not session_data:
                return self._error_response(msg_id, -32602, f"Session not found: {session_id}")

            # Update session
            session_data["status"] = "completed"
            session_data["end_time"] = datetime.now(UTC).isoformat()
            session_data["outcome"] = args["outcome"]
            session_data["notes"] = args.get("notes", "")

            self.storage.update_session(session_id, session_data)

            # Calculate duration
            duration = self.stats_engine.calculate_session_duration_minutes(session_data)

            # Get session issues
            issues = self.storage.get_session_issues(session_id)

            logger.info(f"Ended session {session_id}, outcome: {args['outcome']}")

            interactions = session_data.get("total_interactions", 0)
            avg_eff = session_data.get("avg_effectiveness", 0)
            response_text = f"""
✅ Session Ended: {session_id}
Duration: {duration:.1f}min | Outcome: {args['outcome']}
Metrics: {interactions} interactions, {avg_eff:.1f}/5 avg, {len(issues)} issues
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

        Records an issue with type and severity for later analysis.
        Issues help identify patterns in AI failures and areas needing
        improved prompting or different approaches.

        Business context: Issue tracking is essential for continuous
        improvement of AI workflows. Analyzing issue patterns helps
        teams develop better prompting strategies and identify when
        to adjust AI tool usage.

        Args:
            args: Tool arguments containing:
                - session_id: Parent session identifier
                - issue_type: Category (e.g., 'hallucination', 'incorrect_output')
                - description: Detailed description of the problem
                - severity: 'low', 'medium', 'high', or 'critical'
            msg_id: JSON-RPC message ID for response correlation.

        Returns:
            JSON-RPC success response with issue confirmation including
            severity emoji indicator, or error response on failure.

        Raises:
            None - Returns error response on exception or missing session.

        Example:
            >>> response = await server._handle_flag_issue({
            ...     'session_id': 'abc123',
            ...     'issue_type': 'hallucination',
            ...     'description': 'Referenced non-existent API',
            ...     'severity': 'medium'
            ... }, msg_id=1)
        """
        try:
            session_id = args["session_id"]
            session_data = self.storage.get_session(session_id)

            if not session_data:
                return self._error_response(msg_id, -32602, f"Session not found: {session_id}")

            issue = Issue.create(
                session_id=session_id,
                issue_type=args["issue_type"],
                description=args["description"],
                severity=args["severity"],
            )

            self.storage.add_issue(issue.to_dict())

            logger.info(
                f"Flagged issue for session {session_id}: "
                f"{args['issue_type']} ({args['severity']})"
            )

            severity_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
            emoji = severity_emoji.get(args["severity"], "⚪")

            response_text = f"""
{emoji} Issue Flagged: {args['issue_type']} ({args['severity'].upper()})
Session: {session_id}
📋 Next: log_ai_interaction() or end_ai_session()
"""
            return self._success_response(msg_id, response_text)

        except KeyError as e:
            return self._error_response(msg_id, -32602, f"Missing required parameter: {e}")
        except Exception as e:
            logger.error(f"Error flagging issue: {e}")
            return self._error_response(msg_id, -32603, f"Failed to flag issue: {e}")

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

            session_data = self.storage.get_session(session_id)
            if not session_data:
                return self._error_response(msg_id, -32602, f"Session not found: {session_id}")

            # Validate file type
            if not file_path.endswith(".py"):
                return self._error_response(
                    msg_id,
                    -32602,
                    f"Unsupported file type: {file_path}. Only Python (.py) files supported.",
                )

            # Read and parse file
            try:
                with open(file_path, encoding="utf-8") as f:
                    code = f.read()
                tree = ast.parse(code)
            except FileNotFoundError:
                return self._error_response(msg_id, -32602, f"File not found: {file_path}")
            except SyntaxError as e:
                return self._error_response(msg_id, -32602, f"Syntax error in file: {e}")

            # Analyze each function
            function_metrics: list[dict[str, Any]] = []

            for func_info in functions_modified:
                func_name = func_info["name"]
                mod_type = func_info["modification_type"]

                # Find function in AST
                func_node = None
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                        and node.name == func_name
                    ):
                        func_node = node
                        break

                if not func_node:
                    logger.debug(f"Function '{func_name}' not found in AST, skipping")
                    continue

                # Calculate cyclomatic complexity
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

                # Calculate documentation score
                docstring = ast.get_docstring(func_node)
                doc_score = 0
                has_docstring = docstring is not None

                if docstring:
                    doc_score += 30  # Has docstring
                    if len(docstring) > 50:
                        doc_score += 10
                    if re.search(r"(Args?|Parameters?):", docstring, re.IGNORECASE):
                        doc_score += 20
                    if re.search(r"Returns?:", docstring, re.IGNORECASE):
                        doc_score += 20
                    if re.search(r"(Examples?|Usage):", docstring, re.IGNORECASE):
                        doc_score += 10
                    if re.search(r"Raises?:", docstring, re.IGNORECASE):
                        doc_score += 5

                # Check type hints
                has_type_hints = bool(
                    func_node.returns or any(arg.annotation for arg in func_node.args.args)
                )
                if has_type_hints:
                    doc_score += 5

                metrics = FunctionMetrics(
                    function_name=func_name,
                    modification_type=mod_type,
                    lines_added=func_info.get("lines_added", 0),
                    lines_modified=func_info.get("lines_modified", 0),
                    lines_deleted=func_info.get("lines_deleted", 0),
                    complexity=complexity,
                    documentation_score=min(doc_score, 100),
                    has_docstring=has_docstring,
                    has_type_hints=has_type_hints,
                )
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

            # Calculate summary
            if function_metrics:
                complexity_sum = sum(m["context"]["final_complexity"] for m in function_metrics)
                doc_sum = sum(m["documentation"]["quality_score"] for m in function_metrics)
                total_effort = sum(m["value_metrics"]["effort_score"] for m in function_metrics)
                avg_complexity = complexity_sum / len(function_metrics)
                avg_doc = doc_sum / len(function_metrics)
            else:
                avg_complexity = avg_doc = total_effort = 0

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

    async def run(self) -> None:
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

        Finds any sessions with status 'active' and marks them as completed
        with outcome 'partial' and a note indicating server shutdown. This
        ensures no sessions are left orphaned when the server stops.

        Business context: Active sessions left open when the server stops
        would show incorrect metrics (infinite duration). Auto-closing
        ensures data integrity and accurate tracking.

        Returns:
            None. Sessions are updated in storage.

        Example:
            >>> await server._close_active_sessions()
            # All active sessions now marked completed
        """
        try:
            sessions = self.storage.load_sessions()
            active_count = 0

            for session_id, session_data in sessions.items():
                if session_data.get("status") == "active":
                    session_data["status"] = "completed"
                    session_data["end_time"] = datetime.now(UTC).isoformat()
                    session_data["outcome"] = "partial"
                    session_data["notes"] = (
                        session_data.get("notes", "") + " [Auto-closed on server shutdown]"
                    ).strip()
                    sessions[session_id] = session_data
                    active_count += 1
                    logger.info(f"Auto-closed active session: {session_id}")

            if active_count > 0:
                self.storage.save_sessions(sessions)
                logger.info(f"Auto-closed {active_count} active session(s) on shutdown")

        except Exception as e:
            logger.error(f"Error closing active sessions: {e}")


async def main() -> None:
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
