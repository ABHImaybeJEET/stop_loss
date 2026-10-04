import { PORTFOLIO_SYMBOL } from "@/lib/symbols";
import type { AgentState, AnalysisMessage, AssistantMessage, ChatMessage, StreamEvent } from "@/lib/chat/types";

export function newId(): string {
  return crypto.randomUUID().replace(/-/g, "");
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function isTerminal(event: StreamEvent): boolean {
  return event.type === "final" || event.type === "portfolio_final" || event.type === "reply" || event.type === "error" || event.type === "cancelled";
}

function upsertAgent(agents: AgentState[], update: AgentState): AgentState[] {
  const index = agents.findIndex((a) => a.agentId === update.agentId);
  if (index === -1) return [...agents, update];
  const merged: AgentState = {
    ...agents[index],
    ...Object.fromEntries(Object.entries(update).filter(([, v]) => v !== undefined)),
  } as AgentState;
  const next = agents.slice();
  next[index] = merged;
  return next;
}

/** Pure: folds one stream event into an assistant message. */
export function applyEvent(message: AssistantMessage, event: StreamEvent): AssistantMessage {
  const base = { ...message, lastSeq: Math.max(message.lastSeq, event.seq) };
  switch (event.type) {
    case "run_started":
      return { ...base, runId: event.runId, startedAt: event.startedAt, llmEnabled: event.llmEnabled };
    case "agent_update": {
      const { seq: _seq, type: _type, ...agent } = event;
      return { ...base, agents: upsertAgent(base.agents, agent) };
    }
    case "section":
      if (base.kind !== "assistant-analysis") return base;
      return { ...base, partial: { ...base.partial, [event.section]: event.data } };
    case "final":
      return {
        ...(base as AnalysisMessage),
        kind: "assistant-analysis",
        partial: {},
        result: event.result,
        status: "complete",
        endedAt: nowIso(),
        error: undefined,
      };
    case "portfolio_section": {
      if (base.kind !== "assistant-portfolio") return base;
      return { ...base, portfolioPartial: { ...base.portfolioPartial, [event.section]: event.data } };
    }
    case "portfolio_final": {
      const { partial: _p, result: _r, ...rest } = base as AnalysisMessage;
      return {
        ...rest,
        kind: "assistant-portfolio",
        portfolioPartial: {},
        portfolio: event.result,
        status: "complete",
        endedAt: nowIso(),
        error: undefined,
      } as AssistantMessage;
    }
    case "reply": {
      const { partial: _p, result: _r, ...rest } = base as AnalysisMessage;
      return { ...rest, kind: "assistant-text", reply: event.reply, status: "complete", endedAt: nowIso(), error: undefined };
    }
    case "error":
      return {
        ...base,
        status: "error",
        endedAt: nowIso(),
        error: { message: event.message, recoverable: event.recoverable },
        agents: base.agents.map((a) =>
          a.status === "running" || a.status === "queued" ? { ...a, status: "error", message: a.message } : a,
        ),
      };
    case "cancelled":
      return {
        ...base,
        status: "cancelled",
        endedAt: nowIso(),
        agents: base.agents.map((a) =>
          a.status === "running" || a.status === "queued" ? { ...a, status: "error", message: "Stopped" } : a,
        ),
      };
    default:
      return base;
  }
}

export function pendingAssistant(params: {
  id: string;
  userMessageId: string;
  prompt: string;
  asset: AnalysisMessage["asset"];
}): AssistantMessage {
  const base = {
    ...params,
    createdAt: nowIso(),
    status: "streaming" as const,
    agents: [],
    startedAt: nowIso(),
    lastSeq: -1,
  };
  return params.asset.symbol === PORTFOLIO_SYMBOL
    ? { ...base, kind: "assistant-portfolio", portfolioPartial: {} }
    : { ...base, kind: "assistant-analysis", partial: {} };
}

export function isAssistant(message: ChatMessage): message is AssistantMessage {
  return (
    message.kind === "assistant-analysis" ||
    message.kind === "assistant-text" ||
    message.kind === "assistant-portfolio"
  );
}

export type MessagesAction =
  | { type: "reset"; messages: ChatMessage[] }
  | { type: "append"; messages: ChatMessage[] }
  | { type: "put"; message: ChatMessage }
  | { type: "remove"; id: string };

export function messagesReducer(state: ChatMessage[], action: MessagesAction): ChatMessage[] {
  switch (action.type) {
    case "reset":
      return action.messages;
    case "append":
      return [...state, ...action.messages];
    case "put": {
      const index = state.findIndex((m) => m.id === action.message.id);
      if (index === -1) return [...state, action.message];
      const next = state.slice();
      next[index] = action.message;
      return next;
    }
    case "remove":
      return state.filter((m) => m.id !== action.id);
  }
}
