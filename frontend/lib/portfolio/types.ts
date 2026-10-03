import type { MarketState, SentimentLabel } from "@/lib/chat/types";

export interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  /** Optional average buy price (INR) for unrealized P&L. */
  avgPrice?: number;
  addedAt: string;
}

export interface Portfolio {
  holdings: Holding[];
  updatedAt: string;
}

export interface HoldingQuote {
  symbol: string;
  name: string;
  sector?: string;
  industry?: string;
  city?: string;
  status: "ok" | "unavailable";
  price?: number;
  changePct?: number;
  previousClose?: number;
  currency?: string;
  marketState?: MarketState;
  marketTime?: string;
  error?: string;
}

export interface PortfolioNewsItem {
  id: string;
  title: string;
  publisher: string;
  url: string;
  publishedAt?: string;
  sentiment?: SentimentLabel;
  sentimentSource?: string;
  themes: string[];
  symbols: string[];
}

export interface WeatherDay {
  date: string;
  weatherCode?: number;
  tempMax?: number;
  tempMin?: number;
  precipitationSum?: number;
  windGustMax?: number;
}

export interface WeatherLocation {
  location: string;
  latitude: number;
  longitude: number;
  reason: string;
  symbols: string[];
  days: WeatherDay[];
  extremes: { date: string; metric: string; value: number; unit: string; description: string }[];
}

export interface PortfolioWeather {
  locations: WeatherLocation[];
  unavailable: { location: string; symbols: string[]; error: string }[];
  withoutLocation: string[];
}

export interface PortfolioPerformance {
  dates: string[];
  value: number[];
  portfolio: number[];
  nifty: (number | null)[];
  excluded: string[];
}
