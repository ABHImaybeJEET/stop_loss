"use client";

import React from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Skeleton, cn } from "@/components/ui/primitives";
import { formatPct, formatPrice } from "@/lib/format";
import type { PortfolioPerformance } from "@/lib/portfolio/types";

export const PERFORMANCE_RANGES = [
  ["1mo", "1M"],
  ["3mo", "3M"],
  ["6mo", "6M"],
  ["1y", "1Y"],
] as const;

export default function PerformanceChart({
  data,
  range,
  onRange,
  error,
}: {
  data?: PortfolioPerformance;
  range: string;
  onRange: (r: string) => void;
  error?: unknown;
}) {
  const points = (data?.dates ?? []).map((d, i) => ({
    date: d,
    portfolio: data!.portfolio[i],
    nifty: data!.nifty[i] ?? undefined,
    value: data!.value[i],
  }));
  const last = points.at(-1);
  const summary =
    last !== undefined
      ? `Portfolio ${formatPct(last.portfolio - 100)} vs NIFTY 50 ${formatPct(last.nifty !== undefined ? last.nifty - 100 : undefined)} over the period`
      : "";
  return (
    <section className="border border-line bg-white" aria-labelledby="perf-title">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <h3 id="perf-title" className="font-mono text-2xs font-bold uppercase tracking-widest text-ink">
          Portfolio vs NIFTY 50
        </h3>
        <div role="group" aria-label="Performance range" className="flex border border-line">
          {PERFORMANCE_RANGES.map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={range === value}
              onClick={() => onRange(value)}
              className={cn("num h-7 min-w-[2.5rem] border-r border-line px-2 text-2xs font-semibold last:border-r-0", range === value ? "bg-ink text-white" : "text-muted hover:text-ink")}
            >
              {label}
            </button>
          ))}
        </div>
      </header>
      <div className="p-3">
        {error && !data ? (
          <p className="py-16 text-center font-mono text-2xs text-loss">Performance history unavailable right now.</p>
        ) : !data ? (
          <Skeleton className="h-56 w-full" />
        ) : points.length < 2 ? (
          <p className="py-16 text-center font-mono text-2xs text-muted">Not enough shared trading history for these holdings.</p>
        ) : (
          <figure aria-label={summary}>
            <p className="mb-1 font-mono text-2xs text-muted">{summary} · indexed to 100</p>
            <div className="h-56 w-full" aria-hidden="true">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={points} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
                  <CartesianGrid stroke="#EAEAEA" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fontFamily: "monospace", fill: "#6B6A66" }} tickLine={false} axisLine={false} minTickGap={40} tickFormatter={(d: string) => d.slice(5)} />
                  <YAxis domain={["auto", "auto"]} tick={{ fontSize: 9, fontFamily: "monospace", fill: "#6B6A66" }} tickLine={false} axisLine={false} width={40} />
                  <Tooltip
                    contentStyle={{ fontSize: 11, fontFamily: "monospace", border: "1px solid #111", borderRadius: 0 }}
                    formatter={(v: number, name: string, item) =>
                      name === "Portfolio" ? [`${v.toFixed(1)} (${formatPrice(item.payload.value, "INR", 0)})`, name] : [v.toFixed(1), name]
                    }
                  />
                  <Legend wrapperStyle={{ fontSize: 10, fontFamily: "monospace" }} iconSize={8} />
                  <Line type="monotone" dataKey="portfolio" name="Portfolio" stroke="#111111" strokeWidth={1.75} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="nifty" name="NIFTY 50" stroke="#A1A09A" strokeWidth={1.25} strokeDasharray="4 3" dot={false} connectNulls={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {data.excluded.length > 0 && (
              <figcaption className="mt-1 font-mono text-2xs text-muted">No history for: {data.excluded.join(", ")} (excluded)</figcaption>
            )}
          </figure>
        )}
      </div>
    </section>
  );
}
