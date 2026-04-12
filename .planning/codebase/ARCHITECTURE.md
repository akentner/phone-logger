# Architecture

**Analysis Date:** 2026-04-13

## Pattern Overview

**Overall:** Input → Resolve → Output pipeline with adapter-based extensibility

**Key Characteristics:**
- **Adapter pattern**: Three distinct adapter types (input, resolver, output) with pluggable implementations
- **Chain-of-Responsibility**: Resolvers form an ordered chain where the first successful result wins
- **State machine**: PBX line FSM tracks per-line state transitions (IDLE → RING/CALL → TALKING → FINISHED/MISSED/NOT_REACHED)
- **Event-driven async**: FastAPI/asyncio for concurrent event handling, aiosqlite for non-blocking database access
- **Enrichment pipeline**: Events pass through normalization, PBX enrichment, resolution, and output stages with mutation at each step

## Layers

**Input Layer:**
- Purpose: Acquire call events from external sources (Fritz!Box TCP, REST API, MQTT)
- Location: `src/adapters/input/` and `src/adapters/mqtt.py`
- Contains: Concrete input adapters that produce `CallEvent` objects
- Depends on: `BaseInputAdapter`, `CallEvent` models
- Used by: Pipeline calls `adapter.start(callback)` to listen for events

**Normalization Layer:**
- Purpose: Standardize phone numbers to E.164 format with country/area code expansion
- Location: `src/core/phone_number.py`
- Contains: `normalize()`, `to_dialable()`, `to_local()`, `to_scrape_format()` functions
- Depends on: Country code and local area code from config
- Used by: Pipeline applies normalization before enrichment and resolution

**PBX Enrichment Layer:**
- Purpose: Enrich events with PBX infrastructure data (line IDs, device information, MSN resolution)
- Location: `src/core/pbx.py` — `PbxStateManager.enrich_event()` and `update_state()`
- Contains: Event enrichment logic, device/MSN lookups, FSM state machine
- Depends on: `CallEvent`, PbxConfig (devices, MSNs, trunks), LineState
- Used by: Pipeline calls `pbx.enrich_event()` then `pbx.update_state()` before resolution

**Resolver Layer:**
- Purpose: Look up caller/called party names and metadata through a chain of resolvers
- Location: `src/adapters/resolver/` — base class, chain implementation, and concrete resolvers
- Contains: `BaseResolverAdapter`, `ResolverChain` (chain-of-responsibility), implementations for JSON files, SQLite cache, web scrapers (Tellows, DasTelefonbuch, KlarTelefonbuch), and MSN/contact database
- Depends on: `ResolveResult` model, `Database`, adapter configuration
- Used by: Pipeline calls `resolver_chain.resolve(number)` for RING/CALL events; result is cached per `line_id`

**Output Layer:**
- Purpose: Persist events and dispatch them to external systems (database, webhooks, MQTT)
- Location: `src/adapters/output/` and `src/adapters/mqtt.py`
- Contains: Concrete output adapters implementing `BaseOutputAdapter`
- Depends on: `CallEvent`, `ResolveResult`, `LineState`, adapter configuration
- Used by: Pipeline calls `adapter.handle(event, result, line_state=state)` after resolution

**API Layer:**
- Purpose: Expose HTTP endpoints for external access to resolve, contacts, call history, and PBX status
- Location: `src/api/` — `app.py` (FastAPI setup), `routes/` (endpoint definitions), `models.py` (response schemas)
- Contains: GET/POST/PUT/DELETE endpoints for contacts, calls, cache, PBX status, translations, and direct resolution triggers
- Depends on: Pipeline, Database, PbxStateManager for data access
- Used by: Web browser (GUI), external integrations

**GUI Layer:**
- Purpose: Serve web UI for monitoring and management
- Location: `src/gui/routes.py` (page templates), `src/gui/templates/`, `src/gui/static/`
- Contains: Jinja2 template routes and static assets
- Depends on: Fastapi router, template files
- Used by: Browser requests to `/`, `/pbx`, `/contacts`, `/calls`, `/cache`, `/config`

**Database Layer:**
- Purpose: Persist call history, contacts, resolver cache, and raw event logs
- Location: `src/db/database.py`, `src/db/schema.sql`
- Contains: Async SQLite wrapper with schema initialization and migrations
- Depends on: aiosqlite, schema definitions, UUIDv7 generator
- Used by: Pipeline for logging, resolvers for caching, output adapters for storage

**Configuration Layer:**
- Purpose: Load and validate application configuration from YAML (dev), HA options.json (production), or defaults
- Location: `src/config.py`
- Contains: Pydantic models for all config sections (adapters, PBX, phone, database)
- Depends on: YAML, JSON parsing
- Used by: Main entry point to bootstrap the application

## Data Flow

**Call Event Processing (Main Pipeline):**

