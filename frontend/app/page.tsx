"use client";

import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

export default function EntryPage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen flex flex-col justify-between bg-white text-gray-900 font-sans border-t-2 border-black">
      {/* Top Header Bar */}
      <header className="w-full border-b border-gray-200 px-6 py-4 max-w-6xl mx-auto flex justify-between items-center">
        <div className="flex items-center space-x-3">
          <span className="w-2.5 h-2.5 bg-black inline-block"></span>
          <span className="font-semibold text-sm tracking-tight text-gray-900 uppercase">
            StopLoss Terminal
          </span>
        </div>
        <nav className="flex items-center space-x-6 text-sm">
          {user ? (
            <Link
              href="/dashboard"
              className="font-medium text-gray-900 hover:text-gray-600 transition-colors"
            >
              Dashboard &rarr;
            </Link>
          ) : (
            <Link
              href="/login"
              className="bg-black text-white px-4 py-2 text-xs font-semibold uppercase tracking-wider hover:bg-gray-800 transition-colors"
            >
              Log In
            </Link>
          )}
        </nav>
      </header>

      {/* Hero Section */}
      <main className="flex-1 flex flex-col justify-center items-center px-6 py-24 text-center max-w-4xl mx-auto">
        <div className="mb-6 inline-flex items-center space-x-2 border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-700 font-mono">
          <span>STATUS: ONLINE</span>
          <span className="text-gray-400">|</span>
          <span>LATENCY: 14MS</span>
        </div>

        <h1 className="text-4xl md:text-6xl font-bold tracking-tight text-gray-900 mb-6">
          Financial Intelligence Terminal
        </h1>

        <p className="text-lg md:text-xl text-gray-600 max-w-2xl mb-10 leading-relaxed font-normal">
          Analyze real-time market data and macro impacts.
        </p>

        <div className="flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-4">
          <Link
            href={user ? "/dashboard" : "/login"}
            className="w-full sm:w-auto bg-black text-white px-8 py-3.5 text-sm font-semibold uppercase tracking-wider border border-black hover:bg-gray-900 transition-colors shadow-none rounded-none"
          >
            {user ? "Access Terminal" : "Log In"}
          </Link>
          <a
            href="#features"
            className="w-full sm:w-auto bg-white text-gray-900 px-8 py-3.5 text-sm font-semibold uppercase tracking-wider border border-gray-300 hover:border-black transition-colors rounded-none"
          >
            Documentation
          </a>
        </div>

        {/* Utilitarian Feature Highlights */}
        <section id="features" className="w-full grid grid-cols-1 md:grid-cols-3 gap-6 mt-24 text-left">
          <div className="p-6 border border-gray-200 bg-white">
            <h3 className="font-mono text-xs uppercase tracking-wider text-gray-500 mb-2">
              01 // MACRO DATA
            </h3>
            <p className="font-semibold text-gray-900 text-base mb-1">
              Weather & Macro Impacts
            </p>
            <p className="text-sm text-gray-600 leading-normal">
              Correlate NOAA climate events directly with Gulf Coast commodity price shocks.
            </p>
          </div>

          <div className="p-6 border border-gray-200 bg-white">
            <h3 className="font-mono text-xs uppercase tracking-wider text-gray-500 mb-2">
              02 // RAG ENGINE
            </h3>
            <p className="font-semibold text-gray-900 text-base mb-1">
              Vector Intelligence
            </p>
            <p className="text-sm text-gray-600 leading-normal">
              Sub-second retrieval augmented generation on historical financial risk events.
            </p>
          </div>

          <div className="p-6 border border-gray-200 bg-white">
            <h3 className="font-mono text-xs uppercase tracking-wider text-gray-500 mb-2">
              03 // RISK MODELING
            </h3>
            <p className="font-semibold text-gray-900 text-base mb-1">
              Value-at-Risk Engine
            </p>
            <p className="text-sm text-gray-600 leading-normal">
              Quantitative portfolio stress testing and actionable hedging strategies.
            </p>
          </div>
        </section>
      </main>

      {/* Discreet Footer */}
      <footer className="w-full border-t border-gray-200 py-6 text-center text-xs text-gray-500 font-mono">
        Built by SairajTripathy-0077 — Logic-Driven Creator
      </footer>
    </div>
  );
}
