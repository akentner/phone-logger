"""Typed exception hierarchy for resolver adapter failures."""

__all__ = ["ResolverError", "NetworkError", "RateLimitError"]


class ResolverError(Exception):
    """Base class for all resolver adapter failures.

    Raised by resolver implementations for structural or I/O errors.
    Caught by ResolverChain and logged with traceback.
    """


class NetworkError(ResolverError):
    """Raised when a network request fails.

    Covers connection errors, timeouts, and I/O failures from aiohttp.
    Caught by ResolverChain and logged as warning (no traceback).
    """


class RateLimitError(ResolverError):
    """Raised when a resolver service signals rate limiting.

    Typically corresponds to HTTP 429 or equivalent backoff signals.
    Caught by ResolverChain and logged as warning (no traceback).
    """
