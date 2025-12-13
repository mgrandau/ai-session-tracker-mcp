---
applyTo: '**'
---
# Session Tracking

## 🚨 Every request = session. No exceptions.
1. `start_ai_session(name, type, model, mins, source)` → get session_id
2. `log_ai_interaction(session_id, prompt, summary, rating)` — ⚠️ MIN 1 before end!
3. `flag_ai_issue(session_id, type, desc, severity)` — if needed
4. `end_ai_session(session_id, outcome)`

**Types:** code_generation|debugging|refactoring|testing|documentation|analysis|architecture_planning|human_review
**Rating:** 1=fail 2=poor 3=partial 4=good 5=perfect
**Severity:** critical|high|medium|low
**Outcome:** success|partial|failed
**Mins:** 30|60|120|240|480|960|2400|4800
**Source:** issue_tracker|manual|historical

**Lost session_id?** → `get_active_sessions()` → find by name → end it
