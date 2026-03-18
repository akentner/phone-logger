"""MQTT publisher output adapter - publishes call events and line state to MQTT."""

import json
import logging
from typing import TYPE_CHECKING, Optional

from src.adapters.base import BaseOutputAdapter
from src.config import AdapterConfig
from src.core.event import CallEvent, ResolveResult

if TYPE_CHECKING:
    from src.core.pbx import LineState

logger = logging.getLogger(__name__)


def _serialize_line_state(line_state: Optional["LineState"]) -> Optional[dict]:
    """Serialize a LineState to a JSON-friendly dict, or None if absent."""
    if line_state is None:
        return None
    return {
        "line_id": line_state.line_id,
        "status": line_state.status.value,
        "connection_id": line_state.connection_id,
        "caller_number": line_state.caller_number,
        "called_number": line_state.called_number,
        "direction": line_state.direction.value if line_state.direction else None,
        "trunk_id": line_state.trunk_id,
        "device": (
            {
                "id": line_state.device.id,
                "name": line_state.device.name,
                "type": line_state.device.type,
            }
            if line_state.device
            else None
        ),
        "is_internal": line_state.is_internal,
        "since": line_state.since.isoformat() if line_state.since else None,
    }


class MqttPublisherOutputAdapter(BaseOutputAdapter):
    """
    Output adapter that publishes call events and line state to MQTT topics.

    Topic structure:
    - {prefix}/event                - All events (JSON payload)
    - {prefix}/event/{type}         - Filtered by event type
    - {prefix}/line/{line_id}/state - Per-line FSM state (retained, only on change)
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
        # Track last published line state per line_id to detect changes
        self._last_line_status: dict[int, str] = {}

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
        """Publish call event and line state to MQTT."""
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
            "line_state": _serialize_line_state(line_state),
        }

        topic_base = self._topic_prefix
        message = json.dumps(payload)

        # Determine whether line state changed (for dedicated state topic)
        line_state_changed = False
        if line_state is not None and line_state.line_id is not None:
            current_status = line_state.status.value
            previous_status = self._last_line_status.get(line_state.line_id)
            if current_status != previous_status:
                line_state_changed = True
                self._last_line_status[line_state.line_id] = current_status

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
                # Publish to general event topic
                await client.publish(
                    f"{topic_base}/event",
                    message,
                    qos=self._qos,
                    retain=self._retain,
                )
                # Publish to event-type-specific topic
                await client.publish(
                    f"{topic_base}/event/{event.event_type.value}",
                    message,
                    qos=self._qos,
                    retain=self._retain,
                )

                # Publish line state to dedicated topic (only on change)
                if line_state_changed and line_state is not None:
                    state_payload = json.dumps(_serialize_line_state(line_state))
                    await client.publish(
                        f"{topic_base}/line/{line_state.line_id}/state",
                        state_payload,
                        qos=self._qos,
                        retain=True,  # Always retain line state
                    )
                    self.logger.debug(
                        "MQTT line state published: %s/line/%d/state -> %s",
                        topic_base,
                        line_state.line_id,
                        line_state.status.value,
                    )

            self.logger.debug(
                "MQTT published for '%s' on %s/event", event.number, topic_base
            )

        except ImportError:
            self.logger.error("aiomqtt not installed")
        except Exception as e:
            self.logger.error("Failed to publish MQTT for '%s': %s", event.number, e)
