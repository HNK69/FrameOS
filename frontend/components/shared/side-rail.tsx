"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrainCircuit, ShieldCheck, Sparkles } from "lucide-react";
import { NavItem } from "./topbar";

interface SideRailProps {
  navItems: NavItem[];
  bottomLinkHref?: string;
  bottomLinkTitle?: string;
}

export function SideRail({
  navItems,
  bottomLinkHref = "/production",
  bottomLinkTitle = "Client Intelligence & Memory",
}: SideRailProps) {
  const pathname = usePathname();

  const isActive = (item: NavItem) => {
    if (item.exact) return pathname === item.href;
    if (item.href === "/" && pathname !== "/") return false;
    return pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
  };

  return (
    <aside className="side-rail" aria-label="Quick Actions">
      <div className="rail-primary-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={active ? "selected" : ""}
              title={item.label}
              aria-label={item.label}
            >
              <Icon size={18} />
            </Link>
          );
        })}
      </div>

      <div className="rail-spacer" />

      <div className="rail-utility-nav">
        {bottomLinkHref && (
          <Link href={bottomLinkHref} title={bottomLinkTitle} aria-label={bottomLinkTitle}>
            <BrainCircuit size={18} />
          </Link>
        )}

        <div className="rail-bottom" title="Enterprise Shield & Isolated Tenant Memory">
          <ShieldCheck size={17} />
        </div>
      </div>
    </aside>
  );
}
