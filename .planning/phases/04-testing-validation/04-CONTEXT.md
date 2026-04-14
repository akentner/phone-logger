# Phase 4: Testing & Validation - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Close 4 test coverage gaps — only new test code is added, no production code changes.

Gaps to close:
- TEST-01: 3 FastAPI routes tested via real TestClient (GET /api/calls, GET /api/pbx/status, POST /api/contacts)
- TEST-02: MQTT reconnect scenarios (broker restart, publish-while-offline, connection drop/recovery)
- TEST-03: Call aggregation edge cases (DISCONNECT without RING, CONNECT without DISCONNECT, orphan calls)
- TEST-04: Fritz!Box parser edge cases (missing fields, out-of-order events, duplicate events) — both parser-level and adapter-level

Not in scope: E2E tests with real MQTT broker or Fritz!Box, new production code, circuit breakers, metrics.

</domain>

<decisions>
## Implementation Decisions

### Fritz!Box Parser Tests — TEST-04

**Parser-level (stateless, in `test_fritz_parser.py`):**
- **D-01:** Duplicate test: same raw line passed to `_parse_line()` twice → both calls return valid equivalent events. Verifies parser is idempotent (no hidden state).
- **D-02:** Out-of-order test: DISCONNECT line parsed independently before any RING line → returns a valid event. Confirms parser makes no ordering assumptions.

**Adapter-level integration (in `test_fritz_parser.py`):**
- **D-03:** Wire up `FritzCallmonitorAdapter` with a mock callback, feed raw line sequences. Tests verify what events the callback receives. No DB, no pipeline, no PBX FSM.
- **D-04:** Duplicate RING sequence: two RING lines with the same `connection_id` fed into the adapter → callback invoked twice with valid events. Parser does not deduplicate — that is PBX FSM's responsibility.
- **D-05:** CONNECT without prior RING sequence: CONNECT line for unknown `connection_id` fed into adapter → callback receives a valid CONNECT event. No crash, no silent drop.

### Claude's Discretion

- TEST-01: How to bootstrap FastAPI app for TestClient (real temp DB vs dependency override, conftest.py vs local fixture)
- TEST-02: Whether "publish-while-offline" tests verify drop behavior (current: `_client is None` → log + return) or something more, and exact scenario breakdown
- TEST-03: Whether edge case tests extend `test_call_aggregation.py` or go into a new file; exact assertions for DISCONNECT-without-RING (adapter logs warning, no crash, no DB record created)
- Exact test helper signatures and class grouping within files

</decisions>

<specifics>
## Specific Ideas

- "Out-of-order" and "duplicate" at parser level are stateless concepts — the parser has no memory. Tests confirm this property explicitly.
- Adapter-level integration scope was chosen (not pipeline-level): simpler setup, no DB, mock callback only. This is consistent with how `test_mqtt_output.py` tests the MQTT adapter without a real broker.
- The PBX FSM already covers state-machine-level duplicate/out-of-order behavior (`test_pbx.py`) — do not re-test FSM logic in TEST-04.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements (acceptance criteria)
- `.planning/REQUIREMENTS.md` §Tests — TEST-01, TEST-02, TEST-03, TEST-04 (exact acceptance criteria for each gap)

### Existing test patterns (read before writing new tests)
- `tests/test_fritz_parser.py` — Existing Fritz parser tests; new tests extend this file
- `tests/test_call_aggregation.py` — Existing aggregation tests with `test_db` fixture; edge case tests follow this pattern
- `tests/test_mqtt_output.py` — Existing MQTT adapter tests; MQTT reconnect tests follow this file's fake-client injection pattern
- `tests/test_api.py` — Current state (only model validation, no TestClient); TestClient tests extend this file
- `tests/conftest.py` — Current shared fixtures

### Production code under test
- `src/adapters/input/fritz_callmonitor.py` — `FritzCallmonitorAdapter._parse_line()` (stateless parser) and adapter start/callback wiring
- `src/adapters/mqtt.py` — `_client is None` drop behavior in `handle()` and `handle_line_state_change()`, reconnect loop
- `src/adapters/output/call_log.py` — Edge case log messages at lines 157-158 and 210-211 (CONNECT/DISCONNECT for unknown connection_id)
- `src/api/routes/` — FastAPI route handlers for the 3 endpoints under test
- `src/main.py` — App factory / startup for TestClient fixture

### Constraints
- `.planning/STATE.md` — All 219 tests must remain green; no breaking changes to MQTT topics, webhooks, API schemas, config structure
- `.planning/PROJECT.md` §Out of Scope — No E2E tests with real MQTT broker or Fritz!Box

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `test_db` fixture in `test_call_aggregation.py` — async temp DB fixture, reusable for TestClient app setup
- `_inject_client()` pattern in `test_mqtt_output.py` — replaces `adapter._client` with a fake; same approach for publish-while-offline tests
- `_make_config()` / `_make_event()` builder helpers in multiple test files — follow this naming convention for new helpers

### Established Patterns
- Class-based test organization (`class TestFritzParser`, `class TestMqttReconnect`) — group new tests under appropriate classes
- `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorators needed
- `AsyncMock` for coroutines, `MagicMock` for sync, fake subclasses for adapters
- Adapter-level testing: inject fake client / mock callback, verify what is published / forwarded

### Integration Points
- Fritz adapter: `start(callback)` accepts `Callable[[CallEvent], Coroutine]` — use `AsyncMock` as callback for adapter-level tests
- FastAPI app: wired in `src/main.py`; `TestClient` or `AsyncClient` (httpx) for route tests — check how `app` is constructed before choosing fixture strategy
- Call log adapter: `handle(event, result, *, line_state=None)` — drive directly with fabricated events for edge case tests

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. v2 requirements (ROB-01 circuit breaker, OBS-01/OBS-02 metrics) remain in REQUIREMENTS.md v2 section.

</deferred>

---

*Phase: 04-testing-validation*
*Context gathered: 2026-04-15*
