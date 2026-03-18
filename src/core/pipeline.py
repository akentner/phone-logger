"""Pipeline orchestration: Input -> Resolve -> Output."""

import logging
from typing import Optional

from src.adapters.base import BaseInputAdapter, BaseOutputAdapter
from src.adapters.resolver.chain import ResolverChain
from src.config import AdapterConfig, AppConfig
from src.core import phone_number as pn
from src.core.event import CallEvent, CallEventType, PipelineResult, ResolveResult
from src.core.pbx import PbxStateManager

ANONYMOUS = "anonymous"
ANONYMOUS_RESULT = ResolveResult(name="Anonym", number=ANONYMOUS, source="system")
from src.db.database import Database

# Import all adapter implementations
from src.adapters.input.fritz import FritzCallmonitorAdapter
from src.adapters.input.rest import RestInputAdapter
from src.adapters.input.mqtt_sub import MqttInputAdapter
from src.adapters.resolver.json_file import JsonFileResolver
from src.adapters.resolver.sqlite_db import SqliteResolver
from src.adapters.resolver.tellows import TellowsResolver
from src.adapters.resolver.dastelefon import DasTelefonbuchResolver
from src.adapters.resolver.klartelbuch import KlarTelefonbuchResolver
from src.adapters.output.call_log import CallLogOutputAdapter
from src.adapters.output.webhook import WebhookOutputAdapter
from src.adapters.output.mqtt_pub import MqttPublisherOutputAdapter

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
        self.pbx = PbxStateManager(config.pbx, config.phone)
        self._input_adapters: list[BaseInputAdapter] = []
        self._output_adapters: list[BaseOutputAdapter] = []
        self._rest_input: Optional[RestInputAdapter] = None

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
        return await self.resolver_chain.resolve(normalized)

    async def _on_event(self, event: CallEvent) -> None:
        """
        Handle an incoming call event.

        Processing order:
        1. Normalize phone number to E.164
        2. Enrich with PBX info (line, device, caller/called numbers)
        3. Update PBX line state (FSM transition)
        4. Resolve phone number (only RING/CALL events)
        5. Dispatch to output adapters
        """
        # 1. Normalize number to E.164
        if event.number:
            normalized = self.normalize(event.number)
            if normalized != event.number:
                logger.debug(
                    "Normalized number: %r -> %r", event.number, normalized
                )
            event = event.model_copy(update={"number": normalized})

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

        # 4. Resolve on RING (inbound) and CALL (outbound) events
        result = None
        if event.event_type in (CallEventType.RING, CallEventType.CALL):
            if event.number == ANONYMOUS:
                result = ANONYMOUS_RESULT
            elif event.number:
                result = await self.resolver_chain.resolve(event.number)

        # 5. Look up current line state (after FSM update)
        line_state = None
        if event.line_id is not None:
            line_state = self.pbx.get_line_state(event.line_id)

        # 6. Dispatch to output adapters
        for adapter in self._output_adapters:
            try:
                await adapter.handle(event, result, line_state=line_state)
            except Exception:
                logger.exception(
                    "Output adapter '%s' failed for event %s",
                    adapter.name,
                    event.number,
                )

    def _setup_resolver_adapters(self) -> None:
        """Create and register resolver adapters."""
        resolver_factories = {
            "json_file": lambda cfg: JsonFileResolver(cfg, self.config.contacts_json_path),
            "sqlite": lambda cfg: SqliteResolver(cfg, self.db),
            "tellows": lambda cfg: TellowsResolver(cfg, self.db),
            "dastelefon": lambda cfg: DasTelefonbuchResolver(cfg, self.db),
            "klartelbuch": lambda cfg: KlarTelefonbuchResolver(cfg, self.db),
        }

        for adapter_config in self.config.resolver_adapters:
            if not adapter_config.enabled:
                logger.debug("Resolver adapter '%s' disabled, skipping", adapter_config.name)
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
                logger.debug("Input adapter '%s' disabled, skipping", adapter_config.name)
                continue

            if adapter_config.name == "fritz":
                adapter = FritzCallmonitorAdapter(adapter_config)
                self._input_adapters.append(adapter)

            elif adapter_config.name == "rest":
                adapter = RestInputAdapter(adapter_config)
                self._rest_input = adapter
                self._input_adapters.append(adapter)

            elif adapter_config.name == "mqtt":
                adapter = MqttInputAdapter(adapter_config)
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
                logger.debug("Output adapter '%s' (%s) disabled, skipping", adapter_config.name, adapter_config.type)
                continue

            adapter_type = adapter_config.type
            
            if adapter_type == "call_log":
                if call_log_registered:
                    logger.warning("Multiple call_log adapters configured — only first instance used")
                    continue
                adapter = CallLogOutputAdapter(adapter_config, self.db)
                call_log_registered = True
                self._output_adapters.append(adapter)

            elif adapter_type == "webhook":
                adapter = WebhookOutputAdapter(adapter_config)
                self._output_adapters.append(adapter)

            elif adapter_type == "mqtt":
                adapter = MqttPublisherOutputAdapter(adapter_config)
                self._output_adapters.append(adapter)

            else:
                logger.warning("Unknown output adapter type: '%s' (name: '%s')", adapter_type, adapter_config.name)
