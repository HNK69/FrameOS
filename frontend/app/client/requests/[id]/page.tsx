"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

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

const STATUS_COLORS: Record<string, string> = {
  draft: "text-gray-400 bg-gray-800",
  submitted: "text-blue-300 bg-blue-900/40",
  under_review: "text-yellow-300 bg-yellow-900/40",
  accepted: "text-green-300 bg-green-900/40",
  declined: "text-red-300 bg-red-900/40",
};

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
      if (!reqR.ok) { router.push("/client/dashboard"); return; }
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

  useEffect(() => { load(); }, [reqId]); // eslint-disable-line react-hooks/exhaustive-deps

  const acceptProposal = async (proposalId: number) => {
    setActionLoading(proposalId);
    setError("");
    try {
      const r = await fetch(`/api/client/requests/${reqId}/proposals/${proposalId}/accept`, {
        method: "POST", credentials: "include",
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
        method: "POST", credentials: "include",
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

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">Loading…</div>
  );

  if (!request) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold">
          <span className="text-white">FRAME</span><span className="text-blue-400">OPS</span>
        </Link>
        <Link href="/client/dashboard" className="text-sm text-gray-400 hover:text-white">← Dashboard</Link>
      </nav>

      <div className="max-w-3xl mx-auto px-6 py-8">
        {error && (
          <div className="mb-4 bg-red-900/30 border border-red-700/50 rounded-lg p-3 text-red-300 text-sm">{error}</div>
        )}

        {/* Request details */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <h1 className="text-xl font-semibold">{request.title}</h1>
              <p className="text-gray-400 text-sm mt-0.5">Agency: {request.agency_name}</p>
            </div>
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_COLORS[request.status] || "text-gray-400 bg-gray-800"}`}>
              {request.status.replace(/_/g, " ")}
            </span>
          </div>

          {request.project_id && (
            <div className="mb-4 p-3 bg-green-900/20 border border-green-700/40 rounded-lg text-green-300 text-sm">
              ✓ Proposal accepted — Project #{request.project_id} has been created. The agency will now begin production.
            </div>
          )}

          <div className="grid sm:grid-cols-2 gap-3 text-sm">
            {request.description && (
              <div className="sm:col-span-2">
                <span className="text-gray-500">Description</span>
                <p className="text-gray-200 mt-1">{request.description}</p>
              </div>
            )}
            {request.video_type && <div><span className="text-gray-500">Video Type:</span> <span className="text-gray-200">{request.video_type}</span></div>}
            {request.target_platform && <div><span className="text-gray-500">Platform:</span> <span className="text-gray-200">{request.target_platform}</span></div>}
            {request.budget && <div><span className="text-gray-500">Budget:</span> <span className="text-gray-200">{request.budget}</span></div>}
            {request.deadline && <div><span className="text-gray-500">Deadline:</span> <span className="text-gray-200">{new Date(request.deadline).toLocaleDateString()}</span></div>}
          </div>
        </div>

        {/* Proposals */}
        <div>
          <h2 className="text-lg font-semibold mb-4">
            Proposals ({proposals.length})
          </h2>

          {proposals.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center text-gray-500">
              <div className="text-3xl mb-2">⏳</div>
              <div className="font-medium">Waiting for proposals</div>
              <div className="text-sm mt-1">The agency will review your brief and submit a proposal.</div>
            </div>
          ) : (
            <div className="space-y-4">
              {proposals.map((p) => (
                <div key={p.id} className={`bg-gray-900 border rounded-xl p-5 ${
                  p.status === "accepted" ? "border-green-700/50" :
                  p.status === "declined" ? "border-gray-800 opacity-60" :
                  "border-gray-800"
                }`}>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="font-medium">Proposal from {request.agency_name}</div>
                    <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                      p.status === "accepted" ? "text-green-300 bg-green-900/40" :
                      p.status === "declined" ? "text-gray-500 bg-gray-800" :
                      "text-yellow-300 bg-yellow-900/40"
                    }`}>
                      {p.status}
                    </span>
                  </div>

                  <p className="text-gray-300 text-sm mb-3">{p.scope_description}</p>
                  <div className="flex gap-4 text-sm text-gray-400 mb-3">
                    <span>⏱ {p.estimated_days} day{p.estimated_days !== 1 ? "s" : ""} estimated</span>
                  </div>
                  {p.deliverables_summary && (
                    <p className="text-gray-400 text-sm mb-3">{p.deliverables_summary}</p>
                  )}

                  {p.status === "pending" && request.status !== "accepted" && (
                    <div className="flex gap-3 mt-4 pt-4 border-t border-gray-800">
                      <button
                        onClick={() => acceptProposal(p.id)}
                        disabled={actionLoading === p.id}
                        className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                      >
                        {actionLoading === p.id ? "Accepting…" : "✓ Accept Proposal"}
                      </button>
                      <button
                        onClick={() => declineProposal(p.id)}
                        disabled={actionLoading === p.id}
                        className="px-4 py-2 border border-gray-700 hover:border-gray-500 rounded-lg text-sm text-gray-400 font-medium transition-colors disabled:opacity-50"
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
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mt-6">
          <h2 className="text-lg font-semibold mb-4">Direct Communication with Agency</h2>

          <div className="space-y-3 mb-6 max-h-80 overflow-y-auto pr-2">
            {messages.length === 0 ? (
              <p className="text-sm text-gray-500">No messages yet. Send a question or clarification to the agency.</p>
            ) : (
              messages.map((m: any) => (
                <div
                  key={m.id}
                  className={`p-3 rounded-lg text-sm ${
                    m.sender_role === "client"
                      ? "bg-blue-950/40 border border-blue-800/50 text-blue-200 ml-8"
                      : "bg-gray-800 text-gray-200 mr-8"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                    <span className="font-semibold text-white">
                      {m.sender_name || (m.sender_role === "client" ? "You (Client)" : "Agency")}
                    </span>
                    <span>{new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  <p>{m.content}</p>
                </div>
              ))
            )}
          </div>

          <form onSubmit={sendMessage} className="flex gap-2">
            <input
              type="text"
              value={msgInput}
              onChange={(e) => setMsgInput(e.target.value)}
              placeholder="Ask a question about the proposal or brief…"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={sendingMsg || !msgInput.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Send Message
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
