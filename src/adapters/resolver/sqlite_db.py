"""SQLite database resolver adapter - reads contacts from the local database."""

from typing import Optional

from src.adapters.base import BaseResolverAdapter
from src.config import AdapterConfig
from src.core.event import ResolveResult
from src.db.database import Database


class SqliteResolver(BaseResolverAdapter):
    """
    Resolves phone numbers from the local SQLite contacts database.

    Expects E.164 input from the pipeline. Contacts should be stored in E.164 format.
    """

    def __init__(self, config: AdapterConfig, db: Database) -> None:
        super().__init__(config)
        self.db = db

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Look up a number in the SQLite contacts table. Expects E.164 input."""
        contact = await self.db.get_contact(number)

        if not contact:
            self.logger.debug("No match for %r in SQLite contacts", number)
            return None

        self.logger.debug("Match for %r in SQLite: %s", number, contact.get("name"))

        # Update last_seen timestamp
        await self.db.update_last_seen(contact["number"])

        return ResolveResult(
            number=number,
            name=contact.get("name"),
            tags=contact.get("tags", []),
            notes=contact.get("notes"),
            spam_score=contact.get("spam_score"),
            source="sqlite",
        )
