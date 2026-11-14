"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  AudioLines,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  ExternalLink,
  Eye,
  FileAudio,
  FileCheck,
  FileText,
  Film,
  FolderKanban,
  HelpCircle,
  Info,
  Layers,
  Lock,
  LogOut,
  Maximize2,
  MessageSquare,
  MessageSquareQuote,
  Mic,
  MicOff,
  MoreVertical,
  Pause,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Send,
  Shield,
  Sliders,
  Sparkles,
  Trash2,
  Upload,
  User,
  Volume2,
  VolumeX,
  Wand2,
  X,
  XCircle,
} from "lucide-react";
import { api, json } from "@/lib/api";

export type PortalClient = {
  id: number;
  name: string;
  brand: string;
  industry: string;
  description: string;
};

export type ReviewVersion = {
  id: number;
  project_id: number;
  version_label: string;
  video_asset_id: number | null;
  video_url: string;
  status: string;
  change_summary: string;
  created_at: string;
};

export type VideoComment = {
  id: number;
  project_id: number;
  review_version_id: number | null;
  timestamp_seconds: number;
  timecode: string;
  author_name: string;
  content: string;
  status: string;
  created_at: string;
};

export type FeedbackItem = {
  id?: string;
  description: string;
  category: string;
  classification: "explicit" | "inferred";
  confidence: number;
  requires_confirmation: boolean;
  client_confirmed: boolean;
  actionable_cut_note?: string;
};

export type FeedbackSubmission = {
  id: number;
  project_id: number;
  review_version_id: number | null;
  feedback_type: string;
  author_name: string;
  content: string;
  items: FeedbackItem[];
  audio_asset_id: number | null;
  status: "submitted" | "processing" | "awaiting_confirmation" | "delivered" | "resolved";
  review_decision: string | null;
  created_at: string;
};

export type PortalProject = {
  id: number;
  name: string;
  description: string;
  status: string;
  due_date: string | null;
  created_at: string;
  client_name: string;
  brand: string;
  current_version: ReviewVersion;
  submissions_count: number;
  comments_count: number;
  unresolved_comments_count: number;
  versions?: ReviewVersion[];
  comments?: VideoComment[];
  feedback_submissions?: FeedbackSubmission[];
  assets?: any[];
};

