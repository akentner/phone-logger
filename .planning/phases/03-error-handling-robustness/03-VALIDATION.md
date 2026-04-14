---
phase: 3
slug: error-handling-robustness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4+ with pytest-asyncio |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/ -v -x` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -v -x`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | ERR-01 | unit | `uv run pytest tests/test_resolver_chain.py -v` | ✅ | ⬜ pending |
| 3-01-02 | 01 | 1 | ERR-01 | unit | `uv run pytest tests/test_resolver_chain.py -v` | ✅ | ⬜ pending |
| 3-02-01 | 02 | 0 | ERR-02 | unit | `uv run pytest tests/test_fritz_parser.py -v` | ✅ | ⬜ pending |
| 3-02-02 | 02 | 1 | ERR-02 | unit | `uv run pytest tests/test_fritz_parser.py -v` | ✅ | ⬜ pending |
| 3-03-01 | 03 | 0 | ERR-03 | unit | `uv run pytest tests/test_mqtt_output.py -v` | ✅ | ⬜ pending |
| 3-03-02 | 03 | 1 | ERR-03 | unit | `uv run pytest tests/test_mqtt_output.py -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_resolver_chain.py` — add test stubs for NETWORK_ERROR, RATE_LIMITED, NOT_FOUND distinction (ERR-01)
- [ ] `tests/test_fritz_parser.py` — add test stubs for field-count validation (ERR-02)
- [ ] `tests/test_mqtt_output.py` — add test stubs for Disconnect/Reconnect logging (ERR-03)

*Existing test infrastructure covers all phase requirements — Wave 0 only adds stubs/cases to existing files.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fritz!Box TCP raw message visible in logs | ERR-02 | Requires live Fritz!Box connection | Send malformed event via TCP; check log output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
