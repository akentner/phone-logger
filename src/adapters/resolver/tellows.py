"""Tellows.de resolver adapter - web scraping for spam scores."""

import logging
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from src.adapters.base import BaseResolverAdapter
from src.config import AdapterConfig
from src.core.event import ResolveResult
from src.db.database import Database

logger = logging.getLogger(__name__)

TELLOWS_URL = "https://www.tellows.de/num/{number}"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class TellowsResolver(BaseResolverAdapter):
    """
    Resolves phone numbers via tellows.de web scraping.

    Results are cached in the SQLite database with a configurable TTL.
    """

    def __init__(self, config: AdapterConfig, db: Database) -> None:
        super().__init__(config)
        self.db = db
        self.ttl_days = config.config.get("ttl_days", 7)
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
        """Try to resolve via tellows.de, checking cache first."""
        # Check cache first
        cached = await self.db.get_cached(number, "tellows")
        if cached:
            self.logger.debug("Cache hit for '%s' on tellows", number)
            return ResolveResult(
                number=number,
                name=cached.get("name"),
                tags=cached.get("tags", []),
                spam_score=cached.get("spam_score"),
                source="tellows",
                cached=True,
            )

        # Scrape tellows.de
        result = await self._scrape(number)
        if result:
            # Cache the result
            await self.db.set_cached(number, "tellows", result.model_dump(), self.ttl_days)

        return result

    async def _scrape(self, number: str) -> Optional[ResolveResult]:
        """Scrape tellows.de for phone number information."""
        if not self._session:
            self.logger.error("HTTP session not initialized")
            return None

        # Clean number for URL (digits only, no +)
        clean_number = number.lstrip("+").replace(" ", "").replace("-", "").replace("/", "")
        # For German numbers: convert +49 prefix to 0
        if clean_number.startswith("49") and len(clean_number) > 4:
            clean_number = "0" + clean_number[2:]

        url = TELLOWS_URL.format(number=clean_number)

        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    self.logger.debug("Tellows returned %d for '%s'", response.status, number)
                    return None

                html = await response.text()
                return self._parse_html(number, html)
        except aiohttp.ClientError as e:
            self.logger.error("Failed to fetch tellows for '%s': %s", number, e)
            return None

    def _parse_html(self, number: str, html: str) -> Optional[ResolveResult]:
        """Parse tellows.de HTML for caller information."""
        soup = BeautifulSoup(html, "lxml")

        # Extract caller name/type
        name = None
        score_tag = soup.select_one("div.score_result span.scoreresult")
        if score_tag:
            # Score is 1-9 on tellows (1=trusted, 9=spam)
            try:
                score_text = score_tag.get_text(strip=True)
                spam_score = int(score_text)
            except (ValueError, TypeError):
                spam_score = None
        else:
            spam_score = None

        # Extract caller name from the headline
        headline = soup.select_one("h1.phonepagetitle")
        if headline:
            name_parts = headline.get_text(strip=True)
            # Typical format: "Rufnummer 0123456789 - Name"
            if " - " in name_parts:
                name = name_parts.split(" - ", 1)[1].strip()

        # Extract caller type
        tags = []
        caller_type = soup.select_one("span.callertype")
        if caller_type:
            type_text = caller_type.get_text(strip=True)
            if type_text:
                tags.append(type_text)

        # Extract number of ratings
        ratings_el = soup.select_one("span.numratings")
        if ratings_el:
            try:
                num_ratings = int(ratings_el.get_text(strip=True).split()[0])
                if num_ratings == 0:
                    # No ratings = no useful data
                    return None
            except (ValueError, IndexError):
                pass

        if not name and not spam_score:
            return None

        return ResolveResult(
            number=number,
            name=name or f"Tellows Score: {spam_score}",
            tags=tags,
            spam_score=spam_score,
            source="tellows",
        )
