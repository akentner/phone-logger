"""Cache management API routes."""

import logging

from fastapi import APIRouter, HTTPException

from src.api.models import CacheResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("", response_model=CacheResponse)
async def list_cache():
    """Get all cache entries with expiration status."""
    from src.main import get_db

    db = get_db()
    entries = await db.get_all_cache_entries()

    return CacheResponse(items=entries, total=len(entries))


@router.delete("/{number}")
async def delete_cache(number: str, adapter: str = None):
    """Delete cache entries for a phone number."""
    from src.main import get_db

    db = get_db()
    deleted = await db.delete_cache_entry(number, adapter)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No cache entry for '{number}'")

    return {"status": "deleted", "number": number}


@router.post("/cleanup")
async def cleanup_cache():
    """Remove all expired cache entries."""
    from src.main import get_db

    db = get_db()
    removed = await db.cleanup_expired_cache()

    return {"status": "cleaned", "removed": removed}
