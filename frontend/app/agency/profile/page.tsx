"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  ExternalLink,
  Globe,
  Mail,
  Phone,
  Plus,
  Save,
  Sparkles,
  Trash2,
  Video,
  X,
} from "lucide-react";
import { AppLayout } from "@/components/shared/app-layout";
import { PageHeader } from "@/components/shared/page-header";

interface AgencyProfile {
  id: number;
  workspace_id: number;
  workspace_name: string;
  tagline: string;
  description: string;
  specializations: string[];
  services: string[];
  portfolio: { title: string; video_url: string; description: string }[];
  contact_email: string;
  contact_phone: string;
  website: string;
  is_published: boolean;
  published_at?: string;
  is_ready_to_publish: boolean;
  missing_fields: string[];
}

export default function AgencyProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<AgencyProfile | null>(null);
  const [tagline, setTagline] = useState("");
  const [description, setDescription] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [website, setWebsite] = useState("");
  const [specInput, setSpecInput] = useState("");
  const [specializations, setSpecializations] = useState<string[]>([]);
  const [srvInput, setSrvInput] = useState("");
  const [services, setServices] = useState<string[]>([]);
  const [portfolioTitle, setPortfolioTitle] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");
  const [portfolioDesc, setPortfolioDesc] = useState("");
  const [portfolio, setPortfolio] = useState<
    { title: string; video_url: string; description: string }[]
  >([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchProfile = async () => {
    try {
      const res = await fetch("/api/agency/profile", { credentials: "include" });
      if (res.status === 401 || res.status === 403) {
        router.push("/agency/login");
        return;
      }
      if (res.ok) {
        const data: AgencyProfile = await res.json();
        setProfile(data);
        setTagline(data.tagline || "");
        setDescription(data.description || "");
        setContactEmail(data.contact_email || "");
        setContactPhone(data.contact_phone || "");
        setWebsite(data.website || "");
        setSpecializations(data.specializations || []);
        setServices(data.services || []);
        setPortfolio(data.portfolio || []);
      }
    } catch {
      setMessage({ type: "error", text: "Failed to load agency profile." });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch("/api/agency/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          tagline,
          description,
          contact_email: contactEmail,
          contact_phone: contactPhone,
          website,
          specializations,
          services,
          portfolio,
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        setProfile(updated);
        setMessage({ type: "success", text: "Profile updated successfully." });
      } else {
        const err = await res.json();
        setMessage({
          type: "error",
          text: typeof err.detail === "string" ? err.detail : "Failed to update profile.",
        });
      }
    } catch {
      setMessage({ type: "error", text: "Network error saving profile." });
    } finally {
      setSaving(false);
    }
  };

  const togglePublish = async () => {
    if (!profile) return;
    setPublishing(true);
    setMessage(null);
    const action = profile.is_published ? "unpublish" : "publish";
    try {
      const res = await fetch(`/api/agency/profile/${action}`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const updated = await res.json();
        setProfile(updated);
        setMessage({
          type: "success",
          text: profile.is_published
            ? "Agency profile unpublished from public discovery."
            : "Agency profile published! Clients can now discover your agency.",
        });
      } else {
        const err = await res.json();
        setMessage({
          type: "error",
          text: typeof err.detail === "string" ? err.detail : `Failed to ${action} profile.`,
        });
      }
    } catch {
      setMessage({ type: "error", text: "Network error updating publish state." });
    } finally {
      setPublishing(false);
    }
  };

  const addSpec = () => {
    if (specInput.trim() && !specializations.includes(specInput.trim())) {
      setSpecializations([...specializations, specInput.trim()]);
      setSpecInput("");
    }
  };

  const removeSpec = (idx: number) => {
    setSpecializations(specializations.filter((_, i) => i !== idx));
  };

  const addSrv = () => {
    if (srvInput.trim() && !services.includes(srvInput.trim())) {
      setServices([...services, srvInput.trim()]);
      setSrvInput("");
    }
  };

  const removeSrv = (idx: number) => {
    setServices(services.filter((_, i) => i !== idx));
  };

  const addPortfolioItem = () => {
    if (portfolioTitle.trim() && portfolioUrl.trim()) {
      setPortfolio([
        ...portfolio,
        {
          title: portfolioTitle.trim(),
          video_url: portfolioUrl.trim(),
          description: portfolioDesc.trim(),
        },
      ]);
      setPortfolioTitle("");
      setPortfolioUrl("");
      setPortfolioDesc("");
    }
  };

  const removePortfolioItem = (idx: number) => {
    setPortfolio(portfolio.filter((_, i) => i !== idx));
  };

  if (loading) {
    return (
      <AppLayout persona="agency">
        <div className="loading-line">Opening Agency Profile…</div>
      </AppLayout>
    );
  }

  const publishHeaderActions = (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <span className={`status-pill ${profile?.is_published ? "accepted" : "under_review"}`}>
        <span className={`status-dot ${profile?.is_published ? "active" : "pending"}`} />
        {profile?.is_published ? "Published in Catalog" : "Draft (Unpublished)"}
      </span>
      <button
        type="button"
        onClick={togglePublish}
        disabled={publishing}
        className={profile?.is_published ? "quiet-button" : "primary-button"}
      >
        {publishing
          ? "Updating…"
          : profile?.is_published
          ? "Unpublish Profile"
          : "Publish to Catalog"}
      </button>
    </div>
  );

  return (
    <AppLayout persona="agency">
      <PageHeader
        eyebrow="WORKSPACE / PROFILE"
        title={`${profile?.workspace_name || "Agency"} Profile`}
        description="Configure your public catalog listing and credentials for discovery by potential clients."
        actions={publishHeaderActions}
      />

      {message && (
        <div
          className="notice"
          style={
            message.type === "error"
              ? { borderColor: "rgba(255,119,125,.4)", background: "rgba(134,44,51,.3)" }
              : undefined
          }
        >
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      )}

      {profile && !profile.is_published && (profile.missing_fields?.length ?? 0) > 0 && (
        <div
          className="panel"
          style={{
            padding: "16px 20px",
            marginBottom: "20px",
            borderColor: "rgba(237,186,98,.35)",
            background: "linear-gradient(145deg,rgba(40,30,15,.7),rgba(20,18,25,.8))",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#f0ce84", marginBottom: "8px", fontSize: "11px", fontWeight: 600 }}>
            <AlertCircle size={15} />
            <span>Publishing Checklist</span>
          </div>
          <p style={{ margin: 0, color: "#cbd5e1", fontSize: "11px" }}>
            Complete the following required fields to make your profile visible to clients in discovery:
          </p>
          <div className="chip-container" style={{ marginTop: "10px" }}>
            {profile.missing_fields.map((f) => (
              <span
                key={f}
                style={{
                  padding: "4px 10px",
                  borderRadius: "6px",
                  fontSize: "10px",
                  fontFamily: "var(--mono)",
                  background: "rgba(237,186,98,.12)",
                  border: "1px solid rgba(237,186,98,.35)",
                  color: "#f0ce84",
                  textTransform: "capitalize",
                }}
              >
                {f.replace("_", " ")}
              </span>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
        {/* General Information */}
        <section className="form-panel">
          <div className="form-section-title">
            <Sparkles size={16} color="var(--violet)" />
            <h3>General Agency Information</h3>
            <small>Public Brand Presentation</small>
          </div>

          <div className="stack-form">
            <label>
              Tagline
              <input
                type="text"
                value={tagline}
                onChange={(e) => setTagline(e.target.value)}
                placeholder="e.g. Cinematic commercial editing & fast turnaround reels"
              />
            </label>

            <label>
              Description <span style={{ color: "var(--violet)" }}>*</span>
              <textarea
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe your agency, creative team, editing style, and production capabilities…"
              />
            </label>

            <div className="form-grid">
              <label>
                Public Contact Email <span style={{ color: "var(--violet)" }}>*</span>
                <input
                  type="email"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
                  placeholder="contact@agency.com"
                />
              </label>

              <label>
                Contact Phone
                <input
                  type="text"
                  value={contactPhone}
                  onChange={(e) => setContactPhone(e.target.value)}
                  placeholder="+1 (555) 000-0000"
                />
              </label>
            </div>

            <label>
              Website URL
              <input
                type="url"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="https://agency.com"
              />
            </label>
          </div>
        </section>

        {/* Specializations & Services */}
        <section className="form-panel">
          <div className="form-section-title">
            <Video size={16} color="var(--violet)" />
            <h3>Specializations & Services</h3>
            <small>Client Matching Capabilities</small>
          </div>

          <div className="stack-form">
            <div>
              <label style={{ display: "block", marginBottom: "8px" }}>
                Specializations <span style={{ color: "var(--violet)" }}>*</span>
              </label>
              <div style={{ display: "flex", gap: "8px", marginBottom: "10px" }}>
                <input
                  type="text"
                  value={specInput}
                  onChange={(e) => setSpecInput(e.target.value)}
                  placeholder="e.g. YouTube Creators, Commercials, Motion Graphics"
                  style={{ flex: 1 }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addSpec();
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={addSpec}
                  className="quiet-button"
                  style={{ height: "34px" }}
                >
                  <Plus size={14} /> Add
                </button>
              </div>

              <div className="chip-container">
                {specializations.map((s, idx) => (
                  <span key={idx} className="chip-badge">
                    {s}
                    <button type="button" onClick={() => removeSpec(idx)} aria-label={`Remove ${s}`}>
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            <div style={{ marginTop: "14px" }}>
              <label style={{ display: "block", marginBottom: "8px" }}>
                Offered Services <span style={{ color: "var(--violet)" }}>*</span>
              </label>
              <div style={{ display: "flex", gap: "8px", marginBottom: "10px" }}>
                <input
                  type="text"
                  value={srvInput}
                  onChange={(e) => setSrvInput(e.target.value)}
                  placeholder="e.g. Color Grading, Sound Design, Subtitles, 4K Upscaling"
                  style={{ flex: 1 }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addSrv();
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={addSrv}
                  className="quiet-button"
                  style={{ height: "34px" }}
                >
                  <Plus size={14} /> Add
                </button>
              </div>

              <div className="chip-container">
                {services.map((s, idx) => (
                  <span key={idx} className="chip-badge" style={{ background: "rgba(255,255,255,.05)", borderColor: "rgba(255,255,255,.12)", color: "#e2e8f0" }}>
                    {s}
                    <button type="button" onClick={() => removeSrv(idx)} aria-label={`Remove ${s}`}>
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Portfolio Items */}
        <section className="form-panel">
          <div className="form-section-title">
            <Globe size={16} color="var(--violet)" />
            <h3>Portfolio Showcases</h3>
            <small>Client Discovery Evidence</small>
          </div>

          <div className="stack-form">
            <div className="form-grid">
              <label>
                Project Title
                <input
                  type="text"
                  value={portfolioTitle}
                  onChange={(e) => setPortfolioTitle(e.target.value)}
                  placeholder="e.g. Nike Brand Anthem"
                />
              </label>

              <label>
                Video URL (YouTube/Vimeo/Drive)
                <input
                  type="url"
                  value={portfolioUrl}
                  onChange={(e) => setPortfolioUrl(e.target.value)}
                  placeholder="https://vimeo.com/…"
                />
              </label>
            </div>

            <label>
              Scope / Description
              <textarea
                rows={2}
                value={portfolioDesc}
                onChange={(e) => setPortfolioDesc(e.target.value)}
                placeholder="Brief description of the work and scope…"
              />
            </label>

            <div>
              <button
                type="button"
                onClick={addPortfolioItem}
                className="quiet-button"
                style={{ height: "34px" }}
              >
                <Plus size={14} /> Add Portfolio Work
              </button>
            </div>

            {portfolio.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "10px" }}>
                {portfolio.map((item, idx) => (
                  <div
                    key={idx}
                    className="panel"
                    style={{
                      padding: "12px 16px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      background: "rgba(255,255,255,.02)",
                    }}
                  >
                    <div>
                      <b style={{ color: "#fff", fontSize: "12px", display: "block" }}>{item.title}</b>
                      <a
                        href={item.video_url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ color: "var(--violet)", fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "4px", marginTop: "3px" }}
                      >
                        {item.video_url} <ExternalLink size={12} />
                      </a>
                      {item.description && (
                        <p style={{ margin: "5px 0 0", color: "#94a3b8", fontSize: "11px" }}>
                          {item.description}
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => removePortfolioItem(idx)}
                      className="icon-button"
                      title="Delete portfolio item"
                      style={{ color: "#ff777d" }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
          <button type="submit" disabled={saving} className="primary-button" style={{ height: "42px", padding: "0 22px" }}>
            <Save size={15} />
            {saving ? "Saving Changes…" : "Save Agency Profile"}
          </button>
        </div>
      </form>
    </AppLayout>
  );
}
