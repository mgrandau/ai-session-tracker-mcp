# Project Plan — ai-session-tracker-mcp

This is a **historical record** of what was actually built, when, and why. It's organized by development phases rather than chronological commits, with GitHub issues and version milestones mapped to each phase.

For the philosophy and design intent behind this project, see [🧭 Intent](../README.md#-intent) in the README. Design decisions and architectural choices throughout this plan trace back to those principles — intent leads, measurement follows.

Current state: **v1.1.3** — 573 tests, 99.55% coverage.

---

## Phase 1: Foundation (2025-12-06 → 2025-12-13)

Established the project from scratch: core architecture, test infrastructure, and the initial feature set.

| Date | Work |
| ---------- | ---- |
| 2025-12-06 | Initial commit — project structure, FileSystem abstraction, install command, first tests |
| 2025-12-08 | Code refactoring and cleanup |
| 2025-12-12 | Gap analysis, dashboard improvements, StatisticsEngine enhancements, CLI refactor, CI workflow |
| 2025-12-13 | Test documentation, bug fixes |

**Key decisions:**
- FileSystem abstraction from day one (testability over convenience)
- CI pipeline established early
- Dashboard and statistics engine built alongside core tracking

---

## Phase 2: Core Features & Installation (2026-01-15 → 2026-01-25)

Closed the first wave of GitHub issues — focused on making the tool installable, usable, and correct.

| Date | Work | Issues |
| ---------- | ---- | ------ |
| 2026-01-15 | CLI install command, global MCP service, config template, auto-close sessions | #1, #2, #3, #4 |
| 2026-01-24 | CLI session tracking, execution context field, agent rename, productivity metrics | #5, #6, #7 |

**Issues resolved:**
- **#1** CLI install command
- **#2** Global MCP service installation
- **#3** Show all MCP server args in config template
- **#4** Auto-close previous session
- **#5** CLI equivalent for MCP server
- **#6** Execution context field
- **#7** Rename agent to VS Code format

**Milestone:** `v1.0.1` (2026-01-15)

---

## Phase 3: Release Engineering & Documentation (2026-01-26 → 2026-02-06)

Stabilized the release process, expanded test coverage, and improved documentation.

| Date | Work | Issues |
| ---------- | ---- | ------ |
| 2026-01-26 | Version checks, CI badges, release process | — |
| 2026-01-31 | Test expansion, instruction updates | #8 |
| 2026-02-02 | README improvements, Codex docs, markdown linting | — |
| 2026-02-06 | mcp.json fixes | — |

**Issues resolved:**
- **#8** Update distributed session tracking instructions

**Milestone:** `v1.0.4` (2026-01-26)

---

## Phase 4: Data Management & Configuration (2026-02-20 → 2026-02-21)

Major refactor of data handling — removed built-in S3 backup in favor of external guides, added configurable output directories, and improved session metadata capture.

| Date | Work | Issues |
| ---------- | ---- | ------ |
| 2026-02-20 | Remove S3 backup (external guide), configurable AI_OUTPUT_DIR, auto-capture dev/project, split estimates, Dendron vault, Discord community | #13, #14, #15, #16 |
| 2026-02-21 | Bug fix for agent reading non-existent file | #9 |

**Issues resolved:**
- **#9** Agent reads non-existent file
- **#13** Configurable output directory (AI_OUTPUT_DIR)
- **#14** Remove S3, document external backup
- **#15** Auto-capture developer/project
- **#16** Split initial/final estimate

**Design discussions (journal):**

These journal entries capture the alternatives explored and rationale behind key decisions:

- [2026-02-20](journal/daily.journal.2026.02.20.md) — **#13 AI_OUTPUT_DIR**: Evaluated MCP server auto-detect vs. environment variables vs. agent-resolved paths. Chose env var for simplicity and cross-host portability. **#15 Auto-capture**: Considered OS username, git config, and explicit params — chose explicit with OS fallback. **#16 Split estimates**: Resolved initial vs. final estimate semantics and impact on ROI calculations. **#17 Integrity**: Evaluated hash chain, sidecar hash, HMAC, git bare repo, and append-only audit log — chose sidecar SHA256 (minimal code, no schema changes).
- [2026-02-21](journal/daily.journal.2026.02.21.md) — Summary of all Phase 4 implementations, decision log, and next steps.

**Milestone:** `v1.0.5` (2026-02-20)

---

## Phase 5: Quality, Testing & Stability (2026-02-23 → 2026-02-25)

Final push on quality — display bug fixes, documentation upgrades, acceptance tests, and schema validation.

| Date | Work | Issues |
| ---------- | ---- | ------ |
| 2026-02-23 | Display bug fix (open session count), Codex MCP server docs | #10, #18 |
| 2026-02-24 | Docstring upgrades across source and tests | — |
| 2026-02-25 | AI_OUTPUT_DIR env block fix, acceptance tests, schema sync tests | #19 |

**Issues resolved:**
- **#10** Codex MCP server setup docs
- **#18** Display bug — open session count
- **#19** AI_OUTPUT_DIR env block fix

**Design discussions (journal):**

- [2026-02-23](journal/daily.journal.2026.02.23.md) — **#18**: Root cause analysis of `completed_sessions` counting from ROI-filtered subset instead of full session set. Decision log on fix approach.
- [2026-02-25](journal/daily.journal.2026.02.25.md) — **#19**: `env` vs `_env_example` root cause. Decision to make `developer`, `project`, `final_estimate_minutes` required fields. Research on LLM-based behavioral testing options (Promptfoo, DeepEval, Prompty) for instruction file validation.

**Milestones:** `v1.0.6` (2026-02-23) → `v1.1.0` → `v1.1.1` → `v1.1.2` (2026-02-25)

---

## Version History

| Version | Date | Highlights |
| ------- | ---- | ---------- |
| v1.0.1 | 2026-01-15 | CLI install, global MCP service, auto-close sessions |
| v1.0.4 | 2026-01-26 | CLI session tracking, release process, CI badges |
| v1.0.5 | 2026-02-20 | Configurable output, split estimates, S3 removal |
| v1.0.6 | 2026-02-23 | Display bug fix, Codex docs |
| v1.1.0 | 2026-02-25 | Env block fix, acceptance tests |
| v1.1.1 | 2026-02-25 | Schema sync tests |
| v1.1.2 | 2026-02-25 | Stability fixes |
| **v1.1.3** | **Current** | **573 tests, 99.55% coverage** |

---

## Roadmap

Open issues tracked for future development:

| Issue | Description | Status |
| ----- | ----------- | ------ |
| [#11](https://github.com/mgrandau/ai-session-tracker-mcp/issues/11) | Package as standalone executable | hold-future |
| [#12](https://github.com/mgrandau/ai-session-tracker-mcp/issues/12) | Code-value metric dashboard | approved-fix |
| [#17](https://github.com/mgrandau/ai-session-tracker-mcp/issues/17) | Sidecar hash files for integrity | hold-future |
| [#20](https://github.com/mgrandau/ai-session-tracker-mcp/issues/20) | LLM behavioral testing | hold-future |
