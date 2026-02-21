# ai-session-tracker-mcp

[![GitHub release](https://img.shields.io/github/v/release/mgrandau/ai-session-tracker-mcp)](https://github.com/mgrandau/ai-session-tracker-mcp/releases) [![CI](https://github.com/mgrandau/ai-session-tracker-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/mgrandau/ai-session-tracker-mcp/actions/workflows/ci.yml) [![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/) [![Type: mypy](https://img.shields.io/badge/type-mypy-blue.svg)](https://mypy-lang.org/) [![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**MCP server for tracking AI coding sessions and measuring developer productivity.**

Track your AI-assisted coding sessions, measure effectiveness, calculate ROI, and identify workflow friction points — all through the Model Context Protocol.

> 📖 **Read the blog post:** [I Stopped Arguing About AI Productivity and Started Measuring It](https://mgrandau.medium.com/i-stopped-arguing-about-ai-productivity-and-started-measuring-it-7b1b030d7d79?source=friends_link&sk=805085ba145a4a501a75510aa6818751)
>
---

## ✨ Features

- 📊 **Session Tracking** — Start, log interactions, and end coding sessions with full context
- 📈 **ROI Metrics** — Calculate time saved, cost savings, and productivity multipliers
- 🎯 **Effectiveness Ratings** — Rate AI responses 1-5 to track quality over time
- 🔍 **Code Metrics** — Analyze complexity and documentation quality of modified code
- 🌐 **Web Dashboard** — Real-time charts and analytics via FastAPI + htmx
- 🤖 **Agent Files** — Pre-configured chat modes and instruction files for VS Code

---

## 📦 Installation

### From Git Repository

```bash
# Install directly from GitHub
pip install git+https://github.com/mgrandau/ai-session-tracker-mcp.git

# Or with pipx for isolated installation
pipx install git+https://github.com/mgrandau/ai-session-tracker-mcp.git
```

### Configure for VS Code

After installing, run the install command in your project directory:

```bash
# Navigate to your project
cd /path/to/your/project

# Install MCP configuration and agent files
ai-session-tracker install
```

This creates:

- `.vscode/mcp.json` — MCP server configuration
- `.github/instructions/` — AI instruction files
- `.github/agents/` — VS Code custom agent definitions

### Full MCP Configuration Template

For manual configuration or to enable all features, use this templatelick the **options menu** (next to the up arrow/return button)
2. E in `.vscode/mcp.json`:

```json
{
  "servers": {
    "ai-session-tracker": {
      "command": "ai-session-tracker",
      "args": [
        "server",
        "--dashboard-host", "127.0.0.1",
        "--dashboard-port", "8050"
      ]
    }lick the **options menu** (next to the up arrow/return button)
2. E
  }
}
```

**Available server arguments:**

| Argument | Description | Default |
| -------- | ----------- | ------- |
| `--dashboard-host` | Host for embedded web dashboard | *(disabled)* |
| `--dashboard-port` | Port for embedded web dashboard | *(disabled)* |
| `--max-session-duration-hours` | Max hours before auto-close caps session end_time | `4.0` |

**Environment variables:**

Configure via `env` in your `mcp.json` or system environment:

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `AI_MAX_SESSION_DURATION_HOURS` | Max session duration in hours | `4.0` |
| `AI_OUTPUT_DIR` | Redirect session data to a custom directory | `.ai_sessions` |

For backup and sync patterns (cloud sync, S3, rsync, git), see the [Backup and Sync Guide](docs/backup-sync-guide.md).

**Example with environment variables:**

```json
{
  "servers": {
    "ai-session-tracker": {
      "command": "ai-session-tracker",
      "args": ["server"],
      "env": {
        "AI_MAX_SESSION_DURATION_HOURS": "8.0"
      }
    }
  }
}
```

> 💡 **Tip:** The `--max-session-duration-hours` setting prevents overnight sessions from skewing metrics. When a session exceeds this limit, its end_time is capped at `start_time + max_duration` instead of actual close time.

> 💡 **Tip:** Enable `--dashboard-host` and `--dashboard-port` to get a live web dashboard at `http://127.0.0.1:8050` while the MCP server runs.

---

## 🚀 Quick Start

### 1. Start a Session

The MCP tools are available in VS Code Copilot Chat when using the "Session Tracked Agent" chat mode (see [Enabling Agent Mode](#-enabling-agent-mode)).

Once enabled, simply describe your task and the agent handles session tracking automatically:

```text
Implement user authentication
```

### 2. Log Interactions

Interactions are logged automatically by the agent as you work. Each prompt/response pair is captured with context.

### 3. End Session

When you're done, the agent closes the session with the appropriate outcome. You can also explicitly request:

```text
End the session as success
```

### 4. View Dashboard

```bash
# Open the web dashboard
ai-session-tracker dashboard

# Then visit http://localhost:8050
```

---

## 🤖 Enabling Agent Mode

After installation, enable the Session Tracked Agent to start automatic session tracking:

### GitHub Copilot (VS Code & Visual Studio)

1. Open Copilot Chat
2. Click the agent dropdown (top of chat panel)
3. Select **"Session Tracked Agent"**

The agent mode persists for your chat session.

### Codex Plugin (VS Code only)

**Important:** First enable IDE context access:

1. In the Codex chat input, ensure **"Include IDE context"** is turned **ON**
2. Look for a **blue icon** — this confirms Codex can see your IDE context (files, selections, workspace structure)

Without IDE context enabled, the agent cannot access your workspace and session tracking may not function properly.

Then at the start of your conversation, type:

```text
Use the Session Tracked Agent as the default for the rest of the conversation.
```

Codex will then track sessions automatically for all subsequent interactions.

---

## 🛠️ CLI Commands

```bash
# Start MCP server (for VS Code integration)
ai-session-tracker server

# Start MCP server with embedded dashboard
ai-session-tracker server --dashboard-host 0.0.0.0 --dashboard-port 8050

# Start MCP server with custom max session duration (8 hours)
ai-session-tracker server --max-session-duration-hours 8.0

# Start standalone web dashboard
ai-session-tracker dashboard [--host HOST] [--port PORT]

# Generate text report to stdout
ai-session-tracker report

# Install MCP config and agent files to current project
ai-session-tracker install

# Install as a system service (auto-start on login)
ai-session-tracker install --service
```

---

## 📝 Session Tracking CLI

Track sessions from the command line without needing an MCP server:

```bash
# Start a session - returns session_id
ai-session-tracker start \
  --name "Implement login feature" \
  --type code_generation \
  --model claude-opus-4-20250514 \
  --mins 60 \
  --source manual

# Log an interaction
ai-session-tracker log \
  --session-id "SESSION_ID" \
  --prompt "Create login form component" \
  --summary "Generated React component with validation" \
  --rating 5

# Flag an issue
ai-session-tracker flag \
  --session-id "SESSION_ID" \
  --type hallucination \
  --desc "AI referenced non-existent library" \
  --severity high

# List active sessions
ai-session-tracker active

# End a session
ai-session-tracker end \
  --session-id "SESSION_ID" \
  --outcome success \
  --notes "Feature completed successfully"
```

### Command Reference

| Command | Description | Required Args |
| ------- | ----------- | ------------- |
| `start` | Start a new session | `--name`, `--type`, `--model`, `--mins`, `--source` |
| `log` | Log an interaction | `--session-id`, `--prompt`, `--summary`, `--rating` |
| `end` | End a session | `--session-id`, `--outcome` |
| `flag` | Flag an issue | `--session-id`, `--type`, `--desc`, `--severity` |
| `active` | List active sessions | *(none)* |

### Task Types

`code_generation`, `debugging`, `refactoring`, `testing`, `documentation`, `analysis`, `architecture_planning`, `human_review`

### Output Formats

All commands support `--json` flag for machine-readable output:

```bash
ai-session-tracker start --name "Test" --type testing --model gpt-4 --mins 30 --source manual --json
# Output: {"success": true, "message": "Session started", "data": {"session_id": "..."}}
```

### Execution Context Isolation

Sessions track an **execution context** (`foreground` or `background`) to enable independent operation:

- **MCP sessions** run as `foreground` — interactive use via VS Code Copilot Chat
- **CLI sessions** run as `background` — batch scripts, CI pipelines, or background processes

**Why this matters:** When you start a new session, any previous *active* session with the **same** execution context is auto-closed with outcome `partial`. Sessions with different contexts are unaffected.

This allows you to:

- Run background batch processes via CLI while interactively using MCP
- Avoid accidentally closing automation sessions when starting interactive work
- Keep foreground and background metrics separate

---

## 🔄 Background Service

Install the MCP server as a system service to run automatically at login:

```bash
# Install as service (creates systemd user service on Linux, launchd agent on macOS, Task Scheduler on Windows)
ai-session-tracker install --service

# Manage the service
ai-session-tracker service start     # Start the service
ai-session-tracker service stop      # Stop the service
ai-session-tracker service status    # Check service status
ai-session-tracker service uninstall # Remove the service
```

### Platform Support

| Platform | Service Type | Location |
| -------- | ------------ | -------- |
| Linux | systemd user service | `~/.config/systemd/user/ai-session-tracker.service` |
| macOS | launchd user agent | `~/Library/LaunchAgents/com.ai-session-tracker.mcp.plist` |
| Windows | Task Scheduler | `AISessionTracker` scheduled task |

---

## 🔧 MCP Tools

| Tool | Description |
| ---- | ----------- |
| `start_ai_session` | Begin a new tracking session |
| `log_ai_interaction` | Record a prompt/response exchange |
| `end_ai_session` | Complete session with outcome |
| `flag_ai_issue` | Report problems for analysis |
| `log_code_metrics` | Analyze modified code quality |
| `get_ai_observability` | Retrieve analytics report |
| `get_active_sessions` | List sessions not yet ended |

---

## 📁 Project Structure

```text
ai-session-tracker-mcp/
├── src/ai_session_tracker_mcp/    # Main package
│   ├── server.py                  # MCP server implementation
│   ├── models.py                  # Domain models
│   ├── storage.py                 # JSON persistence
│   ├── statistics.py              # Analytics engine
│   ├── presenters.py              # Dashboard view models
│   ├── cli.py                     # Command-line interface
│   ├── web/                       # FastAPI dashboard
│   └── agent_files/               # VS Code integration files
├── tests/                         # Test suite (564 tests)
└── utils/                         # Development utilities
```

---

## 📚 Architecture Documentation

Detailed AI-readable architecture docs for each component:

| Component    | Documentation                                                                |
| ------------ | ---------------------------------------------------------------------------- |
| Main Package | [src/ai_session_tracker_mcp/README.md](src/ai_session_tracker_mcp/README.md) |
| Test Suite   | [tests/README.md](tests/README.md)                                           |

---

## 🧪 Development

### Setup

```bash
# Clone repository
git clone https://github.com/mgrandau/ai-session-tracker-mcp.git
cd ai-session-tracker-mcp

# Install with PDM
pdm install

# Run tests
pdm run test

# Run all checks (lint, typecheck, security, test-cov)
pdm run check-all
```

### Available Scripts

| Command | Description |
| ------- | ----------- |
| `pdm run test` | Run pytest |
| `pdm run test-cov` | Run tests with coverage |
| `pdm run lint` | Run ruff linter |
| `pdm run format` | Format code with ruff |
| `pdm run typecheck` | Run mypy type checker |
| `pdm run security` | Run bandit security scan |
| `pdm run check-all` | Run all checks |

---

## 📊 Data Storage

Session data is stored in `.ai_sessions/` in your project root:

```text
.ai_sessions/
├── sessions.json      # Session metadata
├── interactions.json  # Logged interactions
├── issues.json        # Flagged issues
└── charts/            # Generated chart images
```

---

## 🔒 Stability

- **MCP Tools** — 🔒 ABI-frozen, breaking changes require major version bump
- **CLI Commands** — 🔒 ABI-frozen
- **Core Classes** — 🔒 ABI-frozen (Session, Interaction, Issue, etc.)
- **Internal APIs** — ⚠️ Subject to change (Presenters, ViewModels)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 💬 Community

💬 [Join the Discord community](https://discord.gg/2KqjHvh5)

---

## 🤝 Contributing

Contributions welcome! Please ensure:

- All tests pass (`pdm run test`)
- Code is formatted (`pdm run format`)
- No lint errors (`pdm run lint`)
- Type checks pass (`pdm run typecheck`)
