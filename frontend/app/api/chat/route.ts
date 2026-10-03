import { backendFetch, handle, relayJson, relayStream, requireUser } from "@/lib/server/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Starts an analysis run and relays its SSE stream. The run keeps executing on the
 *  backend if this connection drops; the client resumes via /api/chat/runs/:id/events. */
export async function POST(request: Request) {
  return handle(async () => {
    const userId = await requireUser(request);
    const upstream = await backendFetch("/chat", {
      method: "POST",
      userId,
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: await request.text(),
      signal: request.signal,
    });
    if (!upstream.ok) return relayJson(upstream);
    return relayStream(upstream);
  });
}
