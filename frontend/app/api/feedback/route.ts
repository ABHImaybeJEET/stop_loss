import { HttpError, backendFetch, handle, relayJson, requireUser } from "@/lib/server/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  return handle(async () => {
    const userId = await requireUser(request);
    return relayJson(
      await backendFetch("/feedback", {
        method: "POST",
        userId,
        headers: { "Content-Type": "application/json" },
        body: await request.text(),
      }),
    );
  });
}

/** Undo: DELETE /api/feedback?message_id=... */
export async function DELETE(request: Request) {
  return handle(async () => {
    const userId = await requireUser(request);
    const messageId = new URL(request.url).searchParams.get("message_id") ?? "";
    if (!/^[A-Za-z0-9_-]{8,64}$/.test(messageId)) throw new HttpError(422, "invalid_message_id");
    return relayJson(await backendFetch(`/feedback/${messageId}`, { method: "DELETE", userId }));
  });
}
