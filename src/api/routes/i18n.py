"""I18n API routes."""

import logging

from fastapi import APIRouter, Query

from src.i18n import get_translations, get_translation, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/i18n", tags=["i18n"])


@router.get("/translations")
async def translations(lang: str = Query(default="de", description="Language code")):
    """Get all translations for a language."""
    return {
        "lang": lang if lang in SUPPORTED_LANGUAGES else "de",
        "supported_languages": SUPPORTED_LANGUAGES,
        "translations": get_translations(lang),
    }


@router.get("/translate/{key}")
async def translate(key: str, lang: str = Query(default="de")):
    """Get a single translation by key."""
    return {
        "key": key,
        "lang": lang,
        "value": get_translation(key, lang),
    }
