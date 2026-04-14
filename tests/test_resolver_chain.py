"""Tests for the resolver chain (Chain-of-Responsibility)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.adapters.base import BaseResolverAdapter
from src.adapters.resolver.chain import ResolverChain
from src.adapters.resolver.errors import NetworkError, RateLimitError, ResolverError
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


class ErroringResolver(BaseResolverAdapter):
    """Mock resolver that raises a specified exception."""

    def __init__(self, name: str, exc: Exception):
        config = AdapterConfig(type="test", name=name, enabled=True)
        super().__init__(config)
        self._exc = exc

    async def resolve(self, number: str):
        raise self._exc


class TestResolverChainErrorHandling:
    """Tests for typed exception handling in ResolverChain.resolve()."""

    @pytest.fixture
    def chain(self):
        return ResolverChain()

    async def test_network_error_logs_warning_continues(self, chain, caplog):
        import logging

        chain.add_adapter(ErroringResolver("scraper", NetworkError("connection refused")))
        fallback_result = ResolveResult(number="+491234567890", name="Fallback", source="fallback")
        chain.add_adapter(MockResolver("fallback", fallback_result))

        with caplog.at_level(logging.WARNING):
            result = await chain.resolve("+491234567890")

        assert result is not None
        assert result.name == "Fallback"
        assert "[NETWORK_ERROR]" in caplog.text

    async def test_rate_limit_error_logs_warning_continues(self, chain, caplog):
        import logging

        chain.add_adapter(ErroringResolver("scraper", RateLimitError("HTTP 429")))
        fallback_result = ResolveResult(number="+491234567890", name="Fallback", source="fallback")
        chain.add_adapter(MockResolver("fallback", fallback_result))

        with caplog.at_level(logging.WARNING):
            result = await chain.resolve("+491234567890")

        assert result is not None
        assert result.name == "Fallback"
        assert "[RATE_LIMITED]" in caplog.text

    async def test_resolver_error_logs_with_exception(self, chain, caplog):
        import logging

        chain.add_adapter(ErroringResolver("db", ResolverError("SQLite broken")))
        fallback_result = ResolveResult(number="+491234567890", name="Fallback", source="fallback")
        chain.add_adapter(MockResolver("fallback", fallback_result))

        with caplog.at_level(logging.ERROR):
            result = await chain.resolve("+491234567890")

        assert result is not None
        assert result.name == "Fallback"
        assert "[RESOLVER_ERROR]" in caplog.text

    async def test_network_error_no_traceback_in_warning(self, chain, caplog):
        """NetworkError must be logged at WARNING level, not ERROR/EXCEPTION (no traceback)."""
        import logging

        chain.add_adapter(ErroringResolver("scraper", NetworkError("timeout")))
        chain.add_adapter(MockResolver("fallback", None))

        with caplog.at_level(logging.DEBUG):
            await chain.resolve("+491234567890")

        # Find the NETWORK_ERROR log record and assert it's WARNING, not ERROR
        network_records = [r for r in caplog.records if "[NETWORK_ERROR]" in r.message]
        assert len(network_records) == 1
        assert network_records[0].levelno == logging.WARNING
