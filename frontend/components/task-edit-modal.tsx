"use client";

import { useState } from "react";
import { Check, CheckCircle2, Lock, ShieldAlert, Sparkles, X } from "lucide-react";
import { api, json } from "@/lib/api";

export type Task = {
  id: number;
  workspace_id?: number;
  client_id?: number;
  client_name?: string;
  project_id?: number;
  project_name?: string;
  run_id?: number;
  title: string;
  category: string;
  instruction: string;
  original_recommendation?: string;
  is_corrected?: boolean;
  latest_correction?: string;
  resolve_workflow: string;
  priority: string;
  source: string;
  evidence: string;
  confidence: number;
  requires_confirmation: boolean;
  status: string;
  created_at?: string;
  feedback_count?: number;
  latest_feedback?: any;
  feedback_history?: any[];
};

interface TaskEditModalProps {
  task: Task;
  onClose: () => void;
  onSaved: (updatedTask: Task) => void;
  notify: (msg: string) => void;
}

export function TaskEditModal({ task, onClose, onSaved, notify }: TaskEditModalProps) {
  const [instruction, setInstruction] = useState(task.instruction);
  const [priority, setPriority] = useState(task.priority);
  const [status, setStatus] = useState(task.status);
  const [resolveWorkflow, setResolveWorkflow] = useState(task.resolve_workflow);
  const [knowledgeType, setKnowledgeType] = useState<string>("editor_correction");
  const [clientConfirmed, setClientConfirmed] = useState(false);
  const [correctionNote, setCorrectionNote] = useState("");
  const [busy, setBusy] = useState(false);

  const originalRec = task.original_recommendation || task.instruction;
  const hasInstructionChanged = instruction.trim() !== originalRec.trim();

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);

    try {
      const payload: any = {
        priority,
        status,
        resolve_workflow: resolveWorkflow.trim(),
        knowledge_type: knowledgeType,
        client_confirmed: clientConfirmed,
      };

      if (hasInstructionChanged) {
        payload.instruction = instruction.trim();
      }
      if (correctionNote.trim()) {
        payload.correction_note = correctionNote.trim();
      }

      const updated = await api<Task>(`/api/tasks/${task.id}`, json("PATCH", payload));
      notify(`Task #${task.id} updated with editor provenance.`);
      onSaved(updated);
      onClose();
    } catch (err: any) {
      notify(err.message || "Failed to update task");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div className="modal-title">
            <span className="head-icon"><Sparkles size={16} /></span>
            <div>
              <h3>Review & Correct Production Task</h3>
              <small>Task #{task.id} · {task.client_name || "Client"} / {task.project_name || "Project"}</small>
            </div>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close modal">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSave} className="modal-form">
          {/* Immutable Original AI Recommendation */}
          <div className="original-rec-box">
            <div className="original-rec-label">
              <span><Lock size={12} /> Original AI Recommendation</span>
              <small className="provenance-tag">Source: {task.source} ({Math.round(task.confidence * 100)}% conf)</small>
            </div>
            <p className="original-rec-text">{originalRec}</p>
            {task.evidence && (
              <div className="original-rec-evidence">
                <b>Evidence from client:</b> “{task.evidence}”
              </div>
            )}
          </div>

          {/* Editor Instruction / Correction */}
          <label className="field-group">
            <div className="field-head">
              <span>Editor Instruction</span>
              <small className={hasInstructionChanged ? "text-violet" : "text-muted"}>
                {hasInstructionChanged ? "Corrected by Editor" : "Matches original recommendation"}
              </small>
            </div>
            <textarea
              required
              rows={3}
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Enter the refined or corrected instruction for the editor..."
            />
          </label>

          {/* Resolve Workflow */}
          <label className="field-group">
            <div className="field-head">
              <span>DaVinci Resolve Workflow Step</span>
            </div>
            <input
              value={resolveWorkflow}
              onChange={(e) => setResolveWorkflow(e.target.value)}
              placeholder="e.g. Color page -> Node 03 -> Saturation +15"
            />
          </label>

          {/* Status & Priority Grid */}
          <div className="form-grid-2">
            <label className="field-group">
              <span className="field-head">Task Status</span>
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="pending">Pending Review</option>
                <option value="in_progress">In Progress (Active in Resolve)</option>
                <option value="completed">Completed & Verified</option>
                <option value="blocked">Blocked (Missing Assets/Info)</option>
                <option value="accepted">Accepted (As Recommended)</option>
                <option value="rejected">Rejected (Discarded)</option>
              </select>
            </label>

            <label className="field-group">
              <span className="field-head">Priority</span>
              <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                <option value="urgent">Urgent (Immediate Turnaround)</option>
                <option value="high">High (Current Cut)</option>
                <option value="medium">Medium (Standard Timeline)</option>
                <option value="low">Low (Polish / Optional)</option>
              </select>
            </label>
          </div>

          {/* Adaptive Intelligence Classification */}
          <div className="adaptive-classification-box">
            <div className="classification-title">
              <span>Adaptive Intelligence Classification</span>
              <small>Guides how this decision updates the client memory bank</small>
            </div>
            <div className="radio-options">
              <label className={`radio-pill ${knowledgeType === "editor_correction" ? "chosen" : ""}`}>
                <input
                  type="radio"
                  name="knowledgeType"
                  value="editor_correction"
                  checked={knowledgeType === "editor_correction"}
                  onChange={() => setKnowledgeType("editor_correction")}
                />
                <div>
                  <b>Editor Technical Correction</b>
                  <small>Refinement of technique or parameters for this task</small>
                </div>
              </label>

              <label className={`radio-pill ${knowledgeType === "client_confirmed" ? "chosen" : ""}`}>
                <input
                  type="radio"
                  name="knowledgeType"
                  value="client_confirmed"
                  checked={knowledgeType === "client_confirmed"}
                  onChange={() => {
                    setKnowledgeType("client_confirmed");
                    setClientConfirmed(true);
                  }}
                />
                <div>
                  <b>Client-Confirmed Preference</b>
                  <small>Explicitly confirmed with the client; saved to client bank</small>
                </div>
              </label>

              <label className={`radio-pill ${knowledgeType === "reusable_client_knowledge" ? "chosen" : ""}`}>
                <input
                  type="radio"
                  name="knowledgeType"
                  value="reusable_client_knowledge"
                  checked={knowledgeType === "reusable_client_knowledge"}
                  onChange={() => setKnowledgeType("reusable_client_knowledge")}
                />
                <div>
                  <b>Reusable Client Knowledge</b>
                  <small>Editor insight that applies to all future projects for this client</small>
                </div>
              </label>

              <label className={`radio-pill ${knowledgeType === "project_specific" ? "chosen" : ""}`}>
                <input
                  type="radio"
                  name="knowledgeType"
                  value="project_specific"
                  checked={knowledgeType === "project_specific"}
                  onChange={() => setKnowledgeType("project_specific")}
                />
                <div>
                  <b>Project-Specific Decision</b>
                  <small>Applies only to this project cut; will not affect future projects</small>
                </div>
              </label>
            </div>

            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={clientConfirmed}
                onChange={(e) => setClientConfirmed(e.target.checked)}
              />
              <span>Client explicitly confirmed this preference</span>
            </label>
          </div>

          {/* Optional Correction Note */}
          <label className="field-group">
            <div className="field-head">
              <span>Provenance Note / Reason</span>
              <small className="text-muted">Recorded in audit history</small>
            </div>
            <input
              value={correctionNote}
              onChange={(e) => setCorrectionNote(e.target.value)}
              placeholder="e.g. Switched to magic mask per editor preference; client agreed on call"
            />
          </label>

          <div className="modal-actions">
            <button type="button" className="quiet-button" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button type="submit" className="primary-button" disabled={busy}>
              {busy ? "Saving Provenance..." : "Save Task & Provenance"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
