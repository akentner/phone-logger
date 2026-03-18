"""JSON file resolver adapter - reads contacts from a static JSON file."""

import json
from pathlib import Path
from typing import Optional

from src.adapters.base import BaseResolverAdapter
from src.config import AdapterConfig
from src.core.event import ResolveResult


class JsonFileResolver(BaseResolverAdapter):
    """
    Resolves phone numbers from a JSON file.

    Expected JSON format:
    [
        {"number": "+491234567890", "name": "Max Mustermann", "tags": ["Familie"], "notes": "...", "spam_score": null},
        ...
    ]
    """

    def __init__(self, config: AdapterConfig, file_path: str) -> None:
        super().__init__(config)
        self.file_path = file_path
        self._contacts: dict[str, dict] = {}

    async def start(self) -> None:
        """Load contacts from JSON file."""
        await self._load_contacts()

    async def _load_contacts(self) -> None:
        """Load and index contacts from JSON file."""
        path = Path(self.file_path)
        if not path.exists():
            self.logger.warning("Contacts JSON file not found: %s", self.file_path)
            self._contacts = {}
            return

        try:
            with open(path) as f:
                data = json.load(f)

            self._contacts = {}
            for entry in data:
                number = self._normalize_number(entry.get("number", ""))
                if number:
                    self._contacts[number] = entry

            self.logger.info("Loaded %d contacts from %s", len(self._contacts), self.file_path)
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error("Failed to load contacts JSON: %s", e)
            self._contacts = {}

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Look up a number in the loaded contacts."""
        normalized = self._normalize_number(number)

        # Try exact match first
        entry = self._contacts.get(normalized)

        # Try without country code
        if not entry and normalized.startswith("+49"):
            alt = "0" + normalized[3:]
            entry = self._contacts.get(alt)

        if not entry:
            return None

        return ResolveResult(
            number=number,
            name=entry.get("name"),
            tags=entry.get("tags", []),
            notes=entry.get("notes"),
            spam_score=entry.get("spam_score"),
            source="json_file",
        )

    async def reload(self) -> None:
        """Reload contacts from file (can be triggered via API)."""
        await self._load_contacts()

    @staticmethod
    def _normalize_number(number: str) -> str:
        """Basic number normalization: strip whitespace, dashes, slashes."""
        return number.strip().replace(" ", "").replace("-", "").replace("/", "")
