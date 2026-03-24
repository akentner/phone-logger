"""Tests for raw event logging in the pipeline."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.adapters.input.fritz_callmonitor import FritzCallmonitorAdapter
from src.config import AdapterConfig, AppConfig, PbxConfig, PhoneConfig
from src.core.event import CallDirection, CallEvent, CallEventType
from src.core.pipeline import Pipeline
from src.db.database import Database


@pytest.fixture
async def test_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(str(Path(tmpdir) / "test.db"))
        await db.connect()
        yield db
        await db.close()


@pytest.fixture
def app_config():
    config = AppConfig(
        phone=PhoneConfig(country_code="49", local_area_code="6181"),
        pbx=PbxConfig(),
    )
    config.input_adapters = []
    config.resolver_adapters = []
    config.output_adapters = []
    return config


@pytest.fixture
async def pipeline(app_config, test_db):
    pl = Pipeline(app_config, test_db)
    await pl.setup()
    return pl


# --- Fritz Callmonitor raw_input ---


class TestFritzRawInput:
    """Verify that FritzCallmonitorAdapter sets raw_input on the CallEvent."""

    def test_parse_line_has_no_raw_input(self):
        """_parse_line returns event without raw_input (set in _process_line)."""
        line = "15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0"
        event = FritzCallmonitorAdapter._parse_line(line)
        assert event is not None
        # raw_input is set by _process_line, not _parse_line
        assert event.raw_input is None

    @pytest.mark.asyncio
    async def test_process_line_sets_raw_input(self):
        """_process_line attaches the raw TCP line to raw_input."""
        config = AdapterConfig(
            type="fritz_callmonitor",
            name="fritz_callmonitor",
            config={"host": "192.168.178.1", "port": 1012},
        )
        adapter = FritzCallmonitorAdapter(config)

        received_events = []

        async def capture(event: CallEvent):
            received_events.append(event)

        adapter._callback = capture

        line = "15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0"
        await adapter._process_line(line)

        assert len(received_events) == 1
        assert received_events[0].raw_input == line
        assert received_events[0].source == "fritz_callmonitor"


# --- Pipeline raw event persistence ---


@pytest.mark.asyncio
async def test_on_event_logs_raw_event_to_db(pipeline, test_db):
    """_on_event must write a raw_events record before any other processing."""
    event = CallEvent(
        number="+491234567890",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="fritz_callmonitor",
        connection_id="1",
        raw_input="15.03.26 10:15:00;RING;1;+491234567890;990133;SIP0",
    )

    await pipeline._on_event(event)

    rows, next_cursor = await test_db.get_raw_events()
    assert next_cursor is None  # only 1 entry
    assert rows[0]["source"] == "fritz_callmonitor"
    assert rows[0]["raw_input"] == event.raw_input
    # raw_event_json must be valid JSON and contain the event_type
    parsed = json.loads(rows[0]["raw_event_json"])
    assert parsed["event_type"] == "ring"
    assert parsed["source"] == "fritz_callmonitor"


@pytest.mark.asyncio
async def test_on_event_logs_raw_event_from_rest(pipeline, test_db):
    """Events from the REST adapter (no raw_input) are also logged."""
    event = CallEvent(
        number="+491234567890",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        source="rest",
        raw_input=json.dumps(
            {"number": "+491234567890", "direction": "inbound", "event_type": "ring"}
        ),
    )

    await pipeline._on_event(event)

    rows, next_cursor = await test_db.get_raw_events()
    assert next_cursor is None  # only 1 entry
    assert rows[0]["source"] == "rest"
    raw_input_data = json.loads(rows[0]["raw_input"])
    assert raw_input_data["number"] == "+491234567890"


@pytest.mark.asyncio
async def test_on_event_logs_raw_event_without_raw_input(pipeline, test_db):
    """Events without raw_input (e.g. pbx idle callbacks) store NULL raw_input."""
    event = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        source="pbx",
        raw_input=None,
    )

    await pipeline._on_event(event)

    rows, next_cursor = await test_db.get_raw_events()
    assert next_cursor is None  # only 1 entry
    assert rows[0]["raw_input"] is None
    assert rows[0]["source"] == "pbx"


@pytest.mark.asyncio
async def test_on_event_multiple_events_all_logged(pipeline, test_db):
    """Each call to _on_event produces exactly one raw_events row."""
    for i, event_type in enumerate(
        [CallEventType.RING, CallEventType.CONNECT, CallEventType.DISCONNECT]
    ):
        event = CallEvent(
            number="+491234567890",
            direction=CallDirection.INBOUND,
            event_type=event_type,
            source="fritz_callmonitor",
            connection_id=str(i),
        )
        await pipeline._on_event(event)

    _, next_cursor = await test_db.get_raw_events()
    assert next_cursor is None  # only 3 entries, default limit=50


@pytest.mark.asyncio
async def test_get_raw_events_source_filter(pipeline, test_db):
    """get_raw_events supports filtering by source."""
    for source in ["fritz_callmonitor", "rest", "fritz_callmonitor"]:
        event = CallEvent(
            number="+491234567890",
            direction=CallDirection.INBOUND,
            event_type=CallEventType.RING,
            source=source,
        )
        await pipeline._on_event(event)

    fritz_rows, fritz_next = await test_db.get_raw_events(
        source_filter="fritz_callmonitor"
    )
    assert len(fritz_rows) == 2
    assert fritz_next is None  # 2 < default limit

    rest_rows, rest_next = await test_db.get_raw_events(source_filter="rest")
    assert len(rest_rows) == 1
    assert rest_next is None
