"use client";

import Link from "next/link";

interface FrameOpsLogoProps {
  href?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function FrameOpsLogo({ href = "/", size = "md", className = "" }: FrameOpsLogoProps) {
  const content = (
    <div className={`brand-lockup ${className}`}>
      <div className={`logo-mark ${size === "lg" ? "large" : ""}`}>
        <span>F</span>
      </div>
      <span className="brand-name">
        FRAME<span>OPS</span>
      </span>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="brand-link" style={{ textDecoration: "none" }}>
        {content}
      </Link>
    );
  }

  return content;
}
