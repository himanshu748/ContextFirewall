"use client";

import { useState } from "react";
import { X, Trash2, Loader2, CheckCircle2, XCircle } from "lucide-react";
import type { MemoryVerdict } from "@/lib/types";
import { CHECK_META, KindBadge, TrustMeter } from "./badges";

export function MemoryDrawer({
  verdict,
  onClose,
  onForget,
  onJumpToEvidence,
}: {
  verdict: MemoryVerdict | null;
  onClose: () => void;
  onForget?: (id: string) => Promise<void>;
  onJumpToEvidence?: (eventId: string) => void;
}) {
  const [forgetting, setForgetting] = useState(false);
  if (!verdict) return null;
  const v = verdict;
  const blocked = !v.passed;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="animate-fade-up relative h-full w-full max-w-md overflow-y-auto border-l border-ink-700 bg-ink-950 shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-ink-800 bg-ink-950/90 px-5 py-3 backdrop-blur">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                blocked ? "border-block-border bg-block-dim text-block" : "border-pass-border bg-pass-dim text-pass"
              }`}
            >
              {blocked ? "Blocked at the firewall" : "Approved"}
            </span>
            <KindBadge kind={v.kind} />
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-slate-500 transition-colors hover:bg-ink-850 hover:text-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-5 px-5 py-5">
          <p className="text-sm leading-relaxed text-slate-100">{v.text}</p>

          <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
            <div>
              <div className="text-slate-500">Subject</div>
              <div className="mt-0.5 font-mono text-slate-300">{v.subject || "—"}</div>
            </div>
            <div>
              <div className="text-slate-500">Recorded</div>
              <div className="mt-0.5 font-mono text-slate-300">{v.created_at || "—"}</div>
            </div>
            <div className="col-span-2">
              <div className="text-slate-500">Trust score</div>
              <div className="mt-1.5">
                <TrustMeter value={v.trust_score} />
              </div>
            </div>
            <div className="col-span-2">
              <div className="text-slate-500">From session</div>
              <div className="mt-0.5 font-mono text-[11px] text-slate-400">{v.source_session_id || "—"}</div>
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Firewall checks
            </div>
            <div className="space-y-2">
              {v.checks.map((ch) => {
                const meta = CHECK_META[ch.check];
                const Icon = meta?.icon;
                return (
                  <div
                    key={ch.check}
                    className={`rounded-lg border p-3 ${
                      ch.passed ? "border-ink-700 bg-ink-900/50" : "border-block-border/60 bg-block-dim/40"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-300">
                        {Icon ? <Icon className="h-3.5 w-3.5" /> : null}
                        {meta?.label ?? ch.check}
                      </div>
                      {ch.passed ? (
                        <span className="inline-flex items-center gap-1 text-[11px] text-pass">
                          <CheckCircle2 className="h-3.5 w-3.5" /> pass
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] text-block">
                          <XCircle className="h-3.5 w-3.5" /> blocked
                        </span>
                      )}
                    </div>
                    <p className={`mt-1.5 text-xs leading-relaxed ${ch.passed ? "text-slate-500" : "text-block/90"}`}>
                      {ch.reason}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {v.evidence_event_ids && v.evidence_event_ids.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Evidence</div>
              <div className="flex flex-wrap gap-1.5">
                {v.evidence_event_ids.map((eid) => (
                  <button
                    key={eid}
                    onClick={() => onJumpToEvidence?.(eid)}
                    className="rounded-md border border-ink-700 bg-ink-850 px-2 py-1 font-mono text-[10px] text-slate-400 transition-colors hover:border-firewall-600/50 hover:text-slate-200"
                  >
                    {eid}
                  </button>
                ))}
              </div>
              <p className="mt-1.5 text-[11px] text-slate-600">Recorded events that support this memory.</p>
            </div>
          )}

          {blocked && onForget && (
            <button
              onClick={async () => {
                setForgetting(true);
                try {
                  await onForget(v.memory_id);
                  onClose();
                } finally {
                  setForgetting(false);
                }
              }}
              disabled={forgetting}
              className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 text-xs font-medium text-slate-300 transition-colors hover:border-block-border hover:text-block disabled:opacity-50"
              title="Delete this memory from Cognee (graph + vector). The forget() verb."
            >
              {forgetting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              Forget this memory
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