1. **Input stage**: Input adapter receives raw event (TCP line, REST JSON, MQTT message) → parses into `CallEvent`
2. **Raw event logging**: Event and raw input stored in `raw_events` table for audit trail
3. **Normalization**: Phone numbers (`number`, `caller_number`, `called_number`) normalized to E.164 using country/area code config
4. **PBX enrichment**: 
   - `pbx.enrich_event()` extracts `line_id` from `connection_id`, looks up devices by ID, resolves MSN strings to E.164
   - Sets `caller_device`, `called_device`, `caller_number`, `called_number` based on event type and PBX config
5. **State machine update**: `pbx.update_state()` executes FSM transition for the line
   - IDLE + RING/CALL → RING/CALL state, populate line state with call details
   - RING/CALL + CONNECT → TALKING state
   - TALKING + DISCONNECT → FINISHED state
   - RING + DISCONNECT (no CONNECT) → MISSED state
   - CALL + DISCONNECT (no CONNECT) → NOT_REACHED state
   - Terminal states auto-reset to IDLE after 1 second
6. **Early line state notification**: Output adapters notified of line state changes immediately (via `handle_line_state_change()`)
7. **Event enrichment from LineState**: For CONNECT/DISCONNECT events (which lack number fields from Fritz!Box), fill missing fields from stored LineState
8. **Resolution**:
   - For RING/CALL events: Run `resolver_chain.resolve(number)` through all configured resolvers in order
   - First successful result is returned and cached in `_resolve_cache` keyed by `line_id`
   - For CONNECT/DISCONNECT: Look up cached result from earlier RING/CALL on same line
9. **Output dispatch**: All output adapters receive `handle(event, result, line_state=state)` with fully enriched event, resolve result (or None), and current line state
10. **Cache cleanup**: When line enters terminal state (finished/missed/notReached), the cached resolver result for that line is discarded

**State Management:**

- `LineState`: In-memory representation of a single PBX line; includes caller/called numbers, devices, direction, status, and last-changed timestamp
- `LineFSM`: Per-line finite state machine with fault-tolerant invalid-transition handling
- `PbxStateManager`: Manages all FSMs, holds MSN/device lookups, pre-computes E.164 representations of configured MSNs
- `_resolve_cache` (in Pipeline): Transient dict mapping `line_id` → `ResolveResult` to bridge RING/CALL resolution to CONNECT/DISCONNECT output

## Key Abstractions

**CallEvent:**
- Purpose: Normalized representation of a call event
- Location: `src/core/event.py`
- Pattern: Pydantic BaseModel with optional fields for enrichment
- Fields: `number`, `direction`, `event_type`, `timestamp`, `source` (input adapter), `connection_id`, `extension`, `caller_number`, `called_number`, `line_id`, `trunk_id`, `caller_device`, `called_device`, `raw_input`

**ResolveResult:**
- Purpose: Result of a phone number lookup with metadata
- Location: `src/core/event.py`
- Pattern: Pydantic BaseModel; computed property `is_spam` for spam_score >= 7
- Fields: `number`, `name`, `tags`, `notes`, `spam_score`, `source` (resolver adapter), `cached` (boolean)

**BaseInputAdapter:**
- Purpose: Contract for acquiring call events
- Location: `src/adapters/base.py`
- Pattern: Abstract base class with concrete implementations
- Methods: `start(callback)` to begin listening, `stop()` to cease
- Implementations: `FritzCallmonitorAdapter` (TCP/1012), `RestInputAdapter` (HTTP POST), `MqttAdapter` (MQTT subscribe)

**BaseResolverAdapter:**
- Purpose: Contract for resolving phone numbers
- Location: `src/adapters/base.py`
- Pattern: Abstract base class with optional `start()`/`stop()` for resource initialization
- Methods: `resolve(number)` → `Optional[ResolveResult]`
- Implementations: `JsonFileResolver`, `SqliteResolver`, `TellowsResolver`, `DasTelefonbuchResolver`, `KlarTelefonbuchResolver`, `MsnResolver`

**BaseOutputAdapter:**
- Purpose: Contract for processing resolved events
- Location: `src/adapters/base.py`
- Pattern: Abstract base class with lifecycle methods
- Methods: 
  - `handle(event, result, *, line_state)` — process event after resolution
  - `handle_line_state_change(line_state)` — notify of line state changes before resolution (for low-latency updates)
  - `start()`, `stop()` for initialization/cleanup
- Implementations: `CallLogOutputAdapter` (SQLite storage), `WebhookOutputAdapter` (HTTP POST), `MqttAdapter` (MQTT publish)

**ResolverChain:**
- Purpose: Chain-of-Responsibility implementation for resolver selection
- Location: `src/adapters/resolver/chain.py`
- Pattern: Maintains ordered list of resolvers; iterates until first success
- Methods: `resolve(number)` iterates adapters, catches exceptions, logs outcomes

