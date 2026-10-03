"""Application universe: NSE-listed securities and explicit NSE benchmarks."""

import re

NSE_INDICES = frozenset({"^NSEI", "^NSEBANK", "^CNXIT", "^CNX100", "^CNX200"})
NSE_EQUITY = re.compile(r"^[A-Z0-9][A-Z0-9&_-]{0,29}\.NS$")


def nse_symbol(value: str, *, allow_index: bool = True) -> str:
    symbol = value.strip().upper()
    if NSE_EQUITY.fullmatch(symbol) or (allow_index and symbol in NSE_INDICES):
        return symbol
    raise ValueError("NSE symbols only: use the .NS suffix (for example RELIANCE.NS)")


def is_nse_symbol(value: str) -> bool:
    try:
        nse_symbol(value)
    except ValueError:
        return False
    return True


# Macro reference series fetched through yfinance (not tradable app assets): USD/INR,
# Brent crude and India VIX. User-facing endpoints still accept NSE symbols only.
MACRO_REFERENCE = frozenset({"INR=X", "BZ=F", "^INDIAVIX"})


def market_symbol(value: str) -> str:
    """NSE equities, NSE indices, or an allow-listed macro reference series."""
    symbol = value.strip().upper()
    return symbol if symbol in MACRO_REFERENCE else nse_symbol(symbol)
