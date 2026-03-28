"""
Phone number normalization to E.164 format.

Handles common German number formats:
  - International with double-zero prefix: 004915123456789 -> +4915123456789
  - International with + prefix:           +4915123456789  -> +4915123456789
  - National with leading zero:            015123456789    -> +4915123456789
   - Local (no area code):                  123456          -> +4930123456    (with local_area_code="30")

E.164 format: +[country_code][subscriber_number], digits only after +, max 15 digits.
"""

import logging
import re

logger = logging.getLogger(__name__)


def normalize(
    number: str,
    country_code: str = "49",
    local_area_code: str = "",
) -> str:
    """
    Normalize a phone number to E.164 format (+CCXXXXXXXXX).

    Args:
        number: Raw phone number in any common format.
        country_code: Default country code without leading +/00 (default: "49" for Germany).
        local_area_code: Local area code without leading 0 (e.g. "30" for Berlin).
                         Used to expand short local numbers that have no area code.

    Returns:
        E.164 formatted number (e.g. "+49301234567").
        Returns the original number stripped of formatting if normalization fails.

    Examples:
        >>> normalize("030123456", country_code="49")
        '+4930123456'
        >>> normalize("0030123456", country_code="49")
        '+4930123456'
        >>> normalize("+4930123456", country_code="49")
        '+4930123456'
        >>> normalize("123456", country_code="49", local_area_code="30")
        '+4930123456'
    """
    if not number:
        return number

    # Pass through sentinel values unchanged
    if number == "anonymous":
        return number

    # Strip all formatting: spaces, dashes, slashes, parentheses
    cleaned = re.sub(r"[\s\-\./\(\)]", "", number.strip())

    if not cleaned:
        return ""

    # Already E.164: +XXXXXXX
    if cleaned.startswith("+"):
        result = "+" + re.sub(r"\D", "", cleaned[1:])
        logger.debug("normalize: %r -> %r (already E.164)", number, result)
        return result

    # International with double-zero prefix: 00CCXXXXXXX
    if cleaned.startswith("00"):
        result = "+" + re.sub(r"\D", "", cleaned[2:])
        logger.debug("normalize: %r -> %r (double-zero prefix)", number, result)
        return result

    # National with leading zero: 0XXXXXXXXX (e.g. 06301234567)
    if cleaned.startswith("0"):
        result = "+" + country_code + re.sub(r"\D", "", cleaned[1:])
        logger.debug("normalize: %r -> %r (national, leading zero)", number, result)
        return result

    # Pure digits, no leading zero: could be a local/extension number
    digits = re.sub(r"\D", "", cleaned)

    if not digits:
        return number

    if local_area_code:
        # Prepend local area code and country code
        result = "+" + country_code + local_area_code + digits
        logger.debug(
            "normalize: %r -> %r (local number, area code %r applied)",
            number,
            result,
            local_area_code,
        )
        return result

    # No local area code configured — return digits with country code as best-effort
    logger.debug(
        "normalize: %r -> %r (no local_area_code configured, keeping digits)",
        number,
        digits,
    )
    return digits


def to_dialable(e164: str, country_code: str = "49") -> str:
    """
    Convert an E.164 number to national dialable format (with leading 0).

    +4961819901134 -> 061819901134

    Used for web scraping URLs that expect national format.
    """
    if e164.startswith("+" + country_code):
        return "0" + e164[1 + len(country_code) :]
    if e164.startswith("+"):
        # Different country — return as-is without +
        return e164[1:]
    return e164


def to_local(
    e164: str,
    country_code: str = "49",
    local_area_code: str = "",
) -> str:
    """
    Strip the country code and local area code from an E.164 number,
    returning the short subscriber number (MSN).

    +496181990133  (country_code="49", local_area_code="6181") -> "990133"
    +4930123456    (country_code="49", local_area_code="30")   -> "123456"

    If the number doesn't match the expected prefix, returns the original number.
    """
    prefix = "+" + country_code + local_area_code
    if local_area_code and e164.startswith(prefix):
        return e164[len(prefix) :]
    # No area code or no match — fall back to stripping just the country code
    cc_prefix = "+" + country_code
    if e164.startswith(cc_prefix):
        return e164[len(cc_prefix) :]
    return e164


def to_scrape_format(e164: str, country_code: str = "49") -> str:
    """
    Convert an E.164 number to the format expected by German reverse-lookup sites.

    German sites typically expect national format with leading 0, no separators.
    +4961819901134 -> 061819901134
    """
    return to_dialable(e164, country_code)
