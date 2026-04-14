# Phase 3: Error Handling & Robustness - Research

**Researched:** 2026-04-14
**Domain:** Python exception hierarchies, aiohttp error types, asyncio reconnect patterns, Fritz!Box TCP parsing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**ResolveError Exception Hierarchy (ERR-01)**
- D-01: Define exception classes in `src/adapters/resolver/errors.py` — own module in the resolver package
- D-02: Hierarchy: `ResolverError(Exception)` → `NetworkError(ResolverError)`, `RateLimitError(ResolverError)`. NOT_FOUND stays as `None` return (no exception needed)
- D-03: All resolvers (not only web scrapers) shall raise typed exceptions. Web scrapers raise `NetworkError`/`RateLimitError` on I/O failures; local resolvers (SQLite, JSON) raise `ResolverError` for structural/IO issues
- D-04: The chain's `resolve()` signature stays `Optional[ResolveResult]` — no change to public interface
- D-05: Log format: `logger.warning("Adapter '%s' [NETWORK_ERROR] for '%s': %s", adapter.name, number, exc)` — category in brackets for grep-ability

**Chain Behavior on Errors (ERR-01)**
- D-06: Flow stays unchanged: any exception → log with type → `continue`. No short-circuiting on NetworkError or RateLimitError — all adapters are tried
- D-07: Logging level: `NetworkError`/`RateLimitError` → `logger.warning` (no traceback). Unknown `ResolverError` → `logger.exception` (includes traceback)
- D-08: No counter/metrics — explicitly out of scope

**Fritz!Box Parser Validation (ERR-02)**
- D-09: Add `MIN_FIELDS` dict: `RING: 5`, `CALL: 6`, `CONNECT: 5`, `DISCONNECT: 4`
- D-10: Validation logic after `event_type` resolution: `if len(parts) < MIN_FIELDS[event_type]` → log warning with raw line, `return None`
- D-11: "Strict minimum" — optional trailing fields remain tolerant via existing `if len(parts) > N` guards
- D-12: Unknown event type → `logger.debug` (not warning, to avoid noise from new firmware)
- D-13: Validation added in `_parse_line()` static method, after `event_type` resolution and before any field access

**MQTT Reconnect Logging (ERR-03)**
- D-14: Session-based counter: `_reconnect_attempts: int = 0` on adapter, reset to 0 after each successful connection
- D-15: Four explicit log events: CONNECTED (unchanged), DISCONNECTED (new warning), RECONNECTING (new info), RECONNECTED (new info after success)
- D-16: Disconnect reason: `str(exc)` when exception available; "graceful shutdown" when `_running == False`
- D-17: DISCONNECTED → `logger.warning`; graceful shutdown → `logger.info`

### Claude's Discretion
- Whether to add a `__all__` to `errors.py`
- Exact exception message format for individual resolver implementations
- Whether `RECONNECTED` and `CONNECTED` are merged into one log line or kept separate
- Order of resolver exception wrapping (catch specific aiohttp/network exceptions, wrap in ResolverError subclass, or raise directly)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. v2 requirements (ROB-01 circuit breaker, OBS-01/OBS-02 metrics) remain in REQUIREMENTS.md v2 section.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ERR-01 | Resolver-Chain distinguishes NOT_FOUND / NETWORK_ERROR / RATE_LIMITED instead of exception swallowing | Exception hierarchy design in `errors.py`, chain catch-clause refactor, per-resolver raise patterns |
| ERR-02 | Fritz!Box parser validates field count before split, logs raw message on parse failure | `MIN_FIELDS` constant design, `_parse_line()` guard insertion point identified |
| ERR-03 | MQTT adapter logs Disconnect/Reconnect events with connection reason and attempt counter | `_run_loop()` / `_connect()` modification points, counter reset strategy |
</phase_requirements>

## Summary

This phase adds differentiated error classification and defensive validation to three existing subsystems — all of which already work but silently hide failure modes. The scope is tightly constrained by CONTEXT.md decisions: no new adapters, no circuit breakers, no metrics, no public API changes.

