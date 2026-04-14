# Phase 2: Code Quality - Research

**Researched:** 2026-04-14
**Domain:** Python SQL safety, git hygiene, dead code analysis
**Confidence:** HIGH

## Summary

Phase 2 has three requirements: replace f-string SQL query assembly (CODE-01), commit the uncommitted `src/adapters/mqtt.py` change (CODE-02), and verify the codebase has no dead code by Ruff (CODE-03).

The SQL situation is less dangerous than CODE-01's description implies — all user data already flows through `?` parameters; only query *structure* is assembled with f-strings from code-controlled values. The refactoring is convention enforcement, not vulnerability remediation. Existing query-builder patterns (clause lists + param lists) are already correct; only the final assembly line needs to change from f-string to string join.

The MQTT change is a functional bug fix: display name derivation was moved above the payload dict so `_serialize_line_state()` receives the resolved names. The current working tree already contains the corrected version. CODE-03 is entirely satisfied by the current Ruff configuration (E, F, W rules with zero violations); no code changes are needed — it is a verification-only task.

**Primary recommendation:** Three distinct plans — SQL refactor, MQTT commit, Ruff verification — each independent and completable in a single commit.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CODE-01 | f-string SQL concatenation in `src/db/database.py` replaced by safe parametrized patterns | Inventory of all 8 f-string uses in database.py; 5 are structural assembly, 3 are value strings already in params — see Architecture Patterns |
| CODE-02 | Uncommitted changes in `src/adapters/mqtt.py` reviewed, cleaned, and committed | Diff analyzed: it is a bug fix (display names now derived before payload dict), ready to commit as-is |
| CODE-03 | No unused imports, unreachable branches, or dead variables — verified by Ruff | Ruff (E, F, W) returns zero violations today; verification command is sufficient |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiosqlite | 0.20.0+ | Async SQLite driver (already in use) | Project standard; parametrized queries via `?` placeholders |
| Ruff | 0.11.4+ | Linting, dead code detection | Already configured in pyproject.toml; Phase 1 established this |
| git | system | Version control for committing MQTT fix | Standard |

No new dependencies required for this phase.

## Architecture Patterns

### CODE-01: SQL f-string Inventory

All f-strings in `src/db/database.py` categorized:

**Structural assembly (query skeleton uses f-string) — must fix:**

| Line(s) | Method | Pattern | Actual Risk |
|---------|--------|---------|-------------|
| 179 | `update_contact` | `f"UPDATE contacts SET {', '.join(updates)} ..."` | `updates` contains `f"{key} = ?"` where `key` comes from a hardcoded whitelist — no injection possible but convention violation |
| 168 | `update_contact` | `f"{key} = ?"` | Key from whitelist; produces column name fragment |
| 335 | `get_raw_events` | `f"SELECT * FROM raw_events{where} ..."` | `where` assembled from code-controlled strings |
| 395 | `get_call_log` | `f"SELECT * FROM call_log{where} ..."` | Same pattern |
| 568 | `get_calls` | `f"c.msn IN ({placeholders})"` | `placeholders = ",".join("?" * len(msn))` — standard safe IN pattern |
| 583-588 | `get_calls` | `f"""SELECT c.*, ... FROM calls c{join}{where} ..."""` | `join` and `where` from code-controlled strings |

**Value strings already in `?` params (NOT structural — leave as-is):**

| Line | Method | Pattern | Why Safe |
|------|--------|---------|----------|
| 387 | `get_call_log` | `f"%{number_filter}%"` | Passed as `?` param, not SQL text |
| 564 | `get_calls` | `f"%{search}%"` | Passed as `?` param, not SQL text |

**Recommended fix pattern:**

Replace f-string structural assembly with explicit string concatenation:

```python
# Before (f-string SQL assembly)
where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
db_cursor = await self.db.execute(
    f"SELECT * FROM raw_events{where} ORDER BY id DESC LIMIT ?",
    params,
)

# After (plain string concat — no f-string in SQL position)
where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
db_cursor = await self.db.execute(
    "SELECT * FROM raw_events" + where + " ORDER BY id DESC LIMIT ?",
    params,
)
```

