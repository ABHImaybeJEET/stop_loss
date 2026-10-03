"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { doc, getDoc, setDoc } from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useAuth } from "@/context/AuthContext";
import type { Holding, Portfolio } from "@/lib/portfolio/types";

/**
 * The signed-in user's NSE holdings: Firestore users/{uid}/portfolio/current is the source
 * of truth; localStorage caches it so the dashboard and chat render instantly.
 */

interface PortfolioContextValue {
  holdings: Holding[];
  loading: boolean;
  syncError: string | null;
  save: (holdings: Holding[]) => Promise<void>;
  editorOpen: boolean;
  openEditor: () => void;
  closeEditor: () => void;
}

const PortfolioContext = createContext<PortfolioContextValue | null>(null);

const cacheKey = (uid: string) => `sl_portfolio_${uid}`;

function readCache(uid: string): Portfolio | null {
  try {
    const raw = window.localStorage.getItem(cacheKey(uid));
    return raw ? (JSON.parse(raw) as Portfolio) : null;
  } catch {
    return null;
  }
}

function writeCache(uid: string, portfolio: Portfolio): void {
  try {
    window.localStorage.setItem(cacheKey(uid), JSON.stringify(portfolio));
  } catch {
    // best-effort cache
  }
}

function clean(holdings: Holding[]): Holding[] {
  // Firestore rejects undefined; keep only real, positive quantities.
  return holdings
    .filter((h) => h.quantity > 0)
    .map((h) => JSON.parse(JSON.stringify(h)) as Holding);
}

export function PortfolioProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const uid = user?.uid;
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);

  useEffect(() => {
    if (!uid) {
      setHoldings([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    const cached = readCache(uid);
    if (cached) setHoldings(cached.holdings);
    setLoading(true);
    getDoc(doc(db, "users", uid, "portfolio", "current"))
      .then((snap) => {
        if (cancelled) return;
        if (snap.exists()) {
          const remote = snap.data() as Portfolio;
          setHoldings(remote.holdings ?? []);
          writeCache(uid, remote);
        }
        setSyncError(null);
      })
      .catch((err) => {
        console.warn("Portfolio sync failed", err);
        if (!cancelled) setSyncError("Cloud sync unavailable. Your portfolio is saved on this device only.");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [uid]);

  const save = useCallback(
    async (next: Holding[]) => {
      if (!uid) return;
      const portfolio: Portfolio = { holdings: clean(next), updatedAt: new Date().toISOString() };
      setHoldings(portfolio.holdings);
      writeCache(uid, portfolio);
      try {
        await setDoc(doc(db, "users", uid, "portfolio", "current"), portfolio);
        setSyncError(null);
      } catch (err) {
        console.warn("Portfolio save failed", err);
        setSyncError("Cloud sync unavailable. Your portfolio is saved on this device only.");
      }
    },
    [uid],
  );

  const value = useMemo<PortfolioContextValue>(
    () => ({
      holdings,
      loading,
      syncError,
      save,
      editorOpen,
      openEditor: () => setEditorOpen(true),
      closeEditor: () => setEditorOpen(false),
    }),
    [holdings, loading, syncError, save, editorOpen],
  );

  return <PortfolioContext.Provider value={value}>{children}</PortfolioContext.Provider>;
}

export function usePortfolio(): PortfolioContextValue {
  const value = useContext(PortfolioContext);
  if (!value) throw new Error("usePortfolio must be used inside PortfolioProvider");
  return value;
}
