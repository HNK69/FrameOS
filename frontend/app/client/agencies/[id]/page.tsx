"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  Film,
  Globe,
  Mail,
  Phone,
  Plus,
  Sparkles,
  Video,
} from "lucide-react";
import { AppLayout } from "@/components/shared/app-layout";
import { PageHeader } from "@/components/shared/page-header";

interface Agency {
  workspace_id: number;
  name: string;
  tagline: string;
  description: string;
  specializations: string[];
  services: string[];
  portfolio: { title: string; video_url: string; description: string }[];
  contact_email: string;
  contact_phone: string;
  website: string;
  published_at?: string;
}

export default function AgencyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.id as string;
  const [agency, setAgency] = useState<Agency | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    fetch(`/api/discovery/agencies/${workspaceId}`)
      .then((r) => {
        if (r.status === 404) {
          setNotFound(true);
          return null;
        }
        return r.json();
      })
      .then((data) => {
        if (data) setAgency(data);
      })
      .finally(() => setLoading(false));
  }, [workspaceId]);

  if (loading) {
    return (
      <AppLayout persona="client">
        <div className="loading-line">Opening Agency Profile…</div>
      </AppLayout>
    );
  }

  if (notFound || !agency) {
    return (
      <AppLayout persona="client">
        <div className="panel" style={{ padding: "40px 20px", textAlign: "center" }}>
          <h2 style={{ font: "600 20px var(--display)", color: "#fff", marginBottom: "8px" }}>
            Agency Not Found
          </h2>
          <p style={{ color: "#9295a8", marginBottom: "16px" }}>
            The agency profile you requested does not exist or is currently unpublished.
          </p>
          <Link href="/client/agencies" className="primary-button" style={{ textDecoration: "none" }}>
            <ArrowLeft size={14} /> Back to Agency Catalog
          </Link>
        </div>
      </AppLayout>
    );
  }

  const headerActions = (
    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
      <Link href="/client/agencies" className="quiet-button">
        <ArrowLeft size={14} /> Back to Catalog
      </Link>
      <Link
        href={`/client/requests/new?agency=${agency.workspace_id}&name=${encodeURIComponent(agency.name)}`}
        className="primary-button"
      >
        <Plus size={15} /> Submit Project Brief
      </Link>
    </div>
  );

  return (
    <AppLayout persona="client">
      <PageHeader
        eyebrow="CLIENT / AGENCY DETAILS"
        title={agency.name}
        description={agency.tagline || "Verified Video Production Studio"}
        actions={headerActions}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        {/* Agency Hero Card */}
        <section className="panel" style={{ padding: "26px" }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "16px", marginBottom: "16px" }}>
            <div className="client-monogram large" style={{ width: "48px", height: "48px", fontSize: "18px" }}>
              {agency.name.slice(0, 1).toUpperCase()}
            </div>
            <div>
              <h2 style={{ margin: "0 0 4px", font: "600 18px var(--display)", color: "#fff" }}>
                {agency.name}
              </h2>
              {agency.tagline && (
                <p style={{ margin: 0, color: "var(--violet)", fontSize: "12px", fontWeight: 500 }}>
                  {agency.tagline}
                </p>
              )}
            </div>
          </div>

          {agency.description && (
            <p style={{ margin: "0 0 20px", color: "#cbd5e1", fontSize: "13px", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
              {agency.description}
            </p>
          )}

          <div
            style={{
              paddingTop: "16px",
              borderTop: "1px solid var(--line)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div style={{ display: "flex", gap: "16px", fontSize: "11px", color: "#8e92a6", flexWrap: "wrap" }}>
              {agency.contact_email && (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <Mail size={14} color="var(--violet)" /> {agency.contact_email}
                </span>
              )}
              {agency.contact_phone && (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <Phone size={14} color="var(--violet)" /> {agency.contact_phone}
                </span>
              )}
              {agency.website && (
                <a
                  href={agency.website}
                  target="_blank"
                  rel="noreferrer"
                  style={{ display: "inline-flex", alignItems: "center", gap: "6px", color: "var(--violet)", textDecoration: "none" }}
                >
                  <Globe size={14} /> {agency.website.replace(/^https?:\/\//, "")} <ExternalLink size={12} />
                </a>
              )}
            </div>

            <Link
              href={`/client/requests/new?agency=${agency.workspace_id}&name=${encodeURIComponent(agency.name)}`}
              className="primary-button"
            >
              Submit Brief to {agency.name} <ArrowRight size={14} />
            </Link>
          </div>
        </section>

        {/* Specializations & Services */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
          {agency.specializations?.length > 0 && (
            <div className="panel" style={{ padding: "20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                <Sparkles size={15} color="var(--violet)" />
                <h3 style={{ margin: 0, font: "600 14px var(--display)", color: "#fff" }}>Creative Specializations</h3>
              </div>
              <div className="chip-container">
                {agency.specializations.map((s) => (
                  <span key={s} className="chip-badge">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {agency.services?.length > 0 && (
            <div className="panel" style={{ padding: "20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                <Video size={15} color="var(--violet)" />
                <h3 style={{ margin: 0, font: "600 14px var(--display)", color: "#fff" }}>Production Services</h3>
              </div>
              <div className="chip-container">
                {agency.services.map((s) => (
                  <span
                    key={s}
                    className="chip-badge"
                    style={{
                      background: "rgba(255,255,255,.04)",
                      borderColor: "rgba(255,255,255,.1)",
                      color: "#cbd5e1",
                    }}
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Portfolio Section */}
        {agency.portfolio?.length > 0 && (
          <section className="panel" style={{ padding: "22px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
              <span className="head-icon">
                <Film size={15} />
              </span>
              <h3 style={{ margin: 0, font: "600 15px var(--display)", color: "#fff" }}>
                Portfolio Showcases
              </h3>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "14px" }}>
              {agency.portfolio.map((item, i) => (
                <div
                  key={i}
                  className="panel"
                  style={{
                    padding: "16px",
                    background: "rgba(255,255,255,.02)",
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <b style={{ color: "#fff", fontSize: "13px", display: "block", marginBottom: "4px" }}>
                    {item.title}
                  </b>
                  {item.description && (
                    <p style={{ margin: "0 0 12px", color: "#8e92a6", fontSize: "11px", lineHeight: 1.5, flex: 1 }}>
                      {item.description}
                    </p>
                  )}
                  {item.video_url && (
                    <a
                      href={item.video_url}
                      target="_blank"
                      rel="noreferrer"
                      className="outline-action"
                      style={{ marginTop: "auto", alignSelf: "flex-start", textDecoration: "none" }}
                    >
                      <Film size={12} /> Watch Reel <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </AppLayout>
  );
}
