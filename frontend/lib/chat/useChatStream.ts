"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { toStreamEvent } from "@/adapters/backendToUi";
import {
  ApiError,
  AuthExpiredError,
  cancelRun,
  fetchActiveRun,
  openChatStream,
  openResumeStream,
  toChatAsset,
  type ChatBody,
} from "@/lib/chat/api";
import {
  applyEvent,
  isAssistant,
  isTerminal,
  messagesReducer,
  newId,
  nowIso,
  pendingAssistant,
} from "@/lib/chat/reducer";
import { readSSE } from "@/lib/chat/sse";
import { holdingsBody, scopeAsset, type ChatScope } from "@/lib/chat/scope";
import { PORTFOLIO_SYMBOL, displaySymbol } from "@/lib/symbols";
import type { Holding } from "@/lib/portfolio/types";
import type { AssetRef, AssistantMessage, ChatMessage, FeedbackState, StreamEvent } from "@/lib/chat/types";

const MAX_RESUMES = 3;

interface Options {
  /** Persist one message (create or overwrite) in the given thread. */
  persist: (threadId: string, message: ChatMessage) => void;
  /** Delete one stored message (used when a failed answer is replaced by a retry). */
  discard: (threadId: string, messageId: string) => void;
  /** Create the thread on first send; returns its id. */
  ensureThread: (prompt: string, asset: AssetRef) => Promise<string>;
  onAuthExpired: () => void;
  /** Current holdings, sent with portfolio-mode questions (and their retries). */
  portfolioHoldings: () => Holding[];
  /** Screen-reader progress announcements. */
  announce: (text: string) => void;
}

