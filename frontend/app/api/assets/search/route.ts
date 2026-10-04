import { HttpError, backendFetch, handle, relayJson } from "@/lib/server/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return handle(async () => {
    const q = (new URL(request.url).searchParams.get("q") ?? "").trim();
    if (!q || q.length > 64) throw new HttpError(422, "invalid_query");
    return relayJson(await backendFetch(`/assets/search?q=${encodeURIComponent(q)}`));
  });
}
