"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

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

  useEffect(() => { fetchAgencies(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchAgencies();
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold">
          <span className="text-white">FRAME</span><span className="text-blue-400">OPS</span>
        </Link>
        <div className="flex gap-3">
          <Link href="/client/dashboard" className="text-sm text-gray-400 hover:text-white transition-colors">
            ← Dashboard
          </Link>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-semibold mb-2">Browse Agencies</h1>
        <p className="text-gray-400 text-sm mb-6">
          Discover video production agencies and submit your project brief.
        </p>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex gap-3 mb-8">
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, description, tagline…"
            className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
          />
          <input
            type="text"
            value={specialization}
            onChange={e => setSpecialization(e.target.value)}
            placeholder="Specialization…"
            className="w-48 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
          >
            Search
          </button>
        </form>

        {/* Results */}
        {loading ? (
          <div className="text-gray-400 text-center py-16">Loading agencies…</div>
        ) : agencies.length === 0 ? (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center text-gray-500">
            <div className="text-4xl mb-3">🔍</div>
            <div className="font-medium mb-1">No agencies found</div>
            <div className="text-sm">Try adjusting your search terms.</div>
          </div>
        ) : (
          <div className="grid gap-4">
            {agencies.map((agency) => (
              <Link
                key={agency.workspace_id}
                href={`/client/agencies/${agency.workspace_id}`}
                className="block bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-xl p-6 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold">{agency.name}</h2>
                    {agency.tagline && (
                      <p className="text-blue-400 text-sm mt-0.5">{agency.tagline}</p>
                    )}
                    {agency.description && (
                      <p className="text-gray-400 text-sm mt-2 line-clamp-2">{agency.description}</p>
                    )}

                    <div className="flex flex-wrap gap-2 mt-3">
                      {agency.specializations.slice(0, 4).map((s) => (
                        <span key={s} className="text-xs bg-blue-900/30 text-blue-300 border border-blue-800/50 rounded-full px-2.5 py-0.5">
                          {s}
                        </span>
                      ))}
                      {agency.services.slice(0, 3).map((s) => (
                        <span key={s} className="text-xs bg-gray-800 text-gray-400 rounded-full px-2.5 py-0.5">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-blue-400 text-sm font-medium whitespace-nowrap">
                    View →
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
