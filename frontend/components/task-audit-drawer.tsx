"use client";

import { useEffect, useState } from "react";
import { BrainCircuit, CheckCircle2, Clock, FileText, Lock, Sparkles, User, X } from "lucide-react";
import { api } from "@/lib/api";
import { Task } from "./task-edit-modal";

interface TaskAuditDrawerProps {
  taskId: number;
  onClose: () => void;
}

export function TaskAuditDrawer({ taskId, onClose }: TaskAuditDrawerProps) {
  const [taskDetail, setTaskDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api<any>(`/api/tasks/${taskId}`)
      .then((data) => setTaskDetail(data))
      .catch((err) => console.error("Error loading task details:", err))
      .finally(() => setLoading(false));
  }, [taskId]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer-panel panel" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <div className="drawer-title">
            <span className="head-icon"><BrainCircuit size={16} /></span>
            <div>
              <h3>Task Provenance & History</h3>
              <small>Task #{taskId}</small>
            </div>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close drawer">
            <X size={16} />
          </button>
        </div>

        {loading ? (
          <div className="drawer-loading">Loading provenance record...</div>
        ) : taskDetail ? (
          <div className="drawer-content">
            {/* Task Snapshot */}
            <div className="audit-section">
              <span className="audit-label">CURRENT TASK DEFINITION</span>
              <div className="audit-card">
                <div className="audit-card-top">
                  <span className="category-tag">{taskDetail.category}</span>
                  <span className={`priority-label ${taskDetail.priority}`}>{taskDetail.priority}</span>
                  <span className={`status-pill ${taskDetail.status}`}>{taskDetail.status}</span>
                </div>
                <h4>{taskDetail.title}</h4>
                <p className="task-instruction-text">{taskDetail.instruction}</p>
                <div className="resolve-box">
                  <span>RESOLVE WORKFLOW</span>
                  <p>{taskDetail.resolve_workflow}</p>
                </div>
              </div>
            </div>

            {/* Original AI Recommendation */}
            <div className="audit-section">
              <span className="audit-label">ORIGINAL AI RECOMMENDATION (IMMUTABLE)</span>
              <div className="audit-card locked">
                <div className="locked-head">
                  <Lock size={12} />
                  <span>Synthesized by {taskDetail.source || "Groq/OpenClaw"}</span>
                  <small>{Math.round((taskDetail.confidence || 0) * 100)}% confidence</small>
                </div>
                <p>{taskDetail.original_recommendation || taskDetail.instruction}</p>
                {taskDetail.evidence && (
                  <div className="evidence-quote">
                    <b>Transcript Evidence:</b> “{taskDetail.evidence}”
                  </div>
                )}
              </div>
            </div>

            {/* Source Run & Transcript */}
            {taskDetail.source_run && (
              <div className="audit-section">
                <span className="audit-label">SOURCE INGESTION RUN</span>
                <div className="audit-card">
                  <div className="source-run-meta">
                    <span><FileText size={13} /> Run #{taskDetail.source_run.id}</span>
                    <small>{taskDetail.source_run.created_at ? new Date(taskDetail.source_run.created_at).toLocaleString() : "—"}</small>
                  </div>
                  {taskDetail.source_run.transcript_preview && (
                    <blockquote className="transcript-excerpt">
                      “{taskDetail.source_run.transcript_preview}...”
                    </blockquote>
                  )}
                </div>
              </div>
            )}

            {/* Linked Extracted Requirements */}
            {taskDetail.linked_extractions?.length > 0 && (
              <div className="audit-section">
                <span className="audit-label">LINKED TRANSCRIPT REQUIREMENTS</span>
                {taskDetail.linked_extractions.map((ex: any) => (
                  <div key={ex.id} className="extracted-item-mini">
                    <div className="mini-head">
                      <span className="category-tag">{ex.category}</span>
                      <small>{ex.classification} · {Math.round(ex.confidence * 100)}% conf</small>
                    </div>
                    <b>{ex.description}</b>
                    {ex.source_quote && <p>“{ex.source_quote}”</p>}
                  </div>
                ))}
              </div>
            )}

            {/* Feedback & Correction Audit Log */}
            <div className="audit-section">
              <span className="audit-label">EDITOR CORRECTIONS & AUDIT TRAIL</span>
              {taskDetail.feedback_history?.length > 0 ? (
                <div className="audit-timeline">
                  {taskDetail.feedback_history.map((f: any, idx: number) => (
                    <div key={f.id || idx} className="timeline-node">
                      <div className="node-pip"><Clock size={12} /></div>
                      <div className="node-body">
                        <div className="node-head">
                          <b>Action: {f.action}</b>
                          <small>{f.created_at ? new Date(f.created_at).toLocaleString() : "Recently"}</small>
                        </div>
                        <div className="node-author">
                          <User size={11} /> {f.author_email || "Editor"}
                        </div>
                        {f.correction && (
                          <div className="correction-text">
                            <b>Correction:</b> {f.correction}
                          </div>
                        )}
                        <div className="node-pills">
                          {f.client_confirmed && (
                            <span className="provenance-chip confirmed">
                              <CheckCircle2 size={10} /> Client-Confirmed
                            </span>
                          )}
                          <span className={`retention-chip ${f.retention_status}`}>
                            Hindsight: {f.retention_status}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-substate">
                  No editor corrections recorded yet. Task is currently running as originally recommended.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="drawer-loading">Task record not found.</div>
        )}
      </aside>
    </div>
  );
}
