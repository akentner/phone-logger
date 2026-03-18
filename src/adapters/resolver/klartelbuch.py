"""klartelefonbuch.de resolver adapter - reverse phone number lookup."""

import logging
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from src.adapters.base import BaseResolverAdapter
from src.config import AdapterConfig
from src.core.event import ResolveResult
from src.db.database import Database

logger = logging.getLogger(__name__)

KLARTELBUCH_URL = "https://www.klartelefonbuch.de/inverssuche/{number}"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class KlarTelefonbuchResolver(BaseResolverAdapter):
    """
    Resolves phone numbers via klartelefonbuch.de reverse lookup.

    Results are cached in the SQLite database with a configurable TTL.
    """

    def __init__(self, config: AdapterConfig, db: Database) -> None:
        super().__init__(config)
        self.db = db
        self.ttl_days = config.config.get("ttl_days", 30)
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Create HTTP session."""
        self._session = aiohttp.ClientSession(
            headers={"User-Agent": USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=15),
        )

    async def stop(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Try to resolve via klartelefonbuch.de, checking cache first."""
        cached = await self.db.get_cached(number, "klartelbuch")
        if cached:
            self.logger.debug("Cache hit for '%s' on klartelbuch", number)
            return ResolveResult(
                number=number,
                name=cached.get("name"),
                tags=cached.get("tags", []),
                notes=cached.get("notes"),
                source="klartelbuch",
                cached=True,
            )

        result = await self._scrape(number)
        if result:
            await self.db.set_cached(number, "klartelbuch", result.model_dump(), self.ttl_days)

        return result

    async def _scrape(self, number: str) -> Optional[ResolveResult]:
        """Scrape klartelefonbuch.de for phone number information."""
        if not self._session:
            self.logger.error("HTTP session not initialized")
            return None

        clean_number = number.lstrip("+").replace(" ", "").replace("-", "").replace("/", "")
        if clean_number.startswith("49") and len(clean_number) > 4:
            clean_number = "0" + clean_number[2:]

        url = KLARTELBUCH_URL.format(number=clean_number)

        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    self.logger.debug("klartelefonbuch returned %d for '%s'", response.status, number)
                    return None

                html = await response.text()
                return self._parse_html(number, html)
        except aiohttp.ClientError as e:
            self.logger.error("Failed to fetch klartelefonbuch for '%s': %s", number, e)
            return None

    def _parse_html(self, number: str, html: str) -> Optional[ResolveResult]:
        """Parse klartelefonbuch.de HTML for caller information."""
        soup = BeautifulSoup(html, "lxml")

        # Look for result entries
        entry = soup.select_one("div.result-item, div.entry")
        if not entry:
            return None

        # Extract name
        name_tag = entry.select_one("h2 a, div.name, span.entry-name")
        if not name_tag:
            return None

        name = name_tag.get_text(strip=True)
        if not name:
            return None

        # Extract address
        notes = None
        addr_tag = entry.select_one("div.address, span.entry-address")
        if addr_tag:
            notes = addr_tag.get_text(strip=True)

        return ResolveResult(
            number=number,
            name=name,
            tags=[],
            notes=notes,
            source="klartelbuch",
        )
