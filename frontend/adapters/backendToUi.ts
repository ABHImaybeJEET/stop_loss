/**
 * The single translation layer from the Python backend's snake_case wire format to the
 * normalized UI types. Validates at runtime with zod and degrades gracefully: optional
 * fields that are missing stay undefined (never filled with invented values), and an
 * event that fails validation is dropped or turned into an explicit error event.
 */
import { z } from "zod";
import type { PortfolioResult, PortfolioSectionKey } from "@/lib/chat/portfolioTypes";

/** snake_case -> camelCase keys and null -> undefined, recursively (portfolio payloads).
 *  Map keys that are tickers (e.g. "RELIANCE.NS") contain no underscores and are kept. */
export function camelize(value: unknown): any {
  if (value === null) return undefined;
  if (Array.isArray(value)) return value.map((v) => (v === null ? null : camelize(v)));
  if (typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([k, v]) => [
      k.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase()),
      camelize(v),
    ]),
  );
}
import type {
  AgentState,
  AnalysisResult,
  AssetMatch,
  ChartSeries,
  Historical,
  Quote,
  Risk,
  Snapshot,
  Sources,
  StreamEvent,
  TextReply,
} from "@/lib/chat/types";

const optStr = z.string().nullish().transform((v) => v ?? undefined);
const optNum = z.number().nullish().transform((v) => v ?? undefined);
const nullableNum = z.number().nullish().transform((v) => v ?? null);
const nullableStr = z.string().nullish().transform((v) => v ?? null);

const marketState = z.enum(["open", "pre", "post", "closed"]).catch("closed");
const sentiment = z.enum(["positive", "neutral", "negative"]).nullish().transform((v) => v ?? undefined);
const quality = z
  .enum(["good", "missing_fields", "degraded", "suspect"])
  .nullish()
  .transform((v) => v ?? undefined);

const assetSchema = z.object({ symbol: z.string(), name: z.string(), exchange: optStr });

const factSchema = z.object({
  label: z.string(),
  value: z.union([z.number(), z.string()]),
  kind: z.enum(["currency", "percent", "number", "compact", "text"]).catch("text"),
  unit: optStr,
});

const snapshotSchema = z
  .object({
    summary: nullableStr,
    price: optNum,
    change_pct: optNum,
    previous_close: optNum,
    currency: optStr,
    market_state: marketState.optional(),
    as_of: optStr,
    facts: z.array(factSchema).catch([]).default([]),
  })
  .transform(
    (s): Snapshot => ({
      summary: s.summary,
      price: s.price,
      changePct: s.change_pct,
      previousClose: s.previous_close,
      currency: s.currency,
      marketState: s.market_state,
      asOf: s.as_of,
      facts: s.facts,
    }),
  );

const sourcesSchema = z
  .object({
    summary: nullableStr,
    items: z
      .array(
        z.object({
          publisher: z.string(),
          title: z.string(),
          url: z.string(),
          published_at: optStr,
          sentiment,
          sentiment_source: z.enum(["alpha_vantage", "llm"]).nullish().transform((v) => v ?? undefined),
          themes: z.array(z.string()).catch([]).default([]),
        }),
      )
      .catch([])
      .default([]),
  })
  .transform(
    (s): Sources => ({
      summary: s.summary,
      items: s.items.map((i) => ({
        publisher: i.publisher,
        title: i.title,
        url: i.url,
        publishedAt: i.published_at,
        sentiment: i.sentiment,
        sentimentSource: i.sentiment_source,
        themes: i.themes,
      })),
    }),
  );

const historicalSchema = z
  .object({
    summary: nullableStr,
    metrics: z
      .array(
        z.object({
          key: z.string(),
          label: z.string(),
          value: z.union([z.number(), z.string()]),
          kind: z.enum(["currency", "percent", "number", "text"]).catch("text"),
        }),
      )
      .catch([])
      .default([]),
    seasonality: z
      .array(z.object({ month: z.number(), avg_return: z.number(), observations: z.number() }))
      .catch([])
      .default([]),
  })
  .transform(
    (h): Historical => ({
      summary: h.summary,
      metrics: h.metrics,
      seasonality: h.seasonality.map((p) => ({
        month: p.month,
        avgReturn: p.avg_return,
        observations: p.observations,
      })),
    }),
  );

