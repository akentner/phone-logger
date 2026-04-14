# ROADMAP: phone-logger Cleanup & Sanitize

## Summary

**Milestone:** phone-logger Cleanup & Sanitize  
**Phases:** 4  
**Granularity:** Standard  
**Coverage:** 16/16 requirements mapped ✓

This roadmap transforms the codebase from working-but-untested into production-ready: robust error handling, comprehensive test coverage, modern tooling, and secure dependencies.

## Phases

- [x] **Phase 1: Foundation** - Ruff, Coverage, Audit, Dependency Updates (completed 2026-04-13)
- [ ] **Phase 2: Code Quality** - SQL Safety, MQTT Cleanup, Dead Code Removal
- [x] **Phase 3: Error Handling & Robustness** - Resolver Errors, Parser Validation, MQTT Logging (completed 2026-04-14)
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

**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Ruff + pytest-cov tooling: add dev deps, configure pyproject.toml, fix 42 violations
- [x] 01-02-PLAN.md — Dependency upgrade + audit: `uv lock --upgrade`, CVE remediation, move httpx to dev

---

### Phase 2: Code Quality
**Goal**: Eliminate critical code safety issues and dead code

**Depends on**: Phase 1

**Requirements**: CODE-01, CODE-02, CODE-03

**Success Criteria** (what must be TRUE):
1. All SQL queries in `src/db/database.py` use parametrized patterns, no f-string concatenation
2. Uncommitted changes in `src/adapters/mqtt.py` reviewed, cleaned, and committed with clear message
3. Codebase has no unused imports, unreachable code branches, or dead variables (verified by Ruff)

**Plans**: 2 plans

Plans:
- [ ] 02-01-PLAN.md — SQL f-string refactor: replace structural assembly in database.py with string concatenation
- [ ] 02-02-PLAN.md — MQTT bug fix commit + Ruff dead-code verification

---

### Phase 3: Error Handling & Robustness
**Goal**: Add differentiated error types and defensive validation throughout pipeline

**Depends on**: Phase 1 (tooling)

**Requirements**: ERR-01, ERR-02, ERR-03

**Success Criteria** (what must be TRUE):
1. Resolver-Chain distinguishes NOT_FOUND, NETWORK_ERROR, RATE_LIMITED errors instead of swallowing exceptions
2. Fritz!Box event parser validates field count before split and logs raw message on parse failure
3. MQTT adapter logs Disconnect and Reconnect events with connection reason and attempt counter

**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Resolver error hierarchy: create errors.py, refactor chain.py, add typed raises to 4 resolvers
- [x] 03-02-PLAN.md — Fritz parser validation: MIN_FIELDS constant + guard in _parse_line(), unknown event debug log
- [x] 03-03-PLAN.md — MQTT reconnect logging: _reconnect_attempts counter + 4 log events in _run_loop/_connect

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

**Plans**: 4 plans

Plans:
- [ ] 04-01-PLAN.md — API routes TestClient tests: GET /api/calls, GET /api/pbx/status, POST /api/contacts
- [x] 04-02-PLAN.md — MQTT publish-while-offline scenarios: verify silent drop, no crash on connection loss
- [x] 04-03-PLAN.md — Call aggregation edge cases: DISCONNECT without RING, CONNECT without DISCONNECT, orphans
- [x] 04-04-PLAN.md — Fritz!Box parser edge cases: idempotency, out-of-order, adapter integration tests

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/2 | Complete   | 2026-04-13 |
| 2. Code Quality | 0/2 | Planned    |  |
| 3. Error Handling & Robustness | 3/3 | Complete   | 2026-04-14 |
| 4. Testing & Validation | 3/4 | In Progress|  |

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
*Phase 1 planned: 2026-04-13*
*Phase 2 planned: 2026-04-14*
*Phase 3 planned: 2026-04-14*
*Phase 4 planned: 2026-04-15*
