import { HttpError, backendFetch, handle, relayJson, requireUser } from "@/lib/server/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return handle(async () => {
    await requireUser(request);
    const symbol = new URL(request.url).searchParams.get("symbol") ?? "";
    if (!/^[A-Za-z0-9.\-^=]{1,32}$/.test(symbol)) throw new HttpError(422, "invalid_symbol");
    return relayJson(await backendFetch(`/market/quote?symbol=${encodeURIComponent(symbol)}`));
  });
}
