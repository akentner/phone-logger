"""Webhook output adapter - sends events via HTTP POST to configured URLs."""

import logging
from typing import TYPE_CHECKING, Optional

import aiohttp

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


def _matches_filter(
    filter_value: str, event: CallEvent, line_state: Optional["LineState"]
) -> bool:
    """
    Check whether an event/state matches a single filter entry.

    Filter format:
      "ring"           → matches CallEventType.ring
      "call"           → matches CallEventType.call
      "connect"        → matches CallEventType.connect
      "disconnect"     → matches CallEventType.disconnect
      "state:talking"  → matches LineStatus.talking on the associated line
      "state:missed"   → matches LineStatus.missed
      "state:finished" → matches LineStatus.finished
      etc.
    """
    if filter_value.startswith("state:"):
        state_name = filter_value[len("state:") :]
        if line_state is None:
            return False
        return line_state.status.value == state_name
    else:
        return event.event_type.value == filter_value


class WebhookOutputAdapter(BaseOutputAdapter):
    """
    Output adapter that sends call events via HTTP POST to a webhook URL.

    Sends a POST request with call event data to the configured webhook URL.
    Supports multiple independent webhook instances, each with its own URL and event filters.

    The ``events`` config list accepts:
    - Raw event types: ``ring``, ``call``, ``connect``, ``disconnect``
    - FSM line states with ``state:`` prefix: ``state:talking``, ``state:missed``,
      ``state:finished``, ``state:notReached``, ``state:idle``

    Example config::

        events:
          - ring
          - state:talking
          - state:missed
          - state:finished
    """

    def __init__(self, config: AdapterConfig) -> None:
        super().__init__(config)
        self._url = config.config.get("url", "")
        self._token = config.config.get("token", "")
        self._events: list[str] = config.config.get(
            "events", ["ring", "call", "connect", "disconnect"]
        )
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
        self.logger.info("Webhook adapter started (URL: %s)", self._url)

    async def stop(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def handle(
        self,
        event: CallEvent,
        result: Optional[ResolveResult],
        *,
        line_state: Optional["LineState"] = None,
    ) -> None:
        """Send call event to webhook if it matches the configured event filter."""
        if not self._url:
            self.logger.debug("No webhook URL configured, skipping")
            return

        # Check if any configured filter matches
        matched = any(_matches_filter(f, event, line_state) for f in self._events)
        if not matched:
            self.logger.debug(
                "Event '%s' / state '%s' not in configured filters, skipping",
                event.event_type.value,
                line_state.status.value if line_state else "n/a",
            )
            return

        if not self._session:
            self.logger.error("HTTP session not initialized")
            return

        payload = {
            "number": event.number,
            "caller_number": event.caller_number,
            "called_number": event.called_number,
            "direction": event.direction.value,
            "event_type": event.event_type.value,
            "line_id": event.line_id,
            "trunk_id": event.trunk_id,
            "device": (
                {
                    "id": event.device.id,
                    "name": event.device.name,
                    "type": event.device.type,
                }
                if event.device
                else None
            ),
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

        try:
            async with self._session.post(self._url, json=payload) as response:
                if response.status < 300:
                    self.logger.debug(
                        "Webhook sent successfully for '%s'", event.number
                    )
                else:
                    self.logger.warning(
                        "Webhook returned %d for '%s'", response.status, event.number
                    )
        except aiohttp.ClientError as e:
            self.logger.error("Failed to send webhook for '%s': %s", event.number, e)
