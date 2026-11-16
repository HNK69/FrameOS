"use client";

import React from "react";
import { Sparkles, LucideIcon } from "lucide-react";

interface EmptyStateProps {
  title: string;
  body: string;
  icon?: LucideIcon;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  body,
  icon: Icon = Sparkles,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`empty-state ${className}`}>
      <div className="empty-orbit">
        <Icon size={20} />
      </div>
      <b>{title}</b>
      <p>{body}</p>
      {action && <div className="empty-action-wrap">{action}</div>}
    </div>
  );
}
