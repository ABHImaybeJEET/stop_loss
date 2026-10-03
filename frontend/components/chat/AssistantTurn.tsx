"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, RotateCw } from "lucide-react";
import AssetLiveChart from "@/components/chat/AssetLiveChart";
import { EvidenceRef, evidenceMap } from "@/components/chat/EvidenceText";
import FeedbackBar from "@/components/chat/FeedbackBar";
import OrchestrationPanel from "@/components/chat/OrchestrationPanel";
import RiskTrustPanel from "@/components/chat/RiskTrustPanel";
import HistoricalSection from "@/components/chat/sections/HistoricalSection";
import SnapshotSection from "@/components/chat/sections/SnapshotSection";
import SourcesSection from "@/components/chat/sections/SourcesSection";
import SuggestionsSection from "@/components/chat/sections/SuggestionsSection";
import { Badge, Button } from "@/components/ui/primitives";
import { relativeTime } from "@/lib/format";
import type { AssistantMessage, FeedbackState, TextMessage } from "@/lib/chat/types";

interface Props {
  message: AssistantMessage;
  threadId: string | null;
  canRetry: boolean;
  onRetry: (id: string) => void;
  onResume: (id: string) => void;
  onFeedback: (id: string, feedback: FeedbackState | undefined) => void;
}

const AGENT_NAMES: Record<string, string> = {
  market: "Market Data",
  news: "News Sentiment",
  macro: "Macro",
  weather: "Weather",
  quant: "Quant Risk",
};

function StatusBanner({ message, canRetry, onRetry, onResume }: Omit<Props, "threadId" | "onFeedback">) {
  if (message.status === "cancelled") {
    return (
      <div className="flex flex-wrap items-center gap-2 border border-line bg-canvas px-3 py-2" role="status">
        <span className="text-xs text-ink">Analysis stopped.</span>
        {canRetry && (
          <Button size="sm" className="ml-auto" onClick={() => onRetry(message.id)}>
            <RotateCw className="h-3 w-3" aria-hidden="true" /> Run again
          </Button>
        )}
      </div>
    );
  }
  if (message.status !== "error" || !message.error) return null;
  const lostConnection = /connection|stream/i.test(message.error.message) && message.runId;
  return (
    <div className="flex flex-wrap items-center gap-2 border border-loss bg-loss-soft px-3 py-2" role="alert" data-testid="run-error">
      <AlertTriangle className="h-3.5 w-3.5 text-loss" aria-hidden="true" />
      <span className="text-xs text-loss">{message.error.message}</span>
      <span className="ml-auto flex gap-1">
        {lostConnection && canRetry && (
          <Button size="sm" onClick={() => onResume(message.id)}>
            Resume
          </Button>
        )}
        {message.error.recoverable && canRetry && (
          <Button size="sm" onClick={() => onRetry(message.id)}>
            <RotateCw className="h-3 w-3" aria-hidden="true" /> Retry
          </Button>
        )}
      </span>
    </div>
  );
}

function TextReplyBody({ message }: { message: TextMessage }) {
  const evidence = useMemo(() => evidenceMap(message.reply.evidence), [message.reply.evidence]);
  const markdown = message.reply.content.replace(/\[(E\d+)\]/g, "[$1](#evidence-$1)");
  return (
    <div className="border border-line bg-white px-4 py-3" data-testid="text-reply">
      <div className="prose-terminal text-sm leading-relaxed text-ink-soft">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ href, children }) =>
              href?.startsWith("#evidence-") ? (
                <EvidenceRef id={href.slice("#evidence-".length)} evidence={evidence} />
              ) : (
                <a href={href} target="_blank" rel="noopener noreferrer" className="underline">
                  {children}
                </a>
              ),
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
            ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5">{children}</ul>,
            ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5">{children}</ol>,
            strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
            code: ({ children }) => <code className="num bg-subtle px-1 text-xs">{children}</code>,
            table: ({ children }) => <table className="mb-2 w-full border border-line text-xs">{children}</table>,
            th: ({ children }) => <th className="border border-line bg-canvas px-2 py-1 text-left">{children}</th>,
            td: ({ children }) => <td className="num border border-line px-2 py-1">{children}</td>,
          }}
        >
          {markdown}
        </ReactMarkdown>
      </div>
      {message.reply.audit.unverifiedNumbers.length > 0 && (
        <p className="mt-2 font-mono text-2xs text-loss">
          Not found in evidence: {message.reply.audit.unverifiedNumbers.join(", ")}. Treat these figures with caution.
        </p>
      )}
      <p className="mt-2 font-mono text-2xs text-muted">
        {message.reply.audit.checkedNumbers} figures checked against {message.reply.evidence.length} cited evidence items · Not
        investment advice.
      </p>
    </div>
  );
}