The work is purely additive in structure (one new file, additions to three existing files, typed raises in six resolver files). The existing test suite (201 tests, `asyncio_mode = "auto"`) must remain green throughout. All three requirements can be implemented in isolation and verified independently.

**Primary recommendation:** Implement in this order: (1) create `errors.py` and refactor chain, (2) add per-resolver typed raises, (3) Fritz parser validation, (4) MQTT reconnect logging. This ordering means each step builds cleanly on the last with no cross-dependencies.

## Standard Stack

### Core (already in use — no new dependencies needed)
| Library | Version | Purpose | Relevance |
|---------|---------|---------|-----------|
| aiohttp | 3.13.5+ | HTTP client for web scrapers | `aiohttp.ClientError` is the base for network errors to catch and wrap |
| aiosqlite | 0.20.0+ | Async SQLite | `aiosqlite.Error` (inherits from `sqlite3.Error`) is what to catch in SqliteResolver |
| aiomqtt | 2.3.0+ | MQTT client | `aiomqtt.MqttError` is the relevant exception base for connection errors |
| pytest / pytest-asyncio | 8.3.4+ / 0.24.0+ | Test runner | `asyncio_mode = "auto"` means no decorators needed on async tests |

No new installations required. All exception types come from existing dependencies.

## Architecture Patterns

### Recommended Project Structure Change
```
src/adapters/resolver/
├── errors.py          # NEW — ResolverError hierarchy
├── chain.py           # MODIFY — typed exception catches
├── tellows.py         # MODIFY — raise NetworkError / RateLimitError
├── dastelefon.py      # MODIFY — raise NetworkError
├── klartelbuch.py     # MODIFY — raise NetworkError
├── sqlite_db.py       # MODIFY — raise ResolverError on DB failure
├── json_file.py       # MODIFY — raise ResolverError on IO failure
└── msn.py             # MODIFY — raise ResolverError if needed

src/adapters/input/
└── fritz_callmonitor.py  # MODIFY — add MIN_FIELDS, validation in _parse_line()

src/adapters/
└── mqtt.py               # MODIFY — _reconnect_attempts counter, 4 log events
```

### Pattern 1: Exception Hierarchy (errors.py)

**What:** A minimal 3-class hierarchy covering the three distinct failure modes.
**When to use:** Raised by resolver adapters, caught by the chain.

```python
# src/adapters/resolver/errors.py


class ResolverError(Exception):
    """Base class for all resolver adapter failures."""


class NetworkError(ResolverError):
    """Raised when a network request fails (connection error, timeout, HTTP error)."""


class RateLimitError(ResolverError):
    """Raised when a service signals rate limiting (HTTP 429, backoff cues)."""
```

**Note on `__all__`:** Adding `__all__ = ["ResolverError", "NetworkError", "RateLimitError"]` is recommended — makes the public interface explicit and aligns with the module's purpose as a dedicated errors module (Claude's discretion per D-discretion).

### Pattern 2: Chain Exception Handling (chain.py)

**What:** Replace single broad `except Exception` with three typed clauses.
**Why:** Enables differentiated log levels (no traceback for expected network failures, traceback for unexpected structural errors).

```python
# src/adapters/resolver/chain.py
from src.adapters.resolver.errors import NetworkError, RateLimitError, ResolverError

# In resolve() loop — replace existing single except:
try:
    result = await adapter.resolve(number)
    ...
except NetworkError as exc:
    logger.warning("Adapter '%s' [NETWORK_ERROR] for '%s': %s", adapter.name, number, exc)
    continue
except RateLimitError as exc:
    logger.warning("Adapter '%s' [RATE_LIMITED] for '%s': %s", adapter.name, number, exc)
    continue
except ResolverError as exc:
    logger.exception("Adapter '%s' [RESOLVER_ERROR] for '%s': %s", adapter.name, number, exc)
    continue
except Exception:
    logger.exception("Adapter '%s' failed for number '%s'", adapter.name, number)
    continue
```

