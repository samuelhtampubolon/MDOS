"""Guards around model-written text: untrusted-data delimiting and the numeric grounding check."""

from __future__ import annotations

import re
from collections.abc import Iterable

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NUMBER_RE = re.compile(r"(?<![\w.])(?:rp\s?)?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?(?:\s?%)?|(?<![\w.])(?:rp\s?)?\d+(?:[.,]\d+)?(?:\s?%)?",
                       re.IGNORECASE)
SMALL_INTEGERS = {str(i) for i in range(0, 13)}  # counts such as "two segments" or "5-point scale" in digits


def wrap_untrusted(text: str, limit: int = 4000) -> str:
    """Delimit user or customer text so the model treats it as data."""
    clean = CONTROL_RE.sub(" ", text or "")
    clean = clean.replace("<untrusted_data>", "").replace("</untrusted_data>", "")
    if len(clean) > limit:
        clean = clean[:limit] + " [truncated]"
    return f"<untrusted_data>\n{clean}\n</untrusted_data>"


def _normalize(token: str) -> set[str]:
    t = token.lower().replace("rp", "").replace(" ", "")
    pct = t.endswith("%")
    t = t.rstrip("%")
    variants: set[str] = set()
    candidates = {t}
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", t):
        candidates.add(re.sub(r"[.,]", "", t))
    else:
        candidates.add(t.replace(",", "."))
    for c in candidates:
        try:
            value = float(c)
        except ValueError:
            continue
        variants.add(_key(value))
        if pct:
            variants.add(_key(value / 100))
    return variants


def _key(value: float) -> str:
    return f"{value:.6g}"


def allowed_numbers(values: Iterable[float | int | str | None]) -> set[str]:
    """All acceptable renderings of the context's numbers (raw, rounded, percent)."""
    out: set[str] = set()
    for v in values:
        if v is None:
            continue
        if isinstance(v, str):
            for token in NUMBER_RE.findall(v):
                out |= _normalize(token)
            continue
        f = float(v)
        for digits in (0, 1, 2, 3):
            out.add(_key(round(f, digits)))
            out.add(_key(round(f * 100, digits)))
            out.add(_key(round(f / 1000, digits)))
            out.add(_key(round(f / 1_000_000, digits)))
    return out


def ungrounded_numbers(text: str, allowed: set[str]) -> list[str]:
    """Numbers in ``text`` that do not match any number in the context."""
    missing = []
    for token in NUMBER_RE.findall(text or ""):
        bare = token.strip().rstrip("%").strip()
        if bare in SMALL_INTEGERS:
            continue
        if not (_normalize(token) & allowed):
            missing.append(token.strip())
    return missing
