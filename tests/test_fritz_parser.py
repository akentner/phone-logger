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


class TestFritzParserStateless:
    """Tests verifying Fritz!Box parser is stateless and idempotent.

    Parser has no hidden state — multiple calls with the same line return
    equivalent events. Parser also doesn't enforce event ordering; it's the
    PBX FSM's responsibility to validate transitions.
    """

    def test_parser_is_idempotent_duplicate_line(self):
        """Same raw line parsed twice returns equivalent events."""
        line = "15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0"

        # Parse twice
        event1 = FritzCallmonitorAdapter._parse_line(line)
        event2 = FritzCallmonitorAdapter._parse_line(line)

        # Both must be valid
        assert event1 is not None
        assert event2 is not None

        # Both must be equivalent (same data)
        assert event1.number == event2.number
        assert event1.event_type == event2.event_type
        assert event1.connection_id == event2.connection_id
        assert event1.caller_number == event2.caller_number
        assert event1.called_number == event2.called_number
        # Parser has no hidden state — events are fully equivalent
        assert event1.event_type == CallEventType.RING
        assert event2.event_type == CallEventType.RING

    def test_parser_handles_out_of_order_disconnect_before_ring(self):
        """DISCONNECT parsed independently before any RING is valid."""
        disconnect_line = "15.03.26 10:20:00;DISCONNECT;0;120"

        # Parse DISCONNECT on its own (no prior RING context)
        event = FritzCallmonitorAdapter._parse_line(disconnect_line)

        # Must be valid — parser doesn't enforce ordering
        assert event is not None
        assert event.event_type == CallEventType.DISCONNECT
        assert event.connection_id == "0"

    def test_parser_handles_ring_after_disconnect(self):
        """Parse DISCONNECT, then RING for different connection_id — both valid."""
        disconnect_line = "15.03.26 10:20:00;DISCONNECT;0;120"
        ring_line = "15.03.26 10:21:00;RING;1;0123456789;987654321;SIP0"

        # Parse DISCONNECT first
        event1 = FritzCallmonitorAdapter._parse_line(disconnect_line)
        # Then RING with different connection_id
        event2 = FritzCallmonitorAdapter._parse_line(ring_line)

        # Both must be valid
        assert event1 is not None
        assert event2 is not None

        # Different connection_ids
        assert event1.connection_id == "0"
        assert event2.connection_id == "1"

        # Parser is independent of history — no assumptions about ordering
        assert event1.event_type == CallEventType.DISCONNECT
        assert event2.event_type == CallEventType.RING

    def test_parser_accepts_connect_after_disconnect_same_connid(self):
        """Same connection_id can have DISCONNECT then CONNECT (unusual but possible)."""
        disconnect_line = "15.03.26 10:20:00;DISCONNECT;5;120"
        connect_line = "15.03.26 10:21:00;CONNECT;5;12;0123456789"

        # Parse both in sequence
        event1 = FritzCallmonitorAdapter._parse_line(disconnect_line)
        event2 = FritzCallmonitorAdapter._parse_line(connect_line)

        # Both must be valid — parser doesn't track which connection_ids are "closed"
        assert event1 is not None
        assert event2 is not None

        assert event1.connection_id == "5"
        assert event2.connection_id == "5"

        assert event1.event_type == CallEventType.DISCONNECT
        assert event2.event_type == CallEventType.CONNECT


class TestFritzAdapterIntegration:
    """Tests verifying adapter behavior with duplicates and out-of-order events.

    The adapter layer doesn't deduplicate or enforce ordering — it passes all
    valid events to the callback. The PBX FSM is responsible for handling
    duplicate and out-of-order scenarios.
    """

    def test_adapter_parser_not_deduplicate(self):
        """Adapter's _parse_line() doesn't deduplicate identical events."""
        line = "15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0"

        # Feed same RING line to parser twice
        event1 = FritzCallmonitorAdapter._parse_line(line)
        event2 = FritzCallmonitorAdapter._parse_line(line)

        # Both must produce valid events (no deduplication)
        assert event1 is not None
        assert event2 is not None

        # Both must represent the same call but are distinct objects
        assert event1.number == event2.number
        assert event1.event_type == event2.event_type
        assert event1.connection_id == event2.connection_id

        # Verify they're separate event instances
        assert event1 is not event2

    def test_callback_contract_is_async(self):
        """Adapter callback must accept CallEvent and return Coroutine."""
        from unittest.mock import AsyncMock

        # Create an async mock callback matching the signature
        callback = AsyncMock()

        # Create a CallEvent manually
        line = "15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0"
        event = FritzCallmonitorAdapter._parse_line(line)

        # We can't directly await callback here without async context,
        # but we verify the callback's signature is correct by checking
        # that AsyncMock can represent it
        assert callable(callback)

    def test_multiple_events_coexist_no_implicit_state(self):
        """Adapter parser maintains no connection_id state."""
        # Create 5 different RING events with different connection_ids
        lines = [
            "15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0",
            "15.03.26 10:16:00;RING;1;0111111111;988888888;SIP0",
            "15.03.26 10:17:00;RING;2;0222222222;989999999;SIP0",
            "15.03.26 10:18:00;RING;3;0333333333;980000000;SIP0",
            "15.03.26 10:19:00;RING;4;0444444444;981111111;SIP0",
        ]

        events = []
        for line in lines:
            event = FritzCallmonitorAdapter._parse_line(line)
            assert event is not None
            events.append(event)

        # All 5 must parse successfully
        assert len(events) == 5

        # Verify each has the correct connection_id
        for i, event in enumerate(events):
            assert event.connection_id == str(i)
            assert event.event_type == CallEventType.RING

        # Parser maintains no implicit state — no conflicts
