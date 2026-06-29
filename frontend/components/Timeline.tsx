"use client";

import {
  MessageSquare,
  Wrench,
  Terminal,
  FileDiff,
  AlertTriangle,
  CheckCircle2,
  Flag,
  Circle,
  type LucideIcon,
} from "lucide-react";
import type { TimelineEvent } from "@/lib/types";

const KIND: Record<string, { icon: LucideIcon; color: string; ring: string }> = {
  prompt: { icon: MessageSquare, color: "text-sky-400", ring: "border-sky-500/30 bg-sky-500/10" },
  tool_call: { icon: Wrench, color: "text-violet-400", ring: "border-violet-500/30 bg-violet-500/10" },
  terminal: { icon: Terminal, color: "text-slate-300", ring: "border-slate-500/30 bg-slate-500/10" },
  file_change: { icon: FileDiff, color: "text-amber-400", ring: "border-amber-500/30 bg-amber-500/10" },
  error: { icon: AlertTriangle, color: "text-rose-400", ring: "border-rose-500/30 bg-rose-500/10" },
  fix: { icon: CheckCircle2, color: "text-emerald-400", ring: "border-emerald-500/30 bg-emerald-500/10" },
  decision: { icon: Flag, color: "text-firewall-400", ring: "border-firewall-500/30 bg-firewall-500/10" },
};

export function Timeline({ events }: { events: TimelineEvent[] }) {
  if (!events.length) {
    return <div className="py-12 text-center text-sm text-slate-500">No recorded events.</div>;
  }
  return (
    <ol className="relative ml-3 border-l border-ink-700">
      {events.map((e, i) => {
        const meta = KIND[e.kind] ?? { icon: Circle, color: "text-slate-400", ring: "border-ink-600 bg-ink-800" };
        const Icon = meta.icon;
        return (
          <li key={e.event_id || i} className="mb-5 ml-6 animate-fade-up" style={{ animationDelay: `${i * 30}ms` }}>
            <span
              className={`absolute -left-[13px] flex h-6 w-6 items-center justify-center rounded-full border ${meta.ring}`}
            >
              <Icon className={`h-3 w-3 ${meta.color}`} />
            </span>
            <div className="flex items-center gap-2">
              <span className={`font-mono text-[10px] uppercase tracking-wide ${meta.color}`}>{e.kind}</span>
              {e.timestamp && (
                <span className="font-mono text-[10px] text-slate-600">
                  {e.timestamp.replace("T", " ").slice(0, 16)}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm leading-snug text-slate-300">{e.content}</p>
          </li>
        );
      })}
    </ol>
  );
}
