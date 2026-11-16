"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  DollarSign,
  FileCheck,
  FileText,
  Film,
  Layers,
  MessageSquare,
  Send,
  Sparkles,
  Tv,
  X,
} from "lucide-react";
import { AppLayout } from "@/components/shared/app-layout";
import { PageHeader } from "@/components/shared/page-header";
import { StatusPill } from "@/components/shared/status-pill";

interface Proposal {
  id: number;
  scope_description: string;
  estimated_days: number;
  deliverables_summary: string;
  status: string;
  created_at: string;
}

interface Request {
  id: number;
  title: string;
  agency_name: string;
  agency_workspace_id: number;
  status: string;
  description: string;
  video_type: string;
  target_platform: string;
  budget: string;
  deadline?: string;
  proposals_count: number;
  project_id?: number;
  created_at: string;
}

export default function RequestDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reqId = params.id as string;
  const [request, setRequest] = useState<Request | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [messages, setMessages] = useState<any[]>([]);
  const [msgInput, setMsgInput] = useState("");
  const [sendingMsg, setSendingMsg] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const [reqR, propR, msgR] = await Promise.all([
        fetch(`/api/client/requests/${reqId}`, { credentials: "include" }),
        fetch(`/api/client/requests/${reqId}/proposals`, { credentials: "include" }),
        fetch(`/api/requests/${reqId}/messages`, { credentials: "include" }),
      ]);
      if (!reqR.ok) {
        router.push("/client/dashboard");
        return;
      }
      setRequest(await reqR.json());
      if (propR.ok) setProposals(await propR.json());
      if (msgR.ok) setMessages(await msgR.json());
    } catch {
      setError("Failed to load request details.");
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!msgInput.trim()) return;
    setSendingMsg(true);
    try {
      const res = await fetch(`/api/requests/${reqId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ content: msgInput.trim() }),
      });
      if (res.ok) {
        setMsgInput("");
        const refreshed = await fetch(`/api/requests/${reqId}/messages`, { credentials: "include" });
        if (refreshed.ok) setMessages(await refreshed.json());
      }
    } finally {
      setSendingMsg(false);
    }
  };

  useEffect(() => {
    load();
  }, [reqId]); // eslint-disable-line react-hooks/exhaustive-deps

  const acceptProposal = async (proposalId: number) => {
    setActionLoading(proposalId);
    setError("");
    try {
      const r = await fetch(`/api/client/requests/${reqId}/proposals/${proposalId}/accept`, {
        method: "POST",
        credentials: "include",
      });
      if (!r.ok) {
        const data = await r.json();
        setError(typeof data.detail === "string" ? data.detail : "Failed to accept proposal");
      } else {
        await load();
      }
    } catch {
      setError("Network error.");
    } finally {
      setActionLoading(null);
    }
  };

  const declineProposal = async (proposalId: number) => {
    setActionLoading(proposalId);
    setError("");
    try {
      const r = await fetch(`/api/client/requests/${reqId}/proposals/${proposalId}/decline`, {
        method: "POST",
        credentials: "include",
      });
      if (!r.ok) {
        const data = await r.json();
        setError(typeof data.detail === "string" ? data.detail : "Failed to decline proposal");
      } else {
        await load();
      }
    } catch {
      setError("Network error.");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <AppLayout persona="client">
        <div className="loading-line">Opening Project Request…</div>
      </AppLayout>
    );
  }

  if (!request) {
    return (
      <AppLayout persona="client">
        <div className="panel" style={{ padding: "40px 20px", textAlign: "center" }}>
          <p style={{ color: "#9295a8" }}>Project request not found.</p>
          <Link href="/client/dashboard" className="primary-button" style={{ marginTop: "12px" }}>
            <ArrowLeft size={14} /> Back to Dashboard
          </Link>
        </div>
      </AppLayout>
    );
  }

  const headerActions = (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <Link href="/client/dashboard" className="quiet-button">
        <ArrowLeft size={14} /> Back to Dashboard
      </Link>
      {request.project_id && (
        <Link href={`/portal/projects/${request.project_id}`} className="primary-button">
          Open Review Portal <ArrowRight size={14} />
        </Link>
      )}
    </div>
  );

  return (
    <AppLayout persona="client">
      <PageHeader
        eyebrow={`CLIENT / REQUESTS / #${request.id}`}
        title={request.title}
        description={`Direct Brief to ${request.agency_name} · Submitted on ${new Date(request.created_at).toLocaleDateString()}`}
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

      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        {/* Request Details Panel */}
        <div className="panel" style={{ padding: "22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="head-icon">
                <FileText size={15} />
              </span>
              <h2 style={{ margin: 0, font: "600 16px var(--display)", color: "#fff" }}>
                Creative Brief Specifications
              </h2>
            </div>
            <StatusPill status={request.status} />
          </div>

          {request.project_id && (
            <div
              style={{
                padding: "12px 16px",
                borderRadius: "12px",
                background: "rgba(75,214,160,.12)",
                border: "1px solid rgba(75,214,160,.35)",
                color: "#6de4b2",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "16px",
              }}
            >
              <span>✓ Proposal accepted — Project #{request.project_id} has entered active production.</span>
              <Link
                href={`/portal/projects/${request.project_id}`}
                className="outline-action"
                style={{ borderColor: "rgba(75,214,160,.4)", color: "#6de4b2" }}
              >
                Open Review Portal <ArrowRight size={13} />
              </Link>
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "14px",
              padding: "16px",
              borderRadius: "14px",
              background: "rgba(0,0,0,.3)",
              border: "1px solid var(--line)",
              marginBottom: "16px",
            }}
          >
            <div>
              <small style={{ color: "#7e8297", fontSize: "10px", fontFamily: "var(--mono)", textTransform: "uppercase" }}>Video Type</small>
              <div style={{ color: "#f0f0f8", fontSize: "12px", fontWeight: 500, marginTop: "2px" }}>{request.video_type || "Standard"}</div>
            </div>
            <div>
              <small style={{ color: "#7e8297", fontSize: "10px", fontFamily: "var(--mono)", textTransform: "uppercase" }}>Target Platform</small>
              <div style={{ color: "#f0f0f8", fontSize: "12px", fontWeight: 500, marginTop: "2px" }}>{request.target_platform || "All Platforms"}</div>
            </div>
            <div>
              <small style={{ color: "#7e8297", fontSize: "10px", fontFamily: "var(--mono)", textTransform: "uppercase" }}>Target Budget</small>
              <div style={{ color: "#5be3aa", fontSize: "12px", fontWeight: 600, marginTop: "2px" }}>{request.budget || "Open Quote"}</div>
            </div>
            <div>
              <small style={{ color: "#7e8297", fontSize: "10px", fontFamily: "var(--mono)", textTransform: "uppercase" }}>Target Deadline</small>
              <div style={{ color: "#f0f0f8", fontSize: "12px", fontWeight: 500, marginTop: "2px" }}>
                {request.deadline ? new Date(request.deadline).toLocaleDateString() : "Flexible"}
              </div>
            </div>
          </div>

          {request.description && (
            <div>
              <b style={{ color: "#e2e3ec", fontSize: "12px", display: "block", marginBottom: "4px" }}>Brief Description:</b>
              <p style={{ margin: 0, color: "#cbd5e1", fontSize: "12px", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {request.description}
              </p>
            </div>
          )}
        </div>

        {/* Proposals Section */}
        <div className="panel" style={{ padding: "22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="head-icon">
                <Sparkles size={15} />
              </span>
              <h2 style={{ margin: 0, font: "600 16px var(--display)", color: "#fff" }}>
                Agency Proposals ({proposals.length})
              </h2>
            </div>
          </div>

          {proposals.length === 0 ? (
            <div style={{ padding: "30px 20px", textAlign: "center", color: "#8a8ea2" }}>
              <Clock size={28} color="var(--violet)" style={{ margin: "0 auto 8px" }} />
              <b style={{ color: "#fff", display: "block", fontSize: "13px" }}>Waiting for agency review</b>
              <p style={{ margin: "4px 0 0", fontSize: "11px", color: "#8a8ea2" }}>
                {request.agency_name} has received your brief and is preparing a tailored scope of work.
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {proposals.map((p) => (
                <div
                  key={p.id}
                  className="proposal-list-card"
                  style={
                    p.status === "accepted"
                      ? { borderColor: "rgba(75,214,160,.4)", background: "linear-gradient(150deg,rgba(16,36,26,.9),rgba(12,18,16,.95))" }
                      : p.status === "declined"
                      ? { opacity: 0.6 }
                      : undefined
                  }
                >
                  <div className="proposal-card-header">
                    <div>
                      <b style={{ color: "#fff", fontSize: "13px" }}>Proposal from {request.agency_name}</b>
                      <small style={{ color: "#8a8ea2", marginLeft: "10px", font: "9px var(--mono)" }}>
                        {new Date(p.created_at).toLocaleDateString()}
                      </small>
                    </div>
                    <StatusPill status={p.status} />
                  </div>

                  <p style={{ margin: 0, color: "#d1d5db", fontSize: "12px", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                    {p.scope_description}
                  </p>

                  <div style={{ display: "flex", alignItems: "center", gap: "16px", fontSize: "11px", color: "#a5a9bc" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                      <Clock size={13} color="var(--violet)" /> {p.estimated_days} Days Turnaround
                    </span>
                    {p.deliverables_summary && (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                        <Film size={13} color="var(--violet)" /> {p.deliverables_summary}
                      </span>
                    )}
                  </div>

                  {p.status === "pending" && request.status !== "accepted" && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        paddingTop: "14px",
                        borderTop: "1px solid var(--line)",
                        marginTop: "4px",
                      }}
                    >
                      <button
                        onClick={() => acceptProposal(p.id)}
                        disabled={actionLoading === p.id}
                        className="primary-button"
                        style={{ height: "36px", padding: "0 18px" }}
                      >
                        <Check size={14} />
                        {actionLoading === p.id ? "Accepting…" : "Accept Proposal & Begin Production"}
                      </button>
                      <button
                        onClick={() => declineProposal(p.id)}
                        disabled={actionLoading === p.id}
                        className="quiet-button"
                        style={{ height: "36px" }}
                      >
                        Decline
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Messaging Thread */}
        <section className="form-panel">
          <div className="form-section-title">
            <MessageSquare size={16} color="var(--violet)" />
            <h3>Direct Communication with {request.agency_name}</h3>
            <small>Brief Clarification & Notes</small>
          </div>

          <div className="message-thread-box">
            {messages.length === 0 ? (
              <p style={{ margin: 0, padding: "20px", color: "#74788d", fontSize: "11px", textAlign: "center" }}>
                No messages yet. Send a note or ask a question about scope and timelines.
              </p>
            ) : (
              messages.map((m: any) => (
                <div
                  key={m.id}
                  className={`message-bubble ${m.sender_role === "client" ? "agency" : "client"}`}
                >
                  <div className="message-author-row">
                    <b>{m.sender_name || (m.sender_role === "client" ? "You (Client)" : request.agency_name)}</b>
                    <span>{new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  <p style={{ margin: 0 }}>{m.content}</p>
                </div>
              ))
            )}
          </div>

          <form onSubmit={sendMessage} className="chat-input-bar">
            <input
              type="text"
              value={msgInput}
              onChange={(e) => setMsgInput(e.target.value)}
              placeholder="Ask a question about the proposal or creative deliverables…"
            />
            <button
              type="submit"
              disabled={sendingMsg || !msgInput.trim()}
              className="primary-button"
              style={{ height: "40px" }}
            >
              <Send size={14} />
              <span>Send</span>
            </button>
          </form>
        </section>
      </div>
    </AppLayout>
  );
}
