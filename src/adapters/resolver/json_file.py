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

    Expects numbers stored in E.164 format (+49...).
    The pipeline normalizes incoming numbers before calling resolve(),
    so no further normalization is needed here.

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
                number = entry.get("number", "").strip()
                if number:
                    self._contacts[number] = entry

            self.logger.info("Loaded %d contacts from %s", len(self._contacts), self.file_path)
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error("Failed to load contacts JSON: %s", e)
            self._contacts = {}

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Look up a number in the loaded contacts. Expects E.164 input."""
        entry = self._contacts.get(number)
        if not entry:
            self.logger.debug("No match for %r in JSON file", number)
            return None

        self.logger.debug("Match for %r in JSON file: %s", number, entry.get("name"))
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
