"""GUI routes for Jinja2 rendered pages."""

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gui"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/")
async def index(request: Request):
    """Redirect to PBX page."""
    return templates.TemplateResponse("pbx.html", {"request": request, "active": "pbx"})


@router.get("/pbx")
async def pbx_page(request: Request):
    """PBX status page."""
    return templates.TemplateResponse("pbx.html", {"request": request, "active": "pbx"})


@router.get("/contacts")
async def contacts_page(request: Request):
    """Contacts management page."""
    return templates.TemplateResponse("contacts.html", {"request": request, "active": "contacts"})


@router.get("/calls")
async def calls_page(request: Request):
    """Call history page."""
    return templates.TemplateResponse("calls.html", {"request": request, "active": "calls"})


@router.get("/cache")
async def cache_page(request: Request):
    """Cache management page."""
    return templates.TemplateResponse("cache.html", {"request": request, "active": "cache"})


@router.get("/config")
async def config_page(request: Request):
    """Configuration page."""
    return templates.TemplateResponse("config.html", {"request": request, "active": "config"})
