"""Main entry point for the phone-logger application."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn

from src.api.app import create_app
from src.api.routes import resolve, contacts, calls, cache, config as config_routes, i18n, pbx
from src.config import AppConfig, load_config
from src.core.pipeline import Pipeline
from src.db.database import Database
from src.gui.routes import router as gui_router

# Global state
_config: AppConfig | None = None
_db: Database | None = None
_pipeline: Pipeline | None = None


def get_config() -> AppConfig:
    """Get the current application config."""
    if _config is None:
        raise RuntimeError("Application not initialized")
    return _config


def get_db() -> Database:
    """Get the database instance."""
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


def get_pipeline() -> Pipeline:
    """Get the pipeline instance."""
    if _pipeline is None:
        raise RuntimeError("Pipeline not initialized")
    return _pipeline


def setup_logging(level: str = "INFO") -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Reduce noise from third-party libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def create_application():
    """Create the full application with all routes and lifecycle events."""
    global _config, _db, _pipeline

    # Load configuration
    config_path = os.environ.get("PHONE_LOGGER_CONFIG")
    _config = load_config(config_path)

    setup_logging(_config.log_level)
    logger = logging.getLogger(__name__)
    logger.info("phone-logger v0.1.0 starting...")

    # Create database
    _db = Database(_config.db_path)

    # Create pipeline
    _pipeline = Pipeline(_config, _db)

    # Create FastAPI app with lifespan handlers (preferred over @app.on_event)
    @asynccontextmanager
    async def _lifespan(app):
        # `app` is accepted for compatibility with FastAPI/Starlette lifespan
        logger.info("Starting up...")
        await _db.connect()
        await _pipeline.setup()
        await _pipeline.start()
        logger.info("phone-logger ready!")
        try:
            yield
        finally:
            logger.info("Shutting down...")
            await _pipeline.stop()
            await _db.close()
            logger.info("phone-logger stopped")

    # Create FastAPI app and provide lifespan function (do not call it here)
    app = create_app(lifespan=_lifespan)

    # Register API routes
    app.include_router(resolve.router)
    app.include_router(contacts.router)
    app.include_router(calls.router)
    app.include_router(cache.router)
    app.include_router(config_routes.router)
    app.include_router(i18n.router)
    app.include_router(pbx.router)

    # Register GUI routes
    app.include_router(gui_router)


    return app


# Create app instance for uvicorn
app = create_application()


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=_config.ingress_port if _config else 8080,
        log_level="info",
    )
