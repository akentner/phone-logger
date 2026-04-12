# Testing Patterns

**Analysis Date:** 2026-04-13

## Test Framework

**Runner:**
- pytest 8.3.4+
- Config: `pyproject.toml` with `asyncio_mode = "auto"`
- testpaths: `["tests"]`

**Assertion Library:**
- pytest built-in assertions (`assert x == y`)
- unittest.mock for mocking (`AsyncMock`, `MagicMock`, `patch`)

**Run Commands:**
```bash
uv run pytest tests/ -v              # Run all tests with verbose output
uv run pytest tests/test_pbx.py -v   # Run a single test file
uv run pytest tests/test_pbx.py::TestLineFSM -v  # Run a single test class
uv run pytest tests/test_pbx.py::TestLineFSM::test_initial_state_is_idle -v  # Run a single test
```

**Coverage:**
- Coverage not enforced (no pytest-cov config)
- No coverage badge or CI requirement visible
- Can be measured manually: `uv run pytest --cov=src tests/`

## Test File Organization

**Location:**
- All test files in `/home/akentner/Projects/phone-logger/tests/` directory (co-located, not alongside source)
- Mirrored structure: tests for `src/core/pbx.py` are in `tests/test_pbx.py`

**Naming:**
- All test files follow `test_<module>.py` pattern
- Test classes use `Test<Feature>` (e.g., `TestLineFSM`, `TestPbxStateManager`, `TestResolverChain`)
- Test functions use `test_<scenario>` (e.g., `test_initial_state_is_idle`, `test_ring_to_talking`)

**Structure:**
```
tests/
├── conftest.py                      # pytest configuration and shared fixtures
├── test_pbx.py                      # PBX FSM and state manager tests
├── test_phone_number.py             # Phone number normalization tests
├── test_resolver_chain.py           # Resolver chain pattern tests
├── test_pipeline_enrichment.py      # Event enrichment and caching tests
├── test_mqtt_output.py              # MQTT adapter tests (846 lines)
├── test_call_aggregation.py         # Call log and database tests
├── test_api.py                      # REST API model tests
├── test_fritz_parser.py             # Fritz!Box event parsing tests
└── ...                              # Other adapter and flow tests
```

## Test Structure

**Suite Organization:**
```python
# From src/tests/test_pbx.py
class TestLineFSM:
    """Tests for the per-line finite state machine."""

    def test_initial_state_is_idle(self):
        fsm = LineFSM(line_id=0)
        assert fsm.status == LineStatus.IDLE

    def test_idle_to_ring(self):
        fsm = LineFSM(line_id=0)
        status = fsm.transition(CallEventType.RING)
        assert status == LineStatus.RING
```

**Patterns:**

1. **Class-based test organization** — Tests grouped by feature/class being tested
2. **Arrange-Act-Assert** — Each test follows setup → action → verification flow
3. **Descriptive names** — Test names explain the scenario: `test_ring_disconnect_is_missed()`
4. **One assertion focus** — Each test typically checks one behavior (though may have multiple assertions)
5. **No setup/teardown** — Tests are independent; fixtures used for complex state

**Example Async Test:**
```python
# From tests/test_resolver_chain.py
class TestResolverChain:
    @pytest.fixture
    def chain(self):
        return ResolverChain()

    @pytest.mark.asyncio
    async def test_chain_stops_at_first_result(self, chain):
        first = MockResolver("first", ResolveResult(
            number="+491234567890", name="First", source="first"
        ))
        second = MockResolver("second", ResolveResult(
            number="+491234567890", name="Second", source="second"
        ))
        chain.add_adapter(first)
        chain.add_adapter(second)

        result = await chain.resolve("+491234567890")
        assert result.name == "First"
        assert first.resolve_called is True
        assert second.resolve_called is False
```

## Fixture Patterns

**Scope:** Function-scoped fixtures (default); async fixtures with `@pytest_asyncio.fixture`

**Common Patterns:**

1. **Simple value builders** — Return fresh instances:
```python
@pytest.fixture
def phone_config():
    return PhoneConfig(country_code="49", local_area_code="6181")
```

