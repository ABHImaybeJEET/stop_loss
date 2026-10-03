"use client";

import React, { useState } from "react";
import { CloudLightning } from "lucide-react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Skeleton, cn } from "@/components/ui/primitives";
import type { PortfolioWeather } from "@/lib/portfolio/types";

export default function WeatherPanel({ data, error }: { data?: PortfolioWeather; error?: unknown }) {
  const [index, setIndex] = useState(0);
  const locations = data?.locations ?? [];
  const current = locations[Math.min(index, Math.max(locations.length - 1, 0))];
  const points = (current?.days ?? []).map((d) => ({
    date: d.date.slice(5),
    max: d.tempMax,
    min: d.tempMin,
    rain: d.precipitationSum,
    gust: d.windGustMax,
  }));
  const extremes = locations.reduce((n, l) => n + l.extremes.length, 0);
  return (
    <section className="border border-line bg-white" aria-labelledby="weather-title" data-testid="weather-panel">
      <header className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
        <h3 id="weather-title" className="flex items-center gap-2 font-mono text-2xs font-bold uppercase tracking-widest text-ink">
          <CloudLightning className="h-3.5 w-3.5" aria-hidden="true" /> Weather at holding locations
        </h3>
        {data && <Badge tone={extremes ? "loss" : "neutral"}>{extremes ? `${extremes} extreme(s)` : "No extremes"}</Badge>}
      </header>
      <div className="p-3">
        {error && !data ? (
          <p className="py-10 text-center font-mono text-2xs text-loss">Weather forecast unavailable right now.</p>
        ) : !data ? (
          <Skeleton className="h-48 w-full" />
        ) : locations.length === 0 ? (
          <p className="py-10 text-center font-mono text-2xs text-muted">No holding has a known head-office location.</p>
        ) : (
          <>
            <div role="tablist" aria-label="Locations" className="mb-2 flex flex-wrap gap-1">
              {locations.map((l, i) => (
                <button
                  key={l.location}
                  type="button"
                  role="tab"
                  aria-selected={i === index}
                  onClick={() => setIndex(i)}
                  className={cn("border px-2 py-1 font-mono text-2xs", i === index ? "border-ink bg-ink text-white" : "border-line-strong text-muted hover:border-ink hover:text-ink")}
                >
                  {l.location.split(",")[0]} <span className="opacity-70">({l.symbols.length})</span>
                </button>
              ))}
            </div>
            <p className="mb-1 font-mono text-2xs text-muted">
              {current.location} · {current.reason} · {current.symbols.map((s) => s.replace(/\.NS$/, "")).join(", ")}
            </p>
            <div className="h-44 w-full" aria-hidden="true">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={points} margin={{ top: 4, right: 0, bottom: 0, left: -16 }}>
                  <CartesianGrid stroke="#EAEAEA" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fontFamily: "monospace", fill: "#6B6A66" }} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="t" tick={{ fontSize: 9, fontFamily: "monospace", fill: "#6B6A66" }} tickLine={false} axisLine={false} width={36} unit="°" />
                  <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 9, fontFamily: "monospace", fill: "#6B6A66" }} tickLine={false} axisLine={false} width={36} unit="mm" />
                  <Tooltip contentStyle={{ fontSize: 11, fontFamily: "monospace", border: "1px solid #111", borderRadius: 0 }} />
                  <Legend wrapperStyle={{ fontSize: 10, fontFamily: "monospace" }} iconSize={8} />
                  <Bar yAxisId="r" dataKey="rain" name="Rain (mm)" fill="#A1A09A" isAnimationActive={false} />
                  <Line yAxisId="t" dataKey="max" name="Max °C" stroke="#111111" dot={{ r: 2 }} isAnimationActive={false} />
                  <Line yAxisId="t" dataKey="min" name="Min °C" stroke="#6B6A66" strokeDasharray="4 3" dot={{ r: 2 }} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <table className="sr-only">
              <caption>7-day forecast for {current.location}</caption>
              <tbody>
                {points.map((p) => (
                  <tr key={p.date}><th scope="row">{p.date}</th><td>max {p.max}°C, min {p.min}°C, rain {p.rain} mm, gusts {p.gust} km/h</td></tr>
                ))}
              </tbody>
            </table>
            {current.extremes.length > 0 && (
              <ul className="mt-2 space-y-1 border-l-2 border-loss pl-2 text-2xs text-loss">
                {current.extremes.map((e, i) => (
                  <li key={i}><span className="num">{e.date}</span> · {e.description}</li>
                ))}
              </ul>
            )}
          </>
        )}
        {data && data.unavailable.length > 0 && (
          <p className="mt-2 font-mono text-2xs text-muted">Forecast unavailable for: {data.unavailable.map((u) => u.location).join(", ")}</p>
        )}
        <p className="mt-2 font-mono text-2xs text-muted-soft">Source: Open-Meteo 7-day forecast at company head offices.</p>
      </div>
    </section>
  );
}
