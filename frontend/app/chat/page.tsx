"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import StopLossLogo from "@/components/StopLossLogo";
import ProtectedRoute from "@/components/ProtectedRoute";
import { fetchUserProfile, UserProfile } from "@/lib/userProfile";

/* ─── Types ─── */
interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  tags?: string[];
}

interface ChatThread {
  id: string;
  title: string;
  preview: string;
  timestamp: Date;
  messageCount: number;
}

/* ─── Helpers ─── */
function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/* ─── Tag Badge Component ─── */
function TagBadge({ tag }: { tag: string }) {
  const colorMap: Record<string, string> = {
    TARIFF: "bg-amber-50 text-amber-700 border-amber-200",
    BANK_TAX: "bg-violet-50 text-violet-700 border-violet-200",
    WAR_CRISIS: "bg-red-50 text-red-700 border-red-200",
    WEATHER_EXTREME: "bg-sky-50 text-sky-700 border-sky-200",
    QUANT: "bg-emerald-50 text-emerald-700 border-emerald-200",
    HEDGING: "bg-blue-50 text-blue-700 border-blue-200",
  };
  const style = colorMap[tag] || "bg-gray-100 text-gray-700 border-gray-200";

  return (
    <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider border ${style}`}>
      {tag}
    </span>
  );
}

/* ─── Typing Indicator Component ─── */
function TypingIndicator() {
  return (
    <div className="py-4 px-6 bg-[#FAFAFA] border-b border-gray-100">
      <div className="max-w-3xl mx-auto flex items-center space-x-3">
        <div className="w-7 h-7 bg-black text-white flex items-center justify-center text-[10px] font-mono font-bold flex-shrink-0">
          AI
        </div>
        <div className="flex items-center space-x-1.5 py-2">
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" />
          <span className="text-xs font-mono text-gray-400 ml-2">Agents Analyzing Risk Factors...</span>
        </div>
      </div>
    </div>
  );
}

function ChatContent() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [input, setInput] = useState("");
  const [isTyping] = useState(false);
  const [activeThread, setActiveThread] = useState<string>("new");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [profile, setProfile] = useState<UserProfile | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (user) {
      fetchUserProfile(user.uid || user.email).then((p) => setProfile(p));
    }
  }, [user]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
  };

  const handleSend = () => {
    if (!input.trim() || isTyping) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setActiveThread("new");
    setInput("");
  };

  const avatarInitial = profile?.fullName?.charAt(0) || user?.displayName?.charAt(0) || user?.email?.charAt(0) || "U";
  const displayName = profile?.fullName || user?.displayName || user?.email?.split("@")[0] || "Analyst";

  return (
    <div className="h-screen flex flex-col bg-white text-gray-900 font-sans overflow-hidden">
      {/* ─── Top Bar ─── */}
      <header className="w-full border-b border-gray-200 bg-white px-4 py-3 flex justify-between items-center flex-shrink-0 z-30">
        <div className="flex items-center space-x-4">
          {/* Sidebar Toggle */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-8 h-8 flex items-center justify-center hover:bg-gray-100 transition-colors"
            aria-label="Toggle sidebar"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>

          <Link href="/" className="flex items-center text-gray-900">
            <StopLossLogo height={30} />
          </Link>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            href="/dashboard"
            className="text-xs font-semibold uppercase tracking-wider text-gray-600 hover:text-black transition-colors px-2 py-1"
          >
            Dashboard
          </Link>
          <button
            onClick={async () => {
              await logout();
              router.push("/login");
            }}
            className="bg-white text-gray-900 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider border border-gray-300 hover:border-black transition-colors rounded-none"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* ─── Body: Sidebar + Chat ─── */}
      <div className="flex-1 flex overflow-hidden">
        {/* ─── Sidebar ─── */}
        <aside
          className={`${
            sidebarOpen ? "w-72" : "w-0"
          } transition-all duration-300 ease-in-out border-r border-gray-200 bg-[#FAFAFA] flex-shrink-0 overflow-hidden flex flex-col`}
        >
          <div className="min-w-[288px] h-full flex flex-col">
            {/* New Chat Button */}
            <div className="p-3 border-b border-gray-200 flex-shrink-0">
              <button
                onClick={handleNewChat}
                className="w-full bg-black text-white py-2.5 text-xs font-semibold uppercase tracking-wider hover:bg-gray-800 transition-colors flex items-center justify-center space-x-2"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <span>New Analysis</span>
              </button>
            </div>

            {/* Thread History */}
            <div className="flex-1 overflow-y-auto">
              <div className="px-3 pt-3 pb-1">
                <span className="text-[10px] font-mono font-semibold uppercase tracking-widest text-gray-400">
                  Recent Threads
                </span>
              </div>
              {threads.length === 0 ? (
                <div className="px-3 py-8 text-center">
                  <p className="text-xs text-gray-400 font-mono">No threads yet</p>
                  <p className="text-[10px] text-gray-300 font-mono mt-1">Start a new analysis to begin</p>
                </div>
              ) : (
                threads.map((thread) => (
                  <button
                    key={thread.id}
                    onClick={() => setActiveThread(thread.id)}
                    className={`w-full text-left px-3 py-3 border-b border-gray-100 hover:bg-white transition-colors group ${
                      activeThread === thread.id ? "bg-white border-l-2 border-l-black" : ""
                    }`}
                  >
                    <div className="flex justify-between items-start mb-0.5">
                      <span className="text-xs font-semibold text-gray-900 truncate pr-2 group-hover:text-black">
                        {thread.title}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-500 truncate">{thread.preview}</p>
                    <div className="flex items-center space-x-2 mt-1.5">
                      <span className="text-[10px] font-mono text-gray-400">{formatTime(thread.timestamp)}</span>
                      <span className="text-[10px] font-mono text-gray-300">·</span>
                      <span className="text-[10px] font-mono text-gray-400">{thread.messageCount} msgs</span>
                    </div>
                  </button>
                ))
              )}
            </div>

            {/* Sidebar Footer - Dynamic User Profile */}
            <div className="border-t border-gray-200 p-3 mt-auto bg-[#FAFAFA] flex-shrink-0">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 bg-black text-white flex items-center justify-center text-xs font-mono font-bold flex-shrink-0 uppercase">
                  {avatarInitial}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-gray-900 truncate">
                    {displayName}
                  </p>
                  <p className="text-[10px] font-mono text-gray-400 truncate">{user?.email}</p>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* ─── Chat Area ─── */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto w-full">
              {messages.length === 0 ? (
                /* ─── Empty State ─── */
                <div className="flex flex-col items-center justify-center h-full min-h-[400px] px-6">
                  <div className="w-10 h-10 bg-black text-white flex items-center justify-center text-sm font-mono font-bold mb-4">
                    S
                  </div>
                  <h3 className="text-base font-bold text-gray-900 mb-1">
                    StopLoss Financial Intelligence Engine
                  </h3>
                  <p className="text-xs text-gray-500 font-mono text-center max-w-md mb-6">
                    Ask questions about global news events, market shocks, tariff escalation, or quant risk scenarios.
                  </p>
                </div>
              ) : (
                <>
                  {messages.map((msg) => {
                    const isUser = msg.role === "user";
                    return (
                      <div
                        key={msg.id}
                        className={`py-6 px-6 border-b border-gray-100 ${
                          isUser ? "bg-white" : "bg-[#FAFAFA]"
                        }`}
                      >
                        <div className="max-w-3xl mx-auto flex space-x-4">
                          <div
                            className={`w-7 h-7 flex items-center justify-center text-[10px] font-mono font-bold flex-shrink-0 mt-0.5 uppercase ${
                              isUser ? "bg-black text-white" : "bg-gray-200 text-gray-700"
                            }`}
                          >
                            {isUser ? avatarInitial : "AI"}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-2 mb-1">
                              <span className="text-xs font-semibold text-gray-900">
                                {isUser ? displayName : "StopLoss Agent"}
                              </span>
                              <span className="text-[10px] font-mono text-gray-400">
                                {formatTime(msg.timestamp)}
                              </span>
                            </div>

                            {msg.tags && msg.tags.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 mb-2.5">
                                {msg.tags.map((tag) => (
                                  <TagBadge key={tag} tag={tag} />
                                ))}
                              </div>
                            )}

                            <div className="text-xs text-gray-800 leading-relaxed font-sans whitespace-pre-wrap">
                              {msg.content}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {isTyping && <TypingIndicator />}
                </>
              )}
              <div ref={messagesEndRef} className="h-4" />
            </div>
          </div>

          {/* ─── Input Bar ─── */}
          <div className="border-t border-gray-200 bg-white p-4 flex-shrink-0">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-end space-x-3">
                <div className="flex-1 border border-gray-300 bg-white focus-within:border-black transition-colors">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about tariffs, risk scenarios, weather impacts, hedging strategies..."
                    rows={1}
                    className="w-full px-4 py-3 text-sm text-gray-900 placeholder-gray-400 bg-transparent resize-none focus:outline-none font-sans"
                    style={{ maxHeight: "160px" }}
                    disabled={isTyping}
                  />
                </div>
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isTyping}
                  className="bg-black text-white px-5 py-3 text-xs font-semibold uppercase tracking-wider hover:bg-gray-800 transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex items-center space-x-2 flex-shrink-0"
                >
                  <span>Send</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
              <div className="flex items-center justify-between mt-2">
                <p className="text-[10px] font-mono text-gray-400">
                  SHIFT + ENTER for new line · Agents: Sentiment · Weather & Macro · Quant Risk · Hedging
                </p>
                <p className="text-[10px] font-mono text-gray-400">
                  {messages.filter((m) => m.role !== "system").length} messages
                </p>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <ProtectedRoute>
      <ChatContent />
    </ProtectedRoute>
  );
}
