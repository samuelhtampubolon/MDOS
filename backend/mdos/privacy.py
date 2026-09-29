"""Personal data minimization for text that leaves this server.

Claude only needs the meaning of survey answers and reviews, never who wrote them. Before a prompt is sent,
email addresses, phone numbers and 16-digit Indonesian ID numbers (NIK) are replaced with placeholders. The
patterns are deliberately narrow so prices, sample sizes, dates and statistics pass through unchanged.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
# Indonesian mobile numbers: 08xx, 628xx or +628xx, with optional spaces, dots or dashes between groups.
_PHONE_ID = re.compile(r"(?<![\w+])(?:\+62|62|0)8\d{1,2}(?:[\s.\-]?\d{2,4}){2,3}(?!\w)")
# Other international numbers must start with + and a country code.
_PHONE_INTL = re.compile(r"(?<![\w+])\+[1-9]\d{0,2}(?:[\s.\-]?\(?\d{2,4}\)?){2,5}(?!\w)")
_NIK = re.compile(r"(?<!\d)\d{16}(?!\d)")


def _phone(match: re.Match[str]) -> str:
    digits = sum(ch.isdigit() for ch in match.group(0))
    return "[phone]" if 9 <= digits <= 15 else match.group(0)  # "+15.2 (95% CI" stays a statistic


def mask_pii(text: str) -> tuple[str, int]:
    """Return the text with personal identifiers replaced, and how many were replaced."""
    masked = _EMAIL.sub("[email]", text)
    masked = _PHONE_ID.sub(_phone, masked)
    masked = _PHONE_INTL.sub(_phone, masked)
    masked = _NIK.sub("[id number]", masked)
    count = sum(masked.count(tag) - text.count(tag) for tag in ("[email]", "[phone]", "[id number]"))
    return masked, count
