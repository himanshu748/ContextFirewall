"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** Live signal that the Cognee backend is up and how many memories it governs. */
export function LiveBadge() {
  const [count, setCount] = useState<number | null>(null);
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => {
        if (!alive) return;
        setOk(h.status === "ok");
        setCount(h.counts?.Memory ?? 0);
      })
      .catch(() => {
        if (alive) setOk(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const live = ok === true;
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-ink-700 bg-ink-900/60 px-3 py-1 text-xs text-slate-400">
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          live ? "bg-pass animate-pulse" : ok === false ? "bg-block" : "bg-slate-600"
        }`}
      />
      {live ? (
        <>
          Cognee live · <span className="font-mono text-slate-200">{count}</span> memories audited
        </>
      ) : ok === false ? (
        "backend waking up…"
      ) : (
        "connecting…"
      )}
    </span>
  );
}
