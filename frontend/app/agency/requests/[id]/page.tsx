"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

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
        setProposalMsg({ type: "error", text: typeof err.detail === "string" ? err.detail : "Failed to submit proposal" });
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
      <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">
        Loading request…
      </div>
    );
  }

  if (!req) {
    return (
      <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center text-gray-400">
        <p>Project request not found.</p>
        <Link href="/agency/requests" className="text-purple-400 mt-2">
          ← Back to Inbox
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Top Navbar */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-xl font-bold">
            <span className="text-white">FRAME</span>
            <span className="text-purple-400">OPS</span>
          </Link>
          <span className="text-xs bg-purple-900/50 text-purple-300 border border-purple-700/50 px-2 py-0.5 rounded">
            Agency Studio
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/agency/requests" className="text-sm text-gray-400 hover:text-white">
            ← Requests Inbox
          </Link>
          <Link href="/clients" className="text-sm text-gray-400 hover:text-white">
            Clients & Projects
          </Link>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* Brief Header */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold">{req.title}</h1>
                <span className="text-xs px-2.5 py-0.5 rounded-full border border-purple-700/50 bg-purple-900/40 text-purple-300 font-medium">
                  {req.status.replace("_", " ")}
                </span>
              </div>
              <p className="text-sm text-gray-400 mt-1">
                Client: <span className="text-gray-200 font-medium">{req.client_name || `User #${req.client_user_id}`}</span> · Submitted on {new Date(req.created_at).toLocaleDateString()}
              </p>
            </div>

            {req.project_id && (
              <div className="bg-green-950/40 border border-green-800 text-green-300 px-3 py-2 rounded-lg text-sm">
                Active Project #{req.project_id}
                <Link href={`/production?project=${req.project_id}`} className="ml-2 underline text-green-200">
                  Open Production →
                </Link>
              </div>
            )}
          </div>

          <div className="border-t border-gray-800 pt-4 grid sm:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Video Type:</span>{" "}
              <span className="text-gray-200">{req.video_type || "Standard"}</span>
            </div>
            <div>
              <span className="text-gray-500">Target Platform:</span>{" "}
              <span className="text-gray-200">{req.target_platform || "All Platforms"}</span>
            </div>
            <div>
              <span className="text-gray-500">Duration:</span>{" "}
              <span className="text-gray-200">{req.target_duration || "Flexible"}</span>
            </div>
            <div>
              <span className="text-gray-500">Aspect Ratio:</span>{" "}
              <span className="text-gray-200">{req.aspect_ratio || "16:9"}</span>
            </div>
            <div>
              <span className="text-gray-500">Budget:</span>{" "}
              <span className="text-gray-200">{req.budget || "Open"}</span>
            </div>
            <div>
              <span className="text-gray-500">Deadline:</span>{" "}
              <span className="text-gray-200">
                {req.deadline ? new Date(req.deadline).toLocaleDateString() : "Flexible"}
              </span>
            </div>
          </div>

          {req.description && (
            <div className="mt-4 pt-4 border-t border-gray-800 text-sm">
              <span className="text-gray-500 font-medium block mb-1">Project Description:</span>
              <p className="text-gray-200 whitespace-pre-wrap">{req.description}</p>
            </div>
          )}

          {req.editing_requirements && (
            <div className="mt-4 pt-4 border-t border-gray-800 text-sm">
              <span className="text-gray-500 font-medium block mb-1">Editing Requirements:</span>
              <p className="text-gray-200 whitespace-pre-wrap">{req.editing_requirements}</p>
            </div>
          )}

          {req.creative_direction && (
            <div className="mt-4 pt-4 border-t border-gray-800 text-sm">
              <span className="text-gray-500 font-medium block mb-1">Creative Direction:</span>
              <p className="text-gray-200 whitespace-pre-wrap">{req.creative_direction}</p>
            </div>
          )}
        </div>

        {/* Submit Proposal Section */}
        {req.status !== "accepted" && req.status !== "declined" && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-2">Submit Agency Proposal</h2>
            <p className="text-gray-400 text-sm mb-4">
              Send your deliverables scope, turnaround estimate, and commercial terms to the client.
            </p>

            {proposalMsg && (
              <div
                className={`mb-4 p-3 rounded-lg text-sm border ${
                  proposalMsg.type === "success"
                    ? "bg-green-950/40 border-green-800 text-green-300"
                    : "bg-red-950/40 border-red-800 text-red-300"
                }`}
              >
                {proposalMsg.text}
              </div>
            )}

            <form onSubmit={submitProposal} className="space-y-4">
              <div>
                <label className="block text-gray-300 text-sm font-medium mb-1">
                  Scope Description <span className="text-purple-400">*</span>
                </label>
                <textarea
                  required
                  rows={3}
                  value={scopeDescription}
                  onChange={(e) => setScopeDescription(e.target.value)}
                  placeholder="Outline what your agency will deliver, revision rounds, creative style, and milestones…"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-gray-300 text-sm font-medium mb-1">
                    Estimated Production Days <span className="text-purple-400">*</span>
                  </label>
                  <input
                    type="number"
                    required
                    min={1}
                    max={365}
                    value={estimatedDays}
                    onChange={(e) => setEstimatedDays(Number(e.target.value))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div>
                  <label className="block text-gray-300 text-sm font-medium mb-1">
                    Deliverables Summary
                  </label>
                  <input
                    type="text"
                    value={deliverablesSummary}
                    onChange={(e) => setDeliverablesSummary(e.target.value)}
                    placeholder="e.g. 1x 4K Master, 2x Social Cuts (9:16), captions"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={proposalSubmitting}
                className="px-6 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {proposalSubmitting ? "Submitting…" : "Send Proposal to Client"}
              </button>
            </form>
          </div>
        )}

        {/* Messaging Thread */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Direct Communication</h2>

          <div className="space-y-3 mb-6 max-h-80 overflow-y-auto pr-2">
            {messages.length === 0 ? (
              <p className="text-sm text-gray-500">No messages yet. Send a note to the client.</p>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={`p-3 rounded-lg text-sm ${
                    m.sender_role === "agency"
                      ? "bg-purple-950/40 border border-purple-800/50 text-purple-200 ml-8"
                      : "bg-gray-800 text-gray-200 mr-8"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                    <span className="font-semibold text-white">
                      {m.sender_name || (m.sender_role === "agency" ? "You (Agency)" : "Client")}
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
              placeholder="Ask a question about the creative direction or budget…"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
            />
            <button
              type="submit"
              disabled={sendingMsg || !msgInput.trim()}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Send Message
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
