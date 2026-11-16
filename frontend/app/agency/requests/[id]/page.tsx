"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  DollarSign,
  Film,
  FileText,
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
  target_duration: string;
  aspect_ratio: string;
  editing_requirements: string;
  creative_direction: string;
  reference_links: string[];
  deliverables_format: string;
  budget: string;
  deadline?: string;
  status: string;
  project_id?: number;
  proposals_count: number;
  created_at: string;
}

interface Message {
  id: number;
  sender_name: string;
  sender_role: string;
  content: string;
  created_at: string;
}

export default function AgencyRequestDetailPage() {
  const params = useParams();
  const router = useRouter();
  const requestId = params.id as string;

  const [req, setReq] = useState<ProjectRequest | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);

  // Proposal form
  const [scopeDescription, setScopeDescription] = useState("");
  const [estimatedDays, setEstimatedDays] = useState(14);
  const [deliverablesSummary, setDeliverablesSummary] = useState("");
  const [proposalSubmitting, setProposalSubmitting] = useState(false);
  const [proposalMsg, setProposalMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Messaging form
  const [msgInput, setMsgInput] = useState("");
  const [sendingMsg, setSendingMsg] = useState(false);

  const loadData = async () => {
    try {
      const [rRes, mRes] = await Promise.all([
        fetch(`/api/agency/requests/${requestId}`, { credentials: "include" }),
        fetch(`/api/agency/requests/${requestId}/messages`, { credentials: "include" }),
      ]);
      if (rRes.status === 401 || rRes.status === 403) {
        router.push("/agency/login");
        return;
      }
      if (rRes.ok) {
        setReq(await rRes.json());
      }
      if (mRes.ok) {
        setMessages(await mRes.json());
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [requestId]); // eslint-disable-line react-hooks/exhaustive-deps

  const submitProposal = async (e: React.FormEvent) => {
    e.preventDefault();
    setProposalSubmitting(true);
    setProposalMsg(null);
    try {
      const res = await fetch(`/api/agency/requests/${requestId}/proposals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          scope_description: scopeDescription,
          estimated_days: Number(estimatedDays),
          deliverables_summary: deliverablesSummary,
        }),
      });
      if (res.ok) {
        setProposalMsg({ type: "success", text: "Proposal submitted successfully to client!" });
        setScopeDescription("");
        setDeliverablesSummary("");
        await loadData();
      } else {
        const err = await res.json();
        setProposalMsg({
          type: "error",
          text: typeof err.detail === "string" ? err.detail : "Failed to submit proposal",
        });
      }
    } catch {
      setProposalMsg({ type: "error", text: "Network error submitting proposal." });
    } finally {
      setProposalSubmitting(false);
    }
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!msgInput.trim()) return;
    setSendingMsg(true);
    try {
      const res = await fetch(`/api/requests/${requestId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          content: msgInput.trim(),
        }),
      });
      if (res.ok) {
        setMsgInput("");
        const refreshed = await fetch(`/api/requests/${requestId}/messages`, { credentials: "include" });
        if (refreshed.ok) setMessages(await refreshed.json());
      }
    } finally {
      setSendingMsg(false);
    }
  };

  if (loading) {
    return (
      <AppLayout persona="agency">
        <div className="loading-line">Opening Project Request…</div>
      </AppLayout>
    );
  }

  if (!req) {
    return (
      <AppLayout persona="agency">
        <div className="panel" style={{ padding: "40px 20px", textAlign: "center" }}>
          <p style={{ color: "#9295a8" }}>Project request not found.</p>
          <Link href="/agency/requests" className="primary-button" style={{ marginTop: "12px" }}>
            <ArrowLeft size={14} /> Back to Requests
          </Link>
        </div>
      </AppLayout>
    );
  }

  const headerActions = (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <Link href="/agency/requests" className="quiet-button">
        <ArrowLeft size={14} /> Requests Inbox
      </Link>
      {req.project_id && (
        <Link href={`/production?project=${req.project_id}`} className="primary-button">
          Open Production <ArrowRight size={14} />
        </Link>
      )}
    </div>
  );

  return (
    <AppLayout persona="agency">
      <PageHeader
        eyebrow={`WORKSPACE / REQUESTS / #${req.id}`}
        title={req.title}
        description={`Submitted by ${req.client_name || `User #${req.client_user_id}`} on ${new Date(req.created_at).toLocaleDateString()}`}
        actions={headerActions}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        {/* Brief Overview Panel */}
        <div className="panel" style={{ padding: "22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="head-icon">
                <FileText size={15} />
              </span>
              <h2 style={{ margin: 0, font: "600 16px var(--display)", color: "#fff" }}>
                Client Brief Specifications
              </h2>
            </div>
            <StatusPill status={req.status} />
          </div>

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
              <div style={{ color: "#f0f0f8", fontSize: "12px", fontWeight: 500, marginTop: "2px" }}>{req.video_type || "Standard"}</div>
            </div>
            <div>
              <small style={{ color: "#7e8297", fontSize: "10px", fontFamily: "var(--mono)", textTransform: "uppercase" }}>Target Platform</small>
              <div style={{ color: "#f0f0f8", fontSize: "12px", fontWeight: 500, marginTop: "2px" }}>{req.target_platform || "All Platforms"}</div>
            </div>
            <div>
              <small style={{ color: "#7e8297", fontSize: "10px", fontFamily: "var(--mono)", textTransform: "uppercase" }}>Target Duration</small>
              <div style={{ color: "#f0f0f8", fontSize: "12px", fontWeight: 500, marginTop: "2px" }}>{req.target_duration || "Flexible"}</div>
            </div>
            <div>
              <small style={{ color: "#7e8297", fontSize: "10px", fontFamily: "var(--mono)", textTransform: "uppercase" }}>Aspect Ratio</small>
              <div style={{ color: "#f0f0f8", fontSize: "12px", fontWeight: 500, marginTop: "2px" }}>{req.aspect_ratio || "16:9"}</div>
            </div>
            <div>
              <small style={{ color: "#7e8297", fontSize: "10px", fontFamily: "var(--mono)", textTransform: "uppercase" }}>Budget</small>
              <div style={{ color: "#5be3aa", fontSize: "12px", fontWeight: 600, marginTop: "2px" }}>{req.budget || "Open"}</div>
            </div>
            <div>
              <small style={{ color: "#7e8297", fontSize: "10px", fontFamily: "var(--mono)", textTransform: "uppercase" }}>Deadline</small>
              <div style={{ color: "#f0f0f8", fontSize: "12px", fontWeight: 500, marginTop: "2px" }}>
                {req.deadline ? new Date(req.deadline).toLocaleDateString() : "Flexible"}
              </div>
            </div>
          </div>

          {req.description && (
            <div style={{ marginBottom: "14px" }}>
              <b style={{ color: "#e2e3ec", fontSize: "12px", display: "block", marginBottom: "4px" }}>Project Scope & Goals:</b>
              <p style={{ margin: 0, color: "#cbd5e1", fontSize: "12px", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {req.description}
              </p>
            </div>
          )}

          {req.editing_requirements && (
            <div style={{ marginBottom: "14px" }}>
              <b style={{ color: "#e2e3ec", fontSize: "12px", display: "block", marginBottom: "4px" }}>Editing Requirements:</b>
              <p style={{ margin: 0, color: "#cbd5e1", fontSize: "12px", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {req.editing_requirements}
              </p>
            </div>
          )}

          {req.creative_direction && (
            <div>
              <b style={{ color: "#e2e3ec", fontSize: "12px", display: "block", marginBottom: "4px" }}>Creative Direction & References:</b>
              <p style={{ margin: 0, color: "#cbd5e1", fontSize: "12px", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {req.creative_direction}
              </p>
            </div>
          )}
        </div>

        {/* Submit Proposal Section */}
        {req.status !== "accepted" && req.status !== "declined" && (
          <section className="form-panel">
            <div className="form-section-title">
              <Sparkles size={16} color="var(--violet)" />
              <h3>Submit Agency Proposal</h3>
              <small>Deliverables & Estimates</small>
            </div>

            {proposalMsg && (
              <div
                className="notice"
                style={
                  proposalMsg.type === "error"
                    ? { borderColor: "rgba(255,119,125,.4)", background: "rgba(134,44,51,.3)" }
                    : undefined
                }
              >
                <span>{proposalMsg.text}</span>
                <button onClick={() => setProposalMsg(null)} aria-label="Dismiss">
                  <X size={14} />
                </button>
              </div>
            )}

            <form onSubmit={submitProposal} className="stack-form">
              <label>
                Scope & Deliverables Description <span style={{ color: "var(--violet)" }}>*</span>
                <textarea
                  name="scope_description"
                  required
                  rows={3}
                  value={scopeDescription}
                  onChange={(e) => setScopeDescription(e.target.value)}
                  placeholder="Outline what your agency will deliver, revision rounds, creative style, and milestones…"
                />
              </label>

              <div className="form-grid">
                <label>
                  Estimated Production Turnaround (Days) <span style={{ color: "var(--violet)" }}>*</span>
                  <input
                    name="estimated_days"
                    type="number"
                    required
                    min={1}
                    max={365}
                    value={estimatedDays}
                    onChange={(e) => setEstimatedDays(Number(e.target.value))}
                  />
                </label>

                <label>
                  Deliverables Summary
                  <input
                    name="deliverables_summary"
                    type="text"
                    value={deliverablesSummary}
                    onChange={(e) => setDeliverablesSummary(e.target.value)}
                    placeholder="e.g. 1x 4K Master, 2x Social Cuts (9:16), Captions"
                  />
                </label>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "6px" }}>
                <button type="submit" disabled={proposalSubmitting} className="primary-button">
                  {proposalSubmitting ? "Submitting Proposal…" : "Send Proposal to Client"}
                  <ArrowRight size={14} />
                </button>
              </div>
            </form>
          </section>
        )}

        {/* Messaging Thread */}
        <section className="form-panel">
          <div className="form-section-title">
            <MessageSquare size={16} color="var(--violet)" />
            <h3>Direct Client Discussion</h3>
            <small>Integrated Communication</small>
          </div>

          <div className="message-thread-box">
            {messages.length === 0 ? (
              <p style={{ margin: 0, padding: "20px", color: "#74788d", fontSize: "11px", textAlign: "center" }}>
                No messages yet. Send a note to align with the client on creative requirements.
              </p>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={`message-bubble ${m.sender_role === "agency" ? "agency" : "client"}`}
                >
                  <div className="message-author-row">
                    <b>{m.sender_name || (m.sender_role === "agency" ? "You (Agency)" : "Client")}</b>
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
              placeholder="Ask a question about creative direction, raw footage format, or budget…"
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
