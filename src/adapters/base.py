"""Base adapter interfaces for the phone-logger pipeline."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from src.config import AdapterConfig
from src.core.event import CallEvent, ResolveResult

logger = logging.getLogger(__name__)


class BaseInputAdapter(ABC):
    """Base class for input adapters that produce call events."""

    def __init__(self, config: AdapterConfig) -> None:
        self.config = config
        self.name = config.name
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    async def start(self, callback) -> None:
        """Start listening for events. Call callback(CallEvent) for each event."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening for events."""


class BaseResolverAdapter(ABC):
    """Base class for resolver adapters that resolve phone numbers."""

    def __init__(self, config: AdapterConfig) -> None:
        self.config = config
        self.name = config.name
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """
        Try to resolve a phone number.

        Returns ResolveResult if found, None if this adapter cannot resolve.
        """

    async def start(self) -> None:
        """Optional initialization (e.g., load file, open connection)."""

    async def stop(self) -> None:
        """Optional cleanup."""


class BaseOutputAdapter(ABC):
    """Base class for output adapters that process resolved events."""

    def __init__(self, config: AdapterConfig) -> None:
        self.config = config
        self.name = config.name
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    async def handle(self, event: CallEvent, result: Optional[ResolveResult]) -> None:
        """Handle a processed call event with its resolve result."""

    async def start(self) -> None:
        """Optional initialization."""

    async def stop(self) -> None:
        """Optional cleanup."""
