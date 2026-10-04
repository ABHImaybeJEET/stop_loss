/**
 * Landing-page market intelligence feed. Data comes only from the StopLoss backend
 * (`GET /news/feed`); when it is unreachable the feed is empty — nothing is fabricated.
 */

export type NewsCategory = "WEATHER_EXTREME" | "TARIFF" | "WAR_CRISIS" | "BANK_TAX" | "MACRO";

export interface NewsArticle {
  id: string;
  category: NewsCategory;
  title: string;
  summary: string;
  source: string;
  publishedAt: string;
  url: string;
  imageUrl?: string;
  ticker?: string;
  companyName?: string;
  priceInr?: string;
  changePercent?: string;
  isPositive?: boolean;
  sector?: string;
}

export interface CategorizedNews {
  topStories: NewsArticle[];
  commodities: NewsArticle[];
  indianStocks: NewsArticle[];
}

export const TOP_STORIES: NewsArticle[] = [];
export const COMMODITIES_NEWS: NewsArticle[] = [];
export const INDIAN_STOCKS: NewsArticle[] = [];

const EMPTY_FEED: CategorizedNews = { topStories: [], commodities: [], indianStocks: [] };

/** Server-only: fetch the categorized feed from the backend. */
export async function fetchMarketNews(): Promise<CategorizedNews> {
  const base = process.env.BACKEND_URL || "http://127.0.0.1:8000";
  console.log("fetchMarketNews called! Using backend:", base);
  const headers: Record<string, string> = {};
  if (process.env.BACKEND_INTERNAL_TOKEN) headers["X-Internal-Token"] = process.env.BACKEND_INTERNAL_TOKEN;
  try {
    const res = await fetch(`${base}/news/feed`, { headers, cache: 'no-store' });
    console.log("Backend /news/feed status:", res.status, res.statusText);
    if (!res.ok) {
       const errText = await res.text().catch(() => "");
       console.error("Backend error response:", errText);
       return EMPTY_FEED;
    }
    const json = (await res.json()) as Partial<CategorizedNews>;
    console.log("Backend returned topStories count:", json.topStories?.length);
    console.log("Backend returned commodities count:", json.commodities?.length);
    console.log("Backend returned indianStocks count:", json.indianStocks?.length);
    return {
      topStories: json.topStories ?? [],
      commodities: json.commodities ?? [],
      indianStocks: json.indianStocks ?? [],
    };
  } catch (err) {
    console.error("fetchMarketNews error:", err);
    return EMPTY_FEED;
  }
}
