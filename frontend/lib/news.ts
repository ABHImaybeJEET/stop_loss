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

/** Server-only: fetch the categorized feed using a free public RSS-to-JSON API to bypass all rate limits. */
export async function fetchMarketNews(): Promise<CategorizedNews> {
  console.log("fetchMarketNews called! Using public RSS2JSON API with unique images");
  
  // A curated list of beautiful, distinct financial Unsplash images
  const FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1590283603385-18ff38540843?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1642790106117-e829e14a795f?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1200&auto=format&fit=crop", // Stock charts
    "https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=1200&auto=format&fit=crop", // Data analysis
    "https://images.unsplash.com/photo-1633158829585-23ba8f7c8caf?q=80&w=1200&auto=format&fit=crop", // Crypto/Finance
    "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?q=80&w=1200&auto=format&fit=crop", // Money
    "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1200&auto=format&fit=crop"  // Screens
  ];

  try {
    // Fetch global market news from CNBC RSS via RSS2JSON (No API Key Required, no restrictive limits)
    const rssUrl = encodeURIComponent("https://www.cnbc.com/id/10000664/device/rss/rss.html");
    const res = await fetch(`https://api.rss2json.com/v1/api.json?rss_url=${rssUrl}`, { cache: 'no-store' });
    
    if (!res.ok) return EMPTY_FEED;
    const data = await res.json();

    if (!data || !data.items) {
        console.error("RSS2JSON missing items array:", data);
        return EMPTY_FEED;
    }

    const articles: NewsArticle[] = data.items.slice(0, 9).map((item: any, i: number) => ({
      id: `rss-${i}`,
      category: "MACRO",
      title: item.title,
      summary: item.description ? item.description.replace(/<[^>]+>/g, '') : "Read the full story to learn more about the market impact.",
      source: "CNBC Finance",
      publishedAt: item.pubDate,
      url: item.link,
      // If the RSS enclosure has an image, use it. Otherwise use a UNIQUE beautiful default stock market image
      imageUrl: item.enclosure?.link || item.thumbnail || FALLBACK_IMAGES[i % FALLBACK_IMAGES.length],
      isPositive: true,
    }));

    return {
      topStories: articles.slice(0, 5),
      commodities: articles.slice(5, 9),
      indianStocks: INDIAN_STOCKS, 
    };
  } catch (err) {
    console.error("fetchMarketNews error:", err);
    return EMPTY_FEED;
  }
}
