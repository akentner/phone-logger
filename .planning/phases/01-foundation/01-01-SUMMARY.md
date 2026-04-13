---
phase: 01-foundation
plan: 01
subsystem: tooling
tags: [ruff, pytest-cov, linting, coverage, dev-tooling]
dependency_graph:
  requires: []
  provides: [ruff-zero-violations, coverage-reporting, dev-tooling-baseline]
  affects: [all-phases]
tech_stack:
  added: [ruff>=0.15.10, pytest-cov>=7.1.0, coverage>=7.13.5]
  patterns: [E/F/W ruleset at 120 char, term-missing coverage, uv dev-groups]
key_files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - src/core/pipeline.py
    - src/api/routes/calls.py
    - src/api/routes/resolve.py
    - src/core/pbx.py
    - src/core/utils.py
    - src/db/database.py
    - src/i18n/translations.py
    - src/main.py
decisions:
  - "Ruff configured with E/F/W ruleset at 120-char line-length (per D-01, D-02)"
  - "pytest-cov addopts added after pytest-cov installed (same commit) to prevent startup failures"
  - "E402 in pipeline.py fixed by moving ANONYMOUS constants after all imports (pure reorder, no semantic change)"
  - "W293 in docstrings fixed manually (ruff --fix cannot modify docstring whitespace)"
metrics:
  duration_minutes: 2
  completed_date: "2026-04-13"
  tasks_completed: 2
  files_changed: 10
requirements_satisfied: [TOOL-01, TOOL-02, TOOL-03]
---

# Phase 01 Plan 01: Dev Tooling Baseline Summary

**One-liner:** Ruff (E/F/W, 120-char) and pytest-cov configured with zero violations across all 42 pre-existing lint errors fixed.

## What Was Built

Established the tooling baseline for the phone-logger Cleanup & Sanitize milestone:

1. **Ruff + pytest-cov added to dev deps** — `[dependency-groups] dev` in pyproject.toml now includes `ruff>=0.15.10` and `pytest-cov>=7.1.0`. Installed via `uv add --dev` to ensure venv is in sync before `addopts` references `--cov=src`.

2. **pyproject.toml configured** — Three new sections added:
   - `[tool.ruff]` with `line-length = 120`
   - `[tool.ruff.lint]` with `select = ["E", "F", "W"]`
   - `[tool.coverage.run]` with `omit = ["tests/*"]`
   - `[tool.pytest.ini_options]` extended with `addopts = "--cov=src --cov-report=term-missing"`

3. **42 Ruff violations fixed** — All violations eliminated from `src/`:
   - 10 F401 (unused imports) — auto-fixed by `ruff check --fix`
   - 20 W293 (whitespace on blank lines) — 13 auto-fixed, 7 manually fixed in docstrings
   - 12 E402 (imports after module-level code) — manually fixed in `src/core/pipeline.py` by moving `ANONYMOUS` constants after all imports

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add ruff and pytest-cov, configure pyproject.toml | b26d928 | pyproject.toml, uv.lock |
| 2 | Fix all Ruff violations in src/ (E402, F401, W293) | cd91aac | src/core/pipeline.py, src/api/routes/calls.py, src/api/routes/resolve.py, src/core/pbx.py, src/core/utils.py, src/db/database.py, src/i18n/translations.py, src/main.py |

## Verification Results

| Check | Result |
|-------|--------|
| `uv run ruff check src/` | ✅ Exit 0, zero violations |
| `uv run pytest --cov=src -q` | ✅ 201 passed, TOTAL coverage line present |
| `[tool.ruff]` in pyproject.toml | ✅ Present |
| `[tool.ruff.lint]` in pyproject.toml | ✅ Present with `select = ["E", "F", "W"]` |
| `[tool.coverage.run]` in pyproject.toml | ✅ Present with `omit = ["tests/*"]` |
| ruff in `[dependency-groups] dev` | ✅ `ruff>=0.15.10` |
| pytest-cov in `[dependency-groups] dev` | ✅ `pytest-cov>=7.1.0` |
| ruff-format NOT listed separately | ✅ Confirmed absent |
| ANONYMOUS after all imports in pipeline.py | ✅ Line 32, last import at line 30 |

## Requirements Satisfied

- **TOOL-01:** `uv run ruff check src/` exits with code 0 — zero violations
- **TOOL-02:** `uv run pytest --cov=src` produces coverage report — term-missing output with TOTAL line
- **TOOL-03:** ruff and pytest-cov in [dependency-groups] dev, configured per D-01 through D-09

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 7 W293 violations in docstrings not auto-fixed by ruff**
- **Found during:** Task 2 — after running `ruff check --fix`
- **Issue:** `ruff check --fix` could not auto-fix W293 in docstring blank lines (lines 10, 14, 17 in `src/core/utils.py`; lines 184, 188, 211, 214 in `src/i18n/translations.py`). Plan described "20 W293 all auto-fixable" but 7 required manual edit.
- **Fix:** Manually removed trailing whitespace from blank lines inside docstrings using Edit tool
- **Files modified:** `src/core/utils.py`, `src/i18n/translations.py`
- **Commit:** cd91aac
- **Impact:** None — same result (zero violations), extra manual step only

## Known Stubs

None. All changes are tooling configuration and import reordering — no UI-facing data or placeholder content.

## Self-Check: PASSED

- ✅ pyproject.toml exists and contains all required sections
- ✅ Commits b26d928 and cd91aac exist in git log
- ✅ 201 tests pass with coverage report
- ✅ `ruff check src/` exits 0
