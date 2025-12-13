#!/usr/bin/env python3
"""Analyze MCP tool overhead and context window usage.

This script queries MCP servers and estimates token usage to help
identify pruning opportunities for reducing context window overhead.

Usage:
    python utils/analyze_mcp_overhead.py [--json] [--verbose]
    python utils/analyze_mcp_overhead.py --replay <chat_replay.json>  # Use active tools from replay
    python utils/analyze_mcp_overhead.py --prune  # Get detailed pruning recommendations

Exit Codes:
    0: Success
    1: Fatal error (reserved for future use)

GitHub Copilot Context Buffers:
    1. Instructions buffer: System prompts, chat modes, .instructions.md files
       NOTE: Instructions buffer is FIXED at 8K tokens across all models
    2. Tools buffer: All tool schemas (MCP + built-in)
    3. Context buffer: Conversation history, file contents, workspace info

Primary Models (recommended for coding + documentation):
    - claude-opus-4.5: Best for complex reasoning, architecture, documentation
    - claude-sonnet-4: Best for day-to-day coding, fast responses
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Public API exports
__all__ = [
    # Dataclasses
    "AnalysisContext",
    "TokenAggregation",
    "MCPServerInfo",
    "ToolInfo",
    "InstructionFile",
    "ModelConfig",
    "BuiltinToolSpec",
    # Functions
    "run_analysis",
    "print_analysis",
    "print_analysis_from_context",
    "parse_chat_replay",
    "get_model_config",
    "get_all_model_names",
    "identify_pruning_candidates",
    "calculate_buffer_usage",
]

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Token estimation constants
CHARS_PER_TOKEN = 4  # Approximate chars per token for English text
TOKENS_PER_TOOL_NAME = 5
TOKENS_PER_PARAMETER = 15
TOKENS_JSON_OVERHEAD = 20

# Pruning thresholds
LARGE_TOOL_THRESHOLD_TOKENS = 400
OVERHEAD_WARNING_THRESHOLD_PCT = 80
OVERHEAD_MODERATE_THRESHOLD_PCT = 50

# Prunable tool categories with detection patterns and disable actions
PRUNABLE_CATEGORIES: dict[str, dict[str, Any]] = {
    "notebook": {
        "patterns": ["notebook"],
        "reason": "Disable if not using Jupyter notebooks",
        "action": "Disable 'github.copilot.chat.agent.notebooks.enabled' in VS Code settings",
        "source": "vscode:notebooks",
    },
    "python": {
        "patterns": ["python", "pylance"],
        "reason": "Disable if not working on Python projects",
        "action": "Disable Pylance MCP in VS Code settings or remove Python extension",
        "source": "vscode:python",
    },
    "vscode_api": {
        "patterns": ["vscode"],
        "extra_pattern": "api",  # Must also contain 'api'
        "reason": "Disable if not developing VS Code extensions",
        "action": "These tools are for extension development - disable if not needed",
        "source": "vscode:extension_dev",
    },
}

# Subprocess settings
MCP_QUERY_TIMEOUT_SECONDS = 10
SUBPROCESS_TRUST_WARNING = (
    "⚠️  Executing commands from .vscode/mcp.json - ensure config is from trusted source"
)

# Output formatting
BOX_WIDTH = 71  # Width of ASCII box for buffer usage display
BAR_WIDTH = 20  # Width of progress bar (each segment = 5%)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def safe_percentage(value: int | float, total: int | float) -> float:
    """Calculate percentage safely, returning 0.0 if total is zero.

    Args:
        value: Numerator value.
        total: Denominator value (divisor).

    Returns:
        Percentage (0-100) or 0.0 if total is zero.
    """
    return (value / total * 100) if total > 0 else 0.0


def make_progress_bar(percentage: float, width: int = BAR_WIDTH) -> str:
    """Create a progress bar string.

    Args:
        percentage: Percentage value (0-100).
        width: Total width of the bar in characters.

    Returns:
        Progress bar string with filled and empty segments.
    """
    filled = int(percentage / (100 / width))
    filled = max(0, min(width, filled))  # Clamp to valid range
    return "█" * filled + "░" * (width - filled)


@dataclass
class InstructionFile:
    """Information about a Copilot instruction/prompt file.

    Represents .instructions.md, .chatmode.md, and similar files that
    are loaded into the Copilot context.

    Attributes:
        path: File path relative to workspace or user config.
        content: Full text content of the file.
        file_type: Category ('instructions', 'chatmode', 'prompt', 'user_prompt').
    """

    path: Path
    content: str
    file_type: str

    @property
    def char_count(self) -> int:
        """Total character count of the content."""
        return len(self.content)

    @property
    def line_count(self) -> int:
        """Number of lines in the content."""
        return len(self.content.splitlines())

    @property
    def estimated_tokens(self) -> int:
        """Estimate tokens using CHARS_PER_TOKEN constant."""
        return self.char_count // CHARS_PER_TOKEN

    @property
    def relative_path(self) -> str:
        """Get a shortened path for display (max 50 chars)."""
        return str(self.path)[-50:] if len(str(self.path)) > 50 else str(self.path)


# GitHub Copilot buffer limits (estimated from observed behavior)
# These are approximate - actual limits may vary by model/tier
# Buffer allocations are controlled by GitHub Copilot, not the model itself
# The tool/instruction content is the SAME across models, but percentage differs
#
# IMPORTANT: Instructions buffer appears to be FIXED at 8K tokens across all models
# This was confirmed through chat replay analysis on 2025-12-13

# Fixed instruction buffer size (same for all models)
INSTRUCTIONS_BUFFER_FIXED = 8_000

# Primary models for coding + documentation
PRIMARY_MODELS = ["claude-opus-4.5", "claude-sonnet-4"]

# Default model for analysis
DEFAULT_MODEL = "claude-opus-4.5"


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a Copilot model's context window limits.

    Attributes:
        context: Total context window size in tokens.
        tools: Maximum tokens allocated for tool schemas.
        conversation: Maximum tokens for conversation history.
        instructions: Maximum tokens for instruction files (fixed at 8K).
        primary: Whether this is a recommended primary model.
        legacy: Whether this is a legacy/deprecated model.
        notes: Optional usage notes for this model.
    """

    context: int
    tools: int
    conversation: int
    instructions: int = INSTRUCTIONS_BUFFER_FIXED
    primary: bool = False
    legacy: bool = False
    notes: str = ""


# Model configurations as immutable dataclasses
_MODEL_CONFIGS: dict[str, ModelConfig] = {
    # PRIMARY MODELS (Recommended for coding + documentation)
    "claude-opus-4.5": ModelConfig(
        context=200_000,
        tools=32_000,
        conversation=160_000,
        primary=True,
        notes="Best for complex reasoning, architecture, documentation",
    ),
    "claude-sonnet-4": ModelConfig(
        context=200_000,
        tools=32_000,
        conversation=160_000,
        primary=True,
        notes="Best for day-to-day coding, fast responses",
    ),
    # OTHER ANTHROPIC CLAUDE MODELS
    "claude-sonnet-4.5": ModelConfig(context=200_000, tools=32_000, conversation=160_000),
    "claude-haiku-4.5": ModelConfig(context=200_000, tools=32_000, conversation=160_000),
    "claude-opus-4.1": ModelConfig(context=200_000, tools=32_000, conversation=160_000),
    # GOOGLE GEMINI MODELS
    "gemini-2.5-pro": ModelConfig(
        context=1_000_000,
        tools=64_000,
        conversation=920_000,
        notes="Large context, good for multi-file refactoring",
    ),
    "gemini-3-pro": ModelConfig(context=2_000_000, tools=128_000, conversation=1_840_000),
    # OPENAI GPT-5 SERIES
    "gpt-5": ModelConfig(context=256_000, tools=40_000, conversation=206_000),
    "gpt-5-codex": ModelConfig(context=256_000, tools=40_000, conversation=206_000),
    "gpt-5.1": ModelConfig(context=512_000, tools=48_000, conversation=452_000),
    "gpt-5.1-codex": ModelConfig(context=512_000, tools=48_000, conversation=452_000),
    "gpt-5.1-codex-mini": ModelConfig(context=256_000, tools=40_000, conversation=206_000),
    "gpt-5.1-codex-max": ModelConfig(context=1_000_000, tools=64_000, conversation=920_000),
    "gpt-5.2": ModelConfig(context=1_000_000, tools=64_000, conversation=920_000),
    # OTHER MODELS
    "grok-code-fast-1": ModelConfig(context=131_072, tools=24_000, conversation=101_000),
    "raptor-mini": ModelConfig(
        context=264_000,
        tools=40_000,
        conversation=216_000,
        notes="Fast, efficient overhead ratio",
    ),
    # LEGACY MODELS (for reference)
    "gpt-4o": ModelConfig(context=128_000, tools=24_000, conversation=98_000, legacy=True),
    "gpt-4-turbo": ModelConfig(context=128_000, tools=24_000, conversation=98_000, legacy=True),
    "o1": ModelConfig(context=200_000, tools=32_000, conversation=160_000),
    "o1-mini": ModelConfig(context=128_000, tools=24_000, conversation=98_000),
}


