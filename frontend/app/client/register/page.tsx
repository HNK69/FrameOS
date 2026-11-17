"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { AuthLayout } from "@/components/shared/auth-layout";

export default function ClientRegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    company_name: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const r = await fetch("/api/auth/register/client", {
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
        Already have a client account?{" "}
        <Link href="/client/login" style={{ color: "var(--violet)", fontWeight: 500 }}>
          Sign in here →
        </Link>
      </div>
      <div>
        Are you an editing agency?{" "}
        <Link href="/agency/register" style={{ color: "var(--muted)", textDecoration: "underline" }}>
          Agency registration
        </Link>
      </div>
    </div>
  );

  return (
    <AuthLayout
      eyebrow="CLIENT ONBOARDING"
      title="Create Client Account"
      subtitle="Discover video production studios, submit creative briefs, and manage deliverables."
      footer={footer}
    >
      <form onSubmit={handleSubmit} className="stack-form">
        {error && <div className="error-box">{error}</div>}

        <label>
          Full Name
          <input
            type="text"
            name="full_name"
            required
            value={form.full_name}
            onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
            placeholder="e.g. Sarah Connor"
          />
        </label>

        <label>
          Company / Brand Name <span style={{ color: "var(--muted)" }}>(Optional)</span>
          <input
            type="text"
            name="company_name"
            value={form.company_name}
            onChange={(e) => setForm((f) => ({ ...f, company_name: e.target.value }))}
            placeholder="e.g. Horizon Labs"
          />
        </label>

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
            minLength={8}
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            placeholder="At least 8 characters"
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="primary-button full"
          style={{ height: "42px" }}
        >
          {loading ? "Creating account…" : "Create Client Account"}
          <ArrowRight size={16} />
        </button>
      </form>
    </AuthLayout>
  );
}
