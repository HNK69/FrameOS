"use client";

import React from "react";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  variant?: "default" | "glow";
  className?: string;
}

export function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = "default",
  className = "",
}: MetricCardProps) {
  return (
    <div className={`panel kpi ${variant === "glow" ? "kpi-glow" : ""} ${className}`}>
      <div className="kpi-top">
        <span>{title}</span>
        <span className="kpi-icon">
          <Icon size={16} />
        </span>
      </div>
      <strong>{value}</strong>
      {subtitle && <small>{subtitle}</small>}
      {variant === "glow" && <div className="kpi-wave" />}
    </div>
  );
}
