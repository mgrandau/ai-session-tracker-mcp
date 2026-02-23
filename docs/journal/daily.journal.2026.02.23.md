---
id: h7azgwrtnnqy8m7k1xepxmo
title: Journal - February 23, 2026
desc: ''
updated: 1740347000000
created: 1740347000000
traitIds:
  - journalNote
---

# Journal - February 23, 2026

## Summary

Diagnosed and fixed Issue #18 — dashboard was displaying a misleading session count that made it look like 2 sessions were stuck open when all sessions were actually completed.

## Work Completed

- **Issue #18 — Root cause analysis and fix**: The dashboard showed `Sessions: 572 (570 completed)`, implying 2 sessions were still active. Investigation revealed this was a labeling bug caused by mismatched counting logic between `total_sessions` and `completed_sessions`.

## Root Cause

In `presenters.py` `_build_roi()`:
```python
total_sessions=len(sessions),                              # 572 — ALL sessions
completed_sessions=roi["time_metrics"]["completed_sessions"],  # 570 — ROI-filtered only
```

`total_sessions` counted every session, but `completed_sessions` came from `calculate_roi_metrics()` which first runs `filter_productive_sessions()` — excluding `task_type: "human_review"` sessions before counting. The 2 "missing" sessions were:
- `gitlab_authentication_issue_20260107_161629` (human_review, completed)
- `explain_git_push_behavior_20260107_165455` (human_review, completed)

Both fully completed — just excluded from ROI calculations by design.

## Fix

Changed `presenters.py` to count completed sessions from the full session set instead of the ROI-filtered subset:
```python
completed_sessions=sum(
    1 for s in sessions.values() if s.get("status") == "completed"
),
```

This separates the display count (all completed sessions) from the ROI math (only productive sessions). The ROI calculations themselves remain unchanged.

## Decision Log

- **Count completed from all sessions, not ROI-filtered**: The `completed_sessions` display metric should reflect actual session status, not ROI inclusion. ROI filtering is a calculation concern, not a status concern. Users seeing `572 (570 completed)` will naturally assume 2 are still open — that's confusing and wrong.

## Commits

- `73c895d` Add evidence files for issue #18 - stale open session state

## Notes

The empty data query (`[]`) reported in the original issue description may be a separate bug — possibly a working directory or code path issue where the query doesn't find the sessions file. Not investigated further today.
