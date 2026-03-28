"""Tests for E.164 phone number normalization."""

import pytest

from src.core.phone_number import normalize, to_dialable, to_local, to_scrape_format


class TestNormalize:
    """Tests for normalize() covering all expected input formats."""

    # --- Already E.164 ---

    def test_e164_unchanged(self):
        assert normalize("+49301234567") == "+49301234567"

    def test_e164_with_spaces_stripped(self):
        assert normalize("+49 30 123456") == "+4930123456"

    def test_e164_with_dashes_stripped(self):
        assert normalize("+49-30-123456") == "+4930123456"

    # --- International double-zero prefix ---

    def test_double_zero_prefix(self):
        assert normalize("0049301234567") == "+49301234567"

    def test_double_zero_with_spaces(self):
        assert normalize("0049 30 123456") == "+4930123456"

    # --- National format (leading 0) ---

    def test_national_leading_zero(self):
        assert normalize("030123456") == "+4930123456"

    def test_national_mobile(self):
        assert normalize("015123456789") == "+4915123456789"

    def test_national_with_spaces(self):
        assert normalize("030 123456") == "+4930123456"

    def test_national_with_dashes(self):
        assert normalize("030-123456") == "+4930123456"

    # --- Local number (no area code) ---

    def test_local_number_with_area_code(self):
        assert normalize("123456", local_area_code="30") == "+4930123456"

    def test_local_number_without_area_code_returns_digits(self):
        # Without local_area_code configured, returns bare digits
        assert normalize("123456") == "123456"

    def test_local_number_different_country(self):
        assert (
            normalize("123456", country_code="43", local_area_code="1") == "+431123456"
        )

    # --- Edge cases ---

    def test_empty_string(self):
        assert normalize("") == ""

    def test_whitespace_only(self):
        result = normalize("   ")
        assert result == ""  # stripped to empty

    def test_plus_only(self):
        result = normalize("+")
        assert result == "+"

    def test_non_german_e164(self):
        assert normalize("+12125551234") == "+12125551234"

    def test_non_german_double_zero(self):
        assert normalize("0012125551234") == "+12125551234"


class TestToDialable:
    """Tests for to_dialable() E.164 -> national format."""

    def test_german_number(self):
        assert to_dialable("+49301234567") == "0301234567"

    def test_german_mobile(self):
        assert to_dialable("+4915123456789") == "015123456789"

    def test_non_german_number(self):
        # Different country code — returns without +
        assert to_dialable("+12125551234") == "12125551234"

    def test_already_national(self):
        # Not E.164 format — returned as-is
        assert to_dialable("0301234567") == "0301234567"


class TestToScrapeFormat:
    """Tests for to_scrape_format() used by web scraping adapters."""

    def test_converts_to_national(self):
        assert to_scrape_format("+49301234567") == "0301234567"

    def test_no_separators(self):
        result = to_scrape_format("+49301234567")
        assert " " not in result
        assert "-" not in result


class TestToLocal:
    """Tests for to_local() — E.164 to short subscriber number (MSN)."""

    def test_strips_country_and_area_code(self):
        assert (
            to_local("+496181990133", country_code="49", local_area_code="6181")
            == "990133"
        )

    def test_berlin_area_code(self):
        assert (
            to_local("+4930123456", country_code="49", local_area_code="30") == "123456"
        )

    def test_no_area_code_strips_country_only(self):
        # Without local_area_code, strips only country code
        assert to_local("+496181990133", country_code="49") == "6181990133"

    def test_different_country(self):
        assert (
            to_local("+431123456", country_code="43", local_area_code="1") == "123456"
        )

    def test_no_match_returns_original(self):
        # US number with German config — no match, returns as-is
        assert (
            to_local("+12125551234", country_code="49", local_area_code="30")
            == "+12125551234"
        )

    def test_already_local_returns_as_is(self):
        assert to_local("990133", country_code="49", local_area_code="6181") == "990133"

    def test_empty_area_code_strips_country(self):
        assert (
            to_local("+4930123456", country_code="49", local_area_code="") == "30123456"
        )
