"""MSN resolver adapter — resolves own subscriber numbers from PBX config."""

from typing import Optional

from src.adapters.base import BaseResolverAdapter
from src.config import AdapterConfig, MsnConfig, PhoneConfig
from src.core import phone_number as pn
from src.core.event import ResolveResult


class MsnResolver(BaseResolverAdapter):
    """
    Resolves phone numbers against the own MSNs (subscriber numbers) from AppConfig.

    MSNs in the config are short subscriber numbers (e.g. "990133") without country
    or area code. This resolver expands them to E.164 at startup using PhoneConfig
    and performs an O(1) lookup at resolve-time.

    MSNs without a label are skipped — they would produce a meaningless result.
    No DB cache or network access needed; the lookup table is built once at init.
    """

    def __init__(
        self,
        config: AdapterConfig,
        msns: list[MsnConfig],
        phone: PhoneConfig,
    ) -> None:
        super().__init__(config)
        self._lookup: dict[str, str] = {}

        for msn in msns:
            if not msn.label:
                self.logger.debug("MSN %r has no label, skipping", msn.number)
                continue

            e164 = pn.normalize(
                msn.number,
                country_code=phone.country_code,
                local_area_code=phone.local_area_code,
            )
            self._lookup[e164] = msn.label
            self.logger.debug(
                "Registered MSN %r -> %r (%s)", msn.number, e164, msn.label
            )

        self.logger.debug("MsnResolver ready with %d entries", len(self._lookup))

    async def resolve(self, number: str) -> Optional[ResolveResult]:
        """Look up an E.164 number against own MSNs. Returns None if not an own number."""
        label = self._lookup.get(number)
        if label is None:
            self.logger.debug("No MSN match for %r", number)
            return None

        self.logger.debug("MSN match: %r -> %r", number, label)
        return ResolveResult(name=label, number=number, source="msn")
