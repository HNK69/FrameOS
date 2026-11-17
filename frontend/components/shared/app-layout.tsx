"use client";

import React, { useEffect, useState } from "react";
import {
  AudioLines,
  FileText,
  Film,
  FolderKanban,
  LayoutDashboard,
  PlusCircle,
  Sparkles,
  UsersRound,
} from "lucide-react";
import { TopBar, NavItem } from "./topbar";
import { SideRail } from "./side-rail";
import { api } from "@/lib/api";

export const AGENCY_NAV: NavItem[] = [
  { href: "/agency/dashboard", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/agency/requests", label: "Requests", icon: FileText },
  { href: "/agency/profile", label: "Profile", icon: Sparkles },
  { href: "/clients", label: "Clients", icon: UsersRound },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/production", label: "Production", icon: AudioLines },
];

export const CLIENT_NAV: NavItem[] = [
  { href: "/client/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/client/agencies", label: "Agencies", icon: Sparkles },
  { href: "/client/requests/new", label: "New Brief", icon: PlusCircle },
  { href: "/portal", label: "Review Portal", icon: Film },
];

interface AppLayoutProps {
  children: React.ReactNode;
  persona?: "agency" | "client" | "public";
  navItems?: NavItem[];
  currentUser?: { email?: string; role?: string; full_name?: string } | null;
  onLogout?: () => void;
  pipLabel?: string;
  showSideRail?: boolean;
  maxWidth?: string;
}

export function AppLayout({
  children,
  persona = "agency",
  navItems,
  currentUser,
  onLogout,
  pipLabel,
  showSideRail = true,
  maxWidth,
}: AppLayoutProps) {
  const [user, setUser] = useState<any>(currentUser || null);

  useEffect(() => {
    if (currentUser !== undefined) {
      setUser(currentUser);
      return;
    }
    api("/api/me")
      .then((data) => {
        if (data && data.email) {
          setUser(data);
        }
      })
      .catch(() => {});
  }, [currentUser]);

  const activeNav = navItems || (persona === "agency" ? AGENCY_NAV : CLIENT_NAV);

  return (
    <div className="app-frame" style={maxWidth ? { maxWidth } : undefined}>
      <TopBar
        navItems={activeNav}
        persona={persona}
        user={user}
        onLogout={onLogout}
        pipLabel={pipLabel}
      />

      <div className={`workspace ${!showSideRail ? "no-rail" : ""}`}>
        {showSideRail && (
          <SideRail
            navItems={activeNav}
            bottomLinkHref={persona === "agency" ? "/production" : "/portal"}
            bottomLinkTitle={persona === "agency" ? "Production Intelligence" : "Client Portal"}
          />
        )}

        <main className="main-content">
          {children}

          <footer className="app-footer">
            <span>
              FRAMEOPS <i>·</i> Remember Every Client. Perfect Every Project.
            </span>
            <span>
              {persona === "agency"
                ? "Data shown from this workspace"
                : "Dedicated Client Intelligence & Video Review"}
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
