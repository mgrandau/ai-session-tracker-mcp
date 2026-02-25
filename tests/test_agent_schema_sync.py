"""Tests that agent files and instructions stay in sync with MCP tool schemas.

These tests catch drift between the MCP tool definitions (server.py) and the
instructions/agent files that tell AI agents how to call them. When we add a
required param to the schema, these tests fail if the instructions don't
mention it — preventing the exact class of bug we hit pre-v1.1.2.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ai_session_tracker_mcp.server import SessionTrackerServer


@pytest.fixture
def server() -> SessionTrackerServer:
    """Create a server instance to access tool definitions."""
    return SessionTrackerServer()


@pytest.fixture
def instructions_text() -> str:
    """Load session_tracking.instructions.md content."""
    instructions_path = (
        Path(__file__).parent.parent
        / "src"
        / "ai_session_tracker_mcp"
        / "agent_files"
        / "instructions"
        / "session_tracking.instructions.md"
    )
    return instructions_path.read_text()


@pytest.fixture
def agent_text() -> str:
    """Load Session Tracked Agent.agent.md content."""
    agent_path = (
        Path(__file__).parent.parent
        / "src"
        / "ai_session_tracker_mcp"
        / "agent_files"
        / "agents"
        / "Session Tracked Agent.agent.md"
    )
    return agent_path.read_text()


@pytest.fixture
def repo_agent_text() -> str:
    """Load .github/agents/Session Tracked Agent.agent.md content."""
    agent_path = (
        Path(__file__).parent.parent / ".github" / "agents" / "Session Tracked Agent.agent.md"
    )
    return agent_path.read_text()


class TestInstructionsSchemaSync:
    """Verify instructions reference all required params from MCP schema."""

    def test_start_session_required_params_in_instructions(
        self, server: SessionTrackerServer, instructions_text: str
    ) -> None:
        """Every required param in start_ai_session schema appears in instructions.

        Business context:
        If the instructions omit a required param, AI agents will skip it,
        resulting in incomplete session metadata. This was the root cause
        of the v1.1.2 fix — developer and project were required in the
        schema but not called out in the instructions.

        Assertion Strategy:
        Each required param name must appear in the instructions text.
        """
        schema = server.tools["start_ai_session"]["inputSchema"]
        for param in schema["required"]:
            assert param in instructions_text, (
                f"Required param '{param}' from start_ai_session schema "
                f"not found in session_tracking.instructions.md"
            )

    def test_end_session_required_params_in_instructions(
        self, server: SessionTrackerServer, instructions_text: str
    ) -> None:
        """Every required param in end_ai_session schema appears in instructions.

        Business context:
        final_estimate_minutes is the core ROI metric. If instructions
        don't mention it as required, agents will skip it and ROI
        calculations break.
        """
        schema = server.tools["end_ai_session"]["inputSchema"]
        for param in schema["required"]:
            assert param in instructions_text, (
                f"Required param '{param}' from end_ai_session schema "
                f"not found in session_tracking.instructions.md"
            )

    def test_start_session_required_params_in_agent(
        self, server: SessionTrackerServer, agent_text: str
    ) -> None:
        """Every required param in start_ai_session schema appears in agent file.

        The agent file is the primary entry point for AI agents. It must
        reference all required params to ensure they're passed.
        """
        schema = server.tools["start_ai_session"]["inputSchema"]
        for param in schema["required"]:
            assert param in agent_text, (
                f"Required param '{param}' from start_ai_session schema "
                f"not found in Session Tracked Agent.agent.md"
            )

    def test_end_session_required_params_in_agent(
        self, server: SessionTrackerServer, agent_text: str
    ) -> None:
        """Every required param in end_ai_session schema appears in agent file."""
        schema = server.tools["end_ai_session"]["inputSchema"]
        for param in schema["required"]:
            assert param in agent_text, (
                f"Required param '{param}' from end_ai_session schema "
                f"not found in Session Tracked Agent.agent.md"
            )

    def test_task_type_enums_in_instructions(
        self, server: SessionTrackerServer, instructions_text: str
    ) -> None:
        """All valid task_type values appear in instructions.

        If we add a new task type to the schema but forget to list it
        in the instructions, agents won't know it exists.
        """
        schema = server.tools["start_ai_session"]["inputSchema"]
        task_types = schema["properties"]["task_type"]["enum"]
        for task_type in task_types:
            assert task_type in instructions_text, (
                f"Task type '{task_type}' from schema enum "
                f"not found in session_tracking.instructions.md"
            )

    def test_outcome_enums_in_instructions(
        self, server: SessionTrackerServer, instructions_text: str
    ) -> None:
        """All valid outcome values appear in instructions."""
        schema = server.tools["end_ai_session"]["inputSchema"]
        outcomes = schema["properties"]["outcome"]["enum"]
        for outcome in outcomes:
            assert outcome in instructions_text, (
                f"Outcome '{outcome}' from schema enum "
                f"not found in session_tracking.instructions.md"
            )

    def test_estimate_source_enums_in_instructions(
        self, server: SessionTrackerServer, instructions_text: str
    ) -> None:
        """All valid estimate_source values appear in instructions."""
        schema = server.tools["start_ai_session"]["inputSchema"]
        sources = schema["properties"]["estimate_source"]["enum"]
        for source in sources:
            assert source in instructions_text, (
                f"Estimate source '{source}' from schema enum "
                f"not found in session_tracking.instructions.md"
            )


class TestAgentFilesInSync:
    """Verify bundled and repo-local agent files are identical."""

    def test_agent_files_match(self, agent_text: str, repo_agent_text: str) -> None:
        """Bundled agent file must match .github/agents/ copy.

        Business context:
        Two copies exist — src/agent_files/agents/ (ships with package)
        and .github/agents/ (repo-local for development). If they diverge,
        one environment gets stale instructions.
        """
        assert agent_text == repo_agent_text, (
            "Bundled agent file (src/agent_files/agents/) and repo agent file "
            "(.github/agents/) have diverged. Run:\n"
            "  cp 'src/.../Session Tracked Agent.agent.md' '.github/agents/'"
        )


class TestInstructionsStructure:
    """Validate structural requirements of instruction files."""

    def test_instructions_has_frontmatter(self, instructions_text: str) -> None:
        """Instructions file must have YAML frontmatter with applyTo."""
        assert instructions_text.startswith("---"), (
            "session_tracking.instructions.md must start with YAML frontmatter (---)"
        )
        assert "applyTo:" in instructions_text, "Frontmatter must contain applyTo directive"

    def test_instructions_mentions_all_tools(self, instructions_text: str) -> None:
        """Instructions must reference all four MCP tools."""
        tools = [
            "start_ai_session",
            "log_ai_interaction",
            "end_ai_session",
            "flag_ai_issue",
        ]
        for tool in tools:
            assert tool in instructions_text, (
                f"Tool '{tool}' not mentioned in session_tracking.instructions.md"
            )

    def test_instructions_has_required_labels(self, instructions_text: str) -> None:
        """Instructions must use REQUIRED labels for enforced params.

        This catches the exact scenario from pre-v1.1.2: params were in
        the schema as required but the instructions didn't call them out,
        so agents treated them as optional.
        """
        # developer and project should be labeled REQUIRED
        assert re.search(r"developer.*REQUIRED|REQUIRED.*developer", instructions_text), (
            "developer param must be labeled REQUIRED in instructions"
        )
        assert re.search(r"project.*REQUIRED|REQUIRED.*project", instructions_text), (
            "project param must be labeled REQUIRED in instructions"
        )
        assert re.search(
            r"final_estimate_minutes.*REQUIRED|REQUIRED.*final_estimate_minutes",
            instructions_text,
        ), "final_estimate_minutes param must be labeled REQUIRED in instructions"
