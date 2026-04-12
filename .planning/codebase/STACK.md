# Technology Stack

**Analysis Date:** 2026-04-13

## Languages

**Primary:**
- Python 3.12+ - Application runtime, all core logic, adapters, API
- YAML - Configuration files (`config.yaml`, `config.dev.yaml`), addon manifest
- SQL - Database schema in `src/db/schema.sql`

**Secondary:**
- HTML/Jinja2 - Web UI templates in `src/gui/templates/`
- JSON - Configuration options, API payloads, serialized data

## Runtime

**Environment:**
- Python 3.12+ (minimum specified in `pyproject.toml`)

**Package Manager:**
- uv - Modern Python package manager (specified in Dockerfile)
- Lockfile: `uv.lock` (present, frozen dependencies)

## Frameworks

**Core:**
- FastAPI 0.115.6+ - HTTP API framework and web server
- Uvicorn 0.34.0+ - ASGI application server (includes standard extras: uvloop, httptools)
- Jinja2 3.1.5+ - Template engine for GUI routes
- Pydantic 2.10.4+ - Data validation and settings management (with pydantic-settings 2.7.1+)

**Async/Event Processing:**
- aiohttp 3.11.11+ - Async HTTP client for web scraping resolvers and webhooks
- aiomqtt 2.3.0+ - MQTT client for broker communication
- aiosqlite 0.20.0+ - Async SQLite database driver
- httpx 0.28.1+ - Async HTTP client (fallback/alternative to aiohttp)

**Web Scraping:**
- BeautifulSoup4 4.12.3+ - HTML parsing for Tellows, DasTelefonbuch, KlarTelefonbuch
- lxml 5.3.0+ - XML/HTML parser backend for BeautifulSoup

**Configuration:**
- PyYAML 6.0.2+ - YAML parsing for config files
- python-multipart 0.0.20+ - Multipart form data parsing for FastAPI uploads

## Key Dependencies

**Critical:**
- FastAPI - Provides REST API, WebSocket support, OpenAPI documentation, ingress middleware
- Pydantic - Data validation for config, events, API models
- aiosqlite - Async database access for contacts, cache, call logs, calls history
- aiohttp - Web scraping and webhook HTTP requests

**Infrastructure:**
- Uvicorn - Production ASGI server with standard features (WebSocket, lifespan)
- aiomqtt - MQTT connectivity for input triggers and output publishing
- BeautifulSoup4 + lxml - HTML parsing for German phone directories (Tellows, DasTelefonbuch, KlarTelefonbuch)

## Configuration

**Environment:**
- Configuration loaded from `PHONE_LOGGER_CONFIG` env var (path to YAML file)
- Fallback to HA addon options at `/data/options.json` (HA addon environment)
- Fallback to `config.yaml` in project root
- Fallback to built-in defaults in `src/config.py`

**Build:**
- `Dockerfile` - Multi-stage build using HA base image (Python 3.12 Alpine), installs build deps, runs `uv sync --frozen --no-dev`
- `build.yaml` - Build configuration for HA CI (specifies build targets)
- `pyproject.toml` - Project metadata, dependencies, dev dependencies (pytest, pytest-asyncio), pytest config

## Platform Requirements

**Development:**
- Python 3.12+
- uv package manager
- Build tools: gcc, musl-dev, libxml2-dev, libxslt-dev, python3-dev (for lxml compilation)
- Fritz!Box with Callmonitor enabled (dial #96*5* on Fritz!Box)

**Production:**
- Home Assistant add-on environment (HA 2024.x+)
- Access to Home Assistant API (via `homeassistant_api: true` in manifest)
- MQTT broker (optional, for MQTT input/output adapters)
- Network access to phone resolver services (Tellows.de, DasTelefonbuch.de, KlarTelefonbuch.de)
- Network access to Fritz!Box on port 1012 (Callmonitor TCP)

## Testing

**Framework:**
- pytest 8.3.4+ - Test runner
- pytest-asyncio 0.24.0+ - Async test support
- Configuration: `asyncio_mode = "auto"` in `pyproject.toml` (auto-detection of async tests)

**Run Commands:**
```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_file.py -v

# Run a specific test
uv run pytest tests/test_file.py::test_name -v
```

**Location:** Tests in `tests/` directory at project root

---

*Stack analysis: 2026-04-13*
