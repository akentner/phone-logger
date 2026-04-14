# Requirements: phone-logger Cleanup & Sanitize

**Defined:** 2026-04-13
**Core Value:** Der Pipeline-Kern (Normalisierung → Resolver → Output) muss zuverlässig und klar nachvollziehbar bleiben.

## v1 Requirements

### Dev-Tooling

- [x] **TOOL-01**: Codebase läuft durch `ruff check` ohne Violations (ruff + ruff-format als dev dependency)
- [x] **TOOL-02**: pytest-cov konfiguriert, Coverage-Report mit `uv run pytest --cov=src` generierbar
- [x] **TOOL-03**: Ruff-Regeln in pyproject.toml definiert, alle bestehenden Violations gefixt

### Fehlerbehandlung

- [ ] **ERR-01**: Resolver-Chain unterscheidet NOT_FOUND / NETWORK_ERROR / RATE_LIMITED statt Exception swallowing
- [ ] **ERR-02**: Fritz!Box-Parser validiert Feldanzahl vor dem Split, loggt rohe Nachricht bei Parse-Fehler
- [ ] **ERR-03**: MQTT-Adapter loggt Disconnect/Reconnect-Events mit relevantem Kontext (Grund, Zähler)

### Tests

- [ ] **TEST-01**: Mindestens 3 FastAPI-Routen mit echtem TestClient getestet (GET /api/calls, GET /api/pbx/status, POST /api/contacts)
- [ ] **TEST-02**: MQTT-Reconnect-Szenarien getestet: Broker-Neustart, Publish-while-offline, Connection-Drop
- [ ] **TEST-03**: Call-Aggregation Edge Cases: DISCONNECT ohne RING, CONNECT ohne DISCONNECT, Orphan-Calls
- [ ] **TEST-04**: Fritz!Box-Parser Edge Cases: fehlende Felder, out-of-order Events, Duplikate

### Dependencies

- [x] **DEP-01**: Alle Pakete auf aktuelle kompatible Versionen aktualisiert, uv.lock refreshed
- [x] **DEP-02**: Security-Check via `uv audit` durchgeführt, bekannte CVEs adressiert oder dokumentiert
- [x] **DEP-03**: Ungenutzte Dependencies identifiziert und aus pyproject.toml entfernt

### Code-Qualität

- [x] **CODE-01**: f-string SQL-Concatenation in `src/db/database.py` durch sichere parametrisierte Patterns ersetzt
- [x] **CODE-02**: Uncommitted Änderungen in `src/adapters/mqtt.py` gereviewed, aufgeräumt und committet
- [x] **CODE-03**: Dead Code entfernt (ungenutzte Imports, unerreichbare Branches, tote Variablen)

## v2 Requirements

### Robustheit

- **ROB-01**: Circuit Breaker für Web-Scraper (fail-fast nach N Consecutive Failures)
- **ROB-02**: Atomische Database-Migrations mit Rollback-Safety
- **ROB-03**: Idempotency für Duplicate RING/CALL-Events via Deduplication-Window

### Observability

- **OBS-01**: Scraper-Success/Failure-Rate als Metriken
- **OBS-02**: Resolver-Latenz pro Adapter messbar

## Out of Scope

| Feature | Reason |
|---------|--------|
| ORM-Migration (SQLAlchemy) | Zu tief für Hygiene-Milestone |
| PostgreSQL-Migration | Infrastruktur-Aufwand unverhältnismäßig |
| Concurrent Resolver Execution | Erst mit Profiling-Daten sinnvoll |
| E2E-Tests mit echtem MQTT/Fritz!Box | Infrastruktur-Aufwand zu groß |
| Neue Features / neue Adapter | Separates Milestone |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TOOL-01 | Phase 1 | Complete |
| TOOL-02 | Phase 1 | Complete |
| TOOL-03 | Phase 1 | Complete |
| ERR-01 | Phase 3 | Pending |
| ERR-02 | Phase 3 | Pending |
| ERR-03 | Phase 3 | Pending |
| TEST-01 | Phase 4 | Pending |
| TEST-02 | Phase 4 | Pending |
| TEST-03 | Phase 4 | Pending |
| TEST-04 | Phase 4 | Pending |
| DEP-01 | Phase 1 | Complete |
| DEP-02 | Phase 1 | Complete |
| DEP-03 | Phase 1 | Complete |
| CODE-01 | Phase 2 | Complete |
| CODE-02 | Phase 2 | Complete |
| CODE-03 | Phase 2 | Complete |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16 ✓
- Unmapped: 0 ✓

---

*Requirements defined: 2026-04-13*
*Last updated: 2026-04-13 nach Roadmap-Erstellung*
