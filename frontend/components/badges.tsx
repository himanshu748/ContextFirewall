import { Clock, GitCompareArrows, KeyRound, HelpCircle, ShieldCheck, type LucideIcon } from "lucide-react";
import type { CheckName } from "@/lib/types";

export const CHECK_META: Record<CheckName, { label: string; icon: LucideIcon }> = {
  staleness: { label: "Stale", icon: Clock },
  contradiction: { label: "Contradicted", icon: GitCompareArrows },
  secret: { label: "Secret", icon: KeyRound },
  evidence: { label: "Unsupported", icon: HelpCircle },
};

export function CheckBadge({ check, passed }: { check: CheckName | "all"; passed: boolean }) {
  if (passed) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-pass-border bg-pass-dim px-2 py-0.5 text-[11px] font-medium text-pass">
        <ShieldCheck className="h-3 w-3" /> Approved
      </span>
    );
  }
  const meta = check !== "all" ? CHECK_META[check] : null;
  const Icon = meta?.icon ?? KeyRound;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-block-border bg-block-dim px-2 py-0.5 text-[11px] font-medium text-block">
      <Icon className="h-3 w-3" /> {meta?.label ?? "Blocked"}
    </span>
  );
}

export function KindBadge({ kind }: { kind: string }) {
  return (
    <span className="rounded border border-ink-700 bg-ink-850 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-slate-400">
      {kind}
    </span>
  );
}

export function TrustMeter({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const color = value >= 0.66 ? "bg-pass" : value >= 0.4 ? "bg-warn" : "bg-block";
  return (
    <div className="flex items-center gap-2" title={`trust ${value.toFixed(2)}`}>
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-ink-700">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-[10px] text-slate-500">{value.toFixed(2)}</span>
    </div>
  );
}
