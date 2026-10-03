"use client";

import React, { useMemo, useState } from "react";
import useSWR from "swr";
import { LineChart as LineChartIcon, RotateCw } from "lucide-react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from "recharts";
import { fetchChart, fetchQuote } from "@/lib/chat/api";
import { Badge, Button, SectionCard, Skeleton, cn } from "@/components/ui/primitives";
import { formatCompact, formatPct, formatPrice, signClass } from "@/lib/format";
import type { AssetRef, ChartSeries } from "@/lib/chat/types";

const RANGES = ["1D", "5D", "1M", "6M", "1Y", "5Y"] as const;
type Range = (typeof RANGES)[number];
const INTRADAY: Range[] = ["1D", "5D"];
const QUOTE_POLL_MS = 10_000;
const CHART_POLL_MS = 60_000;
const GAIN = "#047857";
const LOSS = "#BE123C";

interface Point {
  t: number;
  close: number;
  open?: number;
  high?: number;
  low?: number;
  volume?: number;
  live?: boolean;
}

function timeFormatter(range: Range, timeZone?: string) {
  const opts: Intl.DateTimeFormatOptions =
    range === "1D"
      ? { hour: "2-digit", minute: "2-digit", hour12: false }
      : range === "5D"
        ? { weekday: "short", hour: "2-digit", hour12: false }
        : range === "5Y"
          ? { month: "short", year: "2-digit" }
          : { month: "short", day: "numeric" };
  try {
    return new Intl.DateTimeFormat("en-US", { ...opts, timeZone });
  } catch {
    return new Intl.DateTimeFormat("en-US", opts);
  }
}

function fullTime(t: number, timeZone?: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short", timeZone }).format(t);
  } catch {
    return new Date(t).toLocaleString();
  }
}

function ChartTooltip({ active, payload, currency, timeZone }: TooltipProps<number, string> & { currency?: string; timeZone?: string }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload as Point;
  const row = (label: string, value: string) => (
    <div className="flex justify-between gap-4">
      <span className="text-muted">{label}</span>
      <span className="num text-ink">{value}</span>
    </div>
  );
  return (
    <div className="min-w-[10rem] border border-ink bg-white px-2.5 py-2 font-mono text-2xs shadow-sm">
      <p className="mb-1 font-semibold text-ink">
        {fullTime(p.t, timeZone)}
        {p.live && " · live"}
      </p>
      {p.open !== undefined && row("Open", formatPrice(p.open, currency))}
      {p.high !== undefined && row("High", formatPrice(p.high, currency))}
      {p.low !== undefined && row("Low", formatPrice(p.low, currency))}
      {row("Close", formatPrice(p.close, currency))}
      {p.volume !== undefined && row("Volume", formatCompact(p.volume))}
    </div>
  );
}

