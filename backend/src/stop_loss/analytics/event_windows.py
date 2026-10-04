"""Forward returns after historical event dates, from the local daily price files.

Reads data/processed/{nse_historical,macro_historical} once per symbol (cached), so a
portfolio of holdings x analog events costs no network calls. Missing files or dates
yield None, never an estimate.
"""

import csv
import statistics
from bisect import bisect_left
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

# Channel series kept in macro_historical (file stem -> yfinance-style symbol).
CHANNEL_FILES = {"BZ=F": "BZ_F", "^NSEI": "NSEI", "INR=X": "INR_X", "CL=F": "CL_F"}


def series_path(symbol: str, datasets_dir: Path) -> Path:
    if symbol in CHANNEL_FILES:
        return datasets_dir / "macro_historical" / f"{CHANNEL_FILES[symbol]}.csv"
    return datasets_dir / "nse_historical" / f"{symbol}.csv"


@lru_cache(maxsize=256)
def _load(path: str) -> tuple[tuple[date, ...], tuple[float, ...]]:
    dates: list[date] = []
    closes: list[float] = []
    file = Path(path)
    if not file.exists():
        return (), ()
    with file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                day = datetime.fromisoformat(row["Date"].strip()).date()
                close = float(row["Close"])
            except (KeyError, TypeError, ValueError):
                continue
            if close > 0:
                dates.append(day)
                closes.append(close)
    order = sorted(range(len(dates)), key=dates.__getitem__)
    return tuple(dates[i] for i in order), tuple(closes[i] for i in order)


def forward_return(symbol: str, event_day: date, sessions: int, datasets_dir: Path) -> float | None:
    """Close `sessions` trading days after the first session on/after event_day, vs that
    session's close. None when the series does not cover the window."""
    dates, closes = _load(str(series_path(symbol, datasets_dir)))
    if not dates:
        return None
    start = bisect_left(dates, event_day)
    end = start + sessions
    if start >= len(dates) or end >= len(dates):
        return None
    if (dates[start] - event_day).days > 7:  # no trading near the event: not comparable
        return None
    return closes[end] / closes[start] - 1


def aggregate(values: list[float | None]) -> dict[str, float | int | None]:
    observed = [v for v in values if v is not None]
    if not observed:
        return {"n": 0, "median": None, "min": None, "max": None, "share_negative": None}
    return {
        "n": len(observed),
        "median": statistics.median(observed),
        "min": min(observed),
        "max": max(observed),
        "share_negative": sum(1 for v in observed if v < 0) / len(observed),
    }
