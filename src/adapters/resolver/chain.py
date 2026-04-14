"""Chain-of-Responsibility pattern for phone number resolution."""

import logging
from typing import Optional

from src.adapters.base import BaseResolverAdapter
from src.adapters.resolver.errors import NetworkError, RateLimitError, ResolverError
from src.core.event import ResolveResult

logger = logging.getLogger(__name__)


class ResolverChain:
    """
    Chain-of-Responsibility implementation for phone number resolution.

    Iterates through configured resolver adapters in order.
    Returns the first successful result, or None if no adapter can resolve.
    """

    def __init__(self) -> None:
        self._adapters: list[BaseResolverAdapter] = []

    def add_adapter(self, adapter: BaseResolverAdapter) -> None:
        """Add a resolver adapter to the end of the chain."""
        self._adapters.append(adapter)
        logger.info("Resolver chain: added adapter '%s' at position %d",
                     adapter.name, len(self._adapters))

    @property
    def adapters(self) -> list[BaseResolverAdapter]:
        """Get the list of adapters in the chain."""
        return list(self._adapters)

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """
        Attempt to resolve a phone number through the chain.

        Each adapter is tried in order. The first adapter that returns
        a result wins. If no adapter can resolve, returns None.
        """
        logger.debug("Resolving number '%s' through %d adapters", number, len(self._adapters))

        for adapter in self._adapters:
            try:
                result = await adapter.resolve(number)
                if result is not None:
                    logger.info("Number '%s' resolved by adapter '%s': %s",
                                number, adapter.name, result.name)
                    return result
                logger.debug("Adapter '%s' could not resolve '%s'", adapter.name, number)
            except NetworkError as exc:
                logger.warning("Adapter '%s' [NETWORK_ERROR] for '%s': %s", adapter.name, number, exc)
                continue
            except RateLimitError as exc:
                logger.warning("Adapter '%s' [RATE_LIMITED] for '%s': %s", adapter.name, number, exc)
                continue
            except ResolverError as exc:
                logger.exception("Adapter '%s' [RESOLVER_ERROR] for '%s': %s", adapter.name, number, exc)
                continue
            except Exception:
                logger.exception("Adapter '%s' failed for number '%s'", adapter.name, number)
                continue

        logger.info("Number '%s' could not be resolved by any adapter", number)
        return None

    async def start(self) -> None:
        """Initialize all adapters in the chain."""
        for adapter in self._adapters:
            try:
                await adapter.start()
            except Exception:
                logger.exception("Failed to start adapter '%s'", adapter.name)

    async def stop(self) -> None:
        """Cleanup all adapters in the chain."""
        for adapter in self._adapters:
            try:
                await adapter.stop()
            except Exception:
                logger.exception("Failed to stop adapter '%s'", adapter.name)
