"use client";

import React, { useMemo } from "react";
import {
  Activity,
  Briefcase,
  CloudLightning,
  History,
  Lightbulb,
  ListChecks,
  Newspaper,
  ShieldAlert,
  Sigma,
} from "lucide-react";
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import EvidenceText, { EvidenceRef, evidenceMap } from "@/components/chat/EvidenceText";
import ScoreGauge from "@/components/chat/ScoreGauge";
import { Badge, SectionCard, Skeleton, SkeletonLines, cn } from "@/components/ui/primitives";
import { formatCompact, formatNumber, formatPct, formatPrice, relativeTime, signClass } from "@/lib/format";
import { displaySymbol, stripNs } from "@/lib/symbols";
import type { EvidenceItem } from "@/lib/chat/types";
import type { PortfolioPartial, PortfolioResult, PfExposureRow } from "@/lib/chat/portfolioTypes";

const RECO_TONE = { hedge: "loss", reduce: "loss", add: "gain", rebalance: "outline", monitor: "neutral" } as const;
const SENT_TONE = { positive: "gain", negative: "loss", neutral: "neutral" } as const;

function Text({ text, evidence, pending, lines = 2 }: { text?: string; evidence: Map<string, EvidenceItem>; pending: boolean; lines?: number }) {
  if (text) {
    return (
      <p className="text-sm leading-relaxed text-ink-soft">
        <EvidenceText text={stripNs(text)} evidence={evidence} />
      </p>
    );
  }
  return pending ? <SkeletonLines lines={lines} /> : null;
}

function inr(value?: number): string {
  if (value === undefined) return "—";
  return `${value < 0 ? "−" : ""}${formatPrice(Math.abs(value), "INR", 0)}`;
}

