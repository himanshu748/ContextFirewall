"use client";

import { useEffect, useMemo, useState } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from "d3-force";
import type { GraphResponse } from "@/lib/types";

const TYPE_STYLE: Record<string, { fill: string; r: number; label: string }> = {
  Memory: { fill: "#38bdf8", r: 9, label: "Memory" },
  Rule: { fill: "#f472b6", r: 8, label: "Rule" },
  AgentSession: { fill: "#a78bfa", r: 11, label: "Session" },
  SessionEvent: { fill: "#94a3b8", r: 5, label: "Event" },
  Repo: { fill: "#34d399", r: 12, label: "Repo" },
  Entity: { fill: "#fbbf24", r: 5, label: "Entity" },
  EntityType: { fill: "#f59e0b", r: 7, label: "EntityType" },
  TextSummary: { fill: "#64748b", r: 5, label: "Summary" },
  DocumentChunk: { fill: "#475569", r: 4, label: "Chunk" },
  TextDocument: { fill: "#52525b", r: 6, label: "Doc" },
};
const FALLBACK = { fill: "#64748b", r: 5, label: "Node" };

type SimNode = { id: string; label: string; type: string; x?: number; y?: number };

const W = 920;
const H = 560;

export function GraphView({ data }: { data: GraphResponse | null }) {
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const [links, setLinks] = useState<{ source: SimNode; target: SimNode }[]>([]);
  const [hover, setHover] = useState<SimNode | null>(null);

  const present = useMemo(() => {
    const t = new Set<string>();
    data?.nodes.forEach((n) => t.add(n.type));
    return Array.from(t);
  }, [data]);

  useEffect(() => {
    if (!data || !data.nodes.length) {
      setNodes([]);
      setLinks([]);
      return;
    }
    const simNodes: SimNode[] = data.nodes.map((n) => ({ id: n.id, label: n.label, type: n.type }));
    const byId = new Map(simNodes.map((n) => [n.id, n]));
    const simLinks = data.edges
      .filter((e) => byId.has(e.source) && byId.has(e.target))
      .map((e) => ({ source: byId.get(e.source)!, target: byId.get(e.target)! }));

    const sim = forceSimulation(simNodes as any)
      .force("charge", forceManyBody().strength(-160))
      .force("link", forceLink(simLinks as any).id((d: any) => d.id).distance(60).strength(0.5))
      .force("center", forceCenter(W / 2, H / 2))
      .force("x", forceX(W / 2).strength(0.04))
      .force("y", forceY(H / 2).strength(0.04))
      .force("collide", forceCollide(12))
      .stop();

    for (let i = 0; i < 320; i++) sim.tick();
    setNodes([...simNodes]);
    setLinks([...simLinks]);
  }, [data]);

  if (!data) return null;
  if (!nodes.length) {
    return <div className="py-12 text-center text-sm text-slate-500">Graph is empty — seed the demo data.</div>;
  }

  return (
    <div className="rounded-xl border border-ink-700 bg-ink-950/50">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-[520px] w-full">
        <g>
          {links.map((l, i) => (
            <line
              key={i}
              x1={l.source.x}
              y1={l.source.y}
              x2={l.target.x}
              y2={l.target.y}
              stroke="#1e2330"
              strokeWidth={1}
            />
          ))}
          {nodes.map((n) => {
            const s = TYPE_STYLE[n.type] ?? FALLBACK;
            const showLabel = ["Memory", "AgentSession", "Repo", "EntityType"].includes(n.type) || hover?.id === n.id;
            return (
              <g
                key={n.id}
                transform={`translate(${n.x},${n.y})`}
                onMouseEnter={() => setHover(n)}
                onMouseLeave={() => setHover((h) => (h?.id === n.id ? null : h))}
                className="cursor-pointer"
              >
                <circle r={s.r} fill={s.fill} fillOpacity={0.85} stroke="#08090c" strokeWidth={1.5} />
                {showLabel && (
                  <text
                    x={s.r + 3}
                    y={3}
                    className="fill-slate-300 font-sans"
                    fontSize={9}
                    style={{ pointerEvents: "none" }}
                  >
                    {n.label.length > 28 ? n.label.slice(0, 26) + "…" : n.label}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>
      <div className="flex flex-wrap gap-3 border-t border-ink-800 px-4 py-2.5">
        {present.map((t) => {
          const s = TYPE_STYLE[t] ?? FALLBACK;
          return (
            <span key={t} className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.fill }} />
              {s.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