2. **Event factory helpers** — Private functions with underscore prefix:
```python
def _make_ring_event(
    connection_id: str = "0",
    number: str = "+491234567890",
    called: str = "990133",
    trunk: str = "SIP0",
) -> CallEvent:
    """Create a typical inbound RING event."""
    return CallEvent(
        number=number,
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="fritz_callmonitor",
        connection_id=connection_id,
        extension=called,
        caller_number=number,
        called_number=called,
        trunk_id=trunk,
    )
```

3. **Async database fixture** — Context manager with tempfile:
```python
@pytest.fixture
async def test_db():
    """Create a temporary test database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        db = Database(db_path)
        await db.connect()
        yield db
        await db.close()
```

4. **Mock dependency injection** — Return AsyncMock for services:
```python
@pytest.fixture
async def mock_db():
    db = AsyncMock()
    return db

@pytest.fixture
async def pipeline(app_config, mock_db):
    pl = Pipeline(app_config, mock_db)
    await pl.setup()
    return pl
```

5. **Configuration override pattern** — Builder with defaults:
```python
def _make_config(**overrides) -> AdapterConfig:
    cfg = {
        "broker": "localhost",
        "port": 1883,
        "topic_prefix": "phone-logger",
        "qos": 1,
        "retain": True,
    }
    cfg.update(overrides)
    return AdapterConfig(type="mqtt", name="test", enabled=True, config=cfg)
```

## Mocking

**Framework:** `unittest.mock` (standard library)

**Patterns:**

1. **AsyncMock for coroutines**:
```python
from unittest.mock import AsyncMock

mock_adapter = AsyncMock()
await mock_adapter.handle(event, result)
call_args = mock_adapter.handle.call_args
```

2. **Mock resolver implementations** — Minimal subclass:
```python
class MockResolver(BaseResolverAdapter):
    """Mock resolver for testing."""
    
    def __init__(self, name: str, result: ResolveResult | None = None):
        config = AdapterConfig(type="test", name=name, enabled=True)
        super().__init__(config)
        self._result = result
        self.resolve_called = False

    async def resolve(self, number: str):
        self.resolve_called = True
        return self._result
```

3. **Fake client injection** — Replace internal client with test double:
```python
def _inject_client(adapter: MqttAdapter) -> list[tuple]:
    """Inject a fake client and capture published messages."""
    published: list[tuple] = []

    class FakeClient:
        async def publish(self, topic, message, **kwargs):
            published.append((topic, message, kwargs))

    adapter._client = FakeClient()
    return published
```

4. **Exception simulation**:
```python
class BrokenResolver(BaseResolverAdapter):
    async def resolve(self, number):
        raise RuntimeError("Adapter crashed")
```

**What to Mock:**
- External services (MQTT broker, web scrapers) — use fake clients or mock at network boundary
- Database operations — use AsyncMock for database-dependent tests
- Input adapters — return canned events via fixture
- Other modules' adapters — use minimal Mock/AsyncMock instances

**What NOT to Mock:**
- Core business logic (LineFSM, phone number normalization) — test the real implementation
- Pydantic models — construct real instances, let validation run
- Enums — use real enum values
- Configuration objects — construct real AppConfig/PhoneConfig/etc. (unless testing config loading)

## Test Types

**Unit Tests:**
- Isolated class/function testing with minimal dependencies
- Example: `test_pbx.py` tests LineFSM state transitions without full PBX infrastructure
- Test individual adapters with mocked dependencies
- Scope: Single module or adapter

**Integration Tests:**
- Multi-component testing with real state passing
- Example: `test_pipeline_enrichment.py` tests event flow through pipeline with mocked DB
- Test full call flows (RING → CONNECT → DISCONNECT)
- Test resolver chain with multiple adapters
- Scope: Multiple modules working together

**E2E Tests:**
- Not present in current test suite
- Would require app startup with real database and external services
- Currently tested manually or via GitHub CI workflows

## Common Patterns

**Async Testing:**
```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result is not None
```

**Note:** `asyncio_mode = "auto"` in `pyproject.toml` means tests don't need `@pytest.mark.asyncio` decorator explicitly for auto-discovery, but it's used explicitly for clarity.

