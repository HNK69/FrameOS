"use client";
import Link from "next/link";
import { useState, useEffect } from "react";

export default function LandingPage() {
  const [authStatus, setAuthStatus] = useState<{ setup_required: boolean } | null>(null);

  useEffect(() => {
    fetch("/api/auth/status")
      .then((r) => r.json())
      .then(setAuthStatus)
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Nav */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold tracking-tight text-white">FRAME</span>
          <span className="text-2xl font-bold tracking-tight text-blue-400">OPS</span>
        </div>
        <div className="flex gap-3">
          <Link
            href="/client/login"
            className="px-4 py-2 text-sm text-gray-300 hover:text-white transition-colors"
          >
            Client Login
          </Link>
          <Link
            href="/agency/login"
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors font-medium"
          >
            Agency Login
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-20 text-center">
        <div className="max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 bg-blue-900/40 border border-blue-700/50 rounded-full px-4 py-1.5 text-blue-300 text-sm mb-8">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            Remember Every Client. Perfect Every Project.
          </div>

          <h1 className="text-5xl sm:text-6xl font-bold mb-6 leading-tight">
            The operating system for{" "}
            <span className="text-blue-400">video production</span>
          </h1>

          <p className="text-gray-400 text-xl mb-12 max-w-2xl mx-auto">
            Connect clients with video-editing agencies. Submit project briefs, track
            production, review deliverables — with AI-powered memory that makes every
            project better than the last.
          </p>

          {/* Two entry points */}
          <div className="grid sm:grid-cols-2 gap-6 max-w-2xl mx-auto">
            {/* Client card */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-left hover:border-blue-700/60 transition-colors group">
              <div className="w-12 h-12 rounded-xl bg-blue-900/50 flex items-center justify-center mb-4 text-2xl">
                🎬
              </div>
              <h2 className="text-xl font-semibold mb-2">I&apos;m a Client</h2>
              <p className="text-gray-400 text-sm mb-6">
                Discover agencies, submit project briefs, track production and
                review deliverables — all in one place.
              </p>
              <div className="flex flex-col gap-2">
                <Link
                  href="/client/register"
                  className="w-full text-center py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
                >
                  Get Started Free
                </Link>
                <Link
                  href="/client/login"
                  className="w-full text-center py-2.5 text-gray-400 hover:text-white text-sm transition-colors"
                >
                  Sign In
                </Link>
              </div>
            </div>

            {/* Agency card */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-left hover:border-purple-700/60 transition-colors group">
              <div className="w-12 h-12 rounded-xl bg-purple-900/50 flex items-center justify-center mb-4 text-2xl">
                ✂️
              </div>
              <h2 className="text-xl font-semibold mb-2">I&apos;m an Agency</h2>
              <p className="text-gray-400 text-sm mb-6">
                Build your profile, receive project requests, manage production
                workflows and deliver with AI-powered client memory.
              </p>
              <div className="flex flex-col gap-2">
                <Link
                  href="/agency/register"
                  className="w-full text-center py-2.5 bg-purple-600 hover:bg-purple-500 rounded-lg text-sm font-medium transition-colors"
                >
                  List Your Agency
                </Link>
                <Link
                  href="/agency/login"
                  className="w-full text-center py-2.5 text-gray-400 hover:text-white text-sm transition-colors"
                >
                  Sign In
                </Link>
              </div>
            </div>
          </div>

          {authStatus?.setup_required && (
            <div className="mt-8 p-4 bg-amber-900/30 border border-amber-700/50 rounded-lg text-amber-300 text-sm max-w-md mx-auto">
              First-time setup required.{" "}
              <Link href="/setup" className="underline font-medium hover:text-amber-200">
                Create the workspace owner account →
              </Link>
            </div>
          )}
        </div>
      </main>

      {/* Features strip */}
      <section className="border-t border-gray-800 py-12 px-6">
        <div className="max-w-4xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-8 text-center">
          {[
            { icon: "🤖", label: "AI Feedback Extraction" },
            { icon: "🧠", label: "Adaptive Client Memory" },
            { icon: "📋", label: "Structured Briefs" },
            { icon: "🎯", label: "Task Synthesis" },
          ].map(({ icon, label }) => (
            <div key={label} className="flex flex-col items-center gap-2">
              <span className="text-3xl">{icon}</span>
              <span className="text-gray-400 text-sm">{label}</span>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-gray-800 py-6 text-center text-gray-600 text-sm">
        © {new Date().getFullYear()} FRAMEOPS — Video Production Operations Platform
      </footer>
    </div>
  );
}