interface ActiveRun {
  assistantId: string;
  controller: AbortController;
  runId?: string;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function useChatStream(threadId: string | null, options: Options) {
  const [messages, dispatch] = useReducer(messagesReducer, []);
  const [running, setRunning] = useState(false);
  const activeRef = useRef<ActiveRun | null>(null);
  const threadRef = useRef<string | null>(threadId);
  const sendingRef = useRef(false);
  const messagesRef = useRef<ChatMessage[]>([]);
  const optionsRef = useRef(options);
  optionsRef.current = options;
  messagesRef.current = messages;

  /** Request body for a scope: portfolio questions carry the current holdings. */
  const chatBody = (threadId: string, messageId: string, prompt: string, asset: AssetRef): ChatBody =>
    asset.symbol === PORTFOLIO_SYMBOL
      ? {
          thread_id: threadId,
          message_id: messageId,
          prompt,
          mode: "portfolio",
          holdings: holdingsBody(optionsRef.current.portfolioHoldings()),
        }
      : { thread_id: threadId, message_id: messageId, prompt, mode: "ticker", asset: toChatAsset(asset) };
  // Follows the URL; send() sets it early when it creates a thread before the URL updates.
  useEffect(() => {
    threadRef.current = threadId;
  }, [threadId]);

  const put = useCallback((message: ChatMessage, persist = false) => {
    dispatch({ type: "put", message });
    const tid = threadRef.current;
    if (persist && tid) optionsRef.current.persist(tid, message);
  }, []);

  /** Consumes one SSE response into `current`. Returns the updated message. */
  const consume = useCallback(
    async (response: Response, current: AssistantMessage, active: ActiveRun) => {
      let message = current;
      let terminal = false;
      if (!response.body) return { message, terminal };
      for await (const raw of readSSE(response.body)) {
        const event = toStreamEvent(raw);
        if (!event) continue;
        if (event.seq >= 0 && event.seq <= message.lastSeq) continue; // replayed duplicate
        message = applyEvent(message, event);
        if (event.type === "run_started") {
          active.runId = event.runId;
          put(message, true); // persist the run id so a reload can re-attach
        } else {
          put(message);
        }
        announceEvent(event, optionsRef.current.announce);
        if (isTerminal(event)) {
          terminal = true;
          break;
        }
      }
      return { message, terminal };
    },
    [put],
  );

  const execute = useCallback(
    async (initial: AssistantMessage, open: (signal: AbortSignal) => Promise<Response>) => {
      const active: ActiveRun = { assistantId: initial.id, controller: new AbortController(), runId: initial.runId };
      activeRef.current = active;
      setRunning(true);
      let message = initial;
      try {
        let response = await open(active.controller.signal);
        for (let attempt = 0; ; attempt++) {
          const outcome = await consume(response, message, active);
          message = outcome.message;
          if (outcome.terminal || active.controller.signal.aborted) break;
          if (!active.runId || attempt >= MAX_RESUMES) {
            message = applyEvent(message, {
              seq: message.lastSeq,
              type: "error",
              message: "Connection to the analysis stream was lost.",
              recoverable: true,
            });
            break;
          }
          optionsRef.current.announce("Connection dropped, resuming analysis stream");
          await sleep(600 * 2 ** attempt);
          response = await openResumeStream(active.runId, message.lastSeq, active.controller.signal);
        }
      } catch (err) {
        if (active.controller.signal.aborted) {
          // Stopped by the user; stop() already recorded the cancellation.
          message = messagesRef.current.find((m) => m.id === message.id && isAssistant(m)) as AssistantMessage ?? message;
        } else if (err instanceof AuthExpiredError) {
          message = applyEvent(message, { seq: message.lastSeq, type: "error", message: "Your session expired. Please sign in again.", recoverable: false });
          optionsRef.current.onAuthExpired();
        } else if (err instanceof ApiError && err.status === 409) {
          // The thread already has a run in flight (e.g. double submit from another tab): attach to it.
          const runId = (err.detail as { run_id?: string } | undefined)?.run_id;
          if (runId) {
            activeRef.current = null;
            setRunning(false);
            return execute({ ...message, runId }, (signal) => openResumeStream(runId, -1, signal));
          }
          message = applyEvent(message, { seq: message.lastSeq, type: "error", message: "This thread is busy.", recoverable: true });
        } else if (err instanceof ApiError && err.status === 404 && message.runId) {
          message = applyEvent(message, { seq: message.lastSeq, type: "error", message: "This run is no longer available on the server. Retry to run it again.", recoverable: true });
        } else {
          const detail = err instanceof ApiError ? describe(err) : "Could not reach the analysis service.";
          message = applyEvent(message, { seq: message.lastSeq, type: "error", message: detail, recoverable: true });
        }
      } finally {
        if (activeRef.current === active) {
          activeRef.current = null;
          setRunning(false);
        }
      }
      put(message, true);
      return message;
    },
    [consume, put],
  );

  const send = useCallback(
    async (prompt: string, scope: ChatScope) => {
      const asset = scopeAsset(scope);
      const text = prompt.trim();
      if (!text || sendingRef.current || activeRef.current) return;
      sendingRef.current = true;
      try {
        const tid = threadRef.current ?? (await optionsRef.current.ensureThread(text, asset));
        threadRef.current = tid;
        const lastUser = [...messagesRef.current].reverse().find((m) => m.kind === "user");
        const additions: ChatMessage[] = [];
        if (lastUser && lastUser.kind === "user" && lastUser.asset.symbol !== asset.symbol) {
          additions.push({ id: newId(), kind: "divider", createdAt: nowIso(), asset });
        }
        const user: ChatMessage = { id: newId(), kind: "user", createdAt: nowIso(), content: text, asset };
        const assistant = pendingAssistant({ id: newId(), userMessageId: user.id, prompt: text, asset });
        additions.push(user, assistant);
        for (const m of additions) put(m, true);
        optionsRef.current.announce(`Analysis started for ${displaySymbol(asset.symbol)}`);
        await execute(assistant, (signal) => openChatStream(chatBody(tid, assistant.id, text, asset), signal));
      } finally {
        sendingRef.current = false;
      }
    },
    [execute, put],
  );

  const stop = useCallback(() => {
    const active = activeRef.current;
    if (!active) return;
    const current = messagesRef.current.find((m) => m.id === active.assistantId);
    if (current && isAssistant(current)) {
      put(applyEvent(current, { seq: current.lastSeq, type: "cancelled", message: "Stopped" }), true);
    }
    active.controller.abort();
    if (active.runId) void cancelRun(active.runId);
    optionsRef.current.announce("Analysis stopped");
  }, [put]);

  const retry = useCallback(
    async (assistantId: string) => {
      const failed = messagesRef.current.find((m) => m.id === assistantId);
      const tid = threadRef.current;
      if (!failed || !isAssistant(failed) || !tid || activeRef.current) return;
      dispatch({ type: "remove", id: failed.id });
      const assistant = pendingAssistant({
        id: newId(),
        userMessageId: failed.userMessageId,
        prompt: failed.prompt,
        asset: failed.asset,
      });
      // Replace the failed answer so history keeps one answer per question.
      optionsRef.current.discard(tid, failed.id);
      put(assistant, true);
      await execute(assistant, (signal) =>
        openChatStream(
          chatBody(tid, assistant.id, failed.prompt, failed.asset),
          signal,
        ),
      );
    },
    [execute, put],
  );

  /** Re-attach to a run that was in flight when the page was closed or the stream dropped. */
  const resume = useCallback(
    async (assistantId: string) => {
      const message = messagesRef.current.find((m) => m.id === assistantId);
      const tid = threadRef.current;
      if (!message || !isAssistant(message) || activeRef.current || !tid) return;
      let runId = message.runId;
      if (!runId) {
        const active = await fetchActiveRun(tid).catch(() => null);
        if (active?.messageId === message.id && active.runId) runId = active.runId;
      }
      if (!runId) {
        put(applyEvent(message, { seq: message.lastSeq, type: "error", message: "This analysis was interrupted before it started.", recoverable: true }), true);
        return;
      }
      const fresh: AssistantMessage = { ...message, runId, agents: [], lastSeq: -1, status: "streaming", error: undefined };
      put(fresh);
      await execute(fresh, (signal) => openResumeStream(runId as string, -1, signal));
    },
    [execute, put],
  );

  const setFeedback = useCallback(
    (assistantId: string, feedback: FeedbackState | undefined) => {
      const message = messagesRef.current.find((m) => m.id === assistantId);
      if (message && isAssistant(message)) put({ ...message, feedback }, true);
    },
    [put],
  );

  const load = useCallback((loaded: ChatMessage[]) => {
    activeRef.current?.controller.abort();
    activeRef.current = null;
    setRunning(false);
    dispatch({ type: "reset", messages: loaded });
  }, []);

  // Restored thread with a run still marked as streaming: re-attach automatically.
  useEffect(() => {
    if (running || activeRef.current) return;
    const pending = messages.find((m) => isAssistant(m) && m.status === "streaming");
    if (pending) void resume(pending.id);
  }, [messages, running, resume]);

  useEffect(() => () => activeRef.current?.controller.abort(), []);

  return { messages, running, send, stop, retry, resume, load, setFeedback };
}

function describe(err: ApiError): string {
  if (err.status === 503) return "The analysis service is unavailable. Start the backend and retry.";
  if (err.status === 422) return "The request was rejected as invalid.";
  if (err.status === 502) return "A data provider failed. Retry in a moment.";
  return `The analysis service returned an error (${err.status}).`;
}

function announceEvent(event: StreamEvent, announce: (text: string) => void): void {
  if (event.type === "agent_update" && (event.status === "done" || event.status === "error")) {
    announce(`${event.name} ${event.status === "done" ? "finished" : "failed"}${event.message ? `: ${event.message}` : ""}`);
  } else if (event.type === "final") {
    announce("Analysis complete");
  } else if (event.type === "reply") {
    announce("Answer ready");
  } else if (event.type === "error") {
    announce(`Analysis error: ${event.message}`);
  }
}
