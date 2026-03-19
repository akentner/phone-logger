
# AGENTS — Guidelines for AI coding agents

Short: This project is an adapter-based Phone Logger service (FastAPI) with a clear Input → Resolver → Output pipeline. This file lists the minimal knowledge, conventions and concrete code locations an agent needs to become productive immediately.

1) Big picture (where to look)
- Pipeline orchestration: `src/core/pipeline.py` — lifecycle methods (`setup()`, `start()`, `stop()`), start order (Resolver → Output → Input) and the event processing hub `_on_event`.
- Adapter interfaces: `src/adapters/base.py` — signatures: `Input.start(callback)`, `Resolver.resolve(number)`, `Output.handle(event, result, line_state=...)`.
- Resolver chain: `src/adapters/resolver/chain.py` — first-match wins; order comes from `AppConfig.resolver_adapters`.
- DB & models: `src/db/database.py` (+ `src/db/schema.sql`) and event/result models in `src/core/event.py` and `src/api/models.py`.

2) Important developer workflows (start / test / debug)
- Dev start (recommended):
  - PHONE_LOGGER_CONFIG=config.dev.yaml python -m src.main
  - README also references `uv run python -m src.main` and `uv sync` as helper shortcuts; the minimal functional option is the ENV + `python -m src.main` above.
- Tests: `pytest -v` (see `pyproject.toml`: `asyncio_mode = "auto"`). Many tests live under `tests/` and use `pytest-asyncio`.
- Logging/config: App config loads from environment `PHONE_LOGGER_CONFIG`, HA addon options `/data/options.json`, or local `config.yaml` (`src/config.load_config`). Log level comes from `AppConfig.log_level`.

3) Project-specific conventions / gotchas
- Name vs Type: `AdapterConfig` has both `type` and `name`. The pipeline uses them in different places:
  - Resolver factories match `adapter_config.name` (e.g. `"sqlite"`, `"json_file"`).
  - Output factory matches `adapter_config.type` (e.g. `"call_log"`, `"webhook"`).
  => When adding adapters check both `src/config.py` defaults and factory registration in `src/core/pipeline.py`.
- Singleton adapter: `call_log` is limited to a single instance (see `call_log_registered`). Multiple webhooks/MQTT outputs are allowed.
- REST input special-case: the `rest` input adapter is kept at `Pipeline._rest_input` and used by the API to manually trigger events.

4) Extension points (how to add adapters)
- New resolver:
  1. Implement `BaseResolverAdapter` in `src/adapters/resolver/your_resolver.py`.
  2. Import the implementation in `src/core/pipeline.py` and add it to `resolver_factories` (key = expected `adapter_config.name`).
  3. Optionally add defaults in `src/config.py`.
- New input/output:
  - Implement `BaseInputAdapter` / `BaseOutputAdapter` under `src/adapters/input/` or `src/adapters/output/` and register creation in `_setup_input_adapters` / `_setup_output_adapters` in `pipeline.py`. Be careful whether the selection is by `name` (input/resolver) or `type` (output).

5) Integrations & external dependencies
- Fritz!Box: TCP Callmonitor (default port 1012) — configured in `config.dev.yaml`, parsed in `src/adapters/input/fritz.py`.
- Web-scraping resolvers: `tellows`, `dastelefon`, `klartelbuch` use `aiohttp` + `beautifulsoup4` and cache results in SQLite via `src/db/database.py`; TTL is configurable.
- MQTT: implemented with `aiomqtt` in `src/adapters/input/mqtt_sub.py` and `src/adapters/output/mqtt_pub.py`.

6) Data flow examples (concrete code paths)
- REST trigger → `POST /api/trigger/{number}` → uses pipeline rest adapter → `Pipeline._on_event` → on RING/CALL `resolver_chain.resolve(number)` → result passed to every `Output.handle()` adapter.
- CONNECT/DISCONNECT → resolve result from earlier RING/CALL is cached per line in `Pipeline._resolve_cache[line_id]` and reused for later CONNECT/DISCONNECT events (see `_on_event`).

