import { stripNs } from "@/lib/symbols";
import React from "react";
import type { EvidenceItem } from "@/lib/chat/types";

export function normalizeCitations(text: string): string {
  if (!text) return "";
  return text.replace(/\[(E\d+(?:[\s,]+E?\d+)*)\]/gi, (match, inner) => {
    const parts = inner.match(/E?(\d+)/gi);
    if (!parts) return match;
    return parts.map((p: string) => `[E${p.replace(/^E/i, "")}]`).join(" ");
  });
}

/** Renders text, turning [E12]-style citations into evidence chips with provenance. */
export function EvidenceRef({ id, evidence }: { id: string; evidence: Map<string, EvidenceItem> }) {
  const item = evidence.get(id);
  const label = item ? stripNs(`${item.label}: ${item.display} (source: ${item.source})`) : `Evidence ${id}`;
  const className =
    "mx-0.5 inline-flex -translate-y-px items-center gap-0.5 border border-line-strong bg-subtle px-1 py-0.2 font-mono text-[9px] font-semibold leading-[14px] text-ink hover:border-ink hover:bg-canvas transition-colors cursor-pointer rounded-xs";
  if (item?.url) {
    return (
      <a href={item.url} target="_blank" rel="noopener noreferrer" title={label} aria-label={label} className={className}>
        <span className="text-muted text-[8px]">ref:</span>
        <span>{id}</span>
      </a>
    );
  }
  return (
    <span title={label} aria-label={label} className={className}>
      <span className="text-muted text-[8px]">ref:</span>
      <span>{id}</span>
    </span>
  );
}

export default function EvidenceText({ text, evidence }: { text: string; evidence: Map<string, EvidenceItem> }) {
  if (!text) return null;
  const normalized = normalizeCitations(stripNs(text));
  const parts = normalized.split(/\[(E\d+)\]/g);
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
