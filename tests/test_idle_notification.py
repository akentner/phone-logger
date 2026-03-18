"""Tests for the auto-reset idle notification via on_state_change callback."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.config import (
    AppConfig,
    LineConfig,
    MsnConfig,
    PbxConfig,
    PhoneConfig,
)
from src.core.event import CallDirection, CallEvent, CallEventType
from src.core.pbx import LineState, LineStatus, PbxStateManager
from src.core.pipeline import Pipeline


# --- PbxStateManager callback ---


@pytest.mark.asyncio
async def test_on_state_change_called_after_auto_reset():
    """on_state_change callback should fire with idle state after terminal auto-reset."""
    callback = AsyncMock()
    config = PbxConfig(lines=[LineConfig(id=0)])
    phone = PhoneConfig(country_code="49", local_area_code="6181")
    pbx = PbxStateManager(config, phone, on_state_change=callback)

    # RING → missed (terminal) → auto-reset to idle
    ring_event = CallEvent(
        number="+491234567890",
        caller_number="+491234567890",
        called_number="+496181123456",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="0",
        line_id=0,
    )
    pbx.update_state(ring_event)

    disconnect_event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="0",
        line_id=0,
    )
    pbx.update_state(disconnect_event)

    # State is now "missed" (terminal)
    state = pbx.get_line_state(0)
    assert state.status == LineStatus.MISSED

    # Callback not called yet (waiting 1s)
    callback.assert_not_called()

    # Wait for auto-reset
    await asyncio.sleep(1.2)

    # Callback should have been called with idle state
    callback.assert_called_once()
    call_args = callback.call_args
    assert call_args[0][0] == 0  # line_id
    assert call_args[0][1].status == LineStatus.IDLE  # idle state


@pytest.mark.asyncio
async def test_no_callback_when_not_configured():
    """No crash when on_state_change is None."""
    config = PbxConfig(lines=[LineConfig(id=0)])
    phone = PhoneConfig(country_code="49", local_area_code="6181")
    pbx = PbxStateManager(config, phone)  # No callback

    ring_event = CallEvent(
        number="+491234567890",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="0",
        line_id=0,
    )
    pbx.update_state(ring_event)

    disconnect_event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="0",
        line_id=0,
    )
    pbx.update_state(disconnect_event)

    await asyncio.sleep(1.2)

    # Should not crash — state just resets silently
    state = pbx.get_line_state(0)
    assert state.status == LineStatus.IDLE


@pytest.mark.asyncio
async def test_callback_error_does_not_break_reset():
    """If callback raises, line should still be reset to idle."""
    callback = AsyncMock(side_effect=RuntimeError("boom"))
    config = PbxConfig(lines=[LineConfig(id=0)])
    phone = PhoneConfig(country_code="49", local_area_code="6181")
    pbx = PbxStateManager(config, phone, on_state_change=callback)

    ring_event = CallEvent(
        number="+491234567890",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="0",
        line_id=0,
    )
    pbx.update_state(ring_event)

    disconnect_event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="0",
        line_id=0,
    )
    pbx.update_state(disconnect_event)

    await asyncio.sleep(1.2)

    # Callback was called (and raised), but state is still idle
    callback.assert_called_once()
    state = pbx.get_line_state(0)
    assert state.status == LineStatus.IDLE


# --- Pipeline idle notification to output adapters ---


@pytest.mark.asyncio
async def test_pipeline_dispatches_idle_to_output_adapters():
    """After terminal state auto-reset, output adapters should receive idle notification."""
    phone = PhoneConfig(country_code="49", local_area_code="6181")
    pbx_config = PbxConfig(lines=[LineConfig(id=0)])
    config = AppConfig(
        phone=phone,
        pbx=pbx_config,
        input_adapters=[],
        resolver_adapters=[],
        output_adapters=[],
    )

    mock_db = AsyncMock()
    pipeline = Pipeline(config, mock_db)
    await pipeline.setup()

    mock_adapter = AsyncMock()
    pipeline._output_adapters = [mock_adapter]

    # Process RING
    ring_event = CallEvent(
        number="+491234567890",
        caller_number="+491234567890",
        called_number="+496181123456",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="test",
        connection_id="0",
        line_id=0,
    )
    await pipeline._on_event(ring_event)

    # Process DISCONNECT (terminal → missed)
    disconnect_event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="test",
        connection_id="0",
        line_id=0,
    )
    await pipeline._on_event(disconnect_event)

    # At this point: RING + DISCONNECT = 2 calls to mock_adapter.handle
    assert mock_adapter.handle.call_count == 2

    # Wait for auto-reset to fire idle notification
    await asyncio.sleep(1.5)

    # Third call should be the idle notification
    assert mock_adapter.handle.call_count == 3

    # Verify the idle call
    idle_call = mock_adapter.handle.call_args_list[2]
    idle_event = idle_call[0][0]
    idle_line_state = idle_call[1]["line_state"]

    assert idle_event.source == "pbx"
    assert idle_event.line_id == 0
    assert idle_line_state.status == LineStatus.IDLE


@pytest.mark.asyncio
async def test_webhook_filter_matches_state_idle():
    """Webhook event filter 'state:idle' should match the idle notification."""
    from src.adapters.output.webhook import _matches_filter

    idle_state = LineState(line_id=0, status=LineStatus.IDLE)
    event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="pbx",
        line_id=0,
    )

    assert _matches_filter("state:idle", event, idle_state) is True
    assert _matches_filter("state:missed", event, idle_state) is False
    assert (
        _matches_filter("disconnect", event, idle_state) is True
    )  # event_type matches too
