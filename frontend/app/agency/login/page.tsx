"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function AgencyLoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const r = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
        credentials: "include",
      });
      if (!r.ok) {
        const data = await r.json();
        setError(typeof data.detail === "string" ? data.detail : "Invalid email or password");
        return;
      }
      const data = await r.json();
      if (data.role === "client") {
        setError("This is a client account. Please use Client Login.");
        return;
      }
      router.push("/agency/dashboard");
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="text-2xl font-bold">
            <span className="text-white">FRAME</span>
            <span className="text-purple-400">OPS</span>
          </Link>
          <h1 className="text-white text-2xl font-semibold mt-4">Agency Sign In</h1>
          <p className="text-gray-400 text-sm mt-1">Sign in to your agency workspace</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-2xl p-8 space-y-4">
          {error && (
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-3 text-red-300 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-gray-300 text-sm font-medium mb-1">Email</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-purple-500"
              placeholder="owner@agency.com"
            />
          </div>

          <div>
            <label className="block text-gray-300 text-sm font-medium mb-1">Password</label>
            <input
              type="password"
              required
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-purple-500"
              placeholder="Your password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white font-medium text-sm transition-colors"
          >
            {loading ? "Signing in…" : "Sign In to Workspace"}
          </button>
        </form>

        <p className="text-center text-gray-500 text-sm mt-4">
          Need to register your agency?{" "}
          <Link href="/agency/register" className="text-purple-400 hover:text-purple-300">
            Create an agency workspace
          </Link>
        </p>
        <p className="text-center text-gray-600 text-xs mt-2">
          Looking for client login?{" "}
          <Link href="/client/login" className="text-blue-400 hover:text-blue-300">
            Client sign in →
          </Link>
        </p>
      </div>
    </div>
  );
}
