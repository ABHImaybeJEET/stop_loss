import { NextResponse } from "next/server";
import { fetchMarketNews } from "@/lib/news";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  console.log("Next.js API route /api/news HIT!");
  const news = await fetchMarketNews();
  return NextResponse.json(news);
}
