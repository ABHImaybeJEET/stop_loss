import { proxyGet } from "@/lib/server/proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export const GET = proxyGet("/portfolio/news", ["symbols"]);
