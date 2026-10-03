"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useAuth } from "@/context/AuthContext";
import NewsSection from "@/components/NewsSection";
import GlobalInflationMap from "@/components/GlobalInflationMap";

const FaultyTerminal = dynamic(() => import("@/components/FaultyTerminal"), {
  ssr: false,
});

export default function EntryPage() {
  const { user, logout } = useAuth();

  return (
    <div className="bg-white text-gray-950 font-sans relative border-t-2 border-black">
      {/* Full-Screen Interactive WebGL Light-Mode Background */}
      <div className="fixed inset-0 w-full h-full z-0 pointer-events-none opacity-30">
        <FaultyTerminal
          lightMode={true}
          tint="#ffffff"
          scale={2.0}
          gridMul={[2, 1]}
          digitSize={1.0}
          timeScale={0.3}
          mouseReact={true}
          mouseStrength={0.4}
          scanlineIntensity={0.08}
          glitchAmount={0.8}
          flickerAmount={0.8}
          noiseAmp={0.8}
          curvature={0}
          pageLoadAnimation={true}
          brightness={0.8}
        />
      </div>

      {/* Sticky Hero Full Viewport Container */}
      <div className="sticky top-0 h-screen w-full flex flex-col justify-between z-10 overflow-hidden">
        {/* Top Header Bar */}
        <header className="w-full border-b border-gray-200 bg-white/90 backdrop-blur-sm px-6 py-4 max-w-6xl mx-auto flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <span className="w-2.5 h-2.5 bg-black inline-block"></span>
            <span className="font-semibold text-sm tracking-tight text-gray-900 uppercase">
              StopLoss
            </span>
          </div>
          <nav className="flex items-center space-x-4 text-sm">
            {user ? (
              <>
                <Link
                  href="/dashboard"
                  className="bg-black text-white px-4 py-2 text-xs font-semibold uppercase tracking-wider hover:bg-gray-800 transition-colors"
                >
                  Dashboard &rarr;
                </Link>
                <button
                  onClick={() => logout()}
                  className="bg-white text-gray-900 px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider border border-gray-300 hover:border-black transition-colors rounded-none"
                >
                  Sign Out
                </button>
              </>
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

        {/* Clean Unboxed Hero Section */}
        <main className="flex-1 flex flex-col justify-center items-center px-6 py-8 text-center max-w-4xl mx-auto">
          <h1 className="text-4xl md:text-6xl font-black tracking-tight text-gray-950 mb-6 leading-tight">
            Financial Intelligence Terminal
          </h1>

          <p className="text-lg md:text-xl text-gray-900 font-semibold max-w-2xl mb-10 leading-relaxed">
            Analyze real-time market data and macro impacts.
          </p>

          <div className="flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-4">
            <Link
              href={user ? "/dashboard" : "/login"}
              className="w-full sm:w-auto bg-black text-white px-8 py-3.5 text-xs font-semibold uppercase tracking-wider border border-black hover:bg-gray-800 transition-colors shadow-none rounded-none"
            >
              {user ? "Access Terminal" : "Log In"}
            </Link>
            <a
              href="#intelligence-feed"
              className="w-full sm:w-auto bg-white text-gray-900 px-8 py-3.5 text-xs font-semibold uppercase tracking-wider border border-gray-300 hover:border-black transition-colors rounded-none"
            >
              Documentation
            </a>
          </div>
        </main>

        {/* Scroll Down Indicator */}
        <div className="pb-8 text-center">
          <a
            href="#intelligence-feed"
            className="inline-flex items-center space-x-2 text-xs font-mono text-gray-600 hover:text-black transition-colors uppercase tracking-widest"
          >
            <span>SCROLL FOR INTELLIGENCE FEED</span>
            <span className="animate-bounce">&darr;</span>
          </a>
        </div>
      </div>

      {/* Overlapping Next Section (Scrolls Upwards over sticky hero) */}
      <div className="relative z-20 bg-[#FAFAFA] border-t border-[#EAEAEA] shadow-[0_-12px_40px_rgba(0,0,0,0.06)]">
        {/* GSAP Animated Financial News Section */}
        <NewsSection />

        {/* Interactive Economy & Global Inflation Map Section */}
        <GlobalInflationMap />

        {/* Discreet Footer */}
        <footer className="w-full border-t border-gray-200 bg-white py-6 text-center text-xs text-gray-600 font-mono">
          Built by SairajTripathy-0077 — Logic-Driven Creator
        </footer>
      </div>
    </div>
  );
}
