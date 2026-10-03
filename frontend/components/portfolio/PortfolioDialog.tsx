"use client";

import React, { useEffect, useRef, useState } from "react";
import { Briefcase, Trash2, X } from "lucide-react";
import AssetCombobox from "@/components/chat/AssetCombobox";
import { Button, cn } from "@/components/ui/primitives";
import { usePortfolio } from "@/context/PortfolioContext";
import type { AssetRef } from "@/lib/chat/types";
import type { Holding } from "@/lib/portfolio/types";

interface Row {
  symbol: string;
  name: string;
  quantity: string;
  avgPrice: string;
  addedAt: string;
}

function toRows(holdings: Holding[]): Row[] {
  return holdings.map((h) => ({
    symbol: h.symbol,
    name: h.name,
    quantity: String(h.quantity),
    avgPrice: h.avgPrice !== undefined ? String(h.avgPrice) : "",
    addedAt: h.addedAt,
  }));
}

function rowError(row: Row): string | null {
  const qty = Number(row.quantity);
  if (!row.quantity.trim() || !Number.isInteger(qty) || qty <= 0) return "Whole number of shares > 0";
  if (row.avgPrice.trim() && !(Number(row.avgPrice) > 0)) return "Avg price must be > 0";
  return null;
}

/** Navbar-launched editor for the user's NSE holdings. */
export default function PortfolioDialog() {
  const { holdings, save, editorOpen, closeEditor } = usePortfolio();
  const [rows, setRows] = useState<Row[]>([]);
  const [asset, setAsset] = useState<AssetRef | null>(null);
  const [saving, setSaving] = useState(false);
  const [touched, setTouched] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!editorOpen) return;
    setRows(toRows(holdings));
    setAsset(null);
    setTouched(false);
    requestAnimationFrame(() => panelRef.current?.querySelector<HTMLInputElement>("input")?.focus());
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeEditor();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editorOpen, holdings, closeEditor]);

  if (!editorOpen) return null;

  const add = (picked: AssetRef | null) => {
    setAsset(null);
    if (!picked) return;
    setRows((current) =>
      current.some((r) => r.symbol === picked.symbol)
        ? current
        : [...current, { symbol: picked.symbol, name: picked.name, quantity: "", avgPrice: "", addedAt: new Date().toISOString() }],
    );
    requestAnimationFrame(() =>
      panelRef.current?.querySelector<HTMLInputElement>(`[data-qty="${picked.symbol}"]`)?.focus(),
    );
  };

  const update = (symbol: string, patch: Partial<Row>) =>
    setRows((current) => current.map((r) => (r.symbol === symbol ? { ...r, ...patch } : r)));

  const invalid = rows.some((r) => rowError(r) !== null);

  const submit = async () => {
    setTouched(true);
    if (invalid) return;
    setSaving(true);
    await save(
      rows.map((r) => ({
        symbol: r.symbol,
        name: r.name,
        quantity: Number(r.quantity),
        avgPrice: r.avgPrice.trim() ? Number(r.avgPrice) : undefined,
        addedAt: r.addedAt,
      })),
    );
    setSaving(false);
    closeEditor();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-3 pt-[8vh]" onMouseDown={closeEditor}>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="portfolio-title"
        onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-2xl border border-ink bg-white shadow-xl"
        data-testid="portfolio-dialog"
      >
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 id="portfolio-title" className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-widest text-ink">
            <Briefcase className="h-4 w-4" aria-hidden="true" /> My portfolio
          </h2>
          <button type="button" onClick={closeEditor} aria-label="Close" className="flex h-8 w-8 items-center justify-center hover:bg-subtle">
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>
        <div className="space-y-3 p-4">
          <div>
            <p className="mb-1.5 text-xs text-muted">Add an NSE stock you own, then enter the number of shares.</p>
            <AssetCombobox value={asset} onChange={add} placement="down" />
          </div>
          {rows.length === 0 ? (
            <p className="border border-dashed border-line px-3 py-6 text-center font-mono text-2xs text-muted">No holdings yet</p>
          ) : (
            <div className="overflow-x-auto border border-line">
              <table className="w-full text-left text-xs">
                <thead className="bg-canvas font-mono text-2xs uppercase tracking-wider text-muted">
                  <tr>
                    <th scope="col" className="px-2.5 py-2">Stock</th>
                    <th scope="col" className="px-2.5 py-2">Shares</th>
                    <th scope="col" className="px-2.5 py-2">Avg buy price ₹ (optional)</th>
                    <th scope="col" className="px-2.5 py-2"><span className="sr-only">Remove</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {rows.map((row) => {
                    const error = touched ? rowError(row) : null;
                    return (
                      <tr key={row.symbol} className="align-top">
                        <td className="px-2.5 py-2">
                          <span className="num block font-bold text-ink">{row.symbol.replace(/\.NS$/, "")}</span>
                          <span className="block max-w-[14rem] truncate text-2xs text-muted">{row.name}</span>
                        </td>
                        <td className="px-2.5 py-2">
                          <label className="sr-only" htmlFor={`qty-${row.symbol}`}>Shares of {row.symbol}</label>
                          <input
                            id={`qty-${row.symbol}`}
                            data-qty={row.symbol}
                            inputMode="numeric"
                            value={row.quantity}
                            onChange={(e) => update(row.symbol, { quantity: e.target.value.replace(/[^\d]/g, "") })}
                            className={cn("num h-8 w-24 border px-2", error ? "border-loss" : "border-line-strong focus:border-ink")}
                            aria-invalid={Boolean(error)}
                          />
                        </td>
                        <td className="px-2.5 py-2">
                          <label className="sr-only" htmlFor={`avg-${row.symbol}`}>Average buy price of {row.symbol}</label>
                          <input
                            id={`avg-${row.symbol}`}
                            inputMode="decimal"
                            value={row.avgPrice}
                            onChange={(e) => update(row.symbol, { avgPrice: e.target.value.replace(/[^\d.]/g, "") })}
                            className="num h-8 w-32 border border-line-strong px-2 focus:border-ink"
                          />
                          {error && <p className="mt-1 font-mono text-2xs text-loss">{error}</p>}
                        </td>
                        <td className="px-2.5 py-2 text-right">
                          <button
                            type="button"
                            onClick={() => setRows((current) => current.filter((r) => r.symbol !== row.symbol))}
                            aria-label={`Remove ${row.symbol}`}
                            className="flex h-8 w-8 items-center justify-center text-muted hover:bg-loss-soft hover:text-loss"
                          >
                            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <footer className="flex items-center justify-between gap-2 border-t border-line px-4 py-3">
          <span className="font-mono text-2xs text-muted">{rows.length} holding{rows.length === 1 ? "" : "s"} · NSE only</span>
          <span className="flex gap-2">
            <Button variant="ghost" onClick={closeEditor}>Cancel</Button>
            <Button variant="primary" onClick={submit} disabled={saving || (touched && invalid)} data-testid="portfolio-save">
              {saving ? "Saving…" : "Save portfolio"}
            </Button>
          </span>
        </footer>
      </div>
    </div>
  );
}

export function PortfolioButton({ className }: { className?: string }) {
  const { openEditor, holdings } = usePortfolio();
  return (
    <button
      type="button"
      onClick={openEditor}
      className={cn(
        "inline-flex items-center gap-1.5 border border-line-strong px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-ink hover:border-ink",
        className,
      )}
      data-testid="portfolio-button"
    >
      <Briefcase className="h-3.5 w-3.5" aria-hidden="true" />
      {holdings.length ? `Portfolio (${holdings.length})` : "Add portfolio"}
    </button>
  );
}
