"""Quantitative risk metrics computed only from observed closes (no gap filling).

Conventions: returns and drawdowns are fractions (0.05 == 5%); VaR/CVaR are positive
loss fractions from historical simulation; volatility is annualized.
"""

import math
from collections import defaultdict
from datetime import date, datetime

import numpy as np

from stop_loss.analytics.models import (
    Bar,
    ChartSeries,
    QuantMetrics,
    SeasonalityPoint,
    SeriesPoint,
    VarPoint,
)

TRADING_DAYS = 252
CRYPTO_DAYS = 365
VAR_LEVELS = (0.90, 0.95, 0.975, 0.99)


def closes_of(bars: list[Bar]) -> tuple[list[datetime], list[float]]:
    pairs = [(b.t, b.close) for b in bars if b.close is not None and b.close > 0]
    return [p[0] for p in pairs], [float(p[1]) for p in pairs]


def simple_returns(closes: list[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]


def annualized_volatility(returns: list[float], periods: int) -> float | None:
    if len(returns) < 10:
        return None
    return float(np.std(returns, ddof=1) * math.sqrt(periods))


def historical_var(returns: list[float], confidence: float) -> tuple[float, float] | None:
    """Returns (VaR, CVaR) as positive loss fractions; needs >= 60 observations."""
    if len(returns) < 60:
        return None
    arr = np.asarray(returns)
    cutoff = float(np.quantile(arr, 1 - confidence))
    tail = arr[arr <= cutoff]
    cvar = float(-tail.mean()) if tail.size else -cutoff
    return max(-cutoff, 0.0), max(cvar, 0.0)


def drawdowns(closes: list[float]) -> list[float]:
    peak = -math.inf
    out: list[float] = []
    for close in closes:
        peak = max(peak, close)
        out.append(close / peak - 1)
    return out


def max_drawdown(closes: list[float]) -> float | None:
    return min(drawdowns(closes)) if len(closes) >= 2 else None


def period_return(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    return closes[-1] / closes[-1 - lookback] - 1


def sma(closes: list[float], window: int) -> float | None:
    return float(np.mean(closes[-window:])) if len(closes) >= window else None


def beta(
    asset: tuple[list[datetime], list[float]], bench: tuple[list[datetime], list[float]]
) -> float | None:
    """Beta of daily returns, aligned on calendar dates both series traded."""
    a_ret = _returns_by_date(*asset)
    b_ret = _returns_by_date(*bench)
    common = sorted(set(a_ret) & set(b_ret))
    if len(common) < 60:
        return None
    x = np.asarray([b_ret[d] for d in common])
    y = np.asarray([a_ret[d] for d in common])
    var = float(np.var(x, ddof=1))
    if var == 0:
        return None
    return float(np.cov(y, x, ddof=1)[0, 1] / var)


def _returns_by_date(dates: list[datetime], closes: list[float]) -> dict[date, float]:
    return {dates[i].date(): closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))}


def monthly_seasonality(dates: list[datetime], closes: list[float]) -> list[SeasonalityPoint]:
    """Average calendar-month return using each month's last observed close."""
    month_end: dict[tuple[int, int], float] = {}
    for when, close in zip(dates, closes, strict=True):
        month_end[(when.year, when.month)] = close
    keys = sorted(month_end)
    buckets: dict[int, list[float]] = defaultdict(list)
    for prev, cur in zip(keys, keys[1:], strict=False):
        buckets[cur[1]].append(month_end[cur] / month_end[prev] - 1)
    return [
        SeasonalityPoint(month=m, avg_return=float(np.mean(v)), observations=len(v))
        for m, v in sorted(buckets.items())
        if len(v) >= 2
    ]


def sampled_drawdown_series(
    dates: list[datetime], closes: list[float], max_points: int = 260
) -> list[SeriesPoint]:
    series = drawdowns(closes)
    step = max(1, math.ceil(len(series) / max_points))
    idx = list(range(0, len(series), step))
    if idx and idx[-1] != len(series) - 1:
        idx.append(len(series) - 1)
    return [SeriesPoint(date=dates[i], value=series[i]) for i in idx]


def trend_label(price: float | None, sma50: float | None, sma200: float | None) -> str | None:
    if price is None or sma50 is None or sma200 is None:
        return None
    if price > sma50 > sma200:
        return "uptrend"
    if price < sma50 < sma200:
        return "downtrend"
    return "sideways"


def compute_quant_metrics(daily: ChartSeries, benchmark: ChartSeries | None = None) -> QuantMetrics:
    """`daily` should be a multi-year 1d series (5y gives drawdown and seasonality depth)."""
    dates, closes = closes_of(daily.bars)
    crypto = (daily.instrument_type or "").upper() == "CRYPTOCURRENCY"
    periods = CRYPTO_DAYS if crypto else TRADING_DAYS
    returns = simple_returns(closes)
    one_year = returns[-periods:]
    year_closes = closes[-(periods + 1) :]
    var95 = historical_var(one_year, 0.95)
    sensitivity = [
        VarPoint(confidence=c, var=v[0], cvar=v[1])
        for c in VAR_LEVELS
        if (v := historical_var(one_year, c)) is not None
    ]
    sma50, sma200 = sma(closes, 50), sma(closes, 200)
    last = closes[-1] if closes else None
    bench_beta = None
    if benchmark is not None:
        b_dates, b_closes = closes_of(benchmark.bars)
        cutoff = len(dates) - periods
        bench_beta = beta((dates[max(cutoff, 0) :], closes[max(cutoff, 0) :]), (b_dates, b_closes))
    year_dates = dates[-(periods + 1) :]
    return QuantMetrics(
        as_of=dates[-1] if dates else None,
        observations=len(closes),
        periods_per_year=periods,
        return_1m=period_return(closes, round(periods / 12)),
        return_3m=period_return(closes, round(periods / 4)),
        return_6m=period_return(closes, round(periods / 2)),
        return_1y=period_return(closes, periods),
        return_5y=(closes[-1] / closes[0] - 1) if len(closes) > periods * 4 else None,
        vol_30d=annualized_volatility(returns[-21:], periods) if len(returns) >= 21 else None,
        vol_1y=annualized_volatility(one_year, periods),
        var_95_1d=var95[0] if var95 else None,
        cvar_95_1d=var95[1] if var95 else None,
        var_sensitivity=sensitivity,
        max_drawdown_1y=max_drawdown(year_closes),
        max_drawdown_5y=max_drawdown(closes) if len(closes) > periods * 4 else None,
        current_drawdown=drawdowns(closes)[-1] if closes else None,
        beta_1y=bench_beta,
        benchmark_symbol=benchmark.symbol
        if benchmark is not None and bench_beta is not None
        else None,
        sma_50=sma50,
        sma_200=sma200,
        trend=trend_label(last, sma50, sma200),
        best_day=max(one_year) if one_year else None,
        worst_day=min(one_year) if one_year else None,
        seasonality=monthly_seasonality(dates, closes),
        drawdown_series=sampled_drawdown_series(year_dates, year_closes),
    )


def benchmark_for(symbol: str, quote_type: str | None) -> str | None:
    upper = symbol.upper()
    if (quote_type or "").upper() in {"CRYPTOCURRENCY", "INDEX", "CURRENCY", "FUTURE"}:
        return None
    if upper.endswith(".NS"):
        return "^NSEI"
    return None
