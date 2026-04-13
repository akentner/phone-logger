# Phase 1: Foundation - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the dev-tooling baseline: Ruff linting configured and enforced, coverage measurement operational, all v1 dependencies updated to current compatible versions, and a completed security audit via `uv audit`. This phase delivers infrastructure that all subsequent phases depend on.

Not in scope: fixing logic errors, adding tests, improving error handling (those are Phases 2–4).

</domain>

<decisions>
## Implementation Decisions

### Ruff configuration
- **D-01:** Rule categories: `E`, `F`, `W` only (pyflakes + pycodestyle basics) — minimal ruleset to avoid scope creep
- **D-02:** Line length: 120 characters — consistent with monorepo CLAUDE.md standard
- **D-03:** All existing violations must be fixed so `ruff check` passes with zero violations
- **D-04:** `ruff` added to `[dependency-groups] dev` in `pyproject.toml` — `ruff format` ships as a built-in subcommand of `ruff`; the separate `ruff-format` PyPI package is a PyO3 binding unrelated to the CLI formatter and must NOT be installed
- **D-05:** Ruff config lives in `[tool.ruff]` section of `pyproject.toml` (no separate `.ruff.toml`)

### Coverage measurement
- **D-06:** `pytest-cov` added to `[dependency-groups] dev` in `pyproject.toml`
- **D-07:** Coverage config in `[tool.pytest.ini_options]` or `[tool.coverage]` section of `pyproject.toml`
- **D-08:** Coverage measured via `uv run pytest --cov=src` — baseline report generated and documented
- **D-09:** No fail-under threshold — measure only for now; threshold decision deferred until baseline is known

### Dependency updates
- **D-10:** Update all packages (patch + minor) via `uv lock --upgrade`
- **D-11:** All 201 existing tests must remain green after updates — gate for committing the updated lock
- **D-12:** If a dependency update breaks tests: pin to last working version, document in commit message

### Security audit (CVE policy)
- **D-13:** Run `uv audit` to identify CVEs
- **D-14:** CVEs with available fix: apply the fix (update the package)
- **D-15:** CVEs without available fix: document in a `SECURITY.md` file at project root with CVE ID, affected package, status, and mitigation notes

### Claude's Discretion
- Coverage report format (terminal vs HTML vs XML)
- Exact `pytest-cov` configuration flags (branch coverage, omit patterns)
- Order of operations within the phase (ruff first, deps second, or interleaved)

</decisions>

<specifics>
## Specific Ideas

No specific UI/UX references — this is a pure tooling phase.

Key constraint from PROJECT.md: "Alle bestehenden 201 Tests müssen weiterhin grün bleiben" — this is a hard gate, not a preference.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project configuration
- `pyproject.toml` — Current dependency definitions, pytest config, what needs to be modified
- `CLAUDE.md` — Project conventions (120-char line length, ruff as linter, uv for deps)

### Requirements
- `.planning/REQUIREMENTS.md` §Dev-Tooling — TOOL-01, TOOL-02, TOOL-03 (exact acceptance criteria)
- `.planning/REQUIREMENTS.md` §Dependencies — DEP-01, DEP-02, DEP-03 (exact acceptance criteria)

### Constraints
- `.planning/STATE.md` — Known weaknesses and active constraints (201 tests must stay green)

No external ADRs or design docs for this phase — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml` already has `[dependency-groups] dev` with pytest — extend this section for ruff and pytest-cov
- `.ruff_cache/` exists — Ruff has been used manually before, no prior config to migrate

### Established Patterns
- `uv sync` + `uv run pytest tests/ -v` is the dev workflow — changes must stay compatible with this
- `asyncio_mode = "auto"` in pytest config must be preserved

### Integration Points
- `[tool.pytest.ini_options]` section: add `addopts = "--cov=src"` or equivalent for coverage defaults
- `[tool.ruff]` section: new section to add for linting config
- `uv.lock`: will be refreshed as part of dependency updates

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-04-13*
