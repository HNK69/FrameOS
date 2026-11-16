"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, LucideIcon } from "lucide-react";
import { FrameOpsLogo } from "./frameops-logo";
import { api, json } from "@/lib/api";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
}

interface TopBarProps {
  navItems: NavItem[];
  persona?: "agency" | "client" | "public";
  user?: { email?: string; role?: string; full_name?: string } | null;
  onLogout?: () => void;
  pipLabel?: string;
}

export function TopBar({
  navItems,
  persona = "agency",
  user,
  onLogout,
  pipLabel,
}: TopBarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      if (onLogout) {
        onLogout();
      } else {
        await api("/api/auth/logout", json("POST"));
        router.push(persona === "client" ? "/client/login" : "/agency/login");
      }
    } catch {
      router.push("/");
    } finally {
      setLoggingOut(false);
    }
  };

  const isActive = (item: NavItem) => {
    if (item.exact) return pathname === item.href;
    if (item.href === "/" && pathname !== "/") return false;
    return pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
  };

  const userInitial = (user?.full_name || user?.email || "F").slice(0, 1).toUpperCase();
  const userName = user?.full_name || user?.email?.split("@")[0] || (persona === "agency" ? "Agency" : "Client");

  return (
    <header className="topbar">
      <FrameOpsLogo href={persona === "agency" ? "/agency/dashboard" : persona === "client" ? "/client/dashboard" : "/"} />

      <nav className="top-nav" aria-label="Main Navigation">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={isActive(item) ? "active" : ""}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="top-actions">
        <div className="service-pip" title="Service Readiness">
          <span className="pip-dot status-ready" />
          <span>{pipLabel || (persona === "agency" ? "Workspace" : persona === "client" ? "Client Portal" : "Active")}</span>
        </div>

        {user ? (
          <div className="profile-chip">
            <div className="avatar">{userInitial}</div>
            <span>{userName}</span>
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={14} />
            </button>
          </div>
        ) : persona === "public" ? (
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <Link href="/client/login" className="quiet-button">
              Client Sign In
            </Link>
            <Link href="/agency/login" className="primary-button">
              Agency Studio
            </Link>
          </div>
        ) : null}
      </div>
    </header>
  );
}
