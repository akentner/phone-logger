---
phase: 03-error-handling-robustness
plan: "03"
subsystem: mqtt-adapter
tags: [mqtt, reconnect, logging, observability]
dependency_graph:
  requires: []
  provides: [mqtt-reconnect-counter, mqtt-reconnect-logging]
  affects: [src/adapters/mqtt.py]
tech_stack:
  added: []
  patterns: [reconnect-counter, structured-logging]
key_files:
  created: []
  modified:
    - src/adapters/mqtt.py
    - tests/test_mqtt_output.py
decisions:
  - "Exception-path DISCONNECTED log placed in _run_loop (has exc context), graceful-path in _connect (clean exit)"
  - "RECONNECTED log conditional on _reconnect_attempts > 0 to avoid noise on first connect"
  - "Counter reset to 0 placed in _connect immediately after async with enters, before existing CONNECTED log"
metrics:
  duration: "3 min"
  completed_date: "2026-04-14"
  tasks_completed: 2
  files_modified: 2
---

# Phase 03 Plan 03: MQTT Reconnect Counter and Log Events Summary

## One-liner

MQTT adapter gains `_reconnect_attempts` counter with 4 structured log events: DISCONNECTED (warning on exception), RECONNECTING (info before sleep), RECONNECTED (info after recovery), and graceful shutdown (info on clean exit).

## What Was Built

Added operational observability to the MQTT adapter's reconnection loop. Operators can now see:

- `MQTT disconnected: <reason>` at WARNING when broker drops unexpectedly
- `MQTT reconnecting in 10s (attempt 3)` at INFO before each sleep
- `MQTT reconnected after 3 attempt(s)` at INFO after successful reconnect
- `MQTT disconnected: graceful shutdown` at INFO when adapter stops cleanly

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add failing tests for reconnect counter and log events | c592c22 | tests/test_mqtt_output.py |
| 2 | Add _reconnect_attempts counter and 4 log events to mqtt.py | 5eb0671 | src/adapters/mqtt.py, tests/test_mqtt_output.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing Ruff violations in tests/test_mqtt_output.py**
- **Found during:** Task 2 (ruff check step)
- **Issue:** 5 pre-existing ruff violations: unused `asyncio` import, unused `MsnConfig` import, unused `DeviceInfo` import, unused `birth_topics` variable, unused `original_connect` variable — all in existing test classes, none introduced by this plan
- **Fix:** Removed unused imports and dead variable assignments from `TestBirthAndLWT.test_start_publishes_online`
- **Files modified:** tests/test_mqtt_output.py
- **Commit:** 5eb0671 (included in Task 2 commit)

## Known Stubs

None.

## Self-Check

Files modified exist:
- src/adapters/mqtt.py — modified with _reconnect_attempts counter and 4 log events
- tests/test_mqtt_output.py — modified with TestMqttReconnectLogging class

Commits exist: c592c22, 5eb0671

## Self-Check: PASSED
