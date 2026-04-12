# Coding Conventions

**Analysis Date:** 2026-04-13

## Naming Patterns

**Files:**
- Lowercase with underscores: `phone_number.py`, `fritz_callmonitor.py`
- Adapter implementations follow pattern: `<service>_<adapter_type>.py` (e.g., `tellows.py`, `sqlite_db.py`)
- Test files prefixed with `test_` (e.g., `test_pbx.py`, `test_phone_number.py`)

**Functions:**
- snake_case for all functions: `normalize()`, `enrich_event()`, `get_line_state()`
- Private/internal functions prefixed with underscore: `_on_event()`, `_setup_resolver_adapters()`, `_is_internal()`
- Helper functions in tests prefixed with underscore: `_make_pbx_config()`, `_make_ring_event()`, `_inject_client()`
- Properties use @property decorator: `rest_input`, `adapters`, `status`

**Variables:**
- snake_case for all variables: `call_log_registered`, `norm_updates`, `connection_id`
- Constants in UPPERCASE: `TERMINAL_STATES`, `ANONYMOUS`, `DEFAULT_DATA_PATH`
- Private instance attributes prefixed with underscore: `_status`, `_connected`, `_input_adapters`, `_mqtt_adapters`, `_resolve_cache`
- Dictionary unpacking for config/defaults: `defaults.update(overrides)` pattern in test builders

**Types:**
- Enum classes defined as PascalCase: `CallDirection`, `CallEventType`, `LineStatus`, `NumberType`
- Enum values as lowercase strings: `INBOUND = "inbound"`, `IDLE = "idle"`
- Pydantic BaseModel subclasses in PascalCase: `CallEvent`, `ResolveResult`, `PipelineResult`, `LineState`

## Code Style

**Formatting:**
- No explicit formatter configured (no `.prettierrc`, `.black`, `.ruff.toml` in root)
- Uses implicit Python defaults: 4-space indentation, line wrapping as needed
- Import statements not automatically enforced but followed naturally

**Linting:**
- Ruff cache present (`.ruff_cache/`) but no explicit config in `pyproject.toml`
- No `.flake8`, `.pylint`, or similar config files
- Code adheres to PEP 8 style conventions naturally

## Import Organization

**Order:**
1. Standard library imports (`import asyncio`, `import logging`, `from pathlib import Path`)
2. Third-party imports (`from pydantic import BaseModel`, `import aiohttp`, `from yaml import ...`)
3. Local/relative imports (`from src.config import ...`, `from src.core.event import ...`)

**Path Aliases:**
- No path aliases configured (no `jsconfig.json` or `tsconfig.json` equivalents in Python)
- All imports use full relative paths from project root: `from src.adapters.base import ...`
- TYPE_CHECKING used for circular import avoidance: `if TYPE_CHECKING: from src.core.pbx import LineState`

**Conventions:**
- Empty lines between import groups (standard → third-party → local)
- Single-line imports preferred: `from src.core.event import CallEvent` not multiple lines

## Error Handling

**Patterns:**
- Try-except blocks used around external operations (file I/O, network, DB):
  ```python
  try:
      await adapter.start(self._on_event)
  except Exception:
      logger.exception("Failed to start input adapter '%s'", adapter.name)
  ```
- Broad `Exception` catch with logging (not silent failures)
- `logger.exception()` used when catching errors (includes traceback)
- RuntimeError raised for application state violations: `raise RuntimeError("Application not initialized")`
- HTTPException (FastAPI) used for API endpoints: `raise HTTPException(status_code=404, detail="...")`
- Pydantic validation errors allowed to propagate (config validation)
- asyncio.CancelledError explicitly caught and re-raised/handled in async contexts
- Specific exception types caught when needed (e.g., `asyncio.TimeoutError`, `json.JSONDecodeError`)

**Examples from codebase:**
- `src/core/pipeline.py:85-88` — Try/except with logging around adapter.start()
- `src/adapters/mqtt.py:171-220` — Multiple exception handlers for different failure modes
- `src/adapters/input/fritz_callmonitor.py:115-121` — Catch and log parse failures

## Logging

**Framework:** Python's standard `logging` module

**Patterns:**
- Every module gets: `logger = logging.getLogger(__name__)`
- Adapter instances get per-adapter logger: `self.logger = logging.getLogger(f"{__name__}.{self.name}")`
- Log levels used correctly:
  - `logger.debug()` — Low-level details (normalization, caching decisions)
  - `logger.info()` — Lifecycle events (adapter start/stop), pipeline transitions
  - `logger.warning()` — Configuration issues, unexpected states, adapter skips
  - `logger.exception()` — Error paths with full traceback
  - `logger.error()` — Non-fatal errors

**Examples:**
```python
logger.debug("Normalized number: %r -> %r", event.number, normalized)
logger.info("Pipeline setup complete: %d input, %d resolver, %d output adapters", ...)
logger.warning("Multiple call_log adapters configured — only first instance used")
logger.exception("Failed to start output adapter '%s'", adapter.name)
```

