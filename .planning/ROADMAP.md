# ROADMAP: phone-logger Cleanup & Sanitize

## Summary

**Milestone:** phone-logger Cleanup & Sanitize  
**Phases:** 4  
**Granularity:** Standard  
**Coverage:** 16/16 requirements mapped ✓

This roadmap transforms the codebase from working-but-untested into production-ready: robust error handling, comprehensive test coverage, modern tooling, and secure dependencies.

## Phases

- [ ] **Phase 1: Foundation** - Ruff, Coverage, Audit, Dependency Updates
- [ ] **Phase 2: Code Quality** - SQL Safety, MQTT Cleanup, Dead Code Removal
- [ ] **Phase 3: Error Handling & Robustness** - Resolver Errors, Parser Validation, MQTT Logging
- [ ] **Phase 4: Testing & Validation** - API Routes, MQTT Scenarios, Edge Cases

## Phase Details

### Phase 1: Foundation
**Goal**: Establish linting, coverage measurement, and secure dependency baseline

**Depends on**: Nothing (foundation phase)

**Requirements**: TOOL-01, TOOL-02, TOOL-03, DEP-01, DEP-02, DEP-03

**Success Criteria** (what must be TRUE):
1. Codebase passes `ruff check` with zero violations and includes `ruff` and `ruff-format` as dev dependencies
2. Coverage measurement runs with `uv run pytest --cov=src` and generates a baseline report
3. All v1 dependencies updated to compatible versions with `uv.lock` refreshed
4. Security audit via `uv audit` completed with all CVEs documented or remediated

**Plans**: TBD

---

### Phase 2: Code Quality
**Goal**: Eliminate critical code safety issues and dead code

**Depends on**: Phase 1

**Requirements**: CODE-01, CODE-02, CODE-03

**Success Criteria** (what must be TRUE):
1. All SQL queries in `src/db/database.py` use parametrized patterns, no f-string concatenation
2. Uncommitted changes in `src/adapters/mqtt.py` reviewed, cleaned, and committed with clear message
3. Codebase has no unused imports, unreachable code branches, or dead variables (verified by Ruff)

**Plans**: TBD

---

### Phase 3: Error Handling & Robustness
**Goal**: Add differentiated error types and defensive validation throughout pipeline

**Depends on**: Phase 1 (tooling)

**Requirements**: ERR-01, ERR-02, ERR-03

**Success Criteria** (what must be TRUE):
1. Resolver-Chain distinguishes NOT_FOUND, NETWORK_ERROR, RATE_LIMITED errors instead of swallowing exceptions
2. Fritz!Box event parser validates field count before split and logs raw message on parse failure
3. MQTT adapter logs Disconnect and Reconnect events with connection reason and attempt counter

**Plans**: TBD

---

### Phase 4: Testing & Validation
**Goal**: Close test coverage gaps and validate all pipeline paths

**Depends on**: Phase 1 (tooling), Phase 2 (quality), Phase 3 (robustness)

**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04

**Success Criteria** (what must be TRUE):
1. At least 3 FastAPI routes tested with real TestClient: GET /api/calls, GET /api/pbx/status, POST /api/contacts
2. MQTT reconnection scenarios covered: Broker restart, Publish-while-offline, Connection drop and recovery
3. Call aggregation edge cases tested: DISCONNECT without RING, CONNECT without DISCONNECT, Orphan calls
4. Fritz!Box parser edge cases tested: Missing fields, out-of-order events, Duplicate events

**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/3 | Not started | — |
| 2. Code Quality | 0/3 | Not started | — |
| 3. Error Handling & Robustness | 0/3 | Not started | — |
| 4. Testing & Validation | 0/4 | Not started | — |

---

## Coverage Validation

**Requirement Mapping:**

| Requirement | Phase | Category |
|-------------|-------|----------|
| TOOL-01 | Phase 1 | Dev-Tooling |
| TOOL-02 | Phase 1 | Dev-Tooling |
| TOOL-03 | Phase 1 | Dev-Tooling |
| DEP-01 | Phase 1 | Dependencies |
| DEP-02 | Phase 1 | Dependencies |
| DEP-03 | Phase 1 | Dependencies |
| CODE-01 | Phase 2 | Code-Qualität |
| CODE-02 | Phase 2 | Code-Qualität |
| CODE-03 | Phase 2 | Code-Qualität |
| ERR-01 | Phase 3 | Fehlerbehandlung |
| ERR-02 | Phase 3 | Fehlerbehandlung |
| ERR-03 | Phase 3 | Fehlerbehandlung |
| TEST-01 | Phase 4 | Tests |
| TEST-02 | Phase 4 | Tests |
| TEST-03 | Phase 4 | Tests |
| TEST-04 | Phase 4 | Tests |

**Coverage Summary:**
- Total v1 requirements: 16
- Mapped to phases: 16
- Unmapped: 0 ✓

---

*Roadmap created: 2026-04-13*
