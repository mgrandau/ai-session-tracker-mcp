---
id: be334c49-e6c8-4fca-8622-cba19c6e3d02
title: "February 20, 2026"
desc: ""
updated: 1771636030538
created: 1771634575707
---

# Journal - February 20, 2026

First entry. Dendron vault initialized for project journaling.

## Issue 13: AI_OUTPUT_DIR — Redirect Session Data to Any Directory

Closed Issue 13, which adds the `AI_OUTPUT_DIR` environment variable. This lets the AI session tracker MCP server write all session data to an arbitrary directory instead of the default `.ai_sessions` folder in the project root.

### Why this matters

The MCP server runs locally per-developer, but teams need a way to aggregate session data across people and projects. By pointing `AI_OUTPUT_DIR` at a synced folder, each developer's local MCP server becomes a silent contributor to a shared dataset — no extra tooling required.

The canonical use case is OneDrive or SharePoint: a developer sets `AI_OUTPUT_DIR=/home/jsmith/OneDrive/ai-metrics/my-project` and sync happens transparently via the cloud client. A project lead or manager can then open the web dashboard against the shared folder to see team-wide ROI metrics.

### Why env var over config file

A config file would couple the setting to the project repo, creating merge conflicts when multiple developers have different local paths. An environment variable stays on the machine, not in git, which is the right boundary for a path that is personal to the developer's local sync setup.

### How to set AI_OUTPUT_DIR

There are two ways to configure it, with different scopes:

**Per-project via `mcp.json`** — add an `env` block to the server entry in `.vscode/mcp.json`:

```json
"ai-session-tracker": {
  "command": ".venv/bin/ai-session-tracker",
  "args": ["server"],
  "env": {
    "AI_OUTPUT_DIR": "/home/jsmith/OneDrive/ai-metrics/my-project"
  }
}
```

Each repo can have a different destination. The `install` command scaffolds an `_env_example` block in the generated `mcp.json` as a reminder — rename it to `env` and fill in the path to activate it.

**System-wide via shell environment** — set it once and every project inherits it automatically with no per-project config needed.

On Linux/macOS, add to `~/.bashrc` or `~/.profile`:

```bash
export AI_OUTPUT_DIR=/home/jsmith/OneDrive/ai-metrics
```

On Windows, set a user environment variable via System Properties → Environment Variables, or from PowerShell:

```powershell
[Environment]::SetEnvironmentVariable("AI_OUTPUT_DIR", "C:\Users\jsmith\OneDrive\ai-metrics", "User")
```

A per-project `mcp.json` `env` block takes precedence and overrides the system-wide value for specific repos.

Precedence: `mcp.json` env block → shell environment → default (`.ai_sessions` in project root).

### Centralization patterns enabled

- **OneDrive/SharePoint**: Each dev syncs their `AI_OUTPUT_DIR` subtree into a shared drive folder. IT can provision the share; developers just set the env var.
- **Dropbox / Google Drive**: Same pattern, different sync client.
- **Network share**: `AI_OUTPUT_DIR=/mnt/team-nas/ai-sessions/jsmith` works for on-prem environments.
- **Git repo**: Point to a dedicated metrics repo that gets pushed on a schedule.

### What we deliberately left out

No auto-discovery, no push mechanism, no aggregation logic in the server itself. The server stays dumb — it just writes files. The sync is the user's responsibility. This keeps the blast radius small: a misconfigured `AI_OUTPUT_DIR` can only affect file writes, not the MCP protocol or session logic.
