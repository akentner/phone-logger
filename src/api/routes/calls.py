"""Call log API routes."""

import logging

from fastapi import APIRouter, Query

from src.api.models import (
    CallListResponse,
    CallLogResponse,
    DeviceInfoResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calls", tags=["calls"])


def _enrich_call_devices(call_dict: dict, devices_by_id: dict) -> dict:
    """Reconstruct caller_device / called_device from stored IDs using AppConfig."""
    for field, id_field in [
        ("caller_device", "caller_device_id"),
        ("called_device", "called_device_id"),
    ]:
        device_id = call_dict.get(id_field)
        if device_id and device_id in devices_by_id:
            d = devices_by_id[device_id]
            call_dict[field] = DeviceInfoResponse(
                id=d.id,
                extension=d.extension,
                name=d.name,
                type=d.type.value,
            )
        else:
            call_dict[field] = None
    return call_dict


@router.get("/events", response_model=CallLogResponse)
async def list_call_events(
    cursor: str = Query(None, description="UUID of the last seen row (exclusive)"),
    limit: int = Query(50, ge=1, le=200),
    search: str = Query(
        None, description="Search by phone number or resolved name (partial match)"
    ),
):
    """Get paginated raw call log events (cursor-based).

    Returns individual call events (ring, call, connect, disconnect) as they were logged.
    Pass the returned `next_cursor` as `cursor` to fetch the next page.
    """
    from src.main import get_db

    db = get_db()
    items, next_cursor = await db.get_call_log(
        cursor=cursor, limit=limit, number_filter=search
    )

    return CallLogResponse(
        items=items,
        next_cursor=next_cursor,
        limit=limit,
    )


@router.get("/history", response_model=CallListResponse)
async def list_call_history(
    cursor: str = Query(None, description="UUID of the last seen row (exclusive)"),
    limit: int = Query(50, ge=1, le=200),
    direction: str = Query(
        None, description="Filter by direction: 'inbound' or 'outbound'"
    ),
    status: str = Query(
        None,
        description="Filter by status: 'ringing', 'dialing', 'answered', 'missed', 'notReached'",
    ),
    line_id: int = Query(None, description="Filter by line ID"),
    search: str = Query(
        None, description="Search by phone number or resolved name (partial match)"
    ),
    msn: list[str] = Query(
        None,
        description="Filter by one or more MSNs (e.g. ?msn=+496181990133&msn=+496181990134)",
    ),
):
    """Get paginated aggregated calls (cursor-based).

    Returns aggregated calls with full lifecycle tracking (started, connected, finished).
    Pass the returned `next_cursor` as `cursor` to fetch the next page.
    """
    from src.main import get_db, get_pipeline

    db = get_db()
    items, next_cursor = await db.get_calls(
        cursor=cursor,
        limit=limit,
        direction=direction,
        status=status,
        line_id=line_id,
        search=search,
        msn=msn or None,
    )

    devices_by_id = get_pipeline().pbx._devices_by_id
    enriched = [_enrich_call_devices(item, devices_by_id) for item in items]

    return CallListResponse(
        items=enriched,
        next_cursor=next_cursor,
        limit=limit,
    )


@router.get("", response_model=CallListResponse)
async def list_calls(
    cursor: str = Query(None, description="UUID of the last seen row (exclusive)"),
    limit: int = Query(50, ge=1, le=200),
    direction: str = Query(
        None, description="Filter by direction: 'inbound' or 'outbound'"
    ),
    status: str = Query(
        None,
        description="Filter by status: 'ringing', 'dialing', 'answered', 'missed', 'notReached'",
    ),
    line_id: int = Query(None, description="Filter by line ID"),
    search: str = Query(
        None, description="Search by phone number or resolved name (partial match)"
    ),
    msn: list[str] = Query(
        None,
        description="Filter by one or more MSNs (e.g. ?msn=+496181990133&msn=+496181990134)",
    ),
):
    """Get paginated aggregated calls (default endpoint, cursor-based).

    This is the main calls endpoint that returns aggregated call history.
    Pass the returned `next_cursor` as `cursor` to fetch the next page.
    For raw event logs, use /api/calls/events instead.
    """
    from src.main import get_db, get_pipeline

    db = get_db()
    items, next_cursor = await db.get_calls(
        cursor=cursor,
        limit=limit,
        direction=direction,
        status=status,
        line_id=line_id,
        search=search,
        msn=msn or None,
    )

    devices_by_id = get_pipeline().pbx._devices_by_id
    enriched = [_enrich_call_devices(item, devices_by_id) for item in items]

    return CallListResponse(
        items=enriched,
        next_cursor=next_cursor,
        limit=limit,
    )
