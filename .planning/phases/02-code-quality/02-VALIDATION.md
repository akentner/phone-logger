---
phase: 02
slug: code-quality
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-14
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4+ with pytest-asyncio 0.24.0+ |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/ -q --tb=short` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -q --tb=short`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green + `uv run ruff check src/` clean
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | CODE-01 | code review + regression | `uv run ruff check src/db/database.py && uv run pytest tests/ -q` | ✅ | ⬜ pending |
| 02-01-02 | 01 | 1 | CODE-01 | regression | `uv run pytest tests/ -q --tb=short` | ✅ | ⬜ pending |
| 02-02-01 | 02 | 1 | CODE-02 | git + regression | `git status src/adapters/mqtt.py && uv run pytest tests/ -q` | ✅ | ⬜ pending |
| 02-02-02 | 02 | 1 | CODE-03 | lint | `uv run ruff check src/` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. CODE-01 and CODE-02 are regression-tested by the existing 201 tests; CODE-03 requires no test file.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SQL f-strings only in structure, not values | CODE-01 | Code review needed to distinguish structural vs value f-strings | Read database.py and verify LIKE-value f-strings at lines ~387/564 remain as `?` parameters |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
