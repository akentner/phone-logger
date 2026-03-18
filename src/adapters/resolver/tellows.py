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

# Tellows expects E.164 with + URL-encoded as %2B
# e.g. https://www.tellows.de/num/%2B496181990134
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class TellowsResolver(BaseResolverAdapter):
    """
    Resolves phone numbers via tellows.de web scraping.

    Accepts E.164 input (+49...). Uses E.164 directly in the URL (+ encoded as %2B).
    Results are cached in SQLite with a configurable TTL.

    Debug logging (log_level=DEBUG) shows:
    - Full request URL
    - HTTP status code and response size
    - Which CSS selectors matched / did not match
    - Extracted field values before returning
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
        self.logger.debug("HTTP session created (UA: %s)", USER_AGENT[:40])

    async def stop(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Try to resolve via tellows.de, checking cache first. Expects E.164 input."""
        # Check cache first
        cached = await self.db.get_cached(number, "tellows")
        if cached:
            self.logger.debug("Cache hit for %r (ttl=%d days)", number, self.ttl_days)
            return ResolveResult(
                number=number,
                name=cached.get("name"),
                tags=cached.get("tags", []),
                spam_score=cached.get("spam_score"),
                source="tellows",
                cached=True,
            )

        self.logger.debug("Cache miss for %r, fetching from tellows.de", number)
        result = await self._scrape(number)
        if result:
            await self.db.set_cached(number, "tellows", result.model_dump(), self.ttl_days)
            self.logger.debug("Cached result for %r (ttl=%d days)", number, self.ttl_days)

        return result

    async def _scrape(self, number: str) -> Optional[ResolveResult]:
        """Scrape tellows.de for phone number information."""
        if not self._session:
            self.logger.error("HTTP session not initialized — was start() called?")
            return None

        # Tellows expects E.164 with + URL-encoded as %2B
        from urllib.parse import quote
        url = TELLOWS_URL.format(number=quote(number, safe=""))

        self.logger.debug("GET %s  (number=%r)", url, number)

        try:
            async with self._session.get(url) as response:
                self.logger.debug(
                    "Response: HTTP %d  content-type=%s",
                    response.status,
                    response.headers.get("content-type", "?"),
                )
                if response.status != 200:
                    self.logger.info(
                        "Tellows returned HTTP %d for %r — skipping", response.status, number
                    )
                    return None

                html = await response.text()
                self.logger.debug("Response body: %d bytes", len(html))
                return self._parse_html(number, html)

        except aiohttp.ClientError as e:
            self.logger.error("Request failed for %r: %s", number, e)
            return None

    def _parse_html(self, number: str, html: str) -> Optional[ResolveResult]:
        """Parse tellows.de HTML for caller information."""
        soup = BeautifulSoup(html, "lxml")

        # --- Spam score ---
        # Selector: #tellowsscore > div > a > img.scoreimage
        # Alt attribute format: "tellows Bewertung für 06181990133 : Score 5"
        spam_score: Optional[int] = None
        score_img = soup.select_one("#tellowsscore > div > a > img.scoreimage")
        if score_img:
            alt = str(score_img.get("alt", ""))
            self.logger.debug("Selector '#tellowsscore > div > a > img.scoreimage' -> alt=%r", alt)
            # Extract score from "... : Score 5"
            if ": Score " in alt:
                try:
                    spam_score = int(alt.split(": Score ")[-1].strip())
                    self.logger.debug("Extracted spam_score: %d", spam_score)
                except (ValueError, TypeError):
                    self.logger.debug("Could not parse score from alt %r", alt)
        else:
            self.logger.debug("Selector '#tellowsscore > div > a > img.scoreimage' -> no match")

        # --- Caller name ---
        name: Optional[str] = None
        headline = soup.select_one("h1.phonepagetitle")
        if headline:
            raw = headline.get_text(strip=True)
            self.logger.debug("Selector 'h1.phonepagetitle' -> %r", raw)
            # Typical format: "Rufnummer 0123456789 - Name"
            if " - " in raw:
                name = raw.split(" - ", 1)[1].strip()
                self.logger.debug("Extracted name: %r", name)
        else:
            self.logger.debug("Selector 'h1.phonepagetitle' -> no match")

        # --- Caller type / tags ---
        tags: list[str] = []
        caller_type = soup.select_one("span.callertype")
        if caller_type:
            type_text = caller_type.get_text(strip=True)
            self.logger.debug("Selector 'span.callertype' -> %r", type_text)
            if type_text:
                tags.append(type_text)
        else:
            self.logger.debug("Selector 'span.callertype' -> no match")

        # --- Number of ratings ---
        ratings_el = soup.select_one("span.numratings")
        if ratings_el:
            raw = ratings_el.get_text(strip=True)
            self.logger.debug("Selector 'span.numratings' -> %r", raw)
            try:
                num_ratings = int(raw.split()[0])
                if num_ratings == 0:
                    self.logger.debug("Zero ratings for %r — returning no result", number)
                    return None
            except (ValueError, IndexError):
                pass
        else:
            self.logger.debug("Selector 'span.numratings' -> no match")

        if not name and spam_score is None:
            self.logger.debug("No usable data extracted for %r — returning no result", number)
            return None

        self.logger.info(
            "Tellows result for %r: name=%r score=%r tags=%r",
            number, name, spam_score, tags,
        )
        return ResolveResult(
            number=number,
            name=name or f"Tellows Score: {spam_score}",
            tags=tags,
            spam_score=spam_score,
            source="tellows",
        )
