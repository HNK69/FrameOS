"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface AgencyProfile {
  id: number;
  workspace_id: number;
  workspace_name: string;
  tagline: string;
  description: string;
  specializations: string[];
  services: string[];
  portfolio: { title: string; video_url: string; description: string }[];
  contact_email: string;
  contact_phone: string;
  website: string;
  is_published: boolean;
  published_at?: string;
  is_ready_to_publish: boolean;
  missing_fields: string[];
}

export default function AgencyProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<AgencyProfile | null>(null);
  const [tagline, setTagline] = useState("");
  const [description, setDescription] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [website, setWebsite] = useState("");
  const [specInput, setSpecInput] = useState("");
  const [specializations, setSpecializations] = useState<string[]>([]);
  const [srvInput, setSrvInput] = useState("");
  const [services, setServices] = useState<string[]>([]);
  const [portfolioTitle, setPortfolioTitle] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");
  const [portfolioDesc, setPortfolioDesc] = useState("");
  const [portfolio, setPortfolio] = useState<{ title: string; video_url: string; description: string }[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchProfile = async () => {
    try {
      const res = await fetch("/api/agency/profile", { credentials: "include" });
      if (res.status === 401 || res.status === 403) {
        router.push("/agency/login");
        return;
      }
      if (res.ok) {
        const data: AgencyProfile = await res.json();
        setProfile(data);
        setTagline(data.tagline || "");
        setDescription(data.description || "");
        setContactEmail(data.contact_email || "");
        setContactPhone(data.contact_phone || "");
        setWebsite(data.website || "");
        setSpecializations(data.specializations || []);
        setServices(data.services || []);
        setPortfolio(data.portfolio || []);
      }
    } catch {
      setMessage({ type: "error", text: "Failed to load agency profile." });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch("/api/agency/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          tagline,
          description,
          contact_email: contactEmail,
          contact_phone: contactPhone,
          website,
          specializations,
          services,
          portfolio,
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        setProfile(updated);
        setMessage({ type: "success", text: "Profile updated successfully." });
      } else {
        const err = await res.json();
        setMessage({ type: "error", text: typeof err.detail === "string" ? err.detail : "Save failed" });
      }
    } catch {
      setMessage({ type: "error", text: "Network error while saving." });
    } finally {
      setSaving(false);
    }
  };

  const togglePublish = async () => {
    if (!profile) return;
    setPublishing(true);
    setMessage(null);
    try {
      const endpoint = profile.is_published
        ? "/api/agency/profile/unpublish"
        : "/api/agency/profile/publish";
      const res = await fetch(endpoint, { method: "POST", credentials: "include" });
      const data = await res.json();
      if (res.ok) {
        setMessage({
          type: "success",
          text: profile.is_published ? "Profile unpublished." : "Profile published to Discovery catalog!",
        });
        await fetchProfile();
      } else {
        const missing = data.detail?.missing_fields?.join(", ") || data.detail?.message || "Publishing check failed";
        setMessage({ type: "error", text: `Cannot publish: ${missing}` });
      }
    } catch {
      setMessage({ type: "error", text: "Failed to toggle publish status." });
    } finally {
      setPublishing(false);
    }
  };

  const addSpec = () => {
    if (specInput.trim() && !specializations.includes(specInput.trim())) {
      setSpecializations([...specializations, specInput.trim()]);
      setSpecInput("");
    }
  };

  const removeSpec = (idx: number) => {
    setSpecializations(specializations.filter((_, i) => i !== idx));
  };

  const addSrv = () => {
    if (srvInput.trim() && !services.includes(srvInput.trim())) {
      setServices([...services, srvInput.trim()]);
      setSrvInput("");
    }
  };

  const removeSrv = (idx: number) => {
    setServices(services.filter((_, i) => i !== idx));
  };

  const addPortfolioItem = () => {
    if (portfolioTitle.trim() && portfolioUrl.trim()) {
      setPortfolio([...portfolio, { title: portfolioTitle.trim(), video_url: portfolioUrl.trim(), description: portfolioDesc.trim() }]);
      setPortfolioTitle("");
      setPortfolioUrl("");
      setPortfolioDesc("");
    }
  };

  const removePortfolioItem = (idx: number) => {
    setPortfolio(portfolio.filter((_, i) => i !== idx));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">
        Loading agency profile…
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
          <Link href="/agency/dashboard" className="text-sm text-gray-400 hover:text-white">
            Dashboard
          </Link>
          <Link href="/agency/requests" className="text-sm text-gray-400 hover:text-white">
            Incoming Requests
          </Link>
          <Link href="/clients" className="text-sm text-gray-400 hover:text-white">
            Clients & Projects
          </Link>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold">{profile?.workspace_name || "Agency"} Profile</h1>
            <p className="text-gray-400 text-sm mt-1">
              Configure your public catalog listing and credentials for discovery by potential clients.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`text-xs px-3 py-1.5 rounded-full font-medium ${
                profile?.is_published
                  ? "bg-green-900/40 text-green-300 border border-green-700/50"
                  : "bg-yellow-900/40 text-yellow-300 border border-yellow-700/50"
              }`}
            >
              {profile?.is_published ? "● Published in Catalog" : "○ Draft (Unpublished)"}
            </span>
            <button
              onClick={togglePublish}
              disabled={publishing}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                profile?.is_published
                  ? "bg-gray-800 hover:bg-gray-700 text-gray-300"
                  : "bg-purple-600 hover:bg-purple-500 text-white"
              }`}
            >
              {publishing
                ? "Updating…"
                : profile?.is_published
                ? "Unpublish Profile"
                : "Publish to Catalog"}
            </button>
          </div>
        </div>

        {message && (
          <div
            className={`mb-6 p-4 rounded-lg text-sm border ${
              message.type === "success"
                ? "bg-green-950/40 border-green-800 text-green-300"
                : "bg-red-950/40 border-red-800 text-red-300"
            }`}
          >
            {message.text}
          </div>
        )}

        {profile && !profile.is_published && profile.missing_fields?.length > 0 && (
          <div className="mb-6 p-4 bg-yellow-950/30 border border-yellow-800/60 rounded-xl text-sm text-yellow-300">
            <span className="font-semibold">Publishing Checklist:</span> Complete the following required fields to publish:
            <ul className="list-disc list-inside mt-2 text-yellow-200">
              {profile.missing_fields.map((f) => (
                <li key={f}>{f.replace("_", " ")}</li>
              ))}
            </ul>
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-6">
          {/* General Information */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
            <h2 className="text-lg font-semibold">General Information</h2>

            <div>
              <label className="block text-gray-300 text-sm font-medium mb-1">Tagline</label>
              <input
                type="text"
                value={tagline}
                onChange={(e) => setTagline(e.target.value)}
                placeholder="e.g. Cinematic commercial editing & fast turnaround reels"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>

            <div>
              <label className="block text-gray-300 text-sm font-medium mb-1">
                Description <span className="text-purple-400">*</span>
              </label>
              <textarea
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe your agency, creative team, editing style, and production capabilities…"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-gray-300 text-sm font-medium mb-1">
                  Public Contact Email <span className="text-purple-400">*</span>
                </label>
                <input
                  type="email"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
                  placeholder="contact@agency.com"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-gray-300 text-sm font-medium mb-1">Contact Phone</label>
                <input
                  type="text"
                  value={contactPhone}
                  onChange={(e) => setContactPhone(e.target.value)}
                  placeholder="+1 (555) 000-0000"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-gray-300 text-sm font-medium mb-1">Website URL</label>
              <input
                type="url"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="https://agency.com"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          {/* Specializations & Services */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-6">
            <h2 className="text-lg font-semibold">Specializations & Services</h2>

            {/* Specializations */}
            <div>
              <label className="block text-gray-300 text-sm font-medium mb-1">
                Specializations <span className="text-purple-400">*</span>
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={specInput}
                  onChange={(e) => setSpecInput(e.target.value)}
                  placeholder="e.g. YouTube Creators, Commercials, Motion Graphics"
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addSpec();
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={addSpec}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-sm font-medium"
                >
                  Add
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {specializations.map((s, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-3 py-1 bg-purple-950/60 border border-purple-800/60 rounded-full text-xs text-purple-300"
                  >
                    {s}
                    <button
                      type="button"
                      onClick={() => removeSpec(idx)}
                      className="text-purple-400 hover:text-white"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Services */}
            <div>
              <label className="block text-gray-300 text-sm font-medium mb-1">
                Offered Services <span className="text-purple-400">*</span>
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={srvInput}
                  onChange={(e) => setSrvInput(e.target.value)}
                  placeholder="e.g. Color Grading, Sound Design, Subtitles, 4K Upscaling"
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addSrv();
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={addSrv}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-sm font-medium"
                >
                  Add
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {services.map((s, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-3 py-1 bg-gray-800 border border-gray-700 rounded-full text-xs text-gray-300"
                  >
                    {s}
                    <button
                      type="button"
                      onClick={() => removeSrv(idx)}
                      className="text-gray-400 hover:text-white"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Portfolio Items */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
            <h2 className="text-lg font-semibold">Portfolio Showcases</h2>
            <div className="grid sm:grid-cols-2 gap-3">
              <input
                type="text"
                value={portfolioTitle}
                onChange={(e) => setPortfolioTitle(e.target.value)}
                placeholder="Project title (e.g. Nike Brand Anthem)"
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              />
              <input
                type="url"
                value={portfolioUrl}
                onChange={(e) => setPortfolioUrl(e.target.value)}
                placeholder="Video URL (YouTube/Vimeo/Drive)"
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
              />
            </div>
            <textarea
              rows={2}
              value={portfolioDesc}
              onChange={(e) => setPortfolioDesc(e.target.value)}
              placeholder="Brief description of the work and scope…"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
            />
            <button
              type="button"
              onClick={addPortfolioItem}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-sm font-medium"
            >
              Add Portfolio Work
            </button>

            {portfolio.length > 0 && (
              <div className="space-y-3 pt-2">
                {portfolio.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-start justify-between bg-gray-800/60 border border-gray-700/60 p-3 rounded-lg"
                  >
                    <div>
                      <div className="font-medium text-sm text-white">{item.title}</div>
                      <a
                        href={item.video_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-purple-400 hover:underline"
                      >
                        {item.video_url}
                      </a>
                      {item.description && (
                        <p className="text-xs text-gray-400 mt-1">{item.description}</p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => removePortfolioItem(idx)}
                      className="text-red-400 hover:text-red-300 text-xs px-2 py-1"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
            >
              {saving ? "Saving Changes…" : "Save Agency Profile"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
