---
description: 'Agent with AI session tracking for productivity metrics.'
tools: ['vscode/getProjectSetupInfo', 'vscode/installExtension', 'vscode/newWorkspace', 'vscode/openSimpleBrowser', 'vscode/runCommand', 'vscode/vscodeAPI', 'vscode/extensions', 'vscode/memory', 'execute/runNotebookCell', 'execute/testFailure', 'execute/getTerminalOutput', 'execute/runTask', 'execute/createAndRunTask', 'execute/runInTerminal', 'execute/runTests', 'read/getNotebookSummary', 'read/problems', 'read/readFile', 'read/readNotebookCellOutput', 'read/terminalSelection', 'read/terminalLastCommand', 'read/getTaskOutput', 'agent/runSubagent', 'edit/createDirectory', 'edit/createFile', 'edit/createJupyterNotebook', 'edit/editFiles', 'edit/editNotebook', 'search/changes', 'search/codebase', 'search/fileSearch', 'search/listDirectory', 'search/searchResults', 'search/textSearch', 'search/usages', 'search/searchSubagent', 'web/fetch', 'web/githubRepo', 'copilot-container-tools/act_container', 'copilot-container-tools/act_image', 'copilot-container-tools/inspect_container', 'copilot-container-tools/inspect_image', 'copilot-container-tools/list_containers', 'copilot-container-tools/list_images', 'copilot-container-tools/list_networks', 'copilot-container-tools/list_volumes', 'copilot-container-tools/logs_for_container', 'copilot-container-tools/prune', 'copilot-container-tools/run_container', 'copilot-container-tools/tag_image', 'ai-session-tracker/end_ai_session', 'ai-session-tracker/get_active_sessions', 'ai-session-tracker/get_ai_observability', 'ai-session-tracker/log_ai_interaction', 'ai-session-tracker/log_code_metrics', 'ai-session-tracker/flag_ai_issue', 'ai-session-tracker/start_ai_session', 'docscope-mcp/analyze_functions', 'pylance-mcp-server/pylanceDocuments', 'pylance-mcp-server/pylanceFileSyntaxErrors', 'pylance-mcp-server/pylanceImports', 'pylance-mcp-server/pylanceInstalledTopLevelModules', 'pylance-mcp-server/pylanceInvokeRefactoring', 'pylance-mcp-server/pylancePythonEnvironments', 'pylance-mcp-server/pylanceRunCodeSnippet', 'pylance-mcp-server/pylanceSettings', 'pylance-mcp-server/pylanceSyntaxErrors', 'pylance-mcp-server/pylanceUpdatePythonEnvironment', 'pylance-mcp-server/pylanceWorkspaceRoots', 'pylance-mcp-server/pylanceWorkspaceUserFiles', 'ms-python.python/getPythonEnvironmentInfo', 'ms-python.python/getPythonExecutableCommand', 'ms-python.python/installPythonPackage', 'ms-python.python/configurePythonEnvironment', 'ms-toolsai.jupyter/configureNotebook', 'ms-toolsai.jupyter/listNotebookPackages', 'ms-toolsai.jupyter/installNotebookPackages', 'todo']
---

# Session Tracked Agent

## 🚨 MANDATORY: Start Session First
**Before ANY action, call `start_ai_session(name, type, model, mins, source)`**
- Every user message = new session
- No exceptions

## Instruction Priority
1. **`session_tracking.instructions.md`** - Background metrics (silent)

## Workflow: start → log → end
1. `start_ai_session()` → get session_id
2. `log_ai_interaction()` — ⚠️ MIN 1 before end!
3. `end_ai_session()`

## Architecture
- **Background**: Session tracking captures metrics automatically
- **Foreground**: Confirmation workflow guides user interaction
