"use client";

import { useState } from "react";
import { Check, Copy, Terminal } from "lucide-react";
import { API_BASE } from "@/lib/api";

const MCP_URL = `${API_BASE}/mcp`;
const UVX_SPEC = "git+https://github.com/himanshu748/ContextFirewall#subdirectory=mcp";
const HOSTED = `claude mcp add --transport http contextfirewall ${MCP_URL}`;
const LOCAL = `uvx --from "${UVX_SPEC}" contextfirewall-mcp`;

const TOOLS = [
  "get_trusted_context",
  "audit_context",
  "remember",
  "forget_memory",
  "improve_rules",
  "list_coding_rules",
];

function Line({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="group relative rounded-lg border border-ink-700 bg-ink-950">
      <button
        onClick={() =>
          navigator.clipboard?.writeText(code).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1400);
          })
        }
        className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-[10px] font-medium text-slate-400 opacity-0 transition-opacity hover:text-slate-100 group-hover:opacity-100"
        aria-label="Copy"
      >
        {copied ? <Check className="h-3 w-3 text-pass" /> : <Copy className="h-3 w-3" />}
        {copied ? "copied" : "copy"}
      </button>
      <pre className="overflow-x-auto px-4 py-3 font-mono text-[12px] leading-relaxed text-slate-200">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function ConnectSnippet() {
  return (
    <div className="overflow-hidden rounded-2xl border border-ink-700 bg-ink-900/60">
      <div className="flex items-center gap-2 border-b border-ink-800 px-4 py-2.5">
        <Terminal className="h-3.5 w-3.5 text-firewall-400" />
        <span className="font-mono text-xs text-slate-400">connect your agent</span>
        <span className="ml-auto text-[11px] text-slate-500">Claude Code · Cursor · Windsurf · Cline</span>
      </div>
      <div className="space-y-4 p-5">
        <div>
          <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">Hosted (one line, no install)</div>
          <Line code={HOSTED} />
        </div>
        <div>
          <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">Or run it locally with uvx</div>
          <Line code={LOCAL} />
        </div>
        <div className="flex flex-wrap gap-1.5 pt-1">
          {TOOLS.map((t) => (
            <span key={t} className="rounded-md border border-ink-700 bg-ink-850 px-2 py-1 font-mono text-[11px] text-slate-400">
              {t}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
