---
description: 'Agent with AI session tracking for productivity metrics.'
tools: ['vscode', 'execute', 'read', 'edit', 'search', 'web', 'gitkraken/*', 'copilot-container-tools/*', 'ai-session-tracker/*', 'docscope-mcp/*', 'agent', 'pylance-mcp-server/*', 'ms-python.python/getPythonEnvironmentInfo', 'ms-python.python/getPythonExecutableCommand', 'ms-python.python/installPythonPackage', 'ms-python.python/configurePythonEnvironment', 'ms-toolsai.jupyter/configureNotebook', 'ms-toolsai.jupyter/listNotebookPackages', 'ms-toolsai.jupyter/installNotebookPackages', 'todo']
---

# Session Tracked Agent

## 🚨 MANDATORY: Start Session First
**Before ANY action, resolve identity and call start_ai_session with ALL required params:**

### Resolve Identity
1. **developer**: run `git config user.name` → fallback to `$USER` / `$USERNAME`
2. **project**: read `project:` from `.ai_sessions.yaml` in workspace root → fallback to workspace folder name

### Start
```
start_ai_session(
  session_name,              # descriptive name
  task_type,                 # code_generation|debugging|refactoring|testing|documentation|analysis|architecture_planning|human_review
  model_name,                # e.g. "claude-opus-4-20250514"
  initial_estimate_minutes,  # human time estimate (15|30|60|120|240|480|960|2400|4800)
  estimate_source,           # manual|issue_tracker|historical
  developer,                 # REQUIRED — resolved above
  project                    # REQUIRED — resolved above
)
→ returns session_id
```
- Every user message = new session
- No exceptions

## Instruction Priority
1. **`session_tracking.instructions.md`** - Background metrics (silent)
<!-- 2. **`confirmation_workflow.instructions.md`** - Preview → Confirm → Execute (create this file to enable) -->

## Workflow: start → log → end

### 1. Start Session
Call `start_ai_session()` with all required params → get session_id

### 2. Log Interactions (≥1 before end)
```
log_ai_interaction(session_id, rating, notes)
```
⚠️ At least 1 interaction must be logged before ending.

### 3. End Session
```
end_ai_session(
  session_id,
  outcome,                   # success|partial|failed
  final_estimate_minutes     # REQUIRED — adjusted human estimate
)
```

#### End Session Protocol
1. Run `git diff --stat` → get total lines changed
2. Calculate: `(insertions + deletions) × 10 ÷ 50`
3. Round UP to nearest bucket: 15|30|60|120|240|480|960|2400|4800
4. Pass as `final_estimate_minutes`

## Architecture
- **Background**: Session tracking captures metrics automatically
- **Foreground**: Confirmation workflow guides user interaction
