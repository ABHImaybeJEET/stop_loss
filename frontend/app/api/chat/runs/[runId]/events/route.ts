import { backendFetch, handle, relayJson, relayStream, requireUser } from "@/lib/server/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: { runId: string } }) {
  return handle(async () => {
    const userId = await requireUser(request);
    const after = new URL(request.url).searchParams.get("after") ?? "-1";
    const upstream = await backendFetch(
      `/chat/runs/${encodeURIComponent(params.runId)}/events?after=${encodeURIComponent(after)}`,
      { userId, headers: { Accept: "text/event-stream" }, signal: request.signal },
    );
    if (!upstream.ok) return relayJson(upstream);
    return relayStream(upstream);
  });
}
