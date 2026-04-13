"""PBX state management with per-line FSM and event enrichment."""

import asyncio
import logging
from datetime import UTC, datetime
from enum import Enum
from collections.abc import Awaitable, Callable
from typing import Optional

from pydantic import BaseModel

from src.config import DeviceConfig, PbxConfig, PhoneConfig
from src.core import phone_number as pn
from src.core.event import CallDirection, CallEvent, CallEventType, DeviceInfo

logger = logging.getLogger(__name__)


class LineStatus(str, Enum):
    """FSM states for a PBX line."""

    IDLE = "idle"
    RING = "ring"
    CALL = "call"
    TALKING = "talking"
    FINISHED = "finished"
    MISSED = "missed"
    NOT_REACHED = "notReached"


# Terminal states that auto-reset to IDLE after a delay
TERMINAL_STATES = {LineStatus.FINISHED, LineStatus.MISSED, LineStatus.NOT_REACHED}


class LineState(BaseModel):
    """Current state of a PBX line."""

    line_id: int
    status: LineStatus = LineStatus.IDLE
    connection_id: Optional[str] = None
    caller_number: Optional[str] = None
    called_number: Optional[str] = None
    direction: Optional[CallDirection] = None
    trunk_id: Optional[str] = None
    caller_device: Optional[DeviceInfo] = None
    called_device: Optional[DeviceInfo] = None
    is_internal: bool = False
    last_changed: Optional[datetime] = None

    model_config = {"arbitrary_types_allowed": True}


class LineFSM:
    """
    Finite state machine for a single PBX line.

    Valid transitions:
        idle -> ring (RING)       idle -> call (CALL)
        ring -> talking (CONNECT) call -> talking (CONNECT)
        ring -> missed (DISCONNECT without CONNECT)
        call -> notReached (DISCONNECT without CONNECT)
        talking -> finished (DISCONNECT after CONNECT)

    Invalid transitions reset to idle immediately (fault-tolerant).
    Terminal states (finished, missed, notReached) auto-reset to idle after 1s.
    """

    VALID_TRANSITIONS: dict[LineStatus, dict[CallEventType, LineStatus]] = {
        LineStatus.IDLE: {
            CallEventType.RING: LineStatus.RING,
            CallEventType.CALL: LineStatus.CALL,
        },
        LineStatus.RING: {
            CallEventType.CONNECT: LineStatus.TALKING,
            CallEventType.DISCONNECT: LineStatus.MISSED,
        },
        LineStatus.CALL: {
            CallEventType.CONNECT: LineStatus.TALKING,
            CallEventType.DISCONNECT: LineStatus.NOT_REACHED,
        },
        LineStatus.TALKING: {
            CallEventType.DISCONNECT: LineStatus.FINISHED,
        },
        # Terminal states accept no events
        LineStatus.FINISHED: {},
        LineStatus.MISSED: {},
        LineStatus.NOT_REACHED: {},
    }

    def __init__(self, line_id: int) -> None:
        self.line_id = line_id
        self._status = LineStatus.IDLE
        self._connected = False

    @property
    def status(self) -> LineStatus:
        return self._status

    def transition(self, event_type: CallEventType) -> LineStatus:
        """
        Attempt a state transition for the given event type.

        Returns the new status. On invalid transition, resets to IDLE.
        """
        valid = self.VALID_TRANSITIONS.get(self._status, {})
        new_status = valid.get(event_type)

        if new_status is None:
            # Invalid transition — fault-tolerant reset
            logger.warning(
                "Line %d: invalid transition %s + %s → reset to idle",
                self.line_id,
                self._status.value,
                event_type.value,
            )
            self._status = LineStatus.IDLE
            self._connected = False

            # Retry the transition from idle
            valid = self.VALID_TRANSITIONS.get(LineStatus.IDLE, {})
            new_status = valid.get(event_type)
            if new_status is None:
                return self._status
            # Fall through to apply the retried transition

        if new_status == LineStatus.TALKING:
            self._connected = True

        self._status = new_status
        return self._status

    def reset(self) -> None:
        """Reset the FSM to idle."""
        self._status = LineStatus.IDLE
        self._connected = False


