"""Tests for Fritz!Box Callmonitor line parser."""

import logging

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


class TestFritzParserMinFields:
    """Tests for MIN_FIELDS field count validation in _parse_line()."""

    def test_ring_missing_called_number_returns_none(self):
        """RING with only 4 fields (missing called_number) must be rejected."""
        # date;RING;conn;caller -> 4 parts, needs 5
        line = "15.03.26 10:15:00;RING;0;0123456789"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is None

    def test_ring_minimum_fields_accepted(self):
        """RING with exactly 5 fields must be accepted."""
        # date;RING;conn;caller;called -> 5 parts (no SIP line - optional)
        line = "15.03.26 10:15:00;RING;0;0123456789;987654321"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is not None
        assert event.event_type == CallEventType.RING

    def test_call_missing_called_number_returns_none(self):
        """CALL with only 5 fields (missing called_number) must be rejected."""
        # date;CALL;conn;ext;caller -> 5 parts, needs 6
        line = "15.03.26 10:15:00;CALL;1;12;0123456789"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is None

    def test_call_minimum_fields_accepted(self):
        """CALL with exactly 6 fields must be accepted."""
        # date;CALL;conn;ext;caller;called -> 6 parts (no SIP line - optional)
        line = "15.03.26 10:15:00;CALL;1;12;0123456789;0987654321"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is not None
        assert event.event_type == CallEventType.CALL

    def test_connect_missing_number_returns_none(self):
        """CONNECT with only 4 fields (missing number) must be rejected."""
        # date;CONNECT;conn;ext -> 4 parts, needs 5
        line = "15.03.26 10:15:30;CONNECT;0;12"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is None

    def test_connect_minimum_fields_accepted(self):
        """CONNECT with exactly 5 fields must be accepted."""
        line = "15.03.26 10:15:30;CONNECT;0;12;0123456789"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is not None
        assert event.event_type == CallEventType.CONNECT

    def test_disconnect_minimum_fields_accepted(self):
        """DISCONNECT with exactly 4 fields (the minimum) must be accepted."""
        line = "15.03.26 10:20:00;DISCONNECT;0;120"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is not None
        assert event.event_type == CallEventType.DISCONNECT

    def test_ring_parse_failure_logs_warning_with_raw_line(self, caplog):
        """Parse failure for RING must log WARNING containing the raw line."""
        line = "15.03.26 10:15:00;RING;0;0123456789"  # only 4 parts, needs 5
        with caplog.at_level(logging.WARNING):
            event = FritzCallmonitorAdapter._parse_line(line)
        assert event is None
        assert "Fritz parse error" in caplog.text
        assert line in caplog.text

    def test_unknown_event_logs_debug_not_warning(self, caplog):
        """Unknown event type must log at DEBUG level (not WARNING) to avoid noise."""
        line = "15.03.26 10:15:00;UNKNOWN_EVENT;0;123"
        with caplog.at_level(logging.DEBUG):
            event = FritzCallmonitorAdapter._parse_line(line)
        assert event is None
        # Must have a DEBUG record about the unknown event
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG and "UNKNOWN_EVENT" in r.message]
        assert len(debug_records) >= 1
        # Must NOT have a WARNING about unknown event type
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING and "UNKNOWN_EVENT" in r.message]
        assert len(warning_records) == 0
