"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ShieldCheck, ShieldX, Loader2, Circle, Upload } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type {
  CheckName,
  GraphResponse,
  HealthResponse,
  PackResponse,
  SessionSummary,
  TimelineEvent,
  MemoryVerdict,
} from "@/lib/types";
import { Sidebar, type ConsoleView } from "@/components/Sidebar";
import { Overview } from "@/components/Overview";
import { ConnectView } from "@/components/ConnectView";
import { RulesView } from "@/components/RulesView";
import { QueryBar } from "@/components/QueryBar";
import { MemoryCard } from "@/components/MemoryCard";
import { MemoryDrawer } from "@/components/MemoryDrawer";
import { IngestModal } from "@/components/IngestModal";
import { PackPanel } from "@/components/PackPanel";
import { Timeline } from "@/components/Timeline";
import { GraphView } from "@/components/GraphView";
import { CHECK_META } from "@/components/badges";
import { useOperatorSettings } from "@/lib/operator";

const DEFAULT_QUERY = "What should a new agent know before working on taskflow-api?";
const CHECK_ORDER: CheckName[] = ["staleness", "contradiction", "secret", "evidence"];
const TITLES: Record<ConsoleView, string> = {
  overview: "Overview",
  connect: "Connect agent",
  firewall: "Firewall",
  rules: "Coding rules",
  replay: "Session replay",
  graph: "Knowledge graph",
};