**Pipeline:**
- Purpose: Main orchestrator of input → resolve → output flow
- Location: `src/core/pipeline.py`
- Pattern: Singleton-like (created in main.py, accessed via `get_pipeline()`)
- Key state:
  - `resolver_chain`: ResolverChain instance
  - `pbx`: PbxStateManager instance
  - `_input_adapters`: List of active input adapters
  - `_output_adapters`: List of active output adapters
  - `_resolve_cache`: Dict mapping line_id → ResolveResult
- Key methods:
  - `setup()`: Initialize all adapters from config
  - `start()`: Begin all adapters
  - `stop()`: Halt all adapters
  - `_on_event(event)`: Process a single event through the full pipeline
  - `resolve(number)`: Direct API to resolve a number (used by REST endpoint)

**PbxStateManager:**
- Purpose: Track per-line state and enrich events with PBX data
- Location: `src/core/pbx.py`
- Pattern: Stateful object initialized with PbxConfig; maintains in-memory FSMs and LineStates
- Key state:
  - `_fsms`: Dict mapping line_id → LineFSM
  - `_states`: Dict mapping line_id → LineState
  - `_devices_by_id`, `_devices_by_ext`: Lookup dicts for device configurations
  - `_msn_e164_set`, `_msn_e164_map`: Pre-computed MSN to E.164 mappings
  - `_reset_tasks`: Pending auto-reset tasks for terminal states
- Key methods:
  - `enrich_event()`: Add PBX data to event before state machine update
  - `update_state()`: Execute FSM transition and update LineState
  - `get_line_state()`, `get_line_states()`: Query current state
  - `get_status()`: Full PBX status snapshot for API

## Entry Points

**Application Initialization:**
- Location: `src/main.py`
- Triggers: `uvicorn` server start
- Responsibilities: 
  - Load config from YAML/HA options/defaults
  - Create Database, Pipeline instances
  - Register API and GUI routes
  - Set up lifespan handlers for startup/shutdown
  - Expose global `get_config()`, `get_db()`, `get_pipeline()` accessors

**Input Adapters:**
- Fritz!Box: `FritzCallmonitorAdapter.start()` opens TCP connection to Fritz!Box port 1012; parses newline-delimited event strings
- REST: `RestInputAdapter.start()` (implicit via routes); API endpoints trigger events via `adapter.trigger()`
- MQTT: `MqttAdapter.start()` subscribes to configured topics and generates events from messages

**API Routes:**
- `/api/resolve/{number}` — POST request through REST input adapter (triggers event pipeline)
- `/api/contacts` — CRUD operations on contact database
- `/api/calls` — Query aggregated call history
- `/api/pbx/status` — Full PBX state snapshot
- `/api/pbx/lines` — Current line states with display names
- GUI routes (`/`, `/pbx`, `/contacts`, `/calls`, `/cache`, `/config`) — Jinja2 templates

## Error Handling

**Strategy:** Defensive — adapters log exceptions and continue; invalid transitions are fault-tolerant (reset FSM to IDLE and retry)

**Patterns:**

- **Input adapter failures**: Logged and suppressed; reconnection attempt after delay (Fritz!Box TCP has exponential backoff)
- **Resolver failures**: Logged and skipped; chain continues to next adapter
- **Output adapter failures**: Logged and suppressed; other adapters still process the event
- **FSM invalid transitions**: Logged as warning; line reset to IDLE and transition retried from idle
- **Phone normalization failures**: Returns best-effort result (digits without formatting) or original input if parsing fails
- **Database operations**: Exceptions logged; some operations are best-effort (e.g., raw event logging failures don't block pipeline)

## Cross-Cutting Concerns

**Logging:** 
- All modules use Python `logging` module
- Adapter instances create loggers at `__name__.{adapter.name}` for granular control
- Pipeline logs event reception, routing, and error conditions

**Validation:**
- Pydantic models validate all config and event data at parsing time
- Input adapters parse/normalize before producing CallEvent
- Database operations validate presence of required fields (e.g., number for resolution)

**Authentication:**
- REST input adapter supports optional Bearer token (in webhook config)
- PBX status and contact CRUD are unauthenticated (assumed running behind Home Assistant addon sandbox)
- Home Assistant integration (custom component) handles addon authorization at integration level

**Caching:**
- Resolver cache in Pipeline memory (`_resolve_cache` per line_id)
- Resolver-specific caches in SQLite (Tellows, DasTelefonbuch with configurable TTL)
- No cache invalidation strategy except TTL or explicit cache clear endpoint

**Rate Limiting:** None (assumed running in trusted environment)

**Timezone Handling:**
- UTC for all timestamps internally (`datetime.now(UTC)`)
- Timezone config in Fritz!Box adapter for interpreting Callmonitor timestamps
- Home Assistant UI displays times in user's configured timezone
