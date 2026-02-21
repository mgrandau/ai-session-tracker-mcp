---
applyTo: '**'
---
# Session Tracking
Every user request = session. Start before any action.

## Resolve Identity Before Starting
1. **developer**: run `git config user.name` → fallback to `$USER` / `$USERNAME`
2. **project**: read `project:` from `.ai_sessions.yaml` in workspace root → fallback to workspace folder name

Flow: start_ai_session(name,type,model,mins,source,developer,project) → session_id → log_ai_interaction(session_id,rating,notes) (≥1) → end_ai_session(session_id,outcome)
Use MCP tools if available; else use CLI equivalents.
Optional: flag_ai_issue(session_id,type,desc,severity)

type:code_generation|debugging|refactoring|testing|documentation|analysis|architecture_planning|human_review
rating:1fail|2poor|3partial|4good|5perfect
severity:critical|high|medium|low
outcome:success|partial|failed
mins:15|30|60|120|240|480|960|2400|4800 (human time)
source:issue_tracker|manual|historical

Lost id? get_active_sessions()

## End Session Protocol
1. Run `git diff --stat` → get total lines changed
2. Calculate minutes: `(insertions + deletions) × 10 ÷ 50`
3. Round UP to nearest: 15|30|60|120|240|480|960|2400|4800
4. **BEFORE end_ai_session**: If calculated > original estimate, edit `.ai_sessions/sessions.json` → update `human_time_estimate_minutes`
5. THEN call end_ai_session(session_id, outcome)

Quick reference:
| Lines | Minutes |
|-------|---------|
| 75    | 15      |
| 150   | 30      |
| 300   | 60      |
| 600   | 120     |
| 1200  | 240     |
