import { displaySymbol } from "@/lib/symbols";
import React from "react";
import { Activity } from "lucide-react";
import EvidenceText from "@/components/chat/EvidenceText";
import { Badge, SectionCard, SkeletonLines, Skeleton } from "@/components/ui/primitives";
import { formatCompact, formatNumber, formatPct, formatPrice, relativeTime, signClass } from "@/lib/format";
import type { AssetRef, EvidenceItem, Fact, Snapshot } from "@/lib/chat/types";

function factValue(fact: Fact, currency?: string): string {
  if (typeof fact.value === "string") return fact.value;
  switch (fact.kind) {
    case "currency":
      return formatPrice(fact.value, fact.unit ?? currency);
    case "percent":
      return formatPct(fact.value, 2, false);
    case "compact":
      return formatCompact(fact.value, fact.unit);
    default:
      return formatNumber(fact.value);
  }
}

const STATE_TONE = { open: "gain", pre: "outline", post: "outline", closed: "neutral" } as const;

export default function SnapshotSection({
  asset,
  snapshot,
  evidence,
  pending,
}: {
  asset: AssetRef;
  snapshot?: Snapshot;
  evidence: Map<string, EvidenceItem>;
  pending: boolean;
}) {
  return (
    <SectionCard
      id={`snapshot-${asset.symbol}`}
      title="Asset Snapshot"
      icon={<Activity className="h-3.5 w-3.5" aria-hidden="true" />}
      aside={snapshot?.marketState && <Badge tone={STATE_TONE[snapshot.marketState]}>Market {snapshot.marketState}</Badge>}
    >
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div className="min-w-0">
          <p className="num text-sm font-bold text-ink">{displaySymbol(asset.symbol)}</p>
          <p className="truncate text-xs text-muted">
            {asset.name}
            {asset.exchange ? ` · ${asset.exchange}` : ""}
          </p>
        </div>
        {snapshot ? (
          <div className="text-right">
            <p className="num text-2xl font-bold leading-none text-ink">{formatPrice(snapshot.price, snapshot.currency)}</p>
            <p className={`num mt-1 text-xs font-semibold ${signClass(snapshot.changePct)}`}>
              {formatPct(snapshot.changePct)} <span className="font-normal text-muted">today</span>
              {snapshot.asOf && <span className="ml-2 font-normal text-muted">· {relativeTime(snapshot.asOf)}</span>}
            </p>
          </div>
        ) : (
          <div className="space-y-1.5 text-right">
            <Skeleton className="ml-auto h-6 w-32" />
            <Skeleton className="ml-auto h-3 w-20" />
          </div>
        )}
      </div>

      <div className="mt-3 text-sm leading-relaxed text-ink-soft">
        {snapshot?.summary ? <EvidenceText text={snapshot.summary} evidence={evidence} /> : pending ? <SkeletonLines lines={2} /> : null}
      </div>

      {snapshot && snapshot.facts.length > 0 && (
        <dl className="mt-3 grid grid-cols-2 gap-px border border-line bg-line sm:grid-cols-4">
          {snapshot.facts.map((fact) => (
            <div key={fact.label} className="bg-white px-2.5 py-2">
              <dt className="font-mono text-2xs uppercase tracking-wider text-muted">{fact.label}</dt>
              <dd className={`mt-0.5 truncate text-xs font-semibold text-ink ${fact.kind === "text" ? "" : "num"}`} title={factValue(fact, snapshot.currency)}>
                {factValue(fact, snapshot.currency)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </SectionCard>
  );
}