def get_model_config(model: str) -> ModelConfig:
    """Get configuration for a model, falling back to default if not found.

    Args:
        model: Model name to look up.

    Returns:
        ModelConfig for the requested model or default model.
    """
    return _MODEL_CONFIGS.get(model, _MODEL_CONFIGS[DEFAULT_MODEL])


def get_all_model_names() -> list[str]:
    """Get list of all supported model names."""
    return list(_MODEL_CONFIGS.keys())


# Legacy compatibility - dict-like access to model configs
COPILOT_MODELS: dict[str, dict[str, Any]] = {
    name: {
        "context": cfg.context,
        "instructions": cfg.instructions,
        "tools": cfg.tools,
        "conversation": cfg.conversation,
        "primary": cfg.primary,
        "legacy": cfg.legacy,
        "notes": cfg.notes,
    }
    for name, cfg in _MODEL_CONFIGS.items()
}


@dataclass(frozen=True)
class BuiltinToolSpec:
    """Specification for a VS Code built-in tool.

    Attributes:
        name: Tool name (e.g., 'read_file', 'run_in_terminal').
        desc_length: Estimated description length in characters.
        params: Parameter names as tuple (suffix '?' for optional, '[]' for array).
    """

    name: str
    desc_length: int
    params: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def create(
        cls, name: str, desc_length: int, params: list[str] | tuple[str, ...]
    ) -> BuiltinToolSpec:
        """Factory method to create BuiltinToolSpec from list or tuple params."""
        return cls(name, desc_length, tuple(params) if isinstance(params, list) else params)


# VS Code built-in tools (estimated from typical Copilot agent sessions)
VSCODE_BUILTIN_TOOLS: dict[str, list[BuiltinToolSpec]] = {
    "file_operations": [
        BuiltinToolSpec.create("create_directory", 195, ["dirPath"]),
        BuiltinToolSpec.create("create_file", 172, ["filePath", "content"]),
        BuiltinToolSpec.create("read_file", 280, ["filePath", "offset?", "limit?"]),
        BuiltinToolSpec.create(
            "replace_string_in_file", 890, ["filePath", "oldString", "newString"]
        ),
        BuiltinToolSpec.create(
            "multi_replace_string_in_file", 680, ["explanation", "replacements[]"]
        ),
        BuiltinToolSpec.create("list_dir", 130, ["path"]),
        BuiltinToolSpec.create("file_search", 485, ["query", "maxResults?"]),
        BuiltinToolSpec.create(
            "grep_search",
            890,
            ["query", "isRegexp", "includePattern?", "includeIgnoredFiles?", "maxResults?"],
        ),
    ],
    "terminal": [
        BuiltinToolSpec.create("run_in_terminal", 1580, ["command", "explanation", "isBackground"]),
        BuiltinToolSpec.create("get_terminal_output", 100, ["id"]),
        BuiltinToolSpec.create("terminal_last_command", 60, []),
        BuiltinToolSpec.create("terminal_selection", 55, []),
    ],
    "tasks": [
        BuiltinToolSpec.create("create_and_run_task", 580, ["task", "workspaceFolder"]),
        BuiltinToolSpec.create("run_task", 320, ["id", "workspaceFolder"]),
        BuiltinToolSpec.create("get_task_output", 120, ["id", "workspaceFolder"]),
    ],
    "testing": [
        BuiltinToolSpec.create(
            "runTests", 480, ["files?", "testNames?", "mode?", "coverageFiles?"]
        ),
        BuiltinToolSpec.create("test_failure", 60, []),
    ],
    "notebooks": [
        BuiltinToolSpec.create("create_new_jupyter_notebook", 295, ["query"]),
        BuiltinToolSpec.create(
            "edit_notebook_file", 780, ["filePath", "editType", "cellId", "language?", "newCode?"]
        ),
        BuiltinToolSpec.create(
            "run_notebook_cell", 480, ["filePath", "cellId", "continueOnError?", "reason?"]
        ),
        BuiltinToolSpec.create("read_notebook_cell_output", 320, ["filePath", "cellId"]),
        BuiltinToolSpec.create("copilot_getNotebookSummary", 420, ["filePath"]),
        BuiltinToolSpec.create("configure_notebook", 280, ["filePath"]),
        BuiltinToolSpec.create("notebook_install_packages", 340, ["filePath", "packageList"]),
        BuiltinToolSpec.create("notebook_list_packages", 280, ["filePath"]),
    ],
    "python": [
        BuiltinToolSpec.create("configure_python_environment", 260, ["resourcePath?"]),
        BuiltinToolSpec.create("get_python_environment_details", 340, ["resourcePath?"]),
        BuiltinToolSpec.create("get_python_executable_details", 520, ["resourcePath?"]),
        BuiltinToolSpec.create("install_python_packages", 240, ["packageList", "resourcePath?"]),
    ],
    "workspace": [
        BuiltinToolSpec.create("create_new_workspace", 1580, ["query"]),
        BuiltinToolSpec.create("get_project_setup_info", 190, ["projectType"]),
        BuiltinToolSpec.create("semantic_search", 260, ["query"]),
        BuiltinToolSpec.create("list_code_usages", 380, ["symbolName", "filePaths?"]),
        BuiltinToolSpec.create("get_errors", 340, ["filePaths?"]),
        BuiltinToolSpec.create(
            "get_changed_files", 210, ["repositoryPath?", "sourceControlState?"]
        ),
    ],
    "vscode_specific": [
        BuiltinToolSpec.create("get_vscode_api", 1650, ["query"]),
        BuiltinToolSpec.create("run_vscode_command", 180, ["commandId", "name", "args?"]),
        BuiltinToolSpec.create("install_extension", 160, ["id", "name"]),
        BuiltinToolSpec.create(
            "vscode_searchExtensions_internal", 520, ["category?", "keywords?", "ids?"]
        ),
        BuiltinToolSpec.create("get_search_view_results", 40, []),
        BuiltinToolSpec.create("manage_todo_list", 1420, ["operation", "todoList?"]),
    ],
    "web": [
        BuiltinToolSpec.create("fetch_webpage", 185, ["urls", "query"]),
        BuiltinToolSpec.create("open_simple_browser", 195, ["url"]),
        BuiltinToolSpec.create("github_repo", 230, ["repo", "query"]),
    ],
}


@dataclass
class ToolInfo:
    """Information about a single MCP or VS Code tool.

    Attributes:
        name: Tool name (e.g., 'read_file', 'run_in_terminal').
        description: Tool description text sent to the model.
        parameters: JSON schema for tool parameters.
        source: Origin identifier (e.g., 'vscode:terminal', 'mcp:gitkraken').
    """

    name: str
    description: str
    parameters: dict[str, Any]
    source: str

    @property
    def desc_chars(self) -> int:
        """Character count of the description."""
        return len(self.description)

    @property
    def param_count(self) -> int:
        """Number of parameters in the tool schema."""
        if "properties" in self.parameters:
            return len(self.parameters["properties"])
        return 0

    @property
    def estimated_tokens(self) -> int:
        """Estimate tokens for this tool schema.

        Uses constants for token estimation:
        - TOKENS_PER_TOOL_NAME for the tool name
        - TOKENS_PER_PARAMETER for each parameter
        - CHARS_PER_TOKEN for description conversion
        - TOKENS_JSON_OVERHEAD for JSON structure
        """
        tokens = TOKENS_PER_TOOL_NAME
        tokens += self.param_count * TOKENS_PER_PARAMETER
        tokens += self.desc_chars // CHARS_PER_TOKEN
        tokens += TOKENS_JSON_OVERHEAD
        return tokens