function ScenarioChart({ rows }: { rows: PfExposureRow[] }) {
  const data = rows
    .filter((r) => r.scenarioImpact !== undefined)
    .map((r) => ({ symbol: displaySymbol(r.symbol), impact: r.scenarioImpact as number }));
  if (data.length === 0) return null;
  return (
    <figure className="mt-3" aria-label={data.map((d) => `${d.symbol} ${inr(d.impact)}`).join(", ")}>
      <figcaption className="font-mono text-2xs uppercase tracking-wider text-muted">
        Analog-based 5-day scenario by holding (₹)
      </figcaption>
      <div className="h-40 w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 8 }}>
            <XAxis dataKey="symbol" tick={{ fontSize: 9, fontFamily: "monospace" }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 9, fontFamily: "monospace" }} tickLine={false} axisLine={false} width={56} tickFormatter={(v: number) => formatCompact(v)} />
            <ReferenceLine y={0} stroke="#111111" />
            <Tooltip
              contentStyle={{ fontSize: 11, fontFamily: "monospace", border: "1px solid #111", borderRadius: 0 }}
              formatter={(v: number) => [inr(v), "Scenario"]}
            />
            <Bar dataKey="impact" isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.symbol} fill={d.impact >= 0 ? "#047857" : "#BE123C"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

export default function PortfolioAnswer({
  result,
  partial,
  pending,
}: {
  result?: PortfolioResult;
  partial: PortfolioPartial;
  pending: boolean;
}) {
  const evidence = useMemo(() => evidenceMap(result?.evidence), [result?.evidence]);
  const snapshot = result?.portfolio ?? partial.portfolio;
  const event = result?.event ?? partial.event;
  const exposure = result?.exposure ?? partial.exposure;
  const analogs = result?.analogs ?? partial.analogs;
  const sentiment = result?.sentiment ?? partial.sentiment;
  const risk = result?.risk;

  return (
    <div className="space-y-3" data-testid="portfolio-answer">
      {result?.partial && (
        <p className="border border-line-strong bg-canvas px-3 py-2 text-xs" role="status">
          Partial result: {result.failedAgents.join(", ")} unavailable. The rest uses live data.
        </p>
      )}
      {/* 1. Bottom line */}
      <section className="border-2 border-ink bg-white p-4" aria-labelledby="pf-bottom">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 id="pf-bottom" className="font-mono text-2xs font-bold uppercase tracking-widest text-ink">
            Bottom line
          </h3>
          {result?.narrativeSource === "rules" && <Badge title="LLM unavailable: deterministic, evidence-only text">rules mode</Badge>}
        </div>
        {result ? (
          <p className="text-base leading-relaxed text-ink">
            <EvidenceText text={stripNs(result.bottomLine)} evidence={evidence} />
          </p>
        ) : (
          <SkeletonLines lines={3} />
        )}
      </section>

      {/* 2. Portfolio snapshot */}
      <SectionCard id="pf-snapshot" title="Portfolio" icon={<Briefcase className="h-3.5 w-3.5" aria-hidden="true" />}
        aside={snapshot && <span className="num text-xs font-bold">{inr(snapshot.totalValue)}{" "}
          <span className={signClass(snapshot.dayChangePct)}>{formatPct(snapshot.dayChangePct)}</span></span>}>
        {!snapshot ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-xs">
                <thead className="font-mono text-2xs uppercase tracking-wider text-muted">
                  <tr>
                    <th className="py-1.5 pr-2">Stock</th>
                    <th className="py-1.5 pr-2 text-right">Value</th>
                    <th className="py-1.5 pr-2 text-right">Weight</th>
                    <th className="py-1.5 pr-2 text-right">Day</th>
                    <th className="py-1.5 text-right">In scope</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {snapshot.holdings.map((h) => (
                    <tr key={h.symbol} className={cn(!h.target && "text-muted")}>
                      <td className="py-1.5 pr-2">
                        <span className="num font-bold">{displaySymbol(h.symbol)}</span>
                        <span className="ml-2 text-2xs text-muted">{h.sector ?? ""}</span>
                      </td>
                      <td className="num py-1.5 pr-2 text-right">{inr(h.value)}</td>
                      <td className="num py-1.5 pr-2 text-right">{h.weight !== undefined ? formatPct(h.weight, 1, false) : "—"}</td>
                      <td className={cn("num py-1.5 pr-2 text-right", signClass(h.changePct))}>{formatPct(h.changePct)}</td>
                      <td className="py-1.5 text-right">{h.target ? <Badge tone="solid">yes</Badge> : <Badge>no</Badge>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex h-2 w-full overflow-hidden" aria-label="Sector weights">
              {snapshot.sectors.map((s, i) => (
                <span key={s.sector} title={`${s.sector} ${s.weight.toFixed(1)}%`} style={{ width: `${s.weight}%` }}
                  className={cn("h-full", ["bg-ink", "bg-muted", "bg-muted-soft", "bg-line-strong"][i % 4])} />
              ))}
            </div>
            <p className="mt-1 font-mono text-2xs text-muted">
              {snapshot.sectors.map((s) => `${s.sector} ${s.weight.toFixed(1)}%`).join(" · ")}
            </p>
          </>
        )}
      </SectionCard>

      {/* 3. Event & live tracking */}
      <SectionCard id="pf-event" title="Event & live tracking" icon={<CloudLightning className="h-3.5 w-3.5" aria-hidden="true" />}
        aside={event?.kind && event.kind !== "none" && <Badge tone="outline">{[event.kind, event.region, event.severity].filter(Boolean).join(" · ")}</Badge>}>
        <Text text={event?.summary} evidence={evidence} pending={pending} />
        {event && (
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div>
              <p className="mb-1 font-mono text-2xs font-bold uppercase tracking-widest text-ink">Live alerts (GDACS / USGS)</p>
              {event.alerts.length === 0 ? (
                <p className="font-mono text-2xs text-muted">No live alert matches this event{event.region ? ` in ${event.region}` : ""}.</p>
              ) : (
                <ul className="space-y-1.5">
                  {event.alerts.map((a) => (
                    <li key={`${a.source}-${a.name}`} className="border border-line p-2 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-ink">{a.name}</span>
                        <Badge tone={a.alertLevel === "Red" ? "loss" : a.alertLevel === "Orange" ? "outline" : "neutral"}>{a.alertLevel ?? "n/a"}</Badge>
                      </div>
                      <p className="mt-0.5 font-mono text-2xs text-muted">
                        {a.eventType} · {a.country ?? "—"} · {a.startedAt ? relativeTime(a.startedAt) : ""}
                        {a.severity ? ` · ${a.severity}` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              {event.weather.length > 0 && (
                <ul className="mt-2 space-y-0.5 border-l-2 border-loss pl-2 text-2xs text-loss">
                  {event.weather.map((w, i) => (
                    <li key={i}>{w.date} · {w.location}: {w.description}</li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <p className="mb-1 font-mono text-2xs font-bold uppercase tracking-widest text-ink">Macro channels</p>
              <dl className="grid grid-cols-2 gap-px border border-line bg-line">
                {event.macro.map((m) => (
                  <div key={m.label} className="bg-white px-2 py-1.5">
                    <dt className="font-mono text-2xs text-muted">{m.label}</dt>
                    <dd className="num text-xs font-semibold">
                      {formatNumber(m.latest)}{" "}
                      {m.changePct !== undefined && <span className={signClass(m.changePct)}>{formatPct(m.changePct)}</span>}
                    </dd>
                    {m.latestDate && <dd className="font-mono text-[9px] text-muted-soft">as of {m.latestDate}</dd>}
                  </div>
                ))}
              </dl>
              {event.flags.length > 0 && <p className="mt-1 font-mono text-2xs text-loss">Flags: {event.flags.map((f) => f.replace(/_/g, " ")).join(", ")}</p>}
            </div>
          </div>
        )}
      </SectionCard>

      {/* 4. Exposure & scenario */}
      <SectionCard id="pf-exposure" title="Exposure & scenario" icon={<Activity className="h-3.5 w-3.5" aria-hidden="true" />}
        aside={exposure?.totalImpact !== undefined && <span className={cn("num text-xs font-bold", signClass(exposure.totalImpact))}>{inr(exposure.totalImpact)}</span>}>
        <Text text={exposure?.summary} evidence={evidence} pending={pending} />
        {!exposure ? (
          pending && <Skeleton className="mt-2 h-24 w-full" />
        ) : (
          <>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-xs">
                <thead className="font-mono text-2xs uppercase tracking-wider text-muted">
                  <tr>
                    {["Stock", "Weight", "β NIFTY", "β Brent", "β USD/INR", "Sentiment", "Analogs n", "Median 5d", "Scenario ₹", "Range ₹"].map((h, i) => (
                      <th key={h} className={cn("py-1.5 pr-2", i > 0 && "text-right")}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {exposure.rows.map((r) => (
                    <tr key={r.symbol}>
                      <td className="num py-1.5 pr-2 font-bold">{displaySymbol(r.symbol)}</td>
                      <td className="num py-1.5 pr-2 text-right">{r.weight !== undefined ? formatPct(r.weight, 1, false) : "—"}</td>
                      <td className="num py-1.5 pr-2 text-right">{formatNumber(r.betaNifty)}</td>
                      <td className="num py-1.5 pr-2 text-right">{formatNumber(r.betaBrent)}</td>
                      <td className="num py-1.5 pr-2 text-right">{formatNumber(r.betaInr)}</td>
                      <td className={cn("num py-1.5 pr-2 text-right", signClass(r.sentimentScore))}>{r.sentimentScore !== undefined ? r.sentimentScore.toFixed(2) : "—"}</td>
                      <td className="num py-1.5 pr-2 text-right">{r.analogN}</td>
                      <td className={cn("num py-1.5 pr-2 text-right", signClass(r.analogMedian5d))}>{formatPct(r.analogMedian5d)}</td>
                      <td className={cn("num py-1.5 pr-2 text-right", signClass(r.scenarioImpact))}>{inr(r.scenarioImpact)}</td>
                      <td className="num py-1.5 text-right text-muted">{r.scenarioLow !== undefined ? `${inr(r.scenarioLow)} … ${inr(r.scenarioHigh)}` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ScenarioChart rows={exposure.rows} />
            {exposure.totalImpact !== undefined && (
              <p className="mt-1 text-xs">
                Portfolio scenario (simple sum): <span className={cn("num font-bold", signClass(exposure.totalImpact))}>{inr(exposure.totalImpact)}</span>{" "}
                <span className="num text-muted">({inr(exposure.totalLow)} … {inr(exposure.totalHigh)})</span>
              </p>
            )}
            <p className="mt-1 font-mono text-2xs text-muted">{exposure.method}</p>
          </>
        )}
      </SectionCard>

      {/* 5. Historical analogs */}
      <SectionCard id="pf-analogs" title="Historical parallels" icon={<History className="h-3.5 w-3.5" aria-hidden="true" />}
        aside={analogs && <span className="num text-2xs text-muted">{analogs.events.length} matches</span>}>
        <Text text={analogs?.summary} evidence={evidence} pending={pending} />
        {analogs && (
          <>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {[...analogs.aggregates, analogs.brent, analogs.nifty].filter(Boolean).map((a) => (
                <div key={a!.symbol} className="border border-line px-2.5 py-2">
                  <p className="font-mono text-2xs uppercase tracking-wider text-muted">
                    {a!.symbol === "BZ=F" ? "Brent crude" : a!.symbol === "^NSEI" ? "NIFTY 50" : displaySymbol(a!.symbol)} · n={a!.n}
                  </p>
                  <p className={cn("num text-sm font-bold", signClass(a!.median5d))}>{formatPct(a!.median5d)} <span className="text-2xs font-normal text-muted">median 5d</span></p>
                  {a!.n > 0 && (
                    <p className="num text-2xs text-muted">
                      {formatPct(a!.min5d)} … {formatPct(a!.max5d)} · fell {a!.shareNegative5d !== undefined ? `${Math.round(a!.shareNegative5d * 100)}%` : "—"}
                    </p>
                  )}
                </div>
              ))}
            </div>
            <ul className="mt-3 max-h-64 divide-y divide-line overflow-y-auto border-y border-line">
              {analogs.events.map((e) => (
                <li key={e.id} className="flex items-start justify-between gap-3 py-1.5 text-xs">
                  <span className="min-w-0">
                    <span className="block truncate font-semibold text-ink" title={e.title}>{stripNs(e.title)}</span>
                    <span className="font-mono text-2xs text-muted">{e.date ?? "undated"} · {e.docType ?? "record"} · similarity {e.score.toFixed(2)}</span>
                  </span>
                  <span className="num shrink-0 text-right text-2xs">
                    {Object.entries(e.returns).slice(0, 3).map(([s, r]) => (
                      <span key={s} className={cn("block", signClass(r.d5))}>{displaySymbol(s)} {formatPct(r.d5)}</span>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-1 font-mono text-2xs text-muted">Moves measured from local NSE/Brent/NIFTY daily closes after each matched date. Past reactions do not guarantee future moves.</p>
          </>
        )}
      </SectionCard>

      {/* 6. Sentiment */}
      <SectionCard id="pf-sentiment" title="News sentiment" icon={<Newspaper className="h-3.5 w-3.5" aria-hidden="true" />}
        aside={result?.sentiment.portfolioScore !== undefined && <span className={cn("num text-xs font-bold", signClass(result.sentiment.portfolioScore))}>{result.sentiment.portfolioScore.toFixed(2)} weighted</span>}>
        <Text text={result?.sentiment.summary} evidence={evidence} pending={pending} />
        {sentiment?.perHolding && (
          <div className="mt-2 space-y-1">
            {sentiment.perHolding.map((s) => {
              const total = s.positive + s.negative + s.neutral || 1;
              return (
                <div key={s.symbol} className="flex items-center gap-2 text-2xs">
                  <span className="num w-20 shrink-0 font-bold">{displaySymbol(s.symbol)}</span>
                  <span className="flex h-2 flex-1 overflow-hidden bg-subtle" aria-label={`${s.positive} positive, ${s.negative} negative, ${s.neutral} neutral`}>
                    <span className="bg-gain" style={{ width: `${(s.positive / total) * 100}%` }} />
                    <span className="bg-muted-soft" style={{ width: `${(s.neutral / total) * 100}%` }} />
                    <span className="bg-loss" style={{ width: `${(s.negative / total) * 100}%` }} />
                  </span>
                  <span className="num w-12 text-right">{s.score !== undefined ? s.score.toFixed(2) : "—"}</span>
                </div>
              );
            })}
          </div>
        )}
        {sentiment?.items && sentiment.items.length > 0 && (
          <ul className="mt-3 max-h-56 divide-y divide-line overflow-y-auto border-y border-line">
            {sentiment.items.map((i) => (
              <li key={i.url} className="flex items-start gap-2 py-1.5">
                <a href={i.url} target="_blank" rel="noopener noreferrer" className="min-w-0 flex-1 text-xs font-semibold text-ink hover:underline">
                  {stripNs(i.title)}
                  <span className="block font-mono text-2xs font-normal text-muted">
                    {i.publisher}{i.publishedAt ? ` · ${relativeTime(i.publishedAt)}` : ""} · {i.symbols.map(displaySymbol).join(", ")}
                  </span>
                </a>
                {i.sentiment && <Badge tone={SENT_TONE[i.sentiment]}>{i.sentiment}</Badge>}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* 7. Quant risk */}
      <SectionCard id="pf-risk" title="Quantitative risk" icon={<Sigma className="h-3.5 w-3.5" aria-hidden="true" />}>
        <Text text={risk?.summary} evidence={evidence} pending={pending} />
        {risk && risk.perHolding.length > 0 && (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-xs">
              <thead className="font-mono text-2xs uppercase tracking-wider text-muted">
                <tr>{["Stock", "Risk", "Vol 1Y", "VaR95 1d", "Max DD 1Y", "β NIFTY"].map((h, i) => <th key={h} className={cn("py-1.5 pr-2", i > 0 && "text-right")}>{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-line">
                {risk.perHolding.map((r) => (
                  <tr key={r.symbol}>
                    <td className="num py-1.5 pr-2 font-bold">{displaySymbol(r.symbol)}</td>
                    <td className="num py-1.5 pr-2 text-right">{r.riskScore !== undefined ? `${r.riskScore.toFixed(0)} ${r.band ?? ""}` : "—"}</td>
                    <td className="num py-1.5 pr-2 text-right">{formatPct(r.vol1y, 1, false)}</td>
                    <td className="num py-1.5 pr-2 text-right">{formatPct(r.var951d, 2, false)}</td>
                    <td className="num py-1.5 pr-2 text-right text-loss">{formatPct(r.maxDrawdown1y, 1, false)}</td>
                    <td className="num py-1.5 text-right">{formatNumber(r.beta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {/* 8. Recommendations */}
      <SectionCard id="pf-reco" title="Recommendations" icon={<Lightbulb className="h-3.5 w-3.5" aria-hidden="true" />}>
        {result ? (
          <>
            <ol className="grid gap-2 sm:grid-cols-2">
              {result.recommendations.map((r, i) => (
                <li key={i} className="flex flex-col border border-line p-3" data-testid="pf-recommendation">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-bold leading-snug text-ink">
                      <span className="num mr-1.5 text-muted">{String(i + 1).padStart(2, "0")}</span>
                      {stripNs(r.action)}
                    </p>
                    <Badge tone={RECO_TONE[r.kind]}>{r.kind}</Badge>
                  </div>
                  <p className="mt-1.5 flex-1 text-xs leading-relaxed text-ink-soft">
                    <EvidenceText text={stripNs(r.rationale)} evidence={evidence} />
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-2xs">
                    {r.symbols.map((s) => <Badge key={s} tone="outline">{displaySymbol(s)}</Badge>)}
                    {r.size && <span className="num font-semibold">Size {r.size}</span>}
                    {r.horizon && <span className="font-mono text-muted">{r.horizon}</span>}
                    {r.confidence !== undefined && <span className="num text-muted">conf. {Math.round(r.confidence * 100)}%</span>}
                    <span className="ml-auto">{r.evidenceIds.map((id) => <EvidenceRef key={id} id={id} evidence={evidence} />)}</span>
                  </div>
                </li>
              ))}
            </ol>
            <p className="mt-3 border-l-2 border-ink pl-2 font-mono text-2xs text-muted" role="note">{result.disclaimer}</p>
          </>
        ) : (
          pending && <Skeleton className="h-24 w-full" />
        )}
      </SectionCard>

      {/* 9. Risk & trust + audit trail */}
      {result && (
        <SectionCard id="pf-trust" title="Risk, trust & audit trail" icon={<ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />} className="border-ink">
          <div className="grid gap-4 sm:grid-cols-2">
            <ScoreGauge label="Portfolio risk" score={risk?.riskScore ?? null} band={risk?.riskBand ?? null} kind="risk" />
            <ScoreGauge label="Trust factor" score={risk?.trustScore ?? null} band={risk?.trustBand ?? null} kind="trust">
              {risk && risk.trustReasons.length > 0 && (
                <ul className="mt-1.5 w-full max-w-xs space-y-0.5 text-left text-2xs text-ink-soft">
                  {risk.trustReasons.map((r) => <li key={r}>· {r}</li>)}
                </ul>
              )}
            </ScoreGauge>
          </div>
          <div className="mt-4" data-testid="pf-audit-trail">
            <p className="mb-1 flex items-center gap-1.5 font-mono text-2xs font-bold uppercase tracking-widest text-ink">
              <ListChecks className="h-3.5 w-3.5" aria-hidden="true" /> Step-by-step decision trail
            </p>
            <ol className="space-y-1.5">
              {result.steps.map((s, i) => (
                <li key={s.agent} className="border border-line px-2.5 py-1.5 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold"><span className="num mr-1.5 text-muted">{i + 1}.</span>{s.name}</span>
                    <Badge tone={s.status === "ok" ? "solid" : "neutral"}>{s.status}</Badge>
                  </div>
                  {s.summary && <p className="mt-0.5 font-mono text-2xs text-muted">{stripNs(s.summary)}</p>}
                  {s.evidenceIds.length > 0 && (
                    <p className="mt-1 flex flex-wrap">{s.evidenceIds.slice(0, 16).map((id) => <EvidenceRef key={id} id={id} evidence={evidence} />)}
                      {s.evidenceIds.length > 16 && <span className="font-mono text-2xs text-muted">+{s.evidenceIds.length - 16}</span>}</p>
                  )}
                </li>
              ))}
            </ol>
            <p className="mt-2 font-mono text-2xs text-muted">
              {result.audit.checkedNumbers} figures checked · {result.audit.unverifiedNumbers.length} unverified
              {result.audit.unverifiedNumbers.length > 0 && `: ${result.audit.unverifiedNumbers.join(", ")}`}
            </p>
          </div>
          <details className="mt-3 border border-line">
            <summary className="cursor-pointer px-2.5 py-2 font-mono text-2xs font-bold uppercase tracking-widest hover:bg-canvas">
              Evidence catalog · {result.evidence.length} items
            </summary>
            <div className="max-h-72 overflow-auto border-t border-line">
              <table className="w-full text-left text-2xs">
                <tbody className="divide-y divide-line">
                  {result.evidence.map((e) => (
                    <tr key={e.id} id={`evidence-${e.id}`}>
                      <td className="num px-2 py-1 align-top text-muted">{e.id}</td>
                      <td className="px-2 py-1 align-top font-mono text-muted">{e.agent}</td>
                      <td className="px-2 py-1 align-top">{stripNs(e.label)}: <span className="num">{stripNs(e.display)}</span></td>
                      <td className="px-2 py-1 align-top">
                        {e.url ? <a href={e.url} target="_blank" rel="noopener noreferrer" className="underline decoration-dotted">{e.source}</a> : <span className="text-muted">{e.source}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </SectionCard>
      )}
    </div>
  );
}
