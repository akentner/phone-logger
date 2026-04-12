# External Integrations

**Analysis Date:** 2026-04-13

## APIs & External Services

**Phone Number Resolvers (Web Scraping):**
- Tellows.de - Spam score lookup via reverse number search
  - SDK/Client: aiohttp, BeautifulSoup4
  - URL: `https://www.tellows.de/num/{E164_number}`
  - Implementation: `src/adapters/resolver/tellows.py`
  - Caching: SQLite with configurable TTL (default 7 days)
  - Auth: None (public web scraping)

- DasTelefonbuch.de - German business/private phone directory lookup
  - SDK/Client: aiohttp, BeautifulSoup4
  - URL: `https://www.dastelefonbuch.de/Rückwärtssuche/{national_number}`
  - Implementation: `src/adapters/resolver/dastelefon.py`
  - Caching: SQLite with configurable TTL (default 30 days)
  - Auth: None (public web scraping)

- KlarTelefonbuch.de - German phone directory reverse lookup
  - SDK/Client: aiohttp, BeautifulSoup4
  - URL: `https://www.klartelefonbuch.de/inverssuche/{national_number}`
  - Implementation: `src/adapters/resolver/klartelbuch.py`
  - Caching: SQLite with configurable TTL (default 30 days)
  - Auth: None (public web scraping)

**Fritz!Box Integration:**
- Fritz!Box Callmonitor - TCP event stream on port 1012
  - Protocol: Plain TCP, semicolon-separated events
  - Implementation: `src/adapters/input/fritz_callmonitor.py`
  - Events: RING, CALL, CONNECT, DISCONNECT with timestamps, numbers, extension, SIP trunk info
  - Connection: TCP stream with automatic reconnection (configurable delay)
  - Auth: None (local network, unauthenticated)
  - Configuration: Host/port in config, requires #96*5* to be dialed on Fritz!Box to enable

## Data Storage

**Databases:**
- SQLite (file-based, async via aiosqlite)
  - Location: Configurable via `data_path` config (default: `/addons_config/phone-logger` or `./data`)
  - File: `phone_logger.db`
  - Client: `aiosqlite` (async)
  - ORM: None (raw SQL with connection.execute)
  - Schema: 6 tables (`contacts`, `cache`, `call_log`, `calls`, `raw_events`, `_migrations`)
  - Features: WAL mode enabled, foreign keys enabled, UUIDv7 primary keys for calls

**Tables:**
- `contacts` - Contact directory (name, number, type, tags, spam_score, source)
- `cache` - Resolver result cache (adapter + number + result_json + TTL)
- `call_log` - Raw call events log (number, direction, event_type, timestamp)
- `calls` - Aggregated call history by connection_id (status, devices, duration, line_id, MSN, trunk_id)
- `raw_events` - Raw input data for debugging (source, raw_input, raw_event_json)

**File Storage:**
- JSON file - `contacts.json` for local contact import/export
  - Location: Configurable in config (default: `contacts.json`)
  - Usage: Optional resolver adapter for static contact lookup
  - Implementation: `src/adapters/resolver/json_file.py`

**Caching:**
- SQLite cache table - Result caching with per-adapter TTL (7-30 days)
- Implementation: Automatic via resolver adapters, managed in `src/adapters/resolver/base.py`

## Authentication & Identity

**Auth Provider:**
- Custom/None - No centralized auth provider
  - Webhooks: Optional bearer token via `token` config field (Basic Auth not implemented)
  - MQTT: Optional username/password in broker config
  - Home Assistant: API access via Home Assistant addon context (`homeassistant_api: true`)
  - REST input: No auth required (assumes local network)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry/Error tracking service)
- Errors logged to console via Python logging

**Logs:**
- Console logging via Python `logging` module
- Configurable level via `log_level` config (DEBUG, INFO, WARNING, ERROR)
- Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- Setup in: `src/main.py` - `setup_logging()`

**Debugging:**
- Raw event storage in SQLite `raw_events` table for post-event debugging
- Debug logging in resolver adapters (CSS selector matching, request URLs, response sizes)

## CI/CD & Deployment

