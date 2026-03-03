"""Random string generation utilities for Fishadoo.

All production strings are generated with the ``secrets`` module, which is
backed by the OS cryptographic random number generator (CSPRNG).  A seeded
``random.Random`` is provided only for test reproducibility via the
``seed_override`` parameter – never use it in production paths.
"""

import logging
import secrets
import string
from typing import Optional

logger = logging.getLogger(__name__)

# Supported character sets.  Keys must match the values accepted in config.json.
CHARSETS: dict[str, str] = {
    "alphanumeric": string.ascii_letters + string.digits,
    "alpha": string.ascii_letters,
    "digits": string.digits,
    "hex": string.hexdigits[:16],  # lowercase hex only (0-9a-f)
    "printable": "".join(c for c in string.printable if c.isprintable() and c != " "),
}


def generate_random_string(
    length: int,
    charset: str = "alphanumeric",
    *,
    seed_override: Optional[str] = None,
) -> str:
    """Generate a cryptographically secure random string.

    Args:
        length: Number of characters to produce.  Must be a positive integer.
        charset: Name of the character set to draw from.  Must be one of the
            keys in ``CHARSETS``.
        seed_override: When provided, a deterministic ``random.Random`` seeded
            with this value is used instead of the CSPRNG.  **For tests only.**

    Returns:
        A random string of exactly ``length`` characters.

    Raises:
        ValueError: If ``length`` is not positive, or ``charset`` is unknown.
    """
    if length <= 0:
        raise ValueError(f"String length must be a positive integer, got {length!r}.")

    if charset not in CHARSETS:
        raise ValueError(
            f"Unknown charset {charset!r}. "
            f"Valid options are: {sorted(CHARSETS.keys())}."
        )

    chars = CHARSETS[charset]

    if seed_override is not None:
        import random as _random

        rng = _random.Random(seed_override)
        result = "".join(rng.choice(chars) for _ in range(length))
        logger.debug(
            "Generated seeded string (length=%d, charset=%r, seed=%r).",
            length,
            charset,
            seed_override,
        )
    else:
        result = "".join(secrets.choice(chars) for _ in range(length))
        logger.debug(
            "Generated secure random string (length=%d, charset=%r).", length, charset
        )

    return result
