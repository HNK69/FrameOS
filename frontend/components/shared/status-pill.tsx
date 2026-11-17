"use client";

import React from "react";

export type StatusType =
  | "submitted"
  | "under_review"
  | "proposal_received"
  | "accepted"
  | "declined"
  | "cancelled"
  | "draft"
  | "active"
  | "in_review"
  | "completed"
  | "archived"
  | "pending"
  | "in_progress"
  | "blocked"
  | string;

interface StatusPillProps {
  status: StatusType;
  label?: string;
  className?: string;
}

const STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under Review",
  proposal_received: "Proposal Received",
  accepted: "Accepted",
  declined: "Declined",
  cancelled: "Cancelled",
  draft: "Draft",
  active: "Active",
  in_review: "In Review",
  completed: "Completed",
  archived: "Archived",
  pending: "Pending",
  in_progress: "In Progress",
  blocked: "Blocked",
};

export function StatusPill({ status, label, className = "" }: StatusPillProps) {
  const norm = (status || "").toLowerCase().replace(/\s+/g, "_");
  const display = label || STATUS_LABELS[norm] || status;

  return (
    <span className={`status-pill ${norm} ${className}`}>
      <span className={`status-dot ${norm}`} />
      {display}
    </span>
  );
}
