import { backendFetch, handle, relayJson, requireUser } from "@/lib/server/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: { threadId: string } }) {
  return handle(async () => {
    const userId = await requireUser(request);
    return relayJson(
      await backendFetch(`/chat/threads/${encodeURIComponent(params.threadId)}/active-run`, { userId }),
    );
  });
}
