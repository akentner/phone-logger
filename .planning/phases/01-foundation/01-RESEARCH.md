# Phase 1: Foundation - Research

**Researched:** 2026-04-13
**Domain:** Python dev-tooling (ruff, pytest-cov, uv dependency management, security audit)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Rule categories: `E`, `F`, `W` only (pyflakes + pycodestyle basics) — minimal ruleset to avoid scope creep
- **D-02:** Line length: 120 characters — consistent with monorepo CLAUDE.md standard
- **D-03:** All existing violations must be fixed so `ruff check` passes with zero violations
- **D-04:** `ruff` and `ruff-format` added to `[dependency-groups] dev` in `pyproject.toml`
- **D-05:** Ruff config lives in `[tool.ruff]` section of `pyproject.toml` (no separate `.ruff.toml`)
- **D-06:** `pytest-cov` added to `[dependency-groups] dev` in `pyproject.toml`
- **D-07:** Coverage config in `[tool.pytest.ini_options]` or `[tool.coverage]` section of `pyproject.toml`
- **D-08:** Coverage measured via `uv run pytest --cov=src` — baseline report generated and documented
- **D-09:** No fail-under threshold — measure only for now; threshold decision deferred until baseline is known
- **D-10:** Update all packages (patch + minor) via `uv lock --upgrade`
- **D-11:** All 201 existing tests must remain green after updates — gate for committing the updated lock
- **D-12:** If a dependency update breaks tests: pin to last working version, document in commit message
- **D-13:** Run `uv audit` to identify CVEs
- **D-14:** CVEs with available fix: apply the fix (update the package)
- **D-15:** CVEs without available fix: document in a `SECURITY.md` file at project root with CVE ID, affected package, status, and mitigation notes

### Claude's Discretion

- Coverage report format (terminal vs HTML vs XML)
- Exact `pytest-cov` configuration flags (branch coverage, omit patterns)
- Order of operations within the phase (ruff first, deps second, or interleaved)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-01 | Codebase passes `ruff check` without violations; ruff + ruff-format as dev dependency | 42 violations identified and categorized; fix strategy mapped (30 auto, 12 manual) |
| TOOL-02 | pytest-cov configured, coverage report generatable via `uv run pytest --cov=src` | pytest-cov 7.1.0 on PyPI; config patterns documented |
| TOOL-03 | Ruff rules defined in pyproject.toml, all existing violations fixed | Violation breakdown: 20 W293 + 10 F401 (auto-fix) + 12 E402 (manual, one file) |
| DEP-01 | All packages updated to current compatible versions, uv.lock refreshed | `uv lock --upgrade` tested; 11 packages update; starlette 1.0.0 jump flagged as risk |
| DEP-02 | Security check via `uv audit` completed, known CVEs addressed or documented | 11 CVEs found: 10 in aiohttp (fixed in 3.13.4→3.13.5), 1 in pygments (fixed in 2.20.0) |
| DEP-03 | Unused dependencies identified and removed from pyproject.toml | httpx identified as test-only dep; should move to dev group, not removed |
</phase_requirements>

## Summary

Phase 1 is a pure tooling setup — no application logic changes. The codebase already has a `.ruff_cache/` directory indicating prior manual ruff use but zero ruff configuration in `pyproject.toml`. Running `ruff check src/` with the locked ruleset (`E,F,W`) and 120-char line length reveals exactly 42 violations across 19 files. All E501 (line-too-long) violations disappear entirely once the 120-char line length is configured — zero at that threshold. The remaining 42 break into 30 auto-fixable (W293 + F401) and 12 manual (E402 in `pipeline.py` only).

