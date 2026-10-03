"use client";

import React from "react";
import { ShieldAlert } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ScoreGauge from "@/components/chat/ScoreGauge";
import { SectionCard, Skeleton } from "@/components/ui/primitives";
import { formatNumber, formatPct } from "@/lib/format";
import type { Audit, EvidenceItem, Risk } from "@/lib/chat/types";

const AXIS = { fontSize: 9, fontFamily: "monospace", fill: "#6B6A66" };
const TOOLTIP = { fontSize: 11, fontFamily: "monospace", border: "1px solid #111", borderRadius: 0 };

function MiniChart({ title, summary, children }: { title: string; summary: string; children: React.ReactElement }) {
  return (
    <figure className="border border-line p-2.5">
      <figcaption className="font-mono text-2xs font-bold uppercase tracking-widest text-ink">{title}</figcaption>
      <p className="mb-1 font-mono text-2xs text-muted">{summary}</p>
      <div className="h-36 w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

export default function RiskTrustPanel({
  risk,
  evidence,
  audit,
  pending,
}: {
  risk?: Risk;
  evidence: EvidenceItem[];
  audit?: Audit;
  pending: boolean;
}) {
  if (!risk) {
    return (
      <SectionCard id="risk" title="Risk & Trust" icon={<ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />}>
        {pending ? <Skeleton className="h-40 w-full" /> : <p className="font-mono text-2xs text-muted">Risk metrics unavailable for this run.</p>}
      </SectionCard>
    );
  }
  const sentiment = risk.sentimentDistribution
    ? [
        { label: "Positive", value: risk.sentimentDistribution.positive, fill: "#047857" },
        { label: "Neutral", value: risk.sentimentDistribution.neutral, fill: "#A1A09A" },
        { label: "Negative", value: risk.sentimentDistribution.negative, fill: "#BE123C" },
      ]
    : null;
  const worstDrawdown = risk.drawdown.length ? Math.min(...risk.drawdown.map((d) => d.value)) : null;
  const var95 = risk.varSensitivity.find((p) => p.confidence === 95);

  return (
    <SectionCard id="risk" title="Risk & Trust" icon={<ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />} className="border-ink">
      <div className="grid gap-4 sm:grid-cols-2">
        <ScoreGauge label="Risk score" score={risk.riskScore} band={risk.riskBand} kind="risk" />
        <ScoreGauge label="Trust factor" score={risk.trustScore} band={risk.trustBand} kind="trust">
          {risk.trustReasons.length > 0 && (
            <details className="mt-1.5 w-full max-w-xs text-center">
              <summary className="cursor-pointer font-mono text-2xs text-muted underline decoration-dotted hover:text-ink">
                Why this trust score?
              </summary>
              <ul className="mt-1.5 space-y-1 border border-line bg-canvas p-2 text-left text-2xs text-ink-soft">
                {risk.trustReasons.map((r) => (
                  <li key={r}>· {r}</li>
                ))}
              </ul>
            </details>
          )}
        </ScoreGauge>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {risk.breakdown.length > 0 && (
          <MiniChart
            title="Risk factor breakdown"
            summary={risk.breakdown.map((b) => `${b.label} ${b.value.toFixed(0)}`).join(" · ")}
          >
            <BarChart data={risk.breakdown} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#EAEAEA" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={AXIS} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="label" tick={AXIS} tickLine={false} axisLine={false} width={92} />
              <Tooltip contentStyle={TOOLTIP} cursor={{ fill: "#F4F4F2" }} formatter={(v: number, _n, item) => [`${v.toFixed(0)} / 100`, item.payload.detail]} />
              <Bar dataKey="value" isAnimationActive={false}>
                {risk.breakdown.map((b) => (
                  <Cell key={b.label} fill={b.value >= 50 ? "#BE123C" : "#111111"} />
                ))}
              </Bar>
            </BarChart>
          </MiniChart>
        )}
        {risk.varSensitivity.length > 1 && (
          <MiniChart
            title="VaR sensitivity (1-day)"
            summary={var95 ? `95%: VaR ${formatPct(var95.var, 2, false)}, CVaR ${formatPct(var95.cvar, 2, false)}` : "Historical simulation"}
          >
            <LineChart data={risk.varSensitivity} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
              <CartesianGrid stroke="#EAEAEA" vertical={false} />
              <XAxis dataKey="confidence" tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v}%`} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v.toFixed(1)}%`} />
              <Tooltip contentStyle={TOOLTIP} formatter={(v: number, name: string) => [formatPct(v, 2, false), name.toUpperCase()]} labelFormatter={(l) => `${l}% confidence`} />
              <Legend wrapperStyle={{ fontSize: 9, fontFamily: "monospace" }} iconSize={8} />
              <Line type="monotone" dataKey="var" name="VaR" stroke="#111111" strokeWidth={1.5} dot={{ r: 2 }} isAnimationActive={false} />
              <Line type="monotone" dataKey="cvar" name="CVaR" stroke="#BE123C" strokeWidth={1.5} strokeDasharray="4 3" dot={{ r: 2 }} isAnimationActive={false} />
            </LineChart>
          </MiniChart>
        )}
        {sentiment && (
          <MiniChart title="News sentiment" summary={sentiment.map((s) => `${s.label} ${s.value}`).join(" · ")}>
            <BarChart data={sentiment} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid stroke="#EAEAEA" vertical={false} />
              <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TOOLTIP} cursor={{ fill: "#F4F4F2" }} formatter={(v: number) => [v, "Headlines"]} />
              <Bar dataKey="value" isAnimationActive={false}>
                {sentiment.map((s) => (
                  <Cell key={s.label} fill={s.fill} />
                ))}
              </Bar>
            </BarChart>
          </MiniChart>
        )}
        {risk.drawdown.length > 1 && (
          <MiniChart title="Drawdown from peak (1Y)" summary={`Worst ${formatPct(worstDrawdown, 2, false)} · now ${formatPct(risk.drawdown.at(-1)?.value, 2, false)}`}>
            <AreaChart data={risk.drawdown} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
              <CartesianGrid stroke="#EAEAEA" vertical={false} />
              <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={false} minTickGap={40} tickFormatter={(d: string) => d.slice(2, 7)} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
              <Tooltip contentStyle={TOOLTIP} formatter={(v: number) => [formatPct(v, 2, false), "Drawdown"]} />
              <Area type="monotone" dataKey="value" stroke="#BE123C" fill="#BE123C" fillOpacity={0.12} strokeWidth={1.25} isAnimationActive={false} />
            </AreaChart>
          </MiniChart>
        )}
      </div>

      {(risk.macro.length > 0 || risk.weather.length > 0) && (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {risk.macro.length > 0 && (
            <div className="border border-line p-2.5">
              <p className="font-mono text-2xs font-bold uppercase tracking-widest text-ink">Macro backdrop (FRED)</p>
              <dl className="mt-1.5 space-y-1">
                {risk.macro.map((m) => (
                  <div key={m.label} className="flex justify-between gap-3 text-2xs">
                    <dt className="text-muted">{m.label}</dt>
                    <dd className="num text-ink">
                      {formatNumber(m.value)} {m.unit === "Percent" ? "%" : (m.unit ?? "")}
                      {m.date && <span className="ml-1 text-muted">({m.date})</span>}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
          {risk.weather.length > 0 && (
            <div className="border border-line p-2.5">
              <p className="font-mono text-2xs font-bold uppercase tracking-widest text-ink">Weather extremes (7-day)</p>
              <ul className="mt-1.5 space-y-1 text-2xs text-ink-soft">
                {risk.weather.map((w, i) => (
                  <li key={i}>
                    <span className="num text-muted">{w.date}</span> · {w.location}: {w.description}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {risk.correlations && risk.correlations.length > 0 && (
        <div className="mt-3 border border-line p-2.5">
          <div className="flex flex-wrap items-center justify-between gap-1">
            <p className="font-mono text-2xs font-bold uppercase tracking-widest text-ink">
              Cross-Asset Correlations (1Y Daily Returns)
            </p>
            <span className="font-mono text-2xs text-muted">Brent · USD/INR · NIFTY · VIX</span>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {risk.correlations.map((c) => {
              const val = c.correlation;
              const isPositive = val !== null && val > 0.05;
              const isNegative = val !== null && val < -0.05;
              const colorClass = isPositive
                ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                : isNegative
                  ? "text-rose-700 bg-rose-50 border-rose-200"
                  : "text-ink-soft bg-subtle border-line";
              return (
                <div key={c.symbol} className="border border-line bg-canvas p-2">
                  <div className="flex items-center justify-between text-2xs">
                    <span className="font-semibold text-ink">{c.asset}</span>
                    <span className="font-mono text-muted">{c.symbol}</span>
                  </div>
                  <div className="mt-1 flex items-baseline justify-between">
                    <span
                      className={`inline-block px-1.5 py-0.5 font-mono text-xs font-bold border ${colorClass}`}
                    >
                      {val !== null ? `${val >= 0 ? "+" : ""}${val.toFixed(2)}` : "N/A"}
                    </span>
                    {c.observations ? (
                      <span className="font-mono text-[10px] text-muted">{c.observations}d</span>
                    ) : null}
                  </div>
                  <div className="mt-2 relative h-1.5 w-full bg-line overflow-hidden">
                    <div className="absolute left-1/2 top-0 bottom-0 w-px bg-muted z-10" />
                    {val !== null && (
                      <div
                        className={`h-full ${val >= 0 ? "bg-emerald-600" : "bg-rose-600"}`}
                        style={{
                          width: `${Math.min(Math.abs(val) * 50, 50)}%`,
                          marginLeft: val >= 0 ? "50%" : `${50 - Math.min(Math.abs(val) * 50, 50)}%`,
                        }}
                      />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {evidence.length > 0 && (
        <details className="mt-3 border border-line" data-testid="audit-trail">
          <summary className="cursor-pointer px-2.5 py-2 font-mono text-2xs font-bold uppercase tracking-widest text-ink hover:bg-canvas">
            Audit trail · {evidence.length} evidence items
            {audit && (
              <span className="ml-2 font-normal normal-case tracking-normal text-muted">
                {audit.checkedNumbers} figures checked, {audit.unverifiedNumbers.length} unverified
              </span>
            )}
          </summary>
          {audit && audit.unverifiedNumbers.length > 0 && (
            <p className="border-t border-line bg-loss-soft px-2.5 py-1.5 font-mono text-2xs text-loss">
              Not found in evidence: {audit.unverifiedNumbers.join(", ")}. Treat these figures with caution.
            </p>
          )}
          <div className="max-h-72 overflow-auto border-t border-line">
            <table className="w-full text-left text-2xs">
              <thead className="sticky top-0 bg-canvas font-mono uppercase tracking-wider text-muted">
                <tr>
                  <th scope="col" className="px-2 py-1">ID</th>
                  <th scope="col" className="px-2 py-1">Agent</th>
                  <th scope="col" className="px-2 py-1">Evidence</th>
                  <th scope="col" className="px-2 py-1">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {evidence.map((e) => (
                  <tr key={e.id} id={`evidence-${e.id}`}>
                    <td className="num px-2 py-1 align-top text-muted">{e.id}</td>
                    <td className="px-2 py-1 align-top font-mono text-muted">{e.agent}</td>
                    <td className="px-2 py-1 align-top text-ink">
                      <span className="text-muted">{e.label.startsWith("Headline:") ? "" : `${e.label}: `}</span>
                      <span className="num">{e.display}</span>
                    </td>
                    <td className="px-2 py-1 align-top">
                      {e.url ? (
                        <a href={e.url} target="_blank" rel="noopener noreferrer" className="text-ink underline decoration-dotted">
                          {e.source}
                        </a>
                      ) : (
                        <span className="text-muted">{e.source}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </SectionCard>
  );
}