**Error Testing:**
```python
# Test that an exception is raised
def test_invalid_transition_resets_to_idle(self):
    """Invalid transition should reset to idle (fault-tolerant)."""
    fsm = LineFSM(line_id=0)
    fsm.transition(CallEventType.RING)
    # RING in RING state is invalid → reset to idle
    status = fsm.transition(CallEventType.RING)
    assert status == LineStatus.RING

# Test exception handling in adapters
class TestResolverChain:
    @pytest.mark.asyncio
    async def test_chain_handles_adapter_exception(self, chain):
        class BrokenResolver(BaseResolverAdapter):
            async def resolve(self, number):
                raise RuntimeError("Adapter crashed")
        
        broken = BrokenResolver(...)
        fallback = MockResolver("fallback", ResolveResult(...))
        chain.add_adapter(broken)
        chain.add_adapter(fallback)
        
        result = await chain.resolve("+491234567890")
        assert result.name == "Fallback"  # Fallback adapter was used
```

**State Transition Testing:**
```python
def test_full_inbound_flow(self):
    """idle -> ring -> talking -> finished"""
    fsm = LineFSM(line_id=0)
    assert fsm.transition(CallEventType.RING) == LineStatus.RING
    assert fsm.transition(CallEventType.CONNECT) == LineStatus.TALKING
    assert fsm.transition(CallEventType.DISCONNECT) == LineStatus.FINISHED
```

**Parameterized Scenarios:**
```python
class TestNormalize:
    """Tests for normalize() covering all expected input formats."""

    def test_e164_unchanged(self):
        assert normalize("+49301234567") == "+49301234567"

    def test_e164_with_spaces_stripped(self):
        assert normalize("+49 30 123456") == "+4930123456"

    def test_double_zero_prefix(self):
        assert normalize("0049301234567") == "+49301234567"

    def test_national_leading_zero(self):
        assert normalize("030123456") == "+4930123456"
    
    # ... etc for each format
```

## Coverage Analysis

**High Coverage Areas:**
- PBX state machine (`test_pbx.py` — 425 lines, comprehensive FSM testing)
- Phone number normalization (`test_phone_number.py` — 144 lines, all format variants)
- Resolver chain (`test_resolver_chain.py` — 111 lines, chain-of-responsibility pattern)
- Event pipeline enrichment (`test_pipeline_enrichment.py` — 462 lines, complex flow)
- MQTT output (`test_mqtt_output.py` — 846 lines, extensive adapter testing)

**Lower Coverage Areas:**
- REST API endpoints (`test_api.py` — 51 lines, mostly model validation, needs full app fixture)
- GUI/Jinja2 templating (no tests found)
- Web scraper resolvers (Tellows, DasTelefonbuch, KlarTelefonbuch) — likely covered in adapters

**Gaps:**
- No E2E tests with real database startup
- No async database operation tests (aiosqlite patterns)
- API route testing incomplete (uses mock objects, not full FastAPI TestClient)
- Configuration loading edge cases not fully tested

## Test Data Patterns

**Event Builders:**
All tests use helper functions to create canonical event instances:

```python
def _make_call_event(
    connection_id: str = "0",
    number: str = "+491234567890",
    extension: str = "10",
    trunk: str = "SIP0",
) -> CallEvent:
    """Create a typical outbound CALL event."""
    return CallEvent(
        number=number,
        direction=CallDirection.OUTBOUND,
        event_type=CallEventType.CALL,
        source="fritz_callmonitor",
        connection_id=connection_id,
        extension=extension,
        called_number=number,
        trunk_id=trunk,
    )
```

**Config Builders:**
Test-specific config factories avoid hardcoding test data:

```python
def _make_pbx_config() -> PbxConfig:
    """Create a test PBX config."""
    return PbxConfig(
        trunks=[
            TrunkConfig(id="SIP0", type=TrunkType.SIP, label="Internet 1"),
            TrunkConfig(id="SIP1", type=TrunkType.SIP, label="Internet 2"),
        ],
        msns=[
            MsnConfig(number="990133", label="Hauptnummer"),
        ],
        devices=[
            DeviceConfig(
                id="10", extension="10", name="Wohnzimmer", type=DeviceType.DECT
            ),
        ],
    )
```

## Async Test Configuration

**conftest.py Setup:**
```python
# From tests/conftest.py
import asyncio
import sys
from pathlib import Path

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
```

**Async Mode:** `asyncio_mode = "auto"` in pyproject.toml allows:
- All async tests auto-discovered
- Tests don't require explicit `@pytest.mark.asyncio` (but it's used for clarity)
- Event loop management handled automatically by pytest-asyncio

---

*Testing analysis: 2026-04-13*
