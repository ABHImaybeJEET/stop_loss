"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Briefcase } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { usePortfolio } from "@/context/PortfolioContext";
import StopLossLogo from "@/components/StopLossLogo";
import ProtectedRoute from "@/components/ProtectedRoute";
import AssetLiveChart from "@/components/chat/AssetLiveChart";
import HoldingsTable, { PortfolioSummary } from "@/components/portfolio/HoldingsTable";
import PerformanceChart from "@/components/portfolio/PerformanceChart";
import { PortfolioButton } from "@/components/portfolio/PortfolioDialog";
import PortfolioNews from "@/components/portfolio/PortfolioNews";
import WeatherPanel from "@/components/portfolio/WeatherPanel";
import { combine, usePortfolioData } from "@/components/portfolio/usePortfolioData";
import { Button } from "@/components/ui/primitives";
import { relativeTime } from "@/lib/format";
import { fetchUserProfile, UserProfile } from "@/lib/userProfile";

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const { holdings, loading, syncError, openEditor } = usePortfolio();
  const [range, setRange] = useState("6mo");
  const [selected, setSelected] = useState<string | null>(null);
  const { quotes, news, weather, performance } = usePortfolioData(holdings, range);
  const { rows, totals } = useMemo(() => combine(holdings, quotes.data), [holdings, quotes.data]);

  useEffect(() => {
    if (user) fetchUserProfile(user.uid || user.email).then(setProfile);
  }, [user]);

  // Default the chart to the largest position once prices arrive.
  useEffect(() => {
    if (selected && holdings.some((h) => h.symbol === selected)) return;
    const largest = [...rows].sort((a, b) => (b.value ?? 0) - (a.value ?? 0))[0];
    setSelected(largest?.symbol ?? holdings[0]?.symbol ?? null);
  }, [rows, holdings, selected]);

  const displayName = profile?.fullName || user?.displayName || user?.email?.split("@")[0] || "Analyst";
  const selectedHolding = holdings.find((h) => h.symbol === selected);
  const marketState = quotes.data?.find((q) => q.marketState)?.marketState;
  const asOf = quotes.data?.find((q) => q.marketTime)?.marketTime;

  return (
    <div className="flex min-h-screen flex-col bg-white font-sans text-ink">
      <header className="flex w-full flex-wrap items-center justify-between gap-3 border-b border-line bg-white px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center text-ink" aria-label="StopLoss home">
          <StopLossLogo height={30} />
        </Link>
        <nav className="flex flex-wrap items-center gap-2 sm:gap-3">
          <Link href="/chat" className="bg-ink px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider text-white hover:bg-ink-soft">
            Terminal
          </Link>
          <PortfolioButton />
          <Link href="/onboarding" className="px-2 py-1 text-xs font-semibold uppercase tracking-wider text-muted hover:text-ink">
            Edit profile
          </Link>
          <button
            type="button"
            onClick={async () => {
              await logout();
              router.push("/login");
            }}
            className="border border-line-strong px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider hover:border-ink"
          >
            Sign out
          </button>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 space-y-5 p-4 sm:p-6 md:p-8">
        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line pb-4">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">{displayName}</h1>
            <p className="mt-0.5 font-mono text-xs text-muted">
              {[profile?.role, profile?.organization, profile?.location].filter(Boolean).join(" · ") || user?.email}
            </p>
          </div>
          {holdings.length > 0 && (
            <p className="font-mono text-2xs text-muted">
              NSE {marketState ? `market ${marketState}` : ""}
              {asOf && ` · last trade ${relativeTime(asOf)}`}
              {marketState === "open" && " · auto-refreshing"}
            </p>
          )}
        </div>

        {syncError && <p className="border border-line bg-canvas px-3 py-2 font-mono text-2xs text-muted">{syncError}</p>}

        {loading && holdings.length === 0 ? (
          <div className="h-40 animate-pulse bg-subtle" aria-hidden="true" />
        ) : holdings.length === 0 ? (
          <section className="flex flex-col items-center justify-center border border-dashed border-line-strong px-6 py-16 text-center" data-testid="portfolio-empty">
            <Briefcase className="mb-3 h-8 w-8 text-muted" aria-hidden="true" />
            <h2 className="text-base font-bold">Add your portfolio</h2>
            <p className="mt-1 max-w-md font-mono text-xs text-muted">
              Tell us which NSE stocks you own and how many shares. Your dashboard then shows live prices, P&amp;L,
              weather at company locations and real-time news, and the agents analyze your holdings.
            </p>
            <Button variant="primary" className="mt-5" onClick={openEditor}>
              Add holdings
            </Button>
          </section>
        ) : (
          <>
            <PortfolioSummary totals={totals} holdings={holdings.length} loading={!quotes.data && !quotes.error} />
            {quotes.error && !quotes.data && (
              <p className="font-mono text-2xs text-loss">Live prices are unavailable right now. Retrying automatically.</p>
            )}
            <HoldingsTable rows={rows} selected={selected} onSelect={setSelected} loading={!quotes.data} />
            <div className="grid gap-5 lg:grid-cols-2">
              <PerformanceChart data={performance.data} range={range} onRange={setRange} error={performance.error} />
              {selectedHolding ? (
                <AssetLiveChart
                  key={selectedHolding.symbol}
                  asset={{ symbol: selectedHolding.symbol, name: selectedHolding.name, exchange: "NSE" }}
                />
              ) : (
                <div className="h-56 animate-pulse bg-subtle" aria-hidden="true" />
              )}
            </div>
            <div className="grid gap-5 lg:grid-cols-2">
              <WeatherPanel data={weather.data} error={weather.error} />
              <PortfolioNews items={news.data} error={news.error} symbols={holdings.map((h) => h.symbol)} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border border-line bg-canvas px-4 py-3">
              <p className="text-xs text-ink-soft">Ask the agents how news, weather or macro events affect these holdings.</p>
              <Link href="/chat" className="bg-ink px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white hover:bg-ink-soft">
                Open terminal →
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
