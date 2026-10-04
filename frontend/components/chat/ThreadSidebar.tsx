"use client";

import { displaySymbol, stripNs } from "@/lib/symbols";
import React, { useEffect, useRef, useState } from "react";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { cn } from "@/components/ui/primitives";
import { relativeTime } from "@/lib/format";
import type { ThreadMeta } from "@/lib/chat/types";

interface Props {
  threads: ThreadMeta[];
  loading: boolean;
  activeId: string | null;
  open: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  syncError: string | null;
  footer: React.ReactNode;
}

function ThreadRow({
  thread,
  active,
  onSelect,
  onRename,
  onDelete,
}: {
  thread: ThreadMeta;
  active: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const [mode, setMode] = useState<"view" | "rename" | "confirm">("view");
  const [title, setTitle] = useState(thread.title);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (mode === "rename") inputRef.current?.select();
  }, [mode]);

  if (mode === "rename") {
    return (
      <li className="border-b border-line bg-white px-3 py-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onRename(title);
            setMode("view");
          }}
          className="flex items-center gap-1"
        >
          <label htmlFor={`rename-${thread.id}`} className="sr-only">
            Thread title
          </label>
          <input
            id={`rename-${thread.id}`}
            ref={inputRef}
            value={title}
            maxLength={120}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setMode("view")}
            className="h-7 min-w-0 flex-1 border border-ink px-2 text-xs"
          />
          <button type="submit" aria-label="Save title" className="flex h-7 w-7 items-center justify-center hover:bg-subtle">
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button type="button" aria-label="Cancel rename" onClick={() => setMode("view")} className="flex h-7 w-7 items-center justify-center hover:bg-subtle">
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </form>
      </li>
    );
  }

  return (
    <li className={cn("group relative border-b border-line", active ? "border-l-2 border-l-ink bg-white" : "hover:bg-white")}>
      <button type="button" onClick={onSelect} aria-current={active ? "page" : undefined} className="w-full px-3 py-2.5 pr-16 text-left">
        <span className="block truncate text-xs font-semibold text-ink">{stripNs(thread.title)}</span>
        <span className="mt-0.5 flex items-center gap-1.5 font-mono text-2xs text-muted">
          {thread.asset && <span className="num font-semibold text-ink-soft">{displaySymbol(thread.asset.symbol)}</span>}
          <span>{relativeTime(thread.updatedAt)}</span>
          <span aria-hidden="true">·</span>
          <span>{thread.messageCount} msgs</span>
        </span>
      </button>
      {mode === "confirm" ? (
        <div className="absolute inset-y-0 right-0 flex items-center gap-1 bg-white pl-2 pr-2">
          <span className="font-mono text-2xs text-loss">Delete?</span>
          <button type="button" onClick={onDelete} className="border border-loss px-1.5 py-0.5 font-mono text-2xs text-loss hover:bg-loss hover:text-white">
            Yes
          </button>
          <button type="button" onClick={() => setMode("view")} className="border border-line-strong px-1.5 py-0.5 font-mono text-2xs hover:border-ink">
            No
          </button>
        </div>
      ) : (
        <div className="absolute right-1 top-1/2 flex -translate-y-1/2 gap-0.5 opacity-100 md:opacity-0 md:focus-within:opacity-100 md:group-hover:opacity-100">
          <button
            type="button"
            onClick={() => {
              setTitle(thread.title);
              setMode("rename");
            }}
            aria-label={`Rename thread ${thread.title}`}
            className="flex h-7 w-7 items-center justify-center text-muted hover:bg-subtle hover:text-ink"
          >
            <Pencil className="h-3 w-3" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => setMode("confirm")}
            aria-label={`Delete thread ${thread.title}`}
            className="flex h-7 w-7 items-center justify-center text-muted hover:bg-loss-soft hover:text-loss"
          >
            <Trash2 className="h-3 w-3" aria-hidden="true" />
          </button>
        </div>
      )}
    </li>
  );
}

/** Recent threads. A fixed column on desktop; an overlay drawer below the md breakpoint. */
export default function ThreadSidebar(props: Props) {
  const { threads, loading, activeId, open, onClose, onSelect, onNew, onRename, onDelete, syncError, footer } = props;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={onClose} aria-hidden="true" />}
      <aside
        aria-label="Analysis threads"
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-line bg-canvas transition-transform duration-300 md:static md:z-auto md:transition-[width]",
          open ? "translate-x-0" : "-translate-x-full md:w-0 md:translate-x-0 md:overflow-hidden md:border-r-0",
        )}
      >
        <div className="flex min-w-[18rem] flex-1 flex-col overflow-hidden">
          <div className="flex items-center gap-2 border-b border-line p-3">
            <button
              type="button"
              onClick={onNew}
              className="flex h-9 flex-1 items-center justify-center gap-2 bg-ink text-xs font-semibold uppercase tracking-wider text-white hover:bg-ink-soft"
              data-testid="new-analysis"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" /> New Analysis
            </button>
            <button type="button" onClick={onClose} aria-label="Close threads" className="flex h-9 w-9 items-center justify-center border border-line-strong md:hidden">
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            <p className="px-3 pb-1 pt-3 font-mono text-2xs font-semibold uppercase tracking-widest text-muted">Recent threads</p>
            {syncError && <p className="mx-3 mb-2 border border-line bg-white p-2 font-mono text-2xs text-muted">{syncError}</p>}
            {loading && threads.length === 0 ? (
              <div className="space-y-2 px-3 py-2" aria-hidden="true">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-10 animate-pulse bg-subtle" />
                ))}
              </div>
            ) : threads.length === 0 ? (
              <div className="px-3 py-8 text-center">
                <p className="font-mono text-xs text-muted">No threads yet</p>
                <p className="mt-1 font-mono text-2xs text-muted-soft">Pick an asset and ask a question to begin</p>
              </div>
            ) : (
              <ul data-testid="thread-list">
                {threads.map((t) => (
                  <ThreadRow
                    key={t.id}
                    thread={t}
                    active={t.id === activeId}
                    onSelect={() => onSelect(t.id)}
                    onRename={(title) => onRename(t.id, title)}
                    onDelete={() => onDelete(t.id)}
                  />
                ))}
              </ul>
            )}
          </div>
          <div className="border-t border-line p-3">{footer}</div>
        </div>
      </aside>
    </>
  );
}
