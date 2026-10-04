"""Local historical price metrics for analog events."""

import pandas as pd
from pathlib import Path
from typing import Any

from stop_loss.symbols import nse_symbol

def measure_forward_returns(symbol: str, event_date_str: str, nse_dir: Path) -> dict[str, float | None]:
    """Calculate forward returns from a specific event date."""
    try:
        sym = nse_symbol(symbol)
    except ValueError:
        return {"forward_5d": None, "forward_20d": None}
        
    filepath = nse_dir / f"{sym}.csv"
    if not filepath.exists():
        return {"forward_5d": None, "forward_20d": None}

    try:
        df = pd.read_csv(filepath)
        df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_localize(None).dt.normalize()
        event_date = pd.to_datetime(event_date_str, utc=True).tz_localize(None).normalize()
        
        df_after = df[df["Date"] >= event_date].reset_index(drop=True)
        if df_after.empty:
            return {"forward_5d": None, "forward_20d": None}
            
        start_price = df_after.loc[0, "Close"]
        
        res: dict[str, float | None] = {"forward_5d": None, "forward_20d": None}
        
        if len(df_after) > 5:
            price_5d = df_after.loc[5, "Close"]
            res["forward_5d"] = float((price_5d - start_price) / start_price)
            
        if len(df_after) > 20:
            price_20d = df_after.loc[20, "Close"]
            res["forward_20d"] = float((price_20d - start_price) / start_price)
            
        return res
    except Exception:
        return {"forward_5d": None, "forward_20d": None}
