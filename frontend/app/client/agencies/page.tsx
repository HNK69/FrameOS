"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ExternalLink,
  Globe,
  Mail,
  Search,
  Sparkles,
  Video,
} from "lucide-react";
import { AppLayout } from "@/components/shared/app-layout";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";

interface Agency {
  workspace_id: number;
  name: string;
  tagline: string;
  description: string;
  specializations: string[];
  services: string[];
  contact_email: string;
  website: string;
  published_at?: string;
}

export default function AgenciesPage() {
  const router = useRouter();
  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [search, setSearch] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchAgencies = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (search.trim()) params.set("query", search.trim());
    if (specialization.trim()) params.set("specialization", specialization.trim());
    try {
      const r = await fetch(`/api/discovery/agencies?${params}`);
      if (r.ok) setAgencies(await r.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgencies();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchAgencies();
  };

  return (
    <AppLayout persona="client">
      <PageHeader
        eyebrow="CLIENT / DISCOVERY"
        title="Agency Catalog"
        description="Discover specialized video editing studios, explore verified portfolios, and submit targeted project briefs."
      />

      {/* Search Bar Panel */}
      <div className="panel" style={{ padding: "16px 20px", marginBottom: "20px" }}>
        <form onSubmit={handleSearch} style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <div className="search-box" style={{ flex: "1 1 280px" }}>
            <Search size={15} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search agencies by name, style, or creative focus…"
            />
          </div>

          <div className="search-box" style={{ flex: "0 1 220px" }}>
            <Video size={15} />
            <input
              type="text"
              value={specialization}
              onChange={(e) => setSpecialization(e.target.value)}
              placeholder="Specialization (e.g. YouTube, 3D)…"
            />
          </div>

          <button type="submit" className="primary-button" style={{ height: "35px" }}>
            <Search size={14} /> Search Catalog
          </button>
        </form>
      </div>

      {/* Results Grid */}
      {loading ? (
        <div className="loading-line">Searching published agencies…</div>
      ) : agencies.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No agencies match your criteria"
          body="Try broadening your search keywords or clearing the specialization filter."
          action={
            (search || specialization) && (
              <button
                className="small-action"
                onClick={() => {
                  setSearch("");
                  setSpecialization("");
                  fetchAgencies();
                }}
              >
                Clear all filters <ArrowRight size={13} />
              </button>
            )
          }
        />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: "16px" }}>
          {agencies.map((agency) => (
            <Link
              key={agency.workspace_id}
              href={`/client/agencies/${agency.workspace_id}`}
              className="panel"
              style={{
                padding: "22px",
                display: "flex",
                flexDirection: "column",
                textDecoration: "none",
                transition: "all .2s ease",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" }}>
                <div className="client-monogram large">
                  {agency.name.slice(0, 1).toUpperCase()}
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <h2
                    style={{
                      margin: 0,
                      font: "600 15px var(--display)",
                      color: "#fff",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {agency.name}
                  </h2>
                  {agency.tagline && (
                    <p
                      style={{
                        margin: "2px 0 0",
                        fontSize: "11px",
                        color: "var(--violet)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {agency.tagline}
                    </p>
                  )}
                </div>
              </div>

              {agency.description && (
                <p
                  style={{
                    margin: "0 0 14px",
                    fontSize: "11px",
                    color: "#9295aa",
                    lineHeight: 1.5,
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                    flex: 1,
                  }}
                >
                  {agency.description}
                </p>
              )}

              <div className="chip-container" style={{ marginTop: "auto", marginBottom: "14px" }}>
                {agency.specializations?.slice(0, 3).map((s) => (
                  <span key={s} className="chip-badge" style={{ fontSize: "10px" }}>
                    {s}
                  </span>
                ))}
                {agency.services?.slice(0, 2).map((s) => (
                  <span
                    key={s}
                    className="chip-badge"
                    style={{
                      fontSize: "10px",
                      background: "rgba(255,255,255,.04)",
                      borderColor: "rgba(255,255,255,.1)",
                      color: "#cbd5e1",
                    }}
                  >
                    {s}
                  </span>
                ))}
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  paddingTop: "12px",
                  borderTop: "1px solid var(--line)",
                  fontSize: "11px",
                  color: "#8a8ea2",
                }}
              >
                <span>View studio profile</span>
                <span style={{ color: "var(--violet)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "4px" }}>
                  Explore <ArrowRight size={13} />
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppLayout>
  );
}
