"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Download,
  FileQuestion,
  FileText,
  Film,
  HardDrive,
  HelpCircle,
  Image as ImageIcon,
  Music,
  Plus,
  ShieldAlert,
  Sparkles,
  Type,
  Upload,
  XCircle,
} from "lucide-react";
import { api } from "@/lib/api";

interface AssetIntelligencePanelProps {
  projectId: number;
  notify: (msg: string) => void;
}

export function AssetIntelligencePanel({ projectId, notify }: AssetIntelligencePanelProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<string>("all");
  const [uploadCategory, setUploadCategory] = useState<string>("reference");
  const [uploading, setUploading] = useState(false);

  const fetchAssetIntelligence = () => {
    if (!projectId) return;
    setLoading(true);
    api<any>(`/api/projects/${projectId}/asset-intelligence`)
      .then((res) => setData(res))
      .catch((err) => notify(err.message || "Failed to load asset intelligence"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAssetIntelligence();
  }, [projectId]);

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;

    setUploading(true);
    const form = new FormData();
    form.append("file", file);

    try {
      await api<any>(
        `/api/projects/${projectId}/assets?category=${encodeURIComponent(uploadCategory)}`,
        { method: "POST", body: form }
      );
      notify(`Asset "${file.name}" uploaded under ${uploadCategory} category.`);
      fetchAssetIntelligence();
    } catch (err: any) {
      notify(err.message || "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  const categoryIcons: Record<string, any> = {
    reference: ImageIcon,
    logo: Sparkles,
    font: Type,
    audio: Music,
    footage: Film,
    other: HardDrive,
  };

  if (loading && !data) {
    return <div className="panel asset-panel-loading">Inspecting physical asset storage & evidence...</div>;
  }

  const summary = data?.summary || {
    total_uploaded: 0,
    total_requirements: 0,
    present_count: 0,
    missing_count: 0,
    unknown_count: 0,
    unverified_count: 0,
    readiness_percentage: 0,
  };

  const filteredAssets = data?.uploaded_assets?.filter(
    (a: any) => activeCategory === "all" || a.category === activeCategory
  ) || [];

  const filteredRequirements = data?.extracted_requirements?.filter(
    (r: any) => activeCategory === "all" || r.category === activeCategory
  ) || [];

  return (
    <div className="asset-intelligence-layout">
      {/* Top Evidence Summary Strip */}
      <div className="panel asset-summary-card">
        <div className="summary-headline">
          <div className="headline-title">
            <span className="head-icon"><HardDrive size={16} /></span>
            <div>
              <h3>Project Asset Intelligence</h3>
              <small>Evidence-based verification · Never claims existence without storage proof</small>
            </div>
          </div>

          <div className="upload-quick-bar">
            <select
              value={uploadCategory}
              onChange={(e) => setUploadCategory(e.target.value)}
              aria-label="Upload asset category"
            >
              <option value="reference">Reference Assets</option>
              <option value="logo">Brand Logos</option>
              <option value="font">Fonts & Typography</option>
              <option value="audio">Music & Audio</option>
              <option value="footage">Video Footage</option>
              <option value="other">Other Resources</option>
            </select>

            <label className="primary-button upload-btn">
              <Upload size={14} />
              <span>{uploading ? "Uploading..." : "Upload Asset"}</span>
              <input
                type="file"
                disabled={uploading}
                onChange={handleFileUpload}
                accept="image/*,video/*,audio/*,.pdf,.txt,.md,.woff,.woff2,.ttf,.otf,.svg,.ai"
              />
            </label>
          </div>
        </div>

        {/* Readiness Meter */}
        <div className="readiness-meter">
          <div className="meter-label">
            <span>Asset Coverage Readiness</span>
            <b>{summary.readiness_percentage}% Verified</b>
          </div>
          <div className="meter-bar">
            <div className="meter-fill" style={{ width: `${summary.readiness_percentage}%` }} />
          </div>
        </div>

        {/* Status Counters Strip */}
        <div className="status-counter-grid">
          <div className="counter-box present">
            <div className="counter-top">
              <CheckCircle2 size={14} />
              <span>Present</span>
            </div>
            <strong>{summary.present_count}</strong>
            <small>Verified on disk</small>
          </div>

          <div className="counter-box missing">
            <div className="counter-top">
              <XCircle size={14} />
              <span>Missing</span>
            </div>
            <strong>{summary.missing_count}</strong>
            <small>Needed by cut</small>
          </div>

          <div className="counter-box unknown">
            <div className="counter-top">
              <HelpCircle size={14} />
              <span>Unknown</span>
            </div>
            <strong>{summary.unknown_count}</strong>
            <small>Unconfirmed refs</small>
          </div>

          <div className="counter-box unverified">
            <div className="counter-top">
              <ShieldAlert size={14} />
              <span>Unverified</span>
            </div>
            <strong>{summary.unverified_count}</strong>
            <small>Pending validation</small>
          </div>
        </div>
      </div>

      {/* Category Navigation Pills */}
      <div className="category-filter-strip">
        <button
          className={`cat-pill ${activeCategory === "all" ? "active" : ""}`}
          onClick={() => setActiveCategory("all")}
        >
          All Asset Types <span>{summary.total_uploaded + summary.total_requirements}</span>
        </button>

        {data?.category_breakdown?.map((cat: any) => {
          const Icon = categoryIcons[cat.key] || HardDrive;
          return (
            <button
              key={cat.key}
              className={`cat-pill ${activeCategory === cat.key ? "active" : ""}`}
              onClick={() => setActiveCategory(cat.key)}
            >
              <Icon size={13} />
              <span>{cat.label}</span>
              <small>{cat.uploaded_count}</small>
            </button>
          );
        })}
      </div>

      {/* Two Column Asset & Requirement View */}
      <div className="asset-grid-split">
        {/* Uploaded Physical Assets */}
        <section className="panel asset-subpanel">
          <div className="card-head">
            <div className="card-title">
              <span className="head-icon"><CheckCircle2 size={15} /></span>
              <h2>Verified Project Assets ({filteredAssets.length})</h2>
            </div>
            <span className="card-meta">PHYSICAL STORAGE PROOF</span>
          </div>

          {filteredAssets.length > 0 ? (
            <div className="asset-items-list">
              {filteredAssets.map((a: any) => {
                const Icon = categoryIcons[a.category] || HardDrive;
                return (
                  <article key={a.id} className="asset-card-row">
                    <div className="asset-icon-box">
                      <Icon size={16} />
                    </div>

                    <div className="asset-details">
                      <div className="asset-header-row">
                        <b className="asset-filename" title={a.filename}>{a.filename}</b>
                        <span className={`evidence-badge ${a.status}`}>
                          {a.status === "Present" && <Check size={11} />}
                          {a.status}
                        </span>
                      </div>

                      <div className="asset-evidence-text">
                        <span>{a.evidence}</span>
                      </div>

                      <div className="asset-footer-row">
                        <small className="asset-meta">
                          {a.category_label} · {a.size_bytes ? `${Math.round(a.size_bytes / 1024)} KB` : "—"} · {a.content_type}
                        </small>
                        <a
                          href={a.download_url}
                          download={a.filename}
                          className="download-link"
                          title="Download verified asset"
                        >
                          <Download size={13} />
                          <span>Download</span>
                        </a>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">
              <HardDrive size={22} />
              <b>No uploaded assets in this category</b>
              <p>Upload files above to establish evidence of presence in this project.</p>
            </div>
          )}
        </section>

        {/* Extracted Asset Requirements from Feedback */}
        <section className="panel asset-subpanel">
          <div className="card-head">
            <div className="card-title">
              <span className="head-icon"><FileQuestion size={15} /></span>
              <h2>Extracted Requirements ({filteredRequirements.length})</h2>
            </div>
            <span className="card-meta">TRANSCRIPT DERIVED</span>
          </div>

          {filteredRequirements.length > 0 ? (
            <div className="asset-items-list">
              {filteredRequirements.map((r: any) => {
                const Icon = categoryIcons[r.category] || HardDrive;
                return (
                  <article key={r.id} className="asset-card-row requirement-row">
                    <div className="asset-icon-box req">
                      <Icon size={16} />
                    </div>

                    <div className="asset-details">
                      <div className="asset-header-row">
                        <b className="asset-filename">{r.name}</b>
                        <span className={`evidence-badge ${r.status}`}>
                          {r.status}
                        </span>
                      </div>

                      {r.source_quote && (
                        <blockquote className="req-quote">
                          “{r.source_quote}”
                        </blockquote>
                      )}

                      <div className="asset-evidence-text">
                        <small>Evidence: {r.evidence}</small>
                      </div>

                      <div className="asset-footer-row">
                        <small className="asset-meta">
                          {r.category_label} · {Math.round(r.confidence * 100)}% confidence
                        </small>
                        {r.matched_filename && (
                          <span className="matched-chip">
                            Matched: {r.matched_filename}
                          </span>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">
              <FileText size={22} />
              <b>No extracted asset requirements</b>
              <p>When client transcripts are processed, referenced assets will appear here with evidence verification.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
