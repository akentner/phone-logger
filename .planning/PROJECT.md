# phone-logger — Cleanup & Sanitize

## What This Is

phone-logger ist ein FastAPI-basierter Telefon-Call-Monitor, der Anrufereignisse vom Fritz!Box Callmonitor empfängt, Nummern über eine Resolver-Chain (SQLite, Tellows, DasTelefonbuch u.a.) auflöst und Ergebnisse via MQTT, Webhooks und SQLite persistiert. Das System läuft als Home Assistant Add-on und hat eine eigene Web-UI für Monitoring und Kontaktverwaltung.

Dieses Milestone konzentriert sich auf **Cleanup & Sanitize** — keine neuen Features, sondern Verbesserung der Codebase-Qualität, Test-Coverage, Dev-Tooling und Dependency-Hygiene.

## Core Value

Der Pipeline-Kern (Normalisierung → Resolver → Output) muss zuverlässig und klar nachvollziehbar bleiben — das ist die einzige Garantie, die zählt.

## Requirements

### Validated

- ✓ Input/Resolver/Output-Pipeline über Adapter-Pattern — existing
- ✓ PBX FSM mit IDLE→RING→TALKING→FINISHED/MISSED State Machine — existing
- ✓ Resolver-Chain (First-match-wins, SQLite-Cache, Web-Scraper) — existing
- ✓ MQTT-Output mit Reconnect-Logik — existing
- ✓ REST-API für Contacts, Calls, PBX-Status, Resolver — existing
- ✓ Home Assistant Add-on (Multi-Arch Docker, Ingress) — existing
- ✓ Jinja2 Web-UI mit i18n (DE/EN) — existing

### Active

- [ ] **Fehlerbehandlung**: Silent failures im Resolver-Chain differenzieren (NOT_FOUND vs. NETWORK_ERROR), besseres Error-Logging in Pipeline
- [ ] **Test-Lücken schließen**: MQTT-Reconnect-Szenarien, API-Routen via TestClient, Call-Aggregation mit fehlenden Events
- [ ] **Code-Qualität**: SQL-Concatenation durch parametrisierte Queries ersetzen, Fritz!Box-Parser defensiver machen

### Validated

- ✓ **Dev-Tooling**: Ruff (>=0.15.10) + pytest-cov (>=7.1.0) als Dev-Dependencies konfiguriert, Coverage-Report in jedem pytest-Lauf — Validated in Phase 01: Foundation
- ✓ **Dependencies aufräumen**: 11 CVEs behoben (aiohttp→3.13.5, pygments→2.20.0), starlette→1.0.0, httpx aus Production deps entfernt — Validated in Phase 01: Foundation

### Out of Scope

- Architektur-Umbau (ORM, PostgreSQL-Migration) — zu tief für Hygiene-Milestone
- Neue Features (neue Resolver, neue Output-Adapter) — separates Milestone
- Performance-Optimierungen (Concurrent Resolvers, Write-Batching) — erst mit Profiling-Daten sinnvoll
- E2E-Tests mit echtem MQTT-Broker oder Fritz!Box — Infrastruktur-Aufwand unverhältnismäßig

## Context

- **Codebase-Status**: 201 Tests, alle grün. Ruff ist laut CLAUDE.md der Linter, aber nicht in pyproject.toml als Dev-Dependency. Keine Coverage-Konfiguration.
- **Bekannte Schwachstellen** (aus Codebase-Scan): Resolver-Chain swallowed exceptions, MQTT-Reconnect-Lücken, Fritz!Box-Parser ohne Feldanzahl-Validierung, f-string SQL-Concatenation in database.py
- **Test-Coverage-Lücken**: API-Routen (TestClient fehlt), MQTT-Reconnect, Call-Aggregation Edge-Cases, Web-Scraper-Parser-Fehler
- **Geänderte Datei**: `src/adapters/mqtt.py` hat uncommitted changes — Cleanup muss berücksichtigen was dort läuft

## Constraints

- **Kompatibilität**: Alle bestehenden 201 Tests müssen weiterhin grün bleiben
- **Keine Breaking Changes**: Keine Änderungen an MQTT-Topic-Format, Webhook-Payload, API-Schemas oder Config-Struktur
- **uv**: Dependency-Management ausschließlich via uv (kein pip direkt)
- **Python 3.12+**: Keine Features verwenden, die Python 3.12 nicht unterstützt

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Ruff über pylint/flake8 | Laut CLAUDE.md bereits Projektstandard | — Pending |
| pytest-cov für Coverage | Standard im pytest-Ecosystem, minimale Konfiguration | — Pending |
| ResolveError-Enum statt Exception-Swallowing | Fehlerunterscheidung ohne Pipeline-Break | — Pending |

## Evolution

Dieses Dokument wird an Phasen-Übergängen aktualisiert.

**Nach jeder Phase:**
1. Requirements validiert? → nach Validated verschieben
2. Neue Erkenntnisse? → Active aktualisieren
3. Scope-Erweiterungen abgelehnt? → Out of Scope ergänzen

---
*Last updated: 2026-04-13 — Phase 01: Foundation complete*
