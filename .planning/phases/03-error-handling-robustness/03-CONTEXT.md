# Phase 3: Error Handling & Robustness - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Add differentiated error types and defensive validation throughout the pipeline:
- Resolver chain: distinguish NOT_FOUND vs. NETWORK_ERROR vs. RATE_LIMITED instead of swallowing all exceptions equally
- Fritz!Box parser: validate field count per event type before split, log raw message on failure
- MQTT adapter: log Disconnect/Reconnect events with connection reason and attempt counter

Not in scope: circuit breakers, retry logic, metrics endpoints, new adapter types.

</domain>

<decisions>
## Implementation Decisions

### ResolveError Exception Hierarchy (ERR-01)

- **D-01:** Define exception classes in `src/adapters/resolver/errors.py` — own module in the resolver package, cleanly importable from all concrete resolvers and the chain
- **D-02:** Hierarchy: `ResolverError(Exception)` → `NetworkError(ResolverError)`, `RateLimitError(ResolverError)`. NOT_FOUND stays as `None` return (no exception needed — it's the normal "no result" path)
- **D-03:** All resolvers (not only web scrapers) shall raise typed exceptions. Web scrapers raise `NetworkError`/`RateLimitError` on I/O failures; local resolvers (SQLite, JSON) raise `ResolverError` for structural/IO issues
- **D-04:** The chain's `resolve()` signature stays `Optional[ResolveResult]` — no change to public interface. Chain catches typed exceptions, logs with category, continues to next adapter
- **D-05:** Log format: `logger.warning("Adapter '%s' [NETWORK_ERROR] for '%s': %s", adapter.name, number, exc)` — category in brackets for grep-ability

### Chain Behavior on Errors (ERR-01)

- **D-06:** Flow stays unchanged: any exception → log with type → `continue` to next adapter. No short-circuiting on NetworkError or RateLimitError — all adapters are tried
- **D-07:** Only logging level change: `NetworkError`/`RateLimitError` → `logger.warning` (not `logger.exception` — no traceback noise for expected network failures). Unknown `ResolverError` → `logger.exception` (includes traceback)
- **D-08:** No counter/metrics in chain — metrics are v2-requirements (OBS-01/OBS-02), explicitly out of scope for this phase

### Fritz!Box Parser Validation (ERR-02)

- **D-09:** Add `MIN_FIELDS` dict mapping each `CallEventType` to minimum required field count:
  - `RING: 5` (date;RING;conn;caller;called)
  - `CALL: 6` (date;CALL;conn;ext;caller;called)
  - `CONNECT: 5` (date;CONNECT;conn;ext;number)
  - `DISCONNECT: 4` (date;DISCONNECT;conn;duration)
- **D-10:** Validation logic: after `event_type` is resolved, check `len(parts) < MIN_FIELDS[event_type]`. If too few: `logger.warning("Fritz parse error [%s]: need %d fields, got %d | raw: %s", event_type, min_needed, len(parts), line)` then `return None`
- **D-11:** Validation is "strict minimum" — optional trailing fields (e.g., SIP line in RING) remain tolerant via existing `if len(parts) > N` guards
- **D-12:** Unknown event type (not in EVENT_MAP): `logger.debug("Unknown Fritz event type '%s' | raw: %s", event_name, line)` — debug level to avoid noise from Fritz firmware updates adding new event types
- **D-13:** Validation added in `_parse_line()` static method, directly after `event_type` resolution and before any field access

### MQTT Reconnect Logging (ERR-03)

- **D-14:** Add session-based reconnect counter: `_reconnect_attempts: int = 0` on the adapter. Reset to 0 after each successful connection (in `_connect()` after `async with aiomqtt.Client()` succeeds)
- **D-15:** Four explicit log events:
  - `CONNECTED`: already present (`logger.info("MQTT connected to %s:%d ...")`) — no change
  - `DISCONNECTED`: new `logger.warning("MQTT disconnected: %s", reason)` — fired when `async with aiomqtt.Client()` block exits (normal or exception), before re-entering loop
  - `RECONNECTING`: new `logger.info("MQTT reconnecting in %ds (attempt %d)", self._reconnect_delay, self._reconnect_attempts)` — fired in `_run_loop` before `asyncio.sleep`
  - `RECONNECTED`: new `logger.info("MQTT reconnected after %d attempt(s)", self._reconnect_attempts)` — fired in `_connect()` after successful connection (after the existing connected log, or merged with it)
- **D-16:** Disconnect reason: log `str(exc)` as reason when available (exception message). For clean shutdowns (no exception, `_running == False`), reason = "graceful shutdown"
- **D-17:** Log level for DISCONNECTED: `logger.warning` — unexpected disconnect is noteworthy; graceful shutdown uses `logger.info`

### Claude's Discretion

- Whether to add a `__all__` to `errors.py`
- Exact exception message format for individual resolver implementations
- Whether `RECONNECTED` and `CONNECTED` are merged into one log line or kept separate
- Order of resolver exception wrapping (catch specific aiohttp/network exceptions, wrap in ResolverError subclass, or raise directly)

</decisions>

<specifics>
## Specific Ideas

- Log format with category in brackets (`[NETWORK_ERROR]`, `[RATE_LIMITED]`) is important — makes `grep`-based log analysis easy
- "Strict minimum" parser approach is the right balance: catches malformed Fritz!Box messages without breaking on new firmware adding optional fields

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core files to modify
- `src/adapters/resolver/chain.py` — exception handling in `resolve()` loop; add typed catches
- `src/adapters/input/fritz_callmonitor.py` — `_parse_line()` static method; add MIN_FIELDS validation
- `src/adapters/mqtt.py` — `_run_loop()` and `_connect()` methods; add counter and log events

### New file to create
- `src/adapters/resolver/errors.py` — ResolverError exception hierarchy

### Resolver implementations (all need typed exception raising)
- `src/adapters/resolver/tellows.py`
- `src/adapters/resolver/dastelefon.py`
- `src/adapters/resolver/klartelbuch.py`
- `src/adapters/resolver/sqlite_db.py`
- `src/adapters/resolver/json_file.py`
- `src/adapters/resolver/msn.py`

### Requirements
- `.planning/REQUIREMENTS.md` §Fehlerbehandlung — ERR-01, ERR-02, ERR-03 (exact acceptance criteria)

### Constraints (from Phase 1 context)
- 201 tests must remain green
- No breaking changes to MQTT topic format, webhook payload, API schemas, or config structure
- `Optional[ResolveResult]` return type on `chain.resolve()` must not change

</canonical_refs>

<code_context>
## Existing Code Insights

### Resolver Chain (src/adapters/resolver/chain.py)
- Currently: single `except Exception: logger.exception(...); continue` in `resolve()` loop
- Change point: replace with three except clauses (NetworkError, RateLimitError, base ResolverError/Exception)
- No return type change needed

### Fritz!Box Parser (src/adapters/input/fritz_callmonitor.py)
- `_parse_line()` is a `@staticmethod` — add `MIN_FIELDS` dict as module-level constant
- Existing global check `if len(parts) < 4: return None` can stay or be folded into new per-type check
- Current per-field guards (`parts[N] if len(parts) > N else ""`) stay for optional fields

### MQTT Adapter (src/adapters/mqtt.py)
- `_run_loop()`: add counter increment, RECONNECTING log before `asyncio.sleep`, reset after success
- `_connect()`: add DISCONNECTED log before method exits, RECONNECTED log after successful connect
- Instance variable `_reconnect_attempts: int = 0` added to `__init__`

### Resolver implementations location
- Run `ls src/adapters/resolver/` to confirm exact filenames before planning

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. v2 requirements (ROB-01 circuit breaker, OBS-01/OBS-02 metrics) explicitly remain in REQUIREMENTS.md v2 section.

</deferred>

---

*Phase: 03-error-handling-robustness*
*Context gathered: 2026-04-14*
