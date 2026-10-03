import React from "react";
import { ExternalLink, Radio } from "lucide-react";
import EvidenceText from "@/components/chat/EvidenceText";
import { Badge, SectionCard, Skeleton, SkeletonLines } from "@/components/ui/primitives";
import { relativeTime } from "@/lib/format";
import type { EvidenceItem, Sources } from "@/lib/chat/types";

const SENTIMENT_TONE = { positive: "gain", negative: "loss", neutral: "neutral" } as const;

export default function SourcesSection({
  sources,
  evidence,
  pending,
  failed,
}: {
  sources?: Sources;
  evidence: Map<string, EvidenceItem>;
  pending: boolean;
  failed: boolean;
}) {
  const modelScored = sources?.items.some((i) => i.sentimentSource === "llm");
  return (
    <SectionCard
      id="sources"
      title="Real-time Sources"
      icon={<Radio className="h-3.5 w-3.5" aria-hidden="true" />}
      aside={sources && <span className="num text-2xs text-muted">{sources.items.length} items</span>}
    >
      <div className="text-sm leading-relaxed text-ink-soft">
        {sources?.summary ? <EvidenceText text={sources.summary} evidence={evidence} /> : pending ? <SkeletonLines lines={2} /> : null}
      </div>
      {failed && (
        <p className="mt-2 font-mono text-2xs text-loss">News feeds were unavailable for this run; summary uses the remaining data.</p>
      )}
      {sources ? (
        sources.items.length > 0 ? (
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {sources.items.map((item) => (
              <li key={item.url} className="flex items-start gap-3 py-2">
                <div className="min-w-0 flex-1">
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group inline-flex items-start gap-1 text-xs font-semibold text-ink hover:underline"
                  >
                    <span className="line-clamp-2">{item.title}</span>
                    <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-muted group-hover:text-ink" aria-hidden="true" />
                    <span className="sr-only">(opens in a new tab)</span>
                  </a>
                  <p className="mt-0.5 font-mono text-2xs text-muted">
                    {item.publisher}
                    {item.publishedAt && <> · {relativeTime(item.publishedAt)}</>}
                    {item.themes.length > 0 && <> · {item.themes.join(", ")}</>}
                  </p>
                </div>
                {item.sentiment && (
                  <Badge
                    tone={SENTIMENT_TONE[item.sentiment]}
                    title={item.sentimentSource === "llm" ? "Model-classified sentiment" : "Alpha Vantage sentiment score"}
                  >
                    {item.sentiment}
                  </Badge>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 font-mono text-2xs text-muted">No recent headlines found for this asset in the last 7 days.</p>
        )
      ) : (
        pending && (
          <div className="mt-3 space-y-2" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        )
      )}
      {modelScored && (
        <p className="mt-2 font-mono text-2xs text-muted">Sentiment badges are model-classified from headlines where provider scores were unavailable.</p>
      )}
    </SectionCard>
  );
}