**Note:** The final `except Exception` catches anything not yet typed (e.g., unexpected bugs in resolver code), maintaining existing behavior as a safety net.

### Pattern 3: Per-Resolver Typed Raises

**Web scrapers** (tellows.py, dastelefon.py, klartelbuch.py): Replace `return None` on network failure with `raise NetworkError(...)`. The existing `except aiohttp.ClientError` is the correct catch point.

**Current pattern in `_scrape()` methods:**
```python
except aiohttp.ClientError as e:
    self.logger.error("Request failed for %r: %s", number, e)
    return None  # CHANGE THIS
```

**New pattern:**
```python
from src.adapters.resolver.errors import NetworkError, RateLimitError

# In _scrape():
except aiohttp.ClientError as e:
    raise NetworkError(f"Request failed for {number!r}: {e}") from e

# HTTP 429 handling (add before existing HTTP status check):
if response.status == 429:
    raise RateLimitError(f"Rate limited by {self.name} for {number!r} (HTTP 429)")
```

**Current behavior on non-200:** Three scrapers log `.info()` and `return None`. The decision (D-03) says web scrapers raise on I/O failures — HTTP 4xx/5xx counts as network-level failure. However, `return None` for non-200 (other than 429) is reasonable since these are "not found" signals rather than errors. The `return None` for non-200-non-429 can stay — only `aiohttp.ClientError` (connection failure, timeout) and HTTP 429 become typed raises.

**Local resolvers** (sqlite_db.py, json_file.py, msn.py): Currently no `try/except` in resolve(). For sqlite_db.py, the `db.get_contact()` and `db.update_last_seen()` calls could raise `aiosqlite.Error`. Per D-03, wrap these structural/IO failures in `ResolverError`.

```python
# sqlite_db.py resolve():
from src.adapters.resolver.errors import ResolverError
import aiosqlite

try:
    contact = await self.db.get_contact(number)
except aiosqlite.Error as e:
    raise ResolverError(f"SQLite lookup failed for {number!r}: {e}") from e
```

**json_file.py** already has `try/except` in `_load_contacts()` (startup only). `resolve()` is pure dict lookup — no IO, so no typed raise needed there. **msn.py** is pure in-memory dict lookup — no IO — so no typed raise needed.

### Pattern 4: Fritz Parser MIN_FIELDS Validation

**What:** Module-level constant + single guard after event_type resolution in `_parse_line()`.

```python
# src/adapters/input/fritz_callmonitor.py — module level constant
MIN_FIELDS: dict[CallEventType, int] = {
    CallEventType.RING: 5,       # date;RING;conn;caller;called
    CallEventType.CALL: 6,       # date;CALL;conn;ext;caller;called
    CallEventType.CONNECT: 5,    # date;CONNECT;conn;ext;number
    CallEventType.DISCONNECT: 4, # date;DISCONNECT;conn;duration
}
```

**Insertion point in `_parse_line()`:** After the existing `event_type = EVENT_MAP.get(event_name)` / `if not event_type: return None` block, before any field access.

```python
# After event_type resolution:
if len(parts) < MIN_FIELDS[event_type]:
    logger.warning(
        "Fritz parse error [%s]: need %d fields, got %d | raw: %s",
        event_type.value,
        MIN_FIELDS[event_type],
        len(parts),
        line,
    )
    return None
```

**Unknown event type** (D-12): The current `if not event_type: return None` silently drops unknown events. Per D-12, change to:
```python
event_type = EVENT_MAP.get(event_name)
if not event_type:
    logger.debug("Unknown Fritz event type '%s' | raw: %s", event_name, line)
    return None
```

**Existing guard:** The current `if len(parts) < 4: return None` at the top of `_parse_line()` can remain as a pre-check before event_type resolution (it already runs before `parts[1]` access). The MIN_FIELDS check is additive, not a replacement.

