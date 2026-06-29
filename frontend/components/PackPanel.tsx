"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ShieldCheck, Unlock, Copy, Check, Download, Terminal } from "lucide-react";
import { useState } from "react";
import type { PackResponse } from "@/lib/types";
import { API_BASE } from "@/lib/api";

export function PackPanel({ pack }: { pack: PackResponse | null }) {
  const [copied, setCopied] = useState(false);
  const [showApi, setShowApi] = useState(false);
  if (!pack) return null;

  const download = () => {
    const blob = new Blob([pack.pack_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trusted-context-pack.md";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const curl = `curl -s -X POST ${API_BASE}/pack \\\n  -H 'content-type: application/json' \\\n  -d '{"query": ${JSON.stringify(pack.query)}}'`;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* Gated trusted pack */}
      <div className="relative rounded-xl border border-pass-border/50 bg-ink-900/60 p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium text-pass">
            <ShieldCheck className="h-4 w-4" /> Trusted context pack
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={download}
              className="inline-flex items-center gap-1 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-[11px] text-slate-400 transition-colors hover:text-slate-200"
            >
              <Download className="h-3 w-3" /> .md
            </button>
            <button
              onClick={() => {
                navigator.clipboard.writeText(pack.pack_markdown);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="inline-flex items-center gap-1 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-[11px] text-slate-400 transition-colors hover:text-slate-200"
            >
              {copied ? <Check className="h-3 w-3 text-pass" /> : <Copy className="h-3 w-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
        <div className="pack-md max-h-[420px] overflow-auto pr-1">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{pack.pack_markdown}</ReactMarkdown>
        </div>
        <button
          onClick={() => setShowApi((s) => !s)}
          className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-slate-500 transition-colors hover:text-slate-300"
        >
          <Terminal className="h-3 w-3" /> {showApi ? "Hide API call" : "Use via API"}
        </button>
        {showApi && (
          <pre className="mt-2 overflow-x-auto rounded-lg border border-ink-800 bg-ink-950 p-3 font-mono text-[11px] leading-relaxed text-slate-400">
            {curl}
          </pre>
        )}
      </div>

      {/* Ungoverned baseline */}
      <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-5">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-400">
          <Unlock className="h-4 w-4 text-warn" /> Ungoverned baseline
          <span className="text-[11px] font-normal text-slate-600">(raw recall)</span>
        </div>
        <div className="max-h-[420px] overflow-auto whitespace-pre-wrap text-[13px] leading-relaxed text-slate-400">
          {pack.recall_answer?.trim() || "—"}
        </div>
        <p className="mt-3 text-[11px] text-slate-500">
          What a plain recall hands the next agent: stale, contradicted, and unverified facts included.
        </p>
      </div>
    </div>
  );
}
