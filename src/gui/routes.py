"""GUI routes — serves index.html with injected ingress path."""

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gui"])

_INDEX = Path(__file__).parent / "static" / "index.html"


@router.get("/")
async def index(request: Request) -> HTMLResponse:
    """Serve React SPA with injected ingress base path."""
    ingress_path = request.headers.get("X-Ingress-Path", "").rstrip("/")
    if not _INDEX.exists():
        return HTMLResponse("<h1>Frontend not built</h1><p>Run: task build:frontend</p>", status_code=503)
    html = _INDEX.read_text()
    # Inject base path so apiFetch prepends the correct ingress prefix
    script = f'<script>window.__ingress_path="{ingress_path}/";</script>'
    html = html.replace("</head>", f"{script}</head>", 1)
    return HTMLResponse(html)
