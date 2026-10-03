"use client";

import React from "react";
import { History } from "lucide-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import EvidenceText from "@/components/chat/EvidenceText";
import { SectionCard, SkeletonLines } from "@/components/ui/primitives";
import { formatNumber, formatPct, signClass } from "@/lib/format";
import type { EvidenceItem, Historical } from "@/lib/chat/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function HistoricalSection({
  historical,
  evidence,
  pending,
}: {
  historical?: Historical;
  evidence: Map<string, EvidenceItem>;
  pending: boolean;
}) {
  const seasonality = (historical?.seasonality ?? []).map((p) => ({ ...p, label: MONTHS[p.month - 1] }));
  const best = seasonality.length ? seasonality.reduce((a, b) => (b.avgReturn > a.avgReturn ? b : a)) : null;
  const worst = seasonality.length ? seasonality.reduce((a, b) => (b.avgReturn < a.avgReturn ? b : a)) : null;
  return (
    <SectionCard id="historical" title="Historical Analysis" icon={<History className="h-3.5 w-3.5" aria-hidden="true" />}>
      <div className="text-sm leading-relaxed text-ink-soft">
        {historical?.summary ? <EvidenceText text={historical.summary} evidence={evidence} /> : pending ? <SkeletonLines lines={3} /> : null}
      </div>
      {historical && historical.metrics.length > 0 && (
        <dl className="mt-3 grid grid-cols-2 gap-px border border-line bg-line sm:grid-cols-3 lg:grid-cols-4">
          {historical.metrics.map((m) => (
            <div key={m.key} className="bg-white px-2.5 py-2">
              <dt className="font-mono text-2xs uppercase tracking-wider text-muted">{m.label}</dt>
              <dd
                className={`mt-0.5 text-xs font-semibold ${
                  m.kind === "text" ? "capitalize text-ink" : `num ${m.kind === "percent" && /return|drawdown|peak/i.test(m.label) ? signClass(Number(m.value)) : "text-ink"}`
                }`}
              >
                {typeof m.value === "string"
                  ? m.value
                  : m.kind === "percent"
                    ? formatPct(m.value, 2, /return/i.test(m.label))
                    : formatNumber(m.value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {seasonality.length > 0 && (
        <figure className="mt-3" aria-labelledby="seasonality-caption">
          <figcaption id="seasonality-caption" className="font-mono text-2xs uppercase tracking-wider text-muted">
            Average return by calendar month
            {best && worst && (
              <span className="normal-case tracking-normal">
                {" "}
                · best {best.label} {formatPct(best.avgReturn)}, worst {worst.label} {formatPct(worst.avgReturn)}
              </span>
            )}
          </figcaption>
          <div className="mt-1 h-28 w-full" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={seasonality} margin={{ top: 4, right: 0, bottom: 0, left: -24 }}>
                <XAxis dataKey="label" tick={{ fontSize: 9, fontFamily: "monospace" }} tickLine={false} axisLine={false} interval={0} />
                <YAxis tick={{ fontSize: 9, fontFamily: "monospace" }} tickLine={false} axisLine={false} width={44} tickFormatter={(v: number) => `${v.toFixed(1)}%`} />
                <Tooltip
                  cursor={{ fill: "#F4F4F2" }}
                  contentStyle={{ fontSize: 11, fontFamily: "monospace", border: "1px solid #111", borderRadius: 0 }}
                  formatter={(value: number, _n, item) => [`${formatPct(value)} (${item.payload.observations} yrs)`, "Avg return"]}
                />
                <Bar dataKey="avgReturn" isAnimationActive={false}>
                  {seasonality.map((p) => (
                    <Cell key={p.month} fill={p.avgReturn >= 0 ? "#047857" : "#BE123C"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="sr-only">
            <caption>Average monthly return</caption>
            <tbody>
              {seasonality.map((p) => (
                <tr key={p.month}>
                  <th scope="row">{p.label}</th>
                  <td>{formatPct(p.avgReturn)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </figure>
      )}
    </SectionCard>
  );
}
