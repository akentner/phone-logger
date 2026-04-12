# STATE.md: phone-logger Cleanup & Sanitize

**Milestone:** phone-logger Cleanup & Sanitize  
**Created:** 2026-04-13  
**Status:** Roadmap Approved (awaiting first plan)

## Project Reference

**Core Value:** Der Pipeline-Kern (Normalisierung → Resolver → Output) muss zuverlässig und klar nachvollziehbar bleiben.

**Current Focus:** Phases 1-4 deliver: robust error handling, comprehensive test coverage, modern linting, and secure dependencies.

**Key Constraint:** All 201 existing tests must remain green. No breaking changes to MQTT topics, webhooks, APIs, or config.

## Current Position

**Phase:** None (roadmap complete, awaiting planning)  
**Plan:** —  
**Status:** Roadmap approved, pending Phase 1 plan decomposition

**Progress Bar:**
```
[Foundation    ] [Code Quality ] [Error Handling] [Testing      ]
[0/3 plans    ] [0/3 plans    ] [0/3 plans     ] [0/4 plans    ]
```

## Phase Overview

| Phase | Goal | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation: Ruff, Coverage, Audit, Dependencies | Not Started | 0/3 |
| 2 | Code Quality: SQL Safety, MQTT, Dead Code | Not Started | 0/3 |
| 3 | Error Handling: Resolver, Parser, MQTT Logging | Not Started | 0/3 |
| 4 | Testing: API Routes, MQTT, Aggregation, Parser | Not Started | 0/4 |

## Accumulated Context

### Architecture Overview

**Input → Resolver → Output Pipeline:**
- **Input Adapters:** Fritz TCP, REST API, MQTT
- **Resolver Chain:** SQLite, Tellows, DasTelefonbuch, etc. (first-match-wins)
- **Output Adapters:** CallLog (SQLite), Webhook, MQTT

**Core Models:** `src/core/event.py` (CallEvent, ResolveResult, PipelineResult)  
**PBX FSM:** `src/core/pbx.py` tracks per-line state (IDLE → RING → TALKING → FINISHED/MISSED)  
**Pipeline:** `src/core/pipeline.py` orchestrates adapters and caches resolver results

### Known Weaknesses (Pre-Cleanup)

1. **Ruff not in pyproject.toml** — Standard per CLAUDE.md but missing as dev dependency
2. **No Coverage Config** — pytest-cov needed with baseline setup
3. **Exception Swallowing** — Resolver-Chain doesn't differentiate error types
4. **SQL Concatenation** — f-strings in `src/db/database.py` risk injection
5. **Fritz!Box Parser** — No field count validation before split()
6. **MQTT Reconnect** — Limited logging on disconnect/reconnect events
7. **Uncommitted MQTT Changes** — `src/adapters/mqtt.py` has dirty working tree
8. **Test Gaps** — No API TestClient tests, MQTT reconnect, aggregation edge cases

### Constraints

- **Compatibility:** All 201 existing tests must pass
- **No Breaking Changes:** MQTT topics, webhook payload, API schemas, config structure remain stable
- **uv Only:** No direct pip usage
- **Python 3.12+:** No features beyond 3.12

### Decisions Logged

| Decision | Rationale | Status |
|----------|-----------|--------|
| 4 phases instead of 5-8 | Standard granularity, natural grouping, critical path only | Approved |
| Phase 1: Foundation first | Unblocks all other phases (tools, audit, dependencies) | Approved |
| Phase 2 before Phase 3 | Code quality enables robust error handling patterns | Approved |
| Phase 4 validates all | Testing closes all coverage gaps, end of cleanup | Approved |

## Next Steps

1. **Phase 1 Planning:** Decompose 6 requirements into executable plans (Ruff setup, Coverage config, Audit, Version updates)
2. **Phase 2 Planning:** Decompose 3 requirements into SQL refactoring, MQTT review, dead code scan
3. **Phase 3 Planning:** Decompose 3 requirements into error enum, parser validation, MQTT logging
4. **Phase 4 Planning:** Decompose 4 requirements into API tests, MQTT scenarios, aggregation cases, parser cases

## Session Continuity

This state persists across sessions. Update after each phase completion with:
- Plan completion status
- Blockers or new discoveries
- Traceability updates (REQUIREMENTS.md)
- Evolution of known weaknesses

---

*Last updated: 2026-04-13 after roadmap creation*
