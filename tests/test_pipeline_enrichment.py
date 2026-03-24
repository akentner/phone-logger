"""Tests for event enrichment from LineState and ResolveResult caching in pipeline."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.core.event import (
    CallDirection,
    CallEvent,
    CallEventType,
    DeviceInfo,
    ResolveResult,
)
from src.core.pbx import LineState, LineStatus
from src.core.pipeline import Pipeline, ANONYMOUS_RESULT
from src.config import (
    AdapterConfig,
    AppConfig,
    PhoneConfig,
    PbxConfig,
    MsnConfig,
    TrunkConfig,
)


@pytest.fixture
def phone_config():
    return PhoneConfig(country_code="49", local_area_code="6181")


@pytest.fixture
def pbx_config():
    return PbxConfig(
        trunks=[
            TrunkConfig(id="SIP0"),
            TrunkConfig(id="SIP1"),
            TrunkConfig(id="SIP2"),
            TrunkConfig(id="SIP3"),
            TrunkConfig(id="SIP4"),
            TrunkConfig(id="SIP5"),
        ],
        msns=[
            MsnConfig(number="990133", label="Zentrale"),
            MsnConfig(number="123456", label="Fax"),
        ],
    )


@pytest.fixture
def app_config(phone_config, pbx_config):
    config = AppConfig(phone=phone_config, pbx=pbx_config)
    config.input_adapters = []
    config.resolver_adapters = []
    config.output_adapters = []
    return config


@pytest.fixture
async def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
async def pipeline(app_config, mock_db):
    pl = Pipeline(app_config, mock_db)
    await pl.setup()
    return pl


# --- Event Enrichment from LineState ---


@pytest.mark.asyncio
async def test_disconnect_enriched_from_line_state(pipeline):
    """DISCONNECT event should get caller_number, called_number, trunk_id from LineState."""
    # Setup: RING event that establishes line state
    ring_event = CallEvent(
        number="+491234567890",
        caller_number="+491234567890",
        called_number="+496181123456",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="1",
        trunk_id="SIP0",
    )

    # Add the event to the PBX FSM
    pipeline.pbx.enrich_event(ring_event)
    ring_event = ring_event.model_copy(update={"line_id": 1})
    pipeline.pbx.update_state(ring_event)

    # Now create DISCONNECT event (which has no number/caller/called details from Fritz)
    disconnect_event = CallEvent(
        number="",  # Empty from Fritz!Box
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="1",
    )
    disconnect_event = disconnect_event.model_copy(update={"line_id": 1})

    # Mock output adapter to capture event
    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    # Process the disconnect event
    await pipeline._on_event(disconnect_event)

    # Check that adapter received enriched event
    call_args = mock_adapter.handle.call_args
    processed_event = call_args[0][0]

    assert processed_event.caller_number == "+491234567890"
    assert processed_event.called_number == "+496181123456"
    assert processed_event.trunk_id == "SIP0"
    assert (
        processed_event.number == "+491234567890"
    )  # From LineState caller for INBOUND


@pytest.mark.asyncio
async def test_connect_enriched_from_line_state(pipeline):
    """CONNECT event should get caller/called numbers and trunk_id from LineState."""
    # Setup: CALL event (outbound)
    call_event = CallEvent(
        number="+491234567890",
        caller_number="+496181990133",
        called_number="+491234567890",
        direction=CallDirection.OUTBOUND,
        event_type=CallEventType.CALL,
        source="test",
        connection_id="2",
        trunk_id="SIP1",
    )

    pipeline.pbx.enrich_event(call_event)
    call_event = call_event.model_copy(update={"line_id": 2})
    pipeline.pbx.update_state(call_event)

    # CONNECT event (typically has no details from Fritz)
    connect_event = CallEvent(
        number="",
        direction=CallDirection.OUTBOUND,
        event_type=CallEventType.CONNECT,
        source="test",
        connection_id="2",
    )
    connect_event = connect_event.model_copy(update={"line_id": 2})

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    await pipeline._on_event(connect_event)

    call_args = mock_adapter.handle.call_args
    processed_event = call_args[0][0]

    assert processed_event.caller_number == "+496181990133"
    assert processed_event.called_number == "+491234567890"
    assert processed_event.trunk_id == "SIP1"
    assert (
        processed_event.number == "+491234567890"
    )  # From LineState called for OUTBOUND


# --- ResolveResult Caching ---


@pytest.mark.asyncio
async def test_resolve_result_cached_on_ring(pipeline):
    """ResolveResult from RING should be cached for DISCONNECT."""
    ring_event = CallEvent(
        number="+491234567890",
        caller_number="+491234567890",
        called_number="+496181123456",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="3",
    )

    # Mock resolver to return a result
    mock_resolve_result = ResolveResult(
        name="John Doe",
        number="+491234567890",
        source="test_resolver",
    )
    pipeline.resolver_chain.resolve = AsyncMock(return_value=mock_resolve_result)

    # Enrich and process RING
    pipeline.pbx.enrich_event(ring_event)
    ring_event = ring_event.model_copy(update={"line_id": 3})

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    await pipeline._on_event(ring_event)

    # Check that result was cached
    assert pipeline._resolve_cache.get(3) == mock_resolve_result

    # Check that adapter received the result
    call_args = mock_adapter.handle.call_args
    assert call_args[0][1].name == "John Doe"


@pytest.mark.asyncio
async def test_cached_result_used_on_disconnect(pipeline):
    """DISCONNECT should retrieve ResolveResult from cache."""
    # First: RING with resolver
    ring_event = CallEvent(
        number="+491234567890",
        caller_number="+491234567890",
        called_number="+496181123456",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="4",
    )

    mock_resolve_result = ResolveResult(
        name="Jane Smith",
        number="+491234567890",
        source="test_resolver",
    )
    pipeline.resolver_chain.resolve = AsyncMock(return_value=mock_resolve_result)

    pipeline.pbx.enrich_event(ring_event)
    ring_event = ring_event.model_copy(update={"line_id": 4})

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    await pipeline._on_event(ring_event)
    mock_adapter.reset_mock()

    # Second: DISCONNECT (no resolver call)
    disconnect_event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="4",
    )
    disconnect_event = disconnect_event.model_copy(update={"line_id": 4})

    await pipeline._on_event(disconnect_event)

    # Check that adapter received cached result
    call_args = mock_adapter.handle.call_args
    assert call_args[0][1].name == "Jane Smith"  # From cache, not resolver


@pytest.mark.asyncio
async def test_cache_cleaned_up_on_terminal_state(pipeline):
    """Cache should be cleared after terminal state (finished/missed/notReached)."""
    # RING → cache populated
    ring_event = CallEvent(
        number="+491234567890",
        caller_number="+491234567890",
        called_number="+496181123456",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="5",
    )

    mock_resolve_result = ResolveResult(
        name="Bob", number="+491234567890", source="test"
    )
    pipeline.resolver_chain.resolve = AsyncMock(return_value=mock_resolve_result)

    pipeline.pbx.enrich_event(ring_event)
    ring_event = ring_event.model_copy(update={"line_id": 5})

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    await pipeline._on_event(ring_event)
    assert 5 in pipeline._resolve_cache

    # DISCONNECT → reaches terminal state
    disconnect_event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="5",
    )
    disconnect_event = disconnect_event.model_copy(update={"line_id": 5})

    await pipeline._on_event(disconnect_event)

    # Cache should be cleared
    assert 5 not in pipeline._resolve_cache


# --- Edge Cases ---


@pytest.mark.asyncio
async def test_disconnect_no_crash_without_line_id(pipeline):
    """DISCONNECT without line_id should not crash."""
    disconnect_event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="999",
        line_id=None,
    )

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    # Should not raise
    await pipeline._on_event(disconnect_event)
    assert mock_adapter.handle.called


@pytest.mark.asyncio
async def test_disconnect_no_crash_with_missing_line_state(pipeline):
    """DISCONNECT for unconfigured line should not crash."""
    disconnect_event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="888",
        line_id=999,  # Non-existent line
    )

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    # Should not raise
    await pipeline._on_event(disconnect_event)
    assert mock_adapter.handle.called


@pytest.mark.asyncio
async def test_anonymous_calls_use_cached_result(pipeline):
    """Anonymous RING → DISCONNECT should preserve name from cache."""
    ring_event = CallEvent(
        number="anonymous",
        caller_number="anonymous",
        called_number="+496181123456",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="6",
    )

    # Anonymous calls don't hit resolver, get ANONYMOUS_RESULT
    pipeline.pbx.enrich_event(ring_event)
    ring_event = ring_event.model_copy(update={"line_id": 6})

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    await pipeline._on_event(ring_event)

    # ANONYMOUS_RESULT should be cached
    assert pipeline._resolve_cache.get(6).name == "Anonym"

    mock_adapter.reset_mock()

    # DISCONNECT should use cached result
    disconnect_event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="6",
    )
    disconnect_event = disconnect_event.model_copy(update={"line_id": 6})

    await pipeline._on_event(disconnect_event)

    call_args = mock_adapter.handle.call_args
    assert call_args[0][1].name == "Anonym"  # ANONYMOUS_RESULT from cache


# --- Number Normalization ---


@pytest.mark.asyncio
async def test_outbound_called_number_is_normalized(pipeline):
    """For an outbound CALL, called_number without area code should be normalized to E.164."""
    call_event = CallEvent(
        number="82628",  # local short form, no area code
        caller_number="+496181990133",  # own MSN, already E.164
        called_number="82628",  # same short form — must be normalized
        direction=CallDirection.OUTBOUND,
        event_type=CallEventType.CALL,
        source="test",
        connection_id="10",
    )

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    await pipeline._on_event(call_event)

    call_args = mock_adapter.handle.call_args
    processed_event = call_args[0][0]

    assert processed_event.number == "+49618182628"
    assert processed_event.called_number == "+49618182628"
    assert processed_event.caller_number == "+496181990133"  # already E.164, unchanged


@pytest.mark.asyncio
async def test_inbound_caller_number_is_normalized(pipeline):
    """For an inbound RING, caller_number without area code should be normalized to E.164."""
    ring_event = CallEvent(
        number="82628",  # local short form
        caller_number="82628",  # same — must be normalized
        called_number="+496181990133",  # own MSN, already E.164
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="11",
    )

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    await pipeline._on_event(ring_event)

    call_args = mock_adapter.handle.call_args
    processed_event = call_args[0][0]

    assert processed_event.number == "+49618182628"
    assert processed_event.caller_number == "+49618182628"
    assert processed_event.called_number == "+496181990133"  # already E.164, unchanged


@pytest.mark.asyncio
async def test_anonymous_caller_not_normalized(pipeline):
    """Anonymous caller_number must not be passed through the normalizer."""
    ring_event = CallEvent(
        number="anonymous",
        caller_number="anonymous",
        called_number="+496181990133",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="12",
    )

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    await pipeline._on_event(ring_event)

    call_args = mock_adapter.handle.call_args
    processed_event = call_args[0][0]

    assert processed_event.caller_number == "anonymous"  # must stay unchanged
