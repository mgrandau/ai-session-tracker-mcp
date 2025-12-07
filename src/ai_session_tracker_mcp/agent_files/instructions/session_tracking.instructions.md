---
applyTo: '**'
---
# AI Session Tracking

## 🚨 First: Start Session
`mcp_ai-session-tr_start_ai_session(session_name, task_type)` before any tool.

## Workflow
1. **Start** → `start_ai_session(name, type)` → session_id
   - type: code_generation|debugging|refactoring|testing|documentation|analysis|architecture_planning|human_review
2. **Log** → `log_ai_interaction(session_id, prompt, response_summary, effectiveness_rating)`
   - rating: 5=perfect|4=high|3=works|2=rework|1=failed
3. **Flag** → `flag_ai_issue(session_id, issue_type, description, severity)` on problems
   - severity: critical|high|medium|low
4. **Metrics** → `log_code_metrics(session_id, file_path, functions_modified)` (Python only)
5. **End** → `end_ai_session(session_id, outcome)` when complete
   - outcome: success|partial|failed
