---
id: k9bxhwrtppqz3n8l2yframo
title: Journal - February 25, 2026
desc: ''
updated: 1771993601000
created: 1771993601000
traitIds:
  - journalNote
---

# Journal - February 25, 2026

## Summary

Shipped four releases in one session (v1.1.0 → v1.1.3), resolving Issue #19 and layering on three follow-up improvements to install behavior, schema enforcement, and documentation. Also updated the backup-sync guide with proper MCP config guidance.

## Work Completed

- **Issue #19 fix — `env` block replaces `_env_example` (v1.1.0)**: Root cause was `_generate_mcp_server_config()` writing `_env_example` (underscore-prefixed key ignored by MCP hosts) instead of `env`. Fix generates a real `env` block with `AI_OUTPUT_DIR` (empty default) and `AI_MAX_SESSION_DURATION_HOURS` (default `"4.0"`). Empty string falls through safely: `Config.get_output_dir()` returns `None` → defaults to `.ai_sessions`. Added diagnostic startup logging to `StorageManager` — logs resolution source, warns on empty env var. Commit `3caa734`.

- **Dashboard auto-start on install (v1.1.1)**: Generated `mcp.json` now includes `--dashboard-host 127.0.0.1 --dashboard-port 8000` in server args so the web dashboard launches automatically when VS Code starts the MCP server. Commit `381ee2d`.

- **Required fields enforcement (v1.1.2)**: `developer` and `project` added to `start_ai_session` required array. `final_estimate_minutes` added to `end_ai_session` required array — it's the adjusted human baseline that drives ROI calculation and can't be skipped. Rewrote both `session_tracking.instructions.md` and `Session Tracked Agent.agent.md` with explicit param lists, REQUIRED labels, inline identity resolution, and end session protocol. Commits `753e04b`, `ff102f1`.

- **Install always overwrites agent files (v1.1.3)**: `_copy_agent_files()` previously skipped existing files to "preserve user customizations." This meant schema changes from v1.1.2 would never propagate to existing installs. Changed to always overwrite — agent files are package-managed, not user-editable. Commit `6a484a3`.

- **Backup-sync guide update**: Pattern 1 now properly documents the two-step setup: (1) set `AI_OUTPUT_DIR` at the OS level, (2) reference it in `mcp.json` via `${env:AI_OUTPUT_DIR}` so VS Code passes it through. Previous version incorrectly hardcoded the path in the `env` block. Commits `ae0d575`, `ceace7f`.

## Decision Log

- **`env` over `_env_example`**: MCP hosts only read the `env` key. The underscore-prefixed `_env_example` was dead documentation that users had to manually rename — easy to miss and the root cause of #19. Empty defaults fall through safely, so no behavior change for users who don't set the var.

- **Dashboard args in install**: Users shouldn't have to know about `--dashboard-host` and `--dashboard-port`. The install should produce a working config out of the box.

- **`developer`, `project`, `final_estimate_minutes` required**: These were technically optional in the schema, which meant agents would silently skip them. `developer`/`project` are needed for team-wide analytics. `final_estimate_minutes` is the core ROI metric — without it, we can't calculate time saved.

- **Always overwrite agent files**: These are package-managed files that define the agent's behavior contract. Users who want custom instructions should create separate files, not edit the bundled ones. Overwriting on install ensures schema changes propagate.

- **`${env:AI_OUTPUT_DIR}` in mcp.json**: The `env` block should reference the OS-level variable, not hardcode a path. This keeps the config portable — same `mcp.json` works for every developer, each with their own `AI_OUTPUT_DIR` set at the OS level.

## Commits

- `3caa734` — Issue #19 fix: generate `env` block, add StorageManager diagnostics
- `120d2a1` — Acceptance test: developer/project identity verification
- `6707308` — Release v1.1.0
- `381ee2d` — Install includes dashboard args by default
- `be28e82` — Release v1.1.1
- `753e04b` — Make developer, project, final_estimate_minutes required
- `ff102f1` — Update Session Tracked Agent with required params
- `c55cf47` — Release v1.1.2
- `6a484a3` — Install always overwrites agent files
- `ea06b0d` — Release v1.1.3 (squashed into `6a484a3`)
- `ae0d575` — Docs: add mcp.json env block to backup-sync guide
- `ceace7f` — Docs: fix Pattern 1 ordering (env var first, then mcp.json reference)

## Test Stats

- 573 unit tests passing, 99.55% overall coverage
- `storage.py` at 100% coverage
- 31/31 acceptance checks (`tests/acceptance/test_output_dir_redirect.sh`)

## Notes

- All four releases cut in a single session — Mark identified each issue in rapid succession during review
- The acceptance test validates the full chain: default behavior → env var redirect → install config → mcp.json schema → developer/project identity persistence
- Windows gotcha documented: VS Code doesn't pick up env var changes until fully restarted
