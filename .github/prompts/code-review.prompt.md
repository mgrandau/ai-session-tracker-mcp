# Code Review

Expert code review of `{{file}}` for maintainability, performance, testability, best practices.

## Analysis Areas

### Code Quality
- Naming, formatting, comments, business clarity
- Smells: long methods, deep nesting, duplication, magic numbers
- Error handling, param validation, performance
- Anti-patterns (e.g., C# #region)

### Testability
- DI opportunities, static deps, global state
- SOLID adherence, separation of concerns
- Cyclomatic complexity, test seams

### Documentation
- Public API docs completeness
- Param/return descriptions w/ ranges/units
- Exception docs (direct + propagated)

## Priority Framework
- **P1**: Security, data integrity, severe perf
- **P2**: Testability barriers, maintainability, error gaps
- **P3**: Organization, naming, duplication
- **P4**: Docs, formatting, minor refactoring

## Deliverables

### 1. Summary
- Quality score (1-10) w/ justification
- Critical issues count
- Testability: Poor/Fair/Good/Excellent
- Doc completeness (%)

### 2. Findings (P1→P4)
Each finding:
- Location (file:class:method:lines)
- Category, current state, risk
- Recommendation w/ code example
- Effort: Low/Med/High

**Minimum**: 5-15 findings across P1-P4

### 3. Metrics
- Cyclomatic complexity
- Error handling gaps
- Doc coverage (%)
- Testability score

### 4. Testability Roadmap
- **Short-term (Low)**: Quick wins
- **Medium-term (Mod)**: Refactoring
- **Long-term (High)**: Architecture

### 5. Priority Matrix
| Priority | Category | Recommendation | Impact | Effort | ROI |
|----------|----------|----------------|--------|--------|-----|

Impact: High (user/stability) | Med (dev exp) | Low (aesthetics)
Effort: Low (<2h) | Med (2-8h) | High (>8h)
ROI: ⭐⭐⭐ | ⭐⭐ | ⭐
