"""Pipeline orchestration: Input -> Resolve -> Output."""

import logging
from typing import Optional

from src.adapters.base import BaseInputAdapter, BaseOutputAdapter
from src.adapters.resolver.chain import ResolverChain
from src.config import AdapterConfig, AppConfig
from src.core import phone_number as pn
from src.core.event import (
    CallDirection,
    CallEvent,
    CallEventType,
    PipelineResult,
    ResolveResult,
)
from src.core.pbx import LineState, PbxStateManager

ANONYMOUS = "anonymous"
ANONYMOUS_RESULT = ResolveResult(name="Anonym", number=ANONYMOUS, source="system")
from src.db.database import Database

# Import all adapter implementations
from src.adapters.input.fritz_callmonitor import FritzCallmonitorAdapter
from src.adapters.input.rest import RestInputAdapter
from src.adapters.mqtt import MqttAdapter
from src.adapters.resolver.json_file import JsonFileResolver
from src.adapters.resolver.sqlite_db import SqliteResolver
from src.adapters.resolver.tellows import TellowsResolver
from src.adapters.resolver.dastelefon import DasTelefonbuchResolver
from src.adapters.resolver.klartelbuch import KlarTelefonbuchResolver
from src.adapters.resolver.msn import MsnResolver
from src.adapters.output.call_log import CallLogOutputAdapter
from src.adapters.output.webhook import WebhookOutputAdapter

logger = logging.getLogger(__name__)