export default function AssistantTurn({ message, threadId, canRetry, onRetry, onResume, onFeedback }: Props) {
  const streaming = message.status === "streaming";
  const isText = message.kind === "assistant-text";
  const result = message.kind === "assistant-analysis" ? message.result : undefined;
  const partial = message.kind === "assistant-analysis" ? message.partial : {};
  const evidence = useMemo(() => evidenceMap(result?.evidence), [result?.evidence]);
  const hasData = Boolean(result || partial.snapshot || partial.sources || partial.historical || partial.risk);
  const showSections = !isText && (streaming || hasData);

  return (
    <article className="space-y-3" aria-label={`Analysis of ${message.asset.symbol}`} data-testid="assistant-turn" data-status={message.status}>
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center bg-ink font-mono text-[9px] font-bold text-white" aria-hidden="true">
          SL
        </span>
        <span className="text-xs font-semibold text-ink">StopLoss Agents</span>
        <time className="font-mono text-2xs text-muted" dateTime={message.createdAt}>
          {relativeTime(message.createdAt)}
        </time>
        {result?.narrativeSource === "rules" && <Badge title="No LLM configured on the backend">rules mode</Badge>}
      </div>

      <OrchestrationPanel
        agents={message.agents}
        status={message.status}
        startedAt={message.startedAt}
        endedAt={message.endedAt}
        llmEnabled={message.llmEnabled}
      />

      <StatusBanner message={message} canRetry={canRetry} onRetry={onRetry} onResume={onResume} />

      {result?.partial && (
        <div className="flex flex-wrap items-center gap-2 border border-line-strong bg-canvas px-3 py-2" role="status">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="text-xs text-ink">
            Partial result: {result.failedAgents.map((a) => AGENT_NAMES[a] ?? a).join(", ")} unavailable. Other sections use live data.
          </span>
          {canRetry && (
            <Button size="sm" className="ml-auto" onClick={() => onRetry(message.id)}>
              <RotateCw className="h-3 w-3" aria-hidden="true" /> Retry
            </Button>
          )}
        </div>
      )}

      {isText && <TextReplyBody message={message as TextMessage} />}

      {showSections && (
        <div className="space-y-3" data-testid="result-sections">
          <SnapshotSection asset={message.asset} snapshot={result?.snapshot ?? partial.snapshot} evidence={evidence} pending={streaming} />
          <SourcesSection
            sources={result?.sources ?? partial.sources}
            evidence={evidence}
            pending={streaming}
            failed={Boolean(result?.failedAgents.includes("news"))}
          />
          <HistoricalSection historical={result?.historical ?? partial.historical} evidence={evidence} pending={streaming} />
          <AssetLiveChart asset={message.asset} />
          <SuggestionsSection suggestions={result?.suggestions} evidence={evidence} pending={streaming} narrativeSource={result?.narrativeSource} />
          <RiskTrustPanel risk={result?.risk ?? partial.risk} evidence={result?.evidence ?? []} audit={result?.audit} pending={streaming} />
        </div>
      )}

      {message.status === "complete" && (
        <FeedbackBar
          key={`${message.id}-${message.feedback?.savedAt ?? "none"}`}
          threadId={threadId}
          messageId={message.id}
          feedback={message.feedback}
          onChange={(fb) => onFeedback(message.id, fb)}
        />
      )}
    </article>
  );
}
