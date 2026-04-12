# Codebase Structure

**Analysis Date:** 2026-04-13

## Directory Layout

```
phone-logger/
├── src/                          # Main application source
│   ├── main.py                   # Entry point, lifespan handlers, route registration
│   ├── config.py                 # Configuration loading and validation
│   ├── core/                     # Core domain logic
│   │   ├── event.py              # Event and result models (CallEvent, ResolveResult)
│   │   ├── pbx.py                # PBX state machine and enrichment
│   │   ├── pipeline.py           # Main orchestrator
│   │   ├── phone_number.py       # E.164 normalization utilities
│   │   └── utils.py              # Helper functions (uuid7, etc.)
│   ├── adapters/                 # Pluggable adapters
│   │   ├── base.py               # Base classes for all adapter types
│   │   ├── input/                # Input adapters
│   │   │   ├── fritz_callmonitor.py  # Fritz!Box TCP listener
│   │   │   └── rest.py              # REST API trigger
│   │   ├── resolver/             # Phone number resolvers
│   │   │   ├── base.py           # Base resolver interface
│   │   │   ├── chain.py          # Chain-of-Responsibility orchestrator
│   │   │   ├── json_file.py      # JSON file-based contacts
│   │   │   ├── sqlite_db.py      # SQLite contact cache
│   │   │   ├── msn.py            # PBX MSN resolver
│   │   │   ├── tellows.py        # Tellows web scraper
│   │   │   ├── dastelefon.py     # DasTelefonbuch web scraper
│   │   │   └── klartelbuch.py    # KlarTelefonbuch web scraper
│   │   ├── output/               # Output adapters
│   │   │   ├── base.py           # Base output interface
│   │   │   ├── call_log.py       # SQLite call logging
│   │   │   └── webhook.py        # HTTP webhook dispatcher
│   │   └── mqtt.py               # MQTT input/output adapter (dual-use)
│   ├── db/                       # Database layer
│   │   ├── database.py           # SQLite async wrapper
│   │   └── schema.sql            # Database schema and migrations
│   ├── api/                      # REST API layer
│   │   ├── app.py                # FastAPI app initialization
│   │   ├── models.py             # API response models
│   │   └── routes/               # Endpoint implementations
│   │       ├── resolve.py        # GET /api/resolve/{number}
│   │       ├── contacts.py       # Contact CRUD endpoints
│   │       ├── calls.py          # Call history endpoints
│   │       ├── cache.py          # Resolver cache management
│   │       ├── config.py         # Configuration endpoints
│   │       ├── pbx.py            # PBX status endpoints
│   │       └── i18n.py           # Translations endpoint
│   ├── gui/                      # Web UI layer
│   │   ├── routes.py             # Jinja2 template routes
│   │   ├── templates/            # HTML templates
│   │   │   ├── pbx.html
│   │   │   ├── contacts.html
│   │   │   ├── calls.html
│   │   │   ├── cache.html
│   │   │   ├── config.html
│   │   │   └── base.html
│   │   └── static/               # CSS, JS assets
│   │       ├── css/
│   │       └── js/
│   └── i18n/                     # Internationalization
│       └── translations.py       # English + German translations
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest configuration and fixtures
│   ├── test_pbx.py               # PBX FSM and state tests
│   ├── test_pipeline_enrichment.py  # Full pipeline flow tests
│   ├── test_resolver_chain.py    # Resolver chain tests
│   ├── test_phone_number.py      # Normalization tests
│   ├── test_msn_resolver.py      # MSN resolver tests
│   ├── test_fritz_parser.py      # Fritz!Box Callmonitor parser tests
│   ├── test_call_aggregation.py  # Call history aggregation tests
│   ├── test_output_line_state.py # Output adapter line state tests
│   ├── test_mqtt_output.py       # MQTT adapter tests
│   ├── test_idle_notification.py # Auto-reset notification tests
│   ├── test_anonymous_calls.py   # Anonymous call handling
│   ├── test_api.py               # API endpoint tests
│   ├── test_raw_events.py        # Raw event logging tests
│   └── data/                     # Test fixtures (if any)
├── config.dev.yaml               # Development configuration (Fritz disabled, REST enabled)
├── config.yaml                   # Production template (Fritz enabled)
├── config.dev.yaml.example       # Example config with all options documented
├── pyproject.toml                # Project metadata and dependencies
├── uv.lock                       # Locked dependency versions
├── Dockerfile                    # Container image
├── Taskfile.yml                  # Task automation (dev, test, release)
├── CLAUDE.md                     # Project-specific AI instructions
├── README.md                     # User documentation
├── CHANGELOG.md                  # Version history
├── AGENTS.md                     # GSD agent patterns and workflows
└── .planning/
    └── codebase/                 # Codebase analysis documents (generated)
        ├── ARCHITECTURE.md       # This file's sibling
        ├── STRUCTURE.md          # This file
        ├── CONVENTIONS.md        # Code style and patterns
        ├── TESTING.md            # Test organization and patterns
        ├── STACK.md              # Technology stack
        ├── INTEGRATIONS.md       # External service integrations
        └── CONCERNS.md           # Technical debt and issues
```

