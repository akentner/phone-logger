---
phase: 03-error-handling-robustness
plan: 02
subsystem: testing
tags: [fritz-callmonitor, parser, field-validation, logging, tdd]

# Dependency graph
requires:
  - phase: 03-error-handling-robustness
    provides: Phase context and CONTEXT.md with D-09 through D-13 decisions
provides:
  - MIN_FIELDS constant in fritz_callmonitor.py with per-event-type minimum field counts
  - Field count guard in _parse_line() before field access
  - WARNING logging with raw line on parse failure
  - DEBUG logging for unknown event types
  - TestFritzParserMinFields test class with 9 test cases
affects: [04-testing, fritz-callmonitor]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MIN_FIELDS dict keyed by CallEventType enum for per-event validation"
    - "TDD: write failing tests first, then implement to make them pass"
    - "Log at WARNING for structural errors (bad field counts), DEBUG for expected unknowns"

key-files:
  created: []
  modified:
    - src/adapters/input/fritz_callmonitor.py
    - tests/test_fritz_parser.py

key-decisions:
  - "MIN_FIELDS values: RING=5, CALL=6, CONNECT=5, DISCONNECT=4 (verified against existing test fixtures)"
  - "Unknown event type logs at DEBUG not WARNING to avoid alert noise from firmware updates"
  - "Parse failure log includes event type, expected count, actual count, and raw line for debugging"
  - "Removed unused pytest import from test_fritz_parser.py (Rule 1 auto-fix for Ruff F401)"

patterns-established:
  - "Validation guard inserted after event_type resolution, before any field access by index"
  - "Module-level constant dict for per-variant minimum requirements"

requirements-completed: [ERR-02]

# Metrics
duration: 8min
completed: 2026-04-14
---

# Phase 03 Plan 02: Fritz Parser MIN_FIELDS Validation Summary

**MIN_FIELDS dict with per-event field count validation added to Fritz!Box parser, rejecting malformed lines early with WARNING logs before field access**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-14T21:29:00Z
- **Completed:** 2026-04-14T21:37:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `MIN_FIELDS` constant mapping CallEventType to minimum required field counts (RING=5, CALL=6, CONNECT=5, DISCONNECT=4)
- Inserted validation guard in `_parse_line()` after event_type resolution, before any index-based field access
- Unknown event type now logs at DEBUG level (previously silent) for observability without noise
- Parse failures now log WARNING with event type, expected/actual counts, and raw line for debugging
- Added `TestFritzParserMinFields` class with 9 test cases covering all rejection/acceptance paths and logging behaviors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing tests for MIN_FIELDS validation** - `297ad07` (test)
2. **Task 2: Add MIN_FIELDS constant and validation guard** - `44b4768` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/adapters/input/fritz_callmonitor.py` - Added MIN_FIELDS constant and validation guard in _parse_line()
- `tests/test_fritz_parser.py` - Added TestFritzParserMinFields with 9 test cases, removed unused pytest import

## Decisions Made
- MIN_FIELDS values verified against existing test fixtures to confirm no regressions (RING fixture has 6 fields >= 5 minimum, CALL has 7 >= 6, CONNECT has 5 >= 5, DISCONNECT has 4 >= 4)
- Unknown event type logs at DEBUG (not WARNING) to avoid noise from Fritz!Box firmware updates or unusual network events
- Existing `if len(parts) < 4: return None` pre-check kept as-is — it guards parts[1] access before event_type resolution

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused pytest import causing Ruff F401 violation**
- **Found during:** Task 2 (ruff check verification step)
- **Issue:** `import pytest` was in the original test file but unused; our new test class didn't use it either; Ruff reported F401
- **Fix:** Removed the `import pytest` line from tests/test_fritz_parser.py
- **Files modified:** tests/test_fritz_parser.py
- **Verification:** `uv run ruff check` exits 0; all 210 tests still pass
- **Committed in:** 44b4768 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug - unused import causing lint failure)
**Impact on plan:** Trivial fix, no scope creep.

## Issues Encountered
None - implementation followed plan exactly. MIN_FIELDS values and insertion point were well-specified in CONTEXT.md.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Fritz parser is now defensively coded against malformed input
- Parse failures are observable via WARNING logs with raw line content
- All 210 tests pass (201 original + 9 new from this plan)
- Ready for 03-03-PLAN.md (next plan in phase 03)

---
*Phase: 03-error-handling-robustness*
*Completed: 2026-04-14*
