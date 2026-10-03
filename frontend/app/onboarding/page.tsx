"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import StopLossLogo from "@/components/StopLossLogo";
import ProtectedRoute from "@/components/ProtectedRoute";
import { fetchUserProfile, saveUserProfile, UserProfile } from "@/lib/userProfile";

function OnboardingContent() {
  const { user } = useAuth();
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("Analyst");
  const [organization, setOrganization] = useState("Independent");
  const [location, setLocation] = useState("Global");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) {
      fetchUserProfile(user.uid || user.email).then((existing) => {
        setFullName(existing.fullName || user.displayName || user.email?.split("@")[0] || "");
        if (existing.role) setRole(existing.role);
        if (existing.organization) setOrganization(existing.organization);
        if (existing.location) setLocation(existing.location);
      });
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    const profile: UserProfile = {
      fullName: fullName.trim() || user?.email?.split("@")[0] || "Analyst",
      role,
      organization,
      location,
      updatedAt: new Date().toISOString(),
    };

    await saveUserProfile(profile, user?.uid || user?.email);
    router.push("/chat");
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-between font-sans">
      {/* Top Header */}
      <header className="w-full bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
        <Link href="/" className="flex items-center text-gray-900">
          <StopLossLogo height={30} />
        </Link>
        <div className="flex items-center space-x-3">
          <span className="text-xs font-mono text-gray-400">SESSION: {user?.email}</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-3xl w-full mx-auto p-6 md:py-10">
        <div className="bg-white border border-gray-200 p-8 shadow-none">
          {/* Header Banner */}
          <div className="border-b border-gray-200 pb-6 mb-8">
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-gray-900 uppercase">
              Configure Analyst Profile
            </h1>
            <p className="text-xs md:text-sm text-gray-500 font-mono mt-1">
              Personalize your intelligence terminal parameters and risk mandate. These details will configure your active Dashboard.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Section 1: Identity & Organization */}
            <div>
              <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-gray-400 mb-4 pb-1 border-b border-gray-100">
                01. Identity &amp; Organization
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1.5">
                    Full Name
                  </label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Sairaj Tripathy"
                    className="w-full px-3 py-2 text-sm border border-gray-300 focus:border-black focus:outline-none font-sans text-gray-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1.5">
                    Role
                  </label>
                  <input
                    type="text"
                    required
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    placeholder="e.g. Analyst"
                    className="w-full px-3 py-2 text-sm border border-gray-300 focus:border-black focus:outline-none font-sans text-gray-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1.5">
                    Organization
                  </label>
                  <select
                    value={organization}
                    onChange={(e) => setOrganization(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 focus:border-black focus:outline-none bg-white text-gray-900"
                  >
                    <option value="Independent">Independent</option>
                    <option value="Company">Company</option>
                    <option value="Hedge Fund">Hedge Fund</option>
                    <option value="Investment Bank">Investment Bank</option>
                    <option value="Asset Manager">Asset Manager</option>
                    <option value="Prop Firm">Prop Firm</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1.5">
                    Region
                  </label>
                  <select
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 focus:border-black focus:outline-none bg-white text-gray-900"
                  >
                    <option value="Global">Global</option>
                    <option value="India">India</option>
                    <option value="USA">USA</option>
                    <option value="Europe">Europe</option>
                    <option value="Asia-Pacific">Asia-Pacific</option>
                    <option value="Middle East">Middle East</option>
                    <option value="Latin America">Latin America</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="pt-4 border-t border-gray-200 flex flex-col sm:flex-row items-center justify-between gap-4">
              <button
                type="button"
                onClick={() => router.push("/chat")}
                className="text-xs font-mono text-gray-500 hover:text-black uppercase tracking-wider"
              >
                Skip for now &rarr;
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="w-full sm:w-auto bg-black text-white px-8 py-3 text-xs font-semibold uppercase tracking-wider hover:bg-gray-800 transition-colors disabled:opacity-50"
              >
                {submitting ? "Saving Profile..." : "Complete Onboarding & Save Profile"}
              </button>
            </div>
          </form>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-gray-200 py-4 text-center text-xs text-gray-500 font-mono">
        StopLoss Terminal — Financial Intelligence System
      </footer>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <ProtectedRoute>
      <OnboardingContent />
    </ProtectedRoute>
  );
}
