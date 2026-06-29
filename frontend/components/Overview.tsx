"use client";

import {
  Database,
  ShieldCheck,
  ShieldX,
  Network,
  Activity,
  Boxes,
  ArrowRight,
  Upload,
  type LucideIcon,
} from "lucide-react";
import type { AuditResponse, HealthResponse } from "@/lib/types";
import type { ConsoleView } from "./Sidebar";

function Stat({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: LucideIcon;
  label: string;
  value: number | string;
  tone?: "default" | "pass" | "block";
}) {
  const accent =
    tone === "pass" ? "text-pass" : tone === "block" ? "text-block" : "text-firewall-400";
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900/50 p-4">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-slate-500">
        <Icon className={`h-3.5 w-3.5 ${accent}`} /> {label}
      </div>
      <div className="mt-2 font-mono text-2xl font-semibold text-slate-100">{value}</div>
    </div>
  );
}

export function Overview({
  health,
  audit,
  onView,
  onIngest,
}: {
  health: HealthResponse | null;
  audit: AuditResponse | null;
  onView: (v: ConsoleView) => void;
  onIngest: () => void;
}) {
  const c = health?.counts ?? {};
  const p = (health?.profile ?? {}) as Record<string, unknown>;
  const str = (k: string) => (p[k] != null ? String(p[k]) : "-");

  return (
    <div className="space-y-7">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-100">Overview</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-400">
          ContextFirewall governs the memory of AI coding agents. It records sessions into a Cognee
          knowledge graph and audits every remembered fact before it reaches the next agent.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat icon={Database} label="Memories" value={c.Memory ?? 0} />
        <Stat icon={ShieldCheck} label="Approved" value={audit?.passed_count ?? "-"} tone="pass" />
        <Stat icon={ShieldX} label="Blocked" value={audit?.blocked_count ?? "-"} tone="block" />
        <Stat icon={Boxes} label="Entities" value={c.Entity ?? 0} />
        <Stat icon={Activity} label="Events" value={c.SessionEvent ?? 0} />
        <Stat icon={Network} label="Graph edges" value={c._edges ?? 0} />
      </div>

      {/* infrastructure */}
      <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-5">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Live infrastructure
        </div>
        <div className="mt-3 grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <span className="text-slate-500">Graph</span>{" "}
            <span className="font-mono text-slate-200">{str("graph_provider")}</span>
          </div>
          <div>
            <span className="text-slate-500">Relational</span>{" "}
            <span className="font-mono text-slate-200">{str("relational_provider")}</span>
          </div>
          <div>
            <span className="text-slate-500">Vector</span>{" "}
            <span className="font-mono text-slate-200">{str("vector_provider")}</span>
          </div>
          <div>
            <span className="text-slate-500">Embeddings</span>{" "}
            <span className="font-mono text-slate-200">{str("embedding_dimensions")}d</span>
          </div>
          <div className="sm:col-span-2 lg:col-span-4">
            <span className="text-slate-500">LLM</span>{" "}
            <span className="font-mono text-slate-200">{str("llm_model")}</span>
          </div>
        </div>
      </div>

      {/* lifecycle */}
      <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-5">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Cognee memory lifecycle
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["remember", "Sessions are cognified into the graph."],
            ["recall", "Relevant memories are retrieved per task."],
            ["improve", "Durable coding rules are distilled (memify)."],
            ["forget", "Unsafe or stale memories are removed."],
          ].map(([verb, desc]) => (
            <div key={verb} className="rounded-lg border border-ink-800 bg-ink-950/40 p-3">
              <div className="font-mono text-sm font-semibold text-firewall-400">{verb}()</div>
              <div className="mt-1 text-xs leading-relaxed text-slate-400">{desc}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => onView("firewall")}
          className="group inline-flex items-center gap-2 rounded-lg bg-firewall-500 px-4 py-2.5 text-sm font-semibold text-ink-950 transition-colors hover:bg-firewall-400"
        >
          Run the firewall
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </button>
        <button
          onClick={onIngest}
          className="inline-flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-4 py-2.5 text-sm font-medium text-slate-200 transition-colors hover:border-ink-600 hover:text-slate-100"
        >
          <Upload className="h-4 w-4" /> Ingest your own session
        </button>
      </div>
    </div>
  );
}
