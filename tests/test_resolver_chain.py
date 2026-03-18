"""Tests for the resolver chain (Chain-of-Responsibility)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.adapters.base import BaseResolverAdapter
from src.adapters.resolver.chain import ResolverChain
from src.config import AdapterConfig
from src.core.event import ResolveResult


class MockResolver(BaseResolverAdapter):
    """Mock resolver for testing."""

    def __init__(self, name: str, result: ResolveResult | None = None):
        config = AdapterConfig(type="test", name=name, enabled=True)
        super().__init__(config)
        self._result = result
        self.resolve_called = False

    async def resolve(self, number: str):
        self.resolve_called = True
        return self._result


class TestResolverChain:
    """Tests for ResolverChain."""

    @pytest.fixture
    def chain(self):
        return ResolverChain()

    @pytest.mark.asyncio
    async def test_empty_chain_returns_none(self, chain):
        result = await chain.resolve("+491234567890")
        assert result is None

    @pytest.mark.asyncio
    async def test_single_adapter_resolves(self, chain):
        expected = ResolveResult(
            number="+491234567890",
            name="Test User",
            source="test",
        )
        chain.add_adapter(MockResolver("test", expected))

        result = await chain.resolve("+491234567890")
        assert result is not None
        assert result.name == "Test User"
        assert result.source == "test"

    @pytest.mark.asyncio
    async def test_chain_stops_at_first_result(self, chain):
        first = MockResolver("first", ResolveResult(
            number="+491234567890", name="First", source="first"
        ))
        second = MockResolver("second", ResolveResult(
            number="+491234567890", name="Second", source="second"
        ))
        chain.add_adapter(first)
        chain.add_adapter(second)

        result = await chain.resolve("+491234567890")
        assert result.name == "First"
        assert first.resolve_called is True
        assert second.resolve_called is False

    @pytest.mark.asyncio
    async def test_chain_skips_none_results(self, chain):
        first = MockResolver("first", None)
        second = MockResolver("second", ResolveResult(
            number="+491234567890", name="Second", source="second"
        ))
        chain.add_adapter(first)
        chain.add_adapter(second)

        result = await chain.resolve("+491234567890")
        assert result.name == "Second"
        assert first.resolve_called is True
        assert second.resolve_called is True

    @pytest.mark.asyncio
    async def test_chain_returns_none_if_all_fail(self, chain):
        chain.add_adapter(MockResolver("first", None))
        chain.add_adapter(MockResolver("second", None))

        result = await chain.resolve("+491234567890")
        assert result is None

    @pytest.mark.asyncio
    async def test_chain_handles_adapter_exception(self, chain):
        class BrokenResolver(BaseResolverAdapter):
            async def resolve(self, number):
                raise RuntimeError("Adapter crashed")

        broken = BrokenResolver(AdapterConfig(type="test", name="broken", enabled=True))
        fallback = MockResolver("fallback", ResolveResult(
            number="+491234567890", name="Fallback", source="fallback"
        ))
        chain.add_adapter(broken)
        chain.add_adapter(fallback)

        result = await chain.resolve("+491234567890")
        assert result.name == "Fallback"

    def test_adapters_property(self, chain):
        adapter = MockResolver("test", None)
        chain.add_adapter(adapter)
        assert len(chain.adapters) == 1
        assert chain.adapters[0].name == "test"
