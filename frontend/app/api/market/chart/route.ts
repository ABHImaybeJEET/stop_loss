import { HttpError, backendFetch, handle, relayJson, requireUser } from "@/lib/server/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** UI range → Yahoo range/interval (sensible default intervals per range). */
const RANGES: Record<string, [string, string]> = {
  "1D": ["1d", "5m"],
  "5D": ["5d", "15m"],
  "1M": ["1mo", "60m"],
  "6M": ["6mo", "1d"],
  "1Y": ["1y", "1d"],
  "5Y": ["5y", "1wk"],
};

export async function GET(request: Request) {
  return handle(async () => {
    await requireUser(request);
    const params = new URL(request.url).searchParams;
    const symbol = params.get("symbol") ?? "";
    const mapped = RANGES[params.get("range") ?? "1D"];
    if (!mapped || !/^[A-Za-z0-9.\-^=]{1,32}$/.test(symbol)) throw new HttpError(422, "invalid_params");
    const [range, interval] = mapped;
    const query = new URLSearchParams({ symbol, range, interval: params.get("interval") ?? interval });
    return relayJson(await backendFetch(`/market/chart?${query}`));
  });
}
