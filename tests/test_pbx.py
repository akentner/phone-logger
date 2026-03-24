"""Tests for PBX state management and FSM."""

import asyncio

import pytest

from src.config import (
    DeviceConfig,
    DeviceType,
    MsnConfig,
    PbxConfig,
    PhoneConfig,
    TrunkConfig,
    TrunkType,
)
from src.core.event import CallDirection, CallEvent, CallEventType
from src.core.pbx import LineFSM, LineStatus, PbxStateManager


# --- LineFSM Tests ---


class TestLineFSM:
    """Tests for the per-line finite state machine."""

    def test_initial_state_is_idle(self):
        fsm = LineFSM(line_id=0)
        assert fsm.status == LineStatus.IDLE

    def test_idle_to_ring(self):
        fsm = LineFSM(line_id=0)
        status = fsm.transition(CallEventType.RING)
        assert status == LineStatus.RING

    def test_idle_to_call(self):
        fsm = LineFSM(line_id=0)
        status = fsm.transition(CallEventType.CALL)
        assert status == LineStatus.CALL

    def test_ring_to_talking(self):
        fsm = LineFSM(line_id=0)
        fsm.transition(CallEventType.RING)
        status = fsm.transition(CallEventType.CONNECT)
        assert status == LineStatus.TALKING

    def test_call_to_talking(self):
        fsm = LineFSM(line_id=0)
        fsm.transition(CallEventType.CALL)
        status = fsm.transition(CallEventType.CONNECT)
        assert status == LineStatus.TALKING

    def test_ring_disconnect_is_missed(self):
        fsm = LineFSM(line_id=0)
        fsm.transition(CallEventType.RING)
        status = fsm.transition(CallEventType.DISCONNECT)
        assert status == LineStatus.MISSED

    def test_call_disconnect_is_not_reached(self):
        fsm = LineFSM(line_id=0)
        fsm.transition(CallEventType.CALL)
        status = fsm.transition(CallEventType.DISCONNECT)
        assert status == LineStatus.NOT_REACHED

    def test_talking_disconnect_is_finished(self):
        fsm = LineFSM(line_id=0)
        fsm.transition(CallEventType.RING)
        fsm.transition(CallEventType.CONNECT)
        status = fsm.transition(CallEventType.DISCONNECT)
        assert status == LineStatus.FINISHED

    def test_full_inbound_flow(self):
        """idle -> ring -> talking -> finished"""
        fsm = LineFSM(line_id=0)
        assert fsm.transition(CallEventType.RING) == LineStatus.RING
        assert fsm.transition(CallEventType.CONNECT) == LineStatus.TALKING
        assert fsm.transition(CallEventType.DISCONNECT) == LineStatus.FINISHED

    def test_full_outbound_flow(self):
        """idle -> call -> talking -> finished"""
        fsm = LineFSM(line_id=0)
        assert fsm.transition(CallEventType.CALL) == LineStatus.CALL
        assert fsm.transition(CallEventType.CONNECT) == LineStatus.TALKING
        assert fsm.transition(CallEventType.DISCONNECT) == LineStatus.FINISHED

    def test_missed_inbound_flow(self):
        """idle -> ring -> missed"""
        fsm = LineFSM(line_id=0)
        assert fsm.transition(CallEventType.RING) == LineStatus.RING
        assert fsm.transition(CallEventType.DISCONNECT) == LineStatus.MISSED

    def test_not_reached_outbound_flow(self):
        """idle -> call -> notReached"""
        fsm = LineFSM(line_id=0)
        assert fsm.transition(CallEventType.CALL) == LineStatus.CALL
        assert fsm.transition(CallEventType.DISCONNECT) == LineStatus.NOT_REACHED

    def test_invalid_transition_resets_to_idle(self):
        """Invalid transition should reset to idle (fault-tolerant)."""
        fsm = LineFSM(line_id=0)
        fsm.transition(CallEventType.RING)
        # RING in RING state is invalid → reset to idle
        status = fsm.transition(CallEventType.RING)
        # Should reset to idle then retry RING → back to RING
        assert status == LineStatus.RING

    def test_invalid_connect_from_idle_resets(self):
        """CONNECT from idle is invalid."""
        fsm = LineFSM(line_id=0)
        status = fsm.transition(CallEventType.CONNECT)
        assert status == LineStatus.IDLE

    def test_invalid_disconnect_from_idle_resets(self):
        """DISCONNECT from idle is invalid."""
        fsm = LineFSM(line_id=0)
        status = fsm.transition(CallEventType.DISCONNECT)
        assert status == LineStatus.IDLE

    def test_reset(self):
        fsm = LineFSM(line_id=0)
        fsm.transition(CallEventType.RING)
        fsm.transition(CallEventType.CONNECT)
        fsm.reset()
        assert fsm.status == LineStatus.IDLE

    def test_event_during_terminal_state_resets_and_retries(self):
        """A RING during FINISHED should reset and start new call."""
        fsm = LineFSM(line_id=0)
        fsm.transition(CallEventType.RING)
        fsm.transition(CallEventType.CONNECT)
        fsm.transition(CallEventType.DISCONNECT)
        assert fsm.status == LineStatus.FINISHED
        # New RING arrives before auto-reset
        status = fsm.transition(CallEventType.RING)
        assert status == LineStatus.RING


