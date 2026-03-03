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

- **`env` over `_env_example`**: MCP hosts only read the `env` key. The underscore-prefixed `_env_example` was dead documentation that users had to manually rename — easy to miss and the root cause of #19. Empty defaults fall through safely, so no behavior change for users who don't set the var. **Rejected alternative:** generate a comment block or README-only documentation of env vars instead of a real `env` block. Rejected because the whole point is zero-friction — if the user has to copy/rename/uncomment, they won't.

- **Dashboard args in install**: Users shouldn't have to know about `--dashboard-host` and `--dashboard-port`. The install should produce a working config out of the box. **Rejected alternative:** require users to manually add dashboard args or run a separate `ai-session-tracker dashboard` command. Rejected because a dead dashboard (no args = no dashboard) looks like a broken feature, not a configuration choice.

- **`developer`, `project`, `final_estimate_minutes` required**: These were technically optional in the schema, which meant agents would silently skip them. `developer`/`project` are needed for team-wide analytics. `final_estimate_minutes` is the core ROI metric — without it, we can't calculate time saved. **Rejected alternative:** keep them optional and validate at report time. Rejected because missing data at write time can't be recovered later — the agent has the context at session start/end, not at report time.

- **Always overwrite agent files**: These are package-managed files that define the agent's behavior contract. Users who want custom instructions should create separate files, not edit the bundled ones. Overwriting on install ensures schema changes propagate. **Rejected alternative:** merge/patch strategy that preserves user edits while updating schema-relevant sections. Rejected as fragile — instruction files aren't structured data, they're prose. Merging prose reliably is an unsolved problem.

- **`${env:AI_OUTPUT_DIR}` in mcp.json**: The `env` block should reference the OS-level variable, not hardcode a path. This keeps the config portable — same `mcp.json` works for every developer, each with their own `AI_OUTPUT_DIR` set at the OS level. **Rejected alternative:** per-user `.vscode/mcp.local.json` override file. Rejected because VS Code doesn't support config layering for MCP — there's one `mcp.json` and that's it.

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

## Schema-vs-Instructions Sync Testing

Added `tests/test_agent_schema_sync.py` — 11 mechanical tests that catch drift between MCP tool schemas (server.py) and the instruction/agent files. Commit `5849b05`.

### What it tests (no LLM needed)
- Every required param in `start_ai_session` / `end_ai_session` schema appears in both the instructions and agent file
- All enum values (task_type, outcome, estimate_source) listed in instructions
- Bundled agent file (`src/agent_files/`) and repo copy (`.github/agents/`) are identical
- Instructions have valid YAML frontmatter, reference all four MCP tools, use REQUIRED labels

### What it can't test
Whether an LLM *actually follows* the instructions correctly. That requires behavioral evaluation — feeding the instructions + a mock user request to a model and verifying the generated tool calls contain all required params.

### Options researched for LLM-based prompt/instruction testing

1. **Braintrust Autoevals** (`pip install autoevals`) — lightweight LLM-as-judge scoring. Could write test cases like "given these instructions and this user request, did the model generate a tool call with all required params?"

2. **DeepEval** (`pip install deepeval`) — more full-featured. Built-in metrics for tool use correctness, hallucination, faithfulness. Define test cases with expected tool calls and grade against actual output.

3. **Microsoft Prompty** (`pip install prompty`) — designed for prompt testing. Define prompts as assets, run through models, evaluate outputs.

4. **OpenAI Evals** — heavier setup, battle-tested.

5. **GitHub Copilot as evaluator** — no standalone API for programmatic testing. Copilot is embedded in VS Code / Codex / GitHub, not available as a raw HTTP endpoint. Possible workarounds:
   - Use the Copilot Coding Agent to manually spot-check via GitHub Issues
   - Call the underlying model (Claude, GPT-4o) directly — same model, just without the Copilot wrapper
   - Trigger Copilot Coding Agent in CI via GitHub Actions on PR

6. **Direct model call** — simplest practical approach. ~50 lines of Python using `openai` or `anthropic` SDK: send instructions + mock prompt → check response has correct tool call with all required params. Costs cents per run, non-deterministic.

### Assessment
Mechanical sync tests catch ~90% of bugs (the exact class from the v1.1.2 fix). LLM behavioral eval covers the remaining ~10% but is non-deterministic — useful as a smoke test, risky as a CI gate. Filed as Issue #20 (hold-future).
