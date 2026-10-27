"""Language checks that enforce the specification's quality gates on wording."""

from __future__ import annotations

import re

CAUSAL_PATTERNS = [
    r"\bcauses?\b", r"\bcaused\b", r"\bcausing\b", r"\bdrives?\b", r"\bdriven by\b", r"\bleads? to\b", r"\bresults? in\b",
    r"\bincreases\b", r"\bdecreases\b", r"\bboosts?\b", r"\bmakes?\b (?:people|customers|tourists|them)\b",
    r"\bthe effect of\b", r"\bimpact of\b", r"\bdue to\b", r"\bbecause of\b",
    r"\bmenyebabkan\b", r"\bmengakibatkan\b", r"\bberdampak\b", r"\bmeningkatkan\b", r"\bmenurunkan\b", r"\bpengaruh\b",
]
CAUSAL_RE = re.compile("|".join(CAUSAL_PATTERNS), re.IGNORECASE)


def causal_terms(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in CAUSAL_RE.finditer(text or "")})


def suggest_associational(text: str) -> str:
    """Offer a safer rewording for common causal phrases."""
    replacements = {
        r"\bcauses\b": "is associated with", r"\bcause\b": "are associated with", r"\bdrives\b": "is associated with",
        r"\bleads to\b": "is associated with", r"\bresults in\b": "is associated with", r"\bincreases\b": "is associated with higher",
        r"\bdecreases\b": "is associated with lower", r"\bmeningkatkan\b": "berhubungan dengan peningkatan",
        r"\bmenyebabkan\b": "berhubungan dengan",
    }
    out = text
    for pattern, repl in replacements.items():
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    return out