## Directory Purposes

**`src/`:**
- Purpose: All application source code
- Contains: Python modules organized by functional layer
- Key structure: Core logic → adapters → API/GUI → database

**`src/core/`:**
- Purpose: Domain models and core business logic (event definitions, PBX FSM, pipeline orchestration)
- Contains: Event models, phone number normalization, PBX state machine
- Key files: `event.py`, `pbx.py`, `pipeline.py`, `phone_number.py`

**`src/adapters/`:**
- Purpose: Plugin implementations for input, resolution, and output
- Contains: Base classes and concrete adapter implementations
- Key structure: `base.py` defines interfaces; `input/`, `resolver/`, `output/` contain implementations

**`src/adapters/input/`:**
- Purpose: Event sources (Fritz!Box, REST API)
- Contains: Input adapter implementations
- Key files: `fritz_callmonitor.py` (TCP listener), `rest.py` (API trigger)
- Note: MQTT is dual-use (input/output), located at `src/adapters/mqtt.py`

**`src/adapters/resolver/`:**
- Purpose: Phone number lookup implementations
- Contains: Base class, chain orchestrator, and concrete resolvers
- Key files: `base.py` (interface), `chain.py` (orchestrator), plus JSON, SQLite, web scraper implementations
- Pattern: All resolvers inherit from `BaseResolverAdapter` and implement `resolve(number) → Optional[ResolveResult]`

**`src/adapters/output/`:**
- Purpose: Event sink implementations (database logging, webhooks)
- Contains: Output adapter implementations
- Key files: `base.py` (interface), `call_log.py` (SQLite), `webhook.py` (HTTP POST)
- Note: MQTT output is also at `src/adapters/mqtt.py` (handles both input and output)

**`src/db/`:**
- Purpose: Database abstraction and schema
- Contains: Async SQLite wrapper and schema definitions
- Key files: `database.py` (async wrapper), `schema.sql` (table definitions and migrations)
- Tables: `contacts`, `cache`, `call_log`, `calls`, `raw_events`

**`src/api/`:**
- Purpose: REST API layer
- Contains: FastAPI app setup, endpoint routes, response models
- Key files: `app.py` (FastAPI instance), `models.py` (Pydantic response schemas), `routes/` (endpoint handlers)
- Route groups: `/api/resolve`, `/api/contacts`, `/api/calls`, `/api/pbx`, `/api/cache`, `/api/config`, `/api/i18n`

**`src/gui/`:**
- Purpose: Web user interface
- Contains: Jinja2 templates and static assets
- Key files: `routes.py` (template routes), `templates/` (HTML files), `static/` (CSS/JS)
- Pages: PBX status, contacts, call history, cache, configuration

**`src/i18n/`:**
- Purpose: Internationalization/translations
- Contains: English and German translations for UI and API
- Key files: `translations.py` (translation dict)

**`tests/`:**
- Purpose: Test suite using pytest with asyncio support
- Contains: Unit and integration tests organized by functional area
- Key files: `conftest.py` (pytest setup), individual test files, and optional `data/` for fixtures
- Test pattern: Class-based test organization with descriptive method names

**`config.*.yaml`:**
- Purpose: Application configuration
- `config.dev.yaml`: Development config (Fritz disabled, REST enabled, local database)
- `config.yaml`: Production template for HA addon deployment
- `config.dev.yaml.example`: Fully documented example with all options

## Key File Locations

**Entry Points:**
- `src/main.py`: Application startup and route registration
- `uvicorn` target: `src.main:app` (configured in Taskfile)