export function ClientPortal({ initialProjectId }: { initialProjectId?: number }) {
  const [token, setToken] = useState<string>("");
  const [client, setClient] = useState<PortalClient | null>(null);
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<PortalProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(initialProjectId || null);
  const [activeProject, setActiveProject] = useState<PortalProject | null>(null);
  const [activeTab, setActiveTab] = useState<"review" | "brief" | "voice" | "pipeline" | "assets">("review");
  const [notice, setNotice] = useState<string>("");
  const [errorNotice, setErrorNotice] = useState<string>("");

  // Modals
  const [draftModalOpen, setDraftModalOpen] = useState(false);
  const [decisionModalOpen, setDecisionModalOpen] = useState<"approve" | "changes_requested" | "reject" | null>(null);
  const [draftData, setDraftData] = useState<{
    summary: string;
    requests: FeedbackItem[];
    ambiguities: string[];
    missing_information: string[];
    production_risks: string[];
    originalContent: string;
    feedbackType: string;
    audioAssetId?: number | null;
  } | null>(null);

  // Check initial token from URL or localStorage
  useEffect(() => {
    const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
    const urlToken = params?.get("token") || params?.get("code") || "";
    const storedToken = typeof window !== "undefined" ? localStorage.getItem("frameops_portal_token") || "" : "";
    const effectiveToken = urlToken || storedToken;

    if (effectiveToken) {
      setToken(effectiveToken);
      fetchClientData(effectiveToken);
    } else {
      // Try cookie-based session
      api<{ client: PortalClient }>("/api/portal/auth/me")
        .then((res) => {
          setClient(res.client);
          loadProjects();
        })
        .catch(() => {
          setLoading(false);
        });
    }
  }, []);

  async function fetchClientData(authToken: string) {
    setLoading(true);
    try {
      // Try login endpoint if token looks like access code or raw token
      let authedClient: PortalClient | null = null;
      try {
        const loginRes = await api<any>("/api/portal/auth/login", {
          ...json("POST", { token: authToken, code: authToken }),
          headers: { "X-Portal-Token": authToken },
        });
        authedClient = loginRes.client;
        if (loginRes.token) {
          localStorage.setItem("frameops_portal_token", loginRes.token);
          setToken(loginRes.token);
        }
      } catch {
        // Fallback to me
        const meRes = await api<{ client: PortalClient }>("/api/portal/auth/me", {
          headers: { "X-Portal-Token": authToken, Authorization: `Bearer ${authToken}` },
        });
        authedClient = meRes.client;
      }

      setClient(authedClient);
      await loadProjects(authToken);
    } catch (e: any) {
      setErrorNotice(e.message || "Failed to authenticate client portal access.");
      setClient(null);
    } finally {
      setLoading(false);
    }
  }

  async function loadProjects(overrideToken?: string) {
    const t = overrideToken || token;
    const headers: Record<string, string> = {};
    if (t) {
      headers["X-Portal-Token"] = t;
      headers["Authorization"] = `Bearer ${t}`;
    }
    try {
      const projs = await api<PortalProject[]>("/api/portal/projects", { headers });
      setProjects(projs);
      if (projs.length > 0) {
        const match = selectedProjectId ? projs.find((p) => p.id === selectedProjectId) : projs[0];
        const chosen = match || projs[0];
        setSelectedProjectId(chosen.id);
        await loadProjectDetail(chosen.id, t);
      }
    } catch (e: any) {
      setErrorNotice(e.message);
    }
  }

  async function loadProjectDetail(projectId: number, overrideToken?: string) {
    const t = overrideToken || token;
    const headers: Record<string, string> = {};
    if (t) {
      headers["X-Portal-Token"] = t;
      headers["Authorization"] = `Bearer ${t}`;
    }
    try {
      const detail = await api<PortalProject>(`/api/portal/projects/${projectId}`, { headers });
      setActiveProject(detail);
    } catch (e: any) {
      setErrorNotice(e.message);
    }
  }

  function handleSelectProject(projId: number) {
    setSelectedProjectId(projId);
    loadProjectDetail(projId);
  }

  async function logout() {
    try {
      await api("/api/portal/auth/logout", json("POST"));
    } catch {}
    localStorage.removeItem("frameops_portal_token");
    setToken("");
    setClient(null);
    setActiveProject(null);
    setProjects([]);
  }

  if (loading) {
    return (
      <main className="portal-container">
        <div className="portal-loading">
          <div className="portal-spinner" />
          <span>Accessing FRAMEOPS Secure Client Portal…</span>
        </div>
      </main>
    );
  }

  if (!client) {
    return (
      <PortalAuthGate
        onSuccess={(authToken, authedClient) => {
          setToken(authToken);
          setClient(authedClient);
          localStorage.setItem("frameops_portal_token", authToken);
          loadProjects(authToken);
        }}
      />
    );
  }

  return (
    <div className="portal-shell">
      {/* Top Header */}
      <header className="portal-header">
        <div className="portal-header-left">
          <div className="portal-brand-badge">
            <div className="portal-logo-orb">
              <span>F</span>
            </div>
            <div>
              <div className="portal-brand-title">FRAMEOPS</div>
              <div className="portal-brand-sub">CLIENT REVIEW PORTAL</div>
            </div>
          </div>

          <div className="portal-client-chip">
            <span className="portal-client-avatar">{client.name.slice(0, 1).toUpperCase()}</span>
            <div className="portal-client-meta">
              <b>{client.name}</b>
              <small>{client.brand || "Client Workspace"}</small>
            </div>
          </div>
        </div>

        <div className="portal-header-center">
          {projects.length > 1 ? (
            <div className="portal-project-selector">
              <label>Project:</label>
              <select
                value={selectedProjectId || ""}
                onChange={(e) => handleSelectProject(Number(e.target.value))}
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.current_version?.version_label || "v1"})
                  </option>
                ))}
              </select>
            </div>
          ) : activeProject ? (
            <div className="portal-single-project-title">
              <Film size={16} />
              <span>{activeProject.name}</span>
            </div>
          ) : null}
        </div>

        <div className="portal-header-right">
          <button
            className="portal-quiet-btn"
            onClick={() => {
              if (selectedProjectId) loadProjectDetail(selectedProjectId);
              setNotice("Refreshed project status and comments.");
            }}
            title="Refresh"
          >
            <RefreshCw size={15} />
            <span className="desktop-only">Refresh</span>
          </button>
          <button className="portal-logout-btn" onClick={logout} title="Sign Out">
            <LogOut size={15} />
            <span className="desktop-only">Sign out</span>
          </button>
        </div>
      </header>

      {/* Global Alerts */}
      {notice && (
        <div className="portal-notice">
          <span>{notice}</span>
          <button onClick={() => setNotice("")}>
            <X size={14} />
          </button>
        </div>
      )}
      {errorNotice && (
        <div className="portal-error-notice">
          <AlertCircle size={15} />
          <span>{errorNotice}</span>
          <button onClick={() => setErrorNotice("")}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* Main Portal View */}
      {activeProject ? (
        <main className="portal-main">
          {/* Project Overview Banner */}
          <section className="portal-overview-card">
            <div className="portal-overview-top">
              <div className="portal-overview-info">
                <div className="portal-eyebrow">
                  ACTIVE DELIVERABLE · DUE{" "}
                  {activeProject.due_date ? new Date(activeProject.due_date).toLocaleDateString() : "UPON REVIEW"}
                </div>
                <h2>{activeProject.name}</h2>
                <p>{activeProject.description || "Video cut in review. Submit notes, record voice feedback, or approve."}</p>
              </div>

              <div className="portal-overview-version-badge">
                <span className="portal-version-tag">
                  <Layers size={13} />
                  {activeProject.current_version?.version_label || "v1 - Initial Cut"}
                </span>
                <span className={`portal-status-badge ${activeProject.current_version?.status || activeProject.status}`}>
                  <span className="portal-status-dot" />
                  {formatStatus(activeProject.current_version?.status || activeProject.status)}
                </span>
              </div>
            </div>

            {/* Quick Metrics Bar */}
            <div className="portal-stats-row">
              <div className="portal-stat-pill">
                <Clock size={13} />
                <span>Status:</span>
                <b>{formatStatus(activeProject.status)}</b>
              </div>
              <div className="portal-stat-pill">
                <MessageSquare size={13} />
                <span>Comments:</span>
                <b>
                  {activeProject.unresolved_comments_count} open / {activeProject.comments_count} total
                </b>
              </div>
              <div className="portal-stat-pill">
                <FileCheck size={13} />
                <span>Feedback Rounds:</span>
                <b>{activeProject.submissions_count} submitted</b>
              </div>
            </div>

            {/* Executive Client Action Bar */}
            <div className="portal-action-dock">
              <button
                className="portal-action-btn portal-btn-approve"
                onClick={() => setDecisionModalOpen("approve")}
              >
                <CheckCircle2 size={16} />
                <span>Approve Cut</span>
              </button>
              <button
                className="portal-action-btn portal-btn-changes"
                onClick={() => setDecisionModalOpen("changes_requested")}
              >
                <MessageSquareQuote size={16} />
                <span>Request Changes</span>
              </button>
              <button
                className="portal-action-btn portal-btn-reject"
                onClick={() => setDecisionModalOpen("reject")}
              >
                <XCircle size={16} />
                <span>Reject Version</span>
              </button>
            </div>
          </section>

          {/* Navigation Tabs */}
          <div className="portal-nav-tabs">
            <button
              className={`portal-tab ${activeTab === "review" ? "active" : ""}`}
              onClick={() => setActiveTab("review")}
            >
              <Film size={15} />
              <span>Video Review & Comments</span>
              {activeProject.unresolved_comments_count > 0 && (
                <span className="portal-tab-count">{activeProject.unresolved_comments_count}</span>
              )}
            </button>
            <button
              className={`portal-tab ${activeTab === "brief" ? "active" : ""}`}
              onClick={() => setActiveTab("brief")}
            >
              <FileText size={15} />
              <span>Written Brief / Notes</span>
            </button>
            <button
              className={`portal-tab ${activeTab === "voice" ? "active" : ""}`}
              onClick={() => setActiveTab("voice")}
            >
              <Mic size={15} />
              <span>Voice Feedback Recording</span>
            </button>
            <button
              className={`portal-tab ${activeTab === "pipeline" ? "active" : ""}`}
              onClick={() => setActiveTab("pipeline")}
            >
              <Layers size={15} />
              <span>Feedback Pipeline</span>
              {activeProject.submissions_count > 0 && (
                <span className="portal-tab-count">{activeProject.submissions_count}</span>
              )}
            </button>
            <button
              className={`portal-tab ${activeTab === "assets" ? "active" : ""}`}
              onClick={() => setActiveTab("assets")}
            >
              <FolderKanban size={15} />
              <span>Assets & Deliverables ({activeProject.assets?.length || 0})</span>
            </button>
          </div>

          {/* Tab Views */}
          <div className="portal-tab-content">
            {activeTab === "review" && (
              <VideoReviewStudio
                project={activeProject}
                token={token}
                onCommentsUpdated={() => loadProjectDetail(activeProject.id)}
                onRequestChanges={() => setDecisionModalOpen("changes_requested")}
                onApprove={() => setDecisionModalOpen("approve")}
              />
            )}

            {activeTab === "brief" && (
              <TextFeedbackStudio
                project={activeProject}
                token={token}
                onDraftReady={(draft) => {
                  setDraftData(draft);
                  setDraftModalOpen(true);
                }}
              />
            )}

            {activeTab === "voice" && (
              <VoiceFeedbackStudio
                project={activeProject}
                token={token}
                onDraftReady={(draft) => {
                  setDraftData(draft);
                  setDraftModalOpen(true);
                }}
              />
            )}

            {activeTab === "pipeline" && (
              <FeedbackPipelineView
                project={activeProject}
                token={token}
                onRefresh={() => loadProjectDetail(activeProject.id)}
              />
            )}

            {activeTab === "assets" && (
              <ProjectAssetsView
                project={activeProject}
                token={token}
              />
            )}
          </div>
        </main>
      ) : (
        <div className="portal-empty-projects">
          <Film size={36} />
          <h3>No assigned projects found</h3>
          <p>Your studio team has not yet linked a production project to your account.</p>
        </div>
      )}

      {/* AI Structured Feedback Review Modal (Screen 7) */}
      {draftModalOpen && draftData && activeProject && (
        <StructuredFeedbackModal
          draft={draftData}
          project={activeProject}
          token={token}
          onClose={() => setDraftModalOpen(false)}
          onSubmitted={() => {
            setDraftModalOpen(false);
            setNotice("Your feedback has been structured and submitted directly to the editing queue.");
            loadProjectDetail(activeProject.id);
            setActiveTab("pipeline");
          }}
        />
      )}

      {/* Client Decision Modal (Approve, Request Changes, Reject) */}
      {decisionModalOpen && activeProject && (
        <DecisionModal
          decisionType={decisionModalOpen}
          project={activeProject}
          token={token}
          onClose={() => setDecisionModalOpen(null)}
          onSubmitted={(msg) => {
            setDecisionModalOpen(null);
            setNotice(msg);
            loadProjectDetail(activeProject.id);
          }}
        />
      )}
    </div>
  );
}

