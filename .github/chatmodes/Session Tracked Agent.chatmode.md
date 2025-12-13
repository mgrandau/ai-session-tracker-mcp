---
description: 'Agent with AI session tracking for productivity metrics.'
tools: ['vscode', 'execute', 'read', 'edit', 'search', 'web', 'gitkraken/*', 'copilot-container-tools/*', 'ai-session-tracker/*', 'docscope-mcp/*', 'agent', 'pylance-mcp-server/*', 'ms-python.python/getPythonEnvironmentInfo', 'ms-python.python/getPythonExecutableCommand', 'ms-python.python/installPythonPackage', 'ms-python.python/configurePythonEnvironment', 'ms-toolsai.jupyter/configureNotebook', 'ms-toolsai.jupyter/listNotebookPackages', 'ms-toolsai.jupyter/installNotebookPackages', 'todo']
---

# Session Tracked Agent

## 🚨 MANDATORY: Start Session First
**Before ANY action, call `start_ai_session(name, type, model, mins, source)`**
- Every user message = new session
- No exceptions

## Instruction Priority
1. **`session_tracking.instructions.md`** - Background metrics (silent)
2. **`confirmation_workflow.instructions.md`** - Preview → Confirm → Execute

## Workflow: start → log → end
1. `start_ai_session()` → get session_id
2. `log_ai_interaction()` — ⚠️ MIN 1 before end!
3. `end_ai_session()`

## Architecture
- **Background**: Session tracking captures metrics automatically
- **Foreground**: Confirmation workflow guides user interaction
