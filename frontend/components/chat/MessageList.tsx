"use client";

import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowDown } from "lucide-react";
import AssistantTurn from "@/components/chat/AssistantTurn";
import UserMessage, { AssetDivider } from "@/components/chat/UserMessage";
import { isAssistant } from "@/lib/chat/reducer";
import type { ChatMessage, FeedbackState } from "@/lib/chat/types";

interface Props {
  messages: ChatMessage[];
  threadId: string | null;
  running: boolean;
  userInitial: string;
  onRetry: (id: string) => void;
  onResume: (id: string) => void;
  onFeedback: (id: string, feedback: FeedbackState | undefined) => void;
  empty: React.ReactNode;
}

const NEAR_BOTTOM_PX = 120;

export default function MessageList({ messages, threadId, running, userInitial, onRetry, onResume, onFeedback, empty }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const [showJump, setShowJump] = useState(false);

  const scrollToBottom = useCallback((smooth: boolean) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }, []);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
    pinnedRef.current = near;
    if (near) setShowJump(false);
  };

  // Follow new content only while the user is at the bottom; never yank them back up/down.
  useLayoutEffect(() => {
    if (pinnedRef.current) scrollToBottom(false);
    else setShowJump(true);
  }, [messages, scrollToBottom]);

  // A new thread or a new send re-pins to the bottom.
  const count = messages.filter((m) => m.kind === "user").length;
  useEffect(() => {
    // When a new message is sent, we want to scroll the new user message into view.
    // The user message is the last user message in the list.
    const lastUserMessage = [...messages].reverse().find((m) => m.kind === "user");
    if (lastUserMessage) {
      const el = document.getElementById(`msg-${lastUserMessage.id}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        pinnedRef.current = false; // Unpin from bottom so we don't yank them down during streaming
      }
    } else {
      pinnedRef.current = true;
      scrollToBottom(false);
    }
  }, [threadId, count, scrollToBottom]);

  const lastAssistantId = [...messages].reverse().find(isAssistant)?.id;

  return (
    <div className="relative min-h-0 flex-1">
      <div ref={scrollRef} onScroll={onScroll} className="h-full overflow-y-auto overscroll-contain" data-testid="message-list">
        <div className="mx-auto w-full max-w-terminal space-y-5 px-3 py-5 sm:px-4">
          {messages.length === 0
            ? empty
            : messages.map((message) => {
                if (message.kind === "user") return <div id={`msg-${message.id}`} key={message.id}><UserMessage message={message} initial={userInitial} /></div>;
                if (message.kind === "divider") return <AssetDivider key={message.id} message={message} />;
                return (
                  <AssistantTurn
                    key={message.id}
                    message={message}
                    threadId={threadId}
                    canRetry={!running && message.id === lastAssistantId}
                    onRetry={onRetry}
                    onResume={onResume}
                    onFeedback={onFeedback}
                  />
                );
              })}
        </div>
      </div>
      {showJump && (
        <button
          type="button"
          onClick={() => {
            pinnedRef.current = true;
            setShowJump(false);
            scrollToBottom(true);
          }}
          className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 border border-ink bg-white px-3 py-1.5 font-mono text-2xs font-semibold uppercase tracking-wider text-ink shadow-md hover:bg-ink hover:text-white"
        >
          <ArrowDown className="h-3 w-3" aria-hidden="true" /> Latest
        </button>
      )}
    </div>
  );
}
