"use client";

import { Search, Loader2 } from "lucide-react";
import { useState } from "react";

// Fallback chips if the backend's /demo/queries is unavailable. Kept in sync
// with the bundled sample session (taskflow-api).
const FALLBACK_QUERIES = [
  "What should a new agent know before working on taskflow-api?",
  "How do I deploy taskflow-api safely?",
  "Do JWT access tokens expire in taskflow-api?",
  "How is the public API rate-limited?",
];

export function QueryBar({
  onRun,
  loading,
  initial,
  queries,
}: {
  onRun: (q: string) => void;
  loading: boolean;
  initial?: string;
  queries?: string[];
}) {
  const chips = queries && queries.length ? queries : FALLBACK_QUERIES;
  const [q, setQ] = useState(initial ?? chips[0]);

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) onRun(q.trim());
        }}
        className="flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-850/80 p-1.5 shadow-glow focus-within:border-firewall-600/60"
      >
        <Search className="ml-2 h-4 w-4 shrink-0 text-slate-500" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="What should the next agent know before…?"
          className="w-full bg-transparent py-1.5 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-firewall-500 px-3.5 py-1.5 text-sm font-medium text-ink-950 transition-colors hover:bg-firewall-400 disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Run firewall
        </button>
      </form>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {chips.map((d) => (
          <button
            key={d}
            onClick={() => {
              setQ(d);
              onRun(d);
            }}
            className="rounded-full border border-ink-700 bg-ink-850/60 px-2.5 py-1 text-[11px] text-slate-400 transition-colors hover:border-firewall-600/50 hover:text-slate-200"
          >
            {d.length > 52 ? d.slice(0, 50) + "…" : d}
          </button>
        ))}
      </div>
    </div>
  );
}
