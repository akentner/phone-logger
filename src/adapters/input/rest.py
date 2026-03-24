"""REST input adapter - receives call events via HTTP POST."""

import json
import logging
from typing import Callable, Coroutine, Optional

from src.adapters.base import BaseInputAdapter
from src.core.event import CallDirection, CallEvent, CallEventType

logger = logging.getLogger(__name__)


class RestInputAdapter(BaseInputAdapter):
    """
    Input adapter that receives call events via REST API.

    This adapter doesn't actively listen - instead it provides a method
    that the FastAPI route handler calls when a POST is received.
    """

    def __init__(self, config) -> None:
        super().__init__(config)
        self._callback: Optional[Callable[[CallEvent], Coroutine]] = None

    async def start(self, callback: Callable[[CallEvent], Coroutine]) -> None:
        """Register the event callback."""
        self._callback = callback
        self.logger.info("REST input adapter started")

    async def stop(self) -> None:
        """Nothing to clean up."""
        self._callback = None
        self.logger.info("REST input adapter stopped")

    async def trigger(
        self, number: str, direction: str = "inbound", event_type: str = "ring"
    ) -> Optional[CallEvent]:
        """
        Manually trigger a call event (called from REST API).

        Returns the created CallEvent, or None if no callback registered.
        """
        if not self._callback:
            self.logger.warning("REST trigger called but no callback registered")
            return None

        raw_input = json.dumps(
            {"number": number, "direction": direction, "event_type": event_type}
        )
        event = CallEvent(
            number=number,
            direction=CallDirection(direction),
            event_type=CallEventType(event_type),
            source="rest",
            raw_input=raw_input,
        )

        await self._callback(event)
        return event