# --- PbxStateManager Tests ---


def _make_pbx_config() -> PbxConfig:
    """Create a test PBX config."""
    return PbxConfig(
        trunks=[
            TrunkConfig(id="SIP0", type=TrunkType.SIP, label="Internet 1"),
            TrunkConfig(id="SIP1", type=TrunkType.SIP, label="Internet 2"),
            TrunkConfig(id="SIP2", type=TrunkType.SIP, label="Internet 3"),
        ],
        msns=[
            MsnConfig(number="990133", label="Hauptnummer"),
            MsnConfig(number="990134", label="Fax"),
        ],
        devices=[
            DeviceConfig(
                id="10", extension="10", name="Wohnzimmer", type=DeviceType.DECT
            ),
            DeviceConfig(id="20", extension="20", name="Büro", type=DeviceType.VOIP),
        ],
    )


def _make_phone_config() -> PhoneConfig:
    return PhoneConfig(country_code="49", local_area_code="6181")


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


def _make_connect_event(connection_id: str = "0") -> CallEvent:
    return CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.CONNECT,
        source="fritz_callmonitor",
        connection_id=connection_id,
    )


def _make_disconnect_event(connection_id: str = "0") -> CallEvent:
    return CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="fritz_callmonitor",
        connection_id=connection_id,
    )


