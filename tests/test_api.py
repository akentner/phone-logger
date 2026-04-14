"""Tests for REST API endpoints."""

from datetime import UTC, datetime
import tempfile
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from src.api.app import create_app
from src.api.models import ContactCreate, NumberType
from src.core.event import ResolveResult
from src.core.utils import uuid7
from src.db.database import Database
from src.main import get_db, get_pipeline
from src.core.pipeline import Pipeline
from unittest.mock import MagicMock
from src.core.pbx import PbxStateManager


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestResolveResultModel:
    """Tests for ResolveResult model validation."""

    def test_resolve_result_model(self):
        """Test ResolveResult model validation."""
        result = ResolveResult(
            number="+491234567890",
            name="Test User",
            tags=["Familie"],
            spam_score=2,
            source="test",
        )
        assert result.number == "+491234567890"
        assert result.name == "Test User"
        assert result.is_spam is False

    def test_resolve_result_spam_detection(self):
        """Test spam detection threshold."""
        result = ResolveResult(
            number="+491234567890",
            name="Spammer",
            spam_score=8,
            source="tellows",
        )
        assert result.is_spam is True

    def test_resolve_result_no_score(self):
        """Test spam detection with no score."""
        result = ResolveResult(
            number="+491234567890",
            name="Unknown",
            source="sqlite",
        )
        assert result.is_spam is False


def _make_pbx_mock() -> MagicMock:
    """Create a mock PbxStateManager for testing."""
    pbx = MagicMock(spec=PbxStateManager)
    pbx._devices_by_id = {}

    async def _get_status():
        return {
            "lines": [],
            "trunks": [],
            "msns": [],
            "devices": [],
        }

    pbx.get_status = _get_status
    return pbx


async def test_get_calls_returns_200_with_call_list_response():
    """Test GET /api/calls returns 200 with CallListResponse.

    Verifies:
    - status_code == 200
    - response has items, next_cursor, limit fields
    - items contain expected call data
    """
    # Create temp database for this test
    tmpdir = tempfile.mkdtemp()
    db_path = str(Path(tmpdir) / "test.db")
    db = Database(db_path)
    await db.connect()

    try:
        # Create test calls
        call_id_1 = uuid7()
        call_id_2 = uuid7()
        now = datetime.now(UTC)

        await db.upsert_call(
            call_id=call_id_1,
            connection_id=1,
            caller_number="+496181123456",
            called_number="+496181654321",
            direction="inbound",
            status="answered",
            started_at=now.isoformat(),
        )

        await db.upsert_call(
            call_id=call_id_2,
            connection_id=2,
            caller_number="+496181654321",
            called_number="+496181123456",
            direction="outbound",
            status="answered",
            started_at=now.isoformat(),
        )

        # Create app with mocked dependencies
        app = create_app(lifespan=None)

        # Register routes
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

        # Mock pipeline
        mock_pbx = _make_pbx_mock()
        mock_pipeline = MagicMock(spec=Pipeline)
        mock_pipeline.pbx = mock_pbx
        mock_pipeline.normalize = lambda x: x

        # Override dependencies
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_pipeline] = lambda: mock_pipeline

        # Create test client
        transport = ASGITransport(app=app)
        async with AsyncClient(
            base_url="http://test", transport=transport
        ) as client:
            # GET /api/calls
            response = await client.get("/api/calls")

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "next_cursor" in data
            assert "limit" in data
            assert len(data["items"]) == 2
            assert data["limit"] == 50
            assert data["next_cursor"] is None

            # Verify call fields
            call1 = data["items"][0]
            assert call1["connection_id"] == 1
            assert call1["caller_number"] == "+496181123456"
            assert call1["called_number"] == "+496181654321"
            assert call1["direction"] == "inbound"
            assert call1["status"] == "answered"
            assert "id" in call1
            assert "created_at" in call1

    finally:
        await db.close()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


