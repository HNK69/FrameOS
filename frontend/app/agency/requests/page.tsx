"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

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

const STATUS_PILLS: Record<string, string> = {
  submitted: "bg-blue-900/40 text-blue-300 border-blue-700/50",
  under_review: "bg-yellow-900/40 text-yellow-300 border-yellow-700/50",
  proposal_received: "bg-purple-900/40 text-purple-300 border-purple-700/50",
  accepted: "bg-green-900/40 text-green-300 border-green-700/50",
  declined: "bg-red-900/40 text-red-300 border-red-700/50",
  cancelled: "bg-gray-800 text-gray-400 border-gray-700",
};

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

  const filtered = filter === "all"
    ? requests
    : requests.filter((r) => r.status === filter);

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
          <Link href="/agency/dashboard" className="text-sm text-gray-400 hover:text-white">
            Dashboard
          </Link>
          <Link href="/agency/profile" className="text-sm text-gray-400 hover:text-white">
            Agency Profile
          </Link>
          <Link href="/clients" className="text-sm text-gray-400 hover:text-white">
            Clients & Projects
          </Link>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold">Incoming Project Requests</h1>
            <p className="text-gray-400 text-sm mt-1">
              Review incoming client briefs, submit custom proposals, and establish active production projects.
            </p>
          </div>

          <div className="flex gap-2">
            {["all", "submitted", "under_review", "accepted", "declined"].map((s) => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border capitalize transition-colors ${
                  filter === s
                    ? "bg-purple-900/40 text-purple-200 border-purple-600"
                    : "bg-gray-900 text-gray-400 border-gray-800 hover:text-gray-200"
                }`}
              >
                {s.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="text-gray-400 text-center py-12">Loading requests…</div>
        ) : filtered.length === 0 ? (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center text-gray-500">
            <div className="text-4xl mb-3">📬</div>
            <div className="font-medium text-white mb-1">No requests found</div>
            <p className="text-sm text-gray-400 max-w-sm mx-auto">
              {filter === "all"
                ? "When clients discover your agency in the catalog, their briefs will arrive here."
                : `No requests with status "${filter}".`}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map((req) => (
              <Link
                key={req.id}
                href={`/agency/requests/${req.id}`}
                className="block bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-xl p-6 transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <h2 className="text-lg font-semibold text-white">{req.title}</h2>
                      <span
                        className={`text-xs px-2.5 py-0.5 rounded-full border font-medium ${
                          STATUS_PILLS[req.status] || "bg-gray-800 text-gray-400 border-gray-700"
                        }`}
                      >
                        {req.status.replace("_", " ")}
                      </span>
                    </div>

                    <p className="text-sm text-gray-400 mb-3">
                      From: <span className="text-gray-200 font-medium">{req.client_name || `Client #${req.client_user_id}`}</span>
                    </p>

                    {req.description && (
                      <p className="text-sm text-gray-300 line-clamp-2 mb-3">
                        {req.description}
                      </p>
                    )}

                    <div className="flex flex-wrap gap-4 text-xs text-gray-400">
                      {req.video_type && (
                        <span>Type: <span className="text-gray-200">{req.video_type}</span></span>
                      )}
                      {req.target_platform && (
                        <span>Platform: <span className="text-gray-200">{req.target_platform}</span></span>
                      )}
                      {req.budget && (
                        <span>Budget: <span className="text-gray-200">{req.budget}</span></span>
                      )}
                      {req.deadline && (
                        <span>Deadline: <span className="text-gray-200">{new Date(req.deadline).toLocaleDateString()}</span></span>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col sm:items-end justify-between self-stretch gap-2">
                    <div className="text-xs text-purple-400 font-medium">
                      {req.proposals_count > 0 ? `${req.proposals_count} Proposal submitted` : "Action needed →"}
                    </div>
                    {req.project_id && (
                      <span className="text-xs text-green-400 font-medium">
                        ✓ Active Project #{req.project_id}
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