const breakdownSchema = z.array(z.object({ label: z.string(), value: z.number(), detail: z.string() }));

const riskSchema = z
  .object({
    risk_score: nullableNum,
    risk_band: nullableStr,
    trust_score: nullableNum,
    trust_band: nullableStr,
    trust_reasons: z.array(z.string()).catch([]).default([]),
    breakdown: breakdownSchema.catch([]).default([]),
    trust_breakdown: breakdownSchema.catch([]).default([]),
    var_sensitivity: z
      .array(z.object({ confidence: z.number(), var: z.number(), cvar: optNum }))
      .catch([])
      .default([]),
    drawdown: z.array(z.object({ date: z.string(), value: z.number() })).catch([]).default([]),
    sentiment_distribution: z
      .object({ positive: z.number(), neutral: z.number(), negative: z.number() })
      .nullish()
      .transform((v) => v ?? undefined),
    macro: z
      .array(
        z.object({ label: z.string(), value: optNum, unit: optStr, date: optStr, change: optNum }),
      )
      .catch([])
      .default([]),
    weather: z
      .array(
        z.object({
          location: z.string(),
          date: z.string(),
          description: z.string(),
          value: z.number(),
          unit: z.string(),
        }),
      )
      .catch([])
      .default([]),
    correlations: z
      .array(
        z.object({
          asset: z.string(),
          symbol: z.string(),
          correlation: nullableNum,
          observations: z.number().optional(),
        }),
      )
      .catch([])
      .default([]),
  })
  .transform(
    (r): Risk => ({
      riskScore: r.risk_score,
      riskBand: r.risk_band,
      trustScore: r.trust_score,
      trustBand: r.trust_band,
      trustReasons: r.trust_reasons,
      breakdown: r.breakdown,
      trustBreakdown: r.trust_breakdown,
      varSensitivity: r.var_sensitivity,
      drawdown: r.drawdown,
      sentimentDistribution: r.sentiment_distribution,
      macro: r.macro,
      weather: r.weather,
      correlations: r.correlations,
    }),
  );

const evidenceSchema = z
  .object({
    id: z.string(),
    agent: z.string(),
    label: z.string(),
    value: z.union([z.number(), z.string()]).nullable(),
    unit: optStr,
    display: z.string(),
    source: z.string(),
    url: optStr,
    observed_at: optStr,
  })
  .transform(({ observed_at, ...rest }) => ({ ...rest, observedAt: observed_at }));

const auditSchema = z
  .object({ checked_numbers: z.number(), unverified_numbers: z.array(z.string()) })
  .catch({ checked_numbers: 0, unverified_numbers: [] })
  .transform((a) => ({ checkedNumbers: a.checked_numbers, unverifiedNumbers: a.unverified_numbers }));

