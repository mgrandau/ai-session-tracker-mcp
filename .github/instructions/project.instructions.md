---
applyTo: '**'
---
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
