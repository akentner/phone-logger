"""Tests for anonymous/withheld call number handling."""

import tempfile
from pathlib import Path

import pytest

from src.adapters.input.fritz import FritzCallmonitorAdapter, ANONYMOUS
from src.adapters.output.call_log import CallLogOutputAdapter
from src.config import AdapterConfig
from src.core.event import CallDirection, CallEvent, CallEventType
from src.core.phone_number import normalize
from src.core.pipeline import ANONYMOUS_RESULT
from src.db.database import Database


@pytest.fixture
async def test_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(str(Path(tmpdir) / "test.db"))
        await db.connect()
        yield db
        await db.close()


# --- Fritz parser ---


class TestAnonymousFritzParsing:
    def test_anonymous_ring_returns_event_not_none(self):
        """Critical regression: anonymous RING must not be dropped."""
        line = "18.03.26 22:35:21;RING;0;;06301234567;SIP4;"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is not None

    def test_anonymous_ring_number_is_sentinel(self):
        line = "18.03.26 22:35:21;RING;0;;06301234567;SIP4;"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event.number == ANONYMOUS

    def test_anonymous_ring_caller_number_is_sentinel(self):
        line = "18.03.26 22:35:21;RING;0;;06301234567;SIP4;"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event.caller_number == ANONYMOUS

    def test_anonymous_ring_called_number_preserved(self):
        line = "18.03.26 22:35:21;RING;0;;06301234567;SIP4;"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event.called_number == "06301234567"

    def test_anonymous_ring_trunk_preserved(self):
        line = "18.03.26 22:35:21;RING;0;;06301234567;SIP4;"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event.trunk_id == "SIP4"
        assert event.connection_id == "0"

    def test_normal_ring_unaffected(self):
        """Ensure non-anonymous numbers still parse correctly."""
        line = "18.03.26 22:35:21;RING;0;01701234567;06301234567;SIP4;"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event.number == "01701234567"
        assert event.caller_number == "01701234567"


# --- Phone number normalization ---


class TestAnonymousNormalization:
    def test_anonymous_passes_through_unchanged(self):
        result = normalize("anonymous", country_code="49", local_area_code="6181")
        assert result == "anonymous"

    def test_empty_string_still_returns_empty(self):
        result = normalize("", country_code="49")
        assert result == ""

    def test_normal_number_unaffected(self):
        result = normalize("01701234567", country_code="49")
        assert result == "+491701234567"


# --- Pipeline resolve result ---


class TestAnonymousResolveResult:
    def test_anonymous_result_name(self):
        assert ANONYMOUS_RESULT.name == "Anonym"

    def test_anonymous_result_source(self):
        assert ANONYMOUS_RESULT.source == "system"

    def test_anonymous_result_number(self):
        assert ANONYMOUS_RESULT.number == ANONYMOUS


# --- Call aggregation with anonymous number ---


@pytest.mark.asyncio
async def test_anonymous_ring_creates_call_record(test_db):
    """Anonymous RING must produce a call record with 'anonymous' as caller_number."""
    config = AdapterConfig(type="call_log", name="call_log", enabled=True)
    adapter = CallLogOutputAdapter(config, test_db)

    event = CallEvent(
        number=ANONYMOUS,
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="5",
        caller_number=ANONYMOUS,
        called_number="+496301234567",
        trunk_id="SIP4",
        line_id=0,
    )
    await adapter.handle(event, ANONYMOUS_RESULT)

    # Raw event logged
    raw, total = await test_db.get_call_log()
    assert total == 1
    assert raw[0]["number"] == ANONYMOUS
    assert raw[0]["resolved_name"] == "Anonym"

    # Aggregated call created
    call = await test_db.get_call_by_connection_id(5)
    assert call is not None
    assert call["caller_number"] == ANONYMOUS
    assert call["status"] == "ringing"
    assert call["resolved_name"] == "Anonym"


@pytest.mark.asyncio
async def test_anonymous_missed_call_lifecycle(test_db):
    """Anonymous RING → DISCONNECT results in a missed call with 'anonymous'."""
    config = AdapterConfig(type="call_log", name="call_log", enabled=True)
    adapter = CallLogOutputAdapter(config, test_db)

    ring = CallEvent(
        number=ANONYMOUS,
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="6",
        caller_number=ANONYMOUS,
        called_number="+496301234567",
    )
    disconnect = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        connection_id="6",
    )

    await adapter.handle(ring, ANONYMOUS_RESULT)
    await adapter.handle(disconnect, None)

    call = await test_db.get_call_by_connection_id(6)
    assert call is not None
    assert call["caller_number"] == ANONYMOUS
    assert call["status"] == "missed"
    assert call["resolved_name"] == "Anonym"