// ==============================================================================
// 1. CLIENT AUTHENTICATION GATE
// ==============================================================================

function PortalAuthGate({ onSuccess }: { onSuccess: (token: string, client: PortalClient) => void }) {
  const [accessCode, setAccessCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!accessCode.trim()) return;
    setBusy(true);
    setError("");

    try {
      const res = await api<any>("/api/portal/auth/login", {
        ...json("POST", { token: accessCode.trim(), code: accessCode.trim() }),
      });
      onSuccess(res.token || accessCode.trim(), res.client);
    } catch (e: any) {
      setError(e.message || "Invalid client access code or token.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="portal-auth-container">
      <div className="portal-auth-card">
        <div className="portal-auth-brand">
          <div className="portal-logo-orb large">
            <span>F</span>
          </div>
          <div className="portal-eyebrow">CREATIVE PRODUCTION & CLIENT OPERATIONS</div>
          <h1>Client Portal Access</h1>
          <p>Review cuts, submit timestamped revisions, record voice notes, and approve deliverables.</p>
        </div>

        <form onSubmit={submit} className="portal-auth-form">
          <label>
            <span>Client Access Key or Passcode</span>
            <div className="portal-input-icon-wrap">
              <Lock size={15} />
              <input
                required
                value={accessCode}
                onChange={(e) => setAccessCode(e.target.value)}
                placeholder="Enter client passcode or access token…"
              />
            </div>
            <small>Provided by your FRAMEOPS video editing agency or studio director.</small>
          </label>

          {error && (
            <div className="portal-auth-error">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}

          <button className="portal-auth-submit" disabled={busy || !accessCode.trim()}>
            {busy ? "Validating access…" : "Enter Client Portal"}
            <ArrowRight size={16} />
          </button>
        </form>

        <div className="portal-auth-footer">
          <Shield size={14} />
          <span>Strict client-level data isolation. Project assets and feedback are private to your organization.</span>
        </div>
      </div>
    </main>
  );
}

// ==============================================================================
// 2. VIDEO REVIEW STUDIO (WITH TIMESTAMPTED COMMENTS & SCRUBBING)
// ==============================================================================

function VideoReviewStudio({
  project,
  token,
  onCommentsUpdated,
  onRequestChanges,
  onApprove,
}: {
  project: PortalProject;
  token: string;
  onCommentsUpdated: () => void;
  onRequestChanges: () => void;
  onApprove: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(90); // default 90s fallback
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [newCommentText, setNewCommentText] = useState("");
  const [authorName, setAuthorName] = useState("Client Director");
  const [isAddingComment, setIsAddingComment] = useState(false);
  const [commentTimecode, setCommentTimecode] = useState("00:00");
  const [commentSeconds, setCommentSeconds] = useState(0);
  const [commentFilter, setCommentFilter] = useState<"all" | "unresolved">("unresolved");
  const [submittingComment, setSubmittingComment] = useState(false);

  // Video source: check if project has video assets
  const videoAsset = project.assets?.find((a) => a.content_type?.startsWith("video/") || a.category === "footage");
  const videoSrc = project.current_version?.video_url || (videoAsset ? videoAsset.stream_url : "");

  // Update time as video plays
  function handleTimeUpdate() {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      if (videoRef.current.duration && !isNaN(videoRef.current.duration)) {
        setDuration(videoRef.current.duration);
      }
    }
  }

  function togglePlay() {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  }

  function seekTo(seconds: number) {
    if (!videoRef.current) return;
    videoRef.current.currentTime = Math.max(0, Math.min(seconds, duration));
    setCurrentTime(seconds);
  }

  function skip(delta: number) {
    seekTo(currentTime + delta);
  }

  function changeSpeed(rate: number) {
    setPlaybackRate(rate);
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
  }

  function openAddComment() {
    if (videoRef.current && isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    }
    const tc = formatTimecode(currentTime);
    setCommentTimecode(tc);
    setCommentSeconds(currentTime);
    setIsAddingComment(true);
  }

  async function submitComment(e: React.FormEvent) {
    e.preventDefault();
    if (!newCommentText.trim()) return;
    setSubmittingComment(true);

    try {
      await api(`/api/portal/projects/${project.id}/comments`, {
        ...json("POST", {
          timestamp_seconds: commentSeconds,
          timecode: commentTimecode,
          content: newCommentText.trim(),
          author_name: authorName,
          version_id: project.current_version?.id || null,
        }),
        headers: { "X-Portal-Token": token, Authorization: `Bearer ${token}` },
      });
      setNewCommentText("");
      setIsAddingComment(false);
      onCommentsUpdated();
    } catch (e: any) {
      alert(e.message || "Failed to add comment.");
    } finally {
      setSubmittingComment(false);
    }
  }

  async function toggleResolveComment(commentId: number, currentStatus: string) {
    const nextStatus = currentStatus === "resolved" ? "submitted" : "resolved";
    try {
      await api(`/api/portal/projects/${project.id}/comments/${commentId}?status=${nextStatus}`, {
        method: "PATCH",
        headers: { "X-Portal-Token": token, Authorization: `Bearer ${token}` },
      });
      onCommentsUpdated();
    } catch (e: any) {
      alert(e.message);
    }
  }

  const comments = project.comments || [];
  const filteredComments =
    commentFilter === "all" ? comments : comments.filter((c) => c.status !== "resolved");

  return (
    <div className="portal-review-grid">
      {/* Video Player Column */}
      <div className="portal-video-column">
        <div className="portal-video-wrapper">
          {videoSrc ? (
            <video
              ref={videoRef}
              src={videoSrc}
              className="portal-video-element"
              onTimeUpdate={handleTimeUpdate}
              onEnded={() => setIsPlaying(false)}
              onLoadedMetadata={() => {
                if (videoRef.current?.duration) setDuration(videoRef.current.duration);
              }}
              onClick={togglePlay}
            />
          ) : (
            <div className="portal-video-placeholder" onClick={togglePlay}>
              <div className="portal-placeholder-glow" />
              <Film size={44} />
              <h4>{project.current_version?.version_label || "v1 Review Cut"}</h4>
              <p>Interactive Review Canvas</p>
              <div className="portal-placeholder-timecode">{formatTimecode(currentTime)}</div>
              <small>Click to simulate video playback or upload a review cut in Assets.</small>
            </div>
          )}

          {/* Video Control Bar */}
          <div className="portal-video-controls">
            {/* Timeline Scrub Bar with Timestamp Markers */}
            <div
              className="portal-scrubber-track"
              onClick={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const pos = (e.clientX - rect.left) / rect.width;
                seekTo(pos * duration);
              }}
            >
              <div
                className="portal-scrubber-progress"
                style={{ width: `${(currentTime / Math.max(duration, 1)) * 100}%` }}
              />
              <div
                className="portal-scrubber-playhead"
                style={{ left: `${(currentTime / Math.max(duration, 1)) * 100}%` }}
              />

              {/* Timestamp Comment Pins on Timeline */}
              {comments.map((c) => {
                const pinLeft = Math.min(100, Math.max(0, (c.timestamp_seconds / Math.max(duration, 1)) * 100));
                return (
                  <div
                    key={c.id}
                    className={`portal-timeline-pin ${c.status === "resolved" ? "resolved" : ""}`}
                    style={{ left: `${pinLeft}%` }}
                    onClick={(e) => {
                      e.stopPropagation();
                      seekTo(c.timestamp_seconds);
                    }}
                    title={`${c.timecode} — ${c.author_name}: “${c.content}”`}
                  >
                    <span className="portal-pin-dot" />
                  </div>
                );
              })}
            </div>

            {/* Playback Buttons */}
            <div className="portal-controls-row">
              <div className="portal-controls-left">
                <button className="portal-ctrl-btn" onClick={togglePlay} title={isPlaying ? "Pause" : "Play"}>
                  {isPlaying ? <Pause size={17} /> : <Play size={17} />}
                </button>
                <button className="portal-ctrl-btn" onClick={() => skip(-5)} title="Rewind 5s">
                  <RotateCcw size={15} />
                </button>
                <button className="portal-ctrl-btn" onClick={() => skip(5)} title="Fast-forward 5s">
                  <RotateCcw size={15} style={{ transform: "scaleX(-1)" }} />
                </button>

                <div className="portal-timecode-display">
                  <b>{formatTimecode(currentTime)}</b>
                  <span>/ {formatTimecode(duration)}</span>
                </div>
              </div>

              <div className="portal-controls-right">
                <div className="portal-speed-selector">
                  {[1, 1.25, 1.5, 2].map((speed) => (
                    <button
                      key={speed}
                      className={playbackRate === speed ? "active" : ""}
                      onClick={() => changeSpeed(speed)}
                    >
                      {speed}x
                    </button>
                  ))}
                </div>

                <button
                  className="portal-ctrl-btn"
                  onClick={() => {
                    setIsMuted(!isMuted);
                    if (videoRef.current) videoRef.current.muted = !isMuted;
                  }}
                  title={isMuted ? "Unmute" : "Mute"}
                >
                  {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
                </button>

                <button
                  className="portal-comment-trigger-btn"
                  onClick={openAddComment}
                >
                  <MessageSquare size={14} />
                  <span>Comment at {formatTimecode(currentTime)}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Inline Add Comment Form */}
        {isAddingComment && (
          <form className="portal-comment-form" onSubmit={submitComment}>
            <div className="portal-comment-form-header">
              <div className="portal-comment-tc-badge">
                <Clock size={13} />
                <span>Timestamp: {commentTimecode}</span>
              </div>
              <input
                className="portal-comment-author-input"
                value={authorName}
                onChange={(e) => setAuthorName(e.target.value)}
                placeholder="Your name / title"
              />
              <button
                type="button"
                className="portal-icon-close"
                onClick={() => setIsAddingComment(false)}
              >
                <X size={14} />
              </button>
            </div>
            <textarea
              required
              rows={2}
              value={newCommentText}
              onChange={(e) => setNewCommentText(e.target.value)}
              placeholder={`Write specific revision instructions at ${commentTimecode} (e.g. "Cut audio track before beat drop", "Brighten product shot")…`}
              autoFocus
            />
            <div className="portal-comment-form-actions">
              <small>Clicking on any saved comment jumps directly to that timestamp in the video.</small>
              <button
                type="submit"
                className="portal-primary-action-btn"
                disabled={submittingComment || !newCommentText.trim()}
              >
                <Send size={13} />
                <span>{submittingComment ? "Saving…" : "Post Comment"}</span>
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Timestamped Comments Sidebar */}
      <div className="portal-comments-sidebar">
        <div className="portal-sidebar-head">
          <div className="portal-sidebar-title">
            <MessageSquare size={16} />
            <h3>Timestamped Notes</h3>
            <span className="portal-pill-badge">{comments.length}</span>
          </div>
          <div className="portal-filter-pills">
            <button
              className={commentFilter === "unresolved" ? "active" : ""}
              onClick={() => setCommentFilter("unresolved")}
            >
              Open ({comments.filter((c) => c.status !== "resolved").length})
            </button>
            <button
              className={commentFilter === "all" ? "active" : ""}
              onClick={() => setCommentFilter("all")}
            >
              All
            </button>
          </div>
        </div>

        <div className="portal-comments-list">
          {filteredComments.length > 0 ? (
            filteredComments.map((c) => (
              <div
                key={c.id}
                className={`portal-comment-card ${c.status === "resolved" ? "resolved" : ""}`}
                onClick={() => seekTo(c.timestamp_seconds)}
              >
                <div className="portal-comment-card-top">
                  <span className="portal-comment-badge" title="Click to jump to timecode">
                    <Play size={10} />
                    {c.timecode}
                  </span>
                  <span className="portal-comment-author">{c.author_name}</span>
                  <button
                    className={`portal-resolve-toggle ${c.status === "resolved" ? "is-resolved" : ""}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleResolveComment(c.id, c.status);
                    }}
                    title={c.status === "resolved" ? "Reopen comment" : "Mark resolved"}
                  >
                    <Check size={12} />
                    <span>{c.status === "resolved" ? "Resolved" : "Resolve"}</span>
                  </button>
                </div>
                <p className="portal-comment-text">{c.content}</p>
              </div>
            ))
          ) : (
            <div className="portal-comments-empty">
              <MessageSquare size={26} />
              <b>No comments yet</b>
              <p>Play the video and click “Comment at MM:SS” to pin frame-specific revision notes.</p>
              <button className="portal-quiet-btn" onClick={openAddComment}>
                <Plus size={13} /> Add first comment
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// 3. TEXT-BASED CREATIVE BRIEFS & FEEDBACK SUBMISSION
// ==============================================================================

function TextFeedbackStudio({
  project,
  token,
  onDraftReady,
}: {
  project: PortalProject;
  token: string;
  onDraftReady: (draft: any) => void;
}) {
  const [content, setContent] = useState("");
  const [feedbackType, setFeedbackType] = useState<"text" | "brief">("text");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const templates = [
    "Trim opening scene by 2 seconds to make the intro faster.",
    "Warm up the color grading in the evening exterior shots.",
    "Make the background music quieter during dialogue scenes.",
    "Add animated lower-third title card with company name at 00:15.",
  ];

  async function handleExtract(e: React.FormEvent) {
    e.preventDefault();
    if (content.trim().length < 10) return;
    setBusy(true);
    setError("");

    try {
      const draft = await api<any>(`/api/portal/projects/${project.id}/feedback/draft`, {
        ...json("POST", { feedback_type: feedbackType, content: content.trim() }),
        headers: { "X-Portal-Token": token, Authorization: `Bearer ${token}` },
      });

      onDraftReady({
        ...draft,
        originalContent: content.trim(),
        feedbackType,
      });
    } catch (e: any) {
      setError(e.message || "Failed to analyze feedback with AI.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="portal-form-panel">
      <div className="portal-panel-heading">
        <div className="portal-panel-title">
          <FileText size={18} />
          <div>
            <h3>Submit Creative Feedback or Project Brief</h3>
            <p>Our AI will structure your instructions into actionable requirements for you to review and confirm.</p>
          </div>
        </div>
      </div>

      <div className="portal-type-toggle">
        <button
          className={feedbackType === "text" ? "active" : ""}
          onClick={() => setFeedbackType("text")}
        >
          <MessageSquareQuote size={14} />
          <span>Cut Revision Feedback</span>
        </button>
        <button
          className={feedbackType === "brief" ? "active" : ""}
          onClick={() => setFeedbackType("brief")}
        >
          <FileText size={14} />
          <span>New Creative Brief</span>
        </button>
      </div>

      <form onSubmit={handleExtract} className="portal-feedback-form">
        <div className="portal-textarea-wrap">
          <div className="portal-textarea-header">
            <span>{feedbackType === "text" ? "Feedback Notes & Direction" : "Creative Brief Details"}</span>
            <small>{content.length} characters</small>
          </div>
          <textarea
            required
            minLength={10}
            rows={7}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={
              feedbackType === "text"
                ? "Describe what you would like adjusted in this cut (e.g. pacing, sound mix, titles, color grade, scene order)…"
                : "Describe your goals, audience, brand tone, key message, preferred music vibe, and target deliverable specs…"
            }
          />
        </div>

        {/* Quick Suggestion Chips */}
        <div className="portal-quick-chips">
          <span>Quick ideas:</span>
          {templates.map((tpl, idx) => (
            <button
              key={idx}
              type="button"
              className="portal-chip"
              onClick={() => setContent((prev) => (prev ? `${prev}\n${tpl}` : tpl))}
            >
              + {tpl.slice(0, 36)}…
            </button>
          ))}
        </div>

        {error && (
          <div className="portal-error-notice">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        <div className="portal-form-submit-row">
          <div className="portal-ai-helper-text">
            <Sparkles size={14} />
            <span>AI will organize your notes into structured tasks before you submit.</span>
          </div>
          <button
            type="submit"
            className="portal-primary-action-btn large"
            disabled={busy || content.trim().length < 10}
          >
            <Wand2 size={16} />
            <span>{busy ? "Analyzing with AI…" : "Review Structured Feedback"}</span>
            <ArrowRight size={15} />
          </button>
        </div>
      </form>
    </div>
  );
}

// ==============================================================================
// 4. VOICE FEEDBACK RECORDING / UPLOAD (SCREEN 4)
// ==============================================================================

function VoiceFeedbackStudio({
  project,
  token,
  onDraftReady,
}: {
  project: PortalProject;
  token: string;
  onDraftReady: (draft: any) => void;
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [notesSummary, setNotesSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Cleanup audio preview URL on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [audioUrl]);

  async function startRecording() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mr.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        setAudioBlob(blob);
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        stream.getTracks().forEach((track) => track.stop());
      };

      mr.start(250);
      setIsRecording(true);
      setRecordingTime(0);

      timerRef.current = setInterval(() => {
        setRecordingTime((t) => t + 1);
      }, 1000);
    } catch (e: any) {
      setError("Microphone permission denied or audio device not found.");
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setAudioBlob(file);
    const url = URL.createObjectURL(file);
    setAudioUrl(url);
  }

  async function processVoiceFeedback(e: React.FormEvent) {
    e.preventDefault();
    if (!audioBlob) return;
    setBusy(true);
    setError("");

    try {
      // 1. Upload audio asset to backend
      const form = new FormData();
      form.append("file", audioBlob, "voice_feedback.webm");

      const uploadRes = await api<any>(`/api/portal/projects/${project.id}/voice`, {
        method: "POST",
        body: form,
        headers: { "X-Portal-Token": token, Authorization: `Bearer ${token}` },
      });

      // 2. Draft AI structured requirements from audio summary or spoken notes
      const promptText =
        notesSummary.trim() ||
        `Voice feedback recording (${formatTimecode(recordingTime || 30)}) from client for ${project.name}. Contains creative revision instructions on pacing, tone, and sound design.`;

      const draft = await api<any>(`/api/portal/projects/${project.id}/feedback/draft`, {
        ...json("POST", { feedback_type: "voice", content: promptText }),
        headers: { "X-Portal-Token": token, Authorization: `Bearer ${token}` },
      });

      onDraftReady({
        ...draft,
        originalContent: promptText,
        feedbackType: "voice",
        audioAssetId: uploadRes.asset_id,
      });
    } catch (e: any) {
      setError(e.message || "Failed to process voice feedback.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="portal-voice-panel">
      <div className="portal-panel-heading">
        <div className="portal-panel-title">
          <Mic size={18} />
          <div>
            <h3>Voice Feedback Studio</h3>
            <p>Speak your creative feedback naturally. Record directly or upload an audio voice memo.</p>
          </div>
        </div>
      </div>

      <div className="portal-voice-body">
        {/* Recording Interface */}
        <div className="portal-recorder-box">
          <div className="portal-recorder-visualizer">
            {isRecording ? (
              <div className="portal-waveform-active">
                {[...Array(16)].map((_, i) => (
                  <span
                    key={i}
                    className="portal-waveform-bar"
                    style={{
                      height: `${Math.max(15, Math.floor(Math.sin(i + recordingTime * 2) * 45 + 50))}%`,
                    }}
                  />
                ))}
              </div>
            ) : audioUrl ? (
              <div className="portal-recorded-preview">
                <CheckCircle2 size={32} className="text-emerald" />
                <span>Voice Note Ready ({formatTimecode(recordingTime)})</span>
                <audio controls src={audioUrl} className="portal-audio-player" />
              </div>
            ) : (
              <div className="portal-waveform-idle">
                <Mic size={36} />
                <span>Click Record to speak your revision notes</span>
              </div>
            )}
          </div>

          <div className="portal-recorder-controls">
            {isRecording ? (
              <button
                type="button"
                className="portal-record-btn active"
                onClick={stopRecording}
              >
                <div className="portal-stop-square" />
                <span>Stop Recording ({formatTimecode(recordingTime)})</span>
              </button>
            ) : (
              <button
                type="button"
                className="portal-record-btn"
                onClick={startRecording}
              >
                <Mic size={16} />
                <span>{audioUrl ? "Record Again" : "Start Voice Recording"}</span>
              </button>
            )}

            <span className="portal-or-divider">OR</span>

            <label className="portal-upload-voice-btn">
              <Upload size={14} />
              <span>Upload Audio File</span>
              <input
                type="file"
                accept="audio/*,.mp3,.wav,.m4a,.webm,.ogg"
                onChange={handleFileUpload}
              />
            </label>
          </div>
        </div>

        {/* Optional Context Notes */}
        <div className="portal-voice-summary-field">
          <label>
            <span>Optional note or summary of your voice memo:</span>
            <input
              value={notesSummary}
              onChange={(e) => setNotesSummary(e.target.value)}
              placeholder="e.g. Discussing the intro hook, background audio balance, and ending CTA logo…"
            />
          </label>
        </div>

        {error && (
          <div className="portal-error-notice">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* Action Button */}
        {audioBlob && (
          <div className="portal-form-submit-row">
            <div className="portal-ai-helper-text">
              <Sparkles size={14} />
              <span>AI will structure your voice feedback into clear items for your confirmation.</span>
            </div>
            <button
              onClick={processVoiceFeedback}
              disabled={busy}
              className="portal-primary-action-btn large"
            >
              <Wand2 size={16} />
              <span>{busy ? "Processing Voice with AI…" : "Review Structured Voice Feedback"}</span>
              <ArrowRight size={15} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ==============================================================================
// 5. AI-STRUCTURED FEEDBACK REVIEW MODAL (SCREEN 7)
// ==============================================================================

function StructuredFeedbackModal({
  draft,
  project,
  token,
  onClose,
  onSubmitted,
}: {
  draft: {
    summary: string;
    requests: FeedbackItem[];
    ambiguities: string[];
    missing_information: string[];
    production_risks: string[];
    originalContent: string;
    feedbackType: string;
    audioAssetId?: number | null;
  };
  project: PortalProject;
  token: string;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const [items, setItems] = useState<FeedbackItem[]>(draft.requests || []);
  const [authorName, setAuthorName] = useState("Client Director");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function updateItem(index: number, changes: Partial<FeedbackItem>) {
    setItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], ...changes };
      return copy;
    });
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }

  function addItem() {
    setItems((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).slice(2, 9),
        description: "New creative revision requirement",
        category: "General",
        classification: "explicit",
        confidence: 1.0,
        requires_confirmation: false,
        client_confirmed: false,
      },
    ]);
  }

  async function submitConfirmed() {
    if (items.length === 0) {
      setError("Please include at least one feedback requirement.");
      return;
    }
    setBusy(true);
    setError("");

    try {
      await api(`/api/portal/projects/${project.id}/feedback/submit`, {
        ...json("POST", {
          feedback_type: draft.feedbackType,
          content: draft.originalContent,
          version_id: project.current_version?.id || null,
          items: items,
          audio_asset_id: draft.audioAssetId || null,
          author_name: authorName,
        }),
        headers: { "X-Portal-Token": token, Authorization: `Bearer ${token}` },
      });
      onSubmitted();
    } catch (e: any) {
      setError(e.message || "Failed to submit feedback.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="portal-modal-backdrop" onClick={onClose}>
      <div className="portal-review-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="portal-modal-header">
          <div className="portal-modal-title">
            <Sparkles size={18} className="text-violet" />
            <div>
              <h3>Review Structured Creative Feedback</h3>
              <p>Confirm, refine, or edit each requirement before sending to your editing team.</p>
            </div>
          </div>
          <button className="portal-modal-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="portal-modal-body">
          {/* Ambiguity and Risk Callouts */}
          {draft.ambiguities.length > 0 && (
            <div className="portal-ambiguity-callout">
              <div className="portal-callout-head">
                <AlertTriangle size={15} />
                <b>Detected Ambiguities ({draft.ambiguities.length})</b>
              </div>
              <ul>
                {draft.ambiguities.map((amb, i) => (
                  <li key={i}>{amb}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Actionable Items List */}
          <div className="portal-items-section">
            <div className="portal-items-section-header">
              <b>Extracted Production Requirements ({items.length})</b>
              <button type="button" className="portal-small-add-btn" onClick={addItem}>
                <Plus size={13} /> Add item
              </button>
            </div>

            <div className="portal-items-list">
              {items.map((item, idx) => (
                <div key={idx} className="portal-editable-item-card">
                  <div className="portal-editable-top">
                    <span className="portal-item-category-tag">{item.category}</span>
                    <span className="portal-confidence-tag">
                      {Math.round((item.confidence || 0.9) * 100)}% clarity
                    </span>
                    <button
                      type="button"
                      className="portal-delete-item-btn"
                      onClick={() => removeItem(idx)}
                      title="Remove item"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>

                  <input
                    className="portal-item-input"
                    value={item.description}
                    onChange={(e) => updateItem(idx, { description: e.target.value })}
                  />

                  {/* Confirmation Checkbox for Long-term Preference */}
                  <label className="portal-confirm-pref-label">
                    <input
                      type="checkbox"
                      checked={item.client_confirmed}
                      onChange={(e) => updateItem(idx, { client_confirmed: e.target.checked })}
                    />
                    <span>
                      <b>Confirm as permanent brand preference</b>
                      <small>
                        Checked items will be remembered across all future videos. Leave unchecked for one-off revisions.
                      </small>
                    </span>
                  </label>
                </div>
              ))}
            </div>
          </div>

          {/* Author Name */}
          <div className="portal-author-row">
            <label>
              <span>Submitting as:</span>
              <input
                value={authorName}
                onChange={(e) => setAuthorName(e.target.value)}
                placeholder="Your Name (e.g. Sarah Connor)"
              />
            </label>
          </div>

          {error && (
            <div className="portal-error-notice">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Modal Actions */}
        <div className="portal-modal-footer">
          <button className="portal-cancel-btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="portal-primary-action-btn" onClick={submitConfirmed} disabled={busy}>
            <Check size={16} />
            <span>{busy ? "Submitting to Editors…" : "Confirm & Submit to Editing Team"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// 6. CLIENT DECISION MODAL (APPROVE / REQUEST CHANGES / REJECT)
// ==============================================================================

function DecisionModal({
  decisionType,
  project,
  token,
  onClose,
  onSubmitted,
}: {
  decisionType: "approve" | "changes_requested" | "reject";
  project: PortalProject;
  token: string;
  onClose: () => void;
  onSubmitted: (msg: string) => void;
}) {
  const [notes, setNotes] = useState("");
  const [authorName, setAuthorName] = useState("Client Director");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const titles = {
    approve: "Approve Version for Final Delivery",
    changes_requested: "Request Revisions on Cut",
    reject: "Reject Version / Direction Reset",
  };

  const descriptions = {
    approve: "Confirm that this cut meets all creative expectations and is approved for final render and delivery.",
    changes_requested: "Submit a revision request. Your team will cut the next version incorporating all open comments.",
    reject: "Flag a fundamental creative mismatch. Please provide specific feedback explaining why this direction is being rejected.",
  };

  async function handleDecision(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");

    try {
      const res = await api<any>(`/api/portal/projects/${project.id}/decision`, {
        ...json("POST", {
          decision: decisionType,
          version_id: project.current_version?.id || null,
          notes: notes.trim(),
          author_name: authorName,
        }),
        headers: { "X-Portal-Token": token, Authorization: `Bearer ${token}` },
      });
      onSubmitted(res.message);
    } catch (e: any) {
      setError(e.message || "Failed to record decision.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="portal-modal-backdrop" onClick={onClose}>
      <div className="portal-decision-card" onClick={(e) => e.stopPropagation()}>
        <div className="portal-modal-header">
          <div className="portal-decision-head">
            {decisionType === "approve" ? (
              <CheckCircle2 size={24} className="text-emerald" />
            ) : decisionType === "changes_requested" ? (
              <MessageSquareQuote size={24} className="text-amber" />
            ) : (
              <XCircle size={24} className="text-rose" />
            )}
            <div>
              <h3>{titles[decisionType]}</h3>
              <p>{descriptions[decisionType]}</p>
            </div>
          </div>
          <button className="portal-modal-close" onClick={onClose}>
            <X size={15} />
          </button>
        </div>

        <form onSubmit={handleDecision} className="portal-decision-form">
          <label>
            <span>Notes / Sign-off summary:</span>
            <textarea
              rows={3}
              required={decisionType === "reject"}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={
                decisionType === "approve"
                  ? "Optional sign-off comments (e.g. 'Looks fantastic, ready for master color export!')"
                  : decisionType === "changes_requested"
                  ? "Summary of required revisions (e.g. 'Address the 3 timestamped pacing comments on video timeline.')"
                  : "Required: Please explain the creative disconnect so our team can reset direction."
              }
            />
          </label>

          <label>
            <span>Author name:</span>
            <input
              value={authorName}
              onChange={(e) => setAuthorName(e.target.value)}
              placeholder="Your name / title"
            />
          </label>

          {error && (
            <div className="portal-error-notice">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}

          <div className="portal-modal-footer">
            <button type="button" className="portal-cancel-btn" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button
              type="submit"
              className={`portal-primary-action-btn ${decisionType}`}
              disabled={busy}
            >
              <span>{busy ? "Submitting…" : `Confirm ${formatStatus(decisionType)}`}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ==============================================================================
// 7. FEEDBACK PIPELINE VIEW (STATUS TRACKING)
// ==============================================================================

function FeedbackPipelineView({
  project,
  token,
  onRefresh,
}: {
  project: PortalProject;
  token: string;
  onRefresh: () => void;
}) {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const submissions = project.feedback_submissions || [];

  const filtered =
    statusFilter === "all" ? submissions : submissions.filter((s) => s.status === statusFilter);

  return (
    <div className="portal-pipeline-container">
      <div className="portal-pipeline-header">
        <div className="portal-pipeline-title">
          <Layers size={18} />
          <div>
            <h3>Creative Feedback & Revision History</h3>
            <p>Track delivery status across all feedback rounds and review sign-offs.</p>
          </div>
        </div>

        <div className="portal-pipeline-filters">
          {["all", "submitted", "processing", "awaiting_confirmation", "delivered", "resolved"].map(
            (st) => (
              <button
                key={st}
                className={statusFilter === st ? "active" : ""}
                onClick={() => setStatusFilter(st)}
              >
                {formatStatus(st)}
              </button>
            )
          )}
        </div>
      </div>

      <div className="portal-submissions-grid">
        {filtered.length > 0 ? (
          filtered.map((sub) => (
            <article key={sub.id} className="portal-submission-card">
              <div className="portal-sub-head">
                <div className="portal-sub-meta">
                  <span className="portal-sub-type">{formatFeedbackType(sub.feedback_type)}</span>
                  <span className="portal-sub-date">
                    {new Date(sub.created_at).toLocaleDateString()} at{" "}
                    {new Date(sub.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
                <span className={`portal-status-badge ${sub.status}`}>
                  <span className="portal-status-dot" />
                  {formatStatus(sub.status)}
                </span>
              </div>

              <div className="portal-sub-author">Submitted by: {sub.author_name}</div>
              <p className="portal-sub-content">“{sub.content}”</p>

              {sub.items && sub.items.length > 0 && (
                <div className="portal-sub-items-box">
                  <div className="portal-sub-items-title">Structured Action Items ({sub.items.length}):</div>
                  <ul>
                    {sub.items.map((it, idx) => (
                      <li key={idx}>
                        <span className="portal-mini-tag">{it.category}</span>
                        <span>{it.description}</span>
                        {it.client_confirmed && (
                          <span className="portal-confirmed-tag" title="Confirmed as permanent preference">
                            <Check size={10} /> Brand preference
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </article>
          ))
        ) : (
          <div className="portal-pipeline-empty">
            <Layers size={32} />
            <b>No submissions in this view</b>
            <p>Feedback submissions, voice notes, and review decisions will appear here as they are logged.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ==============================================================================
// 8. PROJECT ASSETS VIEW
// ==============================================================================

function ProjectAssetsView({
  project,
  token,
}: {
  project: PortalProject;
  token: string;
}) {
  const assets = project.assets || [];

  return (
    <div className="portal-assets-panel">
      <div className="portal-panel-heading">
        <div className="portal-panel-title">
          <FolderKanban size={18} />
          <div>
            <h3>Project Deliverables & Shared Assets</h3>
            <p>Download review cuts, reference materials, brand assets, and finalized masters.</p>
          </div>
        </div>
      </div>

      <div className="portal-assets-grid">
        {assets.length > 0 ? (
          assets.map((a) => (
            <div key={a.id} className="portal-asset-card">
              <div className="portal-asset-icon">
                {a.content_type?.startsWith("video/") ? (
                  <Film size={20} />
                ) : a.content_type?.startsWith("audio/") ? (
                  <FileAudio size={20} />
                ) : (
                  <FileText size={20} />
                )}
              </div>
              <div className="portal-asset-info">
                <b>{a.filename}</b>
                <small>
                  {a.category} · {Math.round(a.size_bytes / 1024)} KB · {new Date(a.created_at).toLocaleDateString()}
                </small>
              </div>
              <a
                href={`${a.stream_url}?token=${encodeURIComponent(token)}`}
                target="_blank"
                rel="noreferrer"
                className="portal-download-btn"
                download
              >
                Download
              </a>
            </div>
          ))
        ) : (
          <div className="portal-assets-empty">
            <FolderKanban size={32} />
            <b>No assets uploaded yet</b>
            <p>Deliverables and project files shared by your editor will appear here.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ==============================================================================
// UTILITY FUNCTIONS
// ==============================================================================

function formatTimecode(seconds: number): string {
  const s = Math.floor(seconds);
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

function formatStatus(status: string): string {
  const map: Record<string, string> = {
    active: "Active",
    in_review: "In Review",
    changes_requested: "Changes Requested",
    approved: "Approved",
    delivered: "Delivered",
    resolved: "Resolved",
    submitted: "Submitted",
    processing: "Processing",
    awaiting_confirmation: "Awaiting Confirmation",
    rejected: "Rejected",
    archived: "Archived",
    completed: "Completed",
  };
  return map[status] || status.replace(/_/g, " ").toUpperCase();
}

function formatFeedbackType(type: string): string {
  const map: Record<string, string> = {
    brief: "Creative Brief",
    text: "Written Revision",
    voice: "Voice Feedback Memo",
    review_decision: "Cut Review Decision",
  };
  return map[type] || type.toUpperCase();
}
