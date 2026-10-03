"use client";

import useSWR from "swr";
import {
  fetchHoldingQuotes,
  fetchPortfolioNews,
  fetchPortfolioPerformance,
  fetchPortfolioWeather,
} from "@/lib/portfolio/api";
import type { Holding, HoldingQuote } from "@/lib/portfolio/types";

const QUOTE_POLL_OPEN_MS = 30_000;
const NEWS_POLL_MS = 10 * 60_000;
const WEATHER_POLL_MS = 30 * 60_000;

/** Live dashboard data for the holdings. Quotes poll only while NSE is open and the tab is
 *  visible (SWR pauses hidden tabs); slower feeds refresh on their own cadence. */
export function usePortfolioData(holdings: Holding[], range: string) {
  const symbols = holdings.map((h) => h.symbol).sort();
  const key = symbols.join(",");
  const quotes = useSWR(key ? ["pf-quotes", key] : null, () => fetchHoldingQuotes(symbols), {
    refreshInterval: (latest?: HoldingQuote[]) =>
      latest?.some((q) => q.marketState === "open") ? QUOTE_POLL_OPEN_MS : 0,
    refreshWhenHidden: false,
    keepPreviousData: true,
  });
  const news = useSWR(key ? ["pf-news", key] : null, () => fetchPortfolioNews(symbols), {
    refreshInterval: NEWS_POLL_MS,
    revalidateOnFocus: false,
    keepPreviousData: true,
  });
  const weather = useSWR(key ? ["pf-weather", key] : null, () => fetchPortfolioWeather(symbols), {
    refreshInterval: WEATHER_POLL_MS,
    revalidateOnFocus: false,
    keepPreviousData: true,
  });
  const holdingsKey = holdings.map((h) => `${h.symbol}:${h.quantity}`).sort().join(",");
  const performance = useSWR(
    holdingsKey ? ["pf-perf", holdingsKey, range] : null,
    () => fetchPortfolioPerformance(holdings, range),
    { revalidateOnFocus: false, keepPreviousData: true },
  );
  return { quotes, news, weather, performance };
}

export interface HoldingRow extends Holding {
  quote?: HoldingQuote;
  value?: number;
  dayChange?: number;
  weight?: number;
  pnl?: number;
  pnlPct?: number;
}

export interface PortfolioTotals {
  value?: number;
  dayChange?: number;
  dayChangePct?: number;
  pnl?: number;
  costBasis?: number;
  pricedHoldings: number;
  costedHoldings: number;
}

/** Combines holdings with live quotes. Holdings without a live price are left out of
 *  totals (and reported), never valued at a guessed price. */
export function combine(holdings: Holding[], quotes: HoldingQuote[] | undefined): { rows: HoldingRow[]; totals: PortfolioTotals } {
  const bySymbol = new Map((quotes ?? []).map((q) => [q.symbol, q]));
  const rows: HoldingRow[] = holdings.map((h) => {
    const quote = bySymbol.get(h.symbol);
    const price = quote?.status === "ok" ? quote.price : undefined;
    const value = price !== undefined ? price * h.quantity : undefined;
    const dayChange =
      price !== undefined && quote?.previousClose ? (price - quote.previousClose) * h.quantity : undefined;
    const pnl = value !== undefined && h.avgPrice ? value - h.avgPrice * h.quantity : undefined;
    return { ...h, quote, value, dayChange, pnl, pnlPct: pnl !== undefined && h.avgPrice ? (pnl / (h.avgPrice * h.quantity)) * 100 : undefined };
  });
  const priced = rows.filter((r) => r.value !== undefined);
  const value = priced.length ? priced.reduce((s, r) => s + (r.value ?? 0), 0) : undefined;
  for (const row of rows) row.weight = value && row.value !== undefined ? (row.value / value) * 100 : undefined;
  const withDay = priced.filter((r) => r.dayChange !== undefined);
  const dayChange = withDay.length ? withDay.reduce((s, r) => s + (r.dayChange ?? 0), 0) : undefined;
  const costed = rows.filter((r) => r.pnl !== undefined);
  const pnl = costed.length ? costed.reduce((s, r) => s + (r.pnl ?? 0), 0) : undefined;
  const costBasis = costed.length ? costed.reduce((s, r) => s + (r.avgPrice ?? 0) * r.quantity, 0) : undefined;
  return {
    rows,
    totals: {
      value,
      dayChange,
      dayChangePct: value !== undefined && dayChange !== undefined ? (dayChange / (value - dayChange)) * 100 : undefined,
      pnl,
      costBasis,
      pricedHoldings: priced.length,
      costedHoldings: costed.length,
    },
  };
}
