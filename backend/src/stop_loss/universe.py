"""The application universe: NSE tickers from data/processed, enriched with company metadata.

Symbols come from the per-ticker price files; names/sector/city come from
company_metadata_cleaned.json where available (absent fields stay None).
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from stop_loss.analytics.models import AssetProfile
from stop_loss.symbols import is_nse_symbol

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "processed"


@dataclass(frozen=True)
class Company:
    symbol: str
    name: str
    short_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    city: str | None = None
    country: str | None = None
    market_cap: float | None = None

    @property
    def base(self) -> str:
        return self.symbol.removesuffix(".NS")


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and value == value else None


def _present(info: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in info.items() if v not in (None, "")}


def _company(symbol: str, info: dict[str, Any]) -> Company:
    return Company(
        symbol=symbol,
        name=_text(info.get("longName")) or _text(info.get("shortName")) or symbol[:-3],
        short_name=_text(info.get("shortName")),
        sector=_text(info.get("sector")),
        industry=_text(info.get("industry")),
        city=_text(info.get("city")),
        country=_text(info.get("country")),
        market_cap=_number(info.get("marketCap")),
    )


def _as_info(company: Company) -> dict[str, Any]:
    """Inverse of _company for fields that came from the dataset (bare-ticker names excluded)."""
    return {
        "longName": company.name if company.name != company.symbol[:-3] else None,
        "shortName": company.short_name,
        "sector": company.sector,
        "industry": company.industry,
        "city": company.city,
        "country": company.country,
        "marketCap": company.market_cap,
    }


ENRICHED_FILE = "company_metadata_yfinance.json"


class NseUniverse:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.enriched_path = data_dir / "company_metadata_yfinance.json"
        yfinance_path = data_dir / "company_metadata_yfinance.json"
        yfinance_data: dict[str, dict[str, Any]] = {}
        if yfinance_path.exists():
            yfinance_data = json.loads(yfinance_path.read_text(encoding="utf-8"))

        metadata = yfinance_data
        self._enriched = yfinance_data
        self._lock = Lock()
        symbols = {path.stem.upper() for path in (data_dir / "nse_historical").glob("*.NS.csv")} | {
            symbol.upper() for symbol in metadata
        }
        self._companies: dict[str, Company] = {}
        for symbol in sorted(s for s in symbols if is_nse_symbol(s)):
            info = _present(yfinance_data.get(symbol) or {})
            self._companies[symbol] = _company(symbol, info)

    def __len__(self) -> int:
        return len(self._companies)

    def get(self, symbol: str) -> Company | None:
        return self._companies.get(symbol.strip().upper())

    def needs_profile(self, symbol: str) -> bool:
        company = self.get(symbol)
        return company is not None and (company.sector is None or company.city is None)

    def missing_profiles(self) -> list[str]:
        return [s for s in self._companies if self.needs_profile(s) and s not in self._enriched]

    def record_profile(self, profile: AssetProfile) -> Company | None:
        """Merge a live yfinance profile into the universe and persist it (fills gaps only)."""
        symbol = profile.symbol.upper()
        if symbol not in self._companies:
            return None
        fetched = {
            "longName": profile.long_name,
            "sector": profile.sector,
            "industry": profile.industry,
            "city": profile.city,
            "country": profile.country,
            "marketCap": profile.market_cap,
        }
        with self._lock:
            self._enriched[symbol] = {k: v for k, v in fetched.items() if v is not None}
            current = self._companies[symbol]
            merged = _company(symbol, {**self._enriched[symbol], **_present(_as_info(current))})
            self._companies[symbol] = merged
            tmp = self.enriched_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._enriched, indent=1, sort_keys=True), encoding="utf-8")
            tmp.replace(self.enriched_path)
        return merged

    async def ensure_profile(self, symbol: str, yahoo: Any) -> Company | None:
        """Company with sector/city, fetching the yfinance profile once if the data lacks it."""
        company = self.get(symbol)
        if company is None or not self.needs_profile(symbol) or symbol in self._enriched:
            return company
        try:
            profile = await yahoo.profile(symbol)
        except Exception:  # noqa: BLE001 - a missing profile leaves fields absent, never invented
            return company
        return self.record_profile(profile)

    def search(self, query: str, limit: int = 10) -> list[Company]:
        """Ranks exact ticker > ticker prefix > name prefix > word prefix > substring;
        ties go to larger market cap (known caps before unknown)."""
        q = query.strip().lower().removesuffix(".ns")
        if not q:
            return []
        scored: list[tuple[int, float, str, Company]] = []
        for company in self._companies.values():
            base, name = company.base.lower(), company.name.lower()
            haystack = " ".join(
                filter(
                    None,
                    [
                        name,
                        (company.short_name or "").lower(),
                        (company.sector or "").lower(),
                        (company.industry or "").lower(),
                    ],
                )
            )
            if base == q:
                rank = 0
            elif base.startswith(q):
                rank = 1
            elif name.startswith(q):
                rank = 2
            elif any(word.startswith(q) for word in name.split()):
                rank = 3
            elif q in base or q in haystack:
                rank = 4
            else:
                continue
            scored.append((rank, -(company.market_cap or -1.0), company.symbol, company))
        scored.sort(key=lambda row: row[:3])
        return [row[3] for row in scored[:limit]]


@lru_cache
def get_universe() -> NseUniverse:
    return NseUniverse()


def enrich_main() -> int:
    """`stop-loss-universe enrich [--limit N]`: fill missing sector/city/name via yfinance."""
    import argparse
    import asyncio

    from stop_loss.analytics.yfinance_client import YahooFinanceClient
    from stop_loss.settings import get_terminal_settings

    parser = argparse.ArgumentParser(prog="stop-loss-universe")
    parser.add_argument("command", choices=["enrich", "stats"])
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    universe = get_universe()
    missing = universe.missing_profiles()
    if args.command == "stats":
        print(f"{len(universe):,} NSE symbols; {len(missing):,} still lack a profile")
        return 0

    async def run() -> None:
        yahoo = YahooFinanceClient(get_terminal_settings())
        done = failed = 0
        try:
            for symbol in missing[: args.limit]:
                await universe.ensure_profile(symbol, yahoo)
                if symbol in universe._enriched:  # recorded (some fields may be absent)
                    done += 1
                else:
                    failed += 1
                if (done + failed) % 50 == 0:
                    total = len(missing[: args.limit])
                    print(f"  {done + failed:,}/{total:,} ({failed} without data)", flush=True)
        finally:
            await yahoo.aclose()
        print(f"enriched {done:,}; {failed:,} returned no profile")

    asyncio.run(run())
    return 0
