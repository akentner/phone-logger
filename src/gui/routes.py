"""GUI routes — React SPA is served via StaticFiles in app.py.

This module is kept for potential server-side additions (e.g. injecting
window.__ingress_path). Currently empty.
"""

from fastapi import APIRouter

router = APIRouter(tags=["gui"])
