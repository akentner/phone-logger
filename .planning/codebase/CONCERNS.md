# Codebase Concerns

**Analysis Date:** 2026-04-13

## Tech Debt

**Web Scraping Fragility - CSS Selector Dependencies:**
- Issue: Tellows, DasTelefonbuch, and KlarTelefonbuch resolvers rely on hardcoded CSS selectors that may break if website HTML structure changes
- Files: `src/adapters/resolver/tellows.py`, `src/adapters/resolver/dastelefon.py`, `src/adapters/resolver/klartelbuch.py`
- Impact: Zero warning when scraping fails silently or returns partial/incorrect data. Sites rotate layouts periodically, causing cascading failures
- Fix approach: Add fallback selectors for each scraper; implement HTTP response validation (e.g., check for "sorry, something went wrong" messages); add metrics for scraper success/failure rates to alert on breakage

**Overly Permissive Error Handling in Adapters:**
- Issue: Resolver chain silently catches all exceptions, logs them, and continues. Failed resolvers may return None without distinguishing between "not found" and "error occurred"
- Files: `src/adapters/resolver/chain.py` (lines 44-53), `src/core/pipeline.py` (lines 274-282)
- Impact: Failures in external services (network, timeouts, HTTP 500) are indistinguishable from "number has no public listing". Makes debugging difficult
- Fix approach: Create a ResolveError enum (NOT_FOUND, NETWORK_ERROR, RATE_LIMITED, INTERNAL_ERROR) and return decorated results; log failures with severity levels

**Database Migration Approach Lacks Atomicity:**
- Issue: `src/db/database.py` (_run_migrations) uses individual ALTER TABLE commands without rollback safety. SQLite migration pattern is fragile
- Files: `src/db/database.py` (lines 56-112)
- Impact: If a migration partially fails (e.g., at line 88), DB is left in inconsistent state. No way to recover without manual SQL intervention
- Fix approach: Implement a migration framework with versioning (migration_version table); wrap each migration in a transaction; test migrations with rollback scenarios

**Concurrency Issues in PBX Line State Reset:**
- Issue: `src/core/pbx.py` (_schedule_reset) creates asyncio Tasks without strong error handling. If event loop is not running, state lingers in terminal status
- Files: `src/core/pbx.py` (lines 394-424)
- Impact: In tests or during shutdown, lines may remain in FINISHED/MISSED state, breaking subsequent state queries. Terminal states are supposed to auto-reset after 1s
- Fix approach: Use a background cleanup task that periodically scans stale terminal states; add explicit reset on initialization

**SQL Query String Building with Concatenation:**
- Issue: Database queries use f-string concatenation: `f"SELECT * FROM raw_events{where} ..."`
- Files: `src/db/database.py` (lines 336, 396)
- Impact: Vulnerable to SQL injection if user input ever gets passed to where clause construction. Even with parameterized values now, future changes could introduce bugs
- Fix approach: Migrate to SQLAlchemy ORM or at minimum use SQLite prepared statement patterns throughout

**No Circuit Breaker for External Services:**
- Issue: Web scrapers (Tellows, DasTelefonbuch) can hammer external sites or fail en masse without throttling
- Files: `src/adapters/resolver/tellows.py`, `src/adapters/resolver/dastelefon.py`, `src/adapters/resolver/klartelbuch.py`
- Impact: Resolver timeout is 15s; if site is down, every call resolution waits 15s. In high-call-volume scenarios, this blocks pipeline
- Fix approach: Implement circuit breaker with fallback (fail fast after N consecutive failures); add exponential backoff

## Fragile Areas

**MQTT Connection State Machine:**
- Files: `src/adapters/mqtt.py` (full file - 598 lines)
- Why fragile: Complex state tracking with _running, _ready, _client, _task, and async callbacks. Multiple edge cases: disconnect during message send, reconnect while processing, callback errors
- Safe modification: Add comprehensive state logging; implement connection health checks (ping/pong); test all disconnect/reconnect scenarios systematically
- Test coverage: MQTT adapter has minimal unit test coverage. Behavior depends heavily on external broker availability

**Fritz!Box Callmonitor Parser:**
- Files: `src/adapters/input/fritz_callmonitor.py` (lines 111-150+)
- Why fragile: Message format is loosely specified. Parser assumes exact field ordering and count (e.g., CONNECT has 5 fields, DISCONNECT has 4). Any deviation crashes
- Safe modification: Add defensive parsing with field count validation before split; use named tuple or dataclass for clarity; log raw messages on parse failure
- Test coverage: Gaps in edge case parsing (e.g., numbers with semicolons, malformed timestamps)

**Phone Number Normalization Edge Cases:**
- Files: `src/core/phone_number.py` (lines 19-101)
- Why fragile: Assumes specific input formats (German). Numbers that don't match any pattern silently return partial results or original input
- Safe modification: Add type hints for return value; distinguish between "valid E.164" and "best-effort attempt"; add validation function separate from normalization
- Test coverage: Only positive-case tests visible; missing coverage for invalid inputs, non-German numbers, very short/long numbers

