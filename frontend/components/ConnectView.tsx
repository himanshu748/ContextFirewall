"use client";

import { useEffect, useState } from "react";
import {
  Check,
  Copy,
  Plug,
  ShieldCheck,
  ScanSearch,
  Save,
  Trash2,
  Sparkles,
  ListChecks,
  Circle,
  type LucideIcon,
} from "lucide-react";
import { api, API_BASE } from "@/lib/api";
import { useActiveApiKey } from "@/lib/activeKey";
import type { ActivityEvent } from "@/lib/types";

const MCP_URL = `${API_BASE}/mcp`;
const UVX_SPEC = 'git+https://github.com/himanshu748/ContextFirewall#subdirectory=mcp';
const KEY_PLACEHOLDER = "cf_live_YOUR_KEY";

const TOOLS: { name: string; verb: string; icon: LucideIcon; desc: string }[] = [
  { name: "get_trusted_context", verb: "recall", icon: ShieldCheck, desc: "Pull a trusted context pack for a task. Only memory that passes all four checks is returned." },
  { name: "audit_context", verb: "recall", icon: ScanSearch, desc: "See every recalled memory's verdict: what was approved, what was blocked, and why." },
  { name: "remember", verb: "remember", icon: Save, desc: "Store a durable fact, decision, or command. It becomes auditable on the next recall." },
  { name: "forget_memory", verb: "forget", icon: Trash2, desc: "Delete a memory from the graph and vector store so it can never resurface." },
  { name: "improve_rules", verb: "improve", icon: Sparkles, desc: "Distil reusable coding rules from recorded sessions (Cognee memify)." },
  { name: "list_coding_rules", verb: "recall", icon: ListChecks, desc: "Retrieve the distilled coding rules for this repo." },
];

function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="group relative">
      {label && <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</div>}
      <div className="relative rounded-lg border border-ink-700 bg-ink-950">
        <button
          onClick={() => {
            navigator.clipboard?.writeText(code).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1400);
            });
          }}
          className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-[10px] font-medium text-slate-400 opacity-0 transition-opacity hover:text-slate-100 group-hover:opacity-100"
        >
          {copied ? <Check className="h-3 w-3 text-pass" /> : <Copy className="h-3 w-3" />}
          {copied ? "copied" : "copy"}
        </button>
        <pre className="overflow-x-auto px-4 py-3 font-mono text-[12px] leading-relaxed text-slate-200">
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
}

function hostedSnippets(key: string): Record<string, string> {
  return {
    "Claude Code": `claude mcp add --transport http contextfirewall ${MCP_URL} \\
  --header "Authorization: Bearer ${key}"`,
    "Cursor / Windsurf / generic (mcp.json)": `{
  "mcpServers": {
    "contextfirewall": {
      "url": "${MCP_URL}",
      "headers": { "Authorization": "Bearer ${key}" }
    }
  }
}`,
  };
}

function localSnippets(key: string): Record<string, string> {
  return {
    "Claude Code": `claude mcp add contextfirewall \\
  --env CF_API_BASE=${API_BASE} \\
  --env CF_API_KEY=${key} \\
  -- uvx --from "${UVX_SPEC}" contextfirewall-mcp`,
    "Cursor / Windsurf / Claude Desktop (mcp.json)": `{
  "mcpServers": {
    "contextfirewall": {
      "command": "uvx",
      "args": ["--from", "${UVX_SPEC}", "contextfirewall-mcp"],
      "env": { "CF_API_BASE": "${API_BASE}", "CF_API_KEY": "${key}" }
    }
  }
}`,
  };
}

