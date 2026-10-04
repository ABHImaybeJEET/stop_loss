"use client";

import { displaySymbol } from "@/lib/symbols";
import React, { useEffect, useId, useRef, useState } from "react";
import useSWR from "swr";
import { Search, X } from "lucide-react";
import { searchAssets } from "@/lib/chat/api";
import type { AssetMatch, AssetRef } from "@/lib/chat/types";
import { cn } from "@/components/ui/primitives";

interface Props {
  value: AssetRef | null;
  onChange: (asset: AssetRef | null) => void;
  disabled?: boolean;
  /** Called after a selection so the parent can move focus to the prompt. */
  onSelected?: () => void;
  /** Where the results list opens: "up" above a bottom composer, "down" in dialogs. */
  placement?: "up" | "down";
}

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

/** Searchable ARIA combobox (WAI-ARIA 1.2 pattern) backed by the live asset search API. */
export default function AssetCombobox({ value, onChange, disabled, onSelected, placement = "up" }: Props) {
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const term = useDebounced(query.trim(), 250);
  const { data, error, isLoading } = useSWR(term.length >= 1 ? ["asset-search", term] : null, () => searchAssets(term), {
    keepPreviousData: true,
    revalidateOnFocus: false,
    dedupingInterval: 500,
  });
  const results: AssetMatch[] = term ? (data ?? []) : [];

  useEffect(() => setActive(0), [term]);

  const select = (match: AssetMatch) => {
    onChange({ symbol: match.symbol, name: match.name, exchange: match.exchange });
    setQuery("");
    setOpen(false);
    onSelected?.();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, Math.max(results.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      if (open && results[active]) {
        e.preventDefault();
        select(results[active]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  if (value) {
    return (
      <div className="flex min-w-0 items-center gap-1.5 border border-ink bg-ink py-1 pl-2 pr-1 text-white" data-testid="asset-chip">
        <span className="num text-xs font-bold">{displaySymbol(value.symbol)}</span>
        <span className="hidden max-w-[10rem] truncate text-2xs text-white/70 sm:inline">{value.name}</span>
        {value.exchange && <span className="hidden font-mono text-2xs text-white/50 md:inline">{value.exchange}</span>}
        <button
          type="button"
          onClick={() => {
            onChange(null);
            requestAnimationFrame(() => inputRef.current?.focus());
          }}
          disabled={disabled}
          aria-label={`Remove ${displaySymbol(value.symbol)}`}
          className="ml-0.5 flex h-5 w-5 items-center justify-center text-white/70 hover:bg-white/10 hover:text-white disabled:opacity-40"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
    );
  }

  const expanded = open && term.length > 0;
  return (
    <div className="relative min-w-0 flex-1 sm:w-56 sm:flex-none">
      <div className="flex h-8 items-center gap-1.5 border border-line-strong bg-white px-2 focus-within:border-ink">
        <Search className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
        <input
          ref={inputRef}
          role="combobox"
          aria-label="Search for an NSE stock by ticker or name"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={expanded && results[active] ? `${listId}-${active}` : undefined}
          value={query}
          disabled={disabled}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          placeholder="NSE stock: ticker or name"
          className="num h-full w-full min-w-0 bg-transparent text-xs text-ink placeholder:font-sans placeholder:text-muted-soft focus:outline-none"
          data-testid="asset-search"
        />
      </div>
      {expanded && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Matching assets"
          className={cn(
            "absolute left-0 z-40 max-h-72 w-[min(22rem,calc(100vw-2rem))] overflow-y-auto border border-ink bg-white shadow-lg",
            placement === "up" ? "bottom-full mb-1" : "top-full mt-1",
          )}
        >
          {isLoading && results.length === 0 && <li className="px-3 py-2 font-mono text-2xs text-muted">Searching…</li>}
          {error && <li className="px-3 py-2 font-mono text-2xs text-loss">Asset search unavailable. Check the backend.</li>}
          {!isLoading && !error && results.length === 0 && (
            <li className="px-3 py-2 font-mono text-2xs text-muted">No matching assets</li>
          )}
          {results.map((match, i) => (
            <li
              key={match.symbol}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => select(match)}
              onMouseEnter={() => setActive(i)}
              className={cn(
                "flex cursor-pointer items-center justify-between gap-3 border-b border-line px-3 py-2 last:border-b-0",
                i === active ? "bg-ink text-white" : "text-ink",
              )}
            >
              <span className="min-w-0">
                <span className="num block text-xs font-bold">{displaySymbol(match.symbol)}</span>
                <span className={cn("block truncate text-2xs", i === active ? "text-white/70" : "text-muted")}>{match.name}</span>
              </span>
              <span className={cn("shrink-0 text-right font-mono text-2xs", i === active ? "text-white/60" : "text-muted")}>
                {match.exchange}
                {match.quoteType && <span className="block">{match.quoteType.toLowerCase()}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
