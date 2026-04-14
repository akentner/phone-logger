"""FastAPI application setup."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class IngressRootPathMiddleware(BaseHTTPMiddleware):
    """Set ASGI root_path from X-Ingress-Path header for HA ingress support.

    This allows FastAPI's /docs and /openapi.json to work correctly behind
    the Home Assistant ingress proxy.
    """

    async def dispatch(self, request: Request, call_next):
        ingress_path = request.headers.get("X-Ingress-Path", "")
        if ingress_path:
            request.scope["root_path"] = ingress_path
        return await call_next(request)


def create_app(lifespan=None) -> FastAPI:
    """Create and configure the FastAPI application.

    Accept an optional `lifespan` async context manager and pass it to FastAPI to
    register startup/shutdown behaviour (preferred over @app.on_event).
    """
    app = FastAPI(
        title="phone-logger",
        description="Phone number resolver with Fritz!Box Callmonitor integration",
        version="1.0.3",
        lifespan=lifespan,
    )

    app.add_middleware(IngressRootPathMiddleware)

    # Mount static files
    static_path = Path(__file__).parent.parent / "gui" / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    return app