**Formatting:**
- String formatting with % operator: `logger.info("Value: %s", value)` (not f-strings for logger calls)
- Multiple arguments passed as tuple, not single formatted string

## Comments

**When to Comment:**
- Class-level docstrings explaining purpose and public interface (always)
- Function-level docstrings explaining parameters, returns, and exceptions (always for public methods)
- Inline comments sparingly — code should be self-explanatory
- Comments explain *why*, not *what* the code does
- Examples in docstrings for complex utilities (see `src/core/phone_number.py`)

**JSDoc/TSDoc:**
- Not used (Python project, not TypeScript)
- Google-style docstrings in some modules (Args, Returns, Examples sections)
- Pydantic Field descriptions used in models: `Field(..., description="...")`

**Examples:**
```python
class CallEvent(BaseModel):
    """Normalized call event from any input adapter."""
    
    number: str = Field(
        ..., description="Phone number of the remote party (normalized E.164)"
    )

def normalize(
    number: str,
    country_code: str = "49",
    local_area_code: str = "",
) -> str:
    """
    Normalize a phone number to E.164 format (+CCXXXXXXXXX).

    Args:
        number: Raw phone number in any common format.
        country_code: Default country code without leading +/00 (default: "49" for Germany).
        local_area_code: Local area code without leading 0 (e.g. "30" for Berlin).

    Returns:
        E.164 formatted number (e.g. "+49301234567").

    Examples:
        >>> normalize("030123456", country_code="49")
        '+4930123456'
    """
```

## Function Design

**Size:** Most functions 10-50 lines; complex orchestration like `_on_event()` is 150+ lines with clear numbered steps

**Parameters:**
- Positional parameters for required inputs: `resolve(number)`
- Keyword-only parameters for options: `async def handle(..., *, line_state=None)`
- Type hints required: `def normalize(number: str, country_code: str = "49") -> str:`
- Callbacks use generic Callable types: `Callable[[CallEvent], Coroutine]`

**Return Values:**
- Functions return None explicitly: `async def stop(self) -> None:`
- Optional returns use `Optional[Type]`: `async def resolve(self, number: str) -> Optional[ResolveResult]:`
- Model objects returned as Pydantic BaseModel instances
- Multiple returns via unpacking (rare) or via method chaining (common for adapters)

**Examples:**
```python
# From src/core/pipeline.py
async def resolve(self, number: str) -> Optional[ResolveResult]:
    """Resolve a phone number through the chain (for direct API calls)."""
    normalized = self.normalize(number)
    if normalized == ANONYMOUS:
        return ANONYMOUS_RESULT
    return await self.resolver_chain.resolve(normalized)

# From src/adapters/base.py
async def handle(
    self,
    event: CallEvent,
    result: Optional[ResolveResult],
    *,
    line_state: Optional["LineState"] = None,
) -> None:
    """Handle a processed call event with its resolve result and optional PBX line state."""
```

## Module Design

**Exports:**
- All public classes and functions in `__all__` (if defined) or implicitly by being top-level
- No barrel files (no `__init__.py` re-exports beyond `from . import submodule`)
- Adapter implementations imported explicitly in pipeline: `from src.adapters.input.fritz_callmonitor import FritzCallmonitorAdapter`

**Barrel Files:**
- `src/adapters/__init__.py`, `src/adapters/input/__init__.py`, etc. exist but are empty or minimal
- No re-exporting from `__init__.py` — clients import directly from implementation modules

**Examples:**
- `src/core/__init__.py` — Empty
- `src/adapters/base.py` — Defines abstract base classes
- `src/adapters/input/fritz_callmonitor.py` — Concrete implementation (imported directly)

## Async Patterns

**Coroutines:**
- All I/O operations are async: `async def start()`, `async def resolve()`, `async def handle()`
- `await` used consistently when calling async functions
- `await asyncio.gather()` used for parallel execution when needed
- Task creation via `asyncio.create_task()` for background operations (e.g., auto-reset timer in PBX)

**Examples:**
```python
async def start(self) -> None:
    """Start all adapters."""
    for adapter in self._output_adapters:
        try:
            await adapter.start()
        except Exception:
            logger.exception("Failed to start output adapter '%s'", adapter.name)
```

## Type Annotations

**Coverage:** All function signatures fully annotated

**Standards:**
- Use `Optional[Type]` for optional values (not `Type | None`)
- Use `list[Type]` (PEP 585, Python 3.9+) not `List[Type]`
- Use `dict[Key, Value]` not `Dict[Key, Value]`
- TYPE_CHECKING guards for circular imports and forward references

**Examples:**
```python
# From src/core/pbx.py
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.pbx import LineState

# From src/adapters/base.py
async def handle(
    self,
    event: CallEvent,
    result: Optional[ResolveResult],
    *,
    line_state: Optional["LineState"] = None,
) -> None:
```

---

*Convention analysis: 2026-04-13*
