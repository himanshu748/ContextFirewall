"use client";

import { useEffect, useState } from "react";
import { Sparkles, Loader2, BookText, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import type { ImproveResponse } from "@/lib/types";

function toBullets(rules: string): string[] {
  const t = (rules || "").trim();
  if (!t || t.startsWith("(coding rules unavailable")) return [];
  const parts = t.split(". ");
  return parts
    .map((s, i) => (i < parts.length - 1 ? s.trim() + "." : s.trim()))
    .filter((s) => s.length > 8);
}

export function RulesView() {
  const [rules, setRules] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [distilling, setDistilling] = useState(false);
  const [result, setResult] = useState<ImproveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.rules();
      setRules(r.rules);
    } catch (e: any) {
      setError(e.message || "failed to load rules");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const distill = async () => {
    setDistilling(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.improve();
      setResult(r);
      await load();
    } catch (e: any) {
      setError(e.message || "memify failed");
    } finally {
      setDistilling(false);
    }
  };

  const bullets = toBullets(rules ?? "");

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-slate-100">
            <Sparkles className="h-5 w-5 text-firewall-400" /> Coding rules
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Higher-order lessons Cognee distils from the recorded sessions with{" "}
            <span className="font-mono text-firewall-400">memify</span> (the improve verb). Rules are
            stored as typed nodes and recalled with the CODING_RULES search type.
          </p>
        </div>
        <button
          onClick={distill}
          disabled={distilling}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-firewall-500 px-3.5 py-2 text-sm font-medium text-ink-950 transition-colors hover:bg-firewall-400 disabled:opacity-60"
        >
          {distilling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {distilling ? "Distilling…" : "Distil rules"}
        </button>
      </div>

      {distilling && (
        <div className="rounded-lg border border-firewall-600/30 bg-firewall-500/5 px-4 py-3 text-sm text-slate-300">
          Running Cognee memify over the recorded sessions. This re-derives the rule set with the LLM and
          can take up to a minute.
        </div>
      )}

      {result && result.status === "ok" && (
        <div className="flex items-center gap-2 rounded-lg border border-pass-border/50 bg-pass-dim/40 px-4 py-3 text-sm text-pass">
          <CheckCircle2 className="h-4 w-4" />
          {result.message} ({result.rules_added ?? 0} added · {result.rules_total ?? 0} total)
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-block-border bg-block-dim px-4 py-3 text-sm text-block">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-12 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Recalling distilled rules from Cognee…
        </div>
      ) : bullets.length === 0 ? (
        <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-8 text-center">
          <BookText className="mx-auto h-7 w-7 text-slate-600" />
          <p className="mt-3 text-sm text-slate-400">
            No coding rules yet. Run <span className="text-slate-200">Distil rules</span> to derive them
            from the recorded sessions.
          </p>
        </div>
      ) : (
        <ol className="space-y-2.5">
          {bullets.map((b, i) => (
            <li
              key={i}
              className="flex items-start gap-3 rounded-xl border border-ink-700 bg-ink-900/50 p-4 text-sm leading-relaxed text-slate-200"
            >
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-firewall-600/40 bg-firewall-500/10 font-mono text-[11px] text-firewall-400">
                {i + 1}
              </span>
              {b}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