function formatRelative(ts: string): string {
  const then = new Date(ts).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Math.max(0, Date.now() - then);
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function LiveActivity({ online }: { online: boolean }) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await api.activity(40);
        if (alive) setEvents(res.events || []);
      } catch {
        // best effort only
      }
    };
    load();
    const timer = setInterval(load, 4000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">Live activity</h2>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">
            Every MCP and REST call through the firewall, in real time.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-slate-500">
          <Circle className={`h-2 w-2 ${online ? "fill-pass text-pass" : "fill-block text-block"}`} />
          {online ? "online" : "offline"}
        </div>
      </div>

      <div className="mt-4 max-h-80 overflow-y-auto rounded-lg border border-ink-700 bg-ink-950/50">
        {events.length ? (
          <div className="divide-y divide-ink-700/70">
            {events.map((event) => (
              <div key={event.id} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 px-3 py-2.5 text-xs">
                <span
                  className={`mt-0.5 inline-flex items-center rounded border px-1.5 py-0.5 font-mono uppercase tracking-wide ${
                    event.source === "mcp"
                      ? "border-firewall-500/30 bg-firewall-500/10 text-firewall-400"
                      : "border-ink-700 bg-ink-850 text-slate-400"
                  }`}
                >
                  {event.source}
                </span>
                <div className="min-w-0">
                  <div className="font-mono text-[12px] text-slate-100">{event.tool}</div>
                  <div className="mt-0.5 truncate text-slate-400">{event.detail}</div>
                </div>
                <div className="whitespace-nowrap font-mono text-[11px] text-slate-500">
                  {formatRelative(event.ts)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-4 py-6 text-xs text-slate-500">
            No firewall activity yet — connect an agent or run an audit to see calls stream in.
          </div>
        )}
      </div>
    </div>
  );
}

export function ConnectView({ online }: { online: boolean }) {
  const [mode, setMode] = useState<"hosted" | "local">("hosted");
  const activeKey = useActiveApiKey();
  const key = activeKey || KEY_PLACEHOLDER;
  const snippets = mode === "hosted" ? hostedSnippets(key) : localSnippets(key);

  return (
    <div className="space-y-7">
      <div>
        <div className="flex items-center gap-2 text-[11px] font-medium text-firewall-400">
          <Plug className="h-3.5 w-3.5" /> MODEL CONTEXT PROTOCOL
        </div>
        <h1 className="mt-2 max-w-2xl text-2xl font-semibold leading-tight tracking-tight text-slate-100">
          Connect your agent to a governed memory layer.
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
          ContextFirewall is an MCP server. Point any coding agent at it and every memory it recalls,
          stores, distils, or forgets flows through Cognee and the four firewall checks. Stale,
          contradicted, secret-bearing, and unsupported memory never reaches the model.
        </p>
        <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-500">
          <Circle className={`h-2 w-2 ${online ? "fill-pass text-pass" : "fill-block text-block"}`} />
          {online ? "MCP endpoint live" : "endpoint offline"}
          <span className="mx-1 h-3 w-px bg-ink-700" />
          <span className="font-mono text-slate-400">{MCP_URL}</span>
        </div>
      </div>

      {!activeKey && (
        <div className="rounded-xl border border-firewall-600/25 bg-firewall-500/[0.05] px-4 py-3 text-xs leading-relaxed text-slate-300">
          These configs use a placeholder key. Go to{" "}
          <span className="font-medium text-firewall-400">Account &amp; keys</span>, sign in, and create
          an API key — it is injected here automatically so every recall/remember is scoped to your
          own private namespace. Without a key the endpoint is read-only demo access.
        </div>
      )}

      {/* transport toggle */}
      <div>
        <div className="mb-3 inline-flex rounded-lg border border-ink-700 bg-ink-900/60 p-1 text-xs">
          <button
            onClick={() => setMode("hosted")}
            className={`rounded-md px-3 py-1.5 font-medium transition-colors ${mode === "hosted" ? "bg-firewall-500/15 text-firewall-400" : "text-slate-400 hover:text-slate-200"}`}
          >
            Hosted (one line, no install)
          </button>
          <button
            onClick={() => setMode("local")}
            className={`rounded-md px-3 py-1.5 font-medium transition-colors ${mode === "local" ? "bg-firewall-500/15 text-firewall-400" : "text-slate-400 hover:text-slate-200"}`}
          >
            Local (uvx, private)
          </button>
        </div>
        <p className="mb-3 max-w-2xl text-xs leading-relaxed text-slate-500">
          {mode === "hosted"
            ? "Connect straight to the hosted endpoint. Fastest way to try it: nothing to install."
            : "Run the server on your machine with uvx and point it at any ContextFirewall backend. Self-host the backend and nothing leaves your laptop."}
        </p>
        <div className="grid gap-4">
          {Object.entries(snippets).map(([client, code]) => (
            <CodeBlock key={client} label={client} code={code} />
          ))}
        </div>
      </div>

      <LiveActivity online={online} />

      {/* tool catalog */}
      <div>
        <h2 className="text-sm font-semibold text-slate-200">The six tools your agent gets</h2>
        <p className="mt-1 text-xs text-slate-500">Identical on both transports. Together they exercise all four Cognee verbs.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {TOOLS.map((t) => {
            const Icon = t.icon;
            return (
              <div key={t.name} className="rounded-xl border border-ink-700 bg-ink-900/40 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-mono text-[13px] text-slate-100">
                    <Icon className="h-4 w-4 text-firewall-400" /> {t.name}
                  </div>
                  <span className="rounded border border-ink-700 bg-ink-850 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-slate-400">
                    {t.verb}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-slate-400">{t.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* the loop */}
      <div className="rounded-xl border border-firewall-600/25 bg-firewall-500/[0.04] p-5">
        <h2 className="text-sm font-semibold text-slate-200">The loop</h2>
        <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-slate-400">
          Call <span className="font-mono text-firewall-400">get_trusted_context</span> before you act,
          <span className="font-mono text-firewall-400"> remember</span> durable facts as you learn them, and
          <span className="font-mono text-firewall-400"> improve_rules</span> when a task is done. The next session
          starts from governed memory, not a raw dump, and <span className="font-mono text-firewall-400">forget_memory</span> retracts
          anything that should never come back.
        </p>
      </div>
    </div>
  );
}
