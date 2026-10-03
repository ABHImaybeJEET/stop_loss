import React from "react";
import type { EvidenceItem } from "@/lib/chat/types";

/** Renders text, turning [E12]-style citations into evidence chips with provenance. */
export function EvidenceRef({ id, evidence }: { id: string; evidence: Map<string, EvidenceItem> }) {
  const item = evidence.get(id);
  const label = item ? `${item.label}: ${item.display} (source: ${item.source})` : `Evidence ${id}`;
  const className =
    "mx-0.5 inline-flex -translate-y-px items-center border border-line-strong bg-subtle px-1 font-mono text-[9px] font-semibold leading-[14px] text-muted hover:border-ink hover:text-ink";
  if (item?.url) {
    return (
      <a href={item.url} target="_blank" rel="noopener noreferrer" title={label} aria-label={label} className={className}>
        {id}
      </a>
    );
  }
  return (
    <span title={label} aria-label={label} className={className}>
      {id}
    </span>
  );
}

export default function EvidenceText({ text, evidence }: { text: string; evidence: Map<string, EvidenceItem> }) {
  const parts = text.split(/\[(E\d+)\]/g);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? <EvidenceRef key={i} id={part} evidence={evidence} /> : <React.Fragment key={i}>{part}</React.Fragment>,
      )}
    </>
  );
}

export function evidenceMap(items: EvidenceItem[] | undefined): Map<string, EvidenceItem> {
  return new Map((items ?? []).map((e) => [e.id, e]));
}
