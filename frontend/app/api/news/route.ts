import { NextResponse } from "next/server";
import { fetchMarketNews } from "@/lib/news";

export async function GET() {
  const news = await fetchMarketNews();
  return NextResponse.json(news);
}