@dataclass
class MCPServerInfo:
    """Information about an MCP server and its exposed tools.

    Represents an MCP server configured in .vscode/mcp.json that
    was queried for its tool definitions.

    Attributes:
        name: Server name from configuration (e.g., 'gitkraken', 'ai-session-tracker').
        command: Executable command to run the server.
        args: Command-line arguments for the server.
        tools: List of tools exposed by this server.
        error: Error message if server query failed, None otherwise.
    """

    name: str
    command: str
    args: list[str]
    tools: list[ToolInfo] = field(default_factory=list)
    error: str | None = None

    @property
    def total_tokens(self) -> int:
        """Total estimated tokens for all tools in this server."""
        return sum(t.estimated_tokens for t in self.tools)

    @property
    def total_desc_chars(self) -> int:
        """Total description characters across all tools."""
        return sum(t.desc_chars for t in self.tools)

    @property
    def total_params(self) -> int:
        """Total parameter count across all tools."""
        return sum(t.param_count for t in self.tools)


# Type alias for pruning candidates structure
PruningCandidates = dict[str, list[dict[str, Any]]]


@dataclass
class TokenAggregation:
    """Aggregated token counts for tools.

    Attributes:
        total: Total tokens across all tools.
        vscode: Tokens from VS Code built-in tools.
        mcp: Tokens from MCP server tools.
        all_tools: Combined list of all tools.
    """

    total: int
    vscode: int
    mcp: int
    all_tools: list[ToolInfo]

    @classmethod
    def from_tools(
        cls,
        vscode_tools: list[ToolInfo],
        servers: list[MCPServerInfo],
        active_tools: list[ToolInfo] | None = None,
    ) -> TokenAggregation:
        """Create aggregation from tool sources.

        Args:
            vscode_tools: VS Code built-in tools.
            servers: MCP servers with their tools.
            active_tools: If provided, use these for accurate counts (from replay).

        Returns:
            TokenAggregation with calculated totals.
        """
        all_mcp_tools = [t for s in servers for t in s.tools]

        if active_tools:
            # Replay mode: active_tools contains all tools from session
            return cls(
                total=sum(t.estimated_tokens for t in active_tools),
                vscode=sum(t.estimated_tokens for t in active_tools),  # All from replay
                mcp=0,  # MCP tools included in active_tools
                all_tools=list(active_tools) + all_mcp_tools,
            )
        else:
            # Estimation mode
            vscode_tokens = sum(t.estimated_tokens for t in vscode_tools)
            mcp_tokens = sum(t.estimated_tokens for t in all_mcp_tools)
            return cls(
                total=vscode_tokens + mcp_tokens,
                vscode=vscode_tokens,
                mcp=mcp_tokens,
                all_tools=vscode_tools + all_mcp_tools,
            )


@dataclass
class AnalysisContext:
    """Context for analysis operations.

    Bundles all parameters needed for print_analysis and related functions
    to reduce parameter count and improve testability.

    Attributes:
        servers: MCP servers with their tools.
        vscode_tools: VS Code built-in tools.
        instruction_files: Instruction files found in workspace.
        model: Model name for buffer calculations.
        verbose: Show detailed tool list.
        as_json: Output in JSON format.
        compare_models: Show comparison across all models.
        replay_summary: Parsed chat replay data (optional).
        active_tools: Actual tools from replay (optional).
        show_prune: Show detailed pruning recommendations.
    """

    servers: list[MCPServerInfo]
    vscode_tools: list[ToolInfo]
    instruction_files: list[InstructionFile]
    model: str = DEFAULT_MODEL
    verbose: bool = False
    as_json: bool = False
    compare_models: bool = False
    replay_summary: dict[str, Any] | None = None
    active_tools: list[ToolInfo] | None = None
    show_prune: bool = False

    @property
    def token_aggregation(self) -> TokenAggregation:
        """Calculate token aggregation for this context."""
        return TokenAggregation.from_tools(self.vscode_tools, self.servers, self.active_tools)

    @property
    def total_instruction_tokens(self) -> int:
        """Total tokens for all instruction files."""
        return sum(f.estimated_tokens for f in self.instruction_files)


