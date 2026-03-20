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
