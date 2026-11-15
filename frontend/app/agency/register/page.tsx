"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function AgencyRegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    agency_name: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const r = await fetch("/api/auth/register/agency", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
        credentials: "include",
      });
      if (!r.ok) {
        const data = await r.json();
        setError(typeof data.detail === "string" ? data.detail : "Registration failed");
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
          <h1 className="text-white text-2xl font-semibold mt-4">Register your agency</h1>
          <p className="text-gray-400 text-sm mt-1">
            Build your profile, get discovered, and streamline client production
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-2xl p-8 space-y-4">
          {error && (
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-3 text-red-300 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-gray-300 text-sm font-medium mb-1">Agency Name</label>
            <input
              type="text"
              required
              minLength={2}
              value={form.agency_name}
              onChange={(e) => setForm((f) => ({ ...f, agency_name: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-purple-500"
              placeholder="e.g. Apex Visuals Studio"
            />
          </div>

          <div>
            <label className="block text-gray-300 text-sm font-medium mb-1">Your Full Name</label>
            <input
              type="text"
              required
              value={form.full_name}
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-purple-500"
              placeholder="Agency Owner name"
            />
          </div>

          <div>
            <label className="block text-gray-300 text-sm font-medium mb-1">Work Email</label>
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
              minLength={8}
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-purple-500"
              placeholder="At least 8 characters"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white font-medium text-sm transition-colors"
          >
            {loading ? "Registering…" : "Register Agency Workspace"}
          </button>
        </form>

        <p className="text-center text-gray-500 text-sm mt-4">
          Already registered?{" "}
          <Link href="/agency/login" className="text-purple-400 hover:text-purple-300">
            Sign in
          </Link>
        </p>
        <p className="text-center text-gray-600 text-xs mt-2">
          Are you a client?{" "}
          <Link href="/client/register" className="text-blue-400 hover:text-blue-300">
            Client registration →
          </Link>
        </p>
      </div>
    </div>
  );
}
