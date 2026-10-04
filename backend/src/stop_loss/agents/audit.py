"""Figure verification: every number in generated text must match recorded evidence."""

import re

from stop_loss.agents.models import EvidenceItem

NUMBER = re.compile(
    r"(?<![A-Za-z\d.])(?:[₹$€£¥])?(-?\d[\d,]*(?:\.\d+)?)\s*"
    r"(%|(?:trillion|billion|million|crore|lakh|tn|bn|mn|cr|[TBMK])(?![A-Za-z]))?"
    r"(?!-[A-Za-z])"
    r"(?:\s+(days?|weeks?|months?|years?|sessions?|yrs?)\b)?",
    re.I,
)
SCALE = {
    "t": 1e12,
    "trillion": 1e12,
    "tn": 1e12,
    "b": 1e9,
    "billion": 1e9,
    "bn": 1e9,
    "m": 1e6,
    "million": 1e6,
    "mn": 1e6,
    "k": 1e3,
    "crore": 1e7,
    "cr": 1e7,
    "lakh": 1e5,
}
EVIDENCE_REF = re.compile(r"\[E?\d+(?:[\s,]+E?\d+)*\]|\bE\d+\b", re.I)


def _matches(value: float, candidates: list[float]) -> bool:
    for cand in candidates:
        tol = max(0.051, abs(cand) * 0.005)
        if abs(abs(value) - abs(cand)) <= tol:
            return True
    return False


def extract_figures(text: str) -> list[tuple[str, float]]:
    """Returns (raw, value) for figures that assert a fact; skips ids, years, horizons, counts."""
    figures: list[tuple[str, float]] = []
    for match in NUMBER.finditer(EVIDENCE_REF.sub(" ", text)):
        raw, unit, period = match.group(1), (match.group(2) or ""), match.group(3)
        if period:
            continue  # "6 months", "5 days": horizons, not market facts
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if not unit and float(value).is_integer() and (abs(value) <= 12 or 1900 <= value <= 2100):
            continue  # small counts / list sizes / calendar years
        scale = SCALE.get(unit.lower(), 1.0) if unit != "%" else 1.0
        figures.append((match.group(0).strip(), value * scale))
    return figures


def verify_figures(
    texts: list[str], evidence: list[EvidenceItem], allowed_text: str = ""
) -> tuple[int, list[str]]:
    """Returns (figures checked, unverified raw figures). `allowed_text` (the user's prompt)
    may introduce its own numbers, which the narrative is free to repeat."""
    candidates = [float(e.value) for e in evidence if isinstance(e.value, (int, float))]
    # Figures inside evidence labels ("1-day 95% VaR", "200-day average") are definitional.
    labels = " ".join(e.label for e in evidence)
    # Figures copied verbatim from an evidence item's display (e.g. a scenario's range) are
    # evidence too, not new numbers.
    displays = " ".join(e.display for e in evidence)
    candidates += [v for _, v in extract_figures(f"{allowed_text} {labels} {displays}")]
    checked, unverified = 0, []
    for text in texts:
        for raw, value in extract_figures(text):
            checked += 1
            if not _matches(value, candidates) and raw not in unverified:
                unverified.append(raw)
    return checked, unverified
