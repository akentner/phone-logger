---
phase: 01-foundation
plan: "02"
subsystem: dependencies
tags: [security, dependencies, cve, audit, dev-tooling]
dependency_graph:
  requires: [01-01]
  provides: [DEP-01, DEP-02, DEP-03]
  affects: [uv.lock, pyproject.toml, Docker image size]
tech_stack:
  added: []
  patterns: [uv-managed-deps, dev-dependency-groups]
key_files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
decisions:
  - "Pin starlette not needed — starlette 1.0.0 had no test regressions"
  - "httpx moved to dev group (only used by TestClient in tests/) — not in Docker image"
  - "All 11 CVEs resolved by version upgrades alone — no SECURITY.md needed"
metrics:
  duration: "4 min"
  completed: "2026-04-13"
  tasks: 2
  files: 2
---

# Phase 01 Plan 02: Dependency Upgrade & CVE Remediation Summary

**One-liner:** Upgraded 11 packages to fix all CVEs (aiohttp→3.13.5, pygments→2.20.0) and moved httpx to dev-only dependencies.

## Objective

Upgrade all dependencies to current compatible versions, remediate all 11 known CVEs, and move httpx from production dependencies to dev dependencies.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Upgrade all dependencies and validate test suite | b9f707d | uv.lock |
| 2 | Security audit and move httpx to dev dependencies | ef573f4 | pyproject.toml, uv.lock |

## Decisions Made

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| No starlette pin needed | starlette 1.0.0 → 0 test regressions in all 201 tests | Not pinned — full 1.0.0 adopted |
| httpx → dev group | Only imported in `tests/test_api.py` (FastAPI TestClient) | Removes 3 packages (httpx, httpcore, certifi) from production Docker image |
| No SECURITY.md | All 11 CVEs resolved by version upgrades alone | Clean `uv audit` output |

## Verification Results

```
uv audit: Found no known vulnerabilities and no adverse project statuses in 50 packages
pytest: 201 passed in 9.92s
ruff: All checks passed!
```

### CVEs Resolved

| CVE Package | From | To | CVEs Fixed |
|-------------|------|----|------------|
| aiohttp | 3.13.3 | 3.13.5 | 10 CVEs |
| pygments | 2.19.2 | 2.20.0 | 1 CVE |

### All Upgrades Applied

| Package | From | To |
|---------|------|----|
| aiohttp | 3.13.3 | 3.13.5 |
| starlette | 0.52.1 | 1.0.0 |
| fastapi | 0.135.1 | 0.135.3 |
| uvicorn | 0.42.0 | 0.44.0 |
| pygments | 2.19.2 | 2.20.0 |
| python-multipart | 0.0.22 | 0.0.26 |
| anyio | 4.12.1 | 4.13.0 |
| attrs | 25.4.0 | 26.1.0 |
| click | 8.3.1 | 8.3.2 |
| lxml | 6.0.2 | 6.0.4 |
| pytest | 9.0.2 | 9.0.3 |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED
