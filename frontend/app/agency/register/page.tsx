"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { AuthLayout } from "@/components/shared/auth-layout";

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

  const footer = (
    <div style={{ textAlign: "center", fontSize: "11px", color: "var(--muted)", display: "flex", flexDirection: "column", gap: "8px" }}>
      <div>
        Already have an agency workspace?{" "}
        <Link href="/agency/login" style={{ color: "var(--violet)", fontWeight: 500 }}>
          Sign in here →
        </Link>
      </div>
      <div>
        Are you a client looking to hire agencies?{" "}
        <Link href="/client/register" style={{ color: "var(--muted)", textDecoration: "underline" }}>
          Client registration
        </Link>
      </div>
    </div>
  );

  return (
    <AuthLayout
      eyebrow="AGENCY WORKSPACE ONBOARDING"
      title="Register Your Agency"
      subtitle="Establish your agency studio workspace, publish your profile, and receive client briefs."
      footer={footer}
    >
      <form onSubmit={handleSubmit} className="stack-form">
        {error && <div className="error-box">{error}</div>}

        <label>
          Agency Name
          <input
            type="text"
            name="agency_name"
            required
            minLength={2}
            value={form.agency_name}
            onChange={(e) => setForm((f) => ({ ...f, agency_name: e.target.value }))}
            placeholder="e.g. Apex Visuals Studio"
          />
        </label>

        <label>
          Your Full Name
          <input
            type="text"
            name="full_name"
            required
            value={form.full_name}
            onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
            placeholder="e.g. Alex Rivera"
          />
        </label>

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
          {loading ? "Creating workspace…" : "Create Agency Workspace"}
          <ArrowRight size={16} />
        </button>
      </form>
    </AuthLayout>
  );
}
