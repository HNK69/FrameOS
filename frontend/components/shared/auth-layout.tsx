"use client";

import React from "react";
import Link from "next/link";
import { FrameOpsLogo } from "./frameops-logo";

interface AuthLayoutProps {
  eyebrow?: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export function AuthLayout({
  eyebrow = "CLIENT INTELLIGENCE PLATFORM",
  title,
  subtitle,
  children,
  footer,
}: AuthLayoutProps) {
  return (
    <main className="auth-screen">
      <div className="auth-card panel">
        <div style={{ marginBottom: "20px" }}>
          <FrameOpsLogo href="/" />
        </div>

        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{subtitle}</p>

        {children}

        {footer && <div className="auth-card-footer mt-5">{footer}</div>}
      </div>
    </main>
  );
}
