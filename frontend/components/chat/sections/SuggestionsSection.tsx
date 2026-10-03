import React from "react";
import { Lightbulb } from "lucide-react";
import EvidenceText, { EvidenceRef } from "@/components/chat/EvidenceText";
import { Badge, SectionCard, Skeleton } from "@/components/ui/primitives";
import type { EvidenceItem, Suggestions } from "@/lib/chat/types";

export default function SuggestionsSection({
  suggestions,
  evidence,
  pending,
  narrativeSource,
}: {
  suggestions?: Suggestions;
  evidence: Map<string, EvidenceItem>;
  pending: boolean;
  narrativeSource?: "llm" | "rules";
}) {
  return (
    <SectionCard
      id="suggestions"
      title="Suggestions"
      icon={<Lightbulb className="h-3.5 w-3.5" aria-hidden="true" />}
      aside={narrativeSource === "rules" && <Badge title="Generated from deterministic rules: no LLM configured">rules</Badge>}
    >
      {suggestions ? (
        <>
          <ol className="grid gap-2 sm:grid-cols-2">
            {suggestions.items.map((s, i) => {
              const conf = s.confidence !== undefined ? Math.round(s.confidence * 100) : null;
              return (
                <li key={i} className="flex flex-col border border-line p-3" data-testid="suggestion-card">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-bold leading-snug text-ink">
                      <span className="num mr-1.5 text-muted">{String(i + 1).padStart(2, "0")}</span>
                      {s.action}
                    </p>
                  </div>
                  <p className="mt-1.5 flex-1 text-xs leading-relaxed text-ink-soft">
                    <EvidenceText text={s.rationale} evidence={evidence} />
                  </p>
                  <div className="mt-2.5 flex flex-wrap items-center gap-2">
                    {s.horizon && <Badge tone="outline">{s.horizon}</Badge>}
                    {conf !== null && (
                      <span className="flex items-center gap-1.5" title={`Model confidence ${conf}%`}>
                        <span className="font-mono text-2xs uppercase text-muted">Conf.</span>
                        <span className="relative h-1.5 w-14 bg-subtle" aria-hidden="true">
                          <span className="absolute inset-y-0 left-0 bg-ink" style={{ width: `${conf}%` }} />
                        </span>
                        <span className="num text-2xs text-ink">{conf}%</span>
                      </span>
                    )}
                    {s.evidenceIds.length > 0 && (
                      <span className="ml-auto flex flex-wrap items-center">
                        {s.evidenceIds.map((id) => (
                          <EvidenceRef key={id} id={id} evidence={evidence} />
                        ))}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
          <p className="mt-3 border-l-2 border-ink pl-2 font-mono text-2xs text-muted" role="note">
            {suggestions.disclaimer}
          </p>
        </>
      ) : (
        pending && (
          <div className="grid gap-2 sm:grid-cols-2" aria-hidden="true">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))}
          </div>
        )
      )}
    </SectionCard>
  );
}
