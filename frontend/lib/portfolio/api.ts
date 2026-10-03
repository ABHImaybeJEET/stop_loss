import { z } from "zod";
import { ApiError, apiFetch } from "@/lib/chat/api";
import type {
  Holding,
  HoldingQuote,
  PortfolioNewsItem,
  PortfolioPerformance,
  PortfolioWeather,
} from "@/lib/portfolio/types";

const optStr = z.string().nullish().transform((v) => v ?? undefined);
const optNum = z.number().nullish().transform((v) => v ?? undefined);

async function getJson<T>(path: string, schema: z.ZodType<T, z.ZodTypeDef, unknown>): Promise<T> {
  const response = await apiFetch(path);
  if (!response.ok) {
    let detail: unknown = `http_${response.status}`;
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail ?? detail;
    } catch {
      // keep generic detail
    }
    throw new ApiError(response.status, detail);
  }
  return schema.parse(await response.json());
}

const quotesSchema = z.object({
  quotes: z.array(
    z
      .object({
        symbol: z.string(),
        name: z.string(),
        sector: optStr,
        industry: optStr,
        city: optStr,
        status: z.enum(["ok", "unavailable"]),
        price: optNum,
        change_pct: optNum,
        previous_close: optNum,
        currency: optStr,
        market_state: z.enum(["open", "pre", "post", "closed"]).nullish().transform((v) => v ?? undefined),
        market_time: optStr,
        error: optStr,
      })
      .transform(
        (q): HoldingQuote => ({
          symbol: q.symbol,
          name: q.name,
          sector: q.sector,
          industry: q.industry,
          city: q.city,
          status: q.status,
          price: q.price,
          changePct: q.change_pct,
          previousClose: q.previous_close,
          currency: q.currency,
          marketState: q.market_state,
          marketTime: q.market_time,
          error: q.error,
        }),
      ),
  ),
});

export async function fetchHoldingQuotes(symbols: string[]): Promise<HoldingQuote[]> {
  const data = await getJson(`/api/portfolio/quotes?symbols=${encodeURIComponent(symbols.join(","))}`, quotesSchema);
  return data.quotes;
}

const newsSchema = z.object({
  items: z.array(
    z
      .object({
        id: z.string(),
        title: z.string(),
        publisher: z.string(),
        url: z.string(),
        published_at: optStr,
        sentiment: z.enum(["positive", "neutral", "negative"]).nullish().transform((v) => v ?? undefined),
        sentiment_source: optStr,
        themes: z.array(z.string()).catch([]),
        symbols: z.array(z.string()).catch([]),
      })
      .transform(
        (n): PortfolioNewsItem => ({
          id: n.id,
          title: n.title,
          publisher: n.publisher,
          url: n.url,
          publishedAt: n.published_at,
          sentiment: n.sentiment,
          sentimentSource: n.sentiment_source,
          themes: n.themes,
          symbols: n.symbols,
        }),
      ),
  ),
});

export async function fetchPortfolioNews(symbols: string[]): Promise<PortfolioNewsItem[]> {
  const data = await getJson(`/api/portfolio/news?symbols=${encodeURIComponent(symbols.join(","))}`, newsSchema);
  return data.items;
}

const daySchema = z
  .object({
    date: z.string(),
    weather_code: optNum,
    temp_max: optNum,
    temp_min: optNum,
    precipitation_sum: optNum,
    wind_gust_max: optNum,
  })
  .transform((d) => ({
    date: d.date,
    weatherCode: d.weather_code,
    tempMax: d.temp_max,
    tempMin: d.temp_min,
    precipitationSum: d.precipitation_sum,
    windGustMax: d.wind_gust_max,
  }));

const weatherSchema = z
  .object({
    locations: z.array(
      z.object({
        location: z.string(),
        latitude: z.number(),
        longitude: z.number(),
        reason: z.string(),
        symbols: z.array(z.string()),
        days: z.array(daySchema),
        extremes: z.array(
          z.object({ date: z.string(), metric: z.string(), value: z.number(), unit: z.string(), description: z.string() }),
        ),
      }),
    ),
    unavailable: z.array(z.object({ location: z.string(), symbols: z.array(z.string()), error: z.string() })).catch([]),
    without_location: z.array(z.string()).catch([]),
  })
  .transform(
    (w): PortfolioWeather => ({ locations: w.locations, unavailable: w.unavailable, withoutLocation: w.without_location }),
  );

export function fetchPortfolioWeather(symbols: string[]): Promise<PortfolioWeather> {
  return getJson(`/api/portfolio/weather?symbols=${encodeURIComponent(symbols.join(","))}`, weatherSchema);
}

const performanceSchema = z.object({
  dates: z.array(z.string()),
  value: z.array(z.number()),
  portfolio: z.array(z.number()),
  nifty: z.array(z.number().nullable()),
  excluded: z.array(z.string()),
});

export function fetchPortfolioPerformance(holdings: Holding[], range: string): Promise<PortfolioPerformance> {
  const encoded = holdings.map((h) => `${h.symbol}:${h.quantity}`).join(",");
  return getJson(
    `/api/portfolio/performance?holdings=${encodeURIComponent(encoded)}&range=${encodeURIComponent(range)}`,
    performanceSchema,
  );
}
