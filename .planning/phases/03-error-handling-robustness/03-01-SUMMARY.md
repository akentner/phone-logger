---
phase: 03-error-handling-robustness
plan: 01
subsystem: resolver
tags: [exception-hierarchy, error-handling, aiohttp, aiosqlite, resolver-chain]

requires:
  - phase: 02-code-quality
    provides: clean codebase, Ruff-validated resolver adapters

provides:
  - Typed exception hierarchy (ResolverError, NetworkError, RateLimitError) in errors.py
  - Differentiated log levels in ResolverChain.resolve() (WARNING for network/rate-limit, EXCEPTION for structural)
  - Typed raises in all three web scraper adapters (tellows, dastelefon, klartelbuch)
  - Wrapped SQLite calls in SqliteResolver with ResolverError on aiosqlite.Error

affects: [04-testing]

tech-stack:
  added: []
  patterns:
    - "Typed exception hierarchy: resolver subclasses raise NetworkError/RateLimitError/ResolverError; chain catches and routes to correct log level"
    - "raise ... from e: all typed raises preserve exception chain for debugging"

key-files:
  created:
    - src/adapters/resolver/errors.py
  modified:
    - src/adapters/resolver/chain.py
    - src/adapters/resolver/tellows.py
    - src/adapters/resolver/dastelefon.py
    - src/adapters/resolver/klartelbuch.py
    - src/adapters/resolver/sqlite_db.py
    - tests/test_resolver_chain.py

key-decisions:
  - "NetworkError and RateLimitError logged at WARNING (no traceback) — expected transient conditions"
  - "ResolverError and bare Exception logged with logger.exception() (includes traceback) — structural failures needing investigation"
  - "HTTP 429 check placed BEFORE the generic non-200 guard so it raises instead of silently returning None"
  - "sqlite_db.py wraps both get_contact and update_last_seen independently — each can fail separately"

patterns-established:
  - "Resolver error classification: NetworkError=transient/expected, RateLimitError=backoff signal, ResolverError=structural/IO failure"
  - "Remove self.logger.error() from catch blocks that now raise — chain is responsible for logging"

requirements-completed: [ERR-01]

duration: 8min
completed: 2026-04-14
---

# Phase 03 Plan 01: Resolver Typed Exception Hierarchy Summary

**Typed exception hierarchy (NetworkError, RateLimitError, ResolverError) making resolver failures distinguishable in logs — network errors log as WARNING, structural errors log with traceback**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-14T21:30:00Z
- **Completed:** 2026-04-14T21:38:00Z
- **Tasks:** 2
- **Files modified:** 6 (+ 1 created)

## Accomplishments

- Created `src/adapters/resolver/errors.py` with 3-class exception hierarchy exported via `__all__`
- Refactored `ResolverChain.resolve()` from single `except Exception` to 4 typed clauses with differentiated log levels
- Updated tellows, dastelefon, klartelbuch scrapers to raise `NetworkError` on `aiohttp.ClientError` and `RateLimitError` on HTTP 429
- Wrapped SQLite operations in `SqliteResolver` with `ResolverError` on `aiosqlite.Error`
- Added 4 new tests in `TestResolverChainErrorHandling` verifying chain continues and logs correctly for each error type
- Full test suite: 205 tests passed (201 existing + 4 new), zero regressions

## Task Commits

1. **Task 1: Create errors.py and refactor chain.py with typed exception handling** - `70f1471` (feat)
2. **Task 2: Add typed raises to web scraper and SQLite resolver implementations** - `8bd2c0f` (feat)

## Files Created/Modified

- `src/adapters/resolver/errors.py` — New: 3-class exception hierarchy with `__all__`
- `src/adapters/resolver/chain.py` — 4-clause exception handling in `resolve()` loop
- `src/adapters/resolver/tellows.py` — raises NetworkError on ClientError, RateLimitError on HTTP 429
- `src/adapters/resolver/dastelefon.py` — same pattern as tellows
- `src/adapters/resolver/klartelbuch.py` — same pattern as tellows
- `src/adapters/resolver/sqlite_db.py` — wraps get_contact and update_last_seen with ResolverError
- `tests/test_resolver_chain.py` — added ErroringResolver mock class and TestResolverChainErrorHandling

## Decisions Made

- NetworkError/RateLimitError at WARNING level (no traceback): these are expected transient conditions operators don't need to investigate
- ResolverError/Exception at ERROR level with traceback: these indicate structural failures worth alerting on
- HTTP 429 check inserted before the generic non-200 guard to ensure rate limit is classified correctly
- Removed `self.logger.error()` from scraper catch blocks — the chain is now responsible for logging exceptions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 03 Plan 02 (Fritz!Box parser field count validation) can proceed independently
- Error classification pattern established and tested — future resolvers should follow the same `raise NetworkError/RateLimitError/ResolverError` convention

---
*Phase: 03-error-handling-robustness*
*Completed: 2026-04-14*
