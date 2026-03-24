"""Tests for Fritz!Box Callmonitor line parser."""

import pytest

from src.adapters.input.fritz_callmonitor import FritzCallmonitorAdapter
from src.core.event import CallDirection, CallEventType


class TestFritzParser:
    """Tests for Fritz!Box Callmonitor message parsing."""

    def test_parse_ring_event(self):
        line = "15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0"
        event = FritzCallmonitorAdapter._parse_line(line)

        assert event is not None
        assert event.number == "0123456789"
        assert event.direction == CallDirection.INBOUND
        assert event.event_type == CallEventType.RING
        assert event.connection_id == "0"
        assert event.source == "fritz_callmonitor"
        assert event.caller_number == "0123456789"
        assert event.called_number == "987654321"
        assert event.trunk_id == "SIP0"

    def test_parse_call_event(self):
        line = "15.03.26 10:15:00;CALL;1;12;0123456789;0987654321;SIP0"
        event = FritzCallmonitorAdapter._parse_line(line)

        assert event is not None
        assert event.number == "0987654321"
        assert event.direction == CallDirection.OUTBOUND
        assert event.event_type == CallEventType.CALL
        assert event.extension == "12"
        assert event.caller_number == "0123456789"
        assert event.called_number == "0987654321"
        assert event.trunk_id == "SIP0"

    def test_parse_connect_event(self):
        line = "15.03.26 10:15:30;CONNECT;0;12;0123456789"
        event = FritzCallmonitorAdapter._parse_line(line)

        assert event is not None
        assert event.event_type == CallEventType.CONNECT
        assert event.number == "0123456789"

    def test_parse_disconnect_event(self):
        line = "15.03.26 10:20:00;DISCONNECT;0;120"
        event = FritzCallmonitorAdapter._parse_line(line)

        assert event is not None
        assert event.event_type == CallEventType.DISCONNECT
        assert event.connection_id == "0"

    def test_parse_invalid_line(self):
        event = FritzCallmonitorAdapter._parse_line("invalid")
        assert event is None

    def test_parse_unknown_event(self):
        event = FritzCallmonitorAdapter._parse_line("15.03.26 10:15:00;UNKNOWN;0;123")
        assert event is None

    def test_parse_empty_line(self):
        event = FritzCallmonitorAdapter._parse_line("")
        assert event is None

    def test_parse_anonymous_ring(self):
        """Anonymous inbound call (withheld number) — empty caller field."""
        line = "18.03.26 22:35:21;RING;0;;06301234567;SIP4;"
        event = FritzCallmonitorAdapter._parse_line(line)

        assert event is not None
        assert event.event_type == CallEventType.RING
        assert event.number == "anonymous"
        assert event.caller_number == "anonymous"
        assert event.called_number == "06301234567"
        assert event.direction == CallDirection.INBOUND
        assert event.trunk_id == "SIP4"

    def test_parse_anonymous_ring_no_number_not_dropped(self):
        """Anonymous RING must NOT be dropped — must reach the pipeline."""
        line = "18.03.26 22:35:21;RING;0;;990133;SIP0;"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is not None  # was silently dropped before the fix

    def test_parse_normal_ring_unchanged(self):
        """Non-anonymous RING still works as before."""
        line = "15.03.26 10:15:00;RING;0;01701234567;06301234567;SIP4;"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is not None
        assert event.number == "01701234567"
        assert event.caller_number == "01701234567"