**Test compatibility:** Existing tests in `test_fritz_parser.py` use lines with correct field counts for valid events. The new validation only rejects under-counted lines, so existing tests remain green. Tests for the new validation paths will be added in Phase 4 (TEST-04).

### Pattern 5: MQTT Reconnect Counter & Logging

**What:** Instance variable + four log points in `_run_loop()` and `_connect()`.
**Where:** `src/adapters/mqtt.py`

**Init change (`__init__`):**
```python
self._reconnect_attempts: int = 0
```

**`_run_loop()` changes:** The current exception handler handles `ImportError` and generic `Exception`. Add counter increment and RECONNECTING log before `asyncio.sleep`:

```python
async def _run_loop(self) -> None:
    while self._running:
        try:
            await self._connect()
        except asyncio.CancelledError:
            break
        except ImportError:
            self.logger.error("aiomqtt not installed...")
            break
        except Exception as exc:
            self.logger.exception("MQTT connection error")
            self._client = None
            self._ready.clear()
            if self._running:
                self._reconnect_attempts += 1
                reason = str(exc) if exc else "unknown error"
                self.logger.warning("MQTT disconnected: %s", reason)
                self.logger.info(
                    "MQTT reconnecting in %ds (attempt %d)",
                    self._reconnect_delay,
                    self._reconnect_attempts,
                )
                await asyncio.sleep(self._reconnect_delay)
```

**`_connect()` changes:** After `async with aiomqtt.Client() as client:` block, add DISCONNECTED log. After the existing connected log, add RECONNECTED log. Reset counter after successful connection.

```python
async def _connect(self) -> None:
    ...
    async with aiomqtt.Client(**client_kwargs) as client:
        self._client = client
        if self._reconnect_attempts > 0:
            self.logger.info(
                "MQTT reconnected after %d attempt(s)", self._reconnect_attempts
            )
        self._reconnect_attempts = 0  # reset after success
        self.logger.info("MQTT connected to %s:%d ...", ...)
        ...
        # message loop
    # After context manager exits (both clean and exception paths):
    self._client = None
    self._ready.clear()
    if not self._running:
        self.logger.info("MQTT disconnected: graceful shutdown")
    # Note: exception-path DISCONNECTED is logged in _run_loop
```

**Design note on graceful vs. exception disconnect:** The `async with aiomqtt.Client()` block exits either cleanly (when `_running` becomes False) or via exception. For the exception path, `_run_loop` receives the exception and is the right place to log DISCONNECTED. For the clean path (loop exits because `not self._running`), add a `logger.info("MQTT disconnected: graceful shutdown")` after the context manager exits in `_connect()`.

### Anti-Patterns to Avoid

- **Catching exceptions too broadly in resolvers:** Only catch specific exception types (`aiohttp.ClientError`, `aiosqlite.Error`). Do not use bare `except Exception` in resolver implementations — that belongs in the chain.
- **Changing the chain's return type:** `Optional[ResolveResult]` must stay. The distinction between NOT_FOUND (returns `None`) and NETWORK_ERROR (raises `NetworkError`) is preserved by this design.
- **Short-circuiting on network errors:** D-06 is explicit — all adapters are tried even after a `NetworkError`. Do not add early-return logic.
- **Adding `_reconnect_attempts` increment inside `_connect()` itself:** The counter should increment in `_run_loop()` on failure, not in `_connect()`. This keeps the counter semantics clean: one increment per failed attempt.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP error classification | Custom HTTP status → error type mapping | `aiohttp.ClientError` (already catches connection/timeout), HTTP 429 check | aiohttp already distinguishes connection vs. response errors |
| Exception hierarchy | Complex multi-level hierarchy with codes | 3-class hierarchy (ResolverError, NetworkError, RateLimitError) | YAGNI — three distinct log behaviors is the only need |
| Reconnect counter state machine | Separate state class | Simple int on adapter instance | No persistence needed, reset on success is the only logic |

