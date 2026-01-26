---
applyTo: '**'
---
# Release Process

## Version Badge
The README badge auto-updates from GitHub releases - no manual badge edits needed.

## Release Steps
1. Update version in `src/ai_session_tracker_mcp/__version__.py`
2. Commit changes: `git commit -am "Bump version to X.X.X"`
3. Create and push tag: `git tag vX.X.X && git push origin vX.X.X`
4. Create release: `gh release create vX.X.X --title "vX.X.X" --generate-notes`

## Notes
- Tags must match pattern `vX.X.X` (e.g., `v1.0.3`)
- `--generate-notes` auto-generates release notes from commits
- Badge updates within minutes of release creation
