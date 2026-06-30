"use client";

import Link from "next/link";
import {
  ShieldHalf,
  LayoutDashboard,
  ScanSearch,
  Sparkles,
  History,
  GitGraph,
  Github,
  Circle,
  Loader2,
  Database,
  FolderGit2,
  Plug,
  CircleUser,
  LogIn,
  type LucideIcon,
} from "lucide-react";
import type { HealthResponse } from "@/lib/types";
import { useAuth } from "@/lib/auth";

export type ConsoleView = "overview" | "connect" | "firewall" | "rules" | "replay" | "graph" | "account";

const NAV: { id: ConsoleView; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "connect", label: "Connect agent", icon: Plug },
  { id: "firewall", label: "Firewall", icon: ScanSearch },
  { id: "rules", label: "Coding rules", icon: Sparkles },
  { id: "replay", label: "Session replay", icon: History },
  { id: "graph", label: "Knowledge graph", icon: GitGraph },
  { id: "account", label: "Account & keys", icon: CircleUser },
];

export function Sidebar({
  view,
  setView,
  health,
  onSeed,
  seeding,
  canWrite,
}: {
  view: ConsoleView;
  setView: (v: ConsoleView) => void;
  health: HealthResponse | null;
  onSeed: () => void;
  seeding: boolean;
  canWrite: boolean;
}) {
  const online = !!health && health.status === "ok";
  const mem = health?.counts?.Memory ?? 0;
  const { user, profile, activeKey } = useAuth();

  return (
    <aside className="z-30 flex shrink-0 flex-col border-b border-ink-800 bg-ink-950/80 backdrop-blur md:sticky md:top-0 md:h-screen md:w-64 md:border-b-0 md:border-r">
      {/* brand */}
      <div className="flex items-center gap-2.5 px-4 py-4">
        <Link
          href="/"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-firewall-600/40 bg-firewall-500/10 text-firewall-400"
        >
          <ShieldHalf className="h-4 w-4" />
        </Link>
        <div>
          <div className="text-sm font-semibold tracking-tight text-slate-100">ContextFirewall</div>
          <div className="-mt-0.5 text-[11px] text-slate-500">Guardrails for the memory layer</div>
        </div>
      </div>

      {/* active project */}
      <div className="px-4 pb-3">
        <div className="flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-900/60 px-3 py-2">
          <FolderGit2 className="h-4 w-4 shrink-0 text-firewall-400" />
          <div className="min-w-0">
            <div className="truncate font-mono text-xs text-slate-200">taskflow-api</div>
            <div className="text-[10px] text-slate-500">sample project</div>
          </div>
        </div>
      </div>

      {/* nav */}
      <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-visible">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setView(id)}
            className={`flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors ${
              view === id
                ? "bg-firewall-500/10 text-firewall-400 ring-1 ring-inset ring-firewall-600/30"
                : "text-slate-400 hover:bg-ink-850 hover:text-slate-200"
            }`}
          >
            <Icon className="h-4 w-4 shrink-0" /> {label}
          </button>
        ))}
      </nav>

      {/* footer */}
      <div className="border-t border-ink-800 px-4 py-3">
        <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
          <Circle className={`h-2 w-2 ${online ? "fill-pass text-pass" : "fill-block text-block"}`} />
          {online ? (
            <span>
              Cognee live · <span className="font-mono text-slate-400">{mem}</span> memories
            </span>
          ) : (
            <span>backend offline</span>
          )}
        </div>
        <button
          onClick={() => setView("account")}
          className="mt-3 w-full rounded-xl border border-ink-700 bg-ink-900/50 p-3 text-left transition-colors hover:border-ink-600"
        >
          {user ? (
            <>
              <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-200">
                <CircleUser className="h-3.5 w-3.5 text-firewall-400" />
                <span className="truncate">{profile?.email ?? user.email}</span>
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                ns <span className="font-mono text-slate-400">{profile?.namespace ?? "…"}</span>
                {" · "}
                {activeKey ? (
                  <span className="text-pass">key active</span>
                ) : (
                  <span className="text-slate-500">no active key</span>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-firewall-400">
              <LogIn className="h-3.5 w-3.5" /> Sign in for your own namespace
            </div>
          )}
        </button>
        <button
          onClick={onSeed}
          disabled={seeding || !canWrite}
          title={!canWrite ? "Read-only demo mode. Operator token required to write." : undefined}
          className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-ink-600 hover:text-slate-100 disabled:opacity-60"
        >
          {seeding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
          Reload sample project
        </button>
        <a
          href="https://github.com/himanshu748/ContextFirewall"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-slate-500 transition-colors hover:text-slate-300"
        >
          <Github className="h-3.5 w-3.5" /> Source on GitHub
        </a>
      </div>
    </aside>
  );
}