For `update_contact`, the column whitelist guard makes injection impossible but the convention should still be fixed. The cleanest approach:

```python
# Column whitelist is the guard; f-string generates the fragment list
ALLOWED_CONTACT_COLUMNS = frozenset({"name", "number_type", "tags", "notes", "spam_score"})

# Then in update_contact:
for key, value in kwargs.items():
    if value is not None and key in ALLOWED_CONTACT_COLUMNS:
        ...
        updates.append(key + " = ?")   # plain concat, no f-string in SQL
```

For the MSN IN clause (line 568):

```python
placeholders = ",".join("?" * len(msn))
where_clauses.append("c.msn IN (" + placeholders + ")")  # no f-string
```

### CODE-02: MQTT Uncommitted Change Analysis

The diff moves the display name derivation block **before** the payload dict construction:

```
Before: _serialize_line_state(line_state)          # no display names in payload
After:  _serialize_line_state(line_state, caller_display, called_display)  # names included
```

This is a **functional bug fix**: in the committed version, display names were derived after being used in the payload, so `line_state` in MQTT events never carried `caller_display` / `called_display`. The working tree is already in the correct state.

**Commit decision:** Commit as-is. The change is clean, purposeful, and has no side effects. The commit message should describe the functional fix, not characterize it as cleanup.

**No further modifications needed** to `src/adapters/mqtt.py` to satisfy CODE-02. Review, confirm correctness, commit.

### CODE-03: Dead Code Verification

Current Ruff configuration (from `pyproject.toml`):

```toml
[tool.ruff.lint]
select = ["E", "F", "W"]
```

Relevant rules already enabled:
- `F401` — unused imports
- `F811` — redefinition of unused name
- `F841` — local variable assigned but never used

**Current status:** `uv run ruff check src/` returns zero violations. CODE-03 is already satisfied from Phase 1 work.

**Verification command only:**

```bash
uv run ruff check src/
```

This is the sole deliverable for CODE-03. No code changes are needed or expected.

**Note on broader dead code:** Ruff (E/F/W) does not detect unreachable branches or unused class-level attributes. The requirement says "verified by Ruff" — this scopes the task to what Ruff can actually check, which is already passing.

### Anti-Patterns to Avoid

- **Do not change LIKE parameter values:** `f"%{search}%"` at lines 387 and 564 are passed as `?` params, not SQL text. Changing these would provide no benefit and could introduce bugs.
- **Do not expand Ruff rule set for CODE-03:** The success criterion says "verified by Ruff" against the configured ruleset (E, F, W). Adding rules like `B` or `UP` would introduce new violations unrelated to this phase and require separate remediation.
- **Do not alter MQTT topic structure or payload keys:** The mqtt.py change only affects how display names flow into `_serialize_line_state()`. MQTT topic format and payload schema are unchanged.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQL query builder | Custom ORM or builder class | Plain string concat with existing clause-list pattern | ORM migration is explicitly out of scope; the existing pattern with `?` params is correct |
| Dead code scanner | Custom AST walker | Ruff (already configured) | Ruff F-rules cover the requirement scope |

## Runtime State Inventory

Step 2.5 SKIPPED — this phase has no renaming, refactoring, or migration of stored identifiers. All changes are code-only within the same file paths and function signatures.

## Environment Availability

Step 2.6 SKIPPED — no external dependencies beyond the project's own code and dev tooling (uv, ruff, git) which Phase 1 confirmed are present.

## Common Pitfalls

### Pitfall 1: Over-scoping SQL f-string fix
**What goes wrong:** Treating `f"%{search}%"` as SQL injection risk and trying to eliminate it.
**Why it happens:** The term "f-string SQL" gets applied to all f-strings near SQL, including those used for LIKE parameter values.
**How to avoid:** Distinguish structural assembly (the f-string appears as part of the SQL text passed to `execute()`) from value preparation (the f-string result is passed as a `?` param). Only the former needs fixing.
**Warning signs:** Changing lines 387 or 564 — those are correct as-is.

