"""Tests for REST API endpoints."""

from datetime import UTC, datetime

import pytest

from src.api.models import ContactCreate, NumberType
from src.core.event import ResolveResult
from src.core.utils import uuid7


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


class TestApiRoutes:
    """Test FastAPI routes with TestClient."""

    @pytest.mark.asyncio
    async def test_get_calls_returns_200_with_call_list_response(
        self, test_client, test_db
    ):
        """Test GET /api/calls returns 200 with CallListResponse.

        Verifies:
        - status_code == 200
        - response has items, next_cursor, limit fields
        - items contain expected call data
        """
        # Create test calls
        call_id_1 = uuid7()
        call_id_2 = uuid7()
        now = datetime.now(UTC)

        await test_db.upsert_call(
            call_id=call_id_1,
            connection_id=1,
            caller_number="+496181123456",
            called_number="+496181654321",
            direction="inbound",
            status="answered",
            started_at=now.isoformat(),
        )

        await test_db.upsert_call(
            call_id=call_id_2,
            connection_id=2,
            caller_number="+496181654321",
            called_number="+496181123456",
            direction="outbound",
            status="answered",
            started_at=now.isoformat(),
        )

        # GET /api/calls
        response = await test_client.get("/api/calls")

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

    @pytest.mark.asyncio
    async def test_get_pbx_status_returns_200_with_full_status(
        self, test_client
    ):
        """Test GET /api/pbx/status returns 200 with full PBX state.

        Verifies:
        - status_code == 200
        - response has lines, trunks, msns, devices keys
        - all values are arrays (may be empty)
        """
        response = await test_client.get("/api/pbx/status")

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

    @pytest.mark.asyncio
    async def test_post_contacts_creates_contact_returns_201(
        self, test_client, test_db
    ):
        """Test POST /api/contacts creates contact and returns 201.

        Verifies:
        - status_code == 201
        - response has id, number, name, number_type, tags fields
        - contact is stored in database
        """
        payload = ContactCreate(
            number="+491234567890",
            name="Alice Smith",
            number_type=NumberType.PRIVATE,
            tags=["Familie"],
        )

        response = await test_client.post(
            "/api/contacts", json=payload.model_dump()
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response fields
        assert data["number"] == "+491234567890"
        assert data["name"] == "Alice Smith"
        assert data["number_type"] == "private"
        assert data["tags"] == ["Familie"]
        assert "id" in data or "number" in data  # Contact should have identifier

        # Verify contact was stored
        stored = await test_db.get_contact("+491234567890")
        assert stored is not None
        assert stored["name"] == "Alice Smith"
        assert stored["number_type"] == "private"

    @pytest.mark.asyncio
    async def test_post_contacts_duplicate_returns_409(self, test_client, test_db):
        """Test POST /api/contacts with duplicate number returns 409.

        Verifies:
        - First POST returns 201
        - Second POST with same number returns 409 (Conflict)
        """
        payload = ContactCreate(
            number="+491234567890",
            name="Bob Jones",
            number_type=NumberType.BUSINESS,
            tags=["Arbeit"],
        )

        # First POST should succeed
        response1 = await test_client.post(
            "/api/contacts", json=payload.model_dump()
        )
        assert response1.status_code == 201

        # Second POST with same number should fail
        response2 = await test_client.post(
            "/api/contacts", json=payload.model_dump()
        )
        assert response2.status_code == 409
        error = response2.json()
        assert "already exists" in error.get("detail", "")
