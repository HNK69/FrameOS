"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  AudioLines,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Clock,
  Clock3,
  ExternalLink,
  Eye,
  FileAudio2,
  FileText,
  Filter,
  FolderKanban,
  HardDrive,
  History,
  Lock,
  LockKeyhole,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Upload,
  User,
  WandSparkles,
  X,
  Zap,
} from "lucide-react";
import { api, json } from "@/lib/api";
import { AssetIntelligencePanel } from "./asset-intelligence-panel";
import { Task, TaskEditModal } from "./task-edit-modal";
import { TaskAuditDrawer } from "./task-audit-drawer";

interface ProductionWorkspaceProps {
  clients: any[];
  projects: any[];
  refresh: () => void;
  notify: (msg: string) => void;
}

type ProductionView = "tasks" | "assets" | "ingest" | "memory";

export function ProductionWorkspace({
  clients,
  projects,
  refresh,
  notify,
}: ProductionWorkspaceProps) {
  const [clientId, setClientId] = useState<number>(0);
  const [projectId, setProjectId] = useState<number>(0);
  const [view, setView] = useState<ProductionView>("tasks");

  // Tasks state
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Modals & drawers
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [auditingTaskId, setAuditingTaskId] = useState<number | null>(null);

  // Ingest state
  const [transcript, setTranscript] = useState("");
  const [run, setRun] = useState<any>(null);
  const [ingestBusy, setIngestBusy] = useState(false);

  // Adaptive Memory state
  const [adaptiveData, setAdaptiveData] = useState<any>(null);
  const [loadingAdaptive, setLoadingAdaptive] = useState(false);
  const [memoryFilter, setMemoryFilter] = useState<string>("all");
  const [newPreference, setNewPreference] = useState("");
  const [newPrefConfirmed, setNewPrefConfirmed] = useState(true);
  const [newPrefBusy, setNewPrefBusy] = useState(false);

  // Set initial client and project from URL query or first client
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const paramProj = Number(params.get("project") || 0);
    const paramClient = Number(params.get("client") || 0);

    if (paramProj && projects.length) {
      const match = projects.find((p) => p.id === paramProj);
      if (match) {
        setClientId(match.client_id);
        setProjectId(match.id);
        return;
      }
    }
    if (paramClient) {
      setClientId(paramClient);
    } else if (clients.length && !clientId) {
      setClientId(clients[0].id);
    }
  }, [clients, projects]);

  // Synchronize project selection with client selection
  const visibleProjects = useMemo(() => {
    return projects.filter((p) => !clientId || p.client_id === clientId);
  }, [projects, clientId]);

  useEffect(() => {
    if (visibleProjects.length) {
      if (!visibleProjects.some((p) => p.id === projectId)) {
        setProjectId(visibleProjects[0].id);
      }
    } else {
      setProjectId(0);
    }
  }, [clientId, visibleProjects]);

  // Fetch tasks whenever project changes
  const loadTasks = () => {
    if (!projectId) {
      setTasks([]);
      return;
    }
    setLoadingTasks(true);
    api<Task[]>(`/api/tasks?project_id=${projectId}`)
      .then((data) => setTasks(data))
      .catch((err) => notify(err.message || "Failed to load project tasks"))
      .finally(() => setLoadingTasks(false));
  };

  useEffect(() => {
    loadTasks();
  }, [projectId]);

  // Load adaptive knowledge when memory view is opened
  useEffect(() => {
    if (view === "memory" && clientId) {
      setLoadingAdaptive(true);
      api<any>(`/api/clients/${clientId}/adaptive-knowledge`)
        .then((res) => setAdaptiveData(res))
        .catch((err) => notify(err.message || "Failed to load adaptive knowledge"))
        .finally(() => setLoadingAdaptive(false));
    }
  }, [view, clientId]);

  // Quick task status change
  async function handleQuickStatusChange(task: Task, newStatus: string) {
    try {
      const updated = await api<Task>(
        `/api/tasks/${task.id}`,
        json("PATCH", { status: newStatus })
      );
      setTasks((prev) => prev.map((t) => (t.id === task.id ? updated : t)));
      notify(`Task #${task.id} moved to ${newStatus}.`);
      refresh();
    } catch (err: any) {
      notify(err.message || "Failed to update task status");
    }
  }

  // Quick accept or reject with provenance
  async function handleFeedbackRate(task: Task, action: "accept" | "reject") {
    try {
      const res = await api<any>(
        `/api/tasks/${task.id}/feedback`,
        json("POST", { action, client_confirmed: action === "accept" })
      );
      notify(res.message);
      loadTasks();
      refresh();
    } catch (err: any) {
      notify(err.message || "Failed to save feedback");
    }
  }

  // Process transcript form submission
  async function handleProcessTranscript(e: React.FormEvent) {
    e.preventDefault();
    if (!projectId) return;

    setIngestBusy(true);
    setRun(null);

    try {
      const result = await api<any>("/api/process-transcript", {
        ...json("POST", { project_id: projectId, transcript }),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      setRun(result);
      notify("Transcript processed. Tasks and requirements generated.");
      loadTasks();
      refresh();
    } catch (err: any) {
      notify(err.message || "Transcript processing failed");
      try {
        const p = await api<any>(`/api/projects/${projectId}`);
        if (p.runs?.[0]) setRun(p.runs[0]);
      } catch {}
    } finally {
      setIngestBusy(false);
    }
  }

  // Add confirmed client knowledge directly
  async function handleAddAdaptivePreference(e: React.FormEvent) {
    e.preventDefault();
    if (!newPreference.trim() || !clientId) return;

    setNewPrefBusy(true);
    try {
      await api<any>(
        `/api/clients/${clientId}/adaptive-knowledge`,
        json("POST", {
          content: newPreference.trim(),
          knowledge_type: newPrefConfirmed ? "client_confirmed" : "reusable_client_knowledge",
          client_confirmed: newPrefConfirmed,
          project_id: projectId || null,
        })
      );
      notify("Client knowledge recorded and retained with provenance.");
      setNewPreference("");
      // Refresh adaptive knowledge
      api<any>(`/api/clients/${clientId}/adaptive-knowledge`).then((res) => setAdaptiveData(res));
      refresh();
    } catch (err: any) {
      notify(err.message || "Failed to save preference");
    } finally {
      setNewPrefBusy(false);
    }
  }

  // Filtered task items
  const filteredTasks = useMemo(() => {
    return tasks.filter((t) => {
      if (statusFilter !== "all" && t.status !== statusFilter) return false;
      if (priorityFilter !== "all" && t.priority !== priorityFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          t.title.toLowerCase().includes(q) ||
          t.instruction.toLowerCase().includes(q) ||
          t.category.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [tasks, statusFilter, priorityFilter, searchQuery]);

  // Task status counts for badges
  const taskCounts = useMemo(() => {
    return {
      all: tasks.length,
      pending: tasks.filter((t) => t.status === "pending").length,
      in_progress: tasks.filter((t) => t.status === "in_progress").length,
      completed: tasks.filter((t) => t.status === "completed" || t.status === "accepted").length,
      blocked: tasks.filter((t) => t.status === "blocked").length,
      rejected: tasks.filter((t) => t.status === "rejected").length,
    };
  }, [tasks]);

  const selectedClient = clients.find((c) => c.id === clientId);
  const selectedProject = projects.find((p) => p.id === projectId);

  return (
    <div className="production-intelligence-suite">
      {/* Workspace Header Strip */}
      <div className="panel production-context-bar">
        <div className="context-selects">
          <label>
            <span>CLIENT</span>
            <select
              value={clientId || ""}
              onChange={(e) => {
                setClientId(Number(e.target.value));
                setRun(null);
              }}
            >
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} {c.brand ? `(${c.brand})` : ""}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>PROJECT</span>
            <select
              value={projectId || ""}
              onChange={(e) => {
                setProjectId(Number(e.target.value));
                setRun(null);
              }}
            >
              {visibleProjects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.status})
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* View Toggle Tabs */}
        <nav className="production-view-tabs" aria-label="Production workspace sections">
          <button
            className={view === "tasks" ? "active" : ""}
            onClick={() => setView("tasks")}
          >
            <Zap size={14} />
            <span>Tasks & Resolve Workflow</span>
            <b>{tasks.length}</b>
          </button>

          <button
            className={view === "assets" ? "active" : ""}
            onClick={() => setView("assets")}
          >
            <HardDrive size={14} />
            <span>Asset Intelligence</span>
          </button>

          <button
            className={view === "ingest" ? "active" : ""}
            onClick={() => setView("ingest")}
          >
            <AudioLines size={14} />
            <span>Transcript Feedback</span>
          </button>

          <button
            className={view === "memory" ? "active" : ""}
            onClick={() => setView("memory")}
          >
            <BrainCircuit size={14} />
            <span>Adaptive Memory</span>
          </button>
        </nav>
      </div>

      {/* Main Surface Depending on Active View */}
      {view === "tasks" && (
        <section className="production-tasks-surface">
          {/* Filter and Search Bar */}
          <div className="tasks-toolbar">
            <div className="status-pill-filter">
              {[
                { key: "all", label: "All Tasks", count: taskCounts.all },
                { key: "pending", label: "Pending", count: taskCounts.pending },
                { key: "in_progress", label: "In Progress", count: taskCounts.in_progress },
                { key: "completed", label: "Completed", count: taskCounts.completed },
                { key: "blocked", label: "Blocked", count: taskCounts.blocked },
                { key: "rejected", label: "Rejected", count: taskCounts.rejected },
              ].map((item) => (
                <button
                  key={item.key}
                  className={`filter-chip ${statusFilter === item.key ? "selected" : ""}`}
                  onClick={() => setStatusFilter(item.key)}
                >
                  <span>{item.label}</span>
                  <small>{item.count}</small>
                </button>
              ))}
            </div>

            <div className="tasks-secondary-filters">
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                aria-label="Filter by priority"
              >
                <option value="all">All Priorities</option>
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>

              <div className="task-search-input">
                <Search size={14} />
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter tasks, workflows, instructions..."
                />
              </div>
            </div>
          </div>

          {/* Tasks Grid / List */}
          {loadingTasks ? (
            <div className="panel loading-box">Loading production intelligence tasks...</div>
          ) : filteredTasks.length > 0 ? (
            <div className="tasks-cards-grid">
              {filteredTasks.map((task) => (
                <article key={task.id} className="production-task-card panel">
                  {/* Card Header */}
                  <div className="task-card-header">
                    <div className="header-tags">
                      <span className="category-tag">{task.category}</span>
                      <span className={`priority-label ${task.priority}`}>{task.priority}</span>
                      <span className={`status-pill ${task.status}`}>{task.status}</span>
                    </div>

                    <div className="header-meta">
                      {task.is_corrected && (
                        <span className="corrected-badge" title="Editor has refined this task">
                          <Pencil size={11} /> Edited
                        </span>
                      )}
                      <span className="confidence-pill" title="AI synthesis confidence score">
                        {Math.round(task.confidence * 100)}% conf
                      </span>
                    </div>
                  </div>

                  {/* Title and Instruction */}
                  <h4 className="task-title">{task.title}</h4>
                  <p className="task-instruction">{task.instruction}</p>

                  {/* If Corrected: Show Immutable Original Comparison */}
                  {task.is_corrected && task.original_recommendation && (
                    <details className="original-comparison-details">
                      <summary>
                        <Lock size={11} /> View Original AI Recommendation
                      </summary>
                      <div className="original-comparison-body">
                        <p>{task.original_recommendation}</p>
                        <small>Immutable original preserved in provenance history.</small>
                      </div>
                    </details>
                  )}

                  {/* DaVinci Resolve Workflow Box */}
                  <div className="resolve-workflow-box">
                    <div className="workflow-title">
                      <span>DAVINCI RESOLVE WORKFLOW</span>
                    </div>
                    <p>{task.resolve_workflow}</p>
                  </div>

                  {/* Evidence Citation */}
                  {task.evidence && (
                    <div className="task-evidence-strip">
                      <b>Client Feedback:</b> “{task.evidence}”
                    </div>
                  )}

                  {/* Confirmation Warning if Needed */}
                  {task.requires_confirmation && task.status === "pending" && (
                    <div className="confirmation-warning-bar">
                      <CircleHelp size={13} />
                      <span>Low confidence or sensitive instruction. Editor confirmation required.</span>
                    </div>
                  )}

                  {/* Action Controls */}
                  <div className="task-actions-toolbar">
                    <div className="quick-actions">
                      {task.status !== "in_progress" && (
                        <button
                          className="action-btn"
                          onClick={() => handleQuickStatusChange(task, "in_progress")}
                          title="Move to In Progress in DaVinci Resolve"
                        >
                          <Play size={12} /> Work in Resolve
                        </button>
                      )}

                      {task.status !== "completed" && task.status !== "accepted" && (
                        <button
                          className="action-btn accept"
                          onClick={() => handleQuickStatusChange(task, "completed")}
                          title="Mark task completed"
                        >
                          <Check size={12} /> Complete
                        </button>
                      )}

                      {task.status !== "blocked" && (
                        <button
                          className="action-btn block"
                          onClick={() => handleQuickStatusChange(task, "blocked")}
                          title="Mark task blocked"
                        >
                          <AlertTriangle size={12} /> Block
                        </button>
                      )}
                    </div>

                    <div className="provenance-actions">
                      <button
                        className="action-btn edit"
                        onClick={() => setEditingTask(task)}
                        title="Edit task instruction and record provenance"
                      >
                        <Pencil size={12} /> Correct / Edit
                      </button>

                      <button
                        className="action-btn icon"
                        onClick={() => setAuditingTaskId(task.id)}
                        title="View audit trail and provenance history"
                        aria-label="View history"
                      >
                        <History size={13} />
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="panel empty-state">
              <Zap size={24} />
              <b>No tasks match your filters</b>
              <p>
                {searchQuery || statusFilter !== "all" || priorityFilter !== "all"
                  ? "Try resetting your search or filter pills."
                  : "Process client feedback or a project transcript to generate production tasks."}
              </p>
              <button
                className="primary-button"
                style={{ marginTop: 12 }}
                onClick={() => setView("ingest")}
              >
                <WandSparkles size={14} /> Process Feedback
              </button>
            </div>
          )}
        </section>
      )}

      {/* View: Asset Intelligence */}
      {view === "assets" && (
        <AssetIntelligencePanel projectId={projectId} notify={notify} />
      )}

      {/* View: Transcript Ingestion Pipeline */}
      {view === "ingest" && (
        <div className="production-ingest-split">
          <section className="panel workflow-panel">
            <div className="card-head">
              <div className="card-title">
                <span className="head-icon"><FileAudio2 size={16} /></span>
                <h2>Client Transcript & Feedback Ingestion</h2>
              </div>
              <span className="card-meta">GROQ · HINDSIGHT · OPENCLAW</span>
            </div>

            <form onSubmit={handleProcessTranscript} className="transcript-form">
              <div className="field-label">
                <span><FileText size={14} /> Raw Client Call Transcript or Creative Notes</span>
                <small>{transcript.length.toLocaleString()} / 100,000</small>
              </div>

              <textarea
                required
                minLength={10}
                maxLength={100000}
                rows={9}
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="Paste verbatim client review feedback, call transcript, or revision notes..."
              />

              <div className="form-footnote">
                <LockKeyhole size={13} />
                <span>Text is treated as untrusted source material, never prompt injection.</span>
              </div>

              <button
                type="submit"
                className="primary-button"
                disabled={ingestBusy || transcript.trim().length < 10}
              >
                {ingestBusy ? (
                  <>
                    <span className="spinner" /> Synthesizing with Real Pipeline...
                  </>
                ) : (
                  <>
                    Extract & Synthesize Resolve Tasks <WandSparkles size={15} />
                  </>
                )}
              </button>
            </form>
          </section>

          {/* Ingestion Results Panel */}
          {run && (
            <section className="panel run-panel">
              <div className="card-head">
                <div className="card-title">
                  <span className="head-icon">
                    {run.status === "completed" ? <CheckCircle2 size={16} /> : <Activity size={16} />}
                  </span>
                  <h2>Processing Run #{run.id}</h2>
                </div>
                <span className={`run-status-pill ${run.status}`}>{run.status.toUpperCase()}</span>
              </div>

              {run.error && (
                <div className="error-box">
                  <b>Integration Notice:</b> {run.error}
                </div>
              )}

              {run.extractions?.length > 0 && (
                <div className="evidence-section">
                  <h3>
                    <span>Extracted Requirements ({run.extractions.length})</span>
                    <small>Groq extraction</small>
                  </h3>
                  {run.extractions.map((item: any, i: number) => (
                    <div key={i} className="extracted-item">
                      <span className="category-tag">{item.category}</span>
                      <b>{item.description}</b>
                      {item.source_quote && <p>“{item.source_quote}”</p>}
                      <small>
                        {item.classification} · {Math.round(item.confidence * 100)}% confidence
                        {item.requires_confirmation && " · confirmation required"}
                      </small>
                    </div>
                  ))}
                </div>
              )}

              {run.tasks?.length > 0 && (
                <div className="evidence-section">
                  <h3>
                    <span>Generated Production Tasks ({run.tasks.length})</span>
                    <button className="small-action" onClick={() => setView("tasks")}>
                      View in Tasks <ArrowRight size={12} />
                    </button>
                  </h3>
                  {run.tasks.map((t: any) => (
                    <div key={t.id} className="task-preview-mini">
                      <b>{t.title}</b>
                      <p>{t.instruction}</p>
                      <small>{t.category} · {t.priority} priority</small>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {!run && (
            <section className="panel memory-context-panel">
              <div className="card-head">
                <div className="card-title">
                  <span className="head-icon"><BrainCircuit size={16} /></span>
                  <h2>The Production Intelligence Pipeline</h2>
                </div>
              </div>
              <div className="memory-diagram">
                <div>
                  <span>01</span>
                  <b>Extract Requirements</b>
                  <small>Groq validates explicit client requests & revisions.</small>
                </div>
                <ArrowRight size={15} />
                <div>
                  <span>02</span>
                  <b>Recall Client Bank</b>
                  <small>Hindsight queries historical client-confirmed preferences.</small>
                </div>
                <ArrowRight size={15} />
                <div>
                  <span>03</span>
                  <b>Resolve Synthesis</b>
                  <small>OpenClaw produces evidence-backed Resolve workflows.</small>
                </div>
              </div>
              <div className="service-note">
                <ShieldCheck size={14} />
                <span>External integration operations are recorded with full provenance.</span>
              </div>
            </section>
          )}
        </div>
      )}

      {/* View: Adaptive Client Memory */}
      {view === "memory" && (
        <section className="adaptive-memory-surface">
          <div className="panel adaptive-header-card">
            <div className="adaptive-title-row">
              <div className="card-title">
                <span className="head-icon"><BrainCircuit size={18} /></span>
                <div>
                  <h2>Adaptive Intelligence: {selectedClient?.name || "Client"}</h2>
                  <small>Distinguishes AI recommendations, editor corrections, confirmed preferences, and reusable knowledge</small>
                </div>
              </div>

              <div className="memory-status-badge">
                <i className={selectedClient?.memory_status === "ready" ? "status-ready" : "status-off"} />
                <span>
                  {selectedClient?.memory_status === "ready"
                    ? "Hindsight Memory Bank Active"
                    : "Local Memory Mode (Hindsight Unavailable)"}
                </span>
              </div>
            </div>

            {/* Direct Add Knowledge Form */}
            <form onSubmit={handleAddAdaptivePreference} className="add-preference-form">
              <div className="field-head">
                <span>Record Client Preference or Editing Rule</span>
                <small>Will inform all future synthesis recommendations for this client</small>
              </div>
              <div className="pref-input-row">
                <input
                  required
                  value={newPreference}
                  onChange={(e) => setNewPreference(e.target.value)}
                  placeholder="e.g. Always keep music 18dB below dialogue; prefers warm filmic grade..."
                />
                <label className="pref-checkbox">
                  <input
                    type="checkbox"
                    checked={newPrefConfirmed}
                    onChange={(e) => setNewPrefConfirmed(e.target.checked)}
                  />
                  <span>Confirmed by client</span>
                </label>
                <button type="submit" className="primary-button" disabled={newPrefBusy || !newPreference.trim()}>
                  {newPrefBusy ? "Saving..." : "Record Knowledge"}
                </button>
              </div>
            </form>
          </div>

          {/* Classification Filter Pills */}
          <div className="category-filter-strip">
            {[
              { key: "all", label: "All Intelligence Records", count: (adaptiveData?.counts?.ai_recommendations || 0) + (adaptiveData?.counts?.editor_corrections || 0) + (adaptiveData?.counts?.client_confirmed_preferences || 0) },
              { key: "ai", label: "AI Recommendations", count: adaptiveData?.counts?.ai_recommendations || 0 },
              { key: "corrections", label: "Editor Corrections", count: adaptiveData?.counts?.editor_corrections || 0 },
              { key: "confirmed", label: "Client-Confirmed Preferences", count: adaptiveData?.counts?.client_confirmed_preferences || 0 },
              { key: "reusable", label: "Reusable Client Knowledge", count: adaptiveData?.counts?.reusable_client_knowledge || 0 },
              { key: "project", label: "Project-Specific Decisions", count: adaptiveData?.counts?.project_specific_decisions || 0 },
            ].map((f) => (
              <button
                key={f.key}
                className={`cat-pill ${memoryFilter === f.key ? "active" : ""}`}
                onClick={() => setMemoryFilter(f.key)}
              >
                <span>{f.label}</span>
                <small>{f.count}</small>
              </button>
            ))}
          </div>

          {/* Adaptive Knowledge List */}
          <div className="adaptive-records-grid">
            {/* Editor Corrections */}
            {(memoryFilter === "all" || memoryFilter === "corrections") &&
              adaptiveData?.editor_corrections?.map((ec: any) => (
                <div key={ec.id} className="panel knowledge-card correction">
                  <div className="knowledge-top">
                    <span className="knowledge-badge correction">EDITOR CORRECTION</span>
                    <small>{ec.author} · {ec.created_at ? new Date(ec.created_at).toLocaleDateString() : ""}</small>
                  </div>
                  <b>Correction to recommendation:</b>
                  <p className="correction-quote">{ec.correction}</p>
                  <div className="rec-was">
                    <small>Original AI Recommendation: “{ec.original_recommendation}”</small>
                  </div>
                  <div className="knowledge-footer">
                    <span>Provenance: Editor refinement</span>
                    <span className="retention-status">{ec.retention_status}</span>
                  </div>
                </div>
              ))}

            {/* Client Confirmed Preferences */}
            {(memoryFilter === "all" || memoryFilter === "confirmed") &&
              adaptiveData?.client_confirmed_preferences?.map((cp: any) => (
                <div key={cp.id} className="panel knowledge-card confirmed">
                  <div className="knowledge-top">
                    <span className="knowledge-badge confirmed">CLIENT-CONFIRMED PREFERENCE</span>
                    <small>{cp.author} · {cp.created_at ? new Date(cp.created_at).toLocaleDateString() : ""}</small>
                  </div>
                  <b>Confirmed preference:</b>
                  <p className="confirmed-quote">{cp.correction || cp.original_recommendation}</p>
                  <div className="knowledge-footer">
                    <span>Direct client confirmation</span>
                    <span className="retention-status">{cp.retention_status}</span>
                  </div>
                </div>
              ))}

            {/* Reusable Client Knowledge */}
            {(memoryFilter === "all" || memoryFilter === "reusable") &&
              adaptiveData?.reusable_client_knowledge?.map((rk: any) => (
                <div key={rk.id} className="panel knowledge-card reusable">
                  <div className="knowledge-top">
                    <span className="knowledge-badge reusable">REUSABLE CLIENT KNOWLEDGE</span>
                    <small>{rk.created_at ? new Date(rk.created_at).toLocaleDateString() : ""}</small>
                  </div>
                  <p>{rk.details}</p>
                  <div className="knowledge-footer">
                    <span>Persisted for cross-project recall</span>
                    <span className="retention-status">{rk.status}</span>
                  </div>
                </div>
              ))}

            {/* Project-Specific Decisions */}
            {(memoryFilter === "all" || memoryFilter === "project") &&
              adaptiveData?.project_specific_decisions?.map((pd: any) => (
                <div key={pd.id} className="panel knowledge-card project">
                  <div className="knowledge-top">
                    <span className="knowledge-badge project">PROJECT SPECIFIC DECISION</span>
                    <small>{pd.created_at ? new Date(pd.created_at).toLocaleDateString() : ""}</small>
                  </div>
                  <p>{pd.details}</p>
                  <div className="knowledge-footer">
                    <span>Scoped to project only (not retained globally)</span>
                  </div>
                </div>
              ))}

            {/* AI Generated Recommendations */}
            {(memoryFilter === "all" || memoryFilter === "ai") &&
              adaptiveData?.ai_recommendations?.map((ai: any) => (
                <div key={ai.id} className="panel knowledge-card ai">
                  <div className="knowledge-top">
                    <span className="knowledge-badge ai">AI RECOMMENDATION</span>
                    <small>{Math.round(ai.confidence * 100)}% confidence</small>
                  </div>
                  <b>{ai.title}</b>
                  <p>{ai.instruction}</p>
                  <div className="workflow-preview">
                    <span>Workflow:</span> {ai.resolve_workflow}
                  </div>
                  <div className="knowledge-footer">
                    <span>Source: {ai.source}</span>
                    <span className={`status-pill ${ai.status}`}>{ai.status}</span>
                  </div>
                </div>
              ))}
          </div>
        </section>
      )}

      {/* Task Edit Modal */}
      {editingTask && (
        <TaskEditModal
          task={editingTask}
          onClose={() => setEditingTask(null)}
          onSaved={(updated) => {
            setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
            refresh();
          }}
          notify={notify}
        />
      )}

      {/* Task Audit Drawer */}
      {auditingTaskId !== null && (
        <TaskAuditDrawer
          taskId={auditingTaskId}
          onClose={() => setAuditingTaskId(null)}
        />
      )}
    </div>
  );
}
