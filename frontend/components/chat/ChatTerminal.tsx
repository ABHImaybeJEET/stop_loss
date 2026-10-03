"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Menu } from "lucide-react";
import Composer from "@/components/chat/Composer";
import MessageList from "@/components/chat/MessageList";
import ThreadSidebar from "@/components/chat/ThreadSidebar";
import { PortfolioButton } from "@/components/portfolio/PortfolioDialog";
import StopLossLogo from "@/components/StopLossLogo";
import { useAuth } from "@/context/AuthContext";
import { useChatStream } from "@/lib/chat/useChatStream";
import { useThreads } from "@/lib/chat/useThreads";
import { fetchUserProfile, type UserProfile } from "@/lib/userProfile";
import type { AssetRef, ChatMessage } from "@/lib/chat/types";

function latestAsset(messages: ChatMessage[]): AssetRef | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.kind === "user" || m.kind === "divider") return m.asset;
  }
  return null;
}

const EXAMPLES = [
  "How will the forecasted storm season affect this energy holding over the next month?",
  "I hold this for 6 months. How risky is it now and how should I hedge?",
  "What does live news and macro data say about near-term downside?",
];

export default function ChatTerminal() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const threadId = params.get("thread");
  const uid = user?.uid;

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [asset, setAsset] = useState<AssetRef | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [loadingThread, setLoadingThread] = useState(false);
  const createdRef = useRef<string | null>(null);

  const threads = useThreads(uid);

  useEffect(() => {
    setSidebarOpen(window.matchMedia("(min-width: 768px)").matches);
  }, []);

  useEffect(() => {
    if (uid) fetchUserProfile(uid).then(setProfile);
  }, [uid]);

  const onAuthExpired = useCallback(async () => {
    await logout().catch(() => undefined);
    router.push("/login");
  }, [logout, router]);

  const ensureThread = useCallback(
    async (prompt: string, a: AssetRef) => {
      const id = await threads.createThread(prompt, a);
      createdRef.current = id;
      router.replace(`/chat?thread=${id}`, { scroll: false });
      return id;
    },
    [threads, router],
  );

  const chat = useChatStream(threadId, {
    persist: threads.saveMessage,
    discard: threads.discardMessage,
    ensureThread,
    onAuthExpired,
    announce: setAnnouncement,
  });
  const { load } = chat;

  // Restore a thread from the URL (refresh, deep link, sidebar click).
  useEffect(() => {
    if (!uid) return;
    if (!threadId) {
      if (!createdRef.current) load([]);
      return;
    }
    if (createdRef.current === threadId) return; // just created by this session's first send
    let cancelled = false;
    setLoadingThread(true);
    threads.loadMessages(threadId).then((messages) => {
      if (cancelled) return;
      load(messages);
      const meta = threads.threads.find((t) => t.id === threadId);
      setAsset(latestAsset(messages) ?? meta?.asset ?? null);
      setLoadingThread(false);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when the thread changes
  }, [uid, threadId]);

  const closeOnMobile = () => {
    if (!window.matchMedia("(min-width: 768px)").matches) setSidebarOpen(false);
  };

  const newAnalysis = () => {
    if (chat.running) chat.stop();
    createdRef.current = null;
    load([]);
    setAsset(null);
    router.push("/chat");
    closeOnMobile();
  };

  const selectThread = (id: string) => {
    if (id === threadId) return closeOnMobile();
    if (chat.running) chat.stop();
    createdRef.current = null;
    router.push(`/chat?thread=${id}`);
    closeOnMobile();
  };

  const deleteThread = async (id: string) => {
    await threads.deleteThread(id);
    if (id === threadId) newAnalysis();
  };

  const initial = (profile?.fullName || user?.displayName || user?.email || "U").charAt(0).toUpperCase();
  const displayName = profile?.fullName || user?.displayName || user?.email?.split("@")[0] || "Analyst";

  const empty = loadingThread ? (
    <div className="space-y-3 py-10" aria-hidden="true">
      <div className="ml-auto h-10 w-2/3 animate-pulse bg-subtle" />
      <div className="h-40 animate-pulse bg-subtle" />
    </div>
  ) : (
    <div className="flex min-h-[50vh] flex-col items-center justify-center py-10 text-center">
      <div className="mb-4 flex h-10 w-10 items-center justify-center bg-ink font-mono text-sm font-bold text-white">S</div>
      <h1 className="text-base font-bold text-ink">Asset Analysis Terminal</h1>
      <p className="mt-1 max-w-md font-mono text-xs text-muted">
        Pick an asset, ask a question, and eight agents gather live market, news, macro and weather data, then compute risk
        and evidence-backed hedges.
      </p>
      <ul className="mt-6 w-full max-w-lg space-y-1.5 text-left">
        {EXAMPLES.map((e) => (
          <li key={e} className="border border-line bg-white px-3 py-2 text-xs text-ink-soft">
            <span className="mr-2 font-mono text-2xs text-muted">e.g.</span>
            {e}
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-white text-ink">
      <header className="z-20 flex flex-shrink-0 items-center justify-between border-b border-line bg-white px-3 py-2.5 sm:px-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label={sidebarOpen ? "Hide threads" : "Show threads"}
            aria-expanded={sidebarOpen}
            className="flex h-8 w-8 items-center justify-center hover:bg-subtle"
          >
            <Menu className="h-4 w-4" aria-hidden="true" />
          </button>
          <Link href="/" className="flex items-center text-ink" aria-label="StopLoss home">
            <StopLossLogo height={28} />
          </Link>
        </div>
        <nav className="flex items-center gap-2 sm:gap-3">
          <PortfolioButton />
          <Link href="/dashboard" className="px-2 py-1 text-xs font-semibold uppercase tracking-wider text-muted hover:text-ink">
            Dashboard
          </Link>
          <button
            type="button"
            onClick={async () => {
              await logout();
              router.push("/login");
            }}
            className="border border-line-strong px-3 py-1.5 text-xs font-semibold uppercase tracking-wider hover:border-ink"
          >
            Sign Out
          </button>
        </nav>
      </header>

      <div className="flex min-h-0 flex-1">
        <ThreadSidebar
          threads={threads.threads}
          loading={threads.loading}
          activeId={threadId}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onSelect={selectThread}
          onNew={newAnalysis}
          onRename={threads.renameThread}
          onDelete={deleteThread}
          syncError={threads.syncError}
          footer={
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center bg-ink font-mono text-xs font-bold uppercase text-white">
                {initial}
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-ink">{displayName}</p>
                <p className="truncate font-mono text-2xs text-muted">{user?.email}</p>
              </div>
            </div>
          }
        />
        <main className="flex min-w-0 flex-1 flex-col">
          <MessageList
            messages={chat.messages}
            threadId={threadId}
            running={chat.running}
            userInitial={initial}
            onRetry={chat.retry}
            onResume={chat.resume}
            onFeedback={chat.setFeedback}
            empty={empty}
          />
          <Composer asset={asset} onAssetChange={setAsset} running={chat.running} onSend={chat.send} onStop={chat.stop} />
        </main>
      </div>
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>
    </div>
  );
}