class Pipeline:
    """
    Main pipeline orchestrating Input -> Resolve -> Output flow.

    Manages lifecycle of all adapters and routes events through the system.
    """

    def __init__(self, config: AppConfig, db: Database) -> None:
        self.config = config
        self.db = db
        self.resolver_chain = ResolverChain()
        self.pbx = PbxStateManager(
            config.pbx, config.phone, on_state_change=self._on_line_idle
        )
        self._input_adapters: list[BaseInputAdapter] = []
        self._output_adapters: list[BaseOutputAdapter] = []
        self._rest_input: Optional[RestInputAdapter] = None
        self._mqtt_adapters: dict[str, MqttAdapter] = {}
        self._resolve_cache: dict[
            int, ResolveResult
        ] = {}  # Cache per line_id for CONNECT/DISCONNECT

    @property
    def rest_input(self) -> Optional[RestInputAdapter]:
        """Get the REST input adapter for API trigger."""
        return self._rest_input

    async def setup(self) -> None:
        """Initialize all adapters based on configuration."""
        self._setup_resolver_adapters()
        self._setup_input_adapters()
        self._setup_output_adapters()
        logger.info(
            "Pipeline setup complete: %d input, %d resolver, %d output adapters",
            len(self._input_adapters),
            len(self.resolver_chain.adapters),
            len(self._output_adapters),
        )

    async def start(self) -> None:
        """Start all adapters."""
        # Start resolver chain first
        await self.resolver_chain.start()

        # Start output adapters
        for adapter in self._output_adapters:
            try:
                await adapter.start()
            except Exception:
                logger.exception("Failed to start output adapter '%s'", adapter.name)

        # Start input adapters last (they trigger events)
        for adapter in self._input_adapters:
            try:
                await adapter.start(self._on_event)
            except Exception:
                logger.exception("Failed to start input adapter '%s'", adapter.name)

        logger.info("Pipeline started")

    async def stop(self) -> None:
        """Stop all adapters in reverse order."""
        # Stop input adapters first
        for adapter in self._input_adapters:
            try:
                await adapter.stop()
            except Exception:
                logger.exception("Failed to stop input adapter '%s'", adapter.name)

        # Stop output adapters
        for adapter in self._output_adapters:
            try:
                await adapter.stop()
            except Exception:
                logger.exception("Failed to stop output adapter '%s'", adapter.name)

        # Stop resolver chain last
        await self.resolver_chain.stop()

        logger.info("Pipeline stopped")

    def normalize(self, number: str) -> str:
        """Normalize a phone number to E.164 using configured country/area code."""
        return pn.normalize(
            number,
            country_code=self.config.phone.country_code,
            local_area_code=self.config.phone.local_area_code,
        )

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Resolve a phone number through the chain (for direct API calls)."""
        normalized = self.normalize(number)
        if normalized == ANONYMOUS:
            return ANONYMOUS_RESULT
        return await self.resolver_chain.resolve(normalized)

    async def _on_event(self, event: CallEvent) -> None:
        """
        Handle an incoming call event.

        Processing order:
        0. Persist raw event to DB
        1. Normalize phone number to E.164
        2. Enrich with PBX info (line, device, caller/called numbers)
        3. Update PBX line state (FSM transition)
        4. Enrich event from LineState (CONNECT/DISCONNECT)
        5. Resolve phone number (only RING/CALL events) + cache result
        6. Lookup cached result (CONNECT/DISCONNECT)
        7. Look up current line state
        8. Dispatch to output adapters
        9. Cleanup resolve cache on terminal states
        """
        # 0. Persist raw event before any processing/mutation
        try:
            await self.db.log_raw_event(
                source=event.source,
                raw_input=event.raw_input,
                raw_event_json=event.model_dump_json(),
                timestamp=event.timestamp.isoformat(),
            )
        except Exception:
            logger.exception("Failed to log raw event to DB")

        # 1. Normalize number fields to E.164
        norm_updates: dict = {}
        if event.number:
            normalized = self.normalize(event.number)
            if normalized != event.number:
                logger.debug("Normalized number: %r -> %r", event.number, normalized)
            norm_updates["number"] = normalized
        if event.caller_number and event.caller_number != ANONYMOUS:
            normalized_caller = self.normalize(event.caller_number)
            if normalized_caller != event.caller_number:
                logger.debug(
                    "Normalized caller_number: %r -> %r",
                    event.caller_number,
                    normalized_caller,
                )
            norm_updates["caller_number"] = normalized_caller
        if event.called_number and event.called_number != ANONYMOUS:
            normalized_called = self.normalize(event.called_number)
            if normalized_called != event.called_number:
                logger.debug(
                    "Normalized called_number: %r -> %r",
                    event.called_number,
                    normalized_called,
                )
            norm_updates["called_number"] = normalized_called
        if norm_updates:
            event = event.model_copy(update=norm_updates)

        # 2. Enrich with PBX information
        event = self.pbx.enrich_event(event)

        # 3. Update PBX line state
        self.pbx.update_state(event)

        logger.info(
            "Event received: %s %s %s (source: %s, line: %s)",
            event.direction.value,
            event.event_type.value,
            event.number,
            event.source,
            event.line_id,
        )

        # 3b. Notify output adapters of line state change (before resolve)
        if event.line_id is not None:
            line_state_early = self.pbx.get_line_state(event.line_id)
            if line_state_early is not None:
                for adapter in self._output_adapters:
                    try:
                        await adapter.handle_line_state_change(line_state_early)
                    except Exception:
                        logger.exception(
                            "Output adapter '%s' failed for line state change on line %d",
                            adapter.name,
                            event.line_id,
                        )

        # 4. Enrich event from LineState (for CONNECT/DISCONNECT which lack call details)
        if event.event_type in (CallEventType.CONNECT, CallEventType.DISCONNECT):
            line_state = (
                self.pbx.get_line_state(event.line_id)
                if event.line_id is not None
                else None
            )
            if line_state:
                updates = {}
                # Fill missing number field
                if not event.number:
                    if line_state.direction == CallDirection.INBOUND:
                        updates["number"] = line_state.caller_number or ""
                    elif line_state.direction == CallDirection.OUTBOUND:
                        updates["number"] = line_state.called_number or ""
                # Fill caller/called numbers from LineState
                if not event.caller_number and line_state.caller_number:
                    updates["caller_number"] = line_state.caller_number
                if not event.called_number and line_state.called_number:
                    updates["called_number"] = line_state.called_number
                # Fill other fields from LineState
                if not event.trunk_id and line_state.trunk_id:
                    updates["trunk_id"] = line_state.trunk_id
                # Fill caller/called device from LineState if not already set on event
                if not event.caller_device and line_state.caller_device:
                    updates["caller_device"] = line_state.caller_device
                if not event.called_device and line_state.called_device:
                    updates["called_device"] = line_state.called_device
                # Direction should match LineState
                if event.direction != line_state.direction and line_state.direction:
                    updates["direction"] = line_state.direction
                if updates:
                    event = event.model_copy(update=updates)

        # 5. Resolve on RING (inbound) and CALL (outbound) events + cache result
        result = None
        if event.event_type in (CallEventType.RING, CallEventType.CALL):
            if event.number == ANONYMOUS:
                result = ANONYMOUS_RESULT
            elif event.number:
                result = await self.resolver_chain.resolve(event.number)
            # Cache the result for later retrieval (CONNECT/DISCONNECT on same line)
            if result and event.line_id is not None:
                self._resolve_cache[event.line_id] = result

        # 6. Lookup cached result for CONNECT/DISCONNECT events
        if result is None and event.line_id is not None:
            result = self._resolve_cache.get(event.line_id)

        # 7. Look up current line state (after FSM update)
        line_state = None
        if event.line_id is not None:
            line_state = self.pbx.get_line_state(event.line_id)

        # 8. Dispatch to output adapters
        for adapter in self._output_adapters:
            try:
                await adapter.handle(event, result, line_state=line_state)
            except Exception:
                logger.exception(
                    "Output adapter '%s' failed for event %s",
                    adapter.name,
                    event.number,
                )

        # 9. Cleanup resolve cache on terminal states
        if line_state and line_state.status.value in (
            "finished",
            "missed",
            "notReached",
        ):
            if event.line_id is not None:
                self._resolve_cache.pop(event.line_id, None)

    async def _on_line_idle(self, line_id: int, idle_state: LineState) -> None:
        """Callback from PBX auto-reset: notify output adapters of the idle transition.

        This fires ~1s after a terminal state (finished/missed/notReached)
        so that webhook/MQTT subscribers learn the line is free again.
        """
        logger.debug(
            "Line %d idle notification → dispatching to output adapters", line_id
        )
        for adapter in self._output_adapters:
            try:
                await adapter.handle_line_state_change(idle_state)
            except Exception:
                logger.exception(
                    "Output adapter '%s' failed for idle line state change on line %d",
                    adapter.name,
                    line_id,
                )
            try:
                await adapter.handle(
                    CallEvent(
                        number="",
                        direction=CallDirection.INBOUND,
                        event_type=CallEventType.DISCONNECT,
                        source="pbx",
                        connection_id=None,
                        line_id=line_id,
                    ),
                    None,
                    line_state=idle_state,
                )
            except Exception:
                logger.exception(
                    "Output adapter '%s' failed for idle notification on line %d",
                    adapter.name,
                    line_id,
                )

    def _setup_resolver_adapters(self) -> None:
        """Create and register resolver adapters."""
        resolver_factories = {
            "json_file": lambda cfg: JsonFileResolver(
                cfg, self.config.contacts_json_path
            ),
            "sqlite": lambda cfg: SqliteResolver(cfg, self.db),
            "msn": lambda cfg: MsnResolver(
                cfg, self.config.pbx.msns, self.config.phone
            ),
            "tellows": lambda cfg: TellowsResolver(cfg, self.db),
            "dastelefon": lambda cfg: DasTelefonbuchResolver(cfg, self.db),
            "klartelbuch": lambda cfg: KlarTelefonbuchResolver(cfg, self.db),
        }

        for adapter_config in self.config.resolver_adapters:
            if not adapter_config.enabled:
                logger.debug(
                    "Resolver adapter '%s' disabled, skipping", adapter_config.name
                )
                continue

            factory = resolver_factories.get(adapter_config.name)
            if factory:
                adapter = factory(adapter_config)
                self.resolver_chain.add_adapter(adapter)
            else:
                logger.warning("Unknown resolver adapter: '%s'", adapter_config.name)

    def _setup_input_adapters(self) -> None:
        """Create input adapters."""
        for adapter_config in self.config.input_adapters:
            if not adapter_config.enabled:
                logger.debug(
                    "Input adapter '%s' disabled, skipping", adapter_config.name
                )
                continue

            if adapter_config.name == "fritz_callmonitor":
                adapter = FritzCallmonitorAdapter(adapter_config)
                self._input_adapters.append(adapter)

            elif adapter_config.name == "rest":
                adapter = RestInputAdapter(adapter_config)
                self._rest_input = adapter
                self._input_adapters.append(adapter)

            elif adapter_config.name == "mqtt":
                adapter = MqttAdapter(adapter_config, self.config, self.pbx)
                self._mqtt_adapters[adapter_config.name] = adapter
                self._input_adapters.append(adapter)

            else:
                logger.warning("Unknown input adapter: '%s'", adapter_config.name)

    def _setup_output_adapters(self) -> None:
        """Create output adapters.

        Some adapter types (e.g. call_log) support only a single instance.
        Other types (e.g. webhook, mqtt) support multiple independent instances.
        """
        call_log_registered = False

        for adapter_config in self.config.output_adapters:
            if not adapter_config.enabled:
                logger.debug(
                    "Output adapter '%s' (%s) disabled, skipping",
                    adapter_config.name,
                    adapter_config.type,
                )
                continue

            adapter_type = adapter_config.type

            if adapter_type == "call_log":
                if call_log_registered:
                    logger.warning(
                        "Multiple call_log adapters configured — only first instance used"
                    )
                    continue
                adapter = CallLogOutputAdapter(adapter_config, self.db)
                call_log_registered = True
                self._output_adapters.append(adapter)

            elif adapter_type == "webhook":
                adapter = WebhookOutputAdapter(adapter_config)
                self._output_adapters.append(adapter)

            elif adapter_type == "mqtt":
                # Reuse existing MqttAdapter instance (same connection) if input
                # with the same name was already set up, otherwise create output-only.
                adapter = self._mqtt_adapters.get(adapter_config.name)
                if adapter is None:
                    adapter = MqttAdapter(adapter_config, self.config, self.pbx)
                    self._mqtt_adapters[adapter_config.name] = adapter
                self._output_adapters.append(adapter)

            else:
                logger.warning(
                    "Unknown output adapter type: '%s' (name: '%s')",
                    adapter_type,
                    adapter_config.name,
                )
