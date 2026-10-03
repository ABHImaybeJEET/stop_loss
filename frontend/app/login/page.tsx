"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import StopLossLogo from "@/components/StopLossLogo";

import { hasCompletedOnboarding } from "@/lib/userProfile";

export default function LoginPage() {
  const { user, loading, signInWithEmail, signUpWithEmail, signInWithGoogle } = useAuth();
  const router = useRouter();

  const [isSignUp, setIsSignUp] = useState<boolean>(false);
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Redirect if user is already authenticated
  useEffect(() => {
    if (!loading && user) {
      if (!hasCompletedOnboarding(user.uid || user.email)) {
        router.push("/onboarding");
      } else {
        router.push("/dashboard");
      }
    }
  }, [user, loading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Please fill in all required fields.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    if (isSignUp) {
      if (!confirmPassword) {
        setError("Please confirm your password.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
    }

    setSubmitting(true);
    try {
      if (isSignUp) {
        await signUpWithEmail(email, password);
        router.push("/onboarding");
      } else {
        await signInWithEmail(email, password);
        if (!hasCompletedOnboarding(email)) {
          router.push("/onboarding");
        } else {
          router.push("/dashboard");
        }
      }
    } catch (err: any) {
      console.error("Auth error:", err);
      let msg = err?.message || "Authentication failed. Please check your credentials.";
      if (err?.code === "auth/configuration-not-found") {
        msg = "Firebase Authentication is not enabled for this project. Please go to Firebase Console -> Authentication -> Sign-in method and enable 'Email/Password' and 'Google'.";
      } else if (err?.code === "auth/invalid-credential" || err?.code === "auth/user-not-found") {
        msg = "Invalid email or password.";
      } else if (err?.code === "auth/email-already-in-use") {
        msg = "An account with this email already exists.";
      }
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await signInWithGoogle();
      router.push("/onboarding");
    } catch (err: any) {
      console.error("Google Auth error:", err);
      let msg = err?.message || "Google sign-in failed. Please try again.";
      if (err?.code === "auth/configuration-not-found") {
        msg = "Google Sign-In is not enabled for this Firebase project. Please enable Google under Firebase Console -> Authentication -> Sign-in method.";
      }
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center font-mono text-xs text-gray-500">
        INITIALIZING AUTH SESSION...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-between font-sans">
      {/* Top Header */}
      <header className="w-full bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
        <Link href="/" className="flex items-center text-gray-900">
          <StopLossLogo height={30} />
        </Link>
        <Link href="/" className="text-xs font-mono text-gray-500 hover:text-gray-900">
          &larr; BACK TO HOME
        </Link>
      </header>

      {/* Main Centered Login Card */}
      <main className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white border border-gray-200 p-8 shadow-none">
          {/* Card Header */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold tracking-tight text-gray-900">
              {isSignUp ? "Create Account" : "Terminal Login"}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              {isSignUp
                ? "Enter your credentials to register a new terminal account."
                : "Authenticate to access the Financial Intelligence Terminal."}
            </p>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mb-6 p-3 bg-red-50 border border-red-200 text-red-700 text-xs font-mono">
              [ERROR] {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@firm.com"
                required
                className="w-full border border-gray-300 rounded-none px-3.5 py-2.5 text-sm text-gray-900 placeholder-gray-400 bg-white focus:outline-none focus:border-black transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full border border-gray-300 rounded-none px-3.5 py-2.5 text-sm text-gray-900 placeholder-gray-400 bg-white focus:outline-none focus:border-black transition-colors"
              />
            </div>

            {/* Confirm Password field when creating an account */}
            {isSignUp && (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1.5">
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  required={isSignUp}
                  className="w-full border border-gray-300 rounded-none px-3.5 py-2.5 text-sm text-gray-900 placeholder-gray-400 bg-white focus:outline-none focus:border-black transition-colors"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-black text-white py-3 text-xs font-semibold uppercase tracking-wider border border-black hover:bg-gray-800 transition-colors disabled:opacity-50 rounded-none mt-2"
            >
              {submitting
                ? "PROCESSING..."
                : isSignUp
                ? "CREATE ACCOUNT"
                : "SIGN IN WITH EMAIL"}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6 text-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200"></div>
            </div>
            <span className="relative bg-white px-3 text-xs font-mono text-gray-400 uppercase">
              OR
            </span>
          </div>

          {/* Google Sign In Button */}
          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={submitting}
            className="w-full bg-white text-gray-900 py-3 text-xs font-semibold uppercase tracking-wider border border-gray-300 hover:border-black transition-colors flex items-center justify-center space-x-2 rounded-none"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            <span>SIGN IN WITH GOOGLE</span>
          </button>

          {/* Toggle Login / Sign Up */}
          <div className="mt-6 pt-4 border-t border-gray-100 text-center">
            <button
              type="button"
              onClick={() => {
                setIsSignUp(!isSignUp);
                setConfirmPassword("");
                setError(null);
              }}
              className="text-xs text-gray-600 hover:text-black font-mono underline uppercase"
            >
              {isSignUp
                ? "Already have an account? Sign In"
                : "Don't have an account? Sign Up"}
            </button>
          </div>
        </div>
      </main>

      {/* Discreet Footer */}
      <footer className="w-full bg-white border-t border-gray-200 py-4 text-center text-xs text-gray-500 font-mono">
        Built by SairajTripathy-0077 — Logic-Driven Creator
      </footer>
    </div>
  );
}
