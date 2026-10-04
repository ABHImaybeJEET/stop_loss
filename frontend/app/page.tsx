"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useAuth } from "@/context/AuthContext";
import NewsSection from "@/components/NewsSection";
import GlobalInflationMap from "@/components/GlobalInflationMap";
import StopLossLogo from "@/components/StopLossLogo";
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
        <header className="w-full border-b border-gray-200 bg-white/90 backdrop-blur-sm px-6 py-4 max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <Link href="/" className="flex items-center text-gray-900">
              <StopLossLogo height={32} />
            </Link>
          </div>
          <nav className="flex items-center space-x-4 text-sm tracking-[-0.02em]">
            {user ? (
              <>
                <Link
                  href="/chat"
                  className="bg-black text-white px-4 py-2 text-xs font-semibold uppercase tracking-wider hover:bg-gray-800 transition-colors"
                >
                  Terminal &rarr;
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

        {/* Editorial landing hero */}
        <main className="flex-1 flex flex-col justify-center items-start px-7 py-10 sm:px-12 lg:px-16 text-left w-full max-w-7xl mx-auto">
          <p className="mb-6 text-[11px] font-semibold uppercase tracking-[0.19em] text-[#456d53]">
            Independent market intelligence <span className="px-2 text-[#a6a496]">/</span> India
          </p>
          <h1 className="font-editorial max-w-5xl text-[3.3rem] leading-[0.96] tracking-[-0.055em] text-[#20241f] sm:text-7xl lg:text-[6.5rem]">
            Read the market.<br /><span className="text-[#397456]">See what moves it.</span>
          </h1>

          <p className="mt-7 max-w-xl text-base font-normal leading-7 text-[#60635d] sm:text-lg sm:leading-8">
            Follow NSE stocks, breaking news and the wider forces shaping risk.
          </p>

          <div className="mt-9 flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:gap-4">
            <Link
              href={user ? "/chat" : "/login"}
              className="w-full rounded-full border border-[#263b2e] bg-[#263b2e] px-7 py-3.5 text-xs font-semibold tracking-wide text-white shadow-sm transition hover:border-[#17271e] hover:bg-[#17271e] sm:w-auto"
            >
              {user ? "Access Terminal" : "Log In"}
            </Link>
            <a
              href="#intelligence-feed"
              className="w-full rounded-full border border-gray-300 bg-white px-7 py-3.5 text-xs font-semibold tracking-wide text-gray-900 transition hover:border-[#263b2e] sm:w-auto"
            >
              Explore the briefing
            </a>
          </div>
        </main>

        {/* Scroll Down Indicator */}
        <div className="pb-8 text-center">
          <a
            href="#intelligence-feed"
              className="inline-flex items-center space-x-2 text-[10px] font-mono text-gray-600 hover:text-black transition-colors uppercase tracking-[0.15em]"
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
        <footer className="w-full border-t border-gray-200 bg-white py-6 text-center text-xs text-gray-600 font-mono tracking-widest uppercase">
          MADE BY CATGPT
        </footer>
      </div>
    </div>
  );
}
