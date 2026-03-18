"""Call log API routes."""

import logging

from fastapi import APIRouter, Query

from src.api.models import CallListResponse, CallLogResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("/events", response_model=CallLogResponse)
async def list_call_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    number: str = Query(None, description="Filter by phone number (partial match)"),
):
    """Get paginated raw call log events.
    
    Returns individual call events (ring, call, connect, disconnect) as they were logged.
    This endpoint maintains the original call_log table data for audit and detailed tracking.
    """
    from src.main import get_db

    db = get_db()
    items, total = await db.get_call_log(page=page, page_size=page_size, number_filter=number)

    return CallLogResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/history", response_model=CallListResponse)
async def list_call_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    direction: str = Query(None, description="Filter by direction: 'inbound' or 'outbound'"),
    status: str = Query(None, description="Filter by status: 'ringing', 'dialing', 'answered', 'missed', 'notReached'"),
    line_id: int = Query(None, description="Filter by line ID"),
):
    """Get paginated aggregated calls.
    
    Returns aggregated calls with full lifecycle tracking (started, connected, finished).
    This endpoint groups related call events into logical calls with status tracking.
    """
    from src.main import get_db

    db = get_db()
    items, total = await db.get_calls(
        page=page,
        page_size=page_size,
        direction=direction,
        status=status,
        line_id=line_id,
    )

    return CallListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("", response_model=CallListResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    direction: str = Query(None, description="Filter by direction: 'inbound' or 'outbound'"),
    status: str = Query(None, description="Filter by status: 'ringing', 'dialing', 'answered', 'missed', 'notReached'"),
    line_id: int = Query(None, description="Filter by line ID"),
):
    """Get paginated aggregated calls (default endpoint).
    
    This is the main calls endpoint that returns aggregated call history.
    For raw event logs, use /api/calls/events instead.
    """
    from src.main import get_db

    db = get_db()
    items, total = await db.get_calls(
        page=page,
        page_size=page_size,
        direction=direction,
        status=status,
        line_id=line_id,
    )

    return CallListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
