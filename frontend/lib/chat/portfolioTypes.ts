import type { Audit, EvidenceItem, SentimentLabel } from "@/lib/chat/types";

/** Portfolio-mode answer (camelCased from the backend's PortfolioResult). */

export interface PfHoldingRow {
  symbol: string;
  name: string;
  sector?: string;
  quantity: number;
  avgPrice?: number;
  price?: number;
  changePct?: number;
  value?: number;
  weight?: number;
  target: boolean;
  status: "ok" | "unavailable";
}

export interface PfSnapshot {
  totalValue?: number;
  dayChange?: number;
  dayChangePct?: number;
  priced: number;
  holdings: PfHoldingRow[];
  sectors: { sector: string; weight: number }[];
}

export interface PfAlert {
  source: string;
  eventType: string;
  name: string;
  alertLevel?: string;
  country?: string;
  startedAt?: string;
  severity?: string;
  current?: boolean;
  url?: string;
}

export interface PfEvent {
  summary?: string;
  kind?: string;
  region?: string;
  severity?: string;
  description?: string;
  alerts: PfAlert[];
  macro: { label: string; latest?: number; unit?: string; latestDate?: string; changePct?: number; previousDate?: string; source?: string }[];
  flags: string[];
  weather: { location: string; date: string; description: string }[];
}

export interface PfExposureRow {
  symbol: string;
  name: string;
  sector?: string;
  value?: number;
  weight?: number;
  betaNifty?: number;
  betaBrent?: number;
  betaInr?: number;
  corrBrent?: number;
  sentimentScore?: number;
  analogN: number;
  analogMedian5d?: number;
  scenarioImpact?: number;
  scenarioLow?: number;
  scenarioHigh?: number;
  channelImpact?: number;
}

export interface PfExposure {
  summary?: string;
  rows: PfExposureRow[];
  totalImpact?: number;
  totalLow?: number;
  totalHigh?: number;
  method: string;
}

export interface PfAnalogAggregate {
  symbol: string;
  n: number;
  median5d?: number;
  min5d?: number;
  max5d?: number;
  shareNegative5d?: number;
  median20d?: number;
}

export interface PfAnalogs {
  summary?: string;
  query?: string;
  events: {
    id: string;
    title: string;
    date?: string;
    docType?: string;
    score: number;
    returns: Record<string, { d5?: number; d20?: number }>;
    brent5d?: number;
    nifty5d?: number;
  }[];
  aggregates: PfAnalogAggregate[];
  brent?: PfAnalogAggregate;
  nifty?: PfAnalogAggregate;
}

export interface PfSentiment {
  summary?: string;
  portfolioScore?: number;
  perHolding: { symbol: string; score?: number; positive: number; negative: number; neutral: number }[];
  items: {
    publisher: string;
    title: string;
    url: string;
    publishedAt?: string;
    sentiment?: SentimentLabel;
    sentimentSource?: string;
    themes: string[];
    symbols: string[];
  }[];
}

export interface PfRisk {
  summary?: string;
  riskScore?: number;
  riskBand?: string;
  perHolding: { symbol: string; riskScore?: number; band?: string; vol1y?: number; var951d?: number; maxDrawdown1y?: number; beta?: number }[];
  trustScore?: number;
  trustBand?: string;
  trustReasons: string[];
  niftyHedgeNotional?: number;
}

export interface PfRecommendation {
  action: string;
  kind: "hedge" | "reduce" | "add" | "rebalance" | "monitor";
  symbols: string[];
  size?: string;
  rationale: string;
  horizon?: string;
  confidence?: number;
  evidenceIds: string[];
}

export interface PfStep {
  agent: string;
  name: string;
  status: string;
  summary?: string;
  evidenceIds: string[];
}

export interface PortfolioResult {
  kind: "portfolio";
  messageId: string;
  runId: string;
  threadId: string;
  generatedAt: string;
  narrativeSource: "llm" | "rules";
  partial: boolean;
  failedAgents: string[];
  bottomLine: string;
  portfolio: PfSnapshot;
  event: PfEvent;
  exposure: PfExposure;
  analogs: PfAnalogs;
  sentiment: PfSentiment;
  risk: PfRisk;
  recommendations: PfRecommendation[];
  disclaimer: string;
  evidence: EvidenceItem[];
  audit: Audit;
  steps: PfStep[];
}

export type PortfolioSectionKey = "portfolio" | "sentiment" | "event" | "analogs" | "exposure";

export interface PortfolioPartial {
  portfolio?: PfSnapshot;
  sentiment?: Partial<PfSentiment>;
  event?: PfEvent;
  analogs?: PfAnalogs;
  exposure?: PfExposure;
}
