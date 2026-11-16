"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Lock, Mail } from "lucide-react";
import { AuthLayout } from "@/components/shared/auth-layout";

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

  const footer = (
    <div style={{ textAlign: "center", fontSize: "11px", color: "var(--muted)", display: "flex", flexDirection: "column", gap: "8px" }}>
      <div>
        Need to register your agency?{" "}
        <Link href="/agency/register" style={{ color: "var(--violet)", fontWeight: 500 }}>
          Create an agency workspace →
        </Link>
      </div>
      <div>
        Looking for client sign in?{" "}
        <Link href="/client/login" style={{ color: "var(--muted)", textDecoration: "underline" }}>
          Client Login
        </Link>
      </div>
    </div>
  );

  return (
    <AuthLayout
      eyebrow="AGENCY WORKSPACE ACCESS"
      title="Agency Studio Sign In"
      subtitle="Sign in to your agency workspace and client intelligence pipeline."
      footer={footer}
    >
      <form onSubmit={handleSubmit} className="stack-form">
        {error && <div className="error-box">{error}</div>}

        <label>
          Work Email
          <input
            type="email"
            name="email"
            required
            autoComplete="email"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            placeholder="owner@agency.com"
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
            placeholder="Your workspace password"
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="primary-button full"
          style={{ height: "42px" }}
        >
          {loading ? "Signing in…" : "Sign In to Workspace"}
          <ArrowRight size={16} />
        </button>
      </form>
    </AuthLayout>
  );
}