class PbxStateManager:
    """
    Manages PBX infrastructure state: line FSMs, event enrichment, live status.

    Initialized from PbxConfig (static) + PhoneConfig (for MSN→E.164 resolution).
    Line state is kept in RAM only (no DB persistence).
    """

    def __init__(
        self,
        config: PbxConfig,
        phone_config: PhoneConfig,
        on_state_change: Optional[Callable[[int, "LineState"], Awaitable[None]]] = None,
    ) -> None:
        self._config = config
        self._phone_config = phone_config
        self._on_state_change = on_state_change

        # Build lookup structures
        # Fritz!Box Callmonitor sends the numeric device ID (e.g. "10"), not the
        # dial string extension (e.g. "**610"). Keep both dicts for flexibility.
        self._devices_by_id: dict[str, DeviceConfig] = {d.id: d for d in config.devices}
        self._devices_by_ext: dict[str, DeviceConfig] = {
            d.extension: d for d in config.devices
        }

        # Pre-compute MSN E.164 set for internal call detection
        self._msn_e164_set: set[str] = set()
        self._msn_e164_map: dict[str, str] = {}  # raw msn -> E.164
        for msn in config.msns:
            e164 = self._msn_to_e164(msn.number)
            self._msn_e164_set.add(e164)
            self._msn_e164_map[msn.number] = e164

        # Initialize line FSMs and states — one line per trunk (0-indexed)
        self._fsms: dict[int, LineFSM] = {}
        self._states: dict[int, LineState] = {}
        for i in range(len(config.trunks)):
            self._fsms[i] = LineFSM(i)
            self._states[i] = LineState(line_id=i)

        # Pending auto-reset tasks for terminal states
        self._reset_tasks: dict[int, asyncio.Task] = {}

        logger.info(
            "PBX initialized: %d lines, %d trunks, %d MSNs, %d devices",
            len(config.trunks),
            len(config.trunks),
            len(config.msns),
            len(config.devices),
        )

    def _msn_to_e164(self, msn: str) -> str:
        """Convert a raw MSN number to E.164 using PhoneConfig."""
        # MSN + local_area_code + country_code → E.164
        # e.g. "123456" + area "30" + country "49" → "+4930123456"
        if self._phone_config.local_area_code:
            national = f"0{self._phone_config.local_area_code}{msn}"
        else:
            national = msn
        return pn.normalize(
            national,
            country_code=self._phone_config.country_code,
            local_area_code=self._phone_config.local_area_code,
        )

    def _lookup_device_by_id(self, device_id: str | None) -> DeviceInfo | None:
        """Look up a device by its Fritz!Box numeric ID (e.g. '10')."""
        if not device_id:
            return None
        device_cfg = self._devices_by_id.get(device_id)
        if not device_cfg:
            return None
        return DeviceInfo(
            id=device_cfg.id,
            extension=device_cfg.extension,
            name=device_cfg.name,
            type=device_cfg.type.value,
        )

    def _lookup_device(self, extension: str | None) -> DeviceInfo | None:
        """Look up a device by its dial string extension (e.g. '**610')."""
        if not extension:
            return None
        device_cfg = self._devices_by_ext.get(extension)
        if not device_cfg:
            return None
        return DeviceInfo(
            id=device_cfg.id,
            extension=device_cfg.extension,
            name=device_cfg.name,
            type=device_cfg.type.value,
        )

    def _is_internal(self, caller: str | None, called: str | None) -> bool:
        """Check if both numbers are configured MSNs (internal call)."""
        if not caller or not called:
            return False
        return caller in self._msn_e164_set and called in self._msn_e164_set

    def enrich_event(self, event: CallEvent) -> CallEvent:
        """
        Enrich a CallEvent with PBX information before state update.

        Sets: line_id, caller_device, called_device, caller_number, called_number.
        trunk_id is expected to be set by the input adapter already.

        The Fritz!Box Callmonitor sends the numeric device ID in the 'extension'
        field (e.g. "10" for the device with id="10", extension="**610", name="EG 24").
        """
        updates: dict = {}

        # line_id from connection_id
        if event.connection_id is not None:
            try:
                updates["line_id"] = int(event.connection_id)
            except (ValueError, TypeError):
                pass

        # Device lookup from Fritz!Box numeric extension ID
        device = self._lookup_device_by_id(event.extension)

        # Set caller_number / called_number and assign device to the right party
        if event.event_type == CallEventType.RING:
            # RING: number = caller (remote), extension = called MSN (not a device ID)
            updates["caller_number"] = event.number
            # For RING, extension contains the local MSN, not a device ID
            if event.extension and not device:
                called_e164 = self._try_resolve_msn(event.extension)
                if called_e164:
                    updates["called_number"] = called_e164
            # No device known at RING time (caller is external, called device not yet known)

        elif event.event_type == CallEventType.CALL:
            # CALL (outbound): extension = device ID of the calling device
            updates["called_number"] = event.number
            if event.extension:
                caller_e164 = self._try_resolve_msn(event.extension)
                if caller_e164:
                    updates["caller_number"] = caller_e164
            if device:
                updates["caller_device"] = (
                    device  # outbound: local device is the caller
                )

        elif event.event_type == CallEventType.CONNECT:
            # CONNECT: extension = device ID of the device that answered/connected.
            # Fritz!Box does NOT include direction in the CONNECT message, so
            # event.direction defaults to INBOUND and cannot be trusted here.
            # Instead, look up the stored LineState to get the actual direction.
            if device:
                line_id = updates.get("line_id") or (
                    int(event.connection_id)
                    if event.connection_id is not None
                    else None
                )
                existing_state = (
                    self._states.get(line_id) if line_id is not None else None
                )
                actual_direction = (
                    existing_state.direction
                    if existing_state and existing_state.direction is not None
                    else event.direction
                )
                # For inbound calls the answering device is the called party;
                # for outbound it is the caller (already set at CALL time).
                if actual_direction == CallDirection.INBOUND:
                    updates["called_device"] = device
                else:
                    updates["caller_device"] = device

        if updates:
            event = event.model_copy(update=updates)

        return event

    def _try_resolve_msn(self, value: str) -> str | None:
        """Try to resolve a value as an MSN to E.164. Returns None if not a known MSN."""
        # Direct match in MSN map
        if value in self._msn_e164_map:
            return self._msn_e164_map[value]
        # Try normalizing and checking against the set
        normalized = pn.normalize(
            value,
            country_code=self._phone_config.country_code,
            local_area_code=self._phone_config.local_area_code,
        )
        if normalized in self._msn_e164_set:
            return normalized
        return None

    def update_state(self, event: CallEvent) -> None:
        """
        Update the FSM state for the line affected by this event.

        Must be called after enrich_event().
        """
        line_id = event.line_id
        if line_id is None:
            return

        fsm = self._fsms.get(line_id)
        state = self._states.get(line_id)
        if not fsm or not state:
            # Unknown line — could be an unconfigured line
            logger.debug("Event for unconfigured line %d, ignoring PBX state", line_id)
            return

        # Cancel any pending reset task for this line
        self._cancel_reset(line_id)

        # Execute FSM transition
        new_status = fsm.transition(event.event_type)

        # Update line state
        if new_status == LineStatus.IDLE:
            # FSM was reset (invalid transition) — clear state
            self._clear_line_state(line_id)
            return

        # Populate state on initial events (RING/CALL)
        if new_status in (LineStatus.RING, LineStatus.CALL):
            state.status = new_status
            state.connection_id = event.connection_id
            state.caller_number = event.caller_number
            state.called_number = event.called_number
            state.direction = event.direction
            state.trunk_id = event.trunk_id
            state.caller_device = event.caller_device
            state.called_device = event.called_device
            state.is_internal = self._is_internal(
                event.caller_number, event.called_number
            )
            state.last_changed = event.timestamp
        elif new_status == LineStatus.TALKING:
            # On CONNECT we may learn the answering device — update if provided
            state.status = new_status
            state.last_changed = event.timestamp
            if event.caller_device:
                state.caller_device = event.caller_device
            if event.called_device:
                state.called_device = event.called_device
        else:
            # FINISHED, MISSED, NOT_REACHED — just update status
            state.status = new_status
            state.last_changed = event.timestamp

        # Schedule auto-reset for terminal states
        if new_status in TERMINAL_STATES:
            self._schedule_reset(line_id)

    def _clear_line_state(self, line_id: int) -> None:
        """Reset a line state to idle defaults."""
        self._states[line_id] = LineState(line_id=line_id)
        self._fsms[line_id].reset()

    def _schedule_reset(self, line_id: int) -> None:
        """Schedule an auto-reset to idle after 1 second."""
        self._cancel_reset(line_id)

        async def _reset_after_delay():
            await asyncio.sleep(1.0)
            self._clear_line_state(line_id)
            self._reset_tasks.pop(line_id, None)
            logger.debug("Line %d auto-reset to idle", line_id)
            # Notify callback about the idle transition
            if self._on_state_change:
                idle_state = self._states.get(line_id)
                if idle_state:
                    # Stamp when the line became idle
                    idle_state.last_changed = datetime.now(UTC)
                    try:
                        await self._on_state_change(line_id, idle_state)
                    except Exception:
                        logger.exception(
                            "on_state_change callback failed for line %d", line_id
                        )

        try:
            loop = asyncio.get_running_loop()
            self._reset_tasks[line_id] = loop.create_task(_reset_after_delay())
        except RuntimeError:
            # No running event loop (e.g. in tests or sync context).
            # Terminal state remains visible until next event triggers a reset.
            logger.debug(
                "Line %d in terminal state (no event loop for auto-reset)", line_id
            )

    def _cancel_reset(self, line_id: int) -> None:
        """Cancel a pending auto-reset task."""
        task = self._reset_tasks.pop(line_id, None)
        if task and not task.done():
            task.cancel()

    # --- Public query methods ---

    def get_line_states(self) -> list[LineState]:
        """Get the current state of all configured lines."""
        return list(self._states.values())

    def get_line_state(self, line_id: int) -> LineState | None:
        """Get the current state of a specific line."""
        return self._states.get(line_id)

    def get_trunk_status(self) -> list[dict]:
        """Get all trunks with their current busy/idle status."""
        busy_trunks: set[str] = set()
        for state in self._states.values():
            if state.status not in (LineStatus.IDLE,) and state.trunk_id:
                busy_trunks.add(state.trunk_id)

        return [
            {
                "id": trunk.id,
                "type": trunk.type.value,
                "label": trunk.label,
                "busy": trunk.id in busy_trunks,
            }
            for trunk in self._config.trunks
        ]

    def get_msns_e164(self) -> list[dict]:
        """Get all configured MSNs with their E.164 representation."""
        return [
            {
                "number": msn.number,
                "e164": self._msn_e164_map.get(msn.number, ""),
                "label": msn.label,
            }
            for msn in self._config.msns
        ]

    def get_devices(self) -> list[DeviceConfig]:
        """Get all configured devices."""
        return list(self._config.devices)

    def get_status(self) -> dict:
        """Get a full PBX status snapshot."""
        return {
            "lines": [state.model_dump() for state in self._states.values()],
            "trunks": self.get_trunk_status(),
            "msns": self.get_msns_e164(),
            "devices": [d.model_dump() for d in self._config.devices],
        }

    def e164_to_msn(self, e164: str) -> str | None:
        """Reverse-lookup: convert an E.164 number to the short MSN, or None."""
        for raw_msn, mapped_e164 in self._msn_e164_map.items():
            if mapped_e164 == e164:
                return raw_msn
        return None
