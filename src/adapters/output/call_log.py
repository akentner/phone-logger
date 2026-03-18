"""Call log output adapter - stores all call events in SQLite."""

import logging
from typing import TYPE_CHECKING, Optional

from src.adapters.base import BaseOutputAdapter
from src.config import AdapterConfig
from src.core.event import CallEvent, ResolveResult
from src.db.database import Database

if TYPE_CHECKING:
    from src.core.pbx import LineState

logger = logging.getLogger(__name__)


class CallLogOutputAdapter(BaseOutputAdapter):
    """
    Output adapter that logs all call events to the SQLite database.

    This adapter should always be active to maintain a call history.
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
        """Log call event to database."""
        resolved_name = result.name if result else None
        source = result.source if result else None

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