**Configuration:**
- `src/config.py`: Config models and loading logic
- `config.dev.yaml`: Development configuration (checked into repo)
- `config.yaml`: Production template

**Core Logic:**
- `src/core/pipeline.py`: Main orchestrator (Input → Resolve → Output)
- `src/core/pbx.py`: PBX state machine and event enrichment
- `src/core/event.py`: Event and result models

**Database:**
- `src/db/database.py`: Async SQLite wrapper
- `src/db/schema.sql`: Schema and migrations
- Database path configured in config; defaults to `{data_path}/phone-logger.db`

**Testing:**
- `tests/conftest.py`: Pytest configuration
- `tests/test_*.py`: Test files by functional area
- Run: `uv run pytest tests/ -v`

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `fritz_callmonitor.py`)
- Test files: `test_<feature>.py` (e.g., `test_pbx.py`, `test_pipeline_enrichment.py`)
- Template files: `<page>.html` (e.g., `pbx.html`, `contacts.html`)
- Configuration files: `config*.yaml` (e.g., `config.dev.yaml`, `config.yaml`)

**Directories:**
- Functional grouping: `<layer>/<type>/` (e.g., `adapters/input/`, `adapters/resolver/`)
- Lowercase with underscores (e.g., `call_log`, `raw_events`)

**Classes:**
- PascalCase for all classes (e.g., `FritzCallmonitorAdapter`, `ResolveResult`)
- Adapter classes follow pattern: `<Source><Type>Adapter` (e.g., `FritzCallmonitorAdapter`, `WebhookOutputAdapter`)
- Model classes: `<Entity><Suffix>` (e.g., `CallEvent`, `ResolveResult`, `LineState`)

**Functions:**
- snake_case for all functions (e.g., `normalize()`, `get_line_state()`)
- Private functions: Leading underscore (e.g., `_on_event()`, `_setup_resolver_adapters()`)
- Helper utilities: No special prefix, descriptive names (e.g., `uuid7()`, `to_dialable()`)

**Configuration Keys:**
- snake_case in YAML (e.g., `country_code`, `local_area_code`, `resolver_adapters`)
- Pydantic model fields match YAML keys exactly

**Environment Variables:**
- UPPER_CASE with underscores (e.g., `PHONE_LOGGER_CONFIG`)

**Types & Enums:**
- Enum values: snake_case lowercase (e.g., `CallDirection.INBOUND`, `LineStatus.TALKING`)
- Type hints: Standard Python types and Pydantic models

## Where to Add New Code

**New Resolver (Phone Number Lookup):**
- Primary code: Create `src/adapters/resolver/<name>.py`
- Pattern: Inherit from `BaseResolverAdapter`, implement `async def resolve(number: str) → Optional[ResolveResult]`
- Registration: Add factory entry in `Pipeline._setup_resolver_adapters()` in `src/core/pipeline.py`
- Tests: Create `tests/test_<name>_resolver.py` with test cases
- Configuration: Add `AdapterConfig` entry to default `resolver_adapters` in `src/config.py`
- Example: See `src/adapters/resolver/json_file.py` for simple file-based resolver

**New Input Source (Call Event):**
- Primary code: Create `src/adapters/input/<name>.py`
- Pattern: Inherit from `BaseInputAdapter`, implement `async def start(callback)` and `async def stop()`
- Registration: Add case in `Pipeline._setup_input_adapters()` in `src/core/pipeline.py`
- Tests: Create `tests/test_<name>_input.py`
- Configuration: Add `AdapterConfig` entry to default `input_adapters` in `src/config.py`
- Example: See `src/adapters/input/fritz_callmonitor.py` for TCP-based input

**New Output Adapter (Event Sink):**
- Primary code: Create `src/adapters/output/<name>.py`
- Pattern: Inherit from `BaseOutputAdapter`, implement `async def handle(event, result, *, line_state)` and optional `async def handle_line_state_change(line_state)`
- Registration: Add case in `Pipeline._setup_output_adapters()` in `src/core/pipeline.py`
- Tests: Create `tests/test_<name>_output.py`
- Configuration: Add `AdapterConfig` entry to default `output_adapters` in `src/config.py`
- Example: See `src/adapters/output/webhook.py` for HTTP-based output
- Note: Some output types (call_log) are limited to one instance; check singleton flag in setup

