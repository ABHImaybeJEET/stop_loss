import { backendFetch, handle, relayJson, requireUser } from "@/lib/server/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request, { params }: { params: { runId: string } }) {
  return handle(async () => {
    const userId = await requireUser(request);
    return relayJson(
      await backendFetch(`/chat/runs/${encodeURIComponent(params.runId)}/cancel`, { method: "POST", userId }),
    );
  });
}
