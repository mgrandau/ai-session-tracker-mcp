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

---

## Issue 15: Auto-capture developer and project identifiers in session JSON

### The problem

Every session record needs to know who wrote it and which project it belongs to. Without this, aggregated data from `AI_OUTPUT_DIR` is anonymous — you can count sessions but can't attribute them to a developer or project.

### What we considered

**Option A: MCP server auto-detects at startup**
The server could read `os.getcwd()` for project and `git config user.name` for developer when it starts. Works for local per-project installs (VS Code launches the server from the project root). Breaks for global service installs where the server starts from a fixed location unrelated to any project.

**Option B: Environment variables**
`AI_DEVELOPER` and `AI_PROJECT` as env vars in `mcp.json`. Discarded — `AI_PROJECT` was previously used as an S3 path helper (removed in #14) and the boundary is wrong. `AI_DEVELOPER` in a per-project `mcp.json` risks committing someone's personal identity to git.

**Option C: Agent resolves and passes to `start_ai_session`**
Instructions tell the agent to run `git config user.name` and read the workspace folder. Agent passes them as parameters. Works in all cases (local and global server). No hallucination risk because the agent executes deterministic commands, not reasoning about values. This is the approach we're going with.

### Design outcome

**Developer identity** — resolved by the agent at conversation start via `git config user.name`. This is the same name the developer set intentionally for git commits. No new config needed. No hallucination risk.

**Project identity** — stored in `.ai_sessions.yaml` in the project root (not in the `.ai_sessions/` data directory, which can be redirected by `AI_OUTPUT_DIR`). Written by the install command at setup time. Contains only `project: my-api`. Committed to git so the whole team shares the same project name.

**Why the split:**
- `project` is per-repo and shared → committed config file in root
- `developer` is per-machine and personal → never written to a file, always read fresh from `git config user.name`

This avoids any risk of accidentally committing another person's developer name.

### Implementation plan

1. **MCP tool** — add optional `developer` and `project` parameters to `start_ai_session`, store in session JSON
2. **Session model** — add `developer` and `project` fields
3. **Install command** — write `.ai_sessions.yaml` with detected project name (`os.path.basename(os.getcwd())`)
4. **Session tracking instructions** — update to read `.ai_sessions.yaml` for project, run `git config user.name` for developer, pass both to `start_ai_session`
5. **Fallback** — if `.ai_sessions.yaml` doesn't exist (pre-existing installs), fall back to workspace folder name

### What we deliberately left out

No server-side auto-detection. No new environment variables. No per-machine config file for developer identity. The git config is the source of truth for who the developer is — it's already set, already authoritative, already cross-platform.

---

## Issue 16: Split time estimate into initial and final estimate fields

### The problem

The current `human_time_estimate_minutes` field is captured once at session start and never updated. This loses a useful signal: how the developer's estimate evolves from "before starting" to "after finishing." Comparing initial vs. final vs. actual elapsed time is the foundation for estimation accuracy tracking.

There is also a friction problem in the current End Session Protocol. The existing agent instructions say: manually edit `.ai_sessions/sessions.json` to update `human_time_estimate_minutes` if the git-diff calculation exceeds the original estimate. That is awkward — agents should not be editing raw JSON files as a normal workflow step.

### What we resolved

**Two fields replace one:**
- `initial_estimate_minutes` — the developer's gut estimate before starting, captured at `start_ai_session`
- `final_estimate_minutes` — the revised estimate after completing the work, captured at `end_ai_session` as an optional parameter

The rename from `human_time_estimate_minutes` to `initial_estimate_minutes` is deliberate — the old name implied a single canonical estimate, which no longer fits the model. Backward compatibility is preserved in `from_dict()` by reading the old key as a fallback.

**`end_ai_session` becomes the update point:**
The `end_ai_session` handler already updates the session record in place (writes `end_time`, `outcome`, `notes`, flips `status`). `final_estimate_minutes` is just one more field written at that same moment. No separate operation, no JSON surgery.

**The "manual JSON edit" step is removed entirely:**
The current End Session Protocol step 4 ("if calculated > original estimate, manually edit `sessions.json`") is replaced by simply passing `final_estimate_minutes` to `end_ai_session`. This is strictly less friction.

**What `final_estimate_minutes` means in practice:**
For agents, it is populated from the git-diff calculation (insertions + deletions) × 10 ÷ 50, rounded up to the nearest bucket. This is a mechanical proxy for effort, not a subjective retrospective judgment. The instructions will specify this clearly so agents do not have to reason about which value to use.

**Three data points per session:**
After this change every completed session carries:
1. `initial_estimate_minutes` — what the developer thought it would take
2. `final_estimate_minutes` — what the git diff implies it took (effort proxy)
3. Actual elapsed time — `end_time - start_time` (already tracked)

These three together enable estimation accuracy reporting and AI impact visibility over time.

### ROI and productivity calculations

The statistics layer currently uses `human_time_estimate_minutes` as the human baseline for ROI (cost saved, productivity multiplier). After this change:

- **ROI / cost saved / productivity multiplier** → use `final_estimate_minutes` with fallback to `initial_estimate_minutes` when `final_estimate_minutes` is `None` (abandoned sessions, old data). Final is the better baseline because the developer knows the true complexity after completing the work.
- **Estimation accuracy** (initial vs. final vs. actual over time) → deferred to a future issue. This issue is purely data capture.

### What we deliberately left out

Estimation accuracy analytics — comparing initial vs. final vs. actual elapsed time to measure whether developers get better at estimating over time. That belongs in a later issue (related to #13 centralized aggregation). This issue is the data capture layer only.

The `final_estimate_minutes` field is optional at `end_ai_session`. Sessions that were never properly closed (abandoned, crashed) will have it as `None`, which is fine — only completed sessions are meaningful for estimation accuracy anyway.
