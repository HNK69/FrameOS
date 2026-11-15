"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

function NewRequestForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preAgencyId = searchParams.get("agency") || "";
  const preAgencyName = searchParams.get("name") || "";

  const [form, setForm] = useState({
    agency_workspace_id: preAgencyId ? parseInt(preAgencyId) : 0,
    title: "",
    description: "",
    video_type: "",
    target_platform: "",
    target_duration: "",
    aspect_ratio: "",
    editing_requirements: "",
    creative_direction: "",
    deliverables_format: "",
    budget: "",
    deadline: "",
    status: "submitted" as "submitted" | "draft",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent, asDraft = false) => {
    e.preventDefault();
    if (!form.agency_workspace_id) { setError("Please select an agency first."); return; }
    setLoading(true);
    setError("");
    try {
      const r = await fetch("/api/client/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, status: asDraft ? "draft" : "submitted" }),
        credentials: "include",
      });
      if (!r.ok) {
        const data = await r.json();
        setError(typeof data.detail === "string" ? data.detail : "Failed to submit request");
        return;
      }
      const req = await r.json();
      router.push(`/client/requests/${req.id}`);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const field = (label: string, key: keyof typeof form, type = "text", required = false, placeholder = "") => (
    <div>
      <label className="block text-gray-300 text-sm font-medium mb-1">
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      <input
        type={type}
        required={required}
        value={form[key] as string}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
      />
    </div>
  );

  const textarea = (label: string, key: keyof typeof form, placeholder = "") => (
    <div>
      <label className="block text-gray-300 text-sm font-medium mb-1">{label}</label>
      <textarea
        value={form[key] as string}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        rows={3}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 resize-y"
      />
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold">
          <span className="text-white">FRAME</span><span className="text-blue-400">OPS</span>
        </Link>
        <Link href="/client/dashboard" className="text-sm text-gray-400 hover:text-white">← Dashboard</Link>
      </nav>

      <div className="max-w-2xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-semibold mb-1">New Project Brief</h1>
        {preAgencyName && (
          <p className="text-blue-400 text-sm mb-6">Submitting to: {preAgencyName}</p>
        )}

        <form onSubmit={e => handleSubmit(e, false)} className="space-y-5">
          {error && (
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-3 text-red-300 text-sm">{error}</div>
          )}

          {!preAgencyId && field("Agency Workspace ID", "agency_workspace_id", "number", true, "Enter workspace ID from agency discovery")}
          {field("Project Title", "title", "text", true, "e.g., Q4 Brand Video Campaign")}
          {textarea("Description", "description", "What do you need? Give the agency context about your project goals.")}
          {field("Video Type", "video_type", "text", false, "e.g., Brand Film, Social Reel, Corporate Training")}
          {field("Target Platform", "target_platform", "text", false, "e.g., YouTube, Instagram, LinkedIn")}
          {field("Target Duration", "target_duration", "text", false, "e.g., 60–90 seconds")}
          {field("Aspect Ratio", "aspect_ratio", "text", false, "e.g., 16:9, 9:16, 1:1")}
          {textarea("Editing Requirements", "editing_requirements", "Specific editing style, cuts, pacing requirements…")}
          {textarea("Creative Direction", "creative_direction", "Brand tone, visual style, music direction…")}
          {field("Deliverables Format", "deliverables_format", "text", false, "e.g., H.264 MP4, ProRes, with subtitle files")}
          {field("Budget", "budget", "text", false, "e.g., $3,000–$5,000 or open to quotes")}
          {field("Deadline", "deadline", "date", false)}

          <div className="flex gap-3 pt-2">
            <button
              type="button" disabled={loading}
              onClick={e => handleSubmit(e as unknown as React.FormEvent, true)}
              className="px-5 py-3 border border-gray-700 hover:border-gray-500 rounded-lg text-sm text-gray-300 font-medium transition-colors disabled:opacity-50"
            >
              Save as Draft
            </button>
            <button
              type="submit" disabled={loading}
              className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {loading ? "Submitting…" : "Submit Project Brief"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function NewRequestPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">Loading…</div>}>
      <NewRequestForm />
    </Suspense>
  );
}
