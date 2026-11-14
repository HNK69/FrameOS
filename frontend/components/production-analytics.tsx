"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Clock,
  FolderKanban,
  RotateCcw,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  UsersRound,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

interface ProductionAnalyticsProps {
  analytics: any;
  clients: any[];
  projects: any[];
  tasks: any[];
  readiness: any;
}

export function ProductionAnalytics({
  analytics,
  clients,
  projects,
  tasks,
  readiness,
}: ProductionAnalyticsProps) {
  const [liveData, setLiveData] = useState<any>(analytics);

  useEffect(() => {
    if (analytics) {
      setLiveData(analytics);
    } else {
      api("/api/production-analytics")
        .then((data) => setLiveData(data))
        .catch(() => {});
    }
  }, [analytics]);

  const p = liveData || {};
  const turnaround = p.turnaround || {};
  const revisions = p.revisions || {};
  const dailyRuns = p.activity || [];

  // Bounded check for presence of completed tasks / turnaround data
  const hasTurnaroundData = turnaround.has_turnaround_data && turnaround.avg_task_turnaround_hours !== null;

  return (
    <div className="analytics-intelligence-root">
      {/* KPI Top Grid */}
      <div className="kpi-row-6">
        <div className="panel kpi kpi-glow">
          <div className="kpi-top">
            <span>Active Projects</span>
            <span className="kpi-icon"><FolderKanban size={16} /></span>
          </div>
          <strong>{p.active_projects ?? "0"}</strong>
          <small>{p.completed_projects ?? 0} completed · {p.total_projects ?? 0} total</small>
          <div className="kpi-wave" />
        </div>

        <div className="panel kpi">
          <div className="kpi-top">
            <span>Pending Tasks</span>
            <span className="kpi-icon"><Clock size={16} /></span>
          </div>
          <strong>{p.pending_tasks ?? "0"}</strong>
          <small>Awaiting review / start</small>
        </div>

        <div className="panel kpi">
          <div className="kpi-top">
            <span>In Progress</span>
            <span className="kpi-icon"><Zap size={16} /></span>
          </div>
          <strong>{p.in_progress_tasks ?? "0"}</strong>
          <small>Active in DaVinci Resolve</small>
        </div>

        <div className="panel kpi">
          <div className="kpi-top">
            <span>Completed Tasks</span>
            <span className="kpi-icon"><CheckCircle2 size={16} /></span>
          </div>
          <strong>{p.completed_tasks ?? "0"}</strong>
          <small>{p.blocked_tasks ?? 0} currently blocked</small>
        </div>

        <div className="panel kpi">
          <div className="kpi-top">
            <span>Client Revisions</span>
            <span className="kpi-icon"><RotateCcw size={16} /></span>
          </div>
          <strong>{revisions.editor_corrections ?? "0"}</strong>
          <small>{revisions.client_confirmed ?? 0} confirmed preferences</small>
        </div>

        <div className="panel kpi">
          <div className="kpi-top">
            <span>Confirmed Memories</span>
            <span className="kpi-icon"><BrainCircuit size={16} /></span>
          </div>
          <strong>{p.memories_retained ?? "0"}</strong>
          <small>{p.memory_retrievals ?? 0} memory recalls</small>
        </div>
      </div>

      {/* Middle Analytical Row */}
      <div className="analytics-middle-grid">
        {/* Real Daily Activity Runs */}
        <section className="panel analytics-card">
          <div className="card-head">
            <div className="card-title">
              <span className="head-icon"><Activity size={16} /></span>
              <h2>Feedback Processing Activity</h2>
            </div>
            <span className="card-meta">PERSISTED RUNS</span>
          </div>

          {dailyRuns.length > 0 ? (
            <>
              <div className="bar-chart" aria-label="Processing runs by day">
                {dailyRuns.slice(-10).map((b: any, i: number) => (
                  <div key={i} className="bar-item">
                    <div
                      className="bar"
                      style={{ height: `${Math.max(14, Math.min(100, b.runs * 30))}%` }}
                      title={`${b.runs} runs on ${b.date}`}
                    />
                    <small>{String(b.date).slice(5)}</small>
                  </div>
                ))}
              </div>
              <div className="chart-caption">
                <span>Daily transcript ingestion runs</span>
                <b>{dailyRuns.reduce((sum: number, b: any) => sum + b.runs, 0)} total runs</b>
              </div>
            </>
          ) : (
            <div className="chart-empty">
              <Activity size={24} />
              <span>No transcript runs processed yet. Persisted activity will appear as transcripts are ingested.</span>
            </div>
          )}
        </section>

        {/* Turnaround & Operational Velocity */}
        <section className="panel turnaround-card">
          <div className="card-head">
            <div className="card-title">
              <span className="head-icon"><Clock size={16} /></span>
              <h2>Production Turnaround Indicators</h2>
            </div>
            <span className="card-meta">ACTUAL DELTAS</span>
          </div>

          {hasTurnaroundData ? (
            <div className="turnaround-content">
              <div className="turnaround-kpi">
                <span className="turnaround-label">Average Task Turnaround</span>
                <strong className="turnaround-value">{turnaround.avg_task_turnaround_hours}h</strong>
                <small>From AI recommendation to editor resolution ({turnaround.completed_samples_count} completed tasks)</small>
              </div>

              <div className="turnaround-split">
                <div>
                  <small>Fastest Resolution</small>
                  <b>{turnaround.min_task_turnaround_hours}h</b>
                </div>
                <div>
                  <small>Slowest Resolution</small>
                  <b>{turnaround.max_task_turnaround_hours}h</b>
                </div>
                {turnaround.avg_run_processing_seconds !== null && (
                  <div>
                    <small>Avg Pipeline Speed</small>
                    <b>{turnaround.avg_run_processing_seconds}s</b>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="empty-substate center">
              <Clock size={20} />
              <b>No turnaround records yet</b>
              <p>Turnaround indicators calculate dynamically as tasks are reviewed and completed in the production workflow.</p>
            </div>
          )}
        </section>

        {/* Task Priority & Status Breakdown */}
        <section className="panel distribution-card">
          <div className="card-head">
            <div className="card-title">
              <span className="head-icon"><Zap size={16} /></span>
              <h2>Production Queue Status</h2>
            </div>
            <span className="card-meta">{p.total_tasks ?? 0} TASKS</span>
          </div>

          {(p.total_tasks ?? 0) > 0 ? (
            <div className="distribution-content">
              <div className="dist-group">
                <span className="dist-title">By Priority</span>
                <div className="dist-bars">
                  {Object.entries(p.task_priority_distribution || {}).map(([key, count]: any) => (
                    <div key={key} className="dist-row">
                      <span className={`priority-label ${key}`}>{key}</span>
                      <div className="dist-progress">
                        <div
                          className={`dist-fill ${key}`}
                          style={{ width: `${(p.total_tasks > 0 ? (count / p.total_tasks) * 100 : 0)}%` }}
                        />
                      </div>
                      <b className="dist-val">{count}</b>
                    </div>
                  ))}
                </div>
              </div>

              <div className="dist-group">
                <span className="dist-title">By Execution State</span>
                <div className="status-chips-summary">
                  <span className="status-pill pending">Pending: {p.pending_tasks ?? 0}</span>
                  <span className="status-pill in_progress">In Progress: {p.in_progress_tasks ?? 0}</span>
                  <span className="status-pill completed">Completed: {p.completed_tasks ?? 0}</span>
                  <span className="status-pill blocked">Blocked: {p.blocked_tasks ?? 0}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-substate center">
              <Zap size={20} />
              <b>Queue is currently empty</b>
              <p>Process a project transcript to generate production tasks and recommendations.</p>
            </div>
          )}
        </section>
      </div>

      {/* Client Intelligence & Memory Audit */}
      <section className="panel memory-analytics-panel">
        <div className="card-head">
          <div className="card-title">
            <span className="head-icon"><BrainCircuit size={16} /></span>
            <h2>Client Intelligence & Adaptive Memory Signals</h2>
          </div>
          <span className="card-meta">ISOLATED PER CLIENT</span>
        </div>

        {clients.length > 0 ? (
          <div className="client-memory-table">
            <div className="table-header memory-header">
              <span>Client</span>
              <span>Brand</span>
              <span>Memory Bank</span>
              <span>Verified Retentions</span>
              <span>Confirmed Preferences</span>
              <span />
            </div>

            {clients.map((c: any) => {
              const mem = p.client_memories?.find((m: any) => m.client_id === c.id);
              return (
                <div key={c.id} className="table-row memory-row">
                  <div className="client-info">
                    <div className="client-monogram">{c.name.slice(0, 1).toUpperCase()}</div>
                    <b>{c.name}</b>
                  </div>
                  <span>{c.brand || "—"}</span>
                  <span className="bank-status-pill">
                    <i className={c.memory_status === "ready" ? "status-ready" : "status-off"} />
                    {c.memory_status === "ready" ? "Connected" : "Unavailable"}
                  </span>
                  <b>{mem?.memories_retained ?? c.memories_retained ?? 0} memories</b>
                  <b>{mem?.confirmed_preferences ?? 0} confirmed</b>
                  <Link href={`/production?client=${c.id}`} className="row-link" title="Open client workflow">
                    <ArrowRight size={15} />
                  </Link>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <BrainCircuit size={24} />
            <b>No client profiles registered</b>
            <p>Create client profiles to establish dedicated Hindsight memory banks and track adaptive preferences.</p>
          </div>
        )}
      </section>
    </div>
  );
}
