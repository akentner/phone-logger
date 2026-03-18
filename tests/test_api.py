"""Tests for REST API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.core.event import ResolveResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestResolveAPI:
    """Tests for /api/resolve endpoint."""

    # Note: Full API tests require app setup with database.
    # These are placeholder tests that should be expanded with fixtures.

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
