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
        Initialize MCP server with storage and tool registry.

        Args:
            storage: Optional StorageManager. Creates new one if None.
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
        Build tool registry with JSON schemas.

        SCHEMA DESIGN:
        - Required params: Essential for tool operation
        - Optional params: Have defaults, enhance functionality
        - Descriptions: Guide AI on when/how to use

        Returns:
            Dict of tool_name -> tool_definition
        """
        return {
            "start_ai_session": {
                "name": "start_ai_session",
                "description": (
                    "Start a new AI coding session for tracking workflow metrics. "
                    "⚠️ CALL THIS FIRST at the start of every coding task. "
                    "Returns session_id for subsequent tool calls."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_name": {
                            "type": "string",
                            "description": (
                                "Descriptive name for this session "
                                "(e.g., 'Add user authentication')"
                            ),
                        },
                        "task_type": {
                            "type": "string",
                            "description": "Task category",
                            "enum": list(Config.TASK_TYPES),
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context about the work",
                            "default": "",
                        },
                    },
                    "required": ["session_name", "task_type"],
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
                                "Issue category (e.g., 'incorrect_output', "
                                "'hallucination', 'poor_prompt')"
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
                    "Currently supports Python files only."
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
        Handle start_ai_session tool.

        Creates new session with generated ID and persists to storage.

        Args:
            args: Tool arguments (session_name, task_type, context)
            msg_id: JSON-RPC message ID

        Returns:
            JSON-RPC response with session_id.
        """
        try:
            session = Session.create(
                name=args["session_name"],
                task_type=args["task_type"],
                context=args.get("context", ""),
            )

            sessions = self.storage.load_sessions()
            sessions[session.id] = session.to_dict()
            self.storage.save_sessions(sessions)

            logger.info(f"Started session: {session.id}")

            response_text = f"""
✅ Session Started Successfully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session ID: {session.id}
Task Type: {session.task_type}
Started: {session.start_time}

📋 WORKFLOW REMINDER:
1. ✅ Session started (complete)
2. ⏳ Do your work (code generation, debugging, etc.)
3. ⏳ Log interactions: log_ai_interaction()
4. ⏳ Flag issues if needed: flag_ai_issue()
5. ⏳ End session when done: end_ai_session()
"""
            return self._success_response(msg_id, response_text, {"session_id": session.id})

        except Exception as e:
            logger.error(f"Error starting session: {e}")
            return self._error_response(msg_id, -32603, f"Failed to start session: {e}")

    async def _handle_log_interaction(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle log_ai_interaction tool.

        Records interaction and updates session statistics.

        Args:
            args: Tool arguments (session_id, prompt, response_summary, etc.)
            msg_id: JSON-RPC message ID

        Returns:
            JSON-RPC response confirming log.
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
📝 Interaction Logged
━━━━━━━━━━━━━━━━━━━━━━━━
Rating: {stars} ({rating}/5)
Iterations: {interaction.iteration_count}
Session Total: {total} interactions
Session Avg: {avg_eff:.1f}/5
"""
            return self._success_response(msg_id, response_text)

        except KeyError as e:
            return self._error_response(msg_id, -32602, f"Missing required parameter: {e}")
        except Exception as e:
            logger.error(f"Error logging interaction: {e}")
            return self._error_response(msg_id, -32603, f"Failed to log interaction: {e}")

    async def _handle_end_session(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle end_ai_session tool.

        Marks session complete and calculates final metrics.

        Args:
            args: Tool arguments (session_id, outcome, notes)
            msg_id: JSON-RPC message ID

        Returns:
            JSON-RPC response with session summary.
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

            response_text = f"""
✅ Session Completed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session: {session_id}
Duration: {duration:.1f} minutes
Outcome: {args['outcome']}

📊 SESSION METRICS:
• Interactions: {session_data.get('total_interactions', 0)}
• Avg Effectiveness: {session_data.get('avg_effectiveness', 0):.1f}/5
• Issues Flagged: {len(issues)}

💡 View full analytics with get_ai_observability()
"""
            return self._success_response(msg_id, response_text)

        except KeyError as e:
            return self._error_response(msg_id, -32602, f"Missing required parameter: {e}")
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return self._error_response(msg_id, -32603, f"Failed to end session: {e}")

    async def _handle_flag_issue(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle flag_ai_issue tool.

        Records issue for later analysis.

        Args:
            args: Tool arguments (session_id, issue_type, description, severity)
            msg_id: JSON-RPC message ID

        Returns:
            JSON-RPC response confirming issue logged.
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
{emoji} Issue Flagged
━━━━━━━━━━━━━━━━━━━━━━━━
Type: {args['issue_type']}
Severity: {args['severity'].upper()}
Session: {session_id}

Description: {args['description'][:100]}{'...' if len(args['description']) > 100 else ''}

📋 Continue workflow with log_ai_interaction() or end_ai_session()
"""
            return self._success_response(msg_id, response_text)

        except KeyError as e:
            return self._error_response(msg_id, -32602, f"Missing required parameter: {e}")
        except Exception as e:
            logger.error(f"Error flagging issue: {e}")
            return self._error_response(msg_id, -32603, f"Failed to flag issue: {e}")

    async def _handle_log_code_metrics(self, args: dict[str, Any], msg_id: Any) -> dict[str, Any]:
        """
        Handle log_code_metrics tool.

        Analyzes Python file with AST to calculate complexity and doc quality.

        Args:
            args: Tool arguments (session_id, file_path, functions_modified)
            msg_id: JSON-RPC message ID

        Returns:
            JSON-RPC response with metrics summary.

        LIMITATIONS:
        - Python files only (requires AST parsing)
        - File must be syntactically valid
        - Function must exist in file
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
        Handle get_ai_observability tool.

        Generates comprehensive analytics report.

        Args:
            args: Tool arguments (session_id, time_range)
            msg_id: JSON-RPC message ID

        Returns:
            JSON-RPC response with analytics report.
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
        """Build successful JSON-RPC response."""
        result: dict[str, Any] = {
            "content": [{"type": "text", "text": text}],
        }
        if extra:
            result.update(extra)
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _error_response(self, msg_id: Any, code: int, message: str) -> dict[str, Any]:
        """Build error JSON-RPC response."""
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
        Route incoming MCP message to appropriate handler.

        SUPPORTED METHODS:
        - initialize: Return server capabilities
        - tools/list: Return tool definitions
        - tools/call: Execute requested tool

        Args:
            message: Parsed JSON-RPC message

        Returns:
            JSON-RPC response dict.
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
        Run MCP server event loop (stdio mode).

        Reads JSON-RPC messages from stdin, processes them, writes responses to stdout.
        Runs until EOF on stdin or unrecoverable error.
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

        logger.info("Server shutting down")


async def main() -> None:
    """Entry point for MCP server."""
    server = SessionTrackerServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