## Common Pitfalls

### Pitfall 1: logger.exception() vs logger.warning() in the chain
**What goes wrong:** Using `logger.exception()` for `NetworkError` / `RateLimitError` generates traceback noise in logs — these are expected operational failures, not bugs.
**Why it happens:** The existing chain uses `logger.exception()` for all errors. Copy-paste extends this.
**How to avoid:** Per D-07 explicitly: `NetworkError`/`RateLimitError` → `logger.warning` (no traceback); unknown `ResolverError` → `logger.exception` (includes traceback).
**Warning signs:** Logs showing full `aiohttp.ClientConnectorError` tracebacks on every failed network call.

### Pitfall 2: Existing fritz tests failing on MIN_FIELDS check
**What goes wrong:** Adding MIN_FIELDS with a wrong count for an event type that existing tests use causes regressions.
**Why it happens:** Off-by-one on field counts — the date field is `parts[0]`, so a RING line `date;RING;conn;caller;called;SIP` has 6 parts but only needs 5 as minimum (SIP is optional).
**How to avoid:** Verify against actual test fixtures in `test_fritz_parser.py`:
  - RING test: `"15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0"` — 6 parts, minimum is 5 (indices 0-4)
  - CALL test: `"15.03.26 10:15:00;CALL;1;12;0123456789;0987654321;SIP0"` — 7 parts, minimum is 6 (indices 0-5)
  - CONNECT test: `"15.03.26 10:15:30;CONNECT;0;12;0123456789"` — 5 parts, minimum is 5
  - DISCONNECT test: `"15.03.26 10:20:00;DISCONNECT;0;120"` — 4 parts, minimum is 4
**Warning signs:** `test_parse_ring_event` or any valid-event test returning `None` after the change.

### Pitfall 3: MQTT counter not reset on successful reconnect
**What goes wrong:** Counter accumulates across multiple reconnect cycles, making the "reconnected after N attempts" log misleading (shows lifetime total not per-outage attempts).
**Why it happens:** Reset placed after wrong code path (e.g., after `stop()` rather than in `_connect()` after success).
**How to avoid:** Reset `_reconnect_attempts = 0` immediately after the `async with aiomqtt.Client()` context successfully starts (inside the block, after the connection is live).

