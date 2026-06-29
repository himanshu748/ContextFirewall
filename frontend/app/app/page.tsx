"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, ShieldX, Loader2, Database, GitGraph, History, ScanSearch } from "lucide-react";
import { api } from "@/lib/api";
import type { AuditResponse, GraphResponse, HealthResponse, PackResponse, TimelineEvent } from "@/lib/types";
import { Header } from "@/components/Header";
import { QueryBar } from "@/components/QueryBar";
import { MemoryCard } from "@/components/MemoryCard";
import { PackPanel } from "@/components/PackPanel";
import { Timeline } from "@/components/Timeline";
import { GraphView } from "@/components/GraphView";

type Tab = "firewall" | "replay" | "graph";
const DEFAULT_QUERY = "What should I know before deploying the backend and running the Cognee smoke?";

export default function Page() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [tab, setTab] = useState<Tab>("firewall");
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [pack, setPack] = useState<PackResponse | null>(null);
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);

  const run = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const [a, p] = await Promise.all([api.audit(q), api.pack(q)]);
      setAudit(a);
      setPack(p);
    } catch (e: any) {
      setError(e.message || "request failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const h = await api.health().catch(() => null);
      setHealth(h);
      if (h && (h.counts?.Memory ?? 0) > 0) run(DEFAULT_QUERY);
    })();
  }, [run]);

  useEffect(() => {
    if (tab === "replay" && events === null) {
      api.sessions().then((s) => {
        if (s[0]) api.timeline(s[0].session_id).then((t) => setEvents(t.events));
        else setEvents([]);
      }).catch(() => setEvents([]));
    }
    if (tab === "graph" && graph === null) {
      api.graph(450).then(setGraph).catch(() => setGraph({ nodes: [], edges: [] }));
    }
  }, [tab, events, graph]);

  const seed = async () => {
    setSeeding(true);
    try {
      await api.demoSeed();
      await refreshHealth();
      setGraph(null);
      setEvents(null);
      run(DEFAULT_QUERY);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSeeding(false);
    }
  };

  const onForget = async (id: string) => {
    await api.forget(id, "rejected via firewall UI");
    await refreshHealth();
    if (audit) run(audit.query);
  };

  const blocked = audit?.candidates.filter((c) => !c.passed) ?? [];
  const passed = audit?.candidates.filter((c) => c.passed) ?? [];
  const empty = !!health && (health.counts?.Memory ?? 0) === 0;

  return (
    <main className="min-h-screen pb-20">
      <Header health={health} />

      <div className="mx-auto max-w-6xl px-5">
        {/* Hero */}
        <section className="py-8">
          <h1 className="max-w-2xl text-2xl font-semibold leading-tight tracking-tight text-slate-100 sm:text-3xl">
            Every remembered fact is audited before it reaches the next agent.
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">
            ContextFirewall records AI coding-agent sessions into a Cognee knowledge graph, then runs four
            checks — staleness, contradiction, secrets, evidence — and assembles only what passes into a
            trusted context pack.
          </p>
          <div className="mt-5 max-w-3xl">
            <QueryBar onRun={run} loading={loading} initial={DEFAULT_QUERY} />
          </div>
        </section>

        {empty && (
          <div className="mb-6 flex items-center justify-between rounded-xl border border-firewall-600/40 bg-firewall-500/5 px-5 py-4">
            <div className="text-sm text-slate-300">
              <Database className="mr-2 inline h-4 w-4 text-firewall-400" />
              No memories yet. Seed the real ContextFirewall onboarding session to start.
            </div>
            <button
              onClick={seed}
              disabled={seeding}
              className="inline-flex items-center gap-1.5 rounded-lg bg-firewall-500 px-3 py-1.5 text-sm font-medium text-ink-950 hover:bg-firewall-400 disabled:opacity-60"
            >
              {seeding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
              Seed demo
            </button>
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-lg border border-block-border bg-block-dim px-4 py-3 text-sm text-block">
            {error}
          </div>
        )}

        {/* Tabs */}
        <nav className="mb-5 flex gap-1 border-b border-ink-800">
          {([
            ["firewall", "Firewall", ScanSearch],
            ["replay", "Session replay", History],
            ["graph", "Knowledge graph", GitGraph],
          ] as const).map(([id, label, Icon]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm transition-colors ${
                tab === id
                  ? "border-firewall-500 text-slate-100"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              <Icon className="h-4 w-4" /> {label}
            </button>
          ))}
        </nav>

        {/* Firewall tab */}
        {tab === "firewall" && (
          <div className="space-y-6">
            {audit && (
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="inline-flex items-center gap-1.5 rounded-lg border border-block-border/60 bg-block-dim/50 px-3 py-1.5 text-block">
                  <ShieldX className="h-4 w-4" /> {audit.blocked_count} blocked
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-lg border border-pass-border/60 bg-pass-dim/50 px-3 py-1.5 text-pass">
                  <ShieldCheck className="h-4 w-4" /> {audit.passed_count} approved
                </span>
                <span className="text-xs text-slate-500">for “{audit.query}”</span>
              </div>
            )}

            {loading && !audit && (
              <div className="flex items-center gap-2 py-16 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" /> Auditing memories on live Cognee…
              </div>
            )}

            {blocked.length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-block/80">
                  Blocked at the firewall
                </h3>
                <div className="grid gap-3 md:grid-cols-2">
                  {blocked.map((v) => (
                    <MemoryCard key={v.memory_id} v={v} onForget={onForget} />
                  ))}
                </div>
              </div>
            )}

            {pack && <PackPanel pack={pack} />}

            {passed.length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-pass/80">
                  Approved memories
                </h3>
                <div className="grid gap-3 md:grid-cols-2">
                  {passed.map((v) => (
                    <MemoryCard key={v.memory_id} v={v} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Replay tab */}
        {tab === "replay" && (
          <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-6">
            {events === null ? (
              <div className="flex items-center gap-2 py-12 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading recorded session…
              </div>
            ) : (
              <Timeline events={events} />
            )}
          </div>
        )}

        {/* Graph tab */}
        {tab === "graph" && (
          <div>
            {graph === null ? (
              <div className="flex items-center gap-2 py-12 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading Cognee knowledge graph…
              </div>
            ) : (
              <GraphView data={graph} />
            )}
          </div>
        )}
      </div>
    </main>
  );
}
