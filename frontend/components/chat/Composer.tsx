"use client";

import { displaySymbol } from "@/lib/symbols";
import React, { useEffect, useRef, useState } from "react";
import { ArrowUp, Briefcase, Square, TrendingUp } from "lucide-react";
import AssetCombobox from "@/components/chat/AssetCombobox";
import { Button, cn } from "@/components/ui/primitives";
import type { ChatScope } from "@/lib/chat/scope";
import type { AssetRef } from "@/lib/chat/types";

const MAX_PROMPT = 4000;

interface Props {
  scope: ChatScope | null;
  onScopeChange: (scope: ChatScope | null) => void;
  holdingsCount: number;
  onEditPortfolio: () => void;
  running: boolean;
  onSend: (prompt: string, scope: ChatScope) => void;
  onStop: () => void;
}

/** The user must pick Portfolio or one NSE stock before a question can be written. */
export default function Composer({ scope, onScopeChange, holdingsCount, onEditPortfolio, running, onSend, onStop }: Props) {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<"portfolio" | "ticker" | null>(scope?.kind ?? null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => setMode(scope?.kind ?? mode), [scope]); // eslint-disable-line react-hooks/exhaustive-deps

  const portfolioReady = scope?.kind === "portfolio" && holdingsCount > 0;
  const tickerReady = scope?.kind === "ticker";
  const scopeReady = portfolioReady || tickerReady;
  const trimmed = prompt.trim();
  const canSend = scopeReady && trimmed.length > 0 && trimmed.length <= MAX_PROMPT && !running;
  const hint = running
    ? "Analysis in progress. Stop it to send something new."
    : !mode
      ? "Select Portfolio or a stock to ask a question."
      : mode === "portfolio" && holdingsCount === 0
        ? "Your portfolio is empty: add holdings first."
        : mode === "ticker" && !tickerReady
          ? "Search and select an NSE stock."
          : !trimmed
            ? "Write a question for the agents."
            : trimmed.length > MAX_PROMPT
              ? `Prompt is too long (${trimmed.length}/${MAX_PROMPT}).`
              : null;

  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [prompt]);

  const choose = (next: "portfolio" | "ticker") => {
    setMode(next);
    if (next === "portfolio") {
      if (holdingsCount === 0) onEditPortfolio();
      onScopeChange({ kind: "portfolio" });
      requestAnimationFrame(() => textRef.current?.focus());
    } else {
      onScopeChange(null);
    }
  };

  const submit = () => {
    if (!canSend || !scope) return;
    onSend(trimmed, scope);
    setPrompt("");
  };

  const placeholder = !scopeReady
    ? "Select Portfolio or a stock first…"
    : scope?.kind === "portfolio"
      ? "Ask about your portfolio: events, risks, hedges, what-ifs…"
      : `Ask about ${displaySymbol((scope as { asset: AssetRef }).asset.symbol)}: risk, hedges, news impact…`;

  return (
    <div className="border-t border-line bg-white px-3 pb-3 pt-2 sm:px-4" data-testid="composer">
      <div className="mx-auto max-w-terminal">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="border border-line-strong bg-white focus-within:border-ink"
          aria-describedby="composer-hint"
        >
          <div className="flex flex-wrap items-center gap-2 px-2 pt-2">
            <div role="radiogroup" aria-label="Ask about" className="flex border border-line-strong">
              {([
                ["portfolio", "Portfolio", Briefcase],
                ["ticker", "Stock", TrendingUp],
              ] as const).map(([value, label, Icon]) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={mode === value}
                  disabled={running}
                  onClick={() => choose(value)}
                  className={cn(
                    "flex h-8 items-center gap-1.5 border-r border-line-strong px-2.5 text-2xs font-semibold uppercase tracking-wider last:border-r-0 disabled:opacity-50",
                    mode === value ? "bg-ink text-white" : "bg-white text-muted hover:text-ink",
                  )}
                  data-testid={`scope-${value}`}
                >
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  {label}
                </button>
              ))}
            </div>
            {mode === "portfolio" && (
              <div className="flex items-center gap-1.5 border border-ink bg-ink py-1 pl-2 pr-1 text-white" data-testid="portfolio-chip">
                <span className="text-xs font-bold">My portfolio</span>
                <span className="font-mono text-2xs text-white/70">
                  {holdingsCount} holding{holdingsCount === 1 ? "" : "s"}
                </span>
                <button
                  type="button"
                  onClick={onEditPortfolio}
                  disabled={running}
                  className="ml-0.5 px-1.5 font-mono text-2xs text-white/80 underline-offset-2 hover:underline disabled:opacity-40"
                >
                  Edit
                </button>
              </div>
            )}
            {mode === "ticker" && (
              <AssetCombobox
                value={scope?.kind === "ticker" ? scope.asset : null}
                onChange={(a) => onScopeChange(a ? { kind: "ticker", asset: a } : null)}
                disabled={running}
                onSelected={() => textRef.current?.focus()}
              />
            )}
          </div>
          <div className="flex items-end gap-2 p-2">
            <label htmlFor="prompt" className="sr-only">
              Question
            </label>
            <textarea
              id="prompt"
              ref={textRef}
              value={prompt}
              rows={1}
              maxLength={MAX_PROMPT + 200}
              disabled={running || !scopeReady}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder={placeholder}
              className="max-h-[200px] min-h-[36px] flex-1 resize-none bg-transparent px-1 py-2 text-sm text-ink placeholder:text-muted-soft focus:outline-none disabled:cursor-not-allowed disabled:text-muted"
              data-testid="prompt-input"
            />
            {running ? (
              <Button variant="secondary" onClick={onStop} aria-label="Stop analysis" data-testid="stop-button">
                <Square className="h-3 w-3 fill-current" aria-hidden="true" />
                <span className="hidden sm:inline">Stop</span>
              </Button>
            ) : (
              <Button type="submit" variant="primary" disabled={!canSend} aria-label="Send" data-testid="send-button">
                <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">Send</span>
              </Button>
            )}
          </div>
        </form>
        <div className="mt-1.5 flex items-center justify-between gap-3 font-mono text-2xs text-muted">
          <p id="composer-hint" aria-live="polite" className={trimmed.length > MAX_PROMPT ? "text-loss" : undefined}>
            {hint ?? "Enter to send · Shift+Enter for a new line"}
          </p>
          {trimmed.length > MAX_PROMPT * 0.8 && (
            <span className="num shrink-0">
              {trimmed.length}/{MAX_PROMPT}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
