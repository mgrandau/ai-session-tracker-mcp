---
applyTo: '**'
---
# Session Tracking
Every user request = session. Start before any action.

## Resolve Identity Before Starting
1. **developer**: run `git config user.name` → fallback to `$USER` / `$USERNAME`
2. **project**: read `project:` from `.ai_sessions.yaml` in workspace root → fallback to workspace folder name

## Flow

### 1. Start Session (required before any work)
```
start_ai_session(
  session_name,              # descriptive name for the task
  task_type,                 # see types below
  model_name,                # e.g. "claude-opus-4-20250514"
  initial_estimate_minutes,  # human time estimate (see buckets)
  estimate_source,           # manual|issue_tracker|historical
  developer,                 # REQUIRED — from git config or $USER
  project                    # REQUIRED — from .ai_sessions.yaml or folder name
)
→ returns session_id
```

### 2. Log Interactions (≥1 per session)
```
log_ai_interaction(session_id, rating, notes)
```

### 3. End Session
```
end_ai_session(
  session_id,
  outcome,                   # success|partial|failed
  final_estimate_minutes     # REQUIRED — adjusted human estimate (see End Session Protocol)
)
```

Use MCP tools if available; else use CLI equivalents.
Optional: `flag_ai_issue(session_id, type, desc, severity)`

## Valid Values
- type: code_generation|debugging|refactoring|testing|documentation|analysis|architecture_planning|human_review
- rating: 1 fail|2 poor|3 partial|4 good|5 perfect
- severity: critical|high|medium|low
- outcome: success|partial|failed
- minutes (buckets): 15|30|60|120|240|480|960|2400|4800 (human time)
- source: issue_tracker|manual|historical

Lost id? `get_active_sessions()`

## End Session Protocol
1. Run `git diff --stat` → get total lines changed
2. Calculate minutes: `(insertions + deletions) × 10 ÷ 50`
3. Round UP to nearest bucket: 15|30|60|120|240|480|960|2400|4800
4. Call `end_ai_session(session_id, outcome, final_estimate_minutes=<calculated>)`

Quick reference:
| Lines | Minutes |
|-------|---------|
| 75    | 15      |
| 150   | 30      |
| 300   | 60      |
| 600   | 120     |
| 1200  | 240     |
