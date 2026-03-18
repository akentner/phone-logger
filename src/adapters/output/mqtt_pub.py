"""MQTT publisher output adapter - publishes call events to MQTT."""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Optional

from src.adapters.base import BaseOutputAdapter
from src.config import AdapterConfig
from src.core.event import CallEvent, ResolveResult

if TYPE_CHECKING:
    from src.core.pbx import LineState

logger = logging.getLogger(__name__)


class MqttPublisherOutputAdapter(BaseOutputAdapter):
    """
    Output adapter that publishes call events to MQTT topics.

    Topic structure:
    - {prefix}/event          - All events (JSON payload)
    - {prefix}/event/{type}   - Filtered by event type
    """

    def __init__(self, config: AdapterConfig) -> None:
        super().__init__(config)
        self._broker = config.config.get("broker", "homeassistant")
        self._port = config.config.get("port", 1883)
        self._username = config.config.get("username", "")
        self._password = config.config.get("password", "")
        self._client_id = config.config.get("client_id", "")
        self._topic_prefix = config.config.get("topic_prefix", "phone-logger")
        self._qos = config.config.get("qos", 1)
        self._retain = config.config.get("retain", True)
        self._keep_alive = config.config.get("keep_alive", 60)
        self._connect_timeout = config.config.get("connect_timeout", 30)
        self._client = None

    async def start(self) -> None:
        """Initialize MQTT connection info."""
        self.logger.info(
            "MQTT publisher adapter configured (broker: %s, prefix: %s)",
            self._broker,
            self._topic_prefix,
        )

    async def stop(self) -> None:
        """Cleanup."""
        pass

    async def handle(
        self,
        event: CallEvent,
        result: Optional[ResolveResult],
        *,
        line_state: Optional["LineState"] = None,
    ) -> None:
        """Publish call event to MQTT."""
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

        topic_base = self._topic_prefix
        message = json.dumps(payload)

        try:
            import aiomqtt

            client_kwargs = {
                "hostname": self._broker,
                "port": self._port,
                "username": self._username or None,
                "password": self._password or None,
                "keepalive": self._keep_alive,
                "timeout": self._connect_timeout,
            }
            if self._client_id:
                client_kwargs["identifier"] = self._client_id

            async with aiomqtt.Client(**client_kwargs) as client:
                # Publish to general topic
                await client.publish(
                    f"{topic_base}/event", message,
                    qos=self._qos, retain=self._retain,
                )
                # Publish to event-type-specific topic
                await client.publish(
                    f"{topic_base}/event/{event.event_type.value}", message,
                    qos=self._qos, retain=self._retain,
                )

            self.logger.debug("MQTT published for '%s' on %s/event", event.number, topic_base)

        except ImportError:
            self.logger.error("aiomqtt not installed")
        except Exception as e:
            self.logger.error("Failed to publish MQTT for '%s': %s", event.number, e)
