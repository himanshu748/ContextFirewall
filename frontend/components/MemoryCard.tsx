"use client";

import { useState } from "react";
import { Trash2, Loader2, ChevronRight } from "lucide-react";
import type { MemoryVerdict } from "@/lib/types";
import { CheckBadge, KindBadge, TrustMeter } from "./badges";

export function MemoryCard({
  v,
  onForget,
  onSelect,
  canForget,
}: {
  v: MemoryVerdict;
  onForget?: (id: string) => Promise<void>;
  onSelect?: (v: MemoryVerdict) => void;
  canForget: boolean;
}) {
  const [forgetting, setForgetting] = useState(false);
  const blocked = !v.passed;

  return (
    <div
      onClick={() => onSelect?.(v)}
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={
        onSelect
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(v);
              }
            }
          : undefined
      }
      className={`group relative animate-fade-up rounded-xl border p-4 transition-colors ${
        onSelect ? "cursor-pointer" : ""
      } ${
        blocked
          ? "border-block-border/70 bg-block-dim/40 hover:bg-block-dim/60"
          : "border-ink-700 bg-ink-850/60 hover:border-pass-border/60"
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <CheckBadge check={v.block_check ?? "all"} passed={v.passed} />
          <KindBadge kind={v.kind} />
        </div>
        <TrustMeter value={v.trust_score} />
      </div>

      <p className={`text-sm leading-snug ${blocked ? "text-slate-300" : "text-slate-200"}`}>{v.text}</p>

      {v.subject && (
        <p className="mt-1.5 font-mono text-[10px] uppercase tracking-wide text-slate-600">
          subject: {v.subject}
          {v.created_at ? ` · ${v.created_at}` : ""}
        </p>
      )}

      {blocked && v.block_reason && (
        <div className="mt-3 rounded-lg border border-block-border/50 bg-ink-950/50 px-3 py-2 text-xs leading-relaxed text-block/90">
          {v.block_reason}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between">
        {blocked && onForget ? (
          <button
            onClick={async (e) => {
              e.stopPropagation();
              setForgetting(true);
              try {
                await onForget(v.memory_id);
              } finally {
                setForgetting(false);
              }
            }}
            disabled={forgetting || !canForget}
            className="inline-flex items-center gap-1.5 rounded-md border border-ink-700 bg-ink-800 px-2.5 py-1 text-[11px] font-medium text-slate-400 transition-colors hover:border-block-border hover:text-block disabled:opacity-50"
            title={
              canForget
                ? "Forget this memory in Cognee (graph + vector). Governance: the forget() verb."
                : "Read-only demo mode. Operator token required to forget."
            }
          >
            {forgetting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
            Forget
          </button>
        ) : (
          <span />
        )}
        {onSelect && (
          <span className="inline-flex items-center gap-0.5 text-[11px] text-slate-500 opacity-0 transition-opacity group-hover:opacity-100">
            Details <ChevronRight className="h-3 w-3" />
          </span>
        )}
      </div>
    </div>
  );
}
