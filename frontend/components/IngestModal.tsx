"use client";

import { useRef, useState } from "react";
import { X, Loader2, Upload, FileJson, CheckCircle2, Database } from "lucide-react";
import { api } from "@/lib/api";
import type { IngestResponse } from "@/lib/types";

const TEMPLATE = `{
  "session_id": "my-session-001",
  "task": "Fix the flaky checkout test",
  "agent": "my coding agent",
  "started_at": "2026-06-29T10:00:00",
  "repo": { "name": "my-repo" },
  "events": [
    { "event_id": "e1", "kind": "fix", "timestamp": "2026-06-29T10:05:00",
      "content": "Checkout test was flaky from a race; added a row lock. Stable over 50 runs." },
    { "event_id": "e2", "kind": "decision", "timestamp": "2026-06-29T10:10:00",
      "content": "Run integration tests with TEST_DB on port 5433." }
  ],
  "memories": [
    { "memory_id": "m1", "text": "The checkout race is fixed with a row lock; do not just rerun the test.",
      "kind": "lesson", "subject": "checkout test", "created_at": "2026-06-29",
      "evidence_event_ids": ["e1"], "reinforcement_count": 2, "verified": true },
    { "memory_id": "m2", "text": "Old: deploy with ./scripts/deploy.sh",
      "kind": "decision", "subject": "deploy command", "created_at": "2026-02-01" }
  ]
}`;

export function IngestModal({
  open,
  onClose,
  onIngested,
}: {
  open: boolean;
  onClose: () => void;
  onIngested: () => void;
}) {
  const [text, setText] = useState("");
  const [cognify, setCognify] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  const onFile = (f: File | undefined) => {
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => setText(String(reader.result || ""));
    reader.readAsText(f);
  };

  const ingest = async () => {
    setError(null);
    setResult(null);
    let parsed: any;
    try {
      parsed = JSON.parse(text);
    } catch {
      setError("That is not valid JSON. Paste a recorded session or load the template.");
      return;
    }
    const session = parsed && parsed.session ? parsed.session : parsed;
    if (!session || !session.session_id || !session.task) {
      setError("A session needs at least a session_id and a task.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.ingest(session, cognify);
      setResult(r);
      setTimeout(onIngested, 900);
    } catch (e: any) {
      setError(e.message || "ingest failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={busy ? undefined : onClose} />
      <div className="animate-fade-up relative max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-ink-700 bg-ink-950 shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-ink-800 bg-ink-950/90 px-5 py-3.5 backdrop-blur">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <Database className="h-4 w-4 text-firewall-400" /> Ingest a recorded session
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-slate-500 transition-colors hover:bg-ink-850 hover:text-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-5">
          <p className="text-sm leading-relaxed text-slate-400">
            Bring your own data. Paste a recorded agent session (or upload a <code className="rounded bg-ink-850 px-1 font-mono text-[12px] text-firewall-400">.json</code> file)
            and ContextFirewall will remember it into Cognee and audit it. This is the same shape the recorder
            emits, and the public <code className="rounded bg-ink-850 px-1 font-mono text-[12px] text-firewall-400">POST /ingest</code> API accepts.
          </p>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => fileRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-ink-600 hover:text-slate-100"
            >
              <Upload className="h-3.5 w-3.5" /> Upload .json
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".json,application/json"
              className="hidden"
              onChange={(e) => onFile(e.target.files?.[0])}
            />
            <button
              onClick={() => setText(TEMPLATE)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-ink-600 hover:text-slate-100"
            >
              <FileJson className="h-3.5 w-3.5" /> Load template
            </button>
          </div>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
            placeholder="Paste a recorded session as JSON…"
            className="h-64 w-full resize-y rounded-lg border border-ink-700 bg-ink-900 p-3 font-mono text-[12px] leading-relaxed text-slate-200 placeholder:text-slate-600 focus:border-firewall-600/60 focus:outline-none"
          />

          <label className="flex items-start gap-2.5 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={cognify}
              onChange={(e) => setCognify(e.target.checked)}
              className="mt-0.5 h-3.5 w-3.5 accent-firewall-500"
            />
            <span>
              Also build the knowledge graph (Cognee <span className="font-mono text-slate-300">cognify</span>). Slower,
              about 30 to 60 seconds. Leave off for a fast audit; your memories are still recorded and checked.
            </span>
          </label>

          {error && (
            <div className="rounded-lg border border-block-border bg-block-dim px-4 py-3 text-sm text-block">
              {error}
            </div>
          )}
          {result && (
            <div className="flex items-center gap-2 rounded-lg border border-pass-border/50 bg-pass-dim/40 px-4 py-3 text-sm text-pass">
              <CheckCircle2 className="h-4 w-4" />
              Remembered “{result.session_id}” · {result.memories_created} memories
              {result.cognified ? " · graph built" : ""}. Opening the firewall…
            </div>
          )}
        </div>

        <div className="sticky bottom-0 flex items-center justify-end gap-2 border-t border-ink-800 bg-ink-950/90 px-5 py-3.5 backdrop-blur">
          <button
            onClick={onClose}
            disabled={busy}
            className="rounded-lg px-3 py-2 text-sm text-slate-400 transition-colors hover:text-slate-200 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={ingest}
            disabled={busy || !text.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-firewall-500 px-4 py-2 text-sm font-semibold text-ink-950 transition-colors hover:bg-firewall-400 disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
            {busy ? (cognify ? "Remembering + building graph…" : "Remembering…") : "Ingest and audit"}
          </button>
        </div>
      </div>
    </div>
  );
}