export default function Console() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [view, setView] = useState<ConsoleView>("overview");
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pack, setPack] = useState<PackResponse | null>(null);
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [queries, setQueries] = useState<string[]>([]);
  const [selected, setSelected] = useState<MemoryVerdict | null>(null);
  const [ingestOpen, setIngestOpen] = useState(false);
  const operator = useOperatorSettings();
  const canWrite = !!operator.token.trim();

  const audit = pack?.audit ?? null;

  // memory_id -> verdict, so the knowledge graph can ring Memory nodes by firewall outcome
  const verdictMap = useMemo(() => {
    const m: Record<string, { passed: boolean }> = {};
    audit?.candidates.forEach((c) => {
      m[c.memory_id] = { passed: c.passed };
    });
    return m;
  }, [audit]);


  const writeGateMessage = "Read-only demo mode. Paste an operator token in the sidebar to write.";

  const writeErrorMessage = useCallback((e: unknown, fallback: string) => {
    if (e instanceof ApiError) {
      if (e.status === 401) return writeGateMessage;
      return e.body || fallback;
    }
    if (e instanceof Error) return e.message || fallback;
    return fallback;
  }, []);

  const inspectMemory = useCallback(
    (memoryId: string) => {
      const v = audit?.candidates.find((c) => c.memory_id === memoryId) ?? null;
      if (v) setSelected(v);
    },
    [audit],
  );

  const run = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      setPack(await api.pack(q));
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
      api.demoQueries().then((d) => setQueries(d.queries)).catch(() => {});
      const h = await api.health().catch(() => null);
      setHealth(h);
      if (h && (h.counts?.Memory ?? 0) > 0) run(DEFAULT_QUERY);
    })();
  }, [run]);

  useEffect(() => {
    if (view === "replay" && events === null) {
      api
        .sessions()
        .then((s) => {
          if (s[0]) {
            setSession(s[0]);
            api.timeline(s[0].session_id).then((t) => setEvents(t.events)).catch(() => setEvents([]));
          } else {
            setEvents([]);
          }
        })
        .catch(() => setEvents([]));
    }
    if (view === "graph" && graph === null) {
      api.graph(450).then(setGraph).catch(() => setGraph({ nodes: [], edges: [] }));
    }
  }, [view, events, graph]);

  const seed = async () => {
    setSeeding(true);
    setError(null);
    try {
      await api.demoSeed();
      await refreshHealth();
      setGraph(null);
      setEvents(null);
      run(DEFAULT_QUERY);
    } catch (e: any) {
      setError(writeErrorMessage(e, "Reload sample project failed."));
    } finally {
      setSeeding(false);
    }
  };

  const onForget = async (id: string) => {
    setError(null);
    try {
      const res = await api.forget(id, "rejected via firewall console");
      if (res.status === "forbidden") {
        setError(res.message || writeGateMessage);
        return;
      }
      await refreshHealth();
      if (pack) run(pack.query);
    } catch (e: any) {
      setError(writeErrorMessage(e, "Forget failed."));
    }
  };

  const onIngested = () => {
    setIngestOpen(false);
    setGraph(null);
    setEvents(null);
    refreshHealth();
    setView("firewall");
    run(DEFAULT_QUERY);
  };

  const blocked = audit?.candidates.filter((c) => !c.passed) ?? [];
  const passed = audit?.candidates.filter((c) => c.passed) ?? [];
  const online = !!health && health.status === "ok";

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar view={view} setView={setView} health={health} onSeed={seed} seeding={seeding} canWrite={canWrite} />

      <div className="min-w-0 flex-1">
        {/* topbar */}
        <div className="sticky top-0 z-20 flex items-center justify-between border-b border-ink-800 bg-ink-950/70 px-6 py-3 backdrop-blur">
          <h2 className="text-sm font-semibold text-slate-200">{TITLES[view]}</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIngestOpen(true)}
              disabled={!canWrite}
              title={!canWrite ? writeGateMessage : undefined}
              className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-ink-600 hover:text-slate-100 disabled:opacity-50"
            >
              <Upload className="h-3.5 w-3.5" /> Ingest session
            </button>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
              <Circle className={`h-2 w-2 ${online ? "fill-pass text-pass" : "fill-block text-block"}`} />
              {online ? "Cognee live" : "offline"}
            </div>
          </div>
        </div>

        <main className="mx-auto max-w-6xl px-6 py-7 pb-24">
          {error && (
            <div className="mb-5 rounded-lg border border-block-border bg-block-dim px-4 py-3 text-sm text-block">
              {error}
            </div>
          )}

          {view === "overview" && <Overview health={health} audit={audit} onView={setView} onIngest={() => setIngestOpen(true)} canWrite={canWrite} />}

          {view === "connect" && <ConnectView online={online} />}

          {view === "rules" && <RulesView />}

          {view === "firewall" && (
            <div className="space-y-6">
              <div>
                <h1 className="max-w-2xl text-lg font-semibold leading-tight tracking-tight text-slate-100">
                  Audit memory for a task, then hand the agent only what passes.
                </h1>
                <div className="mt-4 max-w-3xl">
                  <QueryBar onRun={run} loading={loading} initial={DEFAULT_QUERY} queries={queries} />
                </div>
              </div>

              {audit && (
                <div className="flex flex-wrap items-center gap-2.5 text-sm">
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-pass-border/60 bg-pass-dim/50 px-3 py-1.5 font-medium text-pass">
                    <ShieldCheck className="h-4 w-4" /> {audit.passed_count} approved
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-block-border/60 bg-block-dim/50 px-3 py-1.5 font-medium text-block">
                    <ShieldX className="h-4 w-4" /> {audit.blocked_count} blocked
                  </span>
                  <span className="mx-1 hidden h-5 w-px bg-ink-700 sm:block" />
                  {CHECK_ORDER.map((k) => {
                    const meta = CHECK_META[k];
                    const n = audit.candidates.filter((c) => !c.passed && c.block_check === k).length;
                    const Icon = meta.icon;
                    return (
                      <span
                        key={k}
                        title={`${meta.label}: ${n} blocked`}
                        className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs ${
                          n
                            ? "border-block-border/60 bg-block-dim/40 text-block"
                            : "border-ink-700 bg-ink-850/50 text-slate-500"
                        }`}
                      >
                        <Icon className="h-3.5 w-3.5" /> {meta.label} <span className="font-mono">{n}</span>
                      </span>
                    );
                  })}
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
                      <MemoryCard key={v.memory_id} v={v} onForget={onForget} onSelect={setSelected} canForget={canWrite} />
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
                      <MemoryCard key={v.memory_id} v={v} onSelect={setSelected} canForget={canWrite} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {view === "replay" && (
            <div className="space-y-4">
              {session && (
                <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-5">
                  <div className="text-sm font-medium text-slate-200">{session.task}</div>
                  <div className="mt-1 flex flex-wrap gap-x-4 text-[11px] text-slate-500">
                    <span className="font-mono">{session.session_id}</span>
                    {session.agent && <span>agent: {session.agent}</span>}
                    <span>{session.event_count} events</span>
                  </div>
                </div>
              )}
              <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-6">
                {events === null ? (
                  <div className="flex items-center gap-2 py-12 text-sm text-slate-500">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading recorded session…
                  </div>
                ) : (
                  <Timeline events={events} />
                )}
              </div>
            </div>
          )}

          {view === "graph" && (
            <div>
              {graph === null ? (
                <div className="flex items-center gap-2 py-12 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading Cognee knowledge graph…
                </div>
              ) : (
                <GraphView data={graph} verdicts={verdictMap} onInspectMemory={inspectMemory} />
              )}
            </div>
          )}
        </main>
      </div>

      <MemoryDrawer
        verdict={selected}
        onClose={() => setSelected(null)}
        onForget={onForget}
        canForget={canWrite}
        onJumpToEvidence={() => {
          setSelected(null);
          setView("replay");
        }}
      />

      <IngestModal open={ingestOpen} onClose={() => setIngestOpen(false)} onIngested={onIngested} canWrite={canWrite} />
    </div>
  );
}
