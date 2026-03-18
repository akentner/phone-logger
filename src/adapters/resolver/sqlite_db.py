"""SQLite database resolver adapter - reads contacts from the local database."""

from typing import Optional

from src.adapters.base import BaseResolverAdapter
from src.config import AdapterConfig
from src.core.event import ResolveResult
from src.db.database import Database


class SqliteResolver(BaseResolverAdapter):
    """Resolves phone numbers from the local SQLite contacts database."""

    def __init__(self, config: AdapterConfig, db: Database) -> None:
        super().__init__(config)
        self.db = db

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Look up a number in the SQLite contacts table."""
        normalized = self._normalize_number(number)

        # Try exact match
        contact = await self.db.get_contact(normalized)

        # Try without country code
        if not contact and normalized.startswith("+49"):
            alt = "0" + normalized[3:]
            contact = await self.db.get_contact(alt)

        # Try with country code
        if not contact and normalized.startswith("0"):
            alt = "+49" + normalized[1:]
            contact = await self.db.get_contact(alt)

        if not contact:
            return None

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

    @staticmethod
    def _normalize_number(number: str) -> str:
        """Basic number normalization."""
        return number.strip().replace(" ", "").replace("-", "").replace("/", "")
