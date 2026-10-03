"use client";

import React, { useState } from "react";
import { ExternalLink, Newspaper } from "lucide-react";
import { Badge, Skeleton, cn } from "@/components/ui/primitives";
import { relativeTime } from "@/lib/format";
import type { PortfolioNewsItem } from "@/lib/portfolio/types";

const TONE = { positive: "gain", negative: "loss", neutral: "neutral" } as const;

export default function PortfolioNews({ items, error, symbols }: { items?: PortfolioNewsItem[]; error?: unknown; symbols: string[] }) {
  const [filter, setFilter] = useState<string | null>(null);
  const shown = (items ?? []).filter((i) => !filter || i.symbols.includes(filter));
  return (
    <section className="border border-line bg-white" aria-labelledby="pf-news-title" data-testid="portfolio-news">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <h3 id="pf-news-title" className="flex items-center gap-2 font-mono text-2xs font-bold uppercase tracking-widest text-ink">
          <Newspaper className="h-3.5 w-3.5" aria-hidden="true" /> Live news on your holdings
        </h3>
        <div role="group" aria-label="Filter by holding" className="flex flex-wrap gap-1">
          {[null, ...symbols].map((s) => (
            <button
              key={s ?? "all"}
              type="button"
              aria-pressed={filter === s}
              onClick={() => setFilter(s)}
              className={cn("border px-1.5 py-0.5 font-mono text-2xs", filter === s ? "border-ink bg-ink text-white" : "border-line-strong text-muted hover:text-ink")}
            >
              {s ? s.replace(/\.NS$/, "") : "All"}
            </button>
          ))}
        </div>
      </header>
      <div className="max-h-[28rem] overflow-y-auto">
        {error && !items ? (
          <p className="p-6 text-center font-mono text-2xs text-loss">News feeds unavailable right now.</p>
        ) : !items ? (
          <div className="space-y-2 p-3" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : shown.length === 0 ? (
          <p className="p-6 text-center font-mono text-2xs text-muted">No recent headlines.</p>
        ) : (
          <ul className="divide-y divide-line">
            {shown.map((item) => (
              <li key={item.id} className="flex items-start gap-3 px-3 py-2">
                <div className="min-w-0 flex-1">
                  <a href={item.url} target="_blank" rel="noopener noreferrer" className="group inline-flex items-start gap-1 text-xs font-semibold text-ink hover:underline">
                    <span className="line-clamp-2">{item.title}</span>
                    <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-muted" aria-hidden="true" />
                    <span className="sr-only">(opens in a new tab)</span>
                  </a>
                  <p className="mt-0.5 font-mono text-2xs text-muted">
                    {item.publisher}
                    {item.publishedAt && <> · {relativeTime(item.publishedAt)}</>}
                    {" · "}
                    {item.symbols.map((s) => s.replace(/\.NS$/, "")).join(", ")}
                  </p>
                </div>
                {item.sentiment && (
                  <Badge tone={TONE[item.sentiment]} title={item.sentimentSource === "llm" ? "Model-classified sentiment" : "Provider sentiment"}>
                    {item.sentiment}
                  </Badge>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="border-t border-line px-3 py-1.5 font-mono text-2xs text-muted-soft">
        Google News RSS, GDELT and yfinance headlines · sentiment classified by the News agent
      </p>
    </section>
  );
}
