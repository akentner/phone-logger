"""Call log API routes."""

import logging

from fastapi import APIRouter, Query

from src.api.models import CallLogResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("", response_model=CallLogResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    number: str = Query(None, description="Filter by phone number (partial match)"),
):
    """Get paginated call log history."""
    from src.main import get_db

    db = get_db()
    items, total = await db.get_call_log(page=page, page_size=page_size, number_filter=number)

    return CallLogResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