**PBX Event Enrichment with Device Lookup:**
- Files: `src/core/pbx.py` (lines 238-312)
- Why fragile: Device lookup logic uses Fritz!Box numeric IDs (e.g., "10") which may not be stable across firmware upgrades. Extension numbers (e.g., "**610") are also fragile
- Safe modification: Add configuration validation to warn if device IDs are unused (unreachable); log device lookup failures with IDs for debugging
- Test coverage: Device enrichment tested with happy path; missing coverage for missing/invalid device IDs

**Call Aggregation with Correlation ID:**
- Files: `src/adapters/output/call_log.py` (lines 60-212)
- Why fragile: Uses connection_id as primary correlation key. If Fritz!Box reuses connection_ids or sends out-of-order events, aggregation breaks
- Safe modification: Add validation that event sequence respects FSM transitions (RING→CONNECT→DISCONNECT); warn on unexpected transitions; implement timeout-based cleanup for orphaned calls
- Test coverage: Aggregation logic tested only for happy path (RING→CONNECT→DISCONNECT); missing coverage for out-of-order, duplicate, and missing events

## Performance Bottlenecks

**Resolver Chain Blocks Pipeline on Timeout:**
- Problem: resolve() awaits each resolver sequentially with 15s timeout. If one resolver hangs, entire call event is delayed
- Files: `src/adapters/resolver/chain.py` (lines 34-56), `src/core/pipeline.py` (lines 253-263)
- Cause: No timeout wrapping or concurrent resolver execution. Web scrapers have individual 15s timeouts but are tried one-by-one
- Improvement path: Wrap resolver calls with asyncio.timeout (Python 3.11+); implement concurrent resolver execution with first-win pattern; add per-resolver timeout configuration

**Database Checkpoint Overhead:**
- Problem: Every adapter operation (contact create, call log write, cache set) calls `db.commit()`, which blocks on SQLite WAL checkpoint
- Files: `src/db/database.py` (lines 143-148, 179-183, 227-238, etc.)
- Cause: No batch writing or async commit strategy. With high call volume, commit overhead dominates
- Improvement path: Implement write batching for call_log entries; use sqlite3 `PRAGMA synchronous=NORMAL` (currently missing); consider write queue with periodic flush

**Cache Lookup Overhead:**
- Problem: Every resolve operation queries cache table, even for adapters without caching
- Files: `src/adapters/resolver/tellows.py` (lines 60-85), `src/adapters/resolver/dastelefon.py` (lines 57-78)
- Cause: Cache is checked before each adapter, adding DB round-trip latency
- Improvement path: Move cache check to resolver chain level (before trying individual adapters); implement in-memory LRU cache layer for hot numbers

**Synchronous Phone Number Normalization:**
- Problem: normalize() is called on critical path for every number field (caller_number, called_number, number), each invoking regex operations
- Files: `src/core/pipeline.py` (lines 120-189)
- Cause: Single number can be normalized 2-3 times if multiple fields present
- Improvement path: Normalize once at input adapter level; cache normalized results per line_id

## Scaling Limits

**SQLite Write Concurrency:**
- Current capacity: Single writer at a time (SQLite limitation with WAL mode still serializes writes)
- Limit: Under high call volume (>50 concurrent calls), database contention may cause pipeline slowdown
- Scaling path: Migrate to PostgreSQL with connection pooling; implement write queue with async flush; or use separate DB for audit log (raw_events) with eventual consistency

**In-Memory PBX State:**
- Current capacity: Entire line state tree held in RAM (no persistence)
- Limit: After application restart, all line states reset to IDLE; no recovery of in-flight calls
- Scaling path: Persist line state to SQLite on terminal transitions; implement state recovery on startup

**Web Scraper Rate Limiting:**
- Current capacity: No rate limiting, 15s timeout per scraper
- Limit: External sites may block IP after multiple requests in quick succession
- Scaling path: Implement per-adapter request throttling; add distributed rate limiter for multi-instance deployments

## Known Bugs

**MQTT Connection Loss Not Recovered Gracefully:**
- Symptoms: MQTT client disconnects but doesn't reliably reconnect. Events published to offline broker are silently dropped
- Files: `src/adapters/mqtt.py` (connection handling and recovery)
- Trigger: Network interruption, broker restart
- Workaround: Application restart

**Fritz!Box Timestamp Parsing Issues:**
- Symptoms: Callmonitor timestamps may be incorrect if timezone is not configured correctly
- Files: `src/adapters/input/fritz_callmonitor.py` (lines 123-150)
- Trigger: Fritz!Box runs in different timezone than application server
- Workaround: Configure timezone in adapter config; use UTC timestamps from system clock instead

**Duplicate Calls on Rapid RING/CALL Events:**
- Symptoms: Two RING events in quick succession may create two call records instead of one
- Files: `src/adapters/output/call_log.py`, `src/db/database.py` (upsert_call logic)
- Trigger: Fritz!Box sends duplicate events (intermittent firmware bug)
- Workaround: Implement idempotency via connection_id deduplication window

