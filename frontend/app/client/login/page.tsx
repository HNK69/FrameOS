"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { AuthLayout } from "@/components/shared/auth-layout";

export default function ClientLoginPage() {
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
      if (data.role !== "client") {
        setError("This account is not a client account. Please use Agency Login.");
        return;
      }
      router.push("/client/dashboard");
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const footer = (
    <div style={{ textAlign: "center", fontSize: "11px", color: "var(--muted)", display: "flex", flexDirection: "column", gap: "8px" }}>
      <div>
        New client?{" "}
        <Link href="/client/register" style={{ color: "var(--violet)", fontWeight: 500 }}>
          Create client account →
        </Link>
      </div>
      <div>
        Are you an agency?{" "}
        <Link href="/agency/login" style={{ color: "var(--muted)", textDecoration: "underline" }}>
          Agency login
        </Link>
      </div>
    </div>
  );

  return (
    <AuthLayout
      eyebrow="CLIENT PORTAL ACCESS"
      title="Client Sign In"
      subtitle="Sign in to track your video projects, review cuts, and manage creative briefs."
      footer={footer}
    >
      <form onSubmit={handleSubmit} className="stack-form">
        {error && <div className="error-box">{error}</div>}

        <label>
          Email
          <input
            type="email"
            name="email"
            required
            autoComplete="email"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            placeholder="you@company.com"
          />
        </label>

        <label>
          Password
          <input
            type="password"
            name="password"
            required
            autoComplete="current-password"
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            placeholder="Your client password"
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="primary-button full"
          style={{ height: "42px" }}
        >
          {loading ? "Signing in…" : "Sign In to Client Portal"}
          <ArrowRight size={16} />
        </button>
      </form>
    </AuthLayout>
  );
}