export default function AssetLiveChart({ asset }: { asset: AssetRef }) {
  const [range, setRange] = useState<Range>("1D");
  const [hovering, setHovering] = useState(false);
  const chart = useSWR<ChartSeries>(["chart", asset.symbol, range], () => fetchChart(asset.symbol, range), {
    revalidateOnFocus: false,
    keepPreviousData: true,
    refreshInterval: (latest) => (latest?.marketState === "open" && INTRADAY.includes(range) ? CHART_POLL_MS : 0),
  });
  const marketOpen = chart.data?.marketState === "open";
  // Polls only while the market is open; SWR pauses refresh while the tab is hidden.
  const quote = useSWR(marketOpen ? ["quote", asset.symbol] : null, () => fetchQuote(asset.symbol), {
    refreshInterval: QUOTE_POLL_MS,
    refreshWhenHidden: false,
    revalidateOnFocus: true,
  });

  const series = chart.data;
  const points = useMemo<Point[]>(() => {
    if (!series) return [];
    const base: Point[] = series.bars.map((b) => ({ t: b.t, close: b.close, open: b.open, high: b.high, low: b.low, volume: b.volume }));
    const q = quote.data;
    const qTime = q?.marketTime ? Date.parse(q.marketTime) : NaN;
    if (INTRADAY.includes(range) && q?.price !== undefined && Number.isFinite(qTime) && base.length && qTime > base[base.length - 1].t) {
      base.push({ t: qTime, close: q.price, live: true });
    }
    return base;
  }, [series, quote.data, range]);

  const reference = INTRADAY.includes(range) ? (series?.previousClose ?? undefined) : points[0]?.close;
  const last = points.at(-1)?.close;
  const change = last !== undefined && reference ? ((last - reference) / reference) * 100 : undefined;
  const color = change === undefined || change >= 0 ? GAIN : LOSS;
  const fmt = timeFormatter(range, series?.exchangeTimezone);
  const updatedAt = quote.data?.fetchedAt ?? (series ? new Date().toISOString() : undefined);
  const gradientId = `fill-${asset.symbol.replace(/[^A-Za-z0-9]/g, "")}`;
  const summary =
    last !== undefined
      ? `${asset.symbol} ${range} chart: last ${formatPrice(last, series?.currency)}, ${formatPct(change)} versus ${
          INTRADAY.includes(range) ? "previous close" : "start of range"
        }, ${points.length} data points.`
      : "";

  return (
    <SectionCard
      id={`chart-${asset.symbol}`}
      title="Live Chart"
      icon={<LineChartIcon className="h-3.5 w-3.5" aria-hidden="true" />}
      aside={
        <span className="flex items-center gap-2">
          {series &&
            (marketOpen ? (
              <Badge tone="gain" aria-label="Live: market open, auto-updating">
                <span className="sl-pulse h-1.5 w-1.5 rounded-full bg-gain" aria-hidden="true" /> Live
              </Badge>
            ) : (
              <Badge>Market {series.marketState === "closed" ? "closed" : series.marketState}</Badge>
            ))}
        </span>
      }
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div role="group" aria-label="Chart range" className="flex border border-line">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRange(r)}
              aria-pressed={range === r}
              className={cn(
                "num h-7 min-w-[2.5rem] border-r border-line px-2 text-2xs font-semibold last:border-r-0",
                range === r ? "bg-ink text-white" : "bg-white text-muted hover:text-ink",
              )}
            >
              {r}
            </button>
          ))}
        </div>
        <div className="text-right">
          {last !== undefined && (
            <p className="num text-xs font-semibold text-ink">
              {formatPrice(last, series?.currency)} <span className={signClass(change)}>{formatPct(change)}</span>
            </p>
          )}
          {updatedAt && (
            <p className="num text-2xs text-muted">
              Updated {new Date(updatedAt).toLocaleTimeString("en-US", { hour12: false })}
              {!marketOpen && series?.marketTime && ` · last trade ${fullTime(Date.parse(series.marketTime), series.exchangeTimezone)}`}
            </p>
          )}
        </div>
      </div>

      {chart.error && !series ? (
        <div className="flex h-56 flex-col items-center justify-center gap-2 border border-dashed border-line text-center">
          <p className="font-mono text-2xs text-loss">
            {String((chart.error as Error).message).includes("symbol_not_found")
              ? "No chart data: the symbol may be delisted or mistyped."
              : "Chart data is unavailable right now."}
          </p>
          <Button size="sm" onClick={() => chart.mutate()}>
            <RotateCw className="h-3 w-3" aria-hidden="true" /> Retry
          </Button>
        </div>
      ) : !series ? (
        <div aria-hidden="true">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="mt-1 h-12 w-full" />
        </div>
      ) : points.length < 2 ? (
        <div className="flex h-56 items-center justify-center border border-dashed border-line font-mono text-2xs text-muted">
          No price data for this range.
        </div>
      ) : (
        <figure aria-label={summary} className={cn(chart.isValidating && !hovering && "opacity-90")}>
          <div className="h-48 w-full sm:h-56" onMouseEnter={() => setHovering(true)} onMouseLeave={() => setHovering(false)}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={points} syncId={`sync-${asset.symbol}`} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.16} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#EAEAEA" vertical={false} />
                <XAxis
                  dataKey="t"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(t: number) => fmt.format(t)}
                  tick={{ fontSize: 9, fontFamily: "monospace", fill: "#6B6A66" }}
                  tickLine={false}
                  axisLine={{ stroke: "#D4D4D4" }}
                  minTickGap={36}
                  hide
                />
                <YAxis
                  domain={["auto", "auto"]}
                  orientation="right"
                  tickFormatter={(v: number) => formatCompact(v)}
                  tick={{ fontSize: 9, fontFamily: "monospace", fill: "#6B6A66" }}
                  tickLine={false}
                  axisLine={false}
                  width={48}
                />
                <Tooltip
                  content={<ChartTooltip currency={series.currency} timeZone={series.exchangeTimezone} />}
                  cursor={{ stroke: "#111111", strokeDasharray: "3 3" }}
                  isAnimationActive={false}
                />
                {reference !== undefined && (
                  <ReferenceLine
                    y={reference}
                    stroke="#6B6A66"
                    strokeDasharray="4 4"
                    label={{
                      value: INTRADAY.includes(range) ? `Prev close ${formatCompact(reference)}` : "Range start",
                      position: "insideTopLeft",
                      fontSize: 9,
                      fontFamily: "monospace",
                      fill: "#6B6A66",
                    }}
                  />
                )}
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke={color}
                  strokeWidth={1.5}
                  fill={`url(#${gradientId})`}
                  isAnimationActive={false}
                  dot={false}
                  activeDot={{ r: 3, stroke: "#111111", strokeWidth: 1, fill: "#ffffff" }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="h-14 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={points} syncId={`sync-${asset.symbol}`} margin={{ top: 2, right: 52, bottom: 0, left: 0 }}>
                <XAxis
                  dataKey="t"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(t: number) => fmt.format(t)}
                  tick={{ fontSize: 9, fontFamily: "monospace", fill: "#6B6A66" }}
                  tickLine={false}
                  axisLine={{ stroke: "#D4D4D4" }}
                  minTickGap={36}
                />
                <YAxis hide domain={[0, "dataMax"]} />
                <Tooltip content={() => null} cursor={{ fill: "#F4F4F2" }} />
                <Bar dataKey="volume" fill="#A1A09A" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <figcaption className="sr-only">{summary}</figcaption>
        </figure>
      )}
      {chart.error && series && (
        <p className="mt-1 font-mono text-2xs text-loss">Refresh failed; showing the last loaded data.</p>
      )}
    </SectionCard>
  );
}
