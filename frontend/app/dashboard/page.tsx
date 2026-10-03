"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import StopLossLogo from "@/components/StopLossLogo";
import ProtectedRoute from "@/components/ProtectedRoute";
import { fetchUserProfile, UserProfile } from "@/lib/userProfile";

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);

  // Load Profile from Firestore / Local Storage Cache
  useEffect(() => {
    if (user) {
      fetchUserProfile(user.uid || user.email).then((p) => setProfile(p));
    }
  }, [user]);

  const displayName = profile?.fullName || user?.displayName || user?.email?.split("@")[0] || "Analyst";

  return (
    <div className="min-h-screen bg-white text-gray-900 font-sans flex flex-col justify-between">
      {/* Top Navigation */}
      <header className="w-full border-b border-gray-200 bg-white px-6 py-4 flex justify-between items-center">
        <Link href="/" className="flex items-center text-gray-900">
          <StopLossLogo height={30} />
        </Link>
        <div className="flex items-center space-x-4">
          <Link
            href="/chat"
            className="bg-black text-white px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider hover:bg-gray-800 transition-colors rounded-none"
          >
            TERMINAL
          </Link>
          <Link
            href="/onboarding"
            className="text-xs font-semibold uppercase tracking-wider text-gray-600 hover:text-black transition-colors px-2 py-1"
          >
            EDIT PROFILE
          </Link>
          <button
            onClick={async () => {
              await logout();
              router.push("/login");
            }}
            className="bg-white text-gray-900 px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider border border-gray-300 hover:border-black transition-colors rounded-none"
          >
            SIGN OUT
          </button>
        </div>
      </header>

      {/* Main Dashboard Body */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 md:p-10 space-y-8">
        
        {/* Welcome & Profile Summary Section */}
        <div className="border border-gray-200 bg-[#FAFAFA] p-6 md:p-8">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 pb-6 border-b border-gray-200">
            {/* Identity */}
            <div className="flex items-start space-x-4">
              <div className="w-14 h-14 bg-black text-white flex items-center justify-center text-xl font-mono font-bold uppercase flex-shrink-0">
                {displayName.charAt(0)}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">
                    {displayName}
                  </h1>
                </div>
                <p className="text-xs text-gray-600 font-mono mt-1">
                  {profile?.role || "Quant Risk Analyst"} &middot;{" "}
                  <span className="text-gray-900 font-semibold">{profile?.organization || "Independent Firm"}</span>
                </p>
                <p className="text-xs text-gray-400 font-mono mt-0.5">
                  {user?.email} &middot; {profile?.location || "Global Desk"}
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center space-x-3 flex-shrink-0">
              <Link
                href="/onboarding"
                className="border border-gray-300 bg-white text-gray-800 px-4 py-2 text-xs font-mono uppercase tracking-wider hover:border-black transition-colors"
              >
                Edit Onboarding
              </Link>
              <Link
                href="/chat"
                className="bg-black text-white px-5 py-2 text-xs font-mono uppercase tracking-wider hover:bg-gray-800 transition-colors flex items-center space-x-2"
              >
                <span>Launch Chat</span>
                <span>&rarr;</span>
              </Link>
            </div>
          </div>

          {/* Profile Details Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6">
            {/* Professional Role */}
            <div>
              <span className="text-[10px] font-mono font-semibold uppercase tracking-widest text-gray-400 block mb-2">
                Analyst Role &amp; Desk
              </span>
              <div className="space-y-1 font-mono text-xs">
                <p className="text-gray-700">
                  Role: <span className="font-bold text-gray-900">{profile?.role || "Analyst"}</span>
                </p>
                <p className="text-gray-700">
                  Organization: <span className="font-bold text-gray-900">{profile?.organization || "Independent"}</span>
                </p>
              </div>
            </div>

            {/* Geographic Coverage */}
            <div>
              <span className="text-[10px] font-mono font-semibold uppercase tracking-widest text-gray-400 block mb-2">
                Geographic Coverage
              </span>
              <div className="space-y-1 font-mono text-xs">
                <p className="text-gray-700">
                  Primary Region: <span className="font-bold text-gray-900">{profile?.location || "Global"}</span>
                </p>
              </div>
            </div>

            {/* System Status */}
            <div>
              <span className="text-[10px] font-mono font-semibold uppercase tracking-widest text-gray-400 block mb-2">
                Terminal Sync Status
              </span>
              <div className="space-y-1 font-mono text-xs">
                <p className="text-gray-700 flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-green-500 inline-block animate-pulse"></span>
                  <span>Agent Graph: <strong className="text-gray-900">READY</strong></span>
                </p>
                <p className="text-gray-700">
                  Last Updated: <span className="text-gray-500">{profile?.updatedAt ? new Date(profile.updatedAt).toLocaleDateString() : "Today"}</span>
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Intelligence Feeds Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Quant Risk */}
          <div className="border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-mono uppercase tracking-wider text-gray-400">AGENT // 01</span>
              <span className="text-[10px] font-mono bg-gray-100 text-gray-700 px-2 py-0.5 uppercase">VAR MODEL</span>
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-1">Quant Risk Engine</h3>
            <p className="text-xs text-gray-500 font-mono mb-4">
              Value-at-Risk calculations, stress test scenario drawdowns, and portfolio sensitivity matrices.
            </p>
            <div className="border-t border-gray-100 pt-3 flex justify-between items-center text-xs font-mono">
              <span className="text-gray-400">STATUS</span>
              <span className="text-black font-semibold uppercase">95% Confidence Active</span>
            </div>
          </div>

          {/* Card 2: Weather & Macro */}
          <div className="border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-mono uppercase tracking-wider text-gray-400">AGENT // 02</span>
              <span className="text-[10px] font-mono bg-gray-100 text-gray-700 px-2 py-0.5 uppercase">TELEMETRY</span>
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-1">Weather &amp; Macro Impact</h3>
            <p className="text-xs text-gray-500 font-mono mb-4">
              Gulf Coast refinery storm tracking, freeze telemetry, and energy infrastructure disruption shocks.
            </p>
            <div className="border-t border-gray-100 pt-3 flex justify-between items-center text-xs font-mono">
              <span className="text-gray-400">FEEDS</span>
              <span className="text-black font-semibold uppercase">Open-Meteo &amp; FRED</span>
            </div>
          </div>

          {/* Card 3: Sentiment & Hedging */}
          <div className="border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-mono uppercase tracking-wider text-gray-400">AGENT // 03</span>
              <span className="text-[10px] font-mono bg-gray-100 text-gray-700 px-2 py-0.5 uppercase">HEDGING</span>
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-1">Sentiment &amp; Hedging</h3>
            <p className="text-xs text-gray-500 font-mono mb-4">
              GDELT news extraction, trade tariff tone modeling, and evidence-backed collar &amp; futures strategies.
            </p>
            <div className="border-t border-gray-100 pt-3 flex justify-between items-center text-xs font-mono">
              <span className="text-gray-400">STRATEGY</span>
              <span className="text-black font-semibold uppercase">Index Puts &amp; Collars</span>
            </div>
          </div>
        </div>

      </main>

      {/* Footer */}
      <footer className="w-full border-t border-gray-200 py-4 text-center text-xs text-gray-500 font-mono">
        Built by SairajTripathy-0077 — StopLoss Intelligence Terminal
      </footer>
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
