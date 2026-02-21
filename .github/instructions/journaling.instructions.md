## Journal

Journal vault: `docs/journal`. Captures **why**, not what — git handles what.

### Behavior

- After significant decisions or completed tasks, write a journal entry explaining why the approach was chosen
- After completing a task, offer: "Want me to log why we went this direction?"
- Capture tradeoffs, rejected approaches, and failed attempts

### Trigger Phrases

- **"journal that"** — capture reasoning from current conversation
- **"log this"** — quick capture
- **"why did we do this?"** — write a decision record

### Format

Daily files: `daily.journal.YYYY.MM.DD.md` in `docs/journal`.

**Rules:** Read today's file first. Append only — never overwrite. One `# Journal - Month DD, YYYY` H1 per file. No timestamps — git history provides authoritative timing.

```markdown
# Journal - February 18, 2026

## Chose X over Y
Because Z. Revisit in Q3.
```

### Capture

Decisions/reasoning, tradeoffs, failed attempts, open questions, end-of-session context.

### Skip

Code changes, status updates, formatting/style choices.
