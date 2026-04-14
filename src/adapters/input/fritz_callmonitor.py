"""Fritz!Box Callmonitor input adapter - TCP listener on port 1012."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Callable, Coroutine, Optional
from zoneinfo import ZoneInfo

from src.adapters.base import BaseInputAdapter
from src.config import AdapterConfig
from src.core.event import CallDirection, CallEvent, CallEventType

logger = logging.getLogger(__name__)

# Fritz!Box Callmonitor message format:
# DATE;EVENT;CONNECTION_ID;EXTENSION;NUMBER;CALLER_NUMBER;SIP_LINE
# Example: 15.03.26 10:15:00;RING;0;12;0123456789;987654321;SIP0
# Events: RING (inbound), CALL (outbound), CONNECT, DISCONNECT

ANONYMOUS = "anonymous"  # Sentinel for withheld/unavailable caller numbers

EVENT_MAP = {
    "RING": CallEventType.RING,
    "CALL": CallEventType.CALL,
    "CONNECT": CallEventType.CONNECT,
    "DISCONNECT": CallEventType.DISCONNECT,
}

# Minimum required field count per event type (including date field at index 0).
# RING:       date;RING;conn;caller;called             -> 5
# CALL:       date;CALL;conn;ext;caller;called         -> 6
# CONNECT:    date;CONNECT;conn;ext;number             -> 5
# DISCONNECT: date;DISCONNECT;conn;duration            -> 4
MIN_FIELDS: dict[CallEventType, int] = {
    CallEventType.RING: 5,
    CallEventType.CALL: 6,
    CallEventType.CONNECT: 5,
    CallEventType.DISCONNECT: 4,
}


class FritzCallmonitorAdapter(BaseInputAdapter):
    """
    Connects to Fritz!Box Callmonitor via TCP and parses call events.

    Requires Callmonitor to be enabled on Fritz!Box (dial #96*5*).
    """

    def __init__(self, config: AdapterConfig) -> None:
        super().__init__(config)
        self.host = config.config.get("host", "192.168.178.1")
        self.port = config.config.get("port", 1012)
        self._timezone = ZoneInfo(config.config.get("timezone", "Europe/Berlin"))
        self._callback: Optional[Callable[[CallEvent], Coroutine]] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._reconnect_delay = config.config.get("reconnect_delay", 10)

    async def start(self, callback: Callable[[CallEvent], Coroutine]) -> None:
        """Start listening for Fritz!Box Callmonitor events."""
        self._callback = callback
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self.logger.info(
            "Fritz Callmonitor adapter started (target: %s:%d)", self.host, self.port
        )

    async def stop(self) -> None:
        """Stop listening and disconnect."""
        self._running = False
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("Fritz Callmonitor adapter stopped")

    async def _run_loop(self) -> None:
        """Main loop with automatic reconnection."""
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Fritz Callmonitor connection error")

            if self._running:
                self.logger.info(
                    "Reconnecting to Fritz Callmonitor in %d seconds...",
                    self._reconnect_delay,
                )
                await asyncio.sleep(self._reconnect_delay)

    async def _connect_and_listen(self) -> None:
        """Connect to Fritz!Box and listen for events."""
        self.logger.info(
            "Connecting to Fritz!Box Callmonitor at %s:%d", self.host, self.port
        )

        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        self.logger.info("Connected to Fritz!Box Callmonitor")

        while self._running:
            line = await self._reader.readline()
            if not line:
                self.logger.warning("Fritz!Box Callmonitor connection closed")
                break

            decoded = line.decode("utf-8", errors="replace").strip()
            if decoded:
                await self._process_line(decoded)

    async def _process_line(self, line: str) -> None:
        """Parse a single line from the Fritz!Box Callmonitor."""
        self.logger.debug("Fritz raw: %s", line)

        try:
            event = self._parse_line(line, tz=self._timezone)
            if event and self._callback:
                event = event.model_copy(update={"raw_input": line})
                await self._callback(event)
        except Exception:
            self.logger.exception("Failed to parse Fritz Callmonitor line: %s", line)

    @staticmethod
    def _parse_line(line: str, tz: Optional[ZoneInfo] = None) -> Optional[CallEvent]:
        """
        Parse a Fritz!Box Callmonitor line into a CallEvent.

        Format varies by event type:
        RING:       date;RING;conn_id;caller_number;called_number;SIP
        CALL:       date;CALL;conn_id;extension;caller_number;called_number;SIP
        CONNECT:    date;CONNECT;conn_id;extension;number
        DISCONNECT: date;DISCONNECT;conn_id;duration

        Args:
            line: Raw TCP line from Fritz!Box Callmonitor.
            tz: Local timezone for parsing the Fritz!Box timestamp. If None,
                defaults to UTC (timestamps will be off by UTC offset).
        """
        parts = line.split(";")
        if len(parts) < 4:
            return None

        timestamp_str = parts[0].strip()
        event_name = parts[1].strip().upper()
        connection_id = parts[2].strip()

        event_type = EVENT_MAP.get(event_name)
        if not event_type:
            logger.debug("Unknown Fritz event type '%s' | raw: %s", event_name, line)
            return None

        if len(parts) < MIN_FIELDS[event_type]:
            logger.warning(
                "Fritz parse error [%s]: need %d fields, got %d | raw: %s",
                event_type.value,
                MIN_FIELDS[event_type],
                len(parts),
                line,
            )
            return None

        try:
            local_tz = tz or UTC
            naive_dt = datetime.strptime(timestamp_str, "%d.%m.%y %H:%M:%S")
            timestamp = naive_dt.replace(tzinfo=local_tz).astimezone(UTC)
        except ValueError:
            timestamp = datetime.now(UTC)

        number = ""
        direction = CallDirection.INBOUND
        extension = None
        trunk_id = None
        caller_number = None
        called_number = None

        if event_type == CallEventType.RING:
            # RING: date;RING;conn_id;caller_number;called_number;SIP
            caller_number = parts[3].strip() if len(parts) > 3 else ""
            called_number = parts[4].strip() if len(parts) > 4 else None
            trunk_id = parts[5].strip() if len(parts) > 5 else None
            # Empty caller = withheld/anonymous number
            number = caller_number if caller_number else ANONYMOUS
            extension = called_number  # local MSN (used for device/MSN lookup)
            direction = CallDirection.INBOUND

        elif event_type == CallEventType.CALL:
            # CALL: date;CALL;conn_id;extension;caller_number;called_number;SIP
            extension = parts[3].strip() if len(parts) > 3 else None
            caller_number = parts[4].strip() if len(parts) > 4 else None
            called_number = parts[5].strip() if len(parts) > 5 else ""
            trunk_id = parts[6].strip() if len(parts) > 6 else None
            # Remote party for outbound = the called number
            number = called_number if called_number else ANONYMOUS
            direction = CallDirection.OUTBOUND

        elif event_type == CallEventType.CONNECT:
            # CONNECT: date;CONNECT;conn_id;extension;number
            extension = parts[3].strip() if len(parts) > 3 else None
            number = parts[4].strip() if len(parts) > 4 else ""

        elif event_type == CallEventType.DISCONNECT:
            # DISCONNECT: date;DISCONNECT;conn_id;duration
            # No number in disconnect, but we need the connection_id for correlation
            number = ""

        return CallEvent(
            number=number,
            direction=direction,
            event_type=event_type,
            timestamp=timestamp,
            source="fritz_callmonitor",
            connection_id=connection_id,
            extension=extension,
            raw_number=caller_number if event_type == CallEventType.RING else number,
            caller_number=caller_number
            if caller_number
            else (ANONYMOUS if event_type == CallEventType.RING else None),
            called_number=called_number or None,
            trunk_id=trunk_id,
        )
