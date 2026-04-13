"""Utility functions for phone-logger."""

import secrets
import time
import uuid


def uuid7() -> str:
    """Generate a UUIDv7 (time-based, sortable UUID).

    UUIDv7 encodes the current Unix timestamp (48 bits) in the most significant
    bits, followed by random bits. This makes UUIDs sortable by creation time
    while maintaining uniqueness through randomness.

    Returns:
        A UUIDv7 string representation (36 characters with hyphens).

    References:
        - RFC 4122: https://datatracker.ietf.org/doc/html/draft-ietf-uuidrev-rfc4122bis
        - UUIDv7 Specification: Section 6.10
    """
    # Current Unix timestamp in milliseconds (48 bits)
    timestamp_ms = int(time.time() * 1000)

    # UUIDv7 structure (128 bits total):
    # - 48 bits: Unix timestamp in milliseconds (time_low + time_mid)
    # - 4 bits: version (0111 = 7)
    # - 12 bits: random (rand_a)
    # - 2 bits: variant (10)
    # - 62 bits: random (rand_b + rand_c)

    # Split timestamp into 32-bit and 16-bit parts
    time_low = (timestamp_ms >> 16) & 0xFFFFFFFF  # bits 0-31
    time_mid = timestamp_ms & 0xFFFF  # bits 32-47

    # Generate random bytes
    random_bytes = secrets.token_bytes(10)

    # time_hi_version: 4-bit version (7) + 12-bit random
    rand_a = int.from_bytes(random_bytes[0:2], "big") & 0x0FFF
    time_hi_version = 0x7000 | rand_a  # Version 7 in bits 12-15

    # clock_seq_hi_variant: 2-bit variant (10) + 6-bit random
    clock_seq_hi_variant = 0x80 | (random_bytes[2] & 0x3F)

    # clock_seq_low: 8-bit random
    clock_seq_low = random_bytes[3]

    # node: 48-bit random
    node = int.from_bytes(random_bytes[4:10], "big")

    # Create UUID from components using the standard UUID constructor
    uuid_obj = uuid.UUID(
        fields=(
            time_low,
            time_mid,
            time_hi_version,
            clock_seq_hi_variant,
            clock_seq_low,
            node,
        )
    )

    return str(uuid_obj)
