import { auth } from "@/lib/firebase";
import { toAssetMatches, toChartSeries, toQuote } from "@/adapters/backendToUi";
import type { AssetMatch, AssetRef, ChartSeries, FeedbackState, Quote } from "@/lib/chat/types";

export class AuthExpiredError extends Error {
  constructor() {
    super("auth_expired");
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `http_${status}`);
  }
}

async function authHeader(forceRefresh: boolean): Promise<Record<string, string>> {
  const user = auth.currentUser;
  if (!user) throw new AuthExpiredError();
  try {
    return { Authorization: `Bearer ${await user.getIdToken(forceRefresh)}` };
  } catch {
    throw new AuthExpiredError();
  }
}

/** fetch() with the Firebase ID token; refreshes once on 401, then reports expiry. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  for (const force of [false, true]) {
    const headers = new Headers(init.headers);
    for (const [k, v] of Object.entries(await authHeader(force))) headers.set(k, v);
    const response = await fetch(path, { ...init, headers });
    if (response.status !== 401) return response;
  }
  throw new AuthExpiredError();
}

async function readDetail(response: Response): Promise<unknown> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return body.detail ?? body;
  } catch {
    return `http_${response.status}`;
  }
}

async function apiJson<T>(path: string, parse: (raw: unknown) => T, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) throw new ApiError(response.status, await readDetail(response));
  return parse(await response.json());
}

export interface ChatBody {
  thread_id: string;
  message_id: string;
  prompt: string;
  mode?: "ticker" | "portfolio";
  asset?: { symbol: string; name: string; exchange?: string | null };
  holdings?: { symbol: string; quantity: number; avg_price?: number | null; name?: string }[];
}

export async function openChatStream(body: ChatBody, signal: AbortSignal): Promise<Response> {
  const response = await apiFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new ApiError(response.status, await readDetail(response));
  return response;
}

export async function openResumeStream(runId: string, after: number, signal: AbortSignal): Promise<Response> {
  const response = await apiFetch(`/api/chat/runs/${encodeURIComponent(runId)}/events?after=${after}`, {
    headers: { Accept: "text/event-stream" },
    signal,
  });
  if (!response.ok) throw new ApiError(response.status, await readDetail(response));
  return response;
}

export async function cancelRun(runId: string): Promise<void> {
  await apiFetch(`/api/chat/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" }).catch(() => undefined);
}

export async function fetchActiveRun(threadId: string): Promise<{ runId: string | null; messageId: string | null }> {
  return apiJson(`/api/chat/threads/${encodeURIComponent(threadId)}/active-run`, (raw) => {
    const r = raw as { run_id?: string | null; message_id?: string | null };
    return { runId: r.run_id ?? null, messageId: r.message_id ?? null };
  });
}

export async function searchAssets(q: string): Promise<AssetMatch[]> {
  const response = await fetch(`/api/assets/search?q=${encodeURIComponent(q)}`);
  if (!response.ok) throw new ApiError(response.status, await readDetail(response));
  return toAssetMatches(await response.json());
}

export function fetchChart(symbol: string, range: string): Promise<ChartSeries> {
  const query = new URLSearchParams({ symbol, range });
  return apiJson(`/api/market/chart?${query}`, toChartSeries);
}

export function fetchQuote(symbol: string): Promise<Quote> {
  return apiJson(`/api/market/quote?symbol=${encodeURIComponent(symbol)}`, toQuote);
}

export async function submitFeedback(
  threadId: string,
  messageId: string,
  feedback: Omit<FeedbackState, "savedAt">,
): Promise<FeedbackState> {
  return apiJson(
    "/api/feedback",
    (raw) => {
      const r = raw as { rating: "up" | "down"; tags: string[]; comment?: string | null; updated_at: string };
      return { rating: r.rating, tags: r.tags, comment: r.comment ?? undefined, savedAt: r.updated_at };
    },
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: threadId,
        message_id: messageId,
        rating: feedback.rating,
        tags: feedback.tags,
        comment: feedback.comment || null,
      }),
    },
  );
}

export async function deleteFeedback(messageId: string): Promise<void> {
  const response = await apiFetch(`/api/feedback?message_id=${encodeURIComponent(messageId)}`, { method: "DELETE" });
  if (!response.ok) throw new ApiError(response.status, await readDetail(response));
}

export function toChatAsset(asset: AssetRef): ChatBody["asset"] {
  return { symbol: asset.symbol, name: asset.name, exchange: asset.exchange ?? null };
}