class TestPbxStateManager:
    """Tests for PBX state manager."""

    def test_initialization(self):
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        states = pbx.get_line_states()
        assert len(states) == 3
        assert all(s.status == LineStatus.IDLE for s in states)

    def test_enrich_event_sets_line_id(self):
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        event = _make_ring_event(connection_id="1")
        enriched = pbx.enrich_event(event)
        assert enriched.line_id == 1

    def test_enrich_event_sets_device(self):
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        event = _make_call_event(extension="10")
        enriched = pbx.enrich_event(event)
        assert enriched.caller_device is not None
        assert enriched.caller_device.name == "Wohnzimmer"
        assert enriched.caller_device.type == "dect"

    def test_enrich_event_no_device_for_unknown_extension(self):
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        event = _make_call_event(extension="99")
        enriched = pbx.enrich_event(event)
        assert enriched.caller_device is None

    def test_msn_e164_resolution(self):
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        msns = pbx.get_msns_e164()
        assert len(msns) == 2
        assert msns[0]["e164"] == "+496181990133"
        assert msns[1]["e164"] == "+496181990134"

    def test_internal_call_detection(self):
        """Two configured MSNs calling each other should be internal."""
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        assert pbx._is_internal("+496181990133", "+496181990134") is True

    def test_external_call_detection(self):
        """External number + MSN should not be internal."""
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        assert pbx._is_internal("+491234567890", "+496181990133") is False

    def test_update_state_ring(self):
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        event = _make_ring_event(connection_id="0")
        enriched = pbx.enrich_event(event)
        pbx.update_state(enriched)

        state = pbx.get_line_state(0)
        assert state.status == LineStatus.RING
        assert state.caller_number is not None
        assert state.trunk_id == "SIP0"

    def test_update_state_full_call_flow(self):
        """Test complete call: ring -> connect -> disconnect -> finished."""
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())

        # RING
        event = _make_ring_event(connection_id="0")
        pbx.update_state(pbx.enrich_event(event))
        assert pbx.get_line_state(0).status == LineStatus.RING

        # CONNECT
        event = _make_connect_event(connection_id="0")
        pbx.update_state(pbx.enrich_event(event))
        assert pbx.get_line_state(0).status == LineStatus.TALKING

        # DISCONNECT
        event = _make_disconnect_event(connection_id="0")
        pbx.update_state(pbx.enrich_event(event))
        assert pbx.get_line_state(0).status == LineStatus.FINISHED

    def test_outbound_connect_does_not_set_called_device(self):
        """Regression: outbound CALL followed by CONNECT must not set called_device.

        Fritz!Box sends CONNECT without a direction field, so the event always
        arrives with direction=INBOUND.  The fix in enrich_event must look up
        the stored LineState direction instead of trusting event.direction.
        """
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())

        # CALL (outbound, device id=10 → "Wohnzimmer")
        call_ev = _make_call_event(connection_id="0", extension="10")
        pbx.update_state(pbx.enrich_event(call_ev))

        state = pbx.get_line_state(0)
        assert state.direction == CallDirection.OUTBOUND
        assert state.caller_device is not None
        assert state.called_device is None

        # CONNECT — Fritz!Box sends direction=INBOUND (the default), but the
        # actual call is outbound.  called_device must remain None.
        connect_ev = _make_connect_event(connection_id="0")
        assert connect_ev.direction == CallDirection.INBOUND  # confirm the precondition

        enriched_connect = pbx.enrich_event(connect_ev)
        pbx.update_state(enriched_connect)

        state = pbx.get_line_state(0)
        assert state.status == LineStatus.TALKING
        assert state.called_device is None, (
            "called_device must be None for an outbound call to an external number"
        )
        assert state.caller_device is not None, "caller_device must remain set"

    def test_update_state_missed_call(self):
        """Test missed call: ring -> disconnect -> missed."""
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())

        event = _make_ring_event(connection_id="0")
        pbx.update_state(pbx.enrich_event(event))

        event = _make_disconnect_event(connection_id="0")
        pbx.update_state(pbx.enrich_event(event))
        assert pbx.get_line_state(0).status == LineStatus.MISSED

    def test_trunk_busy_status(self):
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())

        # No calls — all trunks idle
        trunks = pbx.get_trunk_status()
        assert all(not t["busy"] for t in trunks)

        # Start a call on SIP0
        event = _make_ring_event(connection_id="0", trunk="SIP0")
        pbx.update_state(pbx.enrich_event(event))

        trunks = pbx.get_trunk_status()
        sip0 = next(t for t in trunks if t["id"] == "SIP0")
        sip1 = next(t for t in trunks if t["id"] == "SIP1")
        assert sip0["busy"] is True
        assert sip1["busy"] is False

    def test_multiple_lines_independent(self):
        """Two lines can be busy simultaneously."""
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())

        # RING on line 0
        event = _make_ring_event(connection_id="0")
        pbx.update_state(pbx.enrich_event(event))

        # RING on line 1
        event = _make_ring_event(connection_id="1", trunk="SIP1")
        pbx.update_state(pbx.enrich_event(event))

        assert pbx.get_line_state(0).status == LineStatus.RING
        assert pbx.get_line_state(1).status == LineStatus.RING
        assert pbx.get_line_state(2).status == LineStatus.IDLE

    def test_get_devices(self):
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        devices = pbx.get_devices()
        assert len(devices) == 2
        assert devices[0].name == "Wohnzimmer"

    def test_get_status_snapshot(self):
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        status = pbx.get_status()
        assert "lines" in status
        assert "trunks" in status
        assert "msns" in status
        assert "devices" in status
        assert len(status["lines"]) == 3
        assert len(status["trunks"]) == 3

    def test_unconfigured_line_ignored(self):
        """Events for unconfigured lines should be silently ignored."""
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        event = _make_ring_event(connection_id="99")
        enriched = pbx.enrich_event(event)
        pbx.update_state(enriched)  # Should not raise
        assert pbx.get_line_state(99) is None

    def test_internal_call_sets_is_internal(self):
        """When both numbers are MSNs, is_internal should be True."""
        pbx = PbxStateManager(_make_pbx_config(), _make_phone_config())
        event = CallEvent(
            number="+496181990134",
            direction=CallDirection.INBOUND,
            event_type=CallEventType.RING,
            source="fritz_callmonitor",
            connection_id="0",
            caller_number="+496181990133",
            called_number="+496181990134",
            trunk_id=None,
        )
        enriched = pbx.enrich_event(event)
        pbx.update_state(enriched)
        state = pbx.get_line_state(0)
        assert state.is_internal is True

    def test_empty_pbx_config(self):
        """PBX with no lines/trunks/msns/devices should work gracefully."""
        pbx = PbxStateManager(PbxConfig(), _make_phone_config())
        assert pbx.get_line_states() == []
        assert pbx.get_trunk_status() == []
        assert pbx.get_msns_e164() == []
        assert pbx.get_devices() == []
