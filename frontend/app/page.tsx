"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  FileCheck,
  Film,
  Layers,
  ShieldCheck,
  Sparkles,
  Tv,
  Users,
  Video,
  Wand2,
} from "lucide-react";
import { FrameOpsLogo } from "@/components/shared/frameops-logo";
import { TopBar } from "@/components/shared/topbar";

export default function LandingPage() {
  const [authStatus, setAuthStatus] = useState<{ setup_required: boolean } | null>(null);

  useEffect(() => {
    fetch("/api/auth/status")
      .then((r) => r.json())
      .then(setAuthStatus)
      .catch(() => {});
  }, []);

  return (
    <div className="app-frame" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Topbar */}
      <TopBar
        persona="public"
        navItems={[
          { href: "/client/agencies", label: "Agency Catalog", icon: Sparkles },
          { href: "/portal", label: "Review Portal", icon: Film },
        ]}
      />

      {/* Main Hero */}
      <main
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "50px 20px 40px",
          textAlign: "center",
        }}
      >
        <div style={{ maxWidth: "860px", margin: "0 auto" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 16px",
              borderRadius: "99px",
              background: "rgba(164,90,255,.08)",
              border: "1px solid rgba(164,90,255,.3)",
              color: "#d8b4fe",
              fontSize: "11px",
              fontFamily: "var(--mono)",
              letterSpacing: "0.06em",
              marginBottom: "24px",
            }}
          >
            <span className="pip-dot status-ready" style={{ boxShadow: "0 0 10px #4bd6a0" }} />
            Remember Every Client. Perfect Every Project.
          </div>

          <h1
            style={{
              font: "600 clamp(32px, 4.5vw, 56px) var(--display)",
              letterSpacing: "-0.04em",
              lineHeight: 1.12,
              margin: "0 0 20px",
              color: "#fff",
            }}
          >
            The Operating System for{" "}
            <span
              style={{
                background: "linear-gradient(135deg, #c084fc, #9333ea 50%, #6366f1)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Video Production
            </span>
          </h1>

          <p
            style={{
              fontSize: "clamp(13px, 1.2vw, 16px)",
              color: "#9ca0b5",
              maxWidth: "680px",
              margin: "0 auto 40px",
              lineHeight: 1.6,
            }}
          >
            Connect clients with premier video-editing agencies. Submit structured briefs,
            review frame-accurate video cuts, and translate feedback directly into DaVinci Resolve
            workflows—powered by adaptive client memory.
          </p>

          {/* Persona Entry Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(290px, 1fr))",
              gap: "20px",
              maxWidth: "780px",
              margin: "0 auto",
              textAlign: "left",
            }}
          >
            {/* Client Card */}
            <div
              className="panel"
              style={{
                padding: "28px",
                display: "flex",
                flexDirection: "column",
                position: "relative",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "12px",
                  background: "linear-gradient(145deg, #2a1645, #141221)",
                  border: "1px solid rgba(164,90,255,.3)",
                  display: "grid",
                  placeItems: "center",
                  color: "#d8b4fe",
                  marginBottom: "16px",
                }}
              >
                <Film size={22} />
              </div>

              <h2 style={{ margin: "0 0 6px", font: "600 20px var(--display)", color: "#fff" }}>
                I&apos;m a Client
              </h2>

              <p style={{ margin: "0 0 22px", fontSize: "12px", color: "#9295a8", lineHeight: 1.55, flex: 1 }}>
                Discover verified agencies, submit creative briefs, track production timelines,
                and review video deliverables with timecode comments.
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <Link
                  href="/client/register"
                  className="primary-button"
                  style={{ height: "40px", width: "100%", justifyContent: "center" }}
                >
                  Get Started Free <ArrowRight size={14} />
                </Link>
                <Link
                  href="/client/login"
                  className="quiet-button"
                  style={{ height: "38px", width: "100%", justifyContent: "center" }}
                >
                  Client Sign In
                </Link>
              </div>
            </div>

            {/* Agency Card */}
            <div
              className="panel"
              style={{
                padding: "28px",
                display: "flex",
                flexDirection: "column",
                position: "relative",
                overflow: "hidden",
                border: "1px solid rgba(164,90,255,.3)",
                background: "linear-gradient(150deg, rgba(28,21,46,.95), rgba(14,15,26,.98))",
              }}
            >
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "12px",
                  background: "linear-gradient(145deg, #431f78, #181328)",
                  border: "1px solid rgba(164,90,255,.5)",
                  display: "grid",
                  placeItems: "center",
                  color: "#fff",
                  boxShadow: "0 0 20px rgba(164,90,255,.35)",
                  marginBottom: "16px",
                }}
              >
                <Sparkles size={22} />
              </div>

              <h2 style={{ margin: "0 0 6px", font: "600 20px var(--display)", color: "#fff" }}>
                I&apos;m an Agency
              </h2>

              <p style={{ margin: "0 0 22px", fontSize: "12px", color: "#9295a8", lineHeight: 1.55, flex: 1 }}>
                Publish your studio profile, receive qualified client briefs, manage production
                milestones, and execute edits with AI-backed client intelligence.
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <Link
                  href="/agency/register"
                  className="primary-button"
                  style={{
                    height: "40px",
                    width: "100%",
                    justifyContent: "center",
                    boxShadow: "0 8px 25px rgba(164,90,255,.4)",
                  }}
                >
                  Register Agency Workspace <ArrowRight size={14} />
                </Link>
                <Link
                  href="/agency/login"
                  className="quiet-button"
                  style={{ height: "38px", width: "100%", justifyContent: "center" }}
                >
                  Agency Studio Login
                </Link>
              </div>
            </div>
          </div>

          {authStatus?.setup_required && (
            <div
              className="panel"
              style={{
                marginTop: "28px",
                padding: "14px 20px",
                borderColor: "rgba(237,186,98,.35)",
                background: "rgba(237,186,98,.08)",
                display: "inline-flex",
                alignItems: "center",
                gap: "10px",
                color: "#f0ce84",
                fontSize: "11px",
              }}
            >
              <span>First-time setup required:</span>
              <Link href="/agency/register" style={{ color: "#fff", textDecoration: "underline", fontWeight: 600 }}>
                Create the first workspace owner account →
              </Link>
            </div>
          )}
        </div>
      </main>

      {/* Feature Strip */}
      <section
        style={{
          borderTop: "1px solid var(--line)",
          padding: "36px 20px",
          marginTop: "auto",
        }}
      >
        <div
          style={{
            maxWidth: "1100px",
            margin: "0 auto",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "20px",
          }}
        >
          {[
            {
              icon: Wand2,
              title: "AI Feedback Extraction",
              desc: "Synthesize unstructured client feedback into structured Resolve cut instructions.",
            },
            {
              icon: BrainCircuit,
              title: "Isolated Client Memory",
              desc: "Hindsight memory banks preserve creative preferences across projects with zero leakage.",
            },
            {
              icon: Film,
              title: "Frame-Accurate Review",
              desc: "Collaborative timecode comments and version approval pipeline.",
            },
            {
              icon: ShieldCheck,
              title: "Enterprise Studio RBAC",
              desc: "Strict multi-tenant workspace isolation for agency rosters and clients.",
            },
          ].map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="panel"
              style={{
                padding: "18px",
                background: "rgba(255,255,255,.02)",
                display: "flex",
                flexDirection: "column",
                gap: "8px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--violet)" }}>
                <Icon size={16} />
                <span style={{ font: "600 12px var(--display)", color: "#fff" }}>{title}</span>
              </div>
              <p style={{ margin: 0, fontSize: "11px", color: "#85899e", lineHeight: 1.5 }}>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="app-footer">
        <span>FRAMEOPS <i>·</i> Remember Every Client. Perfect Every Project.</span>
        <span>Enterprise Video Production Platform</span>
      </footer>
    </div>
  );
}
