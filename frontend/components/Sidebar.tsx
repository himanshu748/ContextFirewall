"use client";

import { useEffect, useState } from "react";
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
  KeyRound,
  type LucideIcon,
} from "lucide-react";
import type { HealthResponse } from "@/lib/types";
import {
  clearOperatorSettings,
  saveOperatorSettings,
  useOperatorSettings,
} from "@/lib/operator";

export type ConsoleView = "overview" | "connect" | "firewall" | "rules" | "replay" | "graph";

const NAV: { id: ConsoleView; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "connect", label: "Connect agent", icon: Plug },
  { id: "firewall", label: "Firewall", icon: ScanSearch },
  { id: "rules", label: "Coding rules", icon: Sparkles },
  { id: "replay", label: "Session replay", icon: History },
  { id: "graph", label: "Knowledge graph", icon: GitGraph },
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
  const operator = useOperatorSettings();
  const [token, setToken] = useState("");
  const [namespace, setNamespace] = useState("");

  useEffect(() => {
    setToken(operator.token);
    setNamespace(operator.namespace);
  }, [operator.token, operator.namespace]);

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
        <div className="mt-3 rounded-xl border border-ink-700 bg-ink-900/50 p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">
            <KeyRound className="h-3.5 w-3.5 text-firewall-400" /> Operator
          </div>
          <div className="mt-2 space-y-2">
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Write token"
              className="w-full rounded-md border border-ink-700 bg-ink-950 px-2.5 py-1.5 font-mono text-[11px] text-slate-200 placeholder:text-slate-600 outline-none ring-0 focus:border-firewall-500/50"
            />
            <input
              value={namespace}
              onChange={(e) => setNamespace(e.target.value)}
              placeholder="Namespace (optional)"
              className="w-full rounded-md border border-ink-700 bg-ink-950 px-2.5 py-1.5 font-mono text-[11px] text-slate-200 placeholder:text-slate-600 outline-none ring-0 focus:border-firewall-500/50"
            />
            <div className="flex gap-2">
              <button
                onClick={() => saveOperatorSettings({ token: token.trim(), namespace: namespace.trim() })}
                className="flex-1 rounded-md border border-firewall-500/30 bg-firewall-500/10 px-2.5 py-1.5 text-[11px] font-medium text-firewall-400 transition-colors hover:bg-firewall-500/15"
              >
                Save
              </button>
              <button
                onClick={() => {
                  setToken("");
                  setNamespace("");
                  clearOperatorSettings();
                }}
                className="rounded-md border border-ink-700 bg-ink-850 px-2.5 py-1.5 text-[11px] font-medium text-slate-400 transition-colors hover:border-ink-600 hover:text-slate-200"
              >
                Clear
              </button>
            </div>
            <p className="text-[11px] leading-relaxed text-slate-500">
              {canWrite
                ? "Writes are enabled for this operator."
                : "Read-only demo mode. Paste an operator token to write."}
            </p>
          </div>
        </div>
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
