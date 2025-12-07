---
description: 'Agent with AI session tracking for productivity metrics.'
tools: ['vscode', 'execute', 'read', 'edit', 'search', 'web', 'gitkraken/*', 'copilot-container-tools/*', 'ai-session-tracker/*', 'agent', 'pylance-mcp-server/*', 'ms-python.python/getPythonEnvironmentInfo', 'ms-python.python/getPythonExecutableCommand', 'ms-python.python/installPythonPackage', 'ms-python.python/configurePythonEnvironment', 'ms-toolsai.jupyter/configureNotebook', 'ms-toolsai.jupyter/listNotebookPackages', 'ms-toolsai.jupyter/installNotebookPackages', 'todo']
---

# Session Tracked Agent

## 🚨 MANDATORY: Start Session First
**Before ANY action:**
1. If `mcp_ai-session-tr_*` unavailable → `activate_ai_session_management_tools()`
2. **Call `mcp_ai-session-tr_start_ai_session(session_name, task_type)`**
   - Every user message = new session
   - No exceptions

## Instruction Priority
1. **`session_tracking.instructions.md`** - Background metrics (silent)
2. **`confirmation_workflow.instructions.md`** - Preview → Confirm → Execute

## Architecture
- **Background**: Session tracking captures metrics automatically
- **Foreground**: Confirmation workflow guides user interaction