7) Tests, debugging & quick checks
- Unit tests: look in `tests/` (use `pytest -q` / `pytest -k <name>` to filter). Mock external HTTP/MQTT/Fritz connections in tests rather than using real network calls.
- Runtime logging: set `log_level` in `config.dev.yaml` to `DEBUG` for detailed tracing.
- DB inspection: DB file is at `data/phone-logger.db` by default (path from `AppConfig.db_path`).

8) Key files (quick reference)
- `src/main.py` — app factory, uvicorn entry, lifecycle events
- `src/config.py` — `AppConfig`, adapter defaults, `load_config` logic
- `src/core/pipeline.py` — orchestrator, adapter factories, `_on_event` processing
- `src/adapters/base.py` — abstract adapter interfaces
- `src/db/database.py`, `src/db/schema.sql` — persistent storage and cache handling
- `src/api/app.py`, `src/api/routes/` — REST endpoints and API models

Notes for GUI and i18n
- The web GUI loads translations in `src/gui/templates/base.html` once on page load via `/api/i18n/translations`. Some pages previously reloaded translations on each poll (e.g. `pbx.html`); avoid reloading translations on short polling intervals — translations are static unless the user changes language.

When generating code: follow existing Pydantic models (`src/core/event.py`, `src/api/models.py`) and use asynchronous lifecycle patterns (`start()`, `stop()`) like in `pipeline.py` and `main.py`.

-- End

# AGENTS — Richtlinien für KI-Coding-Agenten

Kurz: Dieses Projekt ist ein Adapter-basiertes Phone-Logger-Service (FastAPI) mit Input → Resolver → Output Pipeline. Die Datei listet die minimal erforderlichen Kenntnisse, Konventionen und konkrete Codeorte, damit ein Agent sofort produktiv arbeiten kann.

1) Big Picture (wo schauen)
- Pipeline-Orchestrierung: `src/core/pipeline.py` (Lifecycle: `setup()`, `start()`, `stop()`; Reihenfolge: Resolver → Output → Input). Verstehe `_on_event` und `_resolve_cache` für CONNECT/DISCONNECT-Korrelationen.
- Adapter-Interfaces: `src/adapters/base.py` (Signaturen: `Input.start(callback)`, `Resolver.resolve(number)`, `Output.handle(event, result, line_state=...)`).
- Resolver-Chain: `src/adapters/resolver/chain.py` (Reihenfolge/first-match wins, Cache-Integration über `src/db/database.py`).
- DB & Models: `src/db/database.py` und `src/db/schema.sql` (Kontakte, Cache, Call-History); App-Modelle: `src/core/event.py`, API-Modelle: `src/api/models.py`.

2) Wichtige Projekt-Workflows (wie man lokal startet / testet)
- Lokales Starten (Dev config):
  - `PHONE_LOGGER_CONFIG=config.dev.yaml python -m src.main` — (auch in `config.dev.yaml` als Kommentar dokumentiert).
  - README verwendet außerdem `uv run python -m src.main` / `uv sync` zur Dependency-Installation; diese Befehle stammen aus Projekt-Dokumentation und sind die empfohlene Dev-Shortcut-Variante.
- Tests: `pytest -v` (oder `uv run pytest -v` laut README). Pytest-Konfiguration in `pyproject.toml` (`asyncio_mode = "auto"`).
- Logging & config: Logging-Level kommt aus `src/config.AppConfig.log_level`. Konfigurationsquelle: env `PHONE_LOGGER_CONFIG`, HA `options.json` (`/data/options.json`) oder lokale `config.yaml` (`src/config.load_config`).