async def test_get_pbx_status_returns_200_with_full_status():
    """Test GET /api/pbx/status returns 200 with full PBX state."""
    tmpdir = tempfile.mkdtemp()
    db_path = str(Path(tmpdir) / "test.db")
    db = Database(db_path)
    await db.connect()

    try:
        # Create app
        app = create_app(lifespan=None)

        # Register routes
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

        # Mock pipeline
        mock_pbx = _make_pbx_mock()
        mock_pipeline = MagicMock(spec=Pipeline)
        mock_pipeline.pbx = mock_pbx
        mock_pipeline.normalize = lambda x: x

        # Override dependencies
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_pipeline] = lambda: mock_pipeline

        # Create test client
        transport = ASGITransport(app=app)
        async with AsyncClient(
            base_url="http://test", transport=transport
        ) as client:
            response = await client.get("/api/pbx/status")

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "lines" in data
            assert "trunks" in data
            assert "msns" in data
            assert "devices" in data

            # Verify all are arrays
            assert isinstance(data["lines"], list)
            assert isinstance(data["trunks"], list)
            assert isinstance(data["msns"], list)
            assert isinstance(data["devices"], list)

    finally:
        await db.close()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


async def test_post_contacts_creates_contact_returns_201():
    """Test POST /api/contacts creates contact and returns 201."""
    tmpdir = tempfile.mkdtemp()
    db_path = str(Path(tmpdir) / "test.db")
    db = Database(db_path)
    await db.connect()

    try:
        # Create app
        app = create_app(lifespan=None)

        # Register routes
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

        # Mock pipeline
        mock_pbx = _make_pbx_mock()
        mock_pipeline = MagicMock(spec=Pipeline)
        mock_pipeline.pbx = mock_pbx
        mock_pipeline.normalize = lambda x: x

        # Override dependencies
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_pipeline] = lambda: mock_pipeline

        # Create test client
        transport = ASGITransport(app=app)
        async with AsyncClient(
            base_url="http://test", transport=transport
        ) as client:
            payload = ContactCreate(
                number="+491234567890",
                name="Alice Smith",
                number_type=NumberType.PRIVATE,
                tags=["Familie"],
            )

            response = await client.post(
                "/api/contacts", json=payload.model_dump()
            )

            assert response.status_code == 201
            data = response.json()

            # Verify response fields
            assert data["number"] == "+491234567890"
            assert data["name"] == "Alice Smith"
            assert data["number_type"] == "private"
            assert data["tags"] == ["Familie"]

            # Verify contact was stored
            stored = await db.get_contact("+491234567890")
            assert stored is not None
            assert stored["name"] == "Alice Smith"
            assert stored["number_type"] == "private"

    finally:
        await db.close()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


async def test_post_contacts_duplicate_returns_409():
    """Test POST /api/contacts with duplicate number returns 409."""
    tmpdir = tempfile.mkdtemp()
    db_path = str(Path(tmpdir) / "test.db")
    db = Database(db_path)
    await db.connect()

    try:
        # Create app
        app = create_app(lifespan=None)

        # Register routes
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

        # Mock pipeline
        mock_pbx = _make_pbx_mock()
        mock_pipeline = MagicMock(spec=Pipeline)
        mock_pipeline.pbx = mock_pbx
        mock_pipeline.normalize = lambda x: x

        # Override dependencies
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_pipeline] = lambda: mock_pipeline

        # Create test client
        transport = ASGITransport(app=app)
        async with AsyncClient(
            base_url="http://test", transport=transport
        ) as client:
            payload = ContactCreate(
                number="+491234567890",
                name="Bob Jones",
                number_type=NumberType.BUSINESS,
                tags=["Arbeit"],
            )

            # First POST should succeed
            response1 = await client.post(
                "/api/contacts", json=payload.model_dump()
            )
            assert response1.status_code == 201

            # Second POST with same number should fail
            response2 = await client.post(
                "/api/contacts", json=payload.model_dump()
            )
            assert response2.status_code == 409
            error = response2.json()
            assert "already exists" in error.get("detail", "")

    finally:
        await db.close()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
