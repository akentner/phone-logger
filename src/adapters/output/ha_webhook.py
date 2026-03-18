"""Home Assistant webhook output adapter - sends events to HA."""

import logging
from typing import Optional

import aiohttp

from src.adapters.base import BaseOutputAdapter
from src.config import AdapterConfig
from src.core.event import CallEvent, ResolveResult

logger = logging.getLogger(__name__)


class HaWebhookOutputAdapter(BaseOutputAdapter):
    """
    Output adapter that sends call events to Home Assistant via webhook.

    Sends a POST request with call event data to the configured HA webhook URL.
    """

    def __init__(self, config: AdapterConfig) -> None:
        super().__init__(config)
        self._url = config.config.get("url", "")
        self._token = config.config.get("token", "")
        self._events = config.config.get("events", ["ring", "call", "connect", "disconnect"])
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Create HTTP session."""
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        )
        self.logger.info("HA Webhook adapter started (URL: %s)", self._url)

    async def stop(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def handle(self, event: CallEvent, result: Optional[ResolveResult]) -> None:
        """Send call event to Home Assistant webhook."""
        if not self._url:
            self.logger.debug("No webhook URL configured, skipping")
            return

        # Check if this event type should be sent
        if event.event_type.value not in self._events:
            self.logger.debug(
                "Event type '%s' not in configured events, skipping",
                event.event_type.value,
            )
            return

        if not self._session:
            self.logger.error("HTTP session not initialized")
            return

        payload = {
            "number": event.number,
            "direction": event.direction.value,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "source": event.source,
            "resolved": result is not None,
            "name": result.name if result else None,
            "tags": result.tags if result else [],
            "spam_score": result.spam_score if result else None,
            "is_spam": result.is_spam if result else False,
            "resolver_source": result.source if result else None,
        }

        try:
            async with self._session.post(self._url, json=payload) as response:
                if response.status < 300:
                    self.logger.debug("Webhook sent successfully for '%s'", event.number)
                else:
                    self.logger.warning(
                        "Webhook returned %d for '%s'", response.status, event.number
                    )
        except aiohttp.ClientError as e:
            self.logger.error("Failed to send webhook for '%s': %s", event.number, e)
