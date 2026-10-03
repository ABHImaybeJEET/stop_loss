"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center font-mono text-xs text-gray-500">
        <div className="flex items-center space-x-3 bg-white border border-gray-200 px-5 py-3 shadow-xs">
          <span className="w-2 h-2 rounded-full bg-black animate-ping" />
          <span>AUTHENTICATING TERMINAL SESSION...</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
