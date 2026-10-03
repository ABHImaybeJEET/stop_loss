import React from "react";
import {
  CandlestickChart,
  Check,
  Globe,
  Landmark,
  Newspaper,
  Shield,
  ShieldCheck,
  Sigma,
  Workflow,
  X,
  History,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/components/ui/primitives";
import { formatDuration } from "@/lib/format";
import type { AgentState } from "@/lib/chat/types";

const ICONS: Record<string, LucideIcon> = {
  coordinator: Workflow,
  market: CandlestickChart,
  news: Newspaper,
  impact: Globe,
  analogs: History,
  quant: Sigma,
  hedging: Shield,
  audit: ShieldCheck,
};

const STATUS_LABEL: Record<AgentState["status"], string> = {
  queued: "Queued",
  running: "Running",
  done: "Done",
  error: "Error",
};

export function agentElapsed(agent: AgentState, now: number): number | null {
  if (!agent.startedAt) return null;
  const start = Date.parse(agent.startedAt);
  const end = agent.endedAt ? Date.parse(agent.endedAt) : agent.status === "running" ? now : start;
  return Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, end - start) : null;
}

export default function AgentRow({ agent, now }: { agent: AgentState; now: number }) {
  const Icon = ICONS[agent.agentId] ?? Workflow;
  const elapsed = agentElapsed(agent, now);
  const degraded = agent.status === "done" && agent.dataQuality && agent.dataQuality !== "good";
  return (
    <li
      className={cn(
        "relative grid grid-cols-[1.75rem_1fr_auto] items-center gap-x-3 overflow-hidden border-b border-line px-3 py-2 last:border-b-0",
        agent.status === "queued" && "text-muted-soft",
      )}
      data-testid={`agent-${agent.agentId}`}
      data-status={agent.status}
    >
      {agent.status === "running" && (
        <span aria-hidden="true" className="sl-scan pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-subtle to-transparent" />
      )}
      <span
        className={cn(
          "relative flex h-7 w-7 items-center justify-center border",
          agent.status === "running" && "border-ink bg-white text-ink",
          agent.status === "done" && "border-ink bg-ink text-white",
          agent.status === "error" && "border-loss bg-loss-soft text-loss",
          agent.status === "queued" && "border-line bg-white text-muted-soft",
        )}
        aria-hidden="true"
      >
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="relative min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn("truncate text-xs font-semibold", agent.status === "queued" ? "text-muted" : "text-ink")}>{agent.name}</span>
          {degraded && (
            <span className="font-mono text-2xs uppercase text-muted" title={`Data quality: ${agent.dataQuality}`}>
              · {agent.dataQuality?.replace("_", " ")}
            </span>
          )}
        </div>
        <p className={cn("truncate font-mono text-2xs", agent.status === "error" ? "text-loss" : "text-muted")} title={agent.message}>
          {agent.message ?? agent.role ?? "Waiting"}
        </p>
      </div>
      <div className="relative flex items-center gap-2">
        <span className="num w-12 text-right text-2xs text-muted">{elapsed !== null ? formatDuration(elapsed) : ""}</span>
        <span className="flex w-16 items-center justify-end gap-1 font-mono text-2xs uppercase tracking-wider">
          {agent.status === "running" && <span className="sl-pulse h-1.5 w-1.5 rounded-full bg-ink" aria-hidden="true" />}
          {agent.status === "done" && <Check className="h-3 w-3" aria-hidden="true" />}
          {agent.status === "error" && <X className="h-3 w-3 text-loss" aria-hidden="true" />}
          <span className={agent.status === "error" ? "text-loss" : undefined}>{STATUS_LABEL[agent.status]}</span>
        </span>
      </div>
    </li>
  );
}
