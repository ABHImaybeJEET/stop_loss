"use client";

import React, { useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import AssetCombobox from "@/components/chat/AssetCombobox";
import { Button } from "@/components/ui/primitives";
import type { AssetRef } from "@/lib/chat/types";

const MAX_PROMPT = 4000;

interface Props {
  asset: AssetRef | null;
  onAssetChange: (asset: AssetRef | null) => void;
  running: boolean;
  onSend: (prompt: string, asset: AssetRef) => void;
  onStop: () => void;
}

export default function Composer({ asset, onAssetChange, running, onSend, onStop }: Props) {
  const [prompt, setPrompt] = useState("");
  const textRef = useRef<HTMLTextAreaElement>(null);
  const trimmed = prompt.trim();
  const canSend = Boolean(asset) && trimmed.length > 0 && trimmed.length <= MAX_PROMPT && !running;
  const hint = running
    ? "Analysis in progress. Stop it to send something new."
    : !asset
      ? "Select an asset to analyze."
      : !trimmed
        ? "Write a question or instruction for the agents."
        : trimmed.length > MAX_PROMPT
          ? `Prompt is too long (${trimmed.length}/${MAX_PROMPT}).`
          : null;

  const resize = () => {
    const el = textRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };
  useEffect(resize, [prompt]);

  const submit = () => {
    if (!canSend || !asset) return;
    onSend(trimmed, asset);
    setPrompt("");
  };

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
            <AssetCombobox value={asset} onChange={onAssetChange} disabled={running} onSelected={() => textRef.current?.focus()} />
            {asset && !running && <span className="hidden font-mono text-2xs text-muted sm:inline">Active asset for this thread</span>}
          </div>
          <div className="flex items-end gap-2 p-2">
            <label htmlFor="prompt" className="sr-only">
              Prompt
            </label>
            <textarea
              id="prompt"
              ref={textRef}
              value={prompt}
              rows={1}
              maxLength={MAX_PROMPT + 200}
              disabled={running}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder={asset ? `Ask about ${asset.symbol}: risk, hedges, news impact, what-ifs…` : "Pick an asset, then ask a question…"}
              className="max-h-[200px] min-h-[36px] flex-1 resize-none bg-transparent px-1 py-2 text-sm text-ink placeholder:text-muted-soft focus:outline-none disabled:text-muted"
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
          <p id="composer-hint" aria-live="polite" className={hint && !running && trimmed.length > MAX_PROMPT ? "text-loss" : undefined}>
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
