/**
 * Normalized client-side types for the analysis terminal. Raw backend payloads are
 * converted into these by `adapters/backendToUi.ts`; UI components only see these.
 * Extensions to the original contract are marked "ext" (see docs/DECISIONS.md ADR-T08).
 */

export type AgentStatus = "queued" | "running" | "done" | "error";
export type DataQuality = "good" | "missing_fields" | "degraded" | "suspect";
export type MarketState = "open" | "pre" | "post" | "closed";
export type SentimentLabel = "positive" | "neutral" | "negative";
export type SectionKey = "snapshot" | "sources" | "historical" | "suggestions" | "risk";
export type ProgressiveSection = "snapshot" | "sources" | "historical" | "risk";

export interface AssetRef {
  symbol: string;
  name: string;
  exchange?: string;
}

export interface AssetMatch extends AssetRef {
  quoteType?: string;
  sector?: string;
}

export interface AgentState {
  agentId: string;
  name: string;
  role?: string;
  status: AgentStatus;
  message?: string;
  startedAt?: string;
  endedAt?: string;
  dataQuality?: DataQuality;
}

export interface Fact {
  label: string;
  value: number | string;
  kind: "currency" | "percent" | "number" | "compact" | "text";
  unit?: string;
}

export interface Snapshot {
  summary: string | null;
  price?: number;
  changePct?: number;
  previousClose?: number; // ext
  currency?: string; // ext
  marketState?: MarketState; // ext
  asOf?: string; // ext
  facts: Fact[]; // ext: ordered list instead of Record so display order is stable
}

export interface SourceItem {
  publisher: string;
  title: string;
  url: string;
  publishedAt?: string;
  sentiment?: SentimentLabel;
  sentimentSource?: "alpha_vantage" | "llm"; // ext
  themes: string[]; // ext
}

export interface Sources {
  summary: string | null;
  items: SourceItem[];
}

export interface Metric {
  key: string;
  label: string;
  value: number | string;
  kind: "currency" | "percent" | "number" | "text";
}

export interface SeasonalityPoint {
  month: number;
  avgReturn: number;
  observations: number;
}

export interface Historical {
  summary: string | null;
  metrics: Metric[]; // ext
  seasonality: SeasonalityPoint[]; // ext
}

export interface Suggestion {
  action: string;
  rationale: string;
  horizon?: string;
  confidence?: number;
  evidenceIds: string[]; // ext
}

export interface Suggestions {
  items: Suggestion[];
  disclaimer: string;
}

export interface Breakdown {
  label: string;
  value: number;
  detail: string;
}

export interface Risk {
  riskScore: number | null; // null when inputs are missing (never fabricated)
  riskBand: string | null;
  trustScore: number | null;
  trustBand: string | null;
  trustReasons: string[];
  breakdown: Breakdown[];
  trustBreakdown: Breakdown[];
  varSensitivity: { confidence: number; var: number; cvar?: number }[];
  drawdown: { date: string; value: number }[];
  sentimentDistribution?: Record<SentimentLabel, number>;
  macro: { label: string; value?: number; unit?: string; date?: string; change?: number }[];
  weather: { location: string; date: string; description: string; value: number; unit: string }[];
  correlations?: CrossAssetCorrelation[];
}

export interface CrossAssetCorrelation {
  asset: string;
  symbol: string;
  correlation: number | null;
  observations?: number;
}

export interface EvidenceItem {
  id: string;
  agent: string;
  label: string;
  value: number | string | null;
  unit?: string;
  display: string;
  source: string;
  url?: string;
  observedAt?: string;
}

export interface Audit {
  checkedNumbers: number;
  unverifiedNumbers: string[];
}

export interface AnalysisResult {
  messageId: string;
  runId: string;
  threadId: string;
  generatedAt: string;
  narrativeSource: "llm" | "rules";
  partial: boolean;
  failedAgents: string[];
  langsmithRunId?: string;
  asset: AssetRef;
  executiveAnswer?: string;
  snapshot: Snapshot;
  sources: Sources;
  historical: Historical;
  suggestions: Suggestions;
  risk: Risk;
  evidence: EvidenceItem[];
  audit: Audit;
}

export interface TextReply {
  messageId: string;
  runId: string;
  threadId: string;
  generatedAt: string;
  narrativeSource: "llm" | "rules";
  content: string;
  evidence: EvidenceItem[];
  audit: Audit;
  langsmithRunId?: string;
}

export interface PartialSections {
  snapshot?: Snapshot;
  sources?: Sources;
  historical?: Historical;
  risk?: Risk;
}

export type StreamEvent = { seq: number } & (
  | { type: "run_started"; runId: string; threadId: string; messageId: string; startedAt: string; llmEnabled: boolean; langsmithRunId?: string }
  | ({ type: "agent_update" } & AgentState)
  | { type: "section"; section: "snapshot"; data: Snapshot }
  | { type: "section"; section: "sources"; data: Sources }
  | { type: "section"; section: "historical"; data: Historical }
  | { type: "section"; section: "risk"; data: Risk }
  | { type: "final"; result: AnalysisResult }
  | { type: "reply"; reply: TextReply }
  | { type: "error"; message: string; recoverable: boolean }
  | { type: "cancelled"; message: string }
);

/* ─── Conversation messages (persisted per thread) ─── */

export type RunStatus = "streaming" | "complete" | "error" | "cancelled";

export interface FeedbackState {
  rating: "up" | "down";
  tags: string[];
  comment?: string;
  savedAt: string;
}

interface MessageBase {
  id: string;
  createdAt: string;
}

export interface UserMessage extends MessageBase {
  kind: "user";
  content: string;
  asset: AssetRef;
}

export interface DividerMessage extends MessageBase {
  kind: "divider";
  asset: AssetRef;
}

interface AssistantBase extends MessageBase {
  userMessageId: string;
  prompt: string;
  asset: AssetRef;
  runId?: string;
  status: RunStatus;
  agents: AgentState[];
  startedAt: string;
  endedAt?: string;
  lastSeq: number;
  llmEnabled?: boolean;
  error?: { message: string; recoverable: boolean };
  feedback?: FeedbackState;
}

export interface AnalysisMessage extends AssistantBase {
  kind: "assistant-analysis";
  partial: PartialSections;
  result?: AnalysisResult;
}

export interface TextMessage extends AssistantBase {
  kind: "assistant-text";
  reply: TextReply;
}

export type AssistantMessage = AnalysisMessage | TextMessage;
export type ChatMessage = UserMessage | DividerMessage | AssistantMessage;

export interface ThreadMeta {
  id: string;
  title: string;
  asset?: AssetRef;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

/* ─── Market data ─── */

export interface ChartBar {
  t: number; // epoch ms
  open?: number;
  high?: number;
  low?: number;
  close: number;
  volume?: number;
}

export interface ChartSeries {
  symbol: string;
  name?: string;
  currency?: string;
  exchange?: string;
  exchangeTimezone?: string;
  price?: number;
  previousClose?: number;
  changePct?: number;
  marketState: MarketState;
  marketTime?: string;
  range: string;
  interval: string;
  bars: ChartBar[];
}

export interface Quote {
  symbol: string;
  price?: number;
  changePct?: number;
  previousClose?: number;
  currency?: string;
  marketState: MarketState;
  marketTime?: string;
  fetchedAt: string;
}
