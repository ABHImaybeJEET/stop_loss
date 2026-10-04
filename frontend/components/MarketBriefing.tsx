"use client";

import { useEffect, useMemo, useState } from "react";
import type { CategorizedNews, NewsArticle, NewsCategory } from "@/lib/news";
import { ArrowDownRight, ArrowUpRight, ExternalLink, Newspaper, RefreshCw } from "lucide-react";

const EMPTY: CategorizedNews = { topStories: [], commodities: [], indianStocks: [] };
const FILTERS: { label: string; value: NewsCategory | "ALL" }[] = [
  { label: "All coverage", value: "ALL" }, { label: "Markets", value: "MACRO" },
  { label: "Trade", value: "TARIFF" }, { label: "Policy", value: "BANK_TAX" },
  { label: "Geopolitics", value: "WAR_CRISIS" }, { label: "Weather", value: "WEATHER_EXTREME" },
];
const LABEL: Record<NewsCategory, string> = {
  WEATHER_EXTREME: "WEATHER", TARIFF: "TRADE", WAR_CRISIS: "GEOPOLITICS",
  BANK_TAX: "POLICY", MACRO: "MARKETS",
};

function timeLabel(value: string): string {
  if (!value || Number.isNaN(Date.parse(value))) return "Time unavailable";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}

function StoryMeta({ article }: { article: NewsArticle }) {
  return <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] font-medium text-[#77786f]">
    <span className="text-[#397456]">{LABEL[article.category]}</span><span>/</span>
    <span className="max-w-[13rem] truncate">{article.source}</span><span>/</span>
    <time dateTime={article.publishedAt || undefined}>{timeLabel(article.publishedAt)}</time>
  </div>;
}