const resultSchema = z
  .object({
    message_id: z.string(),
    run_id: z.string(),
    thread_id: z.string(),
    generated_at: z.string(),
    narrative_source: z.enum(["llm", "rules"]),
    partial: z.boolean().catch(false).default(false),
    failed_agents: z.array(z.string()).catch([]).default([]),
    langsmith_run_id: optStr,
    asset: assetSchema,
    executive_answer: optStr,
    snapshot: snapshotSchema,
    sources: sourcesSchema,
    historical: historicalSchema,
    suggestions: z.object({
      items: z
        .array(
          z.object({
            action: z.string(),
            rationale: z.string(),
            horizon: optStr,
            confidence: optNum,
            evidence_ids: z.array(z.string()).catch([]).default([]),
          }),
        )
        .catch([]),
      disclaimer: z.string().catch("Not investment advice."),
    }),
    risk: riskSchema,
    evidence: z.array(evidenceSchema).catch([]).default([]),
    audit: auditSchema.default({ checked_numbers: 0, unverified_numbers: [] }),
  })
  .transform(
    (r): AnalysisResult => ({
      messageId: r.message_id,
      runId: r.run_id,
      threadId: r.thread_id,
      generatedAt: r.generated_at,
      narrativeSource: r.narrative_source,
      partial: r.partial,
      failedAgents: r.failed_agents,
      langsmithRunId: r.langsmith_run_id,
      asset: r.asset,
      executiveAnswer: r.executive_answer,
      snapshot: r.snapshot,
      sources: r.sources,
      historical: r.historical,
      suggestions: {
        disclaimer: r.suggestions.disclaimer,
        items: r.suggestions.items.map((s) => ({
          action: s.action,
          rationale: s.rationale,
          horizon: s.horizon,
          confidence: s.confidence,
          evidenceIds: s.evidence_ids,
        })),
      },
      risk: r.risk,
      evidence: r.evidence,
      audit: r.audit,
    }),
  );

const replySchema = z
  .object({
    message_id: z.string(),
    run_id: z.string(),
    thread_id: z.string(),
    generated_at: z.string(),
    narrative_source: z.enum(["llm", "rules"]),
    content: z.string(),
    evidence: z.array(evidenceSchema).catch([]).default([]),
    audit: auditSchema.default({ checked_numbers: 0, unverified_numbers: [] }),
    langsmith_run_id: optStr,
  })
  .transform(
    (r): TextReply => ({
      messageId: r.message_id,
      runId: r.run_id,
      threadId: r.thread_id,
      generatedAt: r.generated_at,
      narrativeSource: r.narrative_source,
      content: r.content,
      evidence: r.evidence,
      audit: r.audit,
      langsmithRunId: r.langsmith_run_id,
    }),
  );

const agentUpdateSchema = z
  .object({
    agent_id: z.string(),
    name: z.string(),
    role: optStr,
    status: z.enum(["queued", "running", "done", "error"]),
    message: optStr,
    started_at: optStr,
    ended_at: optStr,
    data_quality: quality,
  })
  .transform(
    (a): AgentState => ({
      agentId: a.agent_id,
      name: a.name,
      role: a.role,
      status: a.status,
      message: a.message,
      startedAt: a.started_at,
      endedAt: a.ended_at,
      dataQuality: a.data_quality,
    }),
  );

const SECTION_SCHEMAS = {
  snapshot: snapshotSchema,
  sources: sourcesSchema,
  historical: historicalSchema,
  risk: riskSchema,
} as const;

