---
applyTo: '**'
---
# AI Session Tracking

## 🚨 Start Session First
Call `start_ai_session(name, type, model, mins, source)` before any other tool.

## Workflow
1. **Start** → `start_ai_session` → get session_id
   - type: code_generation|debugging|refactoring|testing|documentation|analysis|architecture_planning|human_review
   - model: your model name (e.g. "claude-opus-4-20250514")
   - mins: human time estimate in minutes (see table)
   - source: issue_tracker|manual|historical
2. **Log** → `log_ai_interaction(session_id, prompt, summary, rating)` after each response
   - rating: 1=failed 2=poor 3=partial 4=good 5=perfect
3. **Flag** → `flag_ai_issue(session_id, type, desc, severity)` — severity: critical|high|medium|low
4. **End** → `end_ai_session(session_id, outcome)` — outcome: success|partial|failed

## Time Estimates (mins)
30=0.5h | 60=1h | 120=2h | 240=4h | 480=8h | 960=16h | 2400=40h | 4800=80h
