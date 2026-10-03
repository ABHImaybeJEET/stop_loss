"""Keyword tagging for the four first-class macro themes (AGENTS.md section 2)."""

import re

from fin_terminal.schemas import Theme

THEME_KEYWORDS: dict[Theme, tuple[str, ...]] = {
    Theme.TARIFF: (
        "tariff",
        "duties",
        "import duty",
        "export duty",
        "export control",
        "trade war",
        "anti-dumping",
        "customs",
        "import ban",
        "trade deal",
        "trade talks",
        "quota",
        "supply chain",
    ),
    Theme.BANK_TAX: (
        "windfall tax",
        "bank levy",
        "bank tax",
        "capital requirement",
        "reserve requirement",
        "crr",
        "repo rate",
        "rate hike",
        "rate cut",
        "interest rate",
        "central bank",
        "rbi",
        "federal reserve",
        "the fed",
        "fed ",
        "ecb",
        "monetary policy",
        "basel",
    ),
    Theme.WAR_CRISIS: (
        "war",
        "conflict",
        "sanction",
        "missile",
        "airstrike",
        "invasion",
        "strait of hormuz",
        "red sea",
        "blockade",
        "geopolitic",
        "military",
        "ceasefire",
        "attack",
        "embargo",
        "opec",
        "pipeline disruption",
    ),
    Theme.WEATHER_EXTREME: (
        "hurricane",
        "cyclone",
        "typhoon",
        "flood",
        "storm",
        "heatwave",
        "heat wave",
        "cold snap",
        "freeze",
        "drought",
        "monsoon",
        "wildfire",
        "landfall",
        "el nino",
        "la nina",
    ),
}

_PATTERNS = {
    theme: re.compile(r"\b(" + "|".join(re.escape(k.strip()) for k in words) + r")", re.I)
    for theme, words in THEME_KEYWORDS.items()
}


def tag_themes(*texts: str | None) -> list[Theme]:
    blob = " ".join(t for t in texts if t)
    return sorted(theme for theme, pattern in _PATTERNS.items() if pattern.search(blob))
