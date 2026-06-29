"use client";

import Link from "next/link";
import { ShieldHalf, Github, Circle, ArrowLeft } from "lucide-react";
import type { HealthResponse } from "@/lib/types";

export function Header({ health }: { health: HealthResponse | null }) {
  const online = !!health && health.status === "ok";
  const memCount = health?.counts?.Memory ?? 0;
  return (
    <header className="sticky top-0 z-30 border-b border-ink-800 bg-ink-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
        <Link href="/" className="group flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-firewall-600/40 bg-firewall-500/10 text-firewall-400">
            <ShieldHalf className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-1.5 text-sm font-semibold tracking-tight text-slate-100">
              ContextFirewall
            </div>
            <div className="-mt-0.5 text-[11px] text-slate-500 group-hover:text-slate-400">
              Guardrails for the memory layer
            </div>
          </div>
        </Link>

        <div className="flex items-center gap-4">
          <div className="hidden items-center gap-1.5 text-[11px] text-slate-500 sm:flex">
            <Circle className={`h-2 w-2 ${online ? "fill-pass text-pass" : "fill-block text-block"}`} />
            {online ? (
              <span>
                Cognee live · <span className="font-mono text-slate-400">{memCount}</span> memories
              </span>
            ) : (
              <span>backend offline</span>
            )}
          </div>
          <Link
            href="/"
            className="hidden items-center gap-1.5 text-[12px] text-slate-400 transition-colors hover:text-slate-200 sm:flex"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Home
          </Link>
          <a
            href="https://github.com/himanshu748/ContextFirewall"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 rounded-md border border-ink-700 bg-ink-850 px-2.5 py-1.5 text-[12px] text-slate-300 transition-colors hover:border-ink-600 hover:text-slate-100"
          >
            <Github className="h-3.5 w-3.5" /> Repo
          </a>
        </div>
      </div>
    </header>
  );
}
