"use client";

import React from "react";
import { Badge, Skeleton, cn } from "@/components/ui/primitives";
import { formatCompact, formatNumber, formatPct, formatPrice, signClass } from "@/lib/format";
import type { HoldingRow, PortfolioTotals } from "@/components/portfolio/usePortfolioData";

export function PortfolioSummary({ totals, holdings, loading }: { totals: PortfolioTotals; holdings: number; loading: boolean }) {
  const tile = (label: string, body: React.ReactNode, note?: string) => (
    <div className="bg-white px-4 py-4 transition-colors hover:bg-canvas">
      <p className="font-mono text-2xs uppercase tracking-widest text-muted">{label}</p>
      <div className="mt-1">{loading ? <Skeleton className="h-6 w-28" /> : body}</div>
      {note && <p className="mt-0.5 font-mono text-2xs text-muted">{note}</p>}
    </div>
  );
  return (
    <div className="grid grid-cols-2 gap-px border border-line bg-line lg:grid-cols-4" data-testid="portfolio-summary">
      {tile(
        "Market value",
        <p className="num text-2xl font-bold tracking-tight text-ink">{formatPrice(totals.value, "INR", 0)}</p>,
        totals.pricedHoldings < holdings ? `${holdings - totals.pricedHoldings} holding(s) without a live price` : undefined,
      )}
      {tile(
        "Day change",
        <p className={cn("num text-2xl font-bold tracking-tight", signClass(totals.dayChange))}>
          {totals.dayChange !== undefined ? `${totals.dayChange >= 0 ? "+" : "−"}${formatPrice(Math.abs(totals.dayChange), "INR", 0)}` : "—"}
          <span className="ml-2 text-xs">{formatPct(totals.dayChangePct)}</span>
        </p>,
      )}
      {tile(
        "Unrealized P&L",
        <p className={cn("num text-2xl font-bold tracking-tight", signClass(totals.pnl))}>
          {totals.pnl !== undefined ? `${totals.pnl >= 0 ? "+" : "−"}${formatPrice(Math.abs(totals.pnl), "INR", 0)}` : "—"}
          {totals.pnl !== undefined && totals.costBasis ? (
            <span className="ml-2 text-xs">{formatPct((totals.pnl / totals.costBasis) * 100)}</span>
          ) : null}
        </p>,
        totals.costedHoldings < holdings
          ? `Based on ${totals.costedHoldings} of ${holdings} holdings with a buy price`
          : undefined,
      )}
      {tile("Stocks held", <p className="num text-2xl font-bold tracking-tight text-ink">{holdings}</p>, "NSE equities")}
    </div>
  );
}

export default function HoldingsTable({
  rows,
  selected,
  onSelect,
  loading,
}: {
  rows: HoldingRow[];
  selected: string | null;
  onSelect: (symbol: string) => void;
  loading: boolean;
}) {
  return (
    <div className="overflow-x-auto border border-line" data-testid="holdings-table">
      <table className="w-full min-w-[720px] text-left text-xs">
        <thead className="bg-canvas font-mono text-2xs uppercase tracking-wider text-muted">
          <tr>
            {["Stock", "Shares", "Price", "Day", "Value", "Weight", "P&L"].map((h, i) => (
              <th key={h} scope="col" className={cn("px-3 py-2", i > 0 && "text-right")}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row) => {
            const q = row.quote;
            const active = row.symbol === selected;
            return (
              <tr
                key={row.symbol}
                onClick={() => onSelect(row.symbol)}
                className={cn("cursor-pointer hover:bg-canvas", active && "bg-subtle")}
                aria-selected={active}
              >
                <td className="px-3 py-2">
                  <button type="button" onClick={() => onSelect(row.symbol)} className="text-left">
                    <span className="num block font-bold text-ink">{row.symbol.replace(/\.NS$/, "")}</span>
                    <span className="block max-w-[16rem] truncate text-2xs text-muted">
                      {q?.name ?? row.name}
                      {q?.sector && ` · ${q.sector}`}
                    </span>
                  </button>
                </td>
                <td className="num px-3 py-2 text-right">{formatNumber(row.quantity, 0)}</td>
                <td className="num px-3 py-2 text-right">
                  {loading && !q ? <Skeleton className="ml-auto h-3 w-16" /> : q?.status === "ok" ? formatPrice(q.price, "INR") : <Badge>n/a</Badge>}
                </td>
                <td className={cn("num px-3 py-2 text-right", signClass(q?.changePct))}>{formatPct(q?.changePct)}</td>
                <td className="num px-3 py-2 text-right">{formatCompact(row.value, "INR")}</td>
                <td className="num px-3 py-2 text-right">{row.weight !== undefined ? formatPct(row.weight, 1, false) : "—"}</td>
                <td className={cn("num px-3 py-2 text-right", signClass(row.pnl))}>
                  {row.pnl !== undefined ? (
                    <>
                      {formatCompact(row.pnl, "INR")}
                      <span className="block text-2xs">{formatPct(row.pnlPct)}</span>
                    </>
                  ) : (
                    <span className="text-muted-soft" title="Add an average buy price to see P&L">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
