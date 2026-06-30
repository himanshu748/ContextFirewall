"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, Plug, Server } from "lucide-react";
import { api } from "@/lib/api";
import type { ActivityEntry } from "@/lib/types";

function ago(ts: string): string {
  const d = Date.now() - new Date(ts).getTime();
  const s = Math.max(0, Math.floor(d / 1000));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

export function ActivityFeed({ pollMs = 5000 }: { pollMs?: number }) {
  const [events, setEvents] = useState<ActivityEntry[] | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () =>
      api
        .activity(20)
        .then((r) => alive && setEvents(r.events))
        .catch(() => alive && setEvents((e) => e ?? []));
    tick();
    timer.current = setInterval(tick, pollMs);
    return () => {
      alive = false;
      if (timer.current) clearInterval(timer.current);
    };
  }, [pollMs]);

  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900/40">
      <div className="flex items-center gap-2 border-b border-ink-800 px-4 py-2.5">
        <Activity className="h-3.5 w-3.5 text-firewall-400" />
        <span className="text-sm font-medium text-slate-200">Live firewall activity</span>
        <span className="ml-auto flex items-center gap-1.5 text-[11px] text-slate-500">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-firewall-400" /> polling
        </span>
      </div>
      <div className="max-h-72 overflow-y-auto">
        {events === null ? (
          <div className="px-4 py-6 text-center text-xs text-slate-500">Connecting…</div>
        ) : events.length === 0 ? (
          <div className="px-4 py-6 text-center text-xs text-slate-500">
            No calls yet. Connect an agent over MCP or run an audit and they will appear here.
          </div>
        ) : (
          <ul className="divide-y divide-ink-800/70">
            {events.map((e) => {
              const isMcp = e.source === "mcp";
              return (
                <li key={e.id} className="flex items-start gap-3 px-4 py-2.5">
                  <span
                    className={`mt-0.5 inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                      isMcp ? "border-firewall-600/40 bg-firewall-500/10 text-firewall-400" : "border-ink-700 bg-ink-850 text-slate-400"
                    }`}
                  >
                    {isMcp ? <Plug className="h-3 w-3" /> : <Server className="h-3 w-3" />}
                    {isMcp ? "MCP" : "API"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-mono text-xs text-slate-200">{e.tool}</div>
                    <div className="truncate text-[11px] text-slate-500">{e.detail}</div>
                  </div>
                  <span className="shrink-0 text-[10px] text-slate-600">{ago(e.ts)}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
