"""Unit tests for MsnResolver."""

import pytest

from src.adapters.resolver.msn import MsnResolver
from src.config import AdapterConfig, MsnConfig, PhoneConfig


def _adapter_config() -> AdapterConfig:
    return AdapterConfig(type="msn", name="msn", enabled=True)


def _phone(country_code: str = "49", local_area_code: str = "6181") -> PhoneConfig:
    return PhoneConfig(country_code=country_code, local_area_code=local_area_code)


def _msns(*entries: tuple[str, str]) -> list[MsnConfig]:
    return [MsnConfig(number=number, label=label) for number, label in entries]


# --- Construction / lookup table ---


class TestMsnResolverInit:
    def test_expands_short_number_to_e164(self):
        """MSN '990133' + country '49' + area '6181' → '+496181990133'."""
        resolver = MsnResolver(
            _adapter_config(),
            _msns(("990133", "Am Berghof 24")),
            _phone(),
        )
        assert "+496181990133" in resolver._lookup
        assert resolver._lookup["+496181990133"] == "Am Berghof 24"

    def test_multiple_msns_all_registered(self):
        resolver = MsnResolver(
            _adapter_config(),
            _msns(
                ("990133", "Am Berghof 24"),
                ("990134", "Am Berghof 22"),
                ("990135", "HI Homeoffice"),
            ),
            _phone(),
        )
        assert len(resolver._lookup) == 3
        assert resolver._lookup["+496181990133"] == "Am Berghof 24"
        assert resolver._lookup["+496181990134"] == "Am Berghof 22"
        assert resolver._lookup["+496181990135"] == "HI Homeoffice"

    def test_msn_without_label_is_skipped(self):
        """MSNs without label should not appear in the lookup table."""
        resolver = MsnResolver(
            _adapter_config(),
            [
                MsnConfig(number="990133", label=""),
                MsnConfig(number="990134", label="Am Berghof 22"),
            ],
            _phone(),
        )
        assert len(resolver._lookup) == 1
        assert "+496181990133" not in resolver._lookup
        assert "+496181990134" in resolver._lookup

    def test_empty_msn_list(self):
        resolver = MsnResolver(_adapter_config(), [], _phone())
        assert resolver._lookup == {}

    def test_national_number_with_area_code_expands_correctly(self):
        """A number that already contains the area code (e.g. '06181990133') → E.164."""
        resolver = MsnResolver(
            _adapter_config(),
            _msns(("06181990133", "Full National")),
            _phone(),
        )
        assert "+496181990133" in resolver._lookup

    def test_different_country_code(self):
        """Works with non-German country codes."""
        resolver = MsnResolver(
            _adapter_config(),
            _msns(("123456", "Test AT")),
            PhoneConfig(country_code="43", local_area_code="1"),
        )
        assert "+431123456" in resolver._lookup


# --- Resolution ---


class TestMsnResolverResolve:
    @pytest.mark.asyncio
    async def test_match_returns_resolve_result(self):
        resolver = MsnResolver(
            _adapter_config(),
            _msns(("990133", "Am Berghof 24")),
            _phone(),
        )
        result = await resolver.resolve("+496181990133")
        assert result is not None
        assert result.name == "Am Berghof 24"
        assert result.number == "+496181990133"
        assert result.source == "msn"

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self):
        resolver = MsnResolver(
            _adapter_config(),
            _msns(("990133", "Am Berghof 24")),
            _phone(),
        )
        result = await resolver.resolve("+4930987654")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_lookup_returns_none(self):
        resolver = MsnResolver(_adapter_config(), [], _phone())
        result = await resolver.resolve("+496181990133")
        assert result is None

    @pytest.mark.asyncio
    async def test_result_has_no_tags_or_notes(self):
        """MSN results carry only name, number and source — no spam_score, tags, notes."""
        resolver = MsnResolver(
            _adapter_config(),
            _msns(("990133", "Am Berghof 24")),
            _phone(),
        )
        result = await resolver.resolve("+496181990133")
        assert result is not None
        assert result.tags == []
        assert result.notes is None
        assert result.spam_score is None

    @pytest.mark.asyncio
    async def test_multiple_msns_correct_label_returned(self):
        """Resolving one of several MSNs returns exactly that MSN's label."""
        resolver = MsnResolver(
            _adapter_config(),
            _msns(
                ("990133", "Am Berghof 24"),
                ("990134", "Am Berghof 22"),
            ),
            _phone(),
        )
        result_24 = await resolver.resolve("+496181990133")
        result_22 = await resolver.resolve("+496181990134")

        assert result_24 is not None and result_24.name == "Am Berghof 24"
        assert result_22 is not None and result_22.name == "Am Berghof 22"

    @pytest.mark.asyncio
    async def test_anonymous_number_returns_none(self):
        """'anonymous' placeholder should not match any MSN."""
        resolver = MsnResolver(
            _adapter_config(),
            _msns(("990133", "Am Berghof 24")),
            _phone(),
        )
        result = await resolver.resolve("anonymous")
        assert result is None
