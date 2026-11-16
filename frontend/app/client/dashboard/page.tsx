"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ExternalLink,
  FileCheck,
  FileText,
  Film,
  FolderKanban,
  Inbox,
  Plus,
  Sparkles,
  TrendingUp,
  Tv,
  Users,
} from "lucide-react";
import { AppLayout } from "@/components/shared/app-layout";
import { PageHeader } from "@/components/shared/page-header";
import { MetricCard } from "@/components/shared/metric-card";
import { StatusPill } from "@/components/shared/status-pill";
import { EmptyState } from "@/components/shared/empty-state";

interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  role: string;
  company_name?: string;
}

interface ProjectRequest {
  id: number;
  title: string;
  agency_name: string;
  status: string;
  created_at: string;
  proposals_count: number;
  project_id?: number;
}

export default function ClientDashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [requests, setRequests] = useState<ProjectRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const init = async () => {
      try {
        const meR = await fetch("/api/me", { credentials: "include" });
        if (!meR.ok) {
          router.push("/client/login");
          return;
        }
        const me = await meR.json();
        if (me.role !== "client") {
          router.push("/client/login");
          return;
        }
        setUser(me);

        const reqR = await fetch("/api/client/requests", { credentials: "include" });
        if (reqR.ok) setRequests(await reqR.json());
      } catch {
        setError("Failed to load dashboard data.");
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [router]);

  if (loading) {
    return (
      <AppLayout persona="client">
        <div className="loading-line">Opening Client Workspace…</div>
      </AppLayout>
    );
  }

  const activeProjectsCount = requests.filter((r) => r.project_id).length;
  const proposalsCount = requests.reduce((acc, r) => acc + (r.proposals_count || 0), 0);
  const pendingRequestsCount = requests.filter((r) => r.status === "submitted" || r.status === "under_review").length;

  const headerActions = (
    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
      <Link href="/client/agencies" className="quiet-button">
        <Sparkles size={14} /> Browse Agencies
      </Link>
      <Link href="/client/requests/new" className="primary-button">
        <Plus size={15} /> New Project Brief
      </Link>
    </div>
  );

  return (
    <AppLayout persona="client" currentUser={user}>
      <PageHeader
        eyebrow="CLIENT / OVERVIEW"
        title={`Welcome back, ${user?.full_name || user?.email?.split("@")[0]}`}
        description={
          user?.company_name
            ? `${user.company_name} · Track creative briefs, review proposals, and approve video cuts.`
            : "Track your creative briefs, review agency proposals, and approve video deliverables."
        }
        actions={headerActions}
      />

      {error && (
        <div className="notice" style={{ borderColor: "rgba(255,119,125,.4)", background: "rgba(134,44,51,.3)" }}>
          <span>{error}</span>
        </div>
      )}

      {/* 4 Metric Cards */}
      <div className="kpi-row-4" style={{ marginBottom: "20px" }}>
        <MetricCard
          title="Active Briefs"
          value={requests.length}
          subtitle={`${pendingRequestsCount} awaiting proposal or review`}
          icon={FileText}
          variant="glow"
        />
        <MetricCard
          title="Agency Proposals"
          value={proposalsCount}
          subtitle="Received across all briefs"
          icon={Sparkles}
        />
        <MetricCard
          title="Active Projects"
          value={activeProjectsCount}
          subtitle="In video editing production"
          icon={FolderKanban}
        />
        <MetricCard
          title="Review Portal"
          value="Ready"
          subtitle="Timecode feedback active"
          icon={Film}
        />
      </div>

      {/* Quick Action Panels */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "14px",
          marginBottom: "20px",
        }}
      >
        <Link
          href="/client/agencies"
          className="panel"
          style={{
            padding: "20px 22px",
            display: "flex",
            alignItems: "center",
            gap: "16px",
            transition: ".2s",
            textDecoration: "none",
          }}
        >
          <div
            style={{
              width: "42px",
              height: "42px",
              borderRadius: "12px",
              background: "linear-gradient(145deg, #2c1a4b, #151424)",
              border: "1px solid rgba(164,90,255,.3)",
              display: "grid",
              placeItems: "center",
              color: "#d8b4fe",
              flexShrink: 0,
            }}
          >
            <Sparkles size={20} />
          </div>
          <div>
            <h3 style={{ margin: "0 0 3px", font: "600 14px var(--display)", color: "#fff" }}>
              Explore Agency Catalog
            </h3>
            <p style={{ margin: 0, fontSize: "11px", color: "#8a8ea1" }}>
              Find specialized post-production studios with proven portfolios.
            </p>
          </div>
          <ArrowRight size={16} color="var(--violet)" style={{ marginLeft: "auto" }} />
        </Link>

        <Link
          href="/portal"
          className="panel"
          style={{
            padding: "20px 22px",
            display: "flex",
            alignItems: "center",
            gap: "16px",
            transition: ".2s",
            textDecoration: "none",
          }}
        >
          <div
            style={{
              width: "42px",
              height: "42px",
              borderRadius: "12px",
              background: "linear-gradient(145deg, #1f274a, #121626)",
              border: "1px solid rgba(99,102,241,.3)",
              display: "grid",
              placeItems: "center",
              color: "#93c5fd",
              flexShrink: 0,
            }}
          >
            <Film size={20} />
          </div>
          <div>
            <h3 style={{ margin: "0 0 3px", font: "600 14px var(--display)", color: "#fff" }}>
              Video Review Portal
            </h3>
            <p style={{ margin: 0, fontSize: "11px", color: "#8a8ea1" }}>
              Leave timestamped notes, audio memos, and approve final deliverables.
            </p>
          </div>
          <ArrowRight size={16} color="var(--violet)" style={{ marginLeft: "auto" }} />
        </Link>
      </div>

      {/* Project Requests Section */}
      <section className="panel" style={{ padding: "20px 22px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "16px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span className="head-icon">
              <FileText size={15} />
            </span>
            <h2 style={{ margin: 0, font: "600 15px var(--display)", color: "#fff" }}>
              Your Project Briefs
            </h2>
          </div>
          <Link href="/client/requests/new" className="outline-action" style={{ textDecoration: "none" }}>
            <Plus size={13} /> Submit Brief
          </Link>
        </div>

        {requests.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No project briefs submitted yet"
            body="Discover an agency from our catalog or submit your first creative brief to receive custom proposals."
            action={
              <Link className="small-action" href="/client/agencies">
                Browse Agency Catalog <ArrowRight size={13} />
              </Link>
            }
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {requests.map((req) => (
              <Link
                key={req.id}
                href={`/client/requests/${req.id}`}
                className="panel"
                style={{
                  padding: "16px 18px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  background: "rgba(255,255,255,.02)",
                  textDecoration: "none",
                  transition: ".2s",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
                    <b style={{ color: "#fff", fontSize: "13px" }}>{req.title}</b>
                    <StatusPill status={req.status} />
                  </div>
                  <div style={{ fontSize: "11px", color: "#878b9f", display: "flex", gap: "12px", alignItems: "center" }}>
                    <span>Agency: <b style={{ color: "#cbd5e1" }}>{req.agency_name}</b></span>
                    <span>·</span>
                    <span>{req.proposals_count} {req.proposals_count === 1 ? "Proposal" : "Proposals"}</span>
                    <span>·</span>
                    <span>{new Date(req.created_at).toLocaleDateString()}</span>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  {req.project_id && (
                    <span
                      style={{
                        padding: "3px 8px",
                        borderRadius: "6px",
                        fontSize: "9px",
                        fontFamily: "var(--mono)",
                        background: "rgba(75,214,160,.12)",
                        border: "1px solid rgba(75,214,160,.35)",
                        color: "#5be3aa",
                      }}
                    >
                      Active Project #{req.project_id}
                    </span>
                  )}
                  <ArrowRight size={15} color="var(--violet)" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </AppLayout>
  );
}
