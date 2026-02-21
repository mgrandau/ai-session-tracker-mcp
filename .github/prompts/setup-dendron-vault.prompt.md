---
description: "Initialize a Dendron vault in docs/journal/ with dendron.yml, VS Code settings, and .gitignore entries."
---

# Set Up Dendron Journal Vault

Initialize a Dendron vault in `docs/journal/` — git-tracked, accessible via the Dendron VS Code extension.

## 1. Create Vault Directory

Create `docs/journal/` if missing.

## 2. Vault Root Files

`docs/journal/root.md`:

```markdown
---
id: root
title: root
desc: "Project journal vault root"
updated: {{TIMESTAMP}}
created: {{TIMESTAMP}}
---
```

`docs/journal/root.schema.yml`:

```yaml
version: 1
imports: []
schemas:
  - id: root
    title: root
    parent: root
```

## 3. `dendron.yml` at Workspace Root (Single Config)

There is only one `dendron.yml` — at the workspace root. Do **not** create a vault-level `dendron.yml` inside `docs/journal/`. Do **not** use `selfContained: true` on the vault. All Dendron configuration lives in the root config.

Create or merge into existing `dendron.yml`. If vault `docs/journal` already listed, skip.

**Do not hardcode config.** Instead:

1. Read the existing root `dendron.yml` to understand the current structure.
2. Ensure `workspace.vaults` includes `fsPath: docs/journal` and `name: journal` (no `selfContained`).
3. Ensure all standard Dendron sections are present: `dev`, `commands`, `workspace` (journal, scratch, task, graph), `preview`, `publishing`.
4. Preserve any existing settings (e.g., additional vaults).
5. **Validate:** After writing, check `dendron.yml` for errors using the editor's YAML schema validation. Remove any properties flagged as "not allowed" by the Dendron schema. The file must have zero validation errors before proceeding.

## 4. VS Code Settings

Merge into `.vscode/settings.json` (preserve existing settings):

```json
{ "dendron.rootDir": "." }
```

## 5. `.gitignore`

Add if missing (do **not** ignore `docs/journal/`):

```
.dendron.*
seeds
```

## 6. Initial Daily Note

`docs/journal/daily.journal.{{YYYY}}.{{MM}}.{{DD}}.md` — local date/time for all values:

```markdown
---
id: {{GENERATE_UUID}}
title: "{{Month DD, YYYY}}"
desc: ""
updated: {{TIMESTAMP}}
created: {{TIMESTAMP}}
---

# Journal - {{Month DD, YYYY}}

First entry. Dendron vault initialized for project journaling.
```

## 7. Initialize Dendron Workspace

Run the VS Code command `dendron.initWS` to initialize the Dendron workspace with the vault configuration. This tells Dendron to read `dendron.yml` and register the vault.

If `dendron.initWS` is unavailable, instruct the user to run from the Command Palette:
`Ctrl+Shift+P` → **Dendron: Initialize Workspace**

## 8. Verify

- `docs/journal/` has `root.md` and `root.schema.yml`
- `dendron.yml` at workspace root references the vault
- `.vscode/settings.json` has `dendron.rootDir`
- `.gitignore` has `.dendron.*` and `seeds`
- Dendron tree view shows the journal vault
- Tell user to reload VS Code (`Developer: Reload Window`) if vault not visible
