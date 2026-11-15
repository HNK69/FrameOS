"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

interface Agency {
  workspace_id: number;
  name: string;
  tagline: string;
  description: string;
  specializations: string[];
  services: string[];
  portfolio: { title: string; video_url: string; description: string }[];
  contact_email: string;
  contact_phone: string;
  website: string;
  published_at?: string;
}

export default function AgencyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.id as string;
  const [agency, setAgency] = useState<Agency | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    fetch(`/api/discovery/agencies/${workspaceId}`)
      .then(r => {
        if (r.status === 404) { setNotFound(true); return null; }
        return r.json();
      })
      .then(data => { if (data) setAgency(data); })
      .finally(() => setLoading(false));
  }, [workspaceId]);

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">Loading…</div>
  );

  if (notFound || !agency) return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center text-gray-400">
      <div className="text-5xl mb-4">404</div>
      <div className="text-lg font-medium mb-2">Agency not found</div>
      <Link href="/client/agencies" className="text-blue-400 hover:text-blue-300 text-sm">
        ← Back to agencies
      </Link>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold">
          <span className="text-white">FRAME</span><span className="text-blue-400">OPS</span>
        </Link>
        <Link href="/client/agencies" className="text-sm text-gray-400 hover:text-white">
          ← All Agencies
        </Link>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-10">
        {/* Hero */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-1">{agency.name}</h1>
          {agency.tagline && <p className="text-blue-400 text-lg">{agency.tagline}</p>}

          {agency.description && (
            <p className="text-gray-300 mt-4 leading-relaxed">{agency.description}</p>
          )}

          <Link
            href={`/client/requests/new?agency=${agency.workspace_id}&name=${encodeURIComponent(agency.name)}`}
            className="inline-flex items-center gap-2 mt-6 px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-medium transition-colors"
          >
            📋 Submit Project Brief to {agency.name}
          </Link>
        </div>

        {/* Specializations */}
        {agency.specializations.length > 0 && (
          <div className="mb-6">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Specializations</h2>
            <div className="flex flex-wrap gap-2">
              {agency.specializations.map(s => (
                <span key={s} className="text-sm bg-blue-900/30 text-blue-300 border border-blue-800/50 rounded-full px-3 py-1">
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Services */}
        {agency.services.length > 0 && (
          <div className="mb-6">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Services</h2>
            <div className="flex flex-wrap gap-2">
              {agency.services.map(s => (
                <span key={s} className="text-sm bg-gray-800 text-gray-300 rounded-full px-3 py-1">
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Portfolio */}
        {agency.portfolio.length > 0 && (
          <div className="mb-6">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Portfolio</h2>
            <div className="grid sm:grid-cols-2 gap-4">
              {agency.portfolio.map((item, i) => (
                <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <div className="font-medium mb-1">{item.title}</div>
                  {item.description && <p className="text-gray-400 text-sm">{item.description}</p>}
                  {item.video_url && (
                    <a href={item.video_url} target="_blank" rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
                      Watch →
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Contact */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="font-semibold mb-4">Contact</h2>
          <div className="space-y-2 text-sm">
            {agency.contact_email && (
              <div className="text-gray-300">📧 {agency.contact_email}</div>
            )}
            {agency.contact_phone && (
              <div className="text-gray-300">📞 {agency.contact_phone}</div>
            )}
            {agency.website && (
              <a href={agency.website} target="_blank" rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 block">
                🌐 {agency.website}
              </a>
            )}
          </div>
          <Link
            href={`/client/requests/new?agency=${agency.workspace_id}&name=${encodeURIComponent(agency.name)}`}
            className="inline-flex items-center gap-2 mt-5 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
          >
            Submit a Project Brief →
          </Link>
        </div>
      </div>
    </div>
  );
}
