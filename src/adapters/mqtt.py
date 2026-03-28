"""Combined MQTT adapter — single persistent connection for both subscribe and publish."""

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING, Callable, Coroutine, Optional

from src.adapters.base import BaseInputAdapter, BaseOutputAdapter
from src.config import AdapterConfig, AppConfig
from src.core.event import CallDirection, CallEvent, CallEventType, ResolveResult
from src.core import phone_number as pn

if TYPE_CHECKING:
    from src.core.pbx import LineState, PbxStateManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_line_state(
    line_state: Optional["LineState"],
    caller_display: Optional[str] = None,
    called_display: Optional[str] = None,
) -> Optional[dict]:
    """Serialize a LineState to a JSON-friendly dict, or None if absent."""
    if line_state is None:
        return None

    def _device_dict(device) -> Optional[dict]:
        if not device:
            return None
        return {"id": device.id, "name": device.name, "type": device.type}

    return {
        "line_id": line_state.line_id,
        "status": line_state.status.value,
        "connection_id": line_state.connection_id,
        "caller_number": line_state.caller_number,
        "called_number": line_state.called_number,
        "caller_display": caller_display,
        "called_display": called_display,
        "direction": line_state.direction.value if line_state.direction else None,
        "trunk_id": line_state.trunk_id,
        "caller_device": _device_dict(line_state.caller_device),
        "called_device": _device_dict(line_state.called_device),
        "is_internal": line_state.is_internal,
        "last_changed": line_state.last_changed.isoformat()
        if line_state.last_changed
        else None,
    }