The dependency situation is straightforward but has one notable risk: `uv lock --upgrade` pulls starlette from 0.52.1 to 1.0.0 (major version jump via FastAPI's transitive dependency). FastAPI 0.135.3 declares compatibility but this is the highest-risk change and requires immediate test-suite validation. The security audit reveals 11 CVEs — all fixable via the planned upgrade: 10 in aiohttp (addressed by 3.13.3→3.13.5) and 1 in pygments (addressed by 2.19.2→2.20.0, a transitive dep via uvicorn[standard]). Pygments is not a direct dependency so the fix is handled automatically by `uv lock --upgrade`.

For DEP-03 (unused deps), `httpx` is listed in `[project] dependencies` but is only used in `tests/test_api.py` (FastAPI TestClient pattern). It should move to `[dependency-groups] dev`, not be removed. No other packages appear unused — all 13 production deps are imported in `src/`.

**Primary recommendation:** Execute in order — (1) ruff config + fix violations, (2) pytest-cov setup, (3) dep upgrade + tests green, (4) security audit + CVE remediation, (5) move httpx to dev deps. Each step is independently committable.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ruff | 0.15.10 | Linting + formatting | Standard Python linter per CLAUDE.md; replaces flake8/black/isort; fast |
| pytest-cov | 7.1.0 | Coverage measurement plugin for pytest | Standard pytest coverage integration; depends on coverage 7.x |
| coverage | 7.13.5 | Underlying coverage engine | Pulled transitively by pytest-cov |
| uv | 0.10.11 (installed) | Package management + audit | Mandatory per CLAUDE.md and project constraints |

### Critical Note on `ruff-format`

D-04 specifies adding `ruff` and `ruff-format` as dev dependencies. **`ruff format` is a built-in subcommand of the `ruff` package** — adding `ruff` to dev deps is sufficient to run `ruff format`. There IS a separate `ruff-format` package on PyPI (v0.5.1) but it is a PyO3 binding for programmatic use, not the CLI formatter. Only `ruff` needs to be added to dev deps to satisfy D-04's intent.

**`ruff format` scope in this phase:** The success criteria for TOOL-01 and TOOL-03 is `ruff check` exiting with zero violations. `ruff format --check src/` currently reports files that would be reformatted, but running `ruff format` is NOT part of Phase 1 success criteria. The formatter is installed as a tool (so developers can use it) but enforcing format compliance is out of scope — that would touch additional files beyond the 42 lint violations and constitutes a separate concern.

**Installation:**
```bash
uv add --dev ruff pytest-cov
```

**Version verification (verified 2026-04-13):**
```bash
uv run ruff --version  # 0.15.10
uv run pytest --co -q  # confirms 201 tests
```

## Architecture Patterns

### pyproject.toml Changes Required

```toml
[dependency-groups]
dev = [
    "pytest>=8.3.4",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.15.10",
    "pytest-cov>=7.1.0",
]

[tool.ruff]
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing"

[tool.coverage.run]
omit = ["tests/*"]
```

Notes on the pytest config:
- `addopts` with `--cov=src` makes coverage run on every `uv run pytest` invocation; acceptable since no threshold is set (D-09)
- `--cov-report=term-missing` shows which lines are uncovered inline; preferred for baseline documentation
- `[tool.coverage.run] omit = ["tests/*"]` avoids counting test code in source coverage

### Ruff Violation Fix Strategy

All violations are in `src/` only. Tests are clean.

| Rule | Count | Fix Method | Effort |
|------|-------|-----------|--------|
| W293 | 20 | `ruff check --fix` (auto) | Trivial |
| F401 | 10 | `ruff check --fix` (auto) | Trivial |
| E402 | 12 | Manual edit to `pipeline.py` only | Low |
| E501 | 0 | Zero at 120-char line length | None |

**E402 fix for `pipeline.py`:** Two module-level constants (`ANONYMOUS`, `ANONYMOUS_RESULT`) are defined between import groups at lines 18-20. Move both constants below all imports (after line 34). This is the entire manual work for TOOL-03.

```python
# Before (causes E402 on lines 21-34)
from src.core.pbx import LineState, PbxStateManager

ANONYMOUS = "anonymous"
ANONYMOUS_RESULT = ResolveResult(name="Anonym", number=ANONYMOUS, source="system")
from src.db.database import Database
...more adapter imports...

# After (compliant)
from src.core.pbx import LineState, PbxStateManager
from src.db.database import Database
from src.adapters.input.fritz_callmonitor import FritzCallmonitorAdapter
...all adapter imports...

ANONYMOUS = "anonymous"
ANONYMOUS_RESULT = ResolveResult(name="Anonym", number=ANONYMOUS, source="system")
```

### Anti-Patterns to Avoid

- **Adding `ruff-format` as a separate dep:** The PyPI `ruff-format` package is a PyO3 binding, not the CLI. The `ruff format` command ships with the `ruff` package itself.
- **Running `ruff format` as part of this phase:** TOOL-01/TOOL-03 success criteria is `ruff check` only. `ruff format` would reformat multiple additional files (src/adapters/base.py, mqtt.py, chain.py, etc.) beyond the 42 lint violations — this is a separate formatting pass and out of scope for Phase 1.
- **Setting `fail-under` in coverage config:** Explicitly deferred (D-09) — do not add `--cov-fail-under` to addopts or `fail_under` to `[tool.coverage.report]`.
- **Adding `--cov` to addopts permanently without consideration:** With no threshold, it slows every test run slightly. Acceptable for now since the goal is baseline measurement.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Linting configuration | Custom pre-commit scripts | `[tool.ruff]` in pyproject.toml | Standard toolchain integration |
| Coverage measurement | Manual file inspection | pytest-cov | Branch tracking, multi-format reports, CI integration |
| Security audit | Manual CVE lookup | `uv audit` | Queries OSV database, structured output, advisory URLs |
| Dependency version detection | Manual pypi.org browsing | `uv lock --upgrade` | Resolves version constraints correctly |

## Runtime State Inventory

Step 2.5 SKIPPED — this is a pure tooling/config phase. No renames, no data migrations, no stored state affected.

## Common Pitfalls

### Pitfall 1: Starlette Major Version Jump
**What goes wrong:** `uv lock --upgrade` upgrades starlette from 0.52.1 to 1.0.0 (pulled transitively by FastAPI). A major version bump may have breaking changes affecting middleware or response classes.
**Why it happens:** FastAPI 0.135.3 declares starlette compatibility, but consumer code using starlette internals directly may break.
**How to avoid:** Run `uv run pytest tests/ -v` immediately after `uv lock --upgrade` before committing. If tests fail, pin `starlette<1.0.0` in pyproject.toml and re-lock.
**Warning signs:** Test failures in `tests/test_api.py` or any route tests after upgrade.

### Pitfall 2: pytest addopts Breaking Existing Test Runs
**What goes wrong:** Adding `--cov=src` to `addopts` in `[tool.pytest.ini_options]` causes `pytest-cov` to be required even without the flag, breaking `uv run pytest` if pytest-cov isn't installed yet.
**Why it happens:** `addopts` is applied to every pytest invocation — including CI and developer runs where pytest-cov may not be in the venv.
**How to avoid:** Add pytest-cov to dev deps in the same commit as adding `addopts`. The `uv sync` step ensures pytest-cov is present.
**Warning signs:** `pytest: error: unrecognized arguments: --cov=src` after adding addopts without installing pytest-cov.

### Pitfall 3: F401 Auto-fix Removing `__all__`-Intended Imports
**What goes wrong:** `ruff check --fix` removes imports that appear unused but are re-exported for API consumers.
**Why it happens:** All 10 F401 violations are in implementation modules, not public-API `__init__.py` files. Review after auto-fix.
**How to avoid:** Review the diff after `ruff --fix`. In this codebase, `__init__.py` files are minimal/empty (no re-exports), so all 10 are genuinely unused.
**Warning signs:** Import removed that is used via `from module import *` elsewhere.

### Pitfall 4: `httpx` Removal Breaking Tests
**What goes wrong:** DEP-03 asks for removal of unused deps. `httpx` is not imported in `src/` but IS used in `tests/test_api.py` (FastAPI TestClient). Removing it breaks the test suite.
**Why it happens:** `httpx` is listed in `[project] dependencies` (production deps) but only needed for testing.
**How to avoid:** Move `httpx` to `[dependency-groups] dev`, do NOT remove it entirely.
**Warning signs:** `ModuleNotFoundError: No module named 'httpx'` in test_api.py after removal.

## Security Audit Findings

Verified by running `uv audit` on 2026-04-13:

### CVEs in aiohttp 3.13.3 (10 CVEs — all fixed in 3.13.4+)

All 10 CVEs are addressed by upgrading aiohttp to 3.13.5 (the version `uv lock --upgrade` selects):

| CVE | Summary | Fixed In |
|-----|---------|---------|
| CVE-2026-34514 | CRLF injection via multipart content-type header | 3.13.4 |
| CVE-2026-34517 | Late size enforcement for multipart fields — memory DoS | 3.13.4 |
| CVE-2026-34520 | C parser accepts null bytes in response headers | 3.13.4 |
| CVE-2026-34518 | Cookie/Proxy-Authorization leak on cross-origin redirect | 3.13.4 |
| CVE-2026-34525 | Accepts duplicate Host headers | 3.13.4 |
| CVE-2026-34513 | DoS via unbounded DNS cache in TCPConnector | 3.13.4 |
| CVE-2026-34516 | Multipart header size bypass | 3.13.4 |
| CVE-2026-34519 | HTTP response splitting via \r in reason phrase | 3.13.4 |
| CVE-2026-34515 | UNC SSRF / NTLMv2 credential theft on Windows | 3.13.4 |
| CVE-2026-22815 | Unlimited trailer headers — uncapped memory usage | 3.13.4 |

**Action:** All fixed by `uv lock --upgrade` (aiohttp 3.13.3 → 3.13.5). No separate pinning needed.

### CVE in pygments 2.19.2 (1 CVE — fixed in 2.20.0)

| CVE | Summary | Fixed In |
|-----|---------|---------|
| CVE-2026-4539 | ReDoS via inefficient GUID matching regex | 2.20.0 |

**Action:** Pygments is a transitive dependency (via uvicorn[standard]). Fixed by `uv lock --upgrade` (pygments 2.19.2 → 2.20.0). Not in pyproject.toml directly — no manual action needed.

**SECURITY.md not required** — all 11 CVEs have available fixes addressed by the planned upgrade. Per D-14, apply the fix; per D-15, SECURITY.md is only for CVEs without available fix.

## Dependency Update Details

Packages changed by `uv lock --upgrade` (verified 2026-04-13):

| Package | Current | Upgraded | Risk |
|---------|---------|---------|------|
| aiohttp | 3.13.3 | 3.13.5 | LOW (patch) — also fixes 10 CVEs |
| starlette | 0.52.1 | 1.0.0 | MEDIUM (major jump) — test gate required |
| fastapi | 0.135.1 | 0.135.3 | LOW (patch) |
| uvicorn | 0.42.0 | 0.44.0 | LOW (minor) |
| pytest | 9.0.2 | 9.0.3 | LOW (patch) |
| lxml | 6.0.2 | 6.0.4 | LOW (patch) |
| pygments | 2.19.2 | 2.20.0 | LOW (minor) — fixes CVE |
| python-multipart | 0.0.22 | 0.0.26 | LOW (patch) |
| anyio | 4.12.1 | 4.13.0 | LOW (minor) |
| attrs | 25.4.0 | 26.1.0 | LOW (minor) |
| click | 8.3.1 | 8.3.2 | LOW (patch) |

All other 38 packages in the lockfile remain unchanged.

## DEP-03 Analysis: Dependency Usage

Packages in `[project] dependencies` (13 total), usage verified by grepping `src/`:

| Package | Used in src/ | Used in tests/ | Action |
|---------|-------------|---------------|--------|
| fastapi | YES | YES | Keep in deps |
| uvicorn | YES | — | Keep in deps |
| jinja2 | YES | — | Keep in deps |
| python-multipart | YES (FastAPI form) | — | Keep in deps |
| pydantic | YES | — | Keep in deps |
| pydantic-settings | YES | — | Keep in deps |
| aiohttp | YES | — | Keep in deps |
| beautifulsoup4 | YES | — | Keep in deps |
| lxml | YES (via bs4) | — | Keep in deps |
| pyyaml | YES | — | Keep in deps |
| aiosqlite | YES | — | Keep in deps |
| aiomqtt | YES (lazy import) | YES | Keep in deps |
| httpx | NO | YES (test_api.py) | Move to dev group |

**httpx action:** Move from `[project] dependencies` to `[dependency-groups] dev`. This keeps it available for tests while removing it from the production Docker image.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (currently locked) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-01 | `ruff check src/` exits 0 | smoke | `uv run ruff check src/ --select E,F,W` | N/A (tool invocation) |
| TOOL-02 | `uv run pytest --cov=src` produces coverage report | smoke | `uv run pytest --cov=src --co -q` | ❌ Wave 0 (pytest-cov not yet installed) |
| TOOL-03 | Zero ruff violations after fixes | smoke | `uv run ruff check src/ --select E,F,W` | N/A (tool invocation) |
| DEP-01 | 201 tests green after `uv lock --upgrade` | regression | `uv run pytest tests/ -v` | ✅ existing |
| DEP-02 | `uv audit` shows no unaddressed CVEs | smoke | `uv audit` | N/A (tool invocation) |
| DEP-03 | httpx absent from `[project] dependencies` | manual check | `grep httpx pyproject.toml` | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -q --no-header`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite (201 tests) green + `uv run ruff check src/` exits 0

### Wave 0 Gaps
- [ ] No new test files needed — validation is smoke/regression on existing infrastructure
- [ ] pytest-cov must be installed before `--cov=src` addopts is committed: `uv add --dev pytest-cov`

*(All validation uses existing 201 tests + CLI tool invocations. No new test file authoring required for Phase 1.)*

## Code Examples

### Ruff configuration in pyproject.toml
```toml
# Source: https://docs.astral.sh/ruff/configuration/
[tool.ruff]
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W"]
```

### pytest-cov configuration in pyproject.toml
```toml
# Source: https://pytest-cov.readthedocs.io/en/latest/config.html
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing"

[tool.coverage.run]
omit = ["tests/*"]
```

### Running the ruff auto-fix
```bash
# Auto-fix W293 and F401 (safe, no semantic changes)
uv run ruff check src/ --select E,F,W --fix

# Verify remaining violations (should be only E402 in pipeline.py)
uv run ruff check src/ --select E,F,W
```

### Dependency workflow
```bash
# Upgrade all packages
uv lock --upgrade

# Install and run test gate
uv sync
uv run pytest tests/ -v

# Security audit
uv audit
```

### Moving httpx to dev deps
```bash
uv remove httpx
uv add --dev httpx
```

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | All dep management | ✓ | 0.10.11 | None — mandatory |
| ruff | TOOL-01, TOOL-03 | ✓ (after `uv add --dev ruff`) | 0.15.10 | None |
| pytest-cov | TOOL-02 | ✗ (not yet installed) | — | None — must be added |
| Python 3.12+ | Runtime | ✓ | (locked in pyproject.toml) | None |

**Missing dependencies with no fallback:**
- `pytest-cov` — must be added via `uv add --dev pytest-cov` as part of Wave 1

## Sources

### Primary (HIGH confidence)
- `uv audit` — live output, 2026-04-13
- `uv run ruff check src/ --select E,F,W --line-length 120 --statistics` — live output, 2026-04-13
- `uv lock --upgrade` — dry-run output showing upgrade candidates, 2026-04-13
- `pyproject.toml` — project configuration, current state
- https://docs.astral.sh/ruff/configuration/ — Ruff config reference
- https://pytest-cov.readthedocs.io/ — pytest-cov configuration

### Secondary (MEDIUM confidence)
- PyPI JSON API — verified ruff 0.15.10, pytest-cov 7.1.0, coverage 7.13.5 (2026-04-13)
- PyPI: `ruff-format` 0.5.1 exists but is a PyO3 binding, not the CLI formatter

### Tertiary (LOW confidence)
- None — all findings directly verified against live project state

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against live pypi + uv.lock
- Architecture: HIGH — pyproject.toml patterns verified against ruff + pytest-cov docs
- Pitfalls: HIGH — E402 and starlette jump directly observed in test run

**Research date:** 2026-04-13
**Valid until:** 2026-05-13 (stable tooling ecosystem)