### Pitfall 2: Rewriting `update_contact` logic
**What goes wrong:** Refactoring the entire update method rather than just replacing the f-string fragment.
**Why it happens:** The column whitelist check (lines 158-165) looks like it could be improved.
**How to avoid:** Minimum change: replace `f"{key} = ?"` with `key + " = ?"` and `f"UPDATE contacts SET {', '.join(updates)} ..."` with string join. No logic changes.

### Pitfall 3: Modifying the MQTT diff before committing
**What goes wrong:** Adding additional "improvements" to `mqtt.py` during CODE-02.
**Why it happens:** Reviewer sees things to improve while reviewing the uncommitted change.
**How to avoid:** Scope CODE-02 strictly to committing the existing diff. Additional changes belong in Phase 3 (MQTT logging) or separate tasks.

### Pitfall 4: Expanding Ruff rule set as part of CODE-03
**What goes wrong:** Running `ruff check --select ALL` and attempting to fix all violations.
**Why it happens:** "No dead code" sounds like it justifies broader rules.
**How to avoid:** The requirement says "verified by Ruff" — the current ruleset (E, F, W) is the measurement. Zero violations already. Verification only.

## Code Examples

### Dynamic WHERE clause without f-string (canonical pattern)

```python
# Source: standard aiosqlite parametrized query pattern
where_clauses = []
params: list = []

if source_filter:
    where_clauses.append("source = ?")
    params.append(source_filter)
if cursor:
    where_clauses.append("id < ?")
    params.append(cursor)

# No f-string in SQL text:
where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
params.append(limit)
db_cursor = await self.db.execute(
    "SELECT * FROM raw_events" + where + " ORDER BY id DESC LIMIT ?",
    params,
)
```

### IN clause without f-string

```python
# Safe IN clause — placeholders is code-controlled, not user input
placeholders = ",".join("?" * len(msn))
where_clauses.append("c.msn IN (" + placeholders + ")")
params.extend(msn)
```

### UPDATE with column whitelist, no f-string

```python
ALLOWED_CONTACT_COLUMNS = frozenset({"name", "number_type", "tags", "notes", "spam_score"})

updates = []
params = []
for key, value in kwargs.items():
    if value is not None and key in ALLOWED_CONTACT_COLUMNS:
        if key == "tags":
            value = json.dumps(value)
        updates.append(key + " = ?")   # plain concat, whitelist-guarded
        params.append(value)

# ...
await self.db.execute(
    "UPDATE contacts SET " + ", ".join(updates) + " WHERE number = ?",
    params,
)
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4+ with pytest-asyncio 0.24.0+ |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/ -q --tb=short` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CODE-01 | SQL queries use `?` params only, no f-string in SQL text | manual review + ruff | `uv run ruff check src/db/database.py` | N/A — code review |
| CODE-01 | All 201 existing tests still pass after refactor | regression | `uv run pytest tests/ -q` | Yes |
| CODE-02 | MQTT change committed; git status clean for mqtt.py | git | `git status src/adapters/mqtt.py` | N/A |
| CODE-02 | All 201 existing tests still pass | regression | `uv run pytest tests/ -q` | Yes |
| CODE-03 | Ruff returns zero violations | lint | `uv run ruff check src/` | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -q --tb=short`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green + `uv run ruff check src/` clean before `/gsd:verify-work`

### Wave 0 Gaps

None — existing test infrastructure covers all phase requirements. CODE-01 and CODE-02 are regression-tested by the existing 201 tests; CODE-03 requires no test file.

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `src/db/database.py` (lines 168, 179, 335, 387, 395, 564, 568, 583-588)
- Direct diff inspection of `src/adapters/mqtt.py` uncommitted change
- `uv run ruff check src/` — verified zero violations under configured ruleset
- `pyproject.toml` — Ruff configuration and pytest configuration confirmed

### Secondary (MEDIUM confidence)
- aiosqlite parametrized query convention — standard Python DB-API 2.0 `?` placeholder pattern

## Metadata

**Confidence breakdown:**
- CODE-01 f-string inventory: HIGH — every f-string in the file examined directly
- CODE-02 diff analysis: HIGH — full diff read and semantically understood
- CODE-03 verification: HIGH — `ruff check` run with configured rules returned zero violations

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable domain, no external dependencies)