**Cache TTL Not Enforced on Read:**
- Symptoms: Expired cache entries may be returned if cleanup job hasn't run
- Files: `src/db/database.py` (lines 204-221)
- Trigger: No scheduled cleanup_expired_cache() calls
- Workaround: Call cleanup_expired_cache() on app startup; add scheduled job

## Security Considerations

**Credentials in Configuration:**
- Risk: MQTT and webhook credentials are stored in config (passed via Home Assistant options.json)
- Files: `src/config.py`, `src/adapters/mqtt.py`, `src/adapters/output/webhook.py`
- Current mitigation: Credentials accessed only by server-side code, not exposed in API responses (redacted in config endpoint)
- Recommendations: Use Home Assistant secrets system (reference via !secret) instead of direct values; add encryption for stored credentials

**Web Scraper User-Agent Spoofing:**
- Risk: Static User-Agent may be flagged as bot and blocked
- Files: `src/adapters/resolver/tellows.py` (lines 20-23), `src/adapters/resolver/dastelefon.py` (lines 18-21)
- Current mitigation: User-Agent matches real browser
- Recommendations: Rotate User-Agent; implement proxy rotation if available; add cloudflare/DDoS mitigation detection

**SQL Injection in Where Clause:**
- Risk: Although currently parameterized, future changes may introduce injection vulnerabilities
- Files: `src/db/database.py` (lines 336, 396)
- Current mitigation: All values are parameterized; concatenated SQL is static
- Recommendations: Migrate to ORM; add SQL query validation in tests

**MQTT Message Injection:**
- Risk: Untrusted input from MQTT trigger topic could be used to inject malformed events
- Files: `src/adapters/mqtt.py` (message parsing)
- Current mitigation: Events are validated via Pydantic models
- Recommendations: Validate MQTT topic permissions; implement message signing for external MQTT sources

## Test Coverage Gaps

**Web Scraper HTML Parsing:**
- What's not tested: Parser behavior on broken/incomplete HTML, unexpected field order, missing required selectors
- Files: `src/adapters/resolver/tellows.py` (_parse_html), `src/adapters/resolver/dastelefon.py` (_parse_html)
- Risk: Silent failures returning None for valid entries due to minor HTML changes
- Priority: High

**Fritz!Box Event Sequence Edge Cases:**
- What's not tested: Out-of-order events (CONNECT before RING), duplicate events, missing DISCONNECT, rapid RING/RING
- Files: `src/adapters/input/fritz_callmonitor.py`, `src/core/pbx.py` (FSM transitions)
- Risk: Invalid state transitions crash or produce incorrect call records
- Priority: High

**Phone Number Normalization:**
- What's not tested: International numbers (non-German), numbers with formatting variants, very long/short numbers, edge cases like "+49" alone
- Files: `src/core/phone_number.py`
- Risk: Normalization failures cause resolver mismatches or incorrect lookups
- Priority: Medium

**MQTT Reconnection Scenarios:**
- What's not tested: Broker restart during message publish, rapid connect/disconnect cycles, network timeout during subscription
- Files: `src/adapters/mqtt.py`
- Risk: Lost messages, stale subscriptions, hanging tasks
- Priority: High

**Database Migration Idempotency:**
- What's not tested: Running migrations twice, partial migration failure recovery, rollback scenarios
- Files: `src/db/database.py` (_run_migrations)
- Risk: Schema inconsistency, data loss, deployment failures
- Priority: Medium

**Call Aggregation with Missing Events:**
- What's not tested: DISCONNECT without prior RING/CALL, CONNECT without DISCONNECT, missing connection_id in events
- Files: `src/adapters/output/call_log.py` (_aggregate_call)
- Risk: Orphaned call records, incorrect status calculations, duration errors
- Priority: High

## Dependencies at Risk

**aiohttp (Web Scraping):**
- Risk: Regularly updated; breaking changes possible; timeout behavior may change
- Impact: Web scrapers (Tellows, DasTelefonbuch) depend on aiohttp client session behavior
- Migration plan: Vendor timeout configuration; add integration tests with real HTTP responses

**aiosqlite (SQLite Async Wrapper):**
- Risk: Thin wrapper around sqlite3; issues with WAL mode under concurrent load not well documented
- Impact: Database operations may deadlock or silently fail under high concurrency
- Migration plan: Monitor for sqlite3 upgrade path to built-in async support; consider psycopg3 + PostgreSQL for higher concurrency

**BeautifulSoup4 (HTML Parsing):**
- Risk: Parser selection (lxml vs html.parser) affects robustness; lxml requires libxml2 system dependency
- Impact: Web scrapers may fail on malformed HTML or on systems without lxml
- Migration plan: Add fallback parser selection; document lxml dependency in Dockerfile

---

*Concerns audit: 2026-04-13*