**Hosting:**
- Home Assistant add-on (containerized, runs on HA host)
- Docker image: Multi-arch build (amd64, aarch64, armv7, armhf, i386)
- Base image: `ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20`
- Port: 8080 (HTTP, with ingress support for HA UI)
- Entry point: `uv run --no-dev python -m src.main`

**CI Pipeline:**
- GitHub Actions: `.github/workflows/build.yml` (triggered on release)
- Publishes multi-arch Docker images to GitHub Container Registry (ghcr.io)
- Build configuration: `build.yaml` (HA-specific build manifest)

**Deployment:**
- HA add-on environment: Options loaded from `/data/options.json`
- Add-on manifest: `config.yaml` (version, icon, ingress settings, option schema)
- Add-on slug: `phone-logger`

## Environment Configuration

**Required env vars:**
- `PHONE_LOGGER_CONFIG` (optional) - Path to YAML config file (otherwise falls back to `/data/options.json` or `config.yaml`)
- `LOG_LEVEL` (optional) - Override logging level (DEBUG, INFO, WARNING, ERROR)

**HA Addon Environment:**
- `homeassistant_api: true` - Access to HA API for integration
- `ingress: true` - Panel access via HA UI ingress proxy
- `X-Ingress-Path` header middleware support for root_path handling

## Webhooks & Callbacks

**Incoming:**
- `/api/resolve/{number}` (GET) - Synchronous resolver chain execution
- `POST /api/resolve` - Webhook trigger input via REST adapter (call events as JSON)
- MQTT subscribe: `{prefix}/trigger` - JSON call event input

**Outgoing:**
- Webhook output adapter: HTTP POST to configured URLs
  - Fields: `timestamp`, `number`, `caller_display`, `called_display`, `direction`, `event_type`, `resolve_result`, `line_state`
  - Filter: Events matched by event type (ring, call, connect, disconnect, state:*)
  - Headers: `Content-Type: application/json`, optional `Authorization: Bearer {token}`
  - Implementation: `src/adapters/output/webhook.py`

- MQTT output: Publish to broker
  - Topics:
    - `{prefix}/status` - Birth/LWT (retained): "online" / "offline"
    - `{prefix}/event` - All events (JSON payload)
    - `{prefix}/event/{event_type}` - Filtered by type
    - `{prefix}/line/{line_id}/state` - Per-line FSM state (retained, on change)
    - `{prefix}/trunk/{trunk_id}/state` - Per-trunk status (retained, on change)
  - Home Assistant Auto Discovery: If enabled (`ha_discovery: true`), publishes MQTT device configs
  - Implementation: `src/adapters/mqtt.py`

## Message Format Examples

**Fritz!Box Callmonitor:**
```
15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0
15.03.26 10:15:02;CONNECT;0;12;
15.03.26 10:15:35;DISCONNECT;0;45
```

**REST/MQTT Trigger Input (JSON):**
```json
{
  "number": "+49123456789",
  "direction": "inbound",
  "event_type": "ring",
  "timestamp": "2026-04-13T10:15:00Z",
  "source": "rest",
  "connection_id": "0",
  "extension": "12"
}
```

**Webhook Outbound Payload:**
```json
{
  "timestamp": "2026-04-13T10:15:00Z",
  "number": "+49123456789",
  "caller_display": "John Doe",
  "called_display": "Office",
  "direction": "inbound",
  "event_type": "ring",
  "resolve_result": {
    "name": "John Doe",
    "number": "+49123456789",
    "number_type": "mobile",
    "tags": ["work"],
    "spam_score": 2,
    "source": "sqlite"
  },
  "line_state": {
    "line_id": 0,
    "status": "ringing",
    "caller_device": {
      "id": "10",
      "name": "EG 24",
      "type": "dect"
    },
    "is_internal": false
  }
}
```

**MQTT Event Payload:**
```json
{
  "timestamp": "2026-04-13T10:15:00Z",
  "number": "+49123456789",
  "direction": "inbound",
  "event_type": "ring",
  "resolve_result": {...},
  "line_state": {...},
  "msn": "990133",
  "short_msn": "**620"
}
```

---

*Integration audit: 2026-04-13*