/** Converts one raw SSE `data:` payload into a normalized event, or null to ignore it. */
export function toStreamEvent(raw: unknown): StreamEvent | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const seq = typeof obj.seq === "number" ? obj.seq : -1;
  switch (obj.type) {
    case "run_started": {
      const p = z
        .object({
          run_id: z.string(),
          thread_id: z.string(),
          message_id: z.string(),
          started_at: z.string(),
          llm_enabled: z.boolean().catch(false),
          langsmith_run_id: optStr,
        })
        .safeParse(obj);
      return p.success
        ? {
            seq,
            type: "run_started",
            runId: p.data.run_id,
            threadId: p.data.thread_id,
            messageId: p.data.message_id,
            startedAt: p.data.started_at,
            llmEnabled: p.data.llm_enabled,
            langsmithRunId: p.data.langsmith_run_id,
          }
        : null;
    }
    case "agent_update": {
      const p = agentUpdateSchema.safeParse(obj);
      return p.success ? { seq, type: "agent_update", ...p.data } : null;
    }
    case "section": {
      const section = obj.section as keyof typeof SECTION_SCHEMAS;
      const schema = SECTION_SCHEMAS[section];
      if (!schema) return null;
      const p = schema.safeParse(obj.data);
      return p.success ? ({ seq, type: "section", section, data: p.data } as StreamEvent) : null;
    }
    case "final": {
      const p = resultSchema.safeParse(obj.result);
      if (p.success) return { seq, type: "final", result: p.data };
      console.error("Malformed analysis result", p.error.issues.slice(0, 5));
      return { seq, type: "error", message: "The analysis result was malformed.", recoverable: true };
    }
    case "reply": {
      const p = replySchema.safeParse(obj.reply);
      if (p.success) return { seq, type: "reply", reply: p.data };
      return { seq, type: "error", message: "The reply was malformed.", recoverable: true };
    }
    case "error": {
      const message = typeof obj.message === "string" ? obj.message : "The analysis failed.";
      return { seq, type: "error", message, recoverable: obj.recoverable !== false };
    }
    case "cancelled":
      return { seq, type: "cancelled", message: typeof obj.message === "string" ? obj.message : "Stopped." };
    case "portfolio_section": {
      const section = obj.section as PortfolioSectionKey;
      if (!["portfolio", "sentiment", "event", "analogs", "exposure"].includes(section)) return null;
      return { seq, type: "portfolio_section", section, data: camelize(obj.data) };
    }
    case "portfolio_final": {
      const result = camelize(obj.result) as PortfolioResult;
      if (typeof result?.bottomLine !== "string" || !result.portfolio || !Array.isArray(result.evidence)) {
        return { seq, type: "error", message: "The portfolio result was malformed.", recoverable: true };
      }
      return { seq, type: "portfolio_final", result };
    }
    default:
      return null;
  }
}

/* ─── Market data ─── */

const chartSchema = z
  .object({
    symbol: z.string(),
    name: optStr,
    currency: optStr,
    exchange: optStr,
    exchange_timezone: optStr,
    price: optNum,
    previous_close: optNum,
    change_pct: optNum,
    market_state: marketState,
    market_time: optStr,
    range: z.string(),
    interval: z.string(),
    bars: z.array(
      z.object({
        t: z.string(),
        open: optNum,
        high: optNum,
        low: optNum,
        close: z.number(),
        volume: optNum,
      }),
    ),
  })
  .transform(
    (c): ChartSeries => ({
      symbol: c.symbol,
      name: c.name,
      currency: c.currency,
      exchange: c.exchange,
      exchangeTimezone: c.exchange_timezone,
      price: c.price,
      previousClose: c.previous_close,
      changePct: c.change_pct,
      marketState: c.market_state,
      marketTime: c.market_time,
      range: c.range,
      interval: c.interval,
      bars: c.bars.map((b) => ({ ...b, t: Date.parse(b.t) })).filter((b) => Number.isFinite(b.t)),
    }),
  );

export function toChartSeries(raw: unknown): ChartSeries {
  return chartSchema.parse(raw);
}

const quoteSchema = z
  .object({
    symbol: z.string(),
    price: optNum,
    change_pct: optNum,
    previous_close: optNum,
    currency: optStr,
    market_state: marketState,
    market_time: optStr,
    fetched_at: z.string(),
  })
  .transform(
    (q): Quote => ({
      symbol: q.symbol,
      price: q.price,
      changePct: q.change_pct,
      previousClose: q.previous_close,
      currency: q.currency,
      marketState: q.market_state,
      marketTime: q.market_time,
      fetchedAt: q.fetched_at,
    }),
  );

export function toQuote(raw: unknown): Quote {
  return quoteSchema.parse(raw);
}

const searchSchema = z.object({
  results: z.array(
    z
      .object({
        symbol: z.string(),
        name: optStr,
        shortname: optStr,
        longname: optStr,
        exchange: optStr,
        quote_type: optStr,
        quoteType: optStr,
        sector: optStr,
      })
      .transform((r) => ({
        symbol: r.symbol,
        name: r.name || r.shortname || r.longname || r.symbol,
        exchange: r.exchange,
        quoteType: r.quote_type || r.quoteType,
        sector: r.sector,
      })),
  ),
});

export function toAssetMatches(raw: unknown): AssetMatch[] {
  return searchSchema.parse(raw).results;
}