def query_mcp_server(name: str, command: str, args: list[str]) -> MCPServerInfo:
    """Query an MCP server for its tool definitions via JSON-RPC.

    Sends initialize and tools/list requests to the server and parses
    the response to extract tool schemas.

    Args:
        name: Server name (for identification in results).
        command: Path to the server executable.
        args: Command-line arguments for the server.

    Returns:
        MCPServerInfo with tools populated, or error set if query failed.

    Security Note:
        This function executes commands from .vscode/mcp.json. Users should
        ensure their MCP configuration is from trusted sources, as malicious
        configs could execute arbitrary commands.
    """
    server = MCPServerInfo(name=name, command=command, args=args)

    # MCP uses JSON-RPC over stdio
    # We need to send initialize first, then tools/list
    init_request = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-analyzer", "version": "1.0.0"},
            },
            "id": 1,
        }
    )

    tools_request = json.dumps({"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2})

    try:
        # Run the MCP server and send requests
        # Security: command comes from user's mcp.json - see docstring
        proc = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Send both requests
        stdout, stderr = proc.communicate(
            input=f"{init_request}\n{tools_request}\n",
            timeout=MCP_QUERY_TIMEOUT_SECONDS,
        )

        # Parse responses (each line is a JSON-RPC response)
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            try:
                response = json.loads(line)
                if response.get("id") == 2 and "result" in response:
                    # This is the tools/list response
                    tools_data = response["result"].get("tools", [])
                    for tool in tools_data:
                        server.tools.append(
                            ToolInfo(
                                name=tool.get("name", "unknown"),
                                description=tool.get("description", ""),
                                parameters=tool.get("inputSchema", {}),
                                source=name,
                            )
                        )
            except json.JSONDecodeError:
                continue

    except subprocess.TimeoutExpired:
        server.error = "Timeout querying server"
        proc.kill()
    except FileNotFoundError:
        server.error = f"Command not found: {command}"
    except Exception as e:
        server.error = str(e)

    return server


def load_mcp_config(workspace_path: Path) -> dict[str, Any]:
    """Load MCP configuration from .vscode/mcp.json.

    Handles JSONC (JSON with comments) by stripping full-line comments.
    Note: Inline comments after values are NOT stripped to avoid breaking URLs.

    Args:
        workspace_path: Path to the workspace root.

    Returns:
        Parsed configuration dict, or empty dict if file doesn't exist.

    Raises:
        json.JSONDecodeError: If the JSON is malformed after comment stripping.
    """
    mcp_json = workspace_path / ".vscode" / "mcp.json"
    if not mcp_json.exists():
        return {}

    with open(mcp_json) as f:
        content = f.read()
        # Strip ONLY full-line comments (to avoid breaking URLs like https://)
        # Pattern: lines that start with optional whitespace then //
        content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
        return json.loads(content)


def get_vscode_builtin_tools() -> list[ToolInfo]:
    """Get estimated VS Code built-in tools.

    Converts BuiltinToolSpec entries to ToolInfo objects with placeholder
    descriptions sized to match estimated token counts.

    Returns:
        List of ToolInfo for all VS Code built-in tools.
    """
    tools = []
    for category, tool_list in VSCODE_BUILTIN_TOOLS.items():
        for spec in tool_list:
            tools.append(
                ToolInfo(
                    name=spec.name,
                    description=f"[Estimated {spec.desc_length} chars for {spec.name}]".ljust(
                        spec.desc_length, "."
                    ),
                    parameters={"properties": {p: {} for p in spec.params}},
                    source=f"vscode:{category}",
                )
            )
    return tools


def find_instruction_files(workspace_path: Path) -> list[InstructionFile]:
    """Find all instruction files in the workspace and user directories.

    Scans workspace and user config directories for Copilot instruction files
    that contribute to the instructions buffer.

    Args:
        workspace_path: Root path of the workspace to scan.

    Returns:
        List of InstructionFile objects found.

    Searched Locations:
        Workspace:
        - .github/copilot-instructions.md (instructions)
        - .github/instructions/*.md (instructions)
        - .github/chatmodes/*.md (chatmode)
        - .github/prompts/*.md (prompt)
        - .vscode/prompts/*.md (prompt)
        - src/*/agent_files/instructions/*.md (instructions)
        - src/*/agent_files/chatmodes/*.md (chatmode)

        User Config:
        - ~/.config/Code/User/prompts/*.md (user_prompt)
        - ~/.config/Code - Insiders/User/prompts/*.md (user_prompt)
    """
    files: list[InstructionFile] = []

    # Workspace instruction locations
    workspace_patterns = [
        (".github/copilot-instructions.md", "instructions"),
        (".github/instructions", "instructions"),
        (".github/chatmodes", "chatmode"),
        (".github/prompts", "prompt"),
        (".vscode/prompts", "prompt"),
        # Package-specific locations (like this project)
        ("src/*/agent_files/instructions", "instructions"),
        ("src/*/agent_files/chatmodes", "chatmode"),
    ]

    for pattern, file_type in workspace_patterns:
        if "*" in pattern:
            # Glob pattern
            for path in workspace_path.glob(pattern):
                if path.is_dir():
                    for md_file in path.glob("*.md"):
                        try:
                            content = md_file.read_text()
                            files.append(
                                InstructionFile(
                                    path=md_file.relative_to(workspace_path),
                                    content=content,
                                    file_type=file_type,
                                )
                            )
                        except Exception as e:
                            logger.debug("Failed to read %s: %s", md_file, e)
        else:
            path = workspace_path / pattern
            if path.is_file():
                try:
                    content = path.read_text()
                    files.append(
                        InstructionFile(
                            path=Path(pattern),
                            content=content,
                            file_type=file_type,
                        )
                    )
                except Exception as e:
                    logger.debug("Failed to read %s: %s", path, e)
            elif path.is_dir():
                for md_file in path.rglob("*.md"):
                    try:
                        content = md_file.read_text()
                        files.append(
                            InstructionFile(
                                path=md_file.relative_to(workspace_path),
                                content=content,
                                file_type=file_type,
                            )
                        )
                    except Exception as e:
                        logger.debug("Failed to read %s: %s", md_file, e)

    # User-level prompts (VS Code Insiders and stable)
    user_prompt_dirs = [
        Path.home() / ".config/Code/User/prompts",
        Path.home() / ".config/Code - Insiders/User/prompts",
    ]

    for prompt_dir in user_prompt_dirs:
        if prompt_dir.is_dir():
            for md_file in prompt_dir.glob("*.md"):
                try:
                    content = md_file.read_text()
                    # Mark as user-level
                    files.append(
                        InstructionFile(
                            path=Path(f"~/{md_file.relative_to(Path.home())}"),
                            content=content,
                            file_type="user_prompt",
                        )
                    )
                except Exception as e:
                    logger.debug("Failed to read user prompt %s: %s", md_file, e)

    return files


def _extract_tool_from_tool_call(entry: dict) -> ToolInfo | None:
    """Extract ToolInfo from a toolCall log entry.

    Args:
        entry: A log entry dict with kind='toolCall'.

    Returns:
        ToolInfo if tool data found, None otherwise.
    """
    tool = entry.get("tool") or {}
    if not isinstance(tool, dict):
        return None

    function = tool.get("function") or tool.get("functionDefinition") or None
    if not isinstance(function, dict):
        return None

    tname = function.get("name") or tool.get("name")
    desc = function.get("description") or ""
    params = function.get("parameters") or function.get("inputSchema") or {"properties": {}}

    return ToolInfo(
        name=tname or "unknown", description=desc, parameters=params, source="replay:toolCall"
    )


def _extract_tools_from_response(entry: dict) -> list[ToolInfo]:
    """Extract ToolInfo list from a request/response log entry.

    Args:
        entry: A log entry dict with kind='request' or 'response'.

    Returns:
        List of ToolInfo objects found in the entry.
    """
    tools_found = []
    resp = entry.get("response") or entry.get("request")

    # response can be dict, list, or string - only process dicts
    if not isinstance(resp, dict):
        return tools_found

    result = resp.get("result")
    tools_list = None
    if isinstance(result, dict):
        tools_list = result.get("tools")
    elif resp.get("tools"):
        tools_list = resp.get("tools")

    if not isinstance(tools_list, list):
        return tools_found

    for fn in tools_list:
        if not isinstance(fn, dict):
            continue
        tname = fn.get("name")
        desc = fn.get("description", "")
        params = fn.get("inputSchema", {"properties": {}})
        tools_found.append(
            ToolInfo(
                name=tname or "unknown",
                description=desc,
                parameters=params,
                source="replay:tools_list",
            )
        )

    return tools_found


def _extract_metadata_from_entry(entry: dict) -> dict[str, Any]:
    """Extract metadata fields from a log entry.

    Args:
        entry: A log entry dict.

    Returns:
        Dict with model, max_prompt_tokens, prompt_tokens, cached_tokens.
    """
    result = {
        "model": None,
        "max_prompt_tokens": None,
        "prompt_tokens": 0,
        "cached_tokens": 0,
    }

    metadata = entry.get("metadata", {})
    if not isinstance(metadata, dict):
        return result

    result["model"] = metadata.get("model")
    if "maxPromptTokens" in metadata:
        result["max_prompt_tokens"] = metadata.get("maxPromptTokens")

    usage = metadata.get("usage") or metadata.get("toolUsage") or None
    if isinstance(usage, dict):
        result["prompt_tokens"] = usage.get("prompt_tokens", 0)
        result["cached_tokens"] = usage.get("cached_tokens", 0)

    return result


def _update_active_tools_map(active_tools_map: dict[str, ToolInfo], tool_info: ToolInfo) -> None:
    """Update active tools map, keeping the longest description.

    Args:
        active_tools_map: Map of tool name to ToolInfo.
        tool_info: Tool to potentially add/update.
    """
    tname = tool_info.name
    if (
        tname
        and tname != "unknown"
        and (
            tname not in active_tools_map
            or len(tool_info.description) > len(active_tools_map[tname].description)
        )
    ):
        active_tools_map[tname] = tool_info


def parse_chat_replay(path: Path) -> dict[str, Any]:
    """Parse a Copilot chat replay JSON export and extract model+token usage and tools.

    Returns a summary dict containing per-prompt usage, per-model aggregates,
    and the ACTIVE tools set extracted from the replay.

    The active_tools list contains ToolInfo objects with full descriptions from
    the actual Copilot session, allowing accurate token estimation.

    Args:
        path: Path to the chat replay JSON file.

    Returns:
        Summary dict with total_prompts, per_prompt, models, active_tools, etc.

    Raises:
        RuntimeError: If the replay file cannot be read.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    try:
        raw = path.read_text()
    except Exception as e:
        raise RuntimeError(f"Could not read replay file: {e}") from e

    data = json.loads(raw)
    prompts = data.get("prompts", [])

    per_prompt = []
    models: dict[str, dict[str, int]] = {}
    active_tools_map: dict[str, ToolInfo] = {}

    for p in prompts:
        if not isinstance(p, dict):
            continue

        logs = p.get("logs", [])
        pm_model = None
        max_prompt_tokens = None
        prompt_tokens = 0
        cached_tokens = 0
        tools_found: list[ToolInfo] = []
        instruction_text: list[str] = []

        for entry in logs:
            if not isinstance(entry, dict):
                continue

            # Extract metadata (model, tokens)
            meta = _extract_metadata_from_entry(entry)
            pm_model = meta["model"] or pm_model
            if meta["max_prompt_tokens"] is not None:
                max_prompt_tokens = meta["max_prompt_tokens"]
            if meta["prompt_tokens"]:
                prompt_tokens = meta["prompt_tokens"]
            if meta["cached_tokens"]:
                cached_tokens = meta["cached_tokens"]

            # Extract tools based on entry kind
            kind = entry.get("kind")
            if kind == "toolCall":
                tool_info = _extract_tool_from_tool_call(entry)
                if tool_info:
                    tools_found.append(tool_info)
                    _update_active_tools_map(active_tools_map, tool_info)

            if kind in ("request", "response"):
                for tool_info in _extract_tools_from_response(entry):
                    tools_found.append(tool_info)
                    _update_active_tools_map(active_tools_map, tool_info)

            # Collect potential instruction/system content
            message = entry.get("message") or entry.get("request") or entry.get("response")
            if isinstance(message, dict):
                text = message.get("text") or message.get("content") or None
                if isinstance(text, str) and text.strip():
                    instruction_text.append(text)

        # Calculate token estimates for this prompt
        tool_tokens_est = sum(t.estimated_tokens for t in tools_found)
        instr_chars = sum(len(x) for x in instruction_text)
        instruction_tokens_est = instr_chars // CHARS_PER_TOKEN

        per_prompt.append(
            {
                "model": pm_model,
                "max_prompt_tokens": max_prompt_tokens,
                "prompt_tokens": prompt_tokens,
                "cached_tokens": cached_tokens,
                "tool_tokens_est": tool_tokens_est,
                "instruction_tokens_est": instruction_tokens_est,
                "tools_found": [t.name for t in tools_found],
            }
        )

        if pm_model:
            models.setdefault(
                pm_model,
                {"count": 0, "prompt_tokens": 0, "tool_tokens_est": 0, "instruction_tokens_est": 0},
            )
            models[pm_model]["count"] += 1
            models[pm_model]["prompt_tokens"] += prompt_tokens or 0
            models[pm_model]["tool_tokens_est"] += tool_tokens_est
            models[pm_model]["instruction_tokens_est"] += instruction_tokens_est

    # Convert active tools map to sorted list
    active_tools = sorted(active_tools_map.values(), key=lambda t: t.estimated_tokens, reverse=True)

    return {
        "total_prompts": len(per_prompt),
        "per_prompt": per_prompt,
        "models": models,
        "active_tools": active_tools,  # Full tool definitions from replay
        "active_tools_count": len(active_tools),
        "active_tools_tokens": sum(t.estimated_tokens for t in active_tools),
    }


def calculate_buffer_usage(
    total_tool_tokens: int, total_instruction_tokens: int = 0, model: str = DEFAULT_MODEL
) -> dict[str, Any]:
    """Calculate buffer usage percentages.

    Args:
        total_tool_tokens: Total estimated tokens for all tools.
        total_instruction_tokens: Total estimated tokens for instructions.
        model: Model name to get buffer limits from.

    Returns:
        Dict with tools_buffer, instructions_buffer, and total_context usage.
    """
    buffers = COPILOT_MODELS.get(model, COPILOT_MODELS[DEFAULT_MODEL])

    tools_limit = buffers["tools"]
    instructions_limit = buffers["instructions"]
    total_limit = buffers["context"]

    # Use safe_percentage to guard against division by zero
    tools_pct = safe_percentage(total_tool_tokens, tools_limit)
    instr_pct = safe_percentage(total_instruction_tokens, instructions_limit)
    total_used = total_tool_tokens + total_instruction_tokens
    total_pct = safe_percentage(total_used, total_limit)

    return {
        "model": model,
        "tools_buffer": {
            "used": total_tool_tokens,
            "limit": tools_limit,
            "percentage": tools_pct,
            "remaining": tools_limit - total_tool_tokens,
        },
        "instructions_buffer": {
            "used": total_instruction_tokens,
            "limit": instructions_limit,
            "percentage": instr_pct,
            "remaining": instructions_limit - total_instruction_tokens,
        },
        "total_context": {
            "used": total_used,
            "limit": total_limit,
            "percentage": total_pct,
        },
        "buffers_breakdown": buffers,
    }


def format_table(
    headers: list[str], rows: list[list[Any]], alignments: list[str] | None = None
) -> str:
    """Format data as an ASCII table with box-drawing characters.

    Args:
        headers: Column header strings.
        rows: List of row data (each row is a list of cell values).
        alignments: Format alignment per column ('<' left, '>' right).
                   Defaults to left-aligned for all columns.

    Returns:
        Multi-line string with ASCII table formatting.

    Example:
        >>> format_table(['Name', 'Value'], [['foo', 123], ['bar', 456]])
        +------+-------+
        | Name | Value |
        +------+-------+
        | foo  | 123   |
        | bar  | 456   |
        +------+-------+
    """
    if not alignments:
        alignments = ["<"] * len(headers)

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    # Build format string
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    lines = [sep]

    # Header
    header_cells = []
    for i, (h, w) in enumerate(zip(headers, widths, strict=False)):
        header_cells.append(f" {h:{alignments[i]}{w}} ")
    lines.append("|" + "|".join(header_cells) + "|")
    lines.append(sep)

    # Rows
    for row in rows:
        row_cells = []
        for i, (cell, w) in enumerate(zip(row, widths, strict=False)):
            row_cells.append(f" {str(cell):{alignments[i]}{w}} ")
        lines.append("|" + "|".join(row_cells) + "|")

    lines.append(sep)
    return "\n".join(lines)


# =============================================================================
# PRINT ANALYSIS HELPERS
# =============================================================================


def _print_instructions_section(
    instruction_files: list[InstructionFile], total_instruction_tokens: int
) -> None:
    """Print the instructions buffer section.

    Args:
        instruction_files: List of instruction files found.
        total_instruction_tokens: Total tokens across all instruction files.
    """
    print()
    print("INSTRUCTIONS BUFFER")
    print("-" * 70)

    if not instruction_files:
        print("  No instruction files found.")
        return

    rows = []

    # Group by type
    by_type: dict[str, list[InstructionFile]] = {}
    for f in instruction_files:
        by_type.setdefault(f.file_type, []).append(f)

    for file_type, files in sorted(by_type.items()):
        type_tokens = sum(f.estimated_tokens for f in files)
        rows.append(
            [
                f"[{file_type}]",
                len(files),
                type_tokens,
                f"{safe_percentage(type_tokens, total_instruction_tokens):.1f}%",
            ]
        )
        for f in files:
            rows.append([f"  {str(f.path)[:45]}", f.line_count, f.estimated_tokens, ""])

    rows.append(
        ["── Instructions Total", len(instruction_files), total_instruction_tokens, "100.0%"]
    )

    print(
        format_table(
            ["File / Category", "Lines", "Est. Tokens", "% of Instr"], rows, ["<", ">", ">", ">"]
        )
    )


def _print_tools_section(
    vscode_tools: list[ToolInfo],
    servers: list[MCPServerInfo],
    total_tool_tokens: int,
    total_vscode_tokens: int,
    total_mcp_tokens: int,
) -> None:
    """Print the tools buffer section.

    Args:
        vscode_tools: VS Code built-in tools.
        servers: MCP servers with their tools.
        total_tool_tokens: Total tokens for all tools.
        total_vscode_tokens: Tokens for VS Code tools only.
        total_mcp_tokens: Tokens for MCP tools only.
    """
    print()
    print("TOOLS BUFFER")
    print("-" * 70)

    rows = []
    all_mcp_tools = [t for s in servers for t in s.tools]

    # VS Code categories
    vscode_by_cat: dict[str, list[ToolInfo]] = {}
    for t in vscode_tools:
        cat = t.source.split(":")[1] if ":" in t.source else "other"
        vscode_by_cat.setdefault(cat, []).append(t)

    for cat, tools in sorted(vscode_by_cat.items()):
        tokens = sum(t.estimated_tokens for t in tools)
        rows.append(
            [
                f"vscode:{cat}",
                len(tools),
                tokens,
                f"{safe_percentage(tokens, total_tool_tokens):.1f}%",
            ]
        )

    # VS Code subtotal
    rows.append(
        [
            "── VS Code Subtotal",
            len(vscode_tools),
            total_vscode_tokens,
            f"{safe_percentage(total_vscode_tokens, total_tool_tokens):.1f}%",
        ]
    )

    # MCP servers
    for server in servers:
        status = f"({server.error})" if server.error else ""
        rows.append(
            [
                f"mcp:{server.name} {status}",
                len(server.tools),
                server.total_tokens,
                f"{safe_percentage(server.total_tokens, total_tool_tokens):.1f}%",
            ]
        )

    # MCP subtotal
    rows.append(
        [
            "── MCP Subtotal",
            len(all_mcp_tools),
            total_mcp_tokens,
            f"{safe_percentage(total_mcp_tokens, total_tool_tokens):.1f}%",
        ]
    )

    # Grand total
    rows.append(["TOTAL", len(vscode_tools) + len(all_mcp_tools), total_tool_tokens, "100.0%"])

    print(
        format_table(["Source", "Tools", "Est. Tokens", "% of Tools"], rows, ["<", ">", ">", ">"])
    )
    print()


def _print_buffer_usage_box(buffer_usage: dict[str, Any], model: str) -> None:
    """Print the buffer usage summary box.

    Args:
        buffer_usage: Buffer usage dict from calculate_buffer_usage().
        model: Model name for display.
    """
    print("BUFFER USAGE SUMMARY")
    print("-" * 70)

    bu = buffer_usage
    buffers = COPILOT_MODELS.get(model, COPILOT_MODELS[DEFAULT_MODEL])
    instr_bar = make_progress_bar(bu["instructions_buffer"]["percentage"])
    tools_bar = make_progress_bar(bu["tools_buffer"]["percentage"])

    # Calculate dynamic field widths based on BOX_WIDTH
    inner_width = BOX_WIDTH - 2  # Subtract box borders
    model_field_width = inner_width - len(" MODEL: ")

    # Build buffer display lines
    instr_used = bu["instructions_buffer"]["used"]
    instr_limit = bu["instructions_buffer"]["limit"]
    instr_remaining = bu["instructions_buffer"]["remaining"]
    tools_used = bu["tools_buffer"]["used"]
    tools_limit = bu["tools_buffer"]["limit"]
    tools_remaining = bu["tools_buffer"]["remaining"]
    total_used = bu["total_context"]["used"]
    total_limit = bu["total_context"]["limit"]
    total_pct = bu["total_context"]["percentage"]

    instr_line = f"{instr_used:>6,} / {instr_limit:>6,} tokens ({instr_remaining:,} remaining)"
    tools_line = f"{tools_used:>6,} / {tools_limit:>6,} tokens ({tools_remaining:,} remaining)"
    total_line = (
        f"TOTAL OVERHEAD: {total_used:>6,} / {total_limit:>6,} tokens │ "
        f"{total_pct:>5.1f}% of context"
    )

    print(f"""
┌{'─' * inner_width}┐
│ MODEL: {model:<{model_field_width - 1}} │
├{'─' * inner_width}┤
│ INSTRUCTIONS BUFFER{' ' * (inner_width - 20)}│
│ {instr_bar} {bu['instructions_buffer']['percentage']:>5.1f}%{' ' * (inner_width - BAR_WIDTH - 9)}│
│ {instr_line}{' ' * (inner_width - len(instr_line) - 1)}│
├{'─' * inner_width}┤
│ TOOLS BUFFER{' ' * (inner_width - 13)}│
│ {tools_bar} {bu['tools_buffer']['percentage']:>5.1f}%{' ' * (inner_width - BAR_WIDTH - 9)}│
│ {tools_line}{' ' * (inner_width - len(tools_line) - 1)}│
├{'─' * inner_width}┤
│ {total_line}{' ' * (inner_width - len(total_line) - 1)}│
└{'─' * inner_width}┘

Buffer Allocations for {model}:
  Instructions: {buffers['instructions']:>6,} tokens (system prompts, .instructions.md, chat modes)
  Tools:        {buffers['tools']:>6,} tokens (MCP + built-in tool schemas)
  Context:      {buffers['context']:>6,} tokens (total model context)
""")


def _print_replay_summary(replay_summary: dict[str, Any]) -> None:
    """Print the replay summary section.

    Args:
        replay_summary: Parsed chat replay data.
    """
    print("REPLAY SUMMARY")
    print("-" * 70)

    rows = []
    for mname, mstats in sorted(replay_summary.get("models", {}).items(), key=lambda x: x[0]):
        count = mstats.get("count", 0)
        prompt_total = mstats.get("prompt_tokens", 0)
        tool_total = mstats.get("tool_tokens_est", 0)
        instr_total = mstats.get("instruction_tokens_est", 0)
        avg_prompt = prompt_total / count if count else 0
        avg_tools = tool_total / count if count else 0
        avg_instr = instr_total / count if count else 0

        # Percentages relative to model buffers
        buffers_for_model = COPILOT_MODELS.get(mname, COPILOT_MODELS[DEFAULT_MODEL])
        tools_pct = safe_percentage(avg_tools, buffers_for_model.get("tools", 1))
        instr_pct = safe_percentage(avg_instr, buffers_for_model.get("instructions", 1))
        total_pct = safe_percentage(avg_tools + avg_instr, buffers_for_model.get("context", 1))

        rows.append(
            [
                mname,
                count,
                f"{int(avg_prompt):,}",
                f"{int(avg_tools):,}",
                f"{tools_pct:.1f}%",
                f"{int(avg_instr):,}",
                f"{instr_pct:.1f}%",
                f"{total_pct:.1f}%",
            ]
        )

    if rows:
        print(
            format_table(
                [
                    "Model",
                    "Prompts",
                    "Avg Prompt",
                    "Avg Tools",
                    "Tools %",
                    "Avg Instr",
                    "Instr %",
                    "Total %",
                ],
                rows,
                ["<", ">", ">", ">", ">", ">", ">", ">"],
            )
        )
        print()


def _print_model_comparison(total_tool_tokens: int, total_instruction_tokens: int) -> None:
    """Print the model comparison table.

    Args:
        total_tool_tokens: Total tool tokens.
        total_instruction_tokens: Total instruction tokens.
    """
    print("MODEL COMPARISON")
    print("-" * 70)
    total_overhead = total_tool_tokens + total_instruction_tokens
    print(
        f"Your overhead is FIXED at {total_overhead:,} tokens. " "Here's how it impacts each model:"
    )
    print()

    rows = []
    for m, b in sorted(COPILOT_MODELS.items(), key=lambda x: x[1]["context"]):
        instr_pct = safe_percentage(total_instruction_tokens, b["instructions"])
        tools_pct = safe_percentage(total_tool_tokens, b["tools"])
        total_pct = safe_percentage(total_tool_tokens + total_instruction_tokens, b["context"])
        rows.append(
            [
                m,
                f"{b['context']:,}",
                f"{instr_pct:.1f}%",
                f"{tools_pct:.1f}%",
                f"{total_pct:.1f}%",
            ]
        )

    print(
        format_table(
            ["Model", "Context", "Instr %", "Tools %", "Total %"], rows, ["<", ">", ">", ">", ">"]
        )
    )
    print()
    print("Note: Instructions buffer is FIXED at 8K across all models.")
    print("      Tool buffer limits vary by model.")
    print()


def _print_pruning_candidates(candidates: dict[str, list[dict]], show_prune: bool) -> None:
    """Print the pruning candidates section.

    Args:
        candidates: Pruning candidates from identify_pruning_candidates().
        show_prune: Whether to show detailed pruning actions.
    """
    print("PRUNING CANDIDATES")
    print("-" * 70)

    # Show actionable summary first
    if candidates.get("actionable"):
        for c in candidates["actionable"]:
            print(f"\n{c['name']}")
            print(f"   {c['reason']}")
            print(f"   → {c['action']}")

    if candidates["high_impact"]:
        print("\n🔴 High Impact (large token savings):")
        for c in candidates["high_impact"][:10]:  # Top 10
            print(f"   • {c['name']}: ~{c['tokens']:,} tokens")
            if show_prune and c.get("action"):
                print(f"     → {c['action']}")

    if candidates["medium_impact"]:
        print("\n🟡 Medium Impact (disable if not needed):")
        for c in candidates["medium_impact"]:
            print(f"   • {c['name']}: ~{c['tokens']:,} tokens - {c['reason']}")
            if show_prune and c.get("action"):
                print(f"     → {c['action']}")

    if candidates["low_usage"]:
        print("\n🟢 MCP Servers (review if actively used):")
        for c in candidates["low_usage"]:
            print(f"   • {c['name']}: ~{c['tokens']:,} tokens")
            if show_prune and c.get("action"):
                print(f"     → {c['action']}")

    print()


def _print_verbose_tools(
    vscode_tools: list[ToolInfo], all_mcp_tools: list[ToolInfo], active_tools: list[ToolInfo] | None
) -> None:
    """Print detailed tool list (verbose mode).

    Args:
        vscode_tools: VS Code built-in tools.
        all_mcp_tools: All MCP server tools.
        active_tools: Active tools from replay (if available).
    """
    print("DETAILED TOOL LIST")
    print("-" * 70)

    all_tools = list((active_tools if active_tools else vscode_tools) + all_mcp_tools)
    all_tools.sort(key=lambda t: t.estimated_tokens, reverse=True)

    rows = []
    for t in all_tools[:30]:  # Top 30
        rows.append([t.name[:40], t.source[:20], t.param_count, t.estimated_tokens])

    print(format_table(["Tool Name", "Source", "Params", "Tokens"], rows, ["<", "<", ">", ">"]))
    if len(all_tools) > 30:
        print(f"  ... and {len(all_tools) - 30} more tools")

    print()


def print_analysis_from_context(ctx: AnalysisContext) -> None:
    """Print analysis results from an AnalysisContext.

    Convenience wrapper that unpacks context and delegates to print_analysis().

    Args:
        ctx: Analysis context containing all parameters.
    """
    print_analysis(
        servers=ctx.servers,
        vscode_tools=ctx.vscode_tools,
        instruction_files=ctx.instruction_files,
        verbose=ctx.verbose,
        as_json=ctx.as_json,
        model=ctx.model,
        compare_models=ctx.compare_models,
        replay_summary=ctx.replay_summary,
        active_tools=ctx.active_tools,
        show_prune=ctx.show_prune,
    )


def print_analysis(
    servers: list[MCPServerInfo],
    vscode_tools: list[ToolInfo],
    instruction_files: list[InstructionFile],
    verbose: bool = False,
    as_json: bool = False,
    model: str = DEFAULT_MODEL,
    compare_models: bool = False,
    replay_summary: dict | None = None,
    active_tools: list[ToolInfo] | None = None,
    show_prune: bool = False,
) -> None:
    """Print the analysis results.

    Args:
        servers: MCP servers with their tools
        vscode_tools: VS Code built-in tools (or active tools from replay)
        instruction_files: Instruction files found
        verbose: Show individual tool details
        as_json: Output as JSON
        model: Model to calculate buffer usage for
        compare_models: Show comparison across all models
        replay_summary: Parsed chat replay data
        active_tools: Actual tools from a Copilot replay (overrides estimates)
        show_prune: Show detailed pruning recommendations

    See Also:
        print_analysis_from_context: Wrapper accepting AnalysisContext.
    """
    # Use TokenAggregation factory for consistent aggregation logic
    tokens = TokenAggregation.from_tools(vscode_tools, servers, active_tools)
    all_mcp_tools = [t for s in servers for t in s.tools]

    total_tool_tokens = tokens.total
    total_vscode_tokens = tokens.vscode
    total_mcp_tokens = tokens.mcp
    total_instruction_tokens = sum(f.estimated_tokens for f in instruction_files)
    buffer_usage = calculate_buffer_usage(total_tool_tokens, total_instruction_tokens, model)

    # JSON output mode
    if as_json:
        output = {
            "summary": {
                "total_tools": len(vscode_tools) + len(all_mcp_tools),
                "total_tool_tokens": total_tool_tokens,
                "vscode_tools": len(vscode_tools),
                "vscode_tokens": total_vscode_tokens,
                "mcp_tools": len(all_mcp_tools),
                "mcp_tokens": total_mcp_tokens,
                "instruction_files": len(instruction_files),
                "instruction_tokens": total_instruction_tokens,
            },
            "buffer_usage": buffer_usage,
            "mcp_servers": [
                {
                    "name": s.name,
                    "tools": len(s.tools),
                    "tokens": s.total_tokens,
                    "error": s.error,
                    "tool_details": [
                        {"name": t.name, "tokens": t.estimated_tokens, "params": t.param_count}
                        for t in s.tools
                    ]
                    if verbose
                    else None,
                }
                for s in servers
            ],
            "instruction_files": [
                {
                    "path": str(f.path),
                    "type": f.file_type,
                    "chars": f.char_count,
                    "lines": f.line_count,
                    "tokens": f.estimated_tokens,
                }
                for f in instruction_files
            ],
            "pruning_candidates": identify_pruning_candidates(servers, vscode_tools),
        }
        if replay_summary is not None:
            output["replay_summary"] = replay_summary
        print(json.dumps(output, indent=2))
        return

    # ASCII output
    print("=" * 70)
    print("COPILOT CONTEXT OVERHEAD ANALYSIS")
    print("=" * 70)

    # Delegate to helper functions for each section
    _print_instructions_section(instruction_files, total_instruction_tokens)
    _print_tools_section(
        vscode_tools, servers, total_tool_tokens, total_vscode_tokens, total_mcp_tokens
    )
    _print_buffer_usage_box(buffer_usage, model)

    if replay_summary is not None:
        _print_replay_summary(replay_summary)

    if compare_models:
        _print_model_comparison(total_tool_tokens, total_instruction_tokens)

    candidates = identify_pruning_candidates(servers, vscode_tools, active_tools=active_tools)
    _print_pruning_candidates(candidates, show_prune)

    if verbose:
        _print_verbose_tools(vscode_tools, all_mcp_tools, active_tools)


def identify_pruning_candidates(
    servers: list[MCPServerInfo],
    vscode_tools: list[ToolInfo],
    active_tools: list[ToolInfo] | None = None,
) -> PruningCandidates:
    """Identify tools that could be pruned to save context.

    Uses PRUNABLE_CATEGORIES constant for pattern matching instead of hardcoded strings.
    If active_tools is provided (from a chat replay), uses those for accurate
    token counts and can identify tools that are never used.

    Args:
        servers: MCP servers with their tools.
        vscode_tools: VS Code built-in tools.
        active_tools: Actual tools from a replay session (optional).

    Returns:
        PruningCandidates dict with high_impact, medium_impact, low_usage, actionable lists.
    """
    candidates: PruningCandidates = {
        "high_impact": [],
        "medium_impact": [],
        "low_usage": [],
        "actionable": [],
    }

    # Use TokenAggregation for consistent calculation
    aggregation = TokenAggregation.from_tools(vscode_tools, servers, active_tools)
    all_tools = aggregation.all_tools

    # High impact: Large tool schemas (> LARGE_TOOL_THRESHOLD_TOKENS)
    large_tools = [t for t in all_tools if t.estimated_tokens > LARGE_TOOL_THRESHOLD_TOKENS]
    for tool in sorted(large_tools, key=lambda t: t.estimated_tokens, reverse=True):
        action = _get_pruning_action(tool.name, tool.estimated_tokens)
        candidates["high_impact"].append(
            {
                "name": tool.name,
                "tokens": tool.estimated_tokens,
                "source": tool.source,
                "reason": "Large schema - consider shorter description",
                "action": action,
            }
        )

    # Medium impact: Use PRUNABLE_CATEGORIES constant for pattern matching
    for category_name, category_config in PRUNABLE_CATEGORIES.items():
        patterns = category_config["patterns"]
        extra_pattern = category_config.get("extra_pattern")

        # Find tools matching this category's patterns
        matched_tools = []
        for tool in all_tools:
            tool_name_lower = tool.name.lower()
            matches_primary = any(p in tool_name_lower for p in patterns)
            matches_extra = extra_pattern is None or extra_pattern in tool_name_lower
            if matches_primary and matches_extra:
                matched_tools.append(tool)

        if matched_tools:
            total = sum(t.estimated_tokens for t in matched_tools)
            cat_title = category_name.replace("_", " ").title()
            candidates["medium_impact"].append(
                {
                    "name": f"{cat_title} tools ({len(matched_tools)} tools)",
                    "tokens": total,
                    "source": category_config["source"],
                    "reason": category_config["reason"],
                    "action": category_config["action"],
                }
            )

    # Low usage: MCP server tools
    for server in servers:
        if server.tools:
            candidates["low_usage"].append(
                {
                    "name": f"MCP: {server.name}",
                    "tokens": server.total_tokens,
                    "source": "mcp",
                    "reason": "Review if actively used",
                    "action": "Disable in .vscode/mcp.json if not needed",
                }
            )

    # Build actionable summary for primary models (Claude Opus 4.5 / Sonnet 4)
    total_tokens = aggregation.total
    primary_config = get_model_config("claude-opus-4.5")
    usage_pct = safe_percentage(total_tokens, primary_config.tools)

    if usage_pct > OVERHEAD_WARNING_THRESHOLD_PCT:
        candidates["actionable"].append(
            {
                "name": "⚠️ HIGH OVERHEAD WARNING",
                "tokens": total_tokens,
                "reason": f"Tools buffer at {usage_pct:.1f}% for Claude models",
                "action": "IMMEDIATELY prune high-impact tools or disable MCP servers",
            }
        )
    elif usage_pct > OVERHEAD_MODERATE_THRESHOLD_PCT:
        candidates["actionable"].append(
            {
                "name": "📊 Moderate overhead",
                "tokens": total_tokens,
                "reason": f"Tools buffer at {usage_pct:.1f}% for Claude models",
                "action": "Consider pruning notebook/python tools if not needed",
            }
        )
    else:
        candidates["actionable"].append(
            {
                "name": "✅ Healthy overhead",
                "tokens": total_tokens,
                "reason": f"Tools buffer at {usage_pct:.1f}% for Claude models",
                "action": "No immediate action needed",
            }
        )

    # Sort by token impact
    for key in ["high_impact", "medium_impact", "low_usage"]:
        candidates[key].sort(key=lambda x: x["tokens"], reverse=True)

    return candidates


def _get_pruning_action(tool_name: str, tokens: int) -> str:
    """Get specific pruning action for a tool."""
    # Map tool names to specific actions
    actions = {
        "run_in_terminal": "Consider using run_task instead for common operations",
        "get_vscode_api": "Disable if not developing VS Code extensions",
        "create_new_workspace": "Rarely used - consider removing from prompts",
        "manage_todo_list": "Disable if not using todo tracking feature",
        "replace_string_in_file": "Core tool - keep, but note large schema",
        "multi_replace_string_in_file": "Core tool - keep, but note large schema",
        "grep_search": "Core tool - keep, but note large schema",
        "semantic_search": "Core tool - keep for codebase search",
    }
    return actions.get(tool_name, f"Review if needed (~{tokens} tokens)")


# =============================================================================
# ANALYSIS ORCHESTRATION
# =============================================================================


def run_analysis(
    workspace: Path,
    model: str = DEFAULT_MODEL,
    verbose: bool = False,
    as_json: bool = False,
    compare_models: bool = False,
    replay_path: Path | None = None,
    show_prune: bool = False,
    primary_only: bool = False,
) -> list[AnalysisContext]:
    """Run MCP overhead analysis and return context(s) for output.

    This function handles all I/O operations (MCP queries, file scanning)
    and returns AnalysisContext objects that can be passed to print_analysis.
    Separating this from main() improves testability.

    Args:
        workspace: Workspace path to analyze.
        model: Model name for buffer calculations.
        verbose: Include detailed tool information.
        as_json: Prepare for JSON output.
        compare_models: Include model comparison data.
        replay_path: Path to chat replay file (optional).
        show_prune: Include detailed pruning recommendations.
        primary_only: Analyze primary models only.

    Returns:
        List of AnalysisContext objects (one per model if primary_only).
    """
    # Load MCP config
    config = load_mcp_config(workspace)
    servers_config = config.get("servers", {})

    # Show trust warning before executing any commands
    if servers_config and not as_json:
        print(SUBPROCESS_TRUST_WARNING, file=sys.stderr)

    # Query each MCP server
    servers = []
    for name, cfg in servers_config.items():
        command = cfg.get("command", "")
        cmd_args = cfg.get("args", [])

        if not as_json:
            print(f"Querying MCP server: {name}...", file=sys.stderr)

        server = query_mcp_server(name, command, cmd_args)
        servers.append(server)

    # Parse replay file if provided
    replay_summary = None
    if replay_path:
        try:
            if not as_json:
                print(f"Parsing replay file: {replay_path}", file=sys.stderr)
            replay_summary = parse_chat_replay(replay_path)
            if not as_json:
                print(
                    f"Loaded {replay_summary.get('total_prompts', 0)} prompts from replay",
                    file=sys.stderr,
                )
        except Exception as e:
            logger.warning("Failed to parse replay file %s: %s", replay_path, e)
            replay_summary = None

    # Get VS Code built-in tools
    vscode_tools = get_vscode_builtin_tools()
    if not as_json:
        mcp_tool_count = sum(len(s.tools) for s in servers)
        print(
            f"Tools: {len(vscode_tools)} VS Code built-in + {mcp_tool_count} MCP server",
            file=sys.stderr,
        )

    # Find instruction files
    if not as_json:
        print("Scanning for instruction files...", file=sys.stderr)
    instruction_files = find_instruction_files(workspace)

    # Build context(s) for analysis
    contexts = []
    models_to_analyze = PRIMARY_MODELS if primary_only else [model]

    for m in models_to_analyze:
        ctx = AnalysisContext(
            servers=servers,
            vscode_tools=vscode_tools,
            instruction_files=instruction_files,
            model=m,
            verbose=verbose,
            as_json=as_json,
            compare_models=compare_models if not primary_only else False,
            replay_summary=replay_summary,
            active_tools=None,
            show_prune=show_prune,
        )
        contexts.append(ctx)

    return contexts


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Analyze MCP tool overhead and context window usage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show individual tools")
    parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=Path.cwd(),
        help="Workspace path (default: current directory)",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=DEFAULT_MODEL,
        choices=get_all_model_names(),
        help=f"Model to calculate buffer usage for (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--compare", "-c", action="store_true", help="Show comparison across all models"
    )
    parser.add_argument(
        "--replay",
        "-r",
        type=Path,
        help="Path to Copilot chat replay JSON export (adds token usage stats)",
    )
    parser.add_argument(
        "--prune", "-p", action="store_true", help="Show detailed pruning recommendations"
    )
    parser.add_argument(
        "--primary",
        action="store_true",
        help="Focus analysis on primary models (Claude Opus 4.5, Sonnet 4)",
    )
    args = parser.parse_args()

    # Run analysis (handles I/O, returns contexts)
    contexts = run_analysis(
        workspace=args.workspace,
        model=args.model,
        verbose=args.verbose,
        as_json=args.json,
        compare_models=args.compare,
        replay_path=args.replay,
        show_prune=args.prune,
        primary_only=args.primary,
    )

    # Print header for primary models analysis
    if args.primary and not args.json:
        print("\n" + "=" * 70, file=sys.stderr)
        print("PRIMARY MODELS ANALYSIS (Claude Opus 4.5 + Sonnet 4)", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

    # Output analysis for each context
    for ctx in contexts:
        print_analysis_from_context(ctx)

    return 0


if __name__ == "__main__":
    sys.exit(main())