function Story({ article, featured = false }: { article: NewsArticle; featured?: boolean }) {
  return <article className={`group overflow-hidden rounded-2xl border border-[#e9e6dd] bg-white transition duration-200 hover:-translate-y-0.5 hover:border-[#c9c5b8] hover:shadow-[0_14px_38px_rgba(43,43,34,0.07)] ${featured ? "lg:grid lg:grid-cols-[1fr_0.82fr]" : ""}`}>
    <div className={featured ? "p-6 sm:p-8 lg:flex lg:flex-col lg:justify-center lg:p-10" : "p-5 sm:p-6"}>
      <StoryMeta article={article} />
      <a href={article.url} target="_blank" rel="noopener noreferrer" className="mt-4 block rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#397456]">
        <h3 className={`font-editorial leading-[1.15] tracking-[-0.035em] text-[#22251f] transition-colors group-hover:text-[#397456] ${featured ? "text-[2rem] sm:text-[2.6rem]" : "text-xl sm:text-[1.4rem]"}`}>{article.title}</h3>
      </a>
      {article.summary && <p className={`mt-3 text-[#6c6d64] ${featured ? "max-w-xl text-[15px] leading-7" : "line-clamp-3 text-sm leading-6"}`}>{article.summary}</p>}
      {article.ticker && <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-md bg-[#f3f2ec] px-2.5 py-1.5 font-mono font-semibold">{article.ticker}.NS</span>
        {article.priceInr && <span className="font-mono text-[#50534b]">₹{article.priceInr}</span>}
        {article.changePercent && <span className={`inline-flex items-center gap-0.5 font-mono font-semibold ${article.isPositive ? "text-[#24714b]" : "text-[#ab4542]"}`}>
          {article.isPositive ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{article.changePercent}
        </span>}
      </div>}
      <a href={article.url} target="_blank" rel="noopener noreferrer" className="mt-5 inline-flex min-h-9 items-center gap-2 text-xs font-semibold text-[#397456] hover:text-[#1f4933]">
        Read the source <ExternalLink size={13} aria-hidden="true" />
      </a>
    </div>
    {featured && article.imageUrl && <div className="relative min-h-56 overflow-hidden bg-[#eeede6] lg:min-h-full">
      <img src={article.imageUrl} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.025]" />
    </div>}
  </article>;
}

function StockWatch({ stocks }: { stocks: NewsArticle[] }) {
  if (!stocks.length) return null;
  return <section aria-labelledby="nse-watchlist" className="mt-12">
    <div className="mb-4 flex items-end justify-between gap-4"><div><p className="feed-kicker">NSE WATCHLIST</p>
      <h3 id="nse-watchlist" className="mt-1 font-editorial text-2xl tracking-tight">Indian equities</h3></div>
      <span className="pb-1 text-xs text-[#77786f]">Prices from Yahoo Finance</span></div>
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {stocks.map((stock) => <a key={stock.id} href={stock.url} target="_blank" rel="noopener noreferrer" className="rounded-xl border border-[#e9e6dd] bg-white p-4 transition hover:border-[#b9c9bb] hover:bg-[#fcfcf9]">
        <div className="flex items-start justify-between gap-2"><div className="min-w-0">
          <div className="truncate font-mono text-sm font-semibold">{stock.ticker}.NS</div>
          <div className="mt-1 truncate text-xs text-[#77786f]">{stock.companyName || stock.ticker}</div>
        </div>{stock.changePercent && <span className={`shrink-0 font-mono text-xs ${stock.isPositive ? "text-[#24714b]" : "text-[#ab4542]"}`}>{stock.changePercent}</span>}</div>
        {stock.priceInr && <div className="mt-4 font-mono text-base font-medium">₹{stock.priceInr}</div>}
      </a>)}
    </div>
  </section>;
}

export default function MarketBriefing() {
  const [feed, setFeed] = useState<CategorizedNews>(EMPTY);
  const [category, setCategory] = useState<NewsCategory | "ALL">("ALL");
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      try {
        const response = await fetch("/api/news", { signal: controller.signal });
        if (!response.ok) throw new Error("feed_unavailable");
        const data = (await response.json()) as Partial<CategorizedNews>;
        setFeed({ topStories: data.topStories ?? [], commodities: data.commodities ?? [], indianStocks: data.indianStocks ?? [] });
        setUnavailable(false);
      } catch {
        if (!controller.signal.aborted) setUnavailable(true);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [refresh]);

  const stories = useMemo(() => {
    const seen = new Set<string>();
    return [...feed.topStories, ...feed.commodities].filter((item) => {
      const key = item.url || item.id;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [feed]);
  const filtered = category === "ALL" ? stories : stories.filter((item) => item.category === category);
  const [feature, ...more] = filtered;

  return <section id="intelligence-feed" className="relative z-10 scroll-mt-8 border-t border-[#e7e4dc] bg-[#f7f6f1] px-5 py-16 sm:px-8 sm:py-24 lg:px-12">
    <div className="mx-auto max-w-7xl">
      <header className="grid gap-8 border-b border-[#dedbd1] pb-8 md:grid-cols-[1fr_auto] md:items-end">
        <div><div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[#dcd9ce] bg-white/70 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-[#56594f]">
          <Newspaper size={13} aria-hidden="true" /> Market briefing <span className="text-[#b8b5aa]">/</span> India
        </div><h2 className="max-w-3xl font-editorial text-[2.85rem] leading-[0.98] tracking-[-0.055em] sm:text-6xl lg:text-[5rem]">
          Markets, <span className="text-[#397456]">in context.</span>
        </h2><p className="mt-5 max-w-xl text-sm leading-6 text-[#696b62] sm:text-base sm:leading-7">
          Headlines, policy shifts and NSE activity, collected from public sources.
        </p></div>
        <div className="flex items-center justify-between gap-4 md:justify-end md:pb-1">
          <p className="text-xs text-[#77786f]">{loading ? "Updating feed" : `${stories.length} stories`}</p>
          <button type="button" onClick={() => setRefresh((value) => value + 1)} disabled={loading} aria-label="Refresh market news" className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[#d8d6ce] bg-white px-4 text-xs font-semibold transition hover:border-[#9ca992] disabled:opacity-50">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </header>

      <div className="flex gap-2 overflow-x-auto py-5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" role="group" aria-label="Filter news by category">
        {FILTERS.map((item) => <button key={item.value} type="button" aria-pressed={category === item.value} onClick={() => setCategory(item.value)} className={`shrink-0 rounded-full px-4 py-2 text-xs font-medium transition-colors ${category === item.value ? "bg-[#263b2e] text-white" : "border border-[#e1ded5] bg-white/70 text-[#62635b] hover:border-[#bcb9ad] hover:text-[#242720]"}`}>
          {item.label}</button>)}
      </div>

      {loading && !stories.length ? <div aria-label="Loading market headlines" className="mt-8 grid gap-4 md:grid-cols-2">
        <div className="h-64 animate-pulse rounded-2xl bg-[#eeede7]" /><div className="h-64 animate-pulse rounded-2xl bg-[#eeede7]" />
      </div> : feature ? <div className="grid gap-4 lg:grid-cols-[1.12fr_0.88fr]">
        <Story article={feature} featured /><div className="grid content-start gap-4">
          {more.slice(0, 3).map((article) => <Story key={article.id} article={article} />)}
          {!more.length && <div className="flex min-h-40 items-center rounded-2xl border border-dashed border-[#d6d3c9] px-6 text-sm leading-6 text-[#77786f]">
            {category === "ALL" ? "More headlines will appear here as sources publish them." : "No stories in this category right now."}
          </div>}
        </div>
      </div> : <div className="rounded-2xl border border-dashed border-[#d6d3c9] bg-white/50 px-6 py-12 text-center">
        <p className="font-editorial text-2xl text-[#35382f]">{unavailable ? "The feed is taking a pause." : "No headlines to show yet."}</p>
        <p className="mt-2 text-sm text-[#77786f]">{unavailable ? "Try again in a moment." : "New stories will appear here when they are available."}</p>
        {unavailable && <button type="button" onClick={() => setRefresh((value) => value + 1)} className="mt-5 rounded-full bg-[#263b2e] px-4 py-2 text-xs font-semibold text-white">Try again</button>}
      </div>}

      <StockWatch stocks={feed.indianStocks} />
      <footer className="mt-12 border-t border-[#dedbd1] pt-4 text-xs text-[#85867c]">
        Public reporting and provider quotes. Headlines link to their original publishers.
      </footer>
    </div>
  </section>;
}
