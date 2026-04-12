# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Install dependencies
uv sync

# Run server with dev config (Fritz disabled, REST input enabled)
PHONE_LOGGER_CONFIG=config.dev.yaml uv run python -m src.main

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_resolver_chain.py -v

# Run a specific test
uv run pytest tests/test_pbx.py::test_name -v
```

Tests use `asyncio_mode = "auto"` — all async tests work without extra decorators.

## Architecture

The system is an **Input → Resolver → Output pipeline** with adapter-based extensibility:

```
Fritz TCP / REST API / MQTT  →  CallEvent
                               ↓
                        Phone normalization (E.164)
                        PBX line state enrichment
                               ↓
                   Resolver Chain (first-match wins)
          JSON file / SQLite / Tellows / DasTelefonbuch / ...
                               ↓
                       Output Adapters
              CallLog (SQLite) / Webhook / MQTT publisher
```

**Core models** live in `src/core/event.py`: `CallEvent`, `ResolveResult`, `PipelineResult`.

**PBX FSM** (`src/core/pbx.py`) tracks per-line state: `IDLE → RING → TALKING → FINISHED/MISSED`, auto-resetting to IDLE after 1s from terminal states.

**Pipeline** (`src/core/pipeline.py`) is the main orchestrator. It registers and starts adapters, routes events, and caches resolver results per `line_id`.

## Adapter Conventions

Three abstract base classes in `src/adapters/base.py`:

- **`BaseInputAdapter.start(callback)`** — accepts a `Callable[[CallEvent], Coroutine]`
- **`BaseResolverAdapter.resolve(number)`** — returns `Optional[ResolveResult]`
- **`BaseOutputAdapter.handle(event, result, *, line_state)`** — processes resolved events

**Adapter selection** in `pipeline.py` factories:
- **Resolver adapters**: matched by `config.name` (e.g., `"sqlite"`, `"tellows"`)
- **Output adapters**: matched by `config.type` (e.g., `"call_log"`, `"webhook"`)

**Singleton constraint**: `call_log` output is limited to one instance (flag `call_log_registered` in pipeline). Multiple webhook/MQTT instances are allowed.

## Configuration

Load priority (`src/config.py`):
1. `PHONE_LOGGER_CONFIG` env var path
2. HA addon options at `/data/options.json`
3. Local `config.yaml`
4. Built-in defaults

`config.dev.yaml` is the development configuration — Fritz input is disabled, REST input is enabled, and MQTT is disabled.

## Database

Async SQLite via `aiosqlite` (`src/db/database.py`). Schema in `src/db/schema.sql` with 4 tables: `contacts`, `cache`, `call_log`, `calls`. WAL mode enabled. The `calls` table uses UUIDv7 primary keys (`src/core/utils.py`).

## API Structure

- `GET /api/resolve/{number}` — run resolver chain
- `GET/POST/PUT/DELETE /api/contacts` — contact CRUD
- `GET /api/calls` — paginated aggregated call history
- `GET /api/pbx/status` — live line/trunk states
- `GET /api/i18n/translations` — load translations once (not on polling intervals)

GUI routes serve Jinja2 templates from `src/gui/templates/`. Translations are in `src/i18n/translations.py` (English + German).

## Web Scraping Resolvers

Tellows, DasTelefonbuch, and KlarTelefonbuch use `aiohttp` + `BeautifulSoup4`. All results are cached in SQLite with a configurable TTL. The spam threshold for Tellows is score ≥ 7.

## Home Assistant Addon

`config.yaml` is the HA addon manifest (not the application config). The app runs on port 8080 with HA ingress support. Multi-arch Docker builds (amd64, aarch64, armv7, armhf, i386) are triggered on GitHub release via `.github/workflows/build.yml`.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**phone-logger — Cleanup & Sanitize**

phone-logger ist ein FastAPI-basierter Telefon-Call-Monitor, der Anrufereignisse vom Fritz!Box Callmonitor empfängt, Nummern über eine Resolver-Chain (SQLite, Tellows, DasTelefonbuch u.a.) auflöst und Ergebnisse via MQTT, Webhooks und SQLite persistiert. Das System läuft als Home Assistant Add-on und hat eine eigene Web-UI für Monitoring und Kontaktverwaltung.

Dieses Milestone konzentriert sich auf **Cleanup & Sanitize** — keine neuen Features, sondern Verbesserung der Codebase-Qualität, Test-Coverage, Dev-Tooling und Dependency-Hygiene.

**Core Value:** Der Pipeline-Kern (Normalisierung → Resolver → Output) muss zuverlässig und klar nachvollziehbar bleiben — das ist die einzige Garantie, die zählt.

### Constraints

- **Kompatibilität**: Alle bestehenden 201 Tests müssen weiterhin grün bleiben
- **Keine Breaking Changes**: Keine Änderungen an MQTT-Topic-Format, Webhook-Payload, API-Schemas oder Config-Struktur
- **uv**: Dependency-Management ausschließlich via uv (kein pip direkt)
- **Python 3.12+**: Keine Features verwenden, die Python 3.12 nicht unterstützt
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12+ - Application runtime, all core logic, adapters, API
- YAML - Configuration files (`config.yaml`, `config.dev.yaml`), addon manifest
- SQL - Database schema in `src/db/schema.sql`
- HTML/Jinja2 - Web UI templates in `src/gui/templates/`
- JSON - Configuration options, API payloads, serialized data
## Runtime
- Python 3.12+ (minimum specified in `pyproject.toml`)
- uv - Modern Python package manager (specified in Dockerfile)
- Lockfile: `uv.lock` (present, frozen dependencies)
## Frameworks
- FastAPI 0.115.6+ - HTTP API framework and web server
- Uvicorn 0.34.0+ - ASGI application server (includes standard extras: uvloop, httptools)
- Jinja2 3.1.5+ - Template engine for GUI routes
- Pydantic 2.10.4+ - Data validation and settings management (with pydantic-settings 2.7.1+)
- aiohttp 3.11.11+ - Async HTTP client for web scraping resolvers and webhooks
- aiomqtt 2.3.0+ - MQTT client for broker communication
- aiosqlite 0.20.0+ - Async SQLite database driver
- httpx 0.28.1+ - Async HTTP client (fallback/alternative to aiohttp)
- BeautifulSoup4 4.12.3+ - HTML parsing for Tellows, DasTelefonbuch, KlarTelefonbuch
- lxml 5.3.0+ - XML/HTML parser backend for BeautifulSoup
- PyYAML 6.0.2+ - YAML parsing for config files
- python-multipart 0.0.20+ - Multipart form data parsing for FastAPI uploads
## Key Dependencies
- FastAPI - Provides REST API, WebSocket support, OpenAPI documentation, ingress middleware
- Pydantic - Data validation for config, events, API models
- aiosqlite - Async database access for contacts, cache, call logs, calls history
- aiohttp - Web scraping and webhook HTTP requests
- Uvicorn - Production ASGI server with standard features (WebSocket, lifespan)
- aiomqtt - MQTT connectivity for input triggers and output publishing
- BeautifulSoup4 + lxml - HTML parsing for German phone directories (Tellows, DasTelefonbuch, KlarTelefonbuch)
## Configuration
- Configuration loaded from `PHONE_LOGGER_CONFIG` env var (path to YAML file)
- Fallback to HA addon options at `/data/options.json` (HA addon environment)
- Fallback to `config.yaml` in project root
- Fallback to built-in defaults in `src/config.py`
- `Dockerfile` - Multi-stage build using HA base image (Python 3.12 Alpine), installs build deps, runs `uv sync --frozen --no-dev`
- `build.yaml` - Build configuration for HA CI (specifies build targets)
- `pyproject.toml` - Project metadata, dependencies, dev dependencies (pytest, pytest-asyncio), pytest config
## Platform Requirements
- Python 3.12+
- uv package manager
- Build tools: gcc, musl-dev, libxml2-dev, libxslt-dev, python3-dev (for lxml compilation)
- Fritz!Box with Callmonitor enabled (dial #96*5* on Fritz!Box)
- Home Assistant add-on environment (HA 2024.x+)
- Access to Home Assistant API (via `homeassistant_api: true` in manifest)
- MQTT broker (optional, for MQTT input/output adapters)
- Network access to phone resolver services (Tellows.de, DasTelefonbuch.de, KlarTelefonbuch.de)
- Network access to Fritz!Box on port 1012 (Callmonitor TCP)
## Testing
- pytest 8.3.4+ - Test runner
- pytest-asyncio 0.24.0+ - Async test support
- Configuration: `asyncio_mode = "auto"` in `pyproject.toml` (auto-detection of async tests)
# Install dependencies
# Run all tests
# Run a single test file
# Run a specific test
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Lowercase with underscores: `phone_number.py`, `fritz_callmonitor.py`
- Adapter implementations follow pattern: `<service>_<adapter_type>.py` (e.g., `tellows.py`, `sqlite_db.py`)
- Test files prefixed with `test_` (e.g., `test_pbx.py`, `test_phone_number.py`)
- snake_case for all functions: `normalize()`, `enrich_event()`, `get_line_state()`
- Private/internal functions prefixed with underscore: `_on_event()`, `_setup_resolver_adapters()`, `_is_internal()`
- Helper functions in tests prefixed with underscore: `_make_pbx_config()`, `_make_ring_event()`, `_inject_client()`
- Properties use @property decorator: `rest_input`, `adapters`, `status`
- snake_case for all variables: `call_log_registered`, `norm_updates`, `connection_id`
- Constants in UPPERCASE: `TERMINAL_STATES`, `ANONYMOUS`, `DEFAULT_DATA_PATH`
- Private instance attributes prefixed with underscore: `_status`, `_connected`, `_input_adapters`, `_mqtt_adapters`, `_resolve_cache`
- Dictionary unpacking for config/defaults: `defaults.update(overrides)` pattern in test builders
- Enum classes defined as PascalCase: `CallDirection`, `CallEventType`, `LineStatus`, `NumberType`
- Enum values as lowercase strings: `INBOUND = "inbound"`, `IDLE = "idle"`
- Pydantic BaseModel subclasses in PascalCase: `CallEvent`, `ResolveResult`, `PipelineResult`, `LineState`
## Code Style
- No explicit formatter configured (no `.prettierrc`, `.black`, `.ruff.toml` in root)
- Uses implicit Python defaults: 4-space indentation, line wrapping as needed
- Import statements not automatically enforced but followed naturally
- Ruff cache present (`.ruff_cache/`) but no explicit config in `pyproject.toml`
- No `.flake8`, `.pylint`, or similar config files
- Code adheres to PEP 8 style conventions naturally
## Import Organization
- No path aliases configured (no `jsconfig.json` or `tsconfig.json` equivalents in Python)
- All imports use full relative paths from project root: `from src.adapters.base import ...`
- TYPE_CHECKING used for circular import avoidance: `if TYPE_CHECKING: from src.core.pbx import LineState`
- Empty lines between import groups (standard → third-party → local)
- Single-line imports preferred: `from src.core.event import CallEvent` not multiple lines
## Error Handling
- Try-except blocks used around external operations (file I/O, network, DB):
- Broad `Exception` catch with logging (not silent failures)
- `logger.exception()` used when catching errors (includes traceback)
- RuntimeError raised for application state violations: `raise RuntimeError("Application not initialized")`
- HTTPException (FastAPI) used for API endpoints: `raise HTTPException(status_code=404, detail="...")`
- Pydantic validation errors allowed to propagate (config validation)
- asyncio.CancelledError explicitly caught and re-raised/handled in async contexts
- Specific exception types caught when needed (e.g., `asyncio.TimeoutError`, `json.JSONDecodeError`)
- `src/core/pipeline.py:85-88` — Try/except with logging around adapter.start()
- `src/adapters/mqtt.py:171-220` — Multiple exception handlers for different failure modes
- `src/adapters/input/fritz_callmonitor.py:115-121` — Catch and log parse failures
## Logging
- Every module gets: `logger = logging.getLogger(__name__)`
- Adapter instances get per-adapter logger: `self.logger = logging.getLogger(f"{__name__}.{self.name}")`
- Log levels used correctly:
- String formatting with % operator: `logger.info("Value: %s", value)` (not f-strings for logger calls)
- Multiple arguments passed as tuple, not single formatted string
## Comments
- Class-level docstrings explaining purpose and public interface (always)
- Function-level docstrings explaining parameters, returns, and exceptions (always for public methods)
- Inline comments sparingly — code should be self-explanatory
- Comments explain *why*, not *what* the code does
- Examples in docstrings for complex utilities (see `src/core/phone_number.py`)
- Not used (Python project, not TypeScript)
- Google-style docstrings in some modules (Args, Returns, Examples sections)
- Pydantic Field descriptions used in models: `Field(..., description="...")`
## Function Design
- Positional parameters for required inputs: `resolve(number)`
- Keyword-only parameters for options: `async def handle(..., *, line_state=None)`
- Type hints required: `def normalize(number: str, country_code: str = "49") -> str:`
- Callbacks use generic Callable types: `Callable[[CallEvent], Coroutine]`
- Functions return None explicitly: `async def stop(self) -> None:`
- Optional returns use `Optional[Type]`: `async def resolve(self, number: str) -> Optional[ResolveResult]:`
- Model objects returned as Pydantic BaseModel instances
- Multiple returns via unpacking (rare) or via method chaining (common for adapters)
## Module Design
- All public classes and functions in `__all__` (if defined) or implicitly by being top-level
- No barrel files (no `__init__.py` re-exports beyond `from . import submodule`)
- Adapter implementations imported explicitly in pipeline: `from src.adapters.input.fritz_callmonitor import FritzCallmonitorAdapter`
- `src/adapters/__init__.py`, `src/adapters/input/__init__.py`, etc. exist but are empty or minimal
- No re-exporting from `__init__.py` — clients import directly from implementation modules
- `src/core/__init__.py` — Empty
- `src/adapters/base.py` — Defines abstract base classes
- `src/adapters/input/fritz_callmonitor.py` — Concrete implementation (imported directly)
## Async Patterns
- All I/O operations are async: `async def start()`, `async def resolve()`, `async def handle()`
- `await` used consistently when calling async functions
- `await asyncio.gather()` used for parallel execution when needed
- Task creation via `asyncio.create_task()` for background operations (e.g., auto-reset timer in PBX)
## Type Annotations
- Use `Optional[Type]` for optional values (not `Type | None`)
- Use `list[Type]` (PEP 585, Python 3.9+) not `List[Type]`
- Use `dict[Key, Value]` not `Dict[Key, Value]`
- TYPE_CHECKING guards for circular imports and forward references
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- **Adapter pattern**: Three distinct adapter types (input, resolver, output) with pluggable implementations
- **Chain-of-Responsibility**: Resolvers form an ordered chain where the first successful result wins
- **State machine**: PBX line FSM tracks per-line state transitions (IDLE → RING/CALL → TALKING → FINISHED/MISSED/NOT_REACHED)
- **Event-driven async**: FastAPI/asyncio for concurrent event handling, aiosqlite for non-blocking database access
- **Enrichment pipeline**: Events pass through normalization, PBX enrichment, resolution, and output stages with mutation at each step
## Layers
- Purpose: Acquire call events from external sources (Fritz!Box TCP, REST API, MQTT)
- Location: `src/adapters/input/` and `src/adapters/mqtt.py`
- Contains: Concrete input adapters that produce `CallEvent` objects
- Depends on: `BaseInputAdapter`, `CallEvent` models
- Used by: Pipeline calls `adapter.start(callback)` to listen for events
- Purpose: Standardize phone numbers to E.164 format with country/area code expansion
- Location: `src/core/phone_number.py`
- Contains: `normalize()`, `to_dialable()`, `to_local()`, `to_scrape_format()` functions
- Depends on: Country code and local area code from config
- Used by: Pipeline applies normalization before enrichment and resolution
- Purpose: Enrich events with PBX infrastructure data (line IDs, device information, MSN resolution)
- Location: `src/core/pbx.py` — `PbxStateManager.enrich_event()` and `update_state()`
- Contains: Event enrichment logic, device/MSN lookups, FSM state machine
- Depends on: `CallEvent`, PbxConfig (devices, MSNs, trunks), LineState
- Used by: Pipeline calls `pbx.enrich_event()` then `pbx.update_state()` before resolution
- Purpose: Look up caller/called party names and metadata through a chain of resolvers
- Location: `src/adapters/resolver/` — base class, chain implementation, and concrete resolvers
- Contains: `BaseResolverAdapter`, `ResolverChain` (chain-of-responsibility), implementations for JSON files, SQLite cache, web scrapers (Tellows, DasTelefonbuch, KlarTelefonbuch), and MSN/contact database
- Depends on: `ResolveResult` model, `Database`, adapter configuration
- Used by: Pipeline calls `resolver_chain.resolve(number)` for RING/CALL events; result is cached per `line_id`
- Purpose: Persist events and dispatch them to external systems (database, webhooks, MQTT)
- Location: `src/adapters/output/` and `src/adapters/mqtt.py`
- Contains: Concrete output adapters implementing `BaseOutputAdapter`
- Depends on: `CallEvent`, `ResolveResult`, `LineState`, adapter configuration
- Used by: Pipeline calls `adapter.handle(event, result, line_state=state)` after resolution
- Purpose: Expose HTTP endpoints for external access to resolve, contacts, call history, and PBX status
- Location: `src/api/` — `app.py` (FastAPI setup), `routes/` (endpoint definitions), `models.py` (response schemas)
- Contains: GET/POST/PUT/DELETE endpoints for contacts, calls, cache, PBX status, translations, and direct resolution triggers
- Depends on: Pipeline, Database, PbxStateManager for data access
- Used by: Web browser (GUI), external integrations
- Purpose: Serve web UI for monitoring and management
- Location: `src/gui/routes.py` (page templates), `src/gui/templates/`, `src/gui/static/`
- Contains: Jinja2 template routes and static assets
- Depends on: Fastapi router, template files
- Used by: Browser requests to `/`, `/pbx`, `/contacts`, `/calls`, `/cache`, `/config`
- Purpose: Persist call history, contacts, resolver cache, and raw event logs
- Location: `src/db/database.py`, `src/db/schema.sql`
- Contains: Async SQLite wrapper with schema initialization and migrations
- Depends on: aiosqlite, schema definitions, UUIDv7 generator
- Used by: Pipeline for logging, resolvers for caching, output adapters for storage
- Purpose: Load and validate application configuration from YAML (dev), HA options.json (production), or defaults
- Location: `src/config.py`
- Contains: Pydantic models for all config sections (adapters, PBX, phone, database)
- Depends on: YAML, JSON parsing
- Used by: Main entry point to bootstrap the application
## Data Flow
- `LineState`: In-memory representation of a single PBX line; includes caller/called numbers, devices, direction, status, and last-changed timestamp
- `LineFSM`: Per-line finite state machine with fault-tolerant invalid-transition handling
- `PbxStateManager`: Manages all FSMs, holds MSN/device lookups, pre-computes E.164 representations of configured MSNs
- `_resolve_cache` (in Pipeline): Transient dict mapping `line_id` → `ResolveResult` to bridge RING/CALL resolution to CONNECT/DISCONNECT output
## Key Abstractions
- Purpose: Normalized representation of a call event
- Location: `src/core/event.py`
- Pattern: Pydantic BaseModel with optional fields for enrichment
- Fields: `number`, `direction`, `event_type`, `timestamp`, `source` (input adapter), `connection_id`, `extension`, `caller_number`, `called_number`, `line_id`, `trunk_id`, `caller_device`, `called_device`, `raw_input`
- Purpose: Result of a phone number lookup with metadata
- Location: `src/core/event.py`
- Pattern: Pydantic BaseModel; computed property `is_spam` for spam_score >= 7
- Fields: `number`, `name`, `tags`, `notes`, `spam_score`, `source` (resolver adapter), `cached` (boolean)
- Purpose: Contract for acquiring call events
- Location: `src/adapters/base.py`
- Pattern: Abstract base class with concrete implementations
- Methods: `start(callback)` to begin listening, `stop()` to cease
- Implementations: `FritzCallmonitorAdapter` (TCP/1012), `RestInputAdapter` (HTTP POST), `MqttAdapter` (MQTT subscribe)
- Purpose: Contract for resolving phone numbers
- Location: `src/adapters/base.py`
- Pattern: Abstract base class with optional `start()`/`stop()` for resource initialization
- Methods: `resolve(number)` → `Optional[ResolveResult]`
- Implementations: `JsonFileResolver`, `SqliteResolver`, `TellowsResolver`, `DasTelefonbuchResolver`, `KlarTelefonbuchResolver`, `MsnResolver`
- Purpose: Contract for processing resolved events
- Location: `src/adapters/base.py`
- Pattern: Abstract base class with lifecycle methods
- Methods: 
- Implementations: `CallLogOutputAdapter` (SQLite storage), `WebhookOutputAdapter` (HTTP POST), `MqttAdapter` (MQTT publish)
- Purpose: Chain-of-Responsibility implementation for resolver selection
- Location: `src/adapters/resolver/chain.py`
- Pattern: Maintains ordered list of resolvers; iterates until first success
- Methods: `resolve(number)` iterates adapters, catches exceptions, logs outcomes
- Purpose: Main orchestrator of input → resolve → output flow
- Location: `src/core/pipeline.py`
- Pattern: Singleton-like (created in main.py, accessed via `get_pipeline()`)
- Key state:
- Key methods:
- Purpose: Track per-line state and enrich events with PBX data
- Location: `src/core/pbx.py`
- Pattern: Stateful object initialized with PbxConfig; maintains in-memory FSMs and LineStates
- Key state:
- Key methods:
## Entry Points
- Location: `src/main.py`
- Triggers: `uvicorn` server start
- Responsibilities: 
- Fritz!Box: `FritzCallmonitorAdapter.start()` opens TCP connection to Fritz!Box port 1012; parses newline-delimited event strings
- REST: `RestInputAdapter.start()` (implicit via routes); API endpoints trigger events via `adapter.trigger()`
- MQTT: `MqttAdapter.start()` subscribes to configured topics and generates events from messages
- `/api/resolve/{number}` — POST request through REST input adapter (triggers event pipeline)
- `/api/contacts` — CRUD operations on contact database
- `/api/calls` — Query aggregated call history
- `/api/pbx/status` — Full PBX state snapshot
- `/api/pbx/lines` — Current line states with display names
- GUI routes (`/`, `/pbx`, `/contacts`, `/calls`, `/cache`, `/config`) — Jinja2 templates
## Error Handling
- **Input adapter failures**: Logged and suppressed; reconnection attempt after delay (Fritz!Box TCP has exponential backoff)
- **Resolver failures**: Logged and skipped; chain continues to next adapter
- **Output adapter failures**: Logged and suppressed; other adapters still process the event
- **FSM invalid transitions**: Logged as warning; line reset to IDLE and transition retried from idle
- **Phone normalization failures**: Returns best-effort result (digits without formatting) or original input if parsing fails
- **Database operations**: Exceptions logged; some operations are best-effort (e.g., raw event logging failures don't block pipeline)
## Cross-Cutting Concerns
- All modules use Python `logging` module
- Adapter instances create loggers at `__name__.{adapter.name}` for granular control
- Pipeline logs event reception, routing, and error conditions
- Pydantic models validate all config and event data at parsing time
- Input adapters parse/normalize before producing CallEvent
- Database operations validate presence of required fields (e.g., number for resolution)
- REST input adapter supports optional Bearer token (in webhook config)
- PBX status and contact CRUD are unauthenticated (assumed running behind Home Assistant addon sandbox)
- Home Assistant integration (custom component) handles addon authorization at integration level
- Resolver cache in Pipeline memory (`_resolve_cache` per line_id)
- Resolver-specific caches in SQLite (Tellows, DasTelefonbuch with configurable TTL)
- No cache invalidation strategy except TTL or explicit cache clear endpoint
- UTC for all timestamps internally (`datetime.now(UTC)`)
- Timezone config in Fritz!Box adapter for interpreting Callmonitor timestamps
- Home Assistant UI displays times in user's configured timezone
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
