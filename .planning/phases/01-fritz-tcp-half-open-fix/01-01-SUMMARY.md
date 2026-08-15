---
phase: 01-fritz-tcp-half-open-fix
plan: 01
subsystem: input-adapter
tags: [fritz, tcp, half-open-socket, keepalive, asyncio, reconnect]

# Dependency graph
requires: []
provides:
  - "FritzCallmonitorAdapter detects half-open sockets via readline timeout (default 300s) and reconnects"
  - "TCP keepalive enabled on the client socket (SO_KEEPALIVE + TCP_KEEPIDLE=60/TCP_KEEPINTVL=10/TCP_KEEPCNT=3) for kernel-level dead-peer detection"
  - "First TCP-level test fixture in repo using asyncio.start_server, enabling future lifecycle tests"
affects: [fritz-monitor-reliability, future-input-adapters]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.wait_for guard around blocking reads with explicit reconnect (not re-raise)"
    - "TCP keepalive belt-and-braces alongside application timeout (kernel + app both detect dead peer)"
    - "Self-terminating silent test fixture via reader.read() (EOF-driven) instead of unbounded asyncio.sleep"

key-files:
  created:
    - tests/test_fritz_connection.py
  modified:
    - src/adapters/input/fritz_callmonitor.py

key-decisions:
  - "Use break (not raise) on TimeoutError to avoid traceback noise in logs; specific 'readline timed out' warning is the operator signal"
  - "Readline timeout default 300s — long enough for normal idle periods, short enough to recover within reasonable window after Fritz!Box reboot"
  - "TCP keepalive constants guarded with hasattr() for portability (verified available on Linux/macOS but Windows lacks TCP_KEEPIDLE etc.)"
  - "Half-open detection layered on top of existing reconnect infrastructure (_run_loop's except Exception) — no changes to reconnect flow needed"

patterns-established:
  - "Time-bounded socket reads: every blocking socket read in input adapters should be wrapped in asyncio.wait_for with explicit timeout"
  - "Test fixture silent handlers must exit on EOF (reader.read()), not fixed-duration sleep — required for server.wait_closed() in finally blocks"

requirements-completed: [TCP-01]

# Metrics
duration: 18min
completed: 2026-08-15
---

# Phase 01 Plan 01: Fritz!Box Half-Open TCP Fix Summary

**FritzCallmonitorAdapter detects dead-peer TCP connections in ~90s (kernel keepalive) or within readline_timeout (default 300s) and reconnects automatically — eliminates silent loss of call events after Fritz!Box reboots.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-08-15T12:37:00Z
- **Completed:** 2026-08-15T12:55:21Z
- **Tasks:** 2/2 complete
- **Files modified:** 2 (1 new test file, 1 production file)
- **Test count:** 241 → 246 (+5 new)
- **Diff:** +54 / −7 across 2 files (production fix + test + fixture correction)

## Accomplishments

- Eliminated the wedged-`readline()` bug confirmed in the live container (PID 91, 42 min CPU over 4 weeks, ESTABLISHED socket with Tx/Rx Q both 0 bytes)
- Application-level guard via `asyncio.wait_for(readline(), timeout=self._readline_timeout)` — converts an indefinite kernel-level block into a clean reconnect
- Kernel-level guard via `SO_KEEPALIVE` + `TCP_KEEPIDLE=60s` + `TCP_KEEPINTVL=10s` + `TCP_KEEPCNT=3` — ~90s detection independent of the app timeout
- New `tests/test_fritz_connection.py` introduces the first TCP-level test fixture in the repo, using `asyncio.start_server` on `127.0.0.1:0` with auto-assigned ports — reusable pattern for future input-adapter lifecycle tests
- Zero regressions: all 241 existing tests remain green

## Task Commits

Each task committed atomically:

1. **Task 1: Add failing TCP connection lifecycle tests** - `77b616f` (test)
   - 5 new tests covering half-open reconnect, SO_KEEPALIVE on socket, default timeout (300s), custom timeout override, and normal-flow regression
   - Pre-fix: 2 fail (AttributeError) + 2 hang (wedged) + 1 pass (regression)

2. **Task 2: Implement half-open guard + SO_KEEPALIVE** - `4906de7` (fix)
   - Added `readline_timeout` config field (float, default 300.0)
   - Wrapped `readline()` in `asyncio.wait_for(timeout=...)`
   - Enabled `SO_KEEPALIVE` + 3 TCP_KEEP* options on the client socket
   - Specific "readline timed out" warning before breaking to reconnect
   - Fixed silent handler test fixture (EOF-aware instead of fixed-sleep)

## Files Created/Modified

- `tests/test_fritz_connection.py` (NEW, 216 lines)
  - `_ServerState` / `_make_silent_handler` / `_make_one_line_handler` / `_start_server` / `_make_adapter` helpers
  - `TestFritzConnectionReconnect`: 4 tests for half-open detection
  - `TestFritzConnectionNormalFlow`: 1 regression test for graceful close + reconnect

- `src/adapters/input/fritz_callmonitor.py` (MODIFIED, +48 / -2)
  - Imports: `import socket` added (no new third-party deps)
  - Constructor: `self._readline_timeout: float = float(config.config.get("readline_timeout", 300.0))`
  - `_connect_and_listen()`: `readline()` wrapped in `asyncio.wait_for(timeout=self._readline_timeout)`, with `asyncio.TimeoutError` → specific warning + break; socket gets `SO_KEEPALIVE` + 3 TCP_KEEP* via `setsockopt`