**New API Endpoint:**
- Primary code: Create route in existing file in `src/api/routes/` or new `<feature>.py`
- Pattern: Use FastAPI `@router.get()`, `@router.post()`, etc.; import `get_pipeline()`, `get_db()` from `src.main`
- Response models: Define in `src/api/models.py` as Pydantic BaseModel
- Registration: Include router in `src/main.py` with `app.include_router()`
- Tests: Add test in `tests/test_api.py` or create `tests/test_<feature>_api.py`
- Example: See `src/api/routes/resolve.py` for simple GET endpoint

**New Database Table/Schema:**
- Primary code: Add SQL to `src/db/schema.sql` with CREATE TABLE and indexes
- Async accessor: Add method to `Database` class in `src/db/database.py`
- Migrations: Add migration check in `Database._run_migrations()` for backward compatibility
- Tests: Add integration tests using in-memory SQLite
- Example: See `raw_events` table and `Database.log_raw_event()` method

**New Web Page:**
- Primary code: Create template in `src/gui/templates/<page>.html`
- Route handler: Add route in `src/gui/routes.py` with `@router.get("/<page>")`
- API integration: Use fetch() to call `/api/` endpoints for data
- Styling: Add CSS to `src/gui/static/css/` or existing stylesheet
- Registration: Route is auto-registered via `app.include_router(gui_router)`
- Example: See `src/gui/templates/pbx.html` and `src/gui/routes.py`

**New Test:**
- Location: `tests/test_<feature>.py`
- Pattern: Class-based with descriptive test method names
- Fixtures: Use pytest fixtures from `conftest.py` (e.g., config, database)
- Async: Use `@pytest.mark.asyncio` or rely on `asyncio_mode = "auto"` in pyproject.toml
- Run: `uv run pytest tests/test_<feature>.py -v` or `uv run pytest tests/ -v` for all

## Special Directories

**`.planning/codebase/`:**
- Purpose: Generated codebase analysis documents
- Generated: By `/gsd:map-codebase` command
- Committed: Yes (checked into repo for reference)
- Files: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md

**`.idea/`:**
- Purpose: JetBrains IDE project configuration
- Generated: By IDE (PyCharm)
- Committed: No (in .gitignore, but checked for historical reasons)
- Note: Safe to delete and regenerate

**`.venv/`:**
- Purpose: Python virtual environment
- Generated: By `uv` (uv manages its own cache; .venv not typically used)
- Committed: No (in .gitignore)

**`.pytest_cache/`, `.ruff_cache/`:**
- Purpose: Tool caches
- Generated: By pytest and ruff linter
- Committed: No (in .gitignore)

**`data/`:**
- Purpose: Runtime data (SQLite database, cache files, etc.)
- Generated: At runtime
- Committed: No (in .gitignore)
- Note: Created automatically on first run

**`translations/`:**
- Purpose: Reserved for future localization files (currently unused; translations in code at `src/i18n/translations.py`)
- Generated: No
- Committed: Yes

## Import Organization

**Pattern:** Absolute imports from project root

```python
# External libraries (sorted alphabetically)
import asyncio
from datetime import UTC, datetime

from aiohttp import ClientSession
from fastapi import APIRouter
from pydantic import BaseModel

# Local modules (sorted alphabetically)
from src.adapters.base import BaseInputAdapter
from src.config import AppConfig
from src.core.event import CallEvent
from src.core.pipeline import Pipeline
from src.db.database import Database
```

**Aliases:** None (use full module paths for clarity)

**Path Aliases:** Not configured (use absolute imports from project root)

## Development Workflow

**Running the application:**
```bash
# With development config (Fritz disabled, REST enabled)
PHONE_LOGGER_CONFIG=config.dev.yaml uv run python -m src.main
```

**Running tests:**
```bash
# All tests
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/test_pbx.py -v

# Specific test
uv run pytest tests/test_pbx.py::TestLineFSM::test_idle_to_ring -v

# With coverage
uv run pytest tests/ --cov=src --cov-report=term-missing
```

**Linting and formatting:**
```bash
# Check with Ruff (120-char lines)
uv run ruff check src/ tests/

# Auto-format with Ruff
uv run ruff format src/ tests/
```

**Task automation:**
```bash
# See all tasks
task -l

# Common tasks (from Taskfile.yml)
task dev          # Run with hot-reload (if configured)
task test         # Run all tests
task lint         # Lint all code
```
