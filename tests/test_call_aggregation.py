"""Tests for call aggregation functionality."""

import logging
import pytest
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from src.core.utils import uuid7
from src.core.event import CallEvent, CallDirection, CallEventType
from src.adapters.output.call_log import CallLogOutputAdapter
from src.config import AdapterConfig
from src.db.database import Database


@pytest.fixture
async def test_db():
    """Create a temporary test database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        db = Database(db_path)
        await db.connect()
        yield db
        await db.close()


@pytest.mark.asyncio
async def test_uuid7_generation():
    """Test that uuid7() generates valid UUIDs."""
    uuids = [uuid7() for _ in range(5)]

    # All should be unique
    assert len(set(uuids)) == 5

    # All should be valid UUIDs
    import uuid

    for u in uuids:
        parsed = uuid.UUID(u)
        assert parsed.version == 7


@pytest.mark.asyncio
async def test_uuid7_sortability():
    """Test that uuid7() generates sortable UUIDs."""
    import time

    uuids = []

    for i in range(3):
        uuids.append(uuid7())
        time.sleep(0.01)  # Small delay to ensure timestamp difference

    # Should be in order
    assert uuids == sorted(uuids)


@pytest.mark.asyncio
async def test_upsert_call_create(test_db):
    """Test creating a new call."""
    db = test_db

    call_id = uuid7()
    await db.upsert_call(
        call_id=call_id,
        connection_id=1,
        caller_number="+496181123456",
        called_number="+496181654321",
        direction="inbound",
        status="ringing",
        caller_device_id="10",
        msn="990133",
        trunk_id="ISDN0",
        line_id=0,
        is_internal=False,
        started_at=datetime.now(UTC).isoformat(),
    )

    # Retrieve the call
    call = await db.get_call(call_id)
    assert call is not None
    assert call["connection_id"] == 1
    assert call["caller_number"] == "+496181123456"
    assert call["status"] == "ringing"
    assert call["caller_device_id"] == "10"
    assert call["is_internal"] is False


@pytest.mark.asyncio
async def test_upsert_call_update(test_db):
    """Test updating an existing call."""
    db = test_db

    call_id = uuid7()
    started_at = datetime.now(UTC).isoformat()

    # Create initial call
    await db.upsert_call(
        call_id=call_id,
        connection_id=1,
        caller_number="+496181123456",
        called_number="+496181654321",
        direction="inbound",
        status="ringing",
        started_at=started_at,
    )

    # Update with connected_at
    connected_at = datetime.now(UTC).isoformat()
    await db.upsert_call(
        call_id=call_id,
        connection_id=1,
        caller_number="+496181123456",
        called_number="+496181654321",
        direction="inbound",
        status="answered",
        started_at=started_at,
        connected_at=connected_at,
    )

    # Retrieve and verify update
    call = await db.get_call(call_id)
    assert call["status"] == "answered"
    assert call["connected_at"] is not None


@pytest.mark.asyncio
async def test_get_calls_pagination(test_db):
    """Test cursor-based pagination for get_calls."""
    db = test_db

    # Create 5 calls
    ids = []
    for i in range(5):
        call_id = uuid7()
        ids.append(call_id)
        await db.upsert_call(
            call_id=call_id,
            connection_id=i,
            caller_number=f"+496181{100000 + i}",
            called_number="+496181999999",
            direction="inbound" if i % 2 == 0 else "outbound",
            status="answered",
        )

    # First page (no cursor) — returns 2 newest rows, next_cursor points to 3rd
    calls, next_cursor = await db.get_calls(limit=2)
    assert len(calls) == 2
    assert next_cursor is not None

    # Second page — use cursor from first page
    calls2, next_cursor2 = await db.get_calls(cursor=next_cursor, limit=2)
    assert len(calls2) == 2
    # No overlap: IDs must be different from first page
    assert {c["id"] for c in calls2}.isdisjoint({c["id"] for c in calls})

    # Third page — only 1 row left, no further cursor
    calls3, next_cursor3 = await db.get_calls(cursor=next_cursor2, limit=2)
    assert len(calls3) == 1
    assert next_cursor3 is None


@pytest.mark.asyncio
async def test_get_calls_filter_by_direction(test_db):
    """Test filtering calls by direction."""
    db = test_db

    # Create calls with different directions
    for i in range(3):
        await db.upsert_call(
            call_id=uuid7(),
            connection_id=i,
            caller_number="+496181123456",
            called_number="+496181654321",
            direction="inbound",
            status="answered",
        )

    for i in range(3, 5):
        await db.upsert_call(
            call_id=uuid7(),
            connection_id=i,
            caller_number="+496181654321",
            called_number="+496181123456",
            direction="outbound",
            status="answered",
        )

    # Filter by inbound
    calls, _ = await db.get_calls(direction="inbound")
    assert len(calls) == 3
    assert all(c["direction"] == "inbound" for c in calls)

    # Filter by outbound
    calls, _ = await db.get_calls(direction="outbound")
    assert len(calls) == 2
    assert all(c["direction"] == "outbound" for c in calls)


@pytest.mark.asyncio
async def test_get_calls_filter_by_status(test_db):
    """Test filtering calls by status."""
    db = test_db

    # Create calls with different statuses
    statuses = ["answered", "missed", "notReached"]
    for i, status in enumerate(statuses):
        await db.upsert_call(
            call_id=uuid7(),
            connection_id=i,
            caller_number="+496181123456",
            called_number="+496181654321",
            direction="inbound",
            status=status,
        )

    # Filter by status
    calls, _ = await db.get_calls(status="answered")
    assert len(calls) == 1
    assert calls[0]["status"] == "answered"


@pytest.mark.asyncio
async def test_get_call_by_connection_id(test_db):
    """Test getting a call by connection_id."""
    db = test_db

    connection_id = 99
    call_id = uuid7()

    await db.upsert_call(
        call_id=call_id,
        connection_id=connection_id,
        caller_number="+496181123456",
        called_number="+496181654321",
        direction="inbound",
        status="answered",
    )

    # Retrieve by connection_id
    call = await db.get_call_by_connection_id(connection_id)
    assert call is not None
    assert call["id"] == call_id
    assert call["connection_id"] == connection_id


@pytest.mark.asyncio
async def test_call_log_adapter_raw_event(test_db):
    """Test that CallLogOutputAdapter logs raw events."""
    db = test_db
    config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
    adapter = CallLogOutputAdapter(config, db)

    event = CallEvent(
        number="+496181123456",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="1",
        caller_number="+496181123456",
        called_number="990133",
    )

    await adapter.handle(event, None)

    # Verify raw event was logged
    calls, next_cursor = await db.get_call_log()
    assert next_cursor is None  # only 1 entry — no further page
    assert len(calls) == 1
    assert calls[0]["number"] == "+496181123456"
    assert calls[0]["event_type"] == "ring"


@pytest.mark.asyncio
async def test_call_log_adapter_with_line_state(test_db):
    """Test that CallLogOutputAdapter can handle calls with line_state."""
    db = test_db
    config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
    adapter = CallLogOutputAdapter(config, db)

    event = CallEvent(
        number="+496181123456",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="42",
        caller_number="+496181123456",
        called_number="990133",
    )

    # Test that handler works without line_state (should not crash)
    await adapter.handle(event, None)

    # Verify raw event was logged
    calls, next_cursor = await db.get_call_log()
    assert next_cursor is None  # only 1 entry — no further page
    assert len(calls) == 1
    assert calls[0]["event_type"] == "ring"


@pytest.mark.asyncio
async def test_adapter_ring_creates_call_record(test_db):
    """RING event must create a call record in the calls table."""
    config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
    adapter = CallLogOutputAdapter(config, test_db)

    event = CallEvent(
        number="+491701234567",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="7",
        caller_number="+491701234567",
        called_number="+496301234567",
        trunk_id="SIP4",
        line_id=0,
    )
    await adapter.handle(event, None)

    call = await test_db.get_call_by_connection_id(7)
    assert call is not None
    assert call["status"] == "ringing"
    assert call["caller_number"] == "+491701234567"
    assert call["direction"] == "inbound"
    assert call["trunk_id"] == "SIP4"
    assert call["line_id"] == 0
    assert call["finished_at"] is None
    assert call["connected_at"] is None


@pytest.mark.asyncio
async def test_adapter_missed_call_lifecycle(test_db):
    """RING → DISCONNECT without CONNECT results in status=missed."""
    config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
    adapter = CallLogOutputAdapter(config, test_db)

    ring = CallEvent(
        number="+491701234567",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="8",
        caller_number="+491701234567",
        called_number="+496301234567",
    )
    disconnect = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        connection_id="8",
    )

    await adapter.handle(ring, None)
    await adapter.handle(disconnect, None)

    call = await test_db.get_call_by_connection_id(8)
    assert call is not None
    assert call["status"] == "missed"
    assert call["finished_at"] is not None
    assert call["connected_at"] is None
    assert call["duration_seconds"] == 0  # no answer, so 0s from start


@pytest.mark.asyncio
async def test_adapter_answered_call_lifecycle(test_db):
    """RING → CONNECT → DISCONNECT results in status=answered with duration."""
    import time

    config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
    adapter = CallLogOutputAdapter(config, test_db)

    ring = CallEvent(
        number="+491701234567",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="9",
        caller_number="+491701234567",
        called_number="+496301234567",
    )
    connect = CallEvent(
        number="+491701234567",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.CONNECT,
        connection_id="9",
    )
    disconnect = CallEvent(
        number="",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.DISCONNECT,
        connection_id="9",
    )

    await adapter.handle(ring, None)
    time.sleep(0.05)
    await adapter.handle(connect, None)
    time.sleep(0.05)
    await adapter.handle(disconnect, None)

    call = await test_db.get_call_by_connection_id(9)
    assert call is not None
    assert call["status"] == "answered"
    assert call["connected_at"] is not None
    assert call["finished_at"] is not None
    # Duration must be >= 0 and measured from connected_at
    assert call["duration_seconds"] >= 0


@pytest.mark.asyncio
async def test_adapter_outbound_not_reached(test_db):
    """CALL → DISCONNECT without CONNECT results in status=notReached."""
    config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
    adapter = CallLogOutputAdapter(config, test_db)

    call_event = CallEvent(
        number="+491701234567",
        direction=CallDirection.OUTBOUND,
        event_type=CallEventType.CALL,
        connection_id="10",
        caller_number="+496301234567",
        called_number="+491701234567",
    )
    disconnect = CallEvent(
        number="",
        direction=CallDirection.OUTBOUND,
        event_type=CallEventType.DISCONNECT,
        connection_id="10",
    )

    await adapter.handle(call_event, None)
    await adapter.handle(disconnect, None)

    call = await test_db.get_call_by_connection_id(10)
    assert call is not None
    assert call["status"] == "notReached"
    assert call["direction"] == "outbound"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


@pytest.mark.asyncio
async def test_get_calls_filter_by_msn(test_db):
    """Test filtering calls by one or more MSNs."""
    db = test_db

    # Two calls on MSN 990133, one call on MSN 990134, one without MSN
    for i in range(2):
        await db.upsert_call(
            call_id=uuid7(),
            connection_id=i,
            caller_number="+496181123456",
            called_number="+496181990133",
            direction="inbound",
            status="answered",
            msn="+496181990133",
        )
    await db.upsert_call(
        call_id=uuid7(),
        connection_id=10,
        caller_number="+496181123456",
        called_number="+496181990134",
        direction="inbound",
        status="answered",
        msn="+496181990134",
    )
    await db.upsert_call(
        call_id=uuid7(),
        connection_id=20,
        caller_number="+496181123456",
        called_number="+496181990135",
        direction="outbound",
        status="answered",
        msn=None,
    )

    # Filter by single MSN
    calls, _ = await db.get_calls(msn=["+496181990133"])
    assert len(calls) == 2
    assert all(c["msn"] == "+496181990133" for c in calls)

    # Filter by multiple MSNs
    calls, _ = await db.get_calls(msn=["+496181990133", "+496181990134"])
    assert len(calls) == 3
    assert all(c["msn"] in {"+496181990133", "+496181990134"} for c in calls)

    # Unknown MSN returns empty result
    calls, next_cursor = await db.get_calls(msn=["+49000000"])
    assert next_cursor is None
    assert calls == []


class TestCallAggregationEdgeCases:
    """Test suite for call aggregation edge cases."""

    @pytest.mark.asyncio
    async def test_disconnect_without_ring_creates_orphan_record(self, test_db, caplog):
        """
        DISCONNECT without prior RING/CALL: orphan call.

        Scenario: DISCONNECT event arrives without a prior RING/CALL (connection_id unknown).
        - Expected: No exception, graceful handling, WARNING logged
        - Database: No call record created (connection_id 999 unknown)
        """
        config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
        adapter = CallLogOutputAdapter(config, test_db)

        disconnect_event = CallEvent(
            number="",
            direction=CallDirection.INBOUND,
            event_type=CallEventType.DISCONNECT,
            connection_id="999",
        )

        # Handle DISCONNECT for unknown connection_id
        with caplog.at_level(logging.WARNING):
            await adapter.handle(disconnect_event, None)

        # Verify: no crash, no exception
        # Database lookup for connection_id 999 returns None (no call was created)
        call = await test_db.get_call_by_connection_id(999)
        assert call is None, "Orphan DISCONNECT should not create a call record"

        # Verify WARNING was logged (from line 209 of call_log.py)
        warning_records = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "DISCONNECT" in r.message
            and "unknown" in r.message.lower()
        ]
        assert len(warning_records) >= 1, "Expected WARNING log for DISCONNECT without prior RING"

    @pytest.mark.asyncio
    async def test_connect_without_prior_disconnect_completes_normally(self, test_db):
        """
        CONNECT without prior DISCONNECT: duplicate CONNECT handling.

        Scenario: RING → CONNECT → CONNECT (again) → DISCONNECT
        - Expected: All events process without exception, final status is 'answered'
        - Database: Call exists with correct status and duration calculated from connected time
        """
        config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
        adapter = CallLogOutputAdapter(config, test_db)

        # Step 1: RING event creates call record
        ring = CallEvent(
            number="+491701234567",
            direction=CallDirection.INBOUND,
            event_type=CallEventType.RING,
            connection_id="100",
            caller_number="+491701234567",
            called_number="+496301234567",
        )
        await adapter.handle(ring, None)

        # Verify call created in ringing state
        call = await test_db.get_call_by_connection_id(100)
        assert call is not None
        assert call["status"] == "ringing"

        # Step 2: First CONNECT updates to answered
        connect1 = CallEvent(
            number="+491701234567",
            direction=CallDirection.INBOUND,
            event_type=CallEventType.CONNECT,
            connection_id="100",
        )
        await adapter.handle(connect1, None)

        call = await test_db.get_call_by_connection_id(100)
        assert call["status"] == "answered"
        assert call["connected_at"] is not None

        # Step 3: Second CONNECT (duplicate) — should not crash
        connect2 = CallEvent(
            number="+491701234567",
            direction=CallDirection.INBOUND,
            event_type=CallEventType.CONNECT,
            connection_id="100",
        )
        await adapter.handle(connect2, None)

        # Verify still answered (duplicate CONNECT doesn't break state)
        call = await test_db.get_call_by_connection_id(100)
        assert call["status"] == "answered"
        assert call["connected_at"] is not None

        # Step 4: DISCONNECT ends call
        disconnect = CallEvent(
            number="",
            direction=CallDirection.INBOUND,
            event_type=CallEventType.DISCONNECT,
            connection_id="100",
        )
        await adapter.handle(disconnect, None)

        # Verify final state
        call = await test_db.get_call_by_connection_id(100)
        assert call is not None
        assert call["status"] == "answered"
        assert call["finished_at"] is not None
        assert call["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_missing_ring_missing_connect_ends_in_unknown_state(self, test_db):
        """
        CALL → DISCONNECT without CONNECT: outbound call not reached.

        Scenario: CALL event (outbound), then immediately DISCONNECT without CONNECT.
        - Expected: Call created with status 'dialing', then finalized as 'notReached'
        - Database: duration_seconds should be 0 (no answer period)
        """
        config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
        adapter = CallLogOutputAdapter(config, test_db)

        # Step 1: CALL event creates outbound call record
        call_event = CallEvent(
            number="+491701234567",
            direction=CallDirection.OUTBOUND,
            event_type=CallEventType.CALL,
            connection_id="101",
            caller_number="+496301234567",
            called_number="+491701234567",
        )
        await adapter.handle(call_event, None)

        # Verify call created in dialing state
        call = await test_db.get_call_by_connection_id(101)
        assert call is not None
        assert call["status"] == "dialing"
        assert call["direction"] == "outbound"
        assert call["connected_at"] is None

        # Step 2: DISCONNECT without CONNECT — not reached
        disconnect = CallEvent(
            number="",
            direction=CallDirection.OUTBOUND,
            event_type=CallEventType.DISCONNECT,
            connection_id="101",
        )
        await adapter.handle(disconnect, None)

        # Verify final state: notReached, no answer time, duration_seconds == 0
        call = await test_db.get_call_by_connection_id(101)
        assert call is not None
        assert call["status"] == "notReached"
        assert call["connected_at"] is None
        assert call["finished_at"] is not None
        assert call["duration_seconds"] == 0, "No answer period, so duration should be 0"
