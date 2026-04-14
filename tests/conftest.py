"""Pytest configuration and shared fixtures."""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.app import create_app
from src.core.pbx import PbxStateManager, DeviceInfo
from src.core.pipeline import Pipeline
from src.core.event import NumberType
from src.db.database import Database
from src.main import get_db, get_pipeline


def _make_pbx_mock() -> MagicMock:
    """Create a mock PbxStateManager for testing.

    Returns a MagicMock that implements:
    - pbx._devices_by_id = {} (empty device mapping)
    - pbx.get_status() returning skeleton structure
    """
    pbx = MagicMock(spec=PbxStateManager)
    pbx._devices_by_id = {}

    # Mock get_status to return empty structures
    async def _get_status():
        return {
            "lines": [],
            "trunks": [],
            "msns": [],
            "devices": [],
        }

    pbx.get_status = _get_status
    return pbx


@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create a temporary test database (function-scoped)."""
    tmpdir = tempfile.mkdtemp()
    db_path = str(Path(tmpdir) / "test.db")
    db = Database(db_path)
    await db.connect()
    try:
        yield db
    finally:
        await db.close()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest_asyncio.fixture(scope="function")
async def test_app(test_db):
    """Create FastAPI app for testing with mocked dependencies.

    Creates app via create_app(lifespan=None) and registers all routes
    with dependency overrides for test_db and a mocked Pipeline.
    """
    # Create app without lifespan (we don't want real MQTT/Fritz startup)
    app = create_app(lifespan=None)

    # Create a mock pipeline with mocked PBX
    mock_pbx = _make_pbx_mock()
    mock_pipeline = MagicMock(spec=Pipeline)
    mock_pipeline.pbx = mock_pbx
    mock_pipeline.normalize = lambda x: x  # Identity function for testing

    # Register all routes with explicit routers
    from src.api.routes import (
        resolve,
        contacts,
        calls,
        cache,
        config as config_routes,
        i18n,
        pbx,
    )
    from src.gui.routes import router as gui_router

    app.include_router(resolve.router)
    app.include_router(contacts.router)
    app.include_router(calls.router)
    app.include_router(cache.router)
    app.include_router(config_routes.router)
    app.include_router(i18n.router)
    app.include_router(pbx.router)
    app.include_router(gui_router)

    # Override dependencies
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_pipeline] = lambda: mock_pipeline

    yield app

    # Cleanup
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_client(test_app, test_db):
    """Create AsyncClient for testing FastAPI endpoints.

    Uses ASGITransport to allow async/await in tests.
    Depends on both test_app and test_db to ensure they're created before the test.
    """
    transport = ASGITransport(app=test_app)
    client = AsyncClient(base_url="http://test", transport=transport)
    try:
        yield client
    finally:
        await client.aclose()
