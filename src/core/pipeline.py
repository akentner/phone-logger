"""Pipeline orchestration: Input -> Resolve -> Output."""

import logging
from typing import Optional

from src.adapters.base import BaseInputAdapter, BaseOutputAdapter
from src.adapters.resolver.chain import ResolverChain
from src.config import AdapterConfig, AppConfig
from src.core.event import CallEvent, CallEventType, PipelineResult, ResolveResult
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
from src.adapters.output.ha_webhook import HaWebhookOutputAdapter
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

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Resolve a phone number through the chain (for direct API calls)."""
        return await self.resolver_chain.resolve(number)

    async def _on_event(self, event: CallEvent) -> None:
        """
        Handle an incoming call event.

        This is the central event handler called by all input adapters.
        """
        logger.info(
            "Event received: %s %s %s (source: %s)",
            event.direction.value,
            event.event_type.value,
            event.number,
            event.source,
        )

        # Only resolve on RING (inbound) and CALL (outbound) events
        result = None
        if event.event_type in (CallEventType.RING, CallEventType.CALL) and event.number:
            result = await self.resolver_chain.resolve(event.number)

        # Send to all output adapters
        for adapter in self._output_adapters:
            try:
                await adapter.handle(event, result)
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
                adapter = FritzCallmonitorAdapter(adapter_config, self.config.fritz)
                self._input_adapters.append(adapter)

            elif adapter_config.name == "rest":
                adapter = RestInputAdapter(adapter_config)
                self._rest_input = adapter
                self._input_adapters.append(adapter)

            elif adapter_config.name == "mqtt":
                adapter = MqttInputAdapter(adapter_config, self.config.mqtt)
                self._input_adapters.append(adapter)

            else:
                logger.warning("Unknown input adapter: '%s'", adapter_config.name)

    def _setup_output_adapters(self) -> None:
        """Create output adapters."""
        for adapter_config in self.config.output_adapters:
            if not adapter_config.enabled:
                logger.debug("Output adapter '%s' disabled, skipping", adapter_config.name)
                continue

            if adapter_config.name == "call_log":
                adapter = CallLogOutputAdapter(adapter_config, self.db)
                self._output_adapters.append(adapter)

            elif adapter_config.name == "ha_webhook":
                adapter = HaWebhookOutputAdapter(adapter_config, self.config.webhook)
                self._output_adapters.append(adapter)

            elif adapter_config.name == "mqtt":
                adapter = MqttPublisherOutputAdapter(adapter_config, self.config.mqtt)
                self._output_adapters.append(adapter)

            else:
                logger.warning("Unknown output adapter: '%s'", adapter_config.name)
