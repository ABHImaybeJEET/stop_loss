import React from "react";
import { relativeTime } from "@/lib/format";
import type { DividerMessage, UserMessage as UserMessageType } from "@/lib/chat/types";

export default function UserMessage({ message, initial }: { message: UserMessageType; initial: string }) {
  return (
    <div className="flex justify-end" data-testid="user-message">
      <div className="max-w-[85%] sm:max-w-[75%]">
        <div className="mb-1 flex items-center justify-end gap-2">
          <span className="num border border-line-strong bg-white px-1.5 py-0.5 text-2xs font-bold text-ink">{message.asset.symbol}</span>
          <time className="font-mono text-2xs text-muted" dateTime={message.createdAt}>
            {relativeTime(message.createdAt)}
          </time>
          <span className="flex h-5 w-5 items-center justify-center bg-ink font-mono text-2xs font-bold uppercase text-white" aria-hidden="true">
            {initial}
          </span>
        </div>
        <p className="whitespace-pre-wrap break-words border border-ink bg-ink px-3 py-2 text-sm text-white">{message.content}</p>
      </div>
    </div>
  );
}

export function AssetDivider({ message }: { message: DividerMessage }) {
  return (
    <div className="flex items-center gap-3 py-1" role="separator" aria-label={`Now analyzing ${message.asset.symbol}`}>
      <span className="h-px flex-1 bg-line-strong" />
      <span className="font-mono text-2xs uppercase tracking-widest text-muted">
        Now analyzing: <span className="num font-bold text-ink">{message.asset.symbol}</span>
      </span>
      <span className="h-px flex-1 bg-line-strong" />
    </div>
  );
}
