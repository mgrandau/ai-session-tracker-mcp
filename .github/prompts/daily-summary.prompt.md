---
description: "Generate a structured end-of-day journal entry from git commits, AI sessions, and memory notes."
---

# Daily Journal Summary

## 1. Gather Context

- `git log --since="00:00" --oneline`
- `.ai_sessions/sessions.json` (if exists)
- `/memories/session/` notes (if exists)
- Today's existing journal file (if exists) — preserve real-time entries

## 2. Create/Update Daily Note

Path: `docs/journal/daily.{{YYYY}}.{{MM}}.{{DD}}.md`. Update if exists (preserve Decision Log entries), otherwise create. One H1, no duplicates. No timestamps on entries — git history provides authoritative timing.

## 3. Note Format

```markdown
---
id: daily.{{YYYY}}.{{MM}}.{{DD}}
title: Journal - {{Month DD, YYYY}}
created: {{local timestamp}}
updated: {{local timestamp}}
---

# Journal - {{Month DD, YYYY}}

## Summary
2-3 sentence overview.

## Work Completed
- Major accomplishments with file refs: [file.py](../src/path/file.py)

## Commits
- Today's commits with short descriptions

## AI Sessions
- Session names and outcomes

## Decision Log
- (Preserve real-time entries captured during the day)

## Notes
Blockers, context, thoughts for tomorrow.

## Next Steps
- What to pick up next session
```

## 4. Behavior

- Concise but complete. Wiki-link previous days: `[[daily.{{YYYY}}.{{MM}}.{{DD-1}}]]`
- Code snippets only if they illustrate key changes
- Track time estimates vs actual where available