### Pitfall 4: Resolver `return None` vs `raise NetworkError` confusion
**What goes wrong:** Raising `NetworkError` where `return None` was appropriate causes the chain to log a warning when the service simply has no data for the number.
**Why it happens:** Conflating "service returned no results" (correct: return None) with "service was unreachable" (correct: raise NetworkError).
**How to avoid:**
  - HTTP 200 with no extractable data → `return None` (NOT_FOUND)
  - HTTP 429 → `raise RateLimitError`
  - `aiohttp.ClientError` (connection refused, timeout) → `raise NetworkError`
  - Other HTTP error (404, 500, etc.) → `return None` (service didn't find it or errored, not our retry problem)

### Pitfall 5: Ruff violations in new code
**What goes wrong:** New exception classes or imports trigger Ruff E/F/W rules.
**Why it happens:** Forgetting to check after adding new imports, unused variables.
**How to avoid:** Run `uv run ruff check src/` after each file modification. The CI config at `pyproject.toml` selects E, F, W rules at 120-char.

## Code Examples

### errors.py — complete file
```python
# src/adapters/resolver/errors.py
"""Typed exception hierarchy for resolver adapter failures."""

__all__ = ["ResolverError", "NetworkError", "RateLimitError"]


class ResolverError(Exception):
    """Base class for all resolver adapter failures.

    Raised by resolver implementations for structural or I/O errors.
    Caught by ResolverChain and logged with traceback.
    """


class NetworkError(ResolverError):
    """Raised when a network request fails.

    Covers connection errors, timeouts, and I/O failures from aiohttp.
    Caught by ResolverChain and logged as warning (no traceback).
    """


class RateLimitError(ResolverError):
    """Raised when a resolver service signals rate limiting.

    Typically corresponds to HTTP 429 or equivalent backoff signals.
    Caught by ResolverChain and logged as warning (no traceback).
    """
```

### chain.py — updated resolve() loop
```python
# In ResolverChain.resolve():
from src.adapters.resolver.errors import NetworkError, RateLimitError, ResolverError

for adapter in self._adapters:
    try:
        result = await adapter.resolve(number)
        if result is not None:
            logger.info("Number '%s' resolved by adapter '%s': %s",
                        number, adapter.name, result.name)
            return result
        logger.debug("Adapter '%s' could not resolve '%s'", adapter.name, number)
    except NetworkError as exc:
        logger.warning("Adapter '%s' [NETWORK_ERROR] for '%s': %s", adapter.name, number, exc)
        continue
    except RateLimitError as exc:
        logger.warning("Adapter '%s' [RATE_LIMITED] for '%s': %s", adapter.name, number, exc)
        continue
    except ResolverError as exc:
        logger.exception("Adapter '%s' [RESOLVER_ERROR] for '%s': %s", adapter.name, number, exc)
        continue
    except Exception:
        logger.exception("Adapter '%s' failed for number '%s'", adapter.name, number)
        continue
```

### tellows.py / dastelefon.py / klartelbuch.py — scraper error raising
```python
# At top of file:
from src.adapters.resolver.errors import NetworkError, RateLimitError

# In _scrape(), replace the aiohttp.ClientError handler:
except aiohttp.ClientError as e:
    raise NetworkError(f"Request failed for {number!r}: {e}") from e

# Add HTTP 429 check before existing status check (inside async with response):
if response.status == 429:
    raise RateLimitError(f"Rate limited by {self.name} for {number!r} (HTTP 429)")
```

### fritz_callmonitor.py — MIN_FIELDS validation
```python
# Module level (after EVENT_MAP):
MIN_FIELDS: dict[CallEventType, int] = {
    CallEventType.RING: 5,
    CallEventType.CALL: 6,
    CallEventType.CONNECT: 5,
    CallEventType.DISCONNECT: 4,
}

# In _parse_line(), after event_type resolution:
event_type = EVENT_MAP.get(event_name)
if not event_type:
    logger.debug("Unknown Fritz event type '%s' | raw: %s", event_name, line)
    return None

if len(parts) < MIN_FIELDS[event_type]:
    logger.warning(
        "Fritz parse error [%s]: need %d fields, got %d | raw: %s",
        event_type.value,
        MIN_FIELDS[event_type],
        len(parts),
        line,
    )
    return None
```

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| Single `except Exception` in chain | Typed `except NetworkError / RateLimitError / ResolverError` | Enables differentiated logging; Python 3.x standard |
| Silent `return None` on network failure | `raise NetworkError` with message | Makes failures observable without changing chain public interface |
| No Fritz field count check | `MIN_FIELDS` dict + guard in `_parse_line()` | Strict minimum with tolerance for optional trailing fields |
| No MQTT reconnect counter | `_reconnect_attempts` int on adapter | Simple session-scoped counter, reset on success |

## Open Questions

1. **Rate limit detection in DasTelefonbuch and KlarTelefonbuch**
   - What we know: Tellows returns standard HTTP codes. DasTelefonbuch / KlarTelefonbuch behavior on overload is unverified.
   - What's unclear: Whether these services return HTTP 429 or use other mechanisms (CAPTCHA, redirect, non-standard status).
   - Recommendation: Add `RateLimitError` for HTTP 429 in all three scrapers. If other signals exist, they can be added in Phase 4 when scraper tests are built.

2. **sqlite_db.py — aiosqlite error wrapping scope**
   - What we know: `db.get_contact()` and `db.update_last_seen()` are async and use aiosqlite. The Database class does its own error handling (logs and propagates).
   - What's unclear: Whether wrapping at the resolver level adds value when the Database layer already logs.
   - Recommendation: Add `try/except aiosqlite.Error → raise ResolverError` in SqliteResolver.resolve() per D-03. This is the correct layer for typed raises.

## Environment Availability

Step 2.6: SKIPPED — phase is purely code/config changes with no new external dependencies. All required tools (Python 3.12, uv, pytest) confirmed available from prior phases.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4+ with pytest-asyncio 0.24.0+ |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_resolver_chain.py tests/test_fritz_parser.py -v` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ERR-01 | Chain catches NetworkError, logs warning without traceback | unit | `uv run pytest tests/test_resolver_chain.py -v -k "network_error"` | ❌ Wave 0 |
| ERR-01 | Chain catches RateLimitError, logs warning without traceback | unit | `uv run pytest tests/test_resolver_chain.py -v -k "rate_limit"` | ❌ Wave 0 |
| ERR-01 | Chain catches base ResolverError, logs with traceback | unit | `uv run pytest tests/test_resolver_chain.py -v -k "resolver_error"` | ❌ Wave 0 |
| ERR-01 | Scraper raises NetworkError on aiohttp.ClientError | unit | `uv run pytest tests/test_tellows.py -v` | ❌ Wave 0 (optional) |
| ERR-02 | _parse_line() returns None for RING with < 5 fields | unit | `uv run pytest tests/test_fritz_parser.py -v -k "min_fields"` | ❌ Wave 0 |
| ERR-02 | _parse_line() logs warning with raw message on field count failure | unit | `uv run pytest tests/test_fritz_parser.py -v -k "parse_error"` | ❌ Wave 0 |
| ERR-02 | Unknown event type logs at DEBUG not WARNING | unit | `uv run pytest tests/test_fritz_parser.py -v -k "unknown_event"` | existing (test_parse_unknown_event) — verify log level only |
| ERR-03 | MQTT adapter increments counter on reconnect | unit | `uv run pytest tests/test_mqtt_output.py -v -k "reconnect"` | ❌ Wave 0 |
| ERR-03 | MQTT adapter resets counter after successful connect | unit | `uv run pytest tests/test_mqtt_output.py -v -k "counter_reset"` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -v` (full suite, 201 tests runs in < 5s locally)
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_resolver_chain.py` — add test cases for `NetworkError`, `RateLimitError`, `ResolverError` typed catches (file exists, extend it)
- [ ] `tests/test_fritz_parser.py` — add test cases for MIN_FIELDS validation and unknown event debug log level (file exists, extend it)
- [ ] `tests/test_mqtt_output.py` — add test cases for reconnect counter increment and reset (file exists, extend it — or use existing test patterns)
- [ ] No new framework installs needed — pytest + pytest-asyncio already configured

## Sources

### Primary (HIGH confidence)
- Direct source code inspection of all 8 files to be modified
- `tests/test_fritz_parser.py` — existing test fixtures verified against proposed MIN_FIELDS values
- `tests/test_resolver_chain.py` — existing test patterns confirm MockResolver approach works
- `pyproject.toml` — test config, ruff rules, and asyncio_mode verified

### Secondary (MEDIUM confidence)
- aiohttp documentation: `aiohttp.ClientError` is the documented base exception for client-side failures (connection errors, timeouts, SSL errors)
- aiomqtt documentation: `aiomqtt.MqttError` base exception; `async with aiomqtt.Client()` context manager is the connect/disconnect boundary
- Python docs: Exception hierarchy design — specific before general, re-raise with `from e` for cause chaining

### Tertiary (LOW confidence)
- Rate limit behavior (HTTP 429) of DasTelefonbuch and KlarTelefonbuch — unverified, assumed from standard HTTP practice

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all existing dependencies verified
- Architecture: HIGH — all modification points identified from direct source reading, decisions locked in CONTEXT.md
- Pitfalls: HIGH — field counts verified against actual test fixtures, exception hierarchy is standard Python practice

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable domain — Python exception handling and aiohttp error types are stable)
