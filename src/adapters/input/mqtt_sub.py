"""MQTT subscriber input adapter - receives call events via MQTT."""

import asyncio
import json
import logging
from typing import Callable, Coroutine, Optional

from src.adapters.base import BaseInputAdapter
from src.config import AdapterConfig, MqttConfig
from src.core.event import CallDirection, CallEvent, CallEventType

logger = logging.getLogger(__name__)


class MqttInputAdapter(BaseInputAdapter):
    """
    Input adapter that subscribes to MQTT topics for call events.

    Expected MQTT payload (JSON):
    {
        "number": "+491234567890",
        "direction": "inbound",
        "event_type": "ring"
    }
    """

    def __init__(self, config: AdapterConfig, mqtt_config: MqttConfig) -> None:
        super().__init__(config)
        self.mqtt_config = mqtt_config
        self.topic = f"{mqtt_config.topic_prefix}/trigger"
        self._callback: Optional[Callable[[CallEvent], Coroutine]] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self, callback: Callable[[CallEvent], Coroutine]) -> None:
        """Start MQTT subscriber."""
        self._callback = callback
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self.logger.info("MQTT input adapter started (topic: %s)", self.topic)

    async def stop(self) -> None:
        """Stop MQTT subscriber."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("MQTT input adapter stopped")

    async def _run_loop(self) -> None:
        """Main MQTT subscription loop with reconnection."""
        while self._running:
            try:
                await self._subscribe()
            except asyncio.CancelledError:
                break
            except ImportError:
                self.logger.error(
                    "aiomqtt not installed. Install with: pip install aiomqtt"
                )
                break
            except Exception:
                self.logger.exception("MQTT connection error")
                if self._running:
                    await asyncio.sleep(5)

    async def _subscribe(self) -> None:
        """Subscribe to MQTT topic and process messages."""
        import aiomqtt

        async with aiomqtt.Client(
            hostname=self.mqtt_config.broker,
            port=self.mqtt_config.port,
            username=self.mqtt_config.username or None,
            password=self.mqtt_config.password or None,
        ) as client:
            await client.subscribe(self.topic)
            self.logger.info("Subscribed to MQTT topic: %s", self.topic)

            async for message in client.messages:
                if not self._running:
                    break
                await self._process_message(message)

    async def _process_message(self, message) -> None:
        """Process a single MQTT message."""
        try:
            payload = json.loads(message.payload.decode("utf-8"))

            event = CallEvent(
                number=payload.get("number", ""),
                direction=CallDirection(payload.get("direction", "inbound")),
                event_type=CallEventType(payload.get("event_type", "ring")),
                source="mqtt",
            )

            if self._callback and event.number:
                await self._callback(event)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            self.logger.error("Failed to parse MQTT message: %s", e)
