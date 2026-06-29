"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ShieldCheck, Unlock, Copy, Check } from "lucide-react";
import { useState } from "react";
import type { PackResponse } from "@/lib/types";

export function PackPanel({ pack }: { pack: PackResponse | null }) {
  const [copied, setCopied] = useState(false);
  if (!pack) return null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* Gated trusted pack */}
      <div className="relative rounded-xl border border-pass-border/50 bg-ink-900/60 p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium text-pass">
            <ShieldCheck className="h-4 w-4" /> Trusted context pack
          </div>
          <button
            onClick={() => {
              navigator.clipboard.writeText(pack.pack_markdown);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
            className="inline-flex items-center gap-1 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-[11px] text-slate-400 hover:text-slate-200"
          >
            {copied ? <Check className="h-3 w-3 text-pass" /> : <Copy className="h-3 w-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <div className="pack-md max-h-[420px] overflow-auto pr-1">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{pack.pack_markdown}</ReactMarkdown>
        </div>
        <p className="mt-3 text-[11px] text-slate-500">
          This is what ContextFirewall hands the next agent — only memories that passed all four checks.
        </p>
      </div>

      {/* Ungoverned baseline */}
      <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-5">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-400">
          <Unlock className="h-4 w-4 text-warn" /> Ungoverned baseline
          <span className="text-[11px] font-normal text-slate-600">(raw Cognee recall)</span>
        </div>
        <div className="max-h-[420px] overflow-auto whitespace-pre-wrap text-[13px] leading-relaxed text-slate-400">
          {pack.recall_answer?.trim() || "—"}
        </div>
        <p className="mt-3 text-[11px] text-slate-500">
          What a normal agent would pull straight from memory — stale, contradicted, and unverified facts included.
        </p>
      </div>
    </div>
  );
}
