"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

export default function DashboardPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  // Route Protection: Redirect to /login if unauthenticated
  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center font-mono text-xs text-gray-500">
        AUTHENTICATING TERMINAL SESSION...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white text-gray-900 font-sans flex flex-col justify-between">
      {/* Top Navigation */}
      <header className="w-full border-b border-gray-200 bg-white px-6 py-4 flex justify-between items-center">
        <Link href="/" className="flex items-center space-x-2 text-sm font-semibold text-gray-900">
          <span className="w-2.5 h-2.5 bg-black inline-block"></span>
          <span className="uppercase tracking-tight">StopLoss Terminal</span>
        </Link>
        <div className="flex items-center space-x-6">
          <span className="text-xs font-mono text-gray-600">
            USER: <span className="font-semibold text-gray-900">{user.email || user.uid}</span>
          </span>
          <button
            onClick={async () => {
              await logout();
              router.push("/login");
            }}
            className="bg-white text-gray-900 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider border border-gray-300 hover:border-black transition-colors rounded-none"
          >
            SIGN OUT
          </button>
        </div>
      </header>

      {/* Main Terminal Body */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 md:p-10">

        {/* Coming Soon Stark Container */}
        <div className="border border-gray-200 bg-white p-12 text-center flex flex-col items-center justify-center my-12">
          <div className="mb-4 inline-block bg-gray-100 border border-gray-200 px-3 py-1 font-mono text-xs uppercase tracking-widest text-gray-600">
            SYSTEM STATUS // DEVELOPMENT IN PROGRESS
          </div>
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-gray-900 uppercase mb-4">
            Coming Soon
          </h2>
          <p className="text-sm text-gray-500 font-mono max-w-md">
            The full interactive terminal capabilities (macro impact charts, hurricane overlays, and risk engine) will be available here shortly.
          </p>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-gray-200 py-4 text-center text-xs text-gray-500 font-mono">
        Built by SairajTripathy-0077 — Logic-Driven Creator
      </footer>
    </div>
  );
}
