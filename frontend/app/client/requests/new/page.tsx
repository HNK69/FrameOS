"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Calendar,
  DollarSign,
  FileText,
  Film,
  Save,
  Send,
  Sparkles,
  Tv,
  X,
  CheckCircle2,
  Building2,
} from "lucide-react";
import { AppLayout } from "@/components/shared/app-layout";
import { PageHeader } from "@/components/shared/page-header";

interface PublishedAgency {
  workspace_id: number;
  name: string;
  tagline: string;
  description: string;
  specializations: string[];
  services: string[];
}

function NewRequestForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preAgencyId = searchParams.get("agency") || searchParams.get("agency_id") || "";
  const preAgencyName = searchParams.get("name") || "";

  const [agencies, setAgencies] = useState<PublishedAgency[]>([]);
  const [selectedAgency, setSelectedAgency] = useState<PublishedAgency | null>(null);
  const [loadingAgencies, setLoadingAgencies] = useState(true);

  const [form, setForm] = useState({
    agency_workspace_id: preAgencyId ? parseInt(preAgencyId) : 0,
    title: "",
    description: "",
    video_type: "",
    target_platform: "",
    target_duration: "",
    aspect_ratio: "",
    editing_requirements: "",
    creative_direction: "",
    deliverables_format: "",
    budget: "",
    deadline: "",
    status: "submitted" as "submitted" | "draft",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoadingAgencies(true);
    fetch("/api/discovery/agencies")
      .then((r) => (r.ok ? r.json() : []))
      .then((data: PublishedAgency[]) => {
        setAgencies(data);
        if (preAgencyId) {
          const matched = data.find((a) => a.workspace_id === parseInt(preAgencyId));
          if (matched) {
            setSelectedAgency(matched);
            setForm((f) => ({ ...f, agency_workspace_id: matched.workspace_id }));
          } else {
            fetch(`/api/discovery/agencies/${preAgencyId}`)
              .then((r) => (r.ok ? r.json() : null))
              .then((detail) => {
                if (detail) {
                  setSelectedAgency(detail);
                  setForm((f) => ({ ...f, agency_workspace_id: detail.workspace_id }));
                }
              });
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoadingAgencies(false));
  }, [preAgencyId]);

  const handleSelectAgency = (wsId: number) => {
    const found = agencies.find((a) => a.workspace_id === wsId);
    if (found) {
      setSelectedAgency(found);
      setForm((f) => ({ ...f, agency_workspace_id: found.workspace_id }));
      setError("");
    } else {
      setSelectedAgency(null);
      setForm((f) => ({ ...f, agency_workspace_id: 0 }));
    }
  };

  const handleChangeAgency = () => {
    setSelectedAgency(null);
    setForm((f) => ({ ...f, agency_workspace_id: 0 }));
  };

  const handleSubmit = async (e: React.FormEvent, asDraft = false) => {
    e.preventDefault();
    const wsId = form.agency_workspace_id;
    if (!wsId || wsId <= 0) {
      setError("Please select a published agency before submitting your project brief.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = {
        ...form,
        agency_workspace_id: wsId,
        deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
        status: asDraft ? "draft" : "submitted",
      };
      const r = await fetch("/api/client/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include",
      });
      if (!r.ok) {
        const data = await r.json();
        setError(typeof data.detail === "string" ? data.detail : "Failed to submit request");
        return;
      }
      const req = await r.json();
      router.push(`/client/requests/${req.id}`);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const headerActions = (
    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
      <Link href="/client/dashboard" className="quiet-button">
        <ArrowLeft size={14} /> Back to Dashboard
      </Link>
    </div>
  );

  return (
    <AppLayout persona="client">
      <PageHeader
        eyebrow="CLIENT / NEW BRIEF"
        title="Submit Project Brief"
        description={
          selectedAgency
            ? `Directing creative brief to: ${selectedAgency.name}`
            : "Define your video scope, turnaround deadlines, and creative goals for agency matching."
        }
        actions={headerActions}
      />

      {error && (
        <div
          className="notice"
          style={{
            borderColor: "rgba(255,119,125,.4)",
            background: "rgba(134,44,51,.3)",
            marginBottom: "20px",
          }}
        >
          <span>{error}</span>
          <button onClick={() => setError("")} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      )}

      <form onSubmit={(e) => handleSubmit(e, false)} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
        {/* Recipient Agency Selector */}
        <section className="form-panel">
          <div className="form-section-title">
            <Building2 size={16} color="var(--violet)" />
            <h3>Target Agency Partner</h3>
            <small>Direct brief routing</small>
          </div>

          {selectedAgency ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 18px",
                background: "rgba(168, 85, 247, 0.08)",
                border: "1px solid rgba(168, 85, 247, 0.25)",
                borderRadius: "12px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                <div
                  style={{
                    width: "42px",
                    height: "42px",
                    borderRadius: "10px",
                    background: "linear-gradient(135deg, rgba(168,85,247,0.3), rgba(99,102,241,0.2))",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--violet)",
                    fontWeight: "bold",
                    fontSize: "18px",
                  }}
                >
                  {selectedAgency.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <b style={{ color: "#fff", fontSize: "15px" }}>{selectedAgency.name}</b>
                    <span className="status-pill status-pill-active" style={{ fontSize: "11px", padding: "1px 8px" }}>
                      Published Agency
                    </span>
                  </div>
                  {selectedAgency.tagline && (
                    <p style={{ margin: "2px 0 0", color: "#9295a8", fontSize: "13px" }}>
                      {selectedAgency.tagline}
                    </p>
                  )}
                  {selectedAgency.specializations?.length > 0 && (
                    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>
                      {selectedAgency.specializations.slice(0, 3).map((s) => (
                        <span
                          key={s}
                          style={{
                            fontSize: "11px",
                            color: "#c4b5fd",
                            background: "rgba(168,85,247,0.12)",
                            padding: "2px 7px",
                            borderRadius: "4px",
                          }}
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={handleChangeAgency}
                className="quiet-button"
                style={{ fontSize: "12px", height: "32px", padding: "0 12px" }}
              >
                Change Agency
              </button>
            </div>
          ) : (
            <div className="stack-form">
              <label>
                Select Agency <span style={{ color: "var(--violet)" }}>*</span>
                {loadingAgencies ? (
                  <div className="loading-line" style={{ padding: "8px 0" }}>Loading verified agencies…</div>
                ) : agencies.length === 0 ? (
                  <div
                    style={{
                      padding: "14px",
                      background: "rgba(255,255,255,0.03)",
                      borderRadius: "8px",
                      border: "1px solid rgba(255,255,255,0.08)",
                      color: "#9295a8",
                      fontSize: "13px",
                    }}
                  >
                    No published agencies are currently available. Browse the{" "}
                    <Link href="/client/agencies" style={{ color: "var(--violet)", textDecoration: "underline" }}>
                      Agency Catalog
                    </Link>{" "}
                    to view partners.
                  </div>
                ) : (
                  <select
                    required
                    value={form.agency_workspace_id || ""}
                    onChange={(e) => handleSelectAgency(parseInt(e.target.value) || 0)}
                    style={{
                      width: "100%",
                      padding: "10px 14px",
                      background: "rgba(15, 17, 26, 0.8)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: "8px",
                      color: "#fff",
                      fontSize: "14px",
                      outline: "none",
                    }}
                  >
                    <option value="">Select a published agency to receive this brief…</option>
                    {agencies.map((a) => (
                      <option key={a.workspace_id} value={a.workspace_id}>
                        {a.name} {a.tagline ? `— ${a.tagline}` : a.specializations?.length ? `— ${a.specializations.join(", ")}` : ""}
                      </option>
                    ))}
                  </select>
                )}
                <small style={{ color: "#6b7280", marginTop: "4px" }}>
                  Your brief will only be delivered to the verified agency you select.
                </small>
              </label>
            </div>
          )}
        </section>

        {/* Project Scope & Core Specs */}
        <section className="form-panel">
          <div className="form-section-title">
            <FileText size={16} color="var(--violet)" />
            <h3>Project Scope & Objectives</h3>
            <small>Deliverable Identity</small>
          </div>

          <div className="stack-form">
            <label>
              Project Title <span style={{ color: "var(--violet)" }}>*</span>
              <input
                type="text"
                name="title"
                required
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="e.g. Q4 Brand Anthem Campaign"
              />
            </label>

            <label>
              Scope & Goal Description
              <textarea
                rows={3}
                name="description"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="What is the story or deliverable? Provide the agency context about your audience and goals…"
              />
            </label>

            <div className="form-grid">
              <label>
                Video Type
                <input
                  type="text"
                  value={form.video_type}
                  onChange={(e) => setForm((f) => ({ ...f, video_type: e.target.value }))}
                  placeholder="e.g. Brand Film, Social Reel, YouTube"
                />
              </label>

              <label>
                Target Platform
                <input
                  type="text"
                  value={form.target_platform}
                  onChange={(e) => setForm((f) => ({ ...f, target_platform: e.target.value }))}
                  placeholder="e.g. YouTube, Instagram 9:16, LinkedIn"
                />
              </label>
            </div>

            <div className="form-grid">
              <label>
                Target Duration
                <input
                  type="text"
                  value={form.target_duration}
                  onChange={(e) => setForm((f) => ({ ...f, target_duration: e.target.value }))}
                  placeholder="e.g. 60–90 seconds, 30s cut"
                />
              </label>

              <label>
                Aspect Ratio
                <input
                  type="text"
                  value={form.aspect_ratio}
                  onChange={(e) => setForm((f) => ({ ...f, aspect_ratio: e.target.value }))}
                  placeholder="e.g. 16:9 widescreen, 9:16 vertical"
                />
              </label>
            </div>
          </div>
        </section>

        {/* Technical & Creative Requirements */}
        <section className="form-panel">
          <div className="form-section-title">
            <Film size={16} color="var(--violet)" />
            <h3>Creative & Editorial Guidelines</h3>
            <small>Production Parameters</small>
          </div>

          <div className="stack-form">
            <label>
              Editing Requirements & Technical Notes
              <textarea
                rows={3}
                value={form.editing_requirements}
                onChange={(e) => setForm((f) => ({ ...f, editing_requirements: e.target.value }))}
                placeholder="Pacing, color palette, audio/music preferences, DaVinci Resolve color grades, sound design…"
              />
            </label>

            <label>
              Creative Direction & Tone
              <textarea
                rows={3}
                value={form.creative_direction}
                onChange={(e) => setForm((f) => ({ ...f, creative_direction: e.target.value }))}
                placeholder="High energy, cinematic, corporate documentary, minimal, luxury aesthetic…"
              />
            </label>

            <label>
              Deliverables Format
              <input
                type="text"
                value={form.deliverables_format}
                onChange={(e) => setForm((f) => ({ ...f, deliverables_format: e.target.value }))}
                placeholder="e.g. ProRes 422HQ master + H.264 web deliverables + Clean feed"
              />
            </label>
          </div>
        </section>

        {/* Timeline & Budget Expectations */}
        <section className="form-panel">
          <div className="form-section-title">
            <DollarSign size={16} color="var(--violet)" />
            <h3>Budget & Timeline</h3>
            <small>Proposal Context</small>
          </div>

          <div className="stack-form">
            <div className="form-grid">
              <label>
                Budget Range
                <input
                  type="text"
                  value={form.budget}
                  onChange={(e) => setForm((f) => ({ ...f, budget: e.target.value }))}
                  placeholder="e.g. $5,000 – $8,000"
                />
              </label>

              <label>
                Desired Completion Deadline
                <input
                  type="date"
                  value={form.deadline}
                  onChange={(e) => setForm((f) => ({ ...f, deadline: e.target.value }))}
                />
              </label>
            </div>
          </div>
        </section>

        {/* Actions Toolbar */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: "10px",
            marginTop: "10px",
          }}
        >
          <button
            type="button"
            disabled={loading}
            onClick={(e) => handleSubmit(e, true)}
            className="quiet-button"
            style={{ height: "42px", padding: "0 18px" }}
          >
            <Save size={14} /> Save as Draft
          </button>
          <button
            type="submit"
            disabled={loading}
            className="primary-button"
            style={{ height: "42px", padding: "0 22px" }}
          >
            <Send size={14} />
            {loading ? "Submitting Brief…" : "Submit Project Brief"}
          </button>
        </div>
      </form>
    </AppLayout>
  );
}

export default function NewRequestPage() {
  return (
    <Suspense
      fallback={
        <AppLayout persona="client">
          <div className="loading-line">Opening Brief Creator…</div>
        </AppLayout>
      }
    >
      <NewRequestForm />
    </Suspense>
  );
}
