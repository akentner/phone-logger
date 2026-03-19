"""FastAPI application setup."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def create_app(lifespan=None) -> FastAPI:
    """Create and configure the FastAPI application.

    Accept an optional `lifespan` async context manager and pass it to FastAPI to
    register startup/shutdown behaviour (preferred over @app.on_event).
    """
    app = FastAPI(
        title="phone-logger",
        description="Phone number resolver with Fritz!Box Callmonitor integration",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Mount static files
    static_path = Path(__file__).parent.parent / "gui" / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    return app
