---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-13
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -q --no-header` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -q --no-header`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-T1 | 01-01 | 1 | TOOL-01, TOOL-02, TOOL-03 | smoke | `uv run ruff check src/ --select E,F,W` | N/A (tool invocation) | ⬜ pending |
| 01-01-T2 | 01-01 | 1 | TOOL-01, TOOL-03 | smoke | `uv run ruff check src/ --select E,F,W` | N/A (tool invocation) | ⬜ pending |
| 01-02-T1 | 01-02 | 2 | DEP-01, DEP-02 | regression | `uv run pytest tests/ -v` | ✅ existing | ⬜ pending |
| 01-02-T2 | 01-02 | 2 | DEP-03 | smoke | `grep httpx pyproject.toml` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `uv add --dev pytest-cov` — required before `--cov=src` addopts is committed (TOOL-02)

*Note: No new test files needed — all validation uses existing 201 tests + CLI tool invocations.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `uv audit` shows no unaddressed CVEs | DEP-02 | Tool output requires human review of CVE disposition | Run `uv audit`; verify 0 unfixed CVEs remain (all 11 CVEs are addressed by aiohttp→3.13.5 and pygments→2.20.0) |
| httpx absent from `[project] dependencies` | DEP-03 | Grep check, no automated assertion in test suite | `grep -A1 "dependencies" pyproject.toml \| grep httpx` must return nothing |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