3) Projekt-spezifische Konventionen / Fallen
- Adapter-Auswahl: Der Code verwendet sowohl `AdapterConfig.type` als Kategorie (z. B. output `type: "webhook"`) als auch `AdapterConfig.name` als Schlüssel zur Auswahl der Implementierung. Beispiel:
  - In `src/core/pipeline.py::_setup_resolver_adapters` wird `adapter_config.name` mit keys wie `"json_file"`, `"sqlite"` verglichen — der `name` entscheidet, welche Resolver-Klasse instanziiert wird.
  - In `src/core/pipeline.py::_setup_output_adapters` wird hingegen `adapter_config.type` genutzt, um Output-Implementierungen zu unterscheiden (`call_log`, `webhook`, `mqtt`).
  => Beim Hinzufügen eines Adapters unbedingt beide Plätze prüfen (Konfiguration defaults in `src/config.py` und Factory-Registrierung in `pipeline.py`).
- Singleton vs. Multi-Instanzen: `call_log` wird nur einmal erlaubt (siehe `call_log_registered` Flag). Webhooks/MQTT können mehrere Instanzen haben.
- REST-Input special-case: Der `rest` input adapter wird in `Pipeline._rest_input` gespeichert und von der API/Tests genutzt (man kann damit manuell Events triggern).

4) Erweiterungspunkte (konkrete Schritte für neue Adapter)
- Neuer Resolver: implementiere `BaseResolverAdapter` in `src/adapters/resolver/your_resolver.py`, importiere Klasse in `src/core/pipeline.py` und füge einen Eintrag in `resolver_factories` (Schlüssel = erwarteter `adapter_config.name`).
- Neuer Input/Output: implementiere `BaseInputAdapter` / `BaseOutputAdapter` und füge die Erzeugung in `_setup_input_adapters` / `_setup_output_adapters` an der Stelle ein, an der vorhandene Adapter anhand `adapter_config.name` oder `adapter_config.type` unterschieden werden.

5) Integration & externe Abhängigkeiten
- Fritz!Box Callmonitor: TCP (standardmäßig host/port in `config.dev.yaml`, port 1012). Parser und Adapter: `src/adapters/input/fritz.py`.
- Web-Scraping-Resolver: `tellows`, `dastelefon`, `klartelbuch` verwenden `aiohttp`/`beautifulsoup4` und schreiben in die DB-Cache (`src/db/database.py`) mit `ttl_days` konfigurierbar (siehe `config.dev.yaml`).
- MQTT: Subscriber/Publisher implementiert unter `src/adapters/input/mqtt_sub.py` und `src/adapters/output/mqtt_pub.py` (abhängig von `aiomqtt`).

6) Datenfluss-Beispiele (konkrete Codepfade)
- Eingang → REST: API `POST /api/trigger/{number}` → nutzt `Pipeline.rest_input` / `Pipeline._on_event` → falls RING/CALL wird `resolver_chain.resolve()` aufgerufen → Ergebnisse an alle `Output.handle()` Adapter weitergereicht.
- CONNECT/DISCONNECT: Resolver-Ergebnis wird beim RING/CALL in `Pipeline._resolve_cache[line_id]` zwischengespeichert und später für CONNECT/DISCONNECT herangezogen (siehe `_on_event`).

7) Quick wins für PRs/Änderungen
- Bevor du Änderungen an Adaptern machst, suche nach `adapter_config.name`-Vergleichen in `src/core/pipeline.py` und default-Einträgen in `src/config.py`.
- Unit/Integration Tests: Tests liegen in `tests/` und nutzen `pytest-asyncio`. Mock externe HTTP/MQTT/Fritz-Verbindungen – das Projekt hat bereits kleine placeholder tests (`tests/test_api.py`).

8) Nützliche Dateipfade (schnellreferenz)
- App entry: `src/main.py`
- Config loading: `src/config.py`
- Pipeline orchestration: `src/core/pipeline.py`
- Adapter base: `src/adapters/base.py`
- DB: `src/db/database.py`, schema: `src/db/schema.sql`
- API: `src/api/app.py`, `src/api/routes/` (endpoints)

Wenn du Code generierst: halte dich an vorhandene Pydantic-Modelle (`src/core/event.py`, `src/api/models.py`) und die async-Start/Stop-Lifecycle-Muster aus `pipeline.py`/`main.py`.


