"""Call log output adapter - stores all call events and aggregated calls in SQLite."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from src.adapters.base import BaseOutputAdapter
from src.config import AdapterConfig
from src.core.event import CallDirection, CallEvent, CallEventType, ResolveResult
from src.core.utils import uuid7
from src.db.database import Database

if TYPE_CHECKING:
    from src.core.pbx import LineState

logger = logging.getLogger(__name__)


class CallLogOutputAdapter(BaseOutputAdapter):
    """
    Output adapter that logs all call events to the SQLite database.

    Maintains two tables:
    - call_log: raw events (ring/call/connect/disconnect) for audit
    - calls: aggregated per-call records with lifecycle tracking
    """

    def __init__(self, config: AdapterConfig, db: Database) -> None:
        super().__init__(config)
        self.db = db

    async def handle(
        self,
        event: CallEvent,
        result: Optional[ResolveResult],
        *,
        line_state: Optional["LineState"] = None,
    ) -> None:
        """Log raw event and maintain aggregated call record."""
        resolved_name = result.name if result else None
        source = result.source if result else None

        # 1. Always log raw event
        await self.db.log_call(
            number=event.number,
            direction=event.direction.value,
            event_type=event.event_type.value,
            resolved_name=resolved_name,
            source=source,
        )

        self.logger.debug(
            "Logged call: %s %s %s -> %s",
            event.direction.value,
            event.event_type.value,
            event.number,
            resolved_name or "unknown",
        )

        # 2. Aggregate into calls table (requires connection_id for correlation)
        if event.connection_id:
            try:
                await self._aggregate_call(event, resolved_name, line_state)
            except Exception:
                self.logger.exception(
                    "Failed to aggregate call for connection_id=%s", event.connection_id
                )

    async def _aggregate_call(
        self,
        event: CallEvent,
        resolved_name: Optional[str],
        line_state: Optional["LineState"],
    ) -> None:
        """Upsert aggregated call record based on event type."""
        connection_id = int(event.connection_id)  # type: ignore[arg-type]
        event_type = event.event_type
        now = datetime.now().isoformat()

        # Extract device info from the event (PBX-enriched) or line_state fallback
        device_info = event.device or (line_state.device if line_state else None)
        device_name = device_info.name if device_info else None
        device_type = (
            device_info.type if device_info else None
        )  # DeviceInfo.type is the type string

        # is_internal lives on line_state (set by PBX enrichment)
        is_internal = line_state.is_internal if line_state else False

        # Determine the local MSN (own number) based on direction
        if event.direction == CallDirection.INBOUND:
            msn = event.called_number  # inbound: we are the called party
        else:
            msn = event.caller_number  # outbound: we are the caller

        if event_type == CallEventType.RING:
            # New inbound call — create record
            await self.db.upsert_call(
                call_id=uuid7(),
                connection_id=connection_id,
                caller_number=event.caller_number or event.number,
                called_number=event.called_number or event.number,
                direction=event.direction.value,
                status="ringing",
                device=device_name,
                device_type=device_type,
                msn=msn,
                trunk_id=event.trunk_id,
                line_id=event.line_id,
                is_internal=is_internal,
                started_at=now,
                resolved_name=resolved_name,
            )

        elif event_type == CallEventType.CALL:
            # New outbound call — create record
            await self.db.upsert_call(
                call_id=uuid7(),
                connection_id=connection_id,
                caller_number=event.caller_number or event.number,
                called_number=event.called_number or event.number,
                direction=event.direction.value,
                status="dialing",
                device=device_name,
                device_type=device_type,
                msn=msn,
                trunk_id=event.trunk_id,
                line_id=event.line_id,
                is_internal=is_internal,
                started_at=now,
                resolved_name=resolved_name,
            )

        elif event_type == CallEventType.CONNECT:
            # Call answered — update existing record
            existing = await self.db.get_call_by_connection_id(connection_id)
            if existing:
                await self.db.upsert_call(
                    call_id=existing["id"],
                    connection_id=connection_id,
                    caller_number=existing["caller_number"],
                    called_number=existing["called_number"],
                    direction=existing["direction"],
                    status="answered",
                    device=device_name or existing.get("device"),
                    device_type=device_type or existing.get("device_type"),
                    msn=existing.get("msn"),
                    trunk_id=existing.get("trunk_id"),
                    line_id=existing.get("line_id"),
                    is_internal=existing.get("is_internal", False),
                    started_at=existing["started_at"],
                    connected_at=now,
                    resolved_name=resolved_name or existing.get("resolved_name"),
                )
            else:
                self.logger.warning(
                    "CONNECT for unknown connection_id=%d — no existing call record",
                    connection_id,
                )

        elif event_type == CallEventType.DISCONNECT:
            # Call ended — finalize existing record
            existing = await self.db.get_call_by_connection_id(connection_id)
            if existing:
                # Determine final status from previous status
                prev_status = existing["status"]
                if prev_status == "answered":
                    final_status = "answered"
                elif prev_status == "ringing":
                    final_status = "missed"
                elif prev_status == "dialing":
                    final_status = "notReached"
                else:
                    final_status = prev_status  # keep as-is if already terminal

                # Duration: from connect time if answered, else from start
                connected_at = existing.get("connected_at")
                if connected_at:
                    start_time = datetime.fromisoformat(connected_at)
                else:
                    start_time = datetime.fromisoformat(existing["started_at"])
                duration = max(
                    0, int((datetime.fromisoformat(now) - start_time).total_seconds())
                )

                await self.db.upsert_call(
                    call_id=existing["id"],
                    connection_id=connection_id,
                    caller_number=existing["caller_number"],
                    called_number=existing["called_number"],
                    direction=existing["direction"],
                    status=final_status,
                    device=existing.get("device"),
                    device_type=existing.get("device_type"),
                    msn=existing.get("msn"),
                    trunk_id=existing.get("trunk_id"),
                    line_id=existing.get("line_id"),
                    is_internal=existing.get("is_internal", False),
                    started_at=existing["started_at"],
                    connected_at=connected_at,
                    finished_at=now,
                    duration_seconds=duration,
                    resolved_name=existing.get("resolved_name"),
                )
            else:
                self.logger.warning(
                    "DISCONNECT for unknown connection_id=%d — no existing call record",
                    connection_id,
                )
