"""Fritz!Box Callmonitor input adapter - TCP listener on port 1012."""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Coroutine, Optional

from src.adapters.base import BaseInputAdapter
from src.config import AdapterConfig
from src.core.event import CallDirection, CallEvent, CallEventType

logger = logging.getLogger(__name__)

# Fritz!Box Callmonitor message format:
# DATE;EVENT;CONNECTION_ID;EXTENSION;NUMBER;CALLER_NUMBER;SIP_LINE
# Example: 15.03.26 10:15:00;RING;0;12;0123456789;987654321;SIP0
# Events: RING (inbound), CALL (outbound), CONNECT, DISCONNECT

EVENT_MAP = {
    "RING": CallEventType.RING,
    "CALL": CallEventType.CALL,
    "CONNECT": CallEventType.CONNECT,
    "DISCONNECT": CallEventType.DISCONNECT,
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
        self._callback: Optional[Callable[[CallEvent], Coroutine]] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._reconnect_delay = 5  # seconds

    async def start(self, callback: Callable[[CallEvent], Coroutine]) -> None:
        """Start listening for Fritz!Box Callmonitor events."""
        self._callback = callback
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self.logger.info("Fritz Callmonitor adapter started (target: %s:%d)", self.host, self.port)

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
        self.logger.info("Connecting to Fritz!Box Callmonitor at %s:%d", self.host, self.port)

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
            event = self._parse_line(line)
            if event and self._callback:
                await self._callback(event)
        except Exception:
            self.logger.exception("Failed to parse Fritz Callmonitor line: %s", line)

    @staticmethod
    def _parse_line(line: str) -> Optional[CallEvent]:
        """
        Parse a Fritz!Box Callmonitor line into a CallEvent.

        Format varies by event type:
        RING:       date;RING;conn_id;caller_number;called_number;SIP
        CALL:       date;CALL;conn_id;extension;called_number;caller_number;SIP
        CONNECT:    date;CONNECT;conn_id;extension;number
        DISCONNECT: date;DISCONNECT;conn_id;duration
        """
        parts = line.split(";")
        if len(parts) < 4:
            return None

        timestamp_str = parts[0].strip()
        event_name = parts[1].strip().upper()
        connection_id = parts[2].strip()

        event_type = EVENT_MAP.get(event_name)
        if not event_type:
            return None

        try:
            timestamp = datetime.strptime(timestamp_str, "%d.%m.%y %H:%M:%S")
        except ValueError:
            timestamp = datetime.now()

        number = ""
        direction = CallDirection.INBOUND
        extension = None

        if event_type == CallEventType.RING:
            # RING: date;RING;conn_id;caller_number;called_number;SIP
            number = parts[3].strip() if len(parts) > 3 else ""
            extension = parts[4].strip() if len(parts) > 4 else None
            direction = CallDirection.INBOUND

        elif event_type == CallEventType.CALL:
            # CALL: date;CALL;conn_id;extension;called_number;caller_number;SIP
            extension = parts[3].strip() if len(parts) > 3 else None
            number = parts[4].strip() if len(parts) > 4 else ""
            direction = CallDirection.OUTBOUND

        elif event_type == CallEventType.CONNECT:
            # CONNECT: date;CONNECT;conn_id;extension;number
            extension = parts[3].strip() if len(parts) > 3 else None
            number = parts[4].strip() if len(parts) > 4 else ""

        elif event_type == CallEventType.DISCONNECT:
            # DISCONNECT: date;DISCONNECT;conn_id;duration
            # No number in disconnect, but we need the connection_id for correlation
            number = ""

        if not number and event_type not in (CallEventType.CONNECT, CallEventType.DISCONNECT):
            return None

        return CallEvent(
            number=number,
            direction=direction,
            event_type=event_type,
            timestamp=timestamp,
            source="fritz",
            connection_id=connection_id,
            extension=extension,
            raw_number=number,
        )
