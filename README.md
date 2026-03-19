# phone-logger

Home Assistant addon for phone number resolution with Fritz!Box Callmonitor integration.

Unknown phone numbers are resolved through a configurable multi-stage adapter chain (Chain-of-Responsibility pattern). Web lookup results are cached in SQLite. All calls are recorded in a persistent call history.

## Architecture

The system uses a symmetric adapter concept across three layers:

```
┌─────────────────────────────────────────────────────────┐
│                    INPUT ADAPTERS                       │
│  Fritz Callmonitor (TCP)  │  REST API  │  MQTT (opt.)   │
│                                                         │
│                 ┌─────▼────────────▼────┐               │
│                 │   Event Normalizer    │               │
│                 └─────────┬─────────────┘               │
│                           │                             │
│          ┌────────────────▼─────────────────┐           │
│          │   RESOLVER (Chain-of-Resp.)      │           │
│          │   JSON → SQLite → Tellows →      │           │
│          │   DasTelefonbuch → Klartelbuch   │           │
│          └────────────────┬─────────────────┘           │
│                           │                             │
│                 ┌─────────▼───────────┐                 │
│                 │   OUTPUT ADAPTERS   │                 │
│  Call Log (SQLite) │  HA Webhook │ MQTT Publisher       │
└─────────────────────────────────────────────────────────┘
```

### Adapters

| Layer | Adapter | Description |
|-------|---------|-------------|
| **Input** | `fritz` | TCP connection to Fritz!Box Callmonitor (port 1012) with auto-reconnect |
| | `rest` | Manual trigger via REST API |
| | `mqtt` | MQTT subscriber (optional) |
| **Resolver** | `json_file` | Static contact list from a JSON file |
| | `sqlite` | SQLite contact database (manageable via GUI) |
| | `tellows` | Spam score via tellows.de (web scraping + cache) |
| | `dastelefon` | Reverse lookup via dasTelefonbuch.de (web scraping + cache) |
| | `klartelbuch` | Reverse lookup via klartelefonbuch.de (web scraping + cache) |
| **Output** | `call_log` | All events stored in SQLite history |
| | `ha_webhook` | POST to Home Assistant webhook |
| | `mqtt` | Publish to MQTT topics (optional) |

All adapters can be individually enabled or disabled. The resolver order determines priority — the first match wins.

## Installation

### As Home Assistant Addon

1. Add this repository as a custom repository in Home Assistant
2. Install the "Phone Logger" addon
3. Configure the addon settings
4. Enable Fritz!Box Callmonitor: dial `#96*5*` on any connected phone

### Local Development

```bash
# Install dependencies
uv sync

# Start server (Fritz disabled, REST input only)
PHONE_LOGGER_CONFIG=config.dev.yaml uv run python -m src.main

# Run tests
uv run pytest -v
```

The application will be available at `http://localhost:8080`.

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/resolve/{number}` | Resolve a phone number through the chain (404 if unknown) |
| `POST` | `/api/trigger/{number}` | Manually trigger a call event through the pipeline |
| `GET` | `/api/contacts` | List all SQLite contacts |
| `POST` | `/api/contacts` | Create a contact |
| `PUT` | `/api/contacts/{number}` | Update a contact |
| `DELETE` | `/api/contacts/{number}` | Delete a contact |
| `GET` | `/api/calls` | Call history (paginated) |
| `GET` | `/api/cache` | List cache entries |
| `DELETE` | `/api/cache/{number}` | Delete a cache entry |
| `POST` | `/api/cache/cleanup` | Remove expired cache entries |
| `GET` | `/api/config` | Current adapter configuration |

## Web Interface

The GUI is accessible via HA Ingress and provides four tabs:

- **Contacts** — CRUD management of SQLite contacts with search
- **Calls** — Call history with direction, resolution status, and pagination
- **Cache** — View, delete, and clean up web service cache entries
- **Configuration** — View active adapter configuration and test number resolution

## Configuration

Adapter order and settings are configured via HA addon options or a YAML file:

```yaml
fritz:
  host: "192.168.178.1"
  port: 1012

resolver_adapters:
  - name: "json_file"
    enabled: true
    config:
      path: "contacts.json"
  - name: "sqlite"
    enabled: true
  - name: "tellows"
    enabled: true
    config:
      ttl_days: 7
  - name: "dastelefon"
    enabled: true
    config:
      ttl_days: 30

output_adapters:
  - name: "call_log"
    enabled: true
  - name: "ha_webhook"
    enabled: true
```

### Cache TTL

Each web scraping adapter has a configurable TTL (time-to-live) in days. Expired entries are automatically refreshed on the next lookup or can be manually cleaned up via the GUI or API.

## Data Model

### Contacts

```
number (PK), name, tags[], notes, spam_score (1-10), source, last_seen, created_at, updated_at
```

### Cache

```
number + adapter (PK), result_json, cached_at, ttl_days
```

### Call History

```
id (PK), number, direction (inbound/outbound), event_type (ring/call/connect/disconnect),
resolved_name, source, timestamp
```

## HA Webhook Payload

When a call is resolved, the `ha_webhook` adapter sends a POST request:

```json
{
  "number": "+491234567890",
  "direction": "inbound",
  "event_type": "ring",
  "timestamp": "2026-03-18T10:15:00",
  "resolved": true,
  "name": "Max Mustermann",
  "tags": ["Familie"],
  "spam_score": null,
  "is_spam": false,
  "resolver_source": "sqlite"
}
```

## Project Structure

```
phone-logger/
├── config.yaml              # HA addon manifest
├── build.yaml               # Multi-arch build config
├── Dockerfile
├── pyproject.toml            # Dependencies (uv)
├── uv.lock
├── config.dev.yaml           # Local development configuration
├── src/
│   ├── main.py               # Entry point, FastAPI lifecycle
│   ├── config.py             # Load YAML/JSON configuration
│   ├── core/
│   │   ├── event.py          # CallEvent, ResolveResult models
│   │   └── pipeline.py       # Input → Resolve → Output orchestration
│   ├── adapters/
│   │   ├── base.py           # Abstract base classes
│   │   ├── input/            # fritz, rest, mqtt_sub
│   │   ├── resolver/         # chain, json_file, sqlite_db, tellows, dastelefon, klartelbuch
│   │   └── output/           # call_log, ha_webhook, mqtt_pub
│   ├── api/
│   │   ├── app.py            # FastAPI app factory
│   │   ├── models.py         # Pydantic request/response models
│   │   └── routes/           # resolve, contacts, calls, cache, config
│   ├── db/
│   │   ├── database.py       # Async SQLite wrapper
│   │   └── schema.sql        # Database schema
│   └── gui/
│       ├── routes.py         # Jinja2 template routes
│       ├── static/css/       # Stylesheet
│       └── templates/        # base, contacts, calls, cache, config
└── tests/
    ├── test_resolver_chain.py
    ├── test_fritz_parser.py
    └── test_api.py
```

## License

MIT