def _slugify(text: str) -> str:
    """Convert a string to a safe slug for use in MQTT topics and HA entity IDs."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


# ---------------------------------------------------------------------------
# Combined adapter
# ---------------------------------------------------------------------------


class MqttAdapter(BaseInputAdapter, BaseOutputAdapter):
    """
    Combined MQTT adapter: a single persistent connection handles both
    subscribing to incoming call-event triggers and publishing resolved
    events / state updates.

    Topic structure:
    - {prefix}/status                 - Birth/LWT: "online" / "offline" (retained)
    - {prefix}/trigger                - Subscribe: incoming JSON call events
    - {prefix}/event                  - Publish: all processed events
    - {prefix}/event/{type}           - Publish: filtered by event type
    - {prefix}/line/{line_id}/state   - Publish: per-line FSM state (retained, on change)
    - {prefix}/trunk/{trunk_id}/state - Publish: per-trunk status   (retained, on change)

    Home Assistant Auto Discovery (if ha_discovery: true):
    - {ha_prefix}/sensor/{entity_prefix}_line_{id}/config
    - {ha_prefix}/sensor/{entity_prefix}_trunk_{id}/config

    Config keys (all optional):
      broker, port, username, password, client_id, topic_prefix,
      qos, retain, keep_alive, connect_timeout, reconnect_delay,
      ha_discovery, ha_discovery_prefix, ha_entity_id_prefix
    """

    def __init__(
        self,
        config: AdapterConfig,
        app_config: Optional[AppConfig] = None,
        pbx: Optional["PbxStateManager"] = None,
    ) -> None:
        # BaseInputAdapter.__init__ and BaseOutputAdapter.__init__ are identical;
        # call only once to avoid duplicate attribute assignment.
        BaseInputAdapter.__init__(self, config)

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
        self._reconnect_delay = config.config.get("reconnect_delay", 10)
        self._ha_discovery = config.config.get("ha_discovery", False)
        self._ha_discovery_prefix = config.config.get(
            "ha_discovery_prefix", "homeassistant"
        )
        self._ha_entity_id_prefix: Optional[str] = config.config.get(
            "ha_entity_id_prefix", None
        )
        self._app_config = app_config
        self._pbx = pbx

        self._trigger_topic = f"{self._topic_prefix}/trigger"
        self._status_topic = f"{self._topic_prefix}/status"

        # Input callback registered via start(callback)
        self._callback: Optional[Callable[[CallEvent], Coroutine]] = None

        # Persistent connection state
        self._client = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._ready = asyncio.Event()

        # Change tracking for state topics
        self._last_line_status: dict[int, str] = {}
        self._last_trunk_status: dict[str, str] = {}

    # ------------------------------------------------------------------
    # BaseInputAdapter.start — called by pipeline with the event callback
    # ------------------------------------------------------------------

    async def start(
        self, callback: Optional[Callable[[CallEvent], Coroutine]] = None
    ) -> None:  # type: ignore[override]
        """Start the persistent MQTT connection (subscribe + publish).

        When called with a callback (input path), registers the callback and
        starts the connection loop.  When called without arguments (output path
        by the pipeline), acts as a no-op if the connection is already running.
        """
        if callback is not None:
            self._callback = callback

        if self._running:
            # Already started via the input path — output start() is a no-op.
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self.logger.info(
            "MQTT adapter started (broker: %s:%d, prefix: %s)",
            self._broker,
            self._port,
            self._topic_prefix,
        )
        # Wait briefly for the initial connection so the first handle() call
        # has a live client available.
        try:
            await asyncio.wait_for(asyncio.shield(self._ready.wait()), timeout=5.0)
        except asyncio.TimeoutError:
            self.logger.warning(
                "MQTT adapter: initial connection timed out — will retry in background"
            )

    # ------------------------------------------------------------------
    # Lifecycle: stop
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """Publish offline status and close the MQTT connection."""
        self._running = False
        if self._client is not None:
            try:
                await self._client.publish(
                    self._status_topic,
                    "offline",
                    qos=self._qos,
                    retain=True,
                )
            except Exception as exc:
                self.logger.debug("Could not publish offline status: %s", exc)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("MQTT adapter stopped")

    # ------------------------------------------------------------------
    # Reconnection loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Reconnection loop with exponential back-off on errors."""
        while self._running:
            try:
                await self._connect()
            except asyncio.CancelledError:
                break
            except ImportError:
                self.logger.error(
                    "aiomqtt not installed. Install with: pip install aiomqtt"
                )
                break
            except Exception:
                self.logger.exception("MQTT connection error")
                self._client = None
                self._ready.clear()
                if self._running:
                    await asyncio.sleep(self._reconnect_delay)

    async def _connect(self) -> None:
        """Open one MQTT connection, publish Birth + HA discovery, subscribe + idle-loop."""
        import aiomqtt

        client_kwargs: dict = {
            "hostname": self._broker,
            "port": self._port,
            "username": self._username or None,
            "password": self._password or None,
            "keepalive": self._keep_alive,
            "timeout": self._connect_timeout,
            "will": aiomqtt.Will(
                topic=self._status_topic,
                payload="offline",
                qos=self._qos,
                retain=True,
            ),
        }
        if self._client_id:
            client_kwargs["identifier"] = self._client_id

        async with aiomqtt.Client(**client_kwargs) as client:
            self._client = client
            self.logger.info(
                "MQTT connected to %s:%d (prefix: %s)",
                self._broker,
                self._port,
                self._topic_prefix,
            )

            # Birth message
            await client.publish(
                self._status_topic, "online", qos=self._qos, retain=True
            )

            # Subscribe to incoming trigger topic
            await client.subscribe(self._trigger_topic, qos=self._qos)
            self.logger.info("Subscribed to %s", self._trigger_topic)

            # Publish HA Auto Discovery once after connect
            if self._ha_discovery and self._app_config is not None:
                await self._publish_ha_discovery(client)

            self._ready.set()

            # Process incoming messages; publish calls happen concurrently via handle()
            async for message in client.messages:
                if not self._running:
                    break
                await self._process_message(message)

        self._client = None
        self._ready.clear()

    # ------------------------------------------------------------------
    # Incoming message handling (subscribe path)
    # ------------------------------------------------------------------

    async def _process_message(self, message) -> None:
        """Parse an incoming trigger message and invoke the pipeline callback."""
        try:
            raw_payload = message.payload.decode("utf-8")
            payload = json.loads(raw_payload)

            event = CallEvent(
                number=payload.get("number", ""),
                direction=CallDirection(payload.get("direction", "inbound")),
                event_type=CallEventType(payload.get("event_type", "ring")),
                source="mqtt",
                raw_input=raw_payload,
            )

            if self._callback and event.number:
                await self._callback(event)
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            self.logger.error("Failed to parse MQTT trigger message: %s", exc)

    # ------------------------------------------------------------------
    # Output: publish resolved events (publish path)
    # ------------------------------------------------------------------

    def _derive_msn(self, event: CallEvent) -> str | None:
        """Derive the short local MSN from the event direction.

        Inbound: the local MSN is called_number.
        Outbound: the local MSN is caller_number.

        Uses PBX reverse map (E.164 -> raw MSN) when available,
        otherwise falls back to ``pn.to_local()``.
        """
        if event.direction == CallDirection.INBOUND:
            e164 = event.called_number
        else:
            e164 = event.caller_number

        if not e164:
            return None

        # Prefer PBX authoritative reverse lookup
        if self._pbx is not None:
            short = self._pbx.e164_to_msn(e164)
            if short:
                return short

        # Fallback: strip country + area code via phone_number helper
        if self._app_config is not None:
            phone_cfg = self._app_config.phone
            return pn.to_local(
                e164,
                country_code=phone_cfg.country_code,
                local_area_code=phone_cfg.local_area_code,
            )

        return None

    async def handle_line_state_change(self, line_state: "LineState") -> None:
        """Publish line state immediately (before resolve).

        Publishes the line state without display names so subscribers get
        the state change with minimal latency. The subsequent handle() call
        will publish again with resolved display names.
        """
        if self._client is None:
            return

        current_status = line_state.status.value
        if current_status == self._last_line_status.get(line_state.line_id):
            return  # No change

        state_payload = json.dumps(_serialize_line_state(line_state))
        try:
            await self._client.publish(
                f"{self._topic_prefix}/line/{line_state.line_id}/state",
                state_payload,
                qos=self._qos,
                retain=True,
            )
            self.logger.debug(
                "MQTT line state (early): line/%d/state -> %s",
                line_state.line_id,
                current_status,
            )
        except Exception as exc:
            self.logger.error("Failed to publish early line state: %s", exc)

    async def handle(
        self,
        event: CallEvent,
        result: Optional[ResolveResult],
        *,
        line_state: Optional["LineState"] = None,
    ) -> None:
        """Publish call event, line state and trunk state over the shared connection."""
        if self._client is None:
            self.logger.debug(
                "MQTT not connected — dropping event for '%s'", event.number
            )
            return

        payload = {
            "number": event.number,
            "caller_number": event.caller_number,
            "called_number": event.called_number,
            "msn": self._derive_msn(event),
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

        # Derive display names from resolve result for the remote party
        caller_display: Optional[str] = None
        called_display: Optional[str] = None
        if line_state is not None and result is not None and result.name:
            if line_state.direction and line_state.direction.value == "inbound":
                caller_display = result.name
            else:
                called_display = result.name

        topic_base = self._topic_prefix
        message = json.dumps(payload)

        # Check if we have display names to enrich the line state with.
        # The early publish (handle_line_state_change) already sent the state
        # without display names, so we only re-publish if we can add them.
        has_display_names = caller_display is not None or called_display is not None

        # Update line status tracker (keeps handle_line_state_change in sync)
        if line_state is not None and line_state.line_id is not None:
            self._last_line_status[line_state.line_id] = line_state.status.value

        # Detect trunk state changes — use PbxStateManager for correct multi-line status
        trunk_changes: list[tuple[str, str]] = []  # [(trunk_id, status), ...]

        if self._pbx is not None:
            # Authoritative: check all trunks across all lines
            for trunk_info in self._pbx.get_trunk_status():
                t_id = trunk_info["id"]
                t_status = "busy" if trunk_info["busy"] else "idle"
                if t_status != self._last_trunk_status.get(t_id):
                    self._last_trunk_status[t_id] = t_status
                    trunk_changes.append((t_id, t_status))
        elif line_state is not None and line_state.trunk_id:
            # Fallback (no pbx reference): derive from the single line_state passed in
            t_id = line_state.trunk_id
            t_status = "idle" if line_state.status.value == "idle" else "busy"
            if t_status != self._last_trunk_status.get(t_id):
                self._last_trunk_status[t_id] = t_status
                trunk_changes.append((t_id, t_status))

        try:
            client = self._client
            if client is None:
                return

            await client.publish(
                f"{topic_base}/event", message, qos=self._qos, retain=self._retain
            )
            await client.publish(
                f"{topic_base}/event/{event.event_type.value}",
                message,
                qos=self._qos,
                retain=self._retain,
            )

            if has_display_names and line_state is not None:
                state_payload = json.dumps(
                    _serialize_line_state(line_state, caller_display, called_display)
                )
                await client.publish(
                    f"{topic_base}/line/{line_state.line_id}/state",
                    state_payload,
                    qos=self._qos,
                    retain=True,
                )
                self.logger.debug(
                    "MQTT line state (enriched): line/%d/state -> %s [%s]",
                    line_state.line_id,
                    line_state.status.value,
                    caller_display or called_display,
                )

            for t_id, t_status in trunk_changes:
                trunk_payload = json.dumps(
                    {
                        "trunk_id": t_id,
                        "status": t_status,
                        "line_id": line_state.line_id if line_state else None,
                        "last_changed": (
                            line_state.last_changed.isoformat()
                            if line_state is not None
                            and line_state.last_changed is not None
                            else event.timestamp.isoformat()
                        ),
                    }
                )
                await client.publish(
                    f"{topic_base}/trunk/{t_id}/state",
                    trunk_payload,
                    qos=self._qos,
                    retain=True,
                )
                self.logger.debug(
                    "MQTT trunk state: %s/trunk/%s/state -> %s",
                    topic_base,
                    t_id,
                    t_status,
                )

            self.logger.debug(
                "MQTT published for '%s' on %s/event", event.number, topic_base
            )

        except Exception as exc:
            self.logger.error("Failed to publish MQTT for '%s': %s", event.number, exc)
            self._client = None
            self._ready.clear()

    # ------------------------------------------------------------------
    # Home Assistant Auto Discovery
    # ------------------------------------------------------------------

    async def _publish_ha_discovery(self, client) -> None:
        """Publish HA MQTT Auto Discovery configs for lines and trunks."""
        if self._app_config is None:
            return

        prefix = self._topic_prefix
        ha_prefix = self._ha_discovery_prefix

        entity_prefix = (
            _slugify(self._ha_entity_id_prefix)
            if self._ha_entity_id_prefix
            else _slugify(prefix)
        )
        device_name = f"Phone Logger ({entity_prefix})"

        ha_device = {
            "identifiers": [entity_prefix],
            "name": device_name,
            "model": "phone-logger",
            "manufacturer": "phone-logger",
        }

        for trunk in self._app_config.pbx.trunks:
            trunk_slug = _slugify(trunk.id)
            unique_id = f"{entity_prefix}_trunk_{trunk_slug}"
            state_topic = f"{prefix}/trunk/{trunk.id}/state"
            config_topic = f"{ha_prefix}/sensor/{unique_id}/config"

            await client.publish(
                config_topic,
                json.dumps(
                    {
                        "name": f"Trunk {trunk.label or trunk.id}",
                        "unique_id": unique_id,
                        "object_id": unique_id,
                        "state_topic": state_topic,
                        "value_template": "{{ value_json.status }}",
                        "json_attributes_topic": state_topic,
                        "json_attributes_template": "{{ value_json | tojson }}",
                        "icon": "mdi:phone-outgoing",
                        "device": ha_device,
                        "availability_topic": f"{prefix}/status",
                        "payload_available": "online",
                        "payload_not_available": "offline",
                    }
                ),
                qos=self._qos,
                retain=True,
            )
            self.logger.debug("HA discovery published: %s", config_topic)

        for line_id, trunk in enumerate(self._app_config.pbx.trunks):
            unique_id = f"{entity_prefix}_line_{line_id}"
            state_topic = f"{prefix}/line/{line_id}/state"
            config_topic = f"{ha_prefix}/sensor/{unique_id}/config"

            await client.publish(
                config_topic,
                json.dumps(
                    {
                        "name": f"Line {line_id} ({trunk.label or trunk.id})",
                        "unique_id": unique_id,
                        "object_id": unique_id,
                        "state_topic": state_topic,
                        "value_template": "{{ value_json.status }}",
                        "json_attributes_topic": state_topic,
                        "json_attributes_template": "{{ value_json | tojson }}",
                        "icon": "mdi:phone",
                        "device": ha_device,
                        "availability_topic": f"{prefix}/status",
                        "payload_available": "online",
                        "payload_not_available": "offline",
                    }
                ),
                qos=self._qos,
                retain=True,
            )
            self.logger.debug("HA discovery published: %s", config_topic)

        self.logger.info(
            "HA MQTT Auto Discovery published: %d trunk(s), %d line(s)",
            len(self._app_config.pbx.trunks),
            len(self._app_config.pbx.trunks),
        )
