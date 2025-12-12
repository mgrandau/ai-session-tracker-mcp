# Architecture Documentation

Generate AI-readable architectural contract for `{{file}}` directory.

## Rules
- Output artifacts only—no chain-of-thought
- Tables/lists/signatures > prose
- **Minimize tokens**: abbreviate, omit obvious, use compact notation
- Note gaps inline
- Preserve API names/casing (ABI-frozen)

## Output: README.md in dir({{file}})

### 1. Component Overview
- **Classification**: name, type (package|module|service|library), responsibility
- **Boundaries**: context, public_surface[]
- **Patterns**: architecture_patterns[]
- **Tech**: language, runtime, stack[]
- **Entry points**: main funcs/classes
- **State**: stateless|stateful (where stored)
- **Decisions**: key choices, risks[], owners[]

### 2. Code Layout
Tree w/ 1-line role per file (code fence)

### 3. Public Surface (⚠️ DO NOT MODIFY w/o approval)
- Classes/funcs/types w/ sigs + stability (🔒frozen, ⚠️internal)
- Change impact: what breaks if modified
- Data contracts: inputs[], outputs[]

### 4. Dependencies
- depends_on[], required_by[], interfaces[]
- IO: HTTP|gRPC|CLI|queue|fs|db

### 5. Invariants & Errors (⚠️ MUST PRESERVE)
- Invariants w/ thresholds
- Verification: test commands
- Constraints: perf[], security[], concurrency
- Side effects: disk/network/global state
- Errors: types + when raised

### 6. Usage
- Minimal snippets (setup only)
- Config: ENV vars, files, defaults
- Testing: how to run tests
- Pitfalls + fixes

### 7. AI-Accessibility Map (⚠️ CRITICAL)
| Task | Target | Guards | Change Impact |
|------|--------|--------|---------------|

### 8. Mermaid (optional)
- flowchart: boundaries + external deps
- classDiagram: key abstractions
- **Use `%%{init: {'theme': 'neutral'}}%%`** for dark/light mode compatibility

## Derivation
1. Resolve dir({{file}})
2. Walk depth=2, skip .gitignore
3. Build tree, assign roles
4. Mark APIs: 🔒frozen, ⚠️internal
5. Extract invariants + side effects
6. Build AI map: tasks → locations + guards
7. Write README.md (safe overwrite: create .new, then move)
