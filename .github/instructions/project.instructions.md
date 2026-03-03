---
applyTo: '**'
---
# Project Intent & Design

This project follows the [Human-AI Intent Transfer Principles](https://mgrandau.medium.com/human-ai-intent-transfer-principles-b6e7404e3d26?source=friends_link&sk=858917bd3f4a686974ed6b6c9c059ac8) — eight principles for making human intent legible to AI systems.

**Context chain (read in order when making design decisions):**

1. [🧭 Intent](../../README.md#-intent) — project philosophy: intent leads, measurement follows
2. [PROJECT_PLAN.md](../../docs/PROJECT_PLAN.md) — phase goals, risk posture, intent evolution
3. [Journal entries](../../docs/journal/) — design alternatives explored and rejected, with rationale
4. Source code — the implementation

**Core design values (from rejection patterns in the journal):**

- **Collection ≠ storage** — the MCP server writes files, it doesn't own backup or sync (S3 removed in Phase 4)
- **Portability over convenience** — env vars over config files, works on OneDrive/NAS/local
- **Schema decisions are permanent** — required fields enforced because optional fields produce garbage data
- **Agent files are package-managed** — always overwritten on install, not user-editable
- **Mechanical over subjective** — git-diff proxy for effort, git config for identity, no retrospective guessing

When proposing new features or changes, check the journal for prior art — the alternative you're considering may have already been evaluated and rejected.

# Release Process

## Version Badge
The README badge auto-updates from GitHub releases - no manual badge edits needed.

## Release Steps
1. Update version in `src/ai_session_tracker_mcp/__version__.py`
2. Commit changes: `git commit -am "release: bump version to X.X.X"`
3. Create and push tag: `git tag vX.X.X && git push origin vX.X.X`
4. Create GitHub release with **changelog notes** covering:
   - **Bug Fixes** — issues fixed with brief description
   - **Features** — new functionality added
   - **Documentation** — significant doc improvements
   - **Issue Triage** — any issue label changes (approved-fix, hold-future, etc.)
   - Link to full changelog comparison: `https://github.com/mgrandau/ai-session-tracker-mcp/compare/vPREV...vX.X.X`

## Changelog Requirements
- Every release **must** have human-written changelog notes — do not rely solely on `--generate-notes`
- Reference issue numbers (e.g., "Fixed #18: display bug in presenters.py")
- Keep notes concise but meaningful — someone reading them should understand what changed and why

## Notes
- Tags must match pattern `vX.X.X` (e.g., `v1.0.3`)
- `--generate-notes` auto-generates release notes from commits
- Badge updates within minutes of release creation

# Markdown
All markdown files must pass linting. Fix all markdown linting errors before committing.
