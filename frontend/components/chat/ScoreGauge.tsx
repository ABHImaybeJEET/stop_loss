"use client";

import React from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

interface Props {
  label: string;
  score: number | null;
  band: string | null;
  /** "risk": higher is worse; "trust": higher is better. */
  kind: "risk" | "trust";
  children?: React.ReactNode;
}

const RISK_BANDS = ["Low", "Moderate", "High", "Severe"];

/** Semi-circle 0-100 gauge. With no score it says so instead of drawing a value. */
export default function ScoreGauge({ label, score, band, kind, children }: Props) {
  const value = score === null ? 0 : Math.max(0, Math.min(100, score));
  const fill =
    score === null ? "#EAEAEA" : kind === "risk" ? (value >= 50 ? "#BE123C" : "#111111") : value >= 70 ? "#047857" : "#111111";
  const text = score === null ? `${label}: unavailable` : `${label}: ${value.toFixed(0)} out of 100, ${band ?? "no band"}`;
  return (
    <div className="flex flex-col items-center" data-testid={`gauge-${kind}`}>
      <div className="relative h-24 w-44" role="img" aria-label={text}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={[{ v: value }, { v: 100 - value }]}
              dataKey="v"
              startAngle={180}
              endAngle={0}
              cx="50%"
              cy={88}
              innerRadius={60}
              outerRadius={78}
              stroke="none"
              isAnimationActive={false}
            >
              <Cell fill={fill} />
              <Cell fill="#F4F4F2" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-x-0 bottom-0 text-center">
          <p className="num text-2xl font-bold leading-none text-ink">{score === null ? "—" : value.toFixed(0)}</p>
        </div>
      </div>
      <p className="mt-1 font-mono text-2xs font-bold uppercase tracking-widest text-ink">{label}</p>
      <p className="font-mono text-2xs text-muted">{score === null ? "Insufficient data" : band}</p>
      {kind === "risk" && (
        <div className="mt-1 flex gap-1" aria-hidden="true">
          {RISK_BANDS.map((b) => (
            <span key={b} className={`h-1 w-6 ${b === band ? "bg-ink" : "bg-line"}`} title={b} />
          ))}
        </div>
      )}
      {children}
    </div>
  );
}
