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
