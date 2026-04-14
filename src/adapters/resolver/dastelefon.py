"""DasTelefonbuch.de resolver adapter - reverse phone number lookup."""

import logging
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from src.adapters.base import BaseResolverAdapter
from src.adapters.resolver.errors import NetworkError, RateLimitError
from src.config import AdapterConfig
from src.core import phone_number as pn
from src.core.event import ResolveResult
from src.db.database import Database

logger = logging.getLogger(__name__)

DASTELEFONBUCH_URL = "https://www.dastelefonbuch.de/R%C3%BCckw%C3%A4rtssuche/{number}"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DasTelefonbuchResolver(BaseResolverAdapter):
    """
    Resolves phone numbers via dasTelefonbuch.de reverse lookup.

    Accepts E.164 input (+49...). Converts to national format for the URL.
    Results are cached in SQLite with a configurable TTL.

    Debug logging (log_level=DEBUG) shows:
    - Full request URL
    - HTTP status and response size
    - CSS selector match results and extracted values
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
        self.logger.debug("HTTP session created")

    async def stop(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Try to resolve via dasTelefonbuch.de, checking cache first. Expects E.164 input."""
        cached = await self.db.get_cached(number, "dastelefon")
        if cached:
            self.logger.debug("Cache hit for %r (ttl=%d days)", number, self.ttl_days)
            return ResolveResult(
                number=number,
                name=cached.get("name"),
                tags=cached.get("tags", []),
                notes=cached.get("notes"),
                spam_score=cached.get("spam_score"),
                source="dastelefon",
                cached=True,
            )

        self.logger.debug("Cache miss for %r, fetching from dastelefonbuch.de", number)
        result = await self._scrape(number)
        if result:
            await self.db.set_cached(number, "dastelefon", result.model_dump(), self.ttl_days)
            self.logger.debug("Cached result for %r (ttl=%d days)", number, self.ttl_days)

        return result

    async def _scrape(self, number: str) -> Optional[ResolveResult]:
        """Scrape dasTelefonbuch.de for phone number information."""
        if not self._session:
            self.logger.error("HTTP session not initialized — was start() called?")
            return None

        national = pn.to_scrape_format(number)
        url = DASTELEFONBUCH_URL.format(number=national)

        self.logger.debug("GET %s  (number=%r national=%r)", url, number, national)

        try:
            async with self._session.get(url) as response:
                self.logger.debug(
                    "Response: HTTP %d  content-type=%s",
                    response.status,
                    response.headers.get("content-type", "?"),
                )
                if response.status == 429:
                    raise RateLimitError(f"Rate limited by {self.name} for {number!r} (HTTP 429)")
                if response.status != 200:
                    self.logger.info(
                        "DasTelefonbuch returned HTTP %d for %r — skipping",
                        response.status, number,
                    )
                    return None

                html = await response.text()
                self.logger.debug("Response body: %d bytes", len(html))
                return self._parse_html(number, html)

        except aiohttp.ClientError as e:
            raise NetworkError(f"Request failed for {number!r}: {e}") from e

    def _parse_html(self, number: str, html: str) -> Optional[ResolveResult]:
        """Parse dasTelefonbuch.de HTML for caller information."""
        soup = BeautifulSoup(html, "lxml")

        # --- Name ---
        name: Optional[str] = None
        for selector in ("div.vcard div.name a", "div.entry__title"):
            name_tag = soup.select_one(selector)
            if name_tag:
                name = name_tag.get_text(strip=True)
                self.logger.debug("Selector %r -> %r", selector, name)
                break
            self.logger.debug("Selector %r -> no match", selector)

        if not name:
            self.logger.debug("No name found for %r — returning no result", number)
            return None

        # --- Address / notes ---
        notes: Optional[str] = None
        for selector in ("div.vcard address", "div.entry__address"):
            addr_tag = soup.select_one(selector)
            if addr_tag:
                notes = addr_tag.get_text(strip=True)
                self.logger.debug("Selector %r -> %r", selector, notes)
                break
            self.logger.debug("Selector %r -> no match", selector)

        # --- Category / tags ---
        tags: list[str] = []
        for selector in ("div.vcard div.category", "span.entry__category"):
            type_tag = soup.select_one(selector)
            if type_tag:
                type_text = type_tag.get_text(strip=True)
                self.logger.debug("Selector %r -> %r", selector, type_text)
                if type_text:
                    tags.append(type_text)
                break
            self.logger.debug("Selector %r -> no match", selector)

        self.logger.info(
            "DasTelefonbuch result for %r: name=%r notes=%r tags=%r",
            number, name, notes, tags,
        )
        return ResolveResult(
            number=number,
            name=name,
            tags=tags,
            notes=notes,
            spam_score=None,
            source="dastelefon",
        )
