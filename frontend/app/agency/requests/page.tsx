"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Calendar,
  Clock,
  DollarSign,
  FileText,
  Filter,
  Film,
  FolderKanban,
  Inbox,
  LayoutDashboard,
  Layers,
  Sparkles,
  Tv,
} from "lucide-react";
import { AppLayout } from "@/components/shared/app-layout";
import { PageHeader } from "@/components/shared/page-header";
import { StatusPill } from "@/components/shared/status-pill";
import { EmptyState } from "@/components/shared/empty-state";

interface ProjectRequest {
  id: number;
  client_user_id: number;
  client_name: string;
  agency_workspace_id: number;
  agency_name: string;
  title: string;
  description: string;
  video_type: string;
  target_platform: string;
  budget: string;
  deadline?: string;
  status: string;
  project_id?: number;
  proposals_count: number;
  created_at: string;
}

export default function AgencyRequestsInboxPage() {
  const router = useRouter();
  const [requests, setRequests] = useState<ProjectRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const loadRequests = async () => {
    try {
      const res = await fetch("/api/agency/requests", { credentials: "include" });
      if (res.status === 401 || res.status === 403) {
        router.push("/agency/login");
        return;
      }
      if (res.ok) {
        setRequests(await res.json());
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered =
    filter === "all" ? requests : requests.filter((r) => r.status === filter);

  if (loading) {
    return (
      <AppLayout persona="agency">
        <div className="loading-line">Opening Incoming Requests…</div>
      </AppLayout>
    );
  }

  const filterAction = (
    <div className="filter-pills">
      {["all", "submitted", "under_review", "accepted", "declined"].map((s) => {
        const count =
          s === "all"
            ? requests.length
            : requests.filter((r) => r.status === s).length;
        return (
          <button
            key={s}
            className={filter === s ? "chosen" : ""}
            onClick={() => setFilter(s)}
          >
            {s.replace("_", " ")}
            <span>{count}</span>
          </button>
        );
      })}
    </div>
  );

  return (
    <AppLayout persona="agency">
      <PageHeader
        eyebrow="WORKSPACE / REQUESTS"
        title="Incoming Project Requests"
        description="Review incoming client briefs, submit custom proposals, and establish active production projects."
        actions={filterAction}
      />

      {filtered.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={filter === "all" ? "No incoming requests yet" : `No requests marked "${filter.replace("_", " ")}"`}
          body={
            filter === "all"
              ? "When clients discover your agency in the catalog, their project briefs will arrive here."
              : "Try switching filters to view other project briefs."
          }
          action={
            filter !== "all" ? (
              <button className="small-action" onClick={() => setFilter("all")}>
                View all requests <ArrowRight size={13} />
              </button>
            ) : (
              <Link className="small-action" href="/agency/profile">
                Publish agency profile to catalog <ArrowRight size={13} />
              </Link>
            )
          }
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {filtered.map((req) => (
            <Link
              key={req.id}
              href={`/agency/requests/${req.id}`}
              className="panel"
              style={{
                padding: "20px 22px",
                display: "block",
                transition: "all .2s ease",
                textDecoration: "none",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: "16px",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ flex: 1, minWidth: "280px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                    <h2 style={{ margin: 0, font: "600 16px var(--display)", color: "#fff" }}>
                      {req.title}
                    </h2>
                    <StatusPill status={req.status} />
                  </div>

                  <div style={{ fontSize: "11px", color: "#a5a9bd", marginBottom: "8px" }}>
                    Client: <b style={{ color: "#e2e3ec" }}>{req.client_name || `Client #${req.client_user_id}`}</b>
                  </div>

                  {req.description && (
                    <p
                      style={{
                        margin: "0 0 12px",
                        fontSize: "12px",
                        color: "#9498ab",
                        lineHeight: 1.5,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {req.description}
                    </p>
                  )}

                  <div style={{ display: "flex", flexWrap: "wrap", gap: "14px", fontSize: "11px", color: "#85899d" }}>
                    {req.video_type && (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
                        <Film size={13} color="var(--violet)" /> {req.video_type}
                      </span>
                    )}
                    {req.target_platform && (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
                        <Tv size={13} color="var(--violet)" /> {req.target_platform}
                      </span>
                    )}
                    {req.budget && (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
                        <DollarSign size={13} color="var(--green)" /> {req.budget}
                      </span>
                    )}
                    {req.deadline && (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
                        <Calendar size={13} color="#a57bd4" /> Due: {new Date(req.deadline).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                    justifyContent: "space-between",
                    gap: "10px",
                  }}
                >
                  <div style={{ fontSize: "11px", color: "var(--violet)", fontWeight: 600 }}>
                    {req.proposals_count > 0
                      ? `${req.proposals_count} Proposal submitted`
                      : "Review & Submit Proposal →"}
                  </div>

                  {req.project_id && (
                    <span
                      style={{
                        padding: "3px 8px",
                        borderRadius: "6px",
                        fontSize: "10px",
                        fontFamily: "var(--mono)",
                        background: "rgba(75,214,160,.12)",
                        border: "1px solid rgba(75,214,160,.35)",
                        color: "#5be3aa",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      ✓ Active Project #{req.project_id}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppLayout>
  );
}
