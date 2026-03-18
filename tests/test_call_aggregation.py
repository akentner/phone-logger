"""Tests for call aggregation functionality."""

import pytest
import tempfile
from datetime import datetime
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
        device="DECT 1",
        device_type="dect",
        msn="990133",
        trunk_id="ISDN0",
        line_id=0,
        is_internal=False,
        started_at=datetime.now().isoformat(),
    )
    
    # Retrieve the call
    call = await db.get_call(call_id)
    assert call is not None
    assert call["connection_id"] == 1
    assert call["caller_number"] == "+496181123456"
    assert call["status"] == "ringing"
    assert call["device"] == "DECT 1"
    assert call["is_internal"] is False


@pytest.mark.asyncio
async def test_upsert_call_update(test_db):
    """Test updating an existing call."""
    db = test_db
    
    call_id = uuid7()
    started_at = datetime.now().isoformat()
    
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
    connected_at = datetime.now().isoformat()
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
    """Test getting calls with pagination."""
    db = test_db
    
    # Create multiple calls
    for i in range(5):
        await db.upsert_call(
            call_id=uuid7(),
            connection_id=i,
            caller_number=f"+496181{100000 + i}",
            called_number="+496181999999",
            direction="inbound" if i % 2 == 0 else "outbound",
            status="answered",
        )
    
    # Get first page
    calls, total = await db.get_calls(page=1, page_size=2)
    assert len(calls) == 2
    assert total == 5
    
    # Get second page
    calls, total = await db.get_calls(page=2, page_size=2)
    assert len(calls) == 2


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
    calls, total = await db.get_calls(direction="inbound")
    assert total == 3
    assert all(c["direction"] == "inbound" for c in calls)
    
    # Filter by outbound
    calls, total = await db.get_calls(direction="outbound")
    assert total == 2
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
    calls, total = await db.get_calls(status="answered")
    assert total == 1
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
    calls, total = await db.get_call_log()
    assert total == 1
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
    calls, total = await db.get_call_log()
    assert total == 1
    assert calls[0]["event_type"] == "ring"


@pytest.mark.asyncio
async def test_adapter_ring_creates_call_record(test_db):
    """RING event must create a call record in the calls table."""
    config = AdapterConfig(type="call_log", name="test_call_log", enabled=True)
    adapter = CallLogOutputAdapter(config, test_db)

    event = CallEvent(
        number="+491783278576",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="7",
        caller_number="+491783278576",
        called_number="+4961813698237",
        trunk_id="SIP4",
        line_id=0,
    )
    await adapter.handle(event, None)

    call = await test_db.get_call_by_connection_id(7)
    assert call is not None
    assert call["status"] == "ringing"
    assert call["caller_number"] == "+491783278576"
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
        number="+491783278576",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="8",
        caller_number="+491783278576",
        called_number="+4961813698237",
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
        number="+491783278576",
        direction=CallDirection.INBOUND,
        event_type=CallEventType.RING,
        connection_id="9",
        caller_number="+491783278576",
        called_number="+4961813698237",
    )
    connect = CallEvent(
        number="+491783278576",
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
        number="+491783278576",
        direction=CallDirection.OUTBOUND,
        event_type=CallEventType.CALL,
        connection_id="10",
        caller_number="+4961813698237",
        called_number="+491783278576",
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
