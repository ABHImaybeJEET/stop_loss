"use client";

import React, { useEffect, useState } from "react";
import { ChevronDown, Cpu } from "lucide-react";
import AgentRow from "@/components/chat/AgentRow";
import { cn } from "@/components/ui/primitives";
import { formatDuration } from "@/lib/format";
import type { AgentState, RunStatus } from "@/lib/chat/types";

interface Props {
  agents: AgentState[];
  status: RunStatus;
  startedAt: string;
  endedAt?: string;
  llmEnabled?: boolean;
}

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

const STATUS_TEXT: Record<RunStatus, string> = {
  streaming: "Running",
  complete: "Completed",
  error: "Failed",
  cancelled: "Stopped",
};

/** Live multi-agent execution view; collapses into a one-line summary when the run ends. */
export default function OrchestrationPanel({ agents, status, startedAt, endedAt, llmEnabled }: Props) {
  const live = status === "streaming";
  const [expanded, setExpanded] = useState(live);
  useEffect(() => setExpanded(live), [live]);
  const now = useNow(live);
  const start = Date.parse(startedAt);
  const end = endedAt ? Date.parse(endedAt) : now;
  const total = Number.isFinite(start) ? Math.max(0, (live ? now : end) - start) : 0;
  const done = agents.filter((a) => a.status === "done").length;
  const failed = agents.filter((a) => a.status === "error").length;
  const panelId = `orch-${startedAt}`;

  return (
    <div className="border border-line bg-white" data-testid="orchestration-panel" data-state={live ? "live" : "collapsed"}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-canvas"
        data-testid="orchestration-summary"
      >
        <span className="flex min-w-0 items-center gap-2">
          <Cpu className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate font-mono text-2xs font-bold uppercase tracking-widest text-ink">
            {live ? "Agents working" : "Agent log"}
          </span>
          <span className="num truncate text-2xs text-muted">
            {agents.length || 8} agents · {formatDuration(total)} · {STATUS_TEXT[status]}
            {live && agents.length > 0 && ` · ${done}/${agents.length} done`}
            {failed > 0 && ` · ${failed} failed`}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {live && <span className="sl-pulse h-1.5 w-1.5 rounded-full bg-ink" aria-hidden="true" />}
          {llmEnabled === false && !live && (
            <span className="hidden font-mono text-2xs uppercase text-muted sm:inline" title="No OPENAI_API_KEY on the backend">
              rules mode
            </span>
          )}
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-300", expanded && "rotate-180")} aria-hidden="true" />
        </span>
      </button>
      <div
        id={panelId}
        className={cn(
          "grid transition-[grid-template-rows] duration-500 ease-in-out",
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          <ol className="border-t border-line" aria-label="Agent progress">
            {agents.length === 0
              ? Array.from({ length: 8 }, (_, i) => (
                  <li key={i} className="flex items-center gap-3 border-b border-line px-3 py-2.5 last:border-b-0">
                    <span className="h-7 w-7 animate-pulse bg-subtle" />
                    <span className="h-3 w-40 animate-pulse bg-subtle" />
                  </li>
                ))
              : agents.map((agent) => <AgentRow key={agent.agentId} agent={agent} now={now} />)}
          </ol>
        </div>
      </div>
    </div>
  );
}
