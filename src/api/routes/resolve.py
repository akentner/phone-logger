"""Resolve API routes."""

import logging

from fastapi import APIRouter, HTTPException

from src.api.models import ResolveResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["resolve"])


@router.get("/resolve/{number}", response_model=ResolveResponse)
async def resolve_number(number: str):
    """
    Resolve a phone number through the configured adapter chain.

    Returns 404 if the number cannot be resolved by any adapter.
    """
    from src.main import get_pipeline

    pipeline = get_pipeline()
    result = await pipeline.resolve(number)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Number '{number}' could not be resolved")

    return ResolveResponse(
        number=result.number,
        name=result.name,
        tags=result.tags,
        notes=result.notes,
        spam_score=result.spam_score,
        source=result.source,
        cached=result.cached,
    )


@router.post("/trigger/{number}")
async def trigger_call_event(number: str, direction: str = "inbound", event_type: str = "ring"):
    """
    Manually trigger a call event through the pipeline (REST input adapter).

    This simulates a call event and processes it through resolve + output.
    """
    from src.main import get_pipeline

    pipeline = get_pipeline()
    rest_input = pipeline.rest_input

    if not rest_input:
        raise HTTPException(status_code=503, detail="REST input adapter not available")

    event = await rest_input.trigger(number, direction, event_type)
    if not event:
        raise HTTPException(status_code=500, detail="Failed to trigger event")

    return {"status": "triggered", "number": number, "direction": direction, "event_type": event_type}