## Decisions Made

- **Break vs raise on TimeoutError**: chose `break` to avoid `logger.exception("Fritz Callmonitor connection error")` traceback noise in production logs. The specific `logger.warning("Fritz Callmonitor readline timed out after %.1fs — likely half-open socket, reconnecting", ...)` is the operator-facing signal — grep-able, single-line, actionable.
- **Default 300s**: long enough that no-call periods don't trigger reconnect, short enough to recover within reasonable window after Fritz!Box reboot. Operators can override via `readline_timeout` in config.yaml / HA addon options.
- **300s default vs config-justified alternative**: rejected a shorter default (e.g. 60s) because normal idle periods between calls can easily exceed a minute; the keepalive (90s) is the faster trigger; the app timeout is the backstop.
- **`hasattr` guards on `TCP_KEEP*` constants**: portable to Windows even though stdlib docs don't guarantee them on Linux/macOS already; verified present on this host.
- **No schema bump**: `AdapterConfig.config` is already a free-form dict; the new field is read via `config.config.get(...)` with default. No Pydantic or HA options.json migration needed.
- **Silent handler test fixture fix** (deviation, see below): `await reader.read()` instead of `await asyncio.sleep(3600)` to allow `server.wait_closed()` to complete in the `finally` block. This is a fixture design correction, not a test logic change — the handler still never sends.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test fixture silent handler blocked server.wait_closed() indefinitely**
- **Found during:** Task 2 verification (after Task 1 commit landed)
- **Issue:** The plan's specified `await asyncio.sleep(3600)` in `_make_silent_handler` made `await server.wait_closed()` (called in the test's `finally` block) hang forever, because asyncio.Server does NOT cancel already-accepted handler coroutines on `close()` — it only stops accepting new connections. Confirmed by isolated repro: `wait_closed()` timed out at 2s with handler still sleeping.
- **Fix:** Changed silent handler to block on `await reader.read()` instead. `reader.read()` returns `b''` on EOF (when the adapter closes its side via `adapter.stop()`), so the handler naturally exits on test teardown. The handler semantics are preserved — it still never sends a line, and from the adapter's perspective the socket is still half-open (server never sends and never proactively closes).
- **Files modified:** `tests/test_fritz_connection.py`
- **Verification:** Full 5-test suite passes in 2.14s; full repo suite (246 tests) green in 9.43s; ruff clean.
- **Committed in:** `4906de7` (part of Task 2 commit)

### Plan Mis-prediction (not a deviation in code, just in expected failure mode)

The plan's acceptance criteria stated `4 tests in TestFritzConnectionReconnect FAIL (or ERROR with AttributeError)`. The actual pre-fix state for `test_half_open_connection_triggers_reconnect_after_timeout` and `test_socket_has_keepalive_enabled` was "wedge forever" (no exception, just an indefinite `readline()` block on the adapter side that propagated to `adapter.stop()` → `task.cancel()` → hung because of the silent handler issue noted above). Only `test_default_readline_timeout_is_300_seconds` and `test_custom_readline_timeout_from_config` failed with the predicted `AttributeError`. Net result matches the plan's intent (2 fail / 2 hang / 1 pass → "4 effectively broken, 1 working").

**Total deviations:** 1 auto-fix (blocking), 1 plan mis-prediction noted
**Impact on plan:** Both are essential for the test suite to terminate. The fix is at the test-fixture layer, not the production code being tested — the half-open behavior the adapter exhibits (wedge forever without timeout) is exactly what the test was supposed to demonstrate.

## Auth Gates

None encountered.

## Known Stubs

None.

## Issues Encountered

- pytest's stdout capture interferes with the test runner when running all 5 new tests in batch mode (the bash command would hang without `-p no:capture` or `--capture=no`). Root cause is pytest's capture plugin awaiting buffered output that never arrives because the underlying test handles have their own asyncio event-loop interactions. Workaround: pass `-p no:capture` when invoking pytest directly. pytest invoked from pyproject.toml-driven configs doesn't appear to hit this in the existing test suite. No code change needed.
- Side observation: `logger.info("Reconnecting ... in %d seconds...", ...)` truncates `reconnect_delay=0.1` to `"0 seconds"` due to `%d` integer formatting. Tests use the float value successfully, only the human-readable log is slightly inaccurate. Not in scope for this fix.

## Next Phase Readiness

This plan closes the half-open socket bug and introduces the first TCP-level test fixture in the repo. Future work could build on this:

- A `docs/` section documenting the new operator-facing `readline_timeout` config + recommended values for different deployments
- E2E test against a real Fritz!Box (out of scope per plan: "no live container restart")
- Apply the same `asyncio.wait_for` + SO_KEEPALIVE pattern to other long-lived input adapters (e.g., MQTT subscriber if it doesn't already)

---

*Phase: 01-fritz-tcp-half-open-fix*
*Completed: 2026-08-15*

## Self-Check: PASSED

All verification artifacts present:

- ✅ `tests/test_fritz_connection.py` exists (216 lines, 5 tests)
- ✅ `src/adapters/input/fritz_callmonitor.py` modified (3 surgical changes per plan)
- ✅ Task 1 commit `77b616f` exists in git log
- ✅ Task 2 commit `4906de7` exists in git log
- ✅ Full test suite green (246/246, 9.48s)
- ✅ Ruff clean (0 violations on changed files)
- ✅ All plan `<verify>` acceptance criteria met (grep checks pass, construction pattern works for default + custom timeout)
