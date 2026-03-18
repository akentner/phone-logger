"""Home Assistant webhook output adapter - sends events to HA."""

import logging
from typing import Optional

import aiohttp

from src.adapters.base import BaseOutputAdapter
from src.config import AdapterConfig, WebhookConfig
from src.core.event import CallEvent, ResolveResult

logger = logging.getLogger(__name__)


class HaWebhookOutputAdapter(BaseOutputAdapter):
    """
    Output adapter that sends call events to Home Assistant via webhook.

    Sends a POST request with call event data to the configured HA webhook URL.
    """

    def __init__(self, config: AdapterConfig, webhook_config: WebhookConfig) -> None:
        super().__init__(config)
        self.webhook_config = webhook_config
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Create HTTP session."""
        headers = {}
        if self.webhook_config.token:
            headers["Authorization"] = f"Bearer {self.webhook_config.token}"
        self._session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        )
        self.logger.info("HA Webhook adapter started (URL: %s)", self.webhook_config.url)

    async def stop(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def handle(self, event: CallEvent, result: Optional[ResolveResult]) -> None:
        """Send call event to Home Assistant webhook."""
        if not self.webhook_config.url:
            self.logger.debug("No webhook URL configured, skipping")
            return

        # Check if this event type should be sent
        if event.event_type.value not in self.webhook_config.events:
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
            async with self._session.post(self.webhook_config.url, json=payload) as response:
                if response.status < 300:
                    self.logger.debug("Webhook sent successfully for '%s'", event.number)
                else:
                    self.logger.warning(
                        "Webhook returned %d for '%s'", response.status, event.number
                    )
        except aiohttp.ClientError as e:
            self.logger.error("Failed to send webhook for '%s': %s", event.number, e)
