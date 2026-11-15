"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

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

const STATUS_COLORS: Record<string, string> = {
  draft: "text-gray-400 bg-gray-800",
  submitted: "text-blue-300 bg-blue-900/40",
  under_review: "text-yellow-300 bg-yellow-900/40",
  proposal_received: "text-purple-300 bg-purple-900/40",
  accepted: "text-green-300 bg-green-900/40",
  declined: "text-red-300 bg-red-900/40",
  cancelled: "text-gray-500 bg-gray-800",
};

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
        if (!meR.ok) { router.push("/client/login"); return; }
        const me = await meR.json();
        if (me.role !== "client") { router.push("/client/login"); return; }
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

  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    router.push("/");
  };

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="text-gray-400">Loading…</div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold">
          <span className="text-white">FRAME</span><span className="text-blue-400">OPS</span>
        </Link>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">{user?.email}</span>
          <button onClick={handleLogout} className="text-sm text-gray-500 hover:text-white transition-colors">
            Sign out
          </button>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Welcome */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold">
            Welcome back, {user?.full_name || user?.email}
          </h1>
          {user?.company_name && (
            <p className="text-gray-400 text-sm mt-1">{user.company_name}</p>
          )}
        </div>

        {error && (
          <div className="mb-6 bg-red-900/30 border border-red-700/50 rounded-lg p-3 text-red-300 text-sm">
            {error}
          </div>
        )}

        {/* Quick actions */}
        <div className="grid sm:grid-cols-2 gap-4 mb-8">
          <Link
            href="/client/agencies"
            className="bg-gray-900 border border-gray-800 hover:border-blue-700/60 rounded-xl p-5 transition-colors group"
          >
            <div className="text-2xl mb-2">🔍</div>
            <div className="font-medium">Browse Agencies</div>
            <div className="text-gray-400 text-sm mt-1">Discover and compare video production agencies</div>
          </Link>
          <Link
            href="/client/requests/new"
            className="bg-blue-900/20 border border-blue-700/40 hover:border-blue-500 rounded-xl p-5 transition-colors group"
          >
            <div className="text-2xl mb-2">📋</div>
            <div className="font-medium text-blue-300">New Project Brief</div>
            <div className="text-gray-400 text-sm mt-1">Submit a project request to an agency</div>
          </Link>
        </div>

        {/* Project Requests */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Your Project Requests</h2>
            <Link href="/client/requests/new" className="text-sm text-blue-400 hover:text-blue-300">
              + New Request
            </Link>
          </div>

          {requests.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center text-gray-500">
              <div className="text-4xl mb-3">📭</div>
              <div className="font-medium mb-1">No project requests yet</div>
              <div className="text-sm">
                <Link href="/client/agencies" className="text-blue-400 hover:text-blue-300">
                  Browse agencies
                </Link>{" "}
                to submit your first project brief.
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {requests.map((req) => (
                <Link
                  key={req.id}
                  href={`/client/requests/${req.id}`}
                  className="block bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-xl p-5 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{req.title}</div>
                      <div className="text-gray-400 text-sm mt-0.5">{req.agency_name}</div>
                    </div>
                    <span className={`text-xs px-2 py-1 rounded-full font-medium whitespace-nowrap ${STATUS_COLORS[req.status] || "text-gray-400 bg-gray-800"}`}>
                      {req.status.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                    <span>{req.proposals_count} proposal{req.proposals_count !== 1 ? "s" : ""}</span>
                    <span>{new Date(req.created_at).toLocaleDateString()}</span>
                    {req.project_id && <span className="text-green-400">✓ Project created</span>}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
