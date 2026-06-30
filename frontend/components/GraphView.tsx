"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
} from "d3-force";
import { ZoomIn, ZoomOut, Maximize2, MousePointerClick } from "lucide-react";
import type { GraphResponse } from "@/lib/types";

const TYPE_STYLE: Record<string, { fill: string; r: number; label: string }> = {
  Memory: { fill: "#38bdf8", r: 10, label: "Memory" },
  Rule: { fill: "#f472b6", r: 9, label: "Rule" },
  AgentSession: { fill: "#a78bfa", r: 12, label: "Session" },
  SessionEvent: { fill: "#94a3b8", r: 5, label: "Event" },
  Repo: { fill: "#34d399", r: 13, label: "Repo" },
  Entity: { fill: "#fbbf24", r: 6, label: "Entity" },
  EntityType: { fill: "#f59e0b", r: 8, label: "EntityType" },
  TextSummary: { fill: "#64748b", r: 5, label: "Summary" },
  DocumentChunk: { fill: "#475569", r: 4, label: "Chunk" },
  TextDocument: { fill: "#52525b", r: 6, label: "Doc" },
  NodeSet: { fill: "#818cf8", r: 7, label: "NodeSet" },
};
const FALLBACK = { fill: "#64748b", r: 5, label: "Node" };

const W = 1000;
const H = 620;
const PASS = "#34d399";
const BLOCK = "#fb7185";

type SimNode = {
  id: string;
  label: string;
  type: string;
  memoryId?: string;
  x: number;
  y: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
};
type SimLink = { source: SimNode | string; target: SimNode | string };

export type GraphVerdict = { passed: boolean };

export function GraphView({
  data,
  verdicts,
  onInspectMemory,
}: {
  data: GraphResponse | null;
  /** memory_id -> verdict, used to ring Memory nodes green (approved) / red (blocked). */
  verdicts?: Record<string, GraphVerdict>;
  /** called when a Memory node is clicked, so the console can open the rich drawer. */
  onInspectMemory?: (memoryId: string) => void;
}) {
  const simRef = useRef<Simulation<SimNode, undefined> | null>(null);
  const nodesRef = useRef<SimNode[]>([]);
  const linksRef = useRef<SimLink[]>([]);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ id: string } | null>(null);
  const panRef = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  const [, setFrame] = useState(0);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<SimNode | null>(null);

  const present = useMemo(() => {
    const t = new Set<string>();
    data?.nodes.forEach((n) => t.add(n.type));
    return Array.from(t).sort();
  }, [data]);

  // neighbor adjacency for hover-highlight
  const adjacency = useMemo(() => {
    const adj = new Map<string, Set<string>>();
    data?.edges.forEach((e) => {
      if (!adj.has(e.source)) adj.set(e.source, new Set());
      if (!adj.has(e.target)) adj.set(e.target, new Set());
      adj.get(e.source)!.add(e.target);
      adj.get(e.target)!.add(e.source);
    });
    return adj;
  }, [data]);

  useEffect(() => {
    if (!data || !data.nodes.length) {
      simRef.current?.stop();
      nodesRef.current = [];
      linksRef.current = [];
      setFrame((f) => f + 1);
      return;
    }
    // preserve positions of nodes that persist across refreshes
    const prev = new Map(nodesRef.current.map((n) => [n.id, n]));
    const simNodes: SimNode[] = data.nodes.map((n) => {
      const old = prev.get(n.id);
      return {
        id: n.id,
        label: n.label,
        type: n.type,
        memoryId: typeof n.props?.memory_id === "string" ? (n.props.memory_id as string) : undefined,
        x: old?.x ?? W / 2 + (Math.random() - 0.5) * 240,
        y: old?.y ?? H / 2 + (Math.random() - 0.5) * 240,
      };
    });
    const byId = new Map(simNodes.map((n) => [n.id, n]));
    const simLinks: SimLink[] = data.edges
      .filter((e) => byId.has(e.source) && byId.has(e.target))
      .map((e) => ({ source: e.source, target: e.target }));

    nodesRef.current = simNodes;
    linksRef.current = simLinks;

    simRef.current?.stop();
    const sim = forceSimulation<SimNode>(simNodes)
      .force("charge", forceManyBody().strength(-220))
      .force(
        "link",
        forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance(64)
          .strength(0.55),
      )
      .force("center", forceCenter(W / 2, H / 2))
      .force("x", forceX(W / 2).strength(0.05))
      .force("y", forceY(H / 2).strength(0.05))
      .force("collide", forceCollide(16))
      .alpha(0.9)
      .alphaDecay(0.028);
    sim.on("tick", () => setFrame((f) => f + 1));
    simRef.current = sim;
    return () => {
      sim.stop();
    };
  }, [data]);

  // ---- pointer helpers ----
  function toUser(evt: { clientX: number; clientY: number }): { x: number; y: number } {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const u = pt.matrixTransform(ctm.inverse());
    return { x: u.x, y: u.y };
  }
  function toGraph(evt: { clientX: number; clientY: number }) {
    const u = toUser(evt);
    return { x: (u.x - view.x) / view.k, y: (u.y - view.y) / view.k };
  }

  function onWheel(e: React.WheelEvent) {
    e.preventDefault();
    const u = toUser(e);
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    const k = Math.max(0.35, Math.min(4, view.k * factor));
    // keep the point under the cursor stable
    const gx = (u.x - view.x) / view.k;
    const gy = (u.y - view.y) / view.k;
    setView({ k, x: u.x - gx * k, y: u.y - gy * k });
  }

  function onPointerDownBg(e: React.PointerEvent) {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const u = toUser(e);
    panRef.current = { x: u.x, y: u.y, vx: view.x, vy: view.y };
  }
  function onPointerMove(e: React.PointerEvent) {
    if (dragRef.current) {
      const g = toGraph(e);
      const node = nodesRef.current.find((n) => n.id === dragRef.current!.id);
      if (node) {
        node.fx = g.x;
        node.fy = g.y;
        setFrame((f) => f + 1);
      }
      return;
    }
    if (panRef.current) {
      const u = toUser(e);
      setView((v) => ({ ...v, x: panRef.current!.vx + (u.x - panRef.current!.x), y: panRef.current!.vy + (u.y - panRef.current!.y) }));
    }
  }
  function endInteraction() {
    if (dragRef.current) {
      const node = nodesRef.current.find((n) => n.id === dragRef.current!.id);
      if (node) {
        node.fx = null;
        node.fy = null;
      }
      simRef.current?.alphaTarget(0);
      dragRef.current = null;
    }
    panRef.current = null;
  }

  function onNodePointerDown(e: React.PointerEvent, n: SimNode) {
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    dragRef.current = { id: n.id };
    simRef.current?.alphaTarget(0.3).restart();
  }
  function onNodeClick(e: React.MouseEvent, n: SimNode) {
    e.stopPropagation();
    if (n.type === "Memory" && n.memoryId && onInspectMemory) {
      onInspectMemory(n.memoryId);
      return;
    }
    setSelected((s) => (s?.id === n.id ? null : n));
  }

  function resetView() {
    setView({ x: 0, y: 0, k: 1 });
  }
  function zoom(factor: number) {
    setView((v) => {
      const k = Math.max(0.35, Math.min(4, v.k * factor));
      const cx = W / 2;
      const cy = H / 2;
      const gx = (cx - v.x) / v.k;
      const gy = (cy - v.y) / v.k;
      return { k, x: cx - gx * k, y: cy - gy * k };
    });
  }

  if (!data) return null;
  if (!data.nodes.length) {
    return (
      <div className="rounded-xl border border-ink-700 bg-ink-950/50 py-16 text-center text-sm text-slate-500">
        Graph is empty. Load the sample project to populate the Cognee graph.
      </div>
    );
  }

  const nodes = nodesRef.current;
  const links = linksRef.current;
  const hoverNeighbors = hover ? adjacency.get(hover) ?? new Set<string>() : null;

  return (
    <div className="relative overflow-hidden rounded-xl border border-ink-700 bg-ink-950/50">
      {/* controls */}
      <div className="absolute right-3 top-3 z-10 flex flex-col gap-1.5">
        <button onClick={() => zoom(1.25)} className="rounded-md border border-ink-700 bg-ink-900/80 p-1.5 text-slate-400 backdrop-blur transition-colors hover:text-slate-100" title="Zoom in">
          <ZoomIn className="h-4 w-4" />
        </button>
        <button onClick={() => zoom(1 / 1.25)} className="rounded-md border border-ink-700 bg-ink-900/80 p-1.5 text-slate-400 backdrop-blur transition-colors hover:text-slate-100" title="Zoom out">
          <ZoomOut className="h-4 w-4" />
        </button>
        <button onClick={resetView} className="rounded-md border border-ink-700 bg-ink-900/80 p-1.5 text-slate-400 backdrop-blur transition-colors hover:text-slate-100" title="Reset view">
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>

      <div className="pointer-events-none absolute left-3 top-3 z-10 flex items-center gap-1.5 rounded-md border border-ink-800 bg-ink-900/70 px-2 py-1 text-[11px] text-slate-500 backdrop-blur">
        <MousePointerClick className="h-3 w-3" /> drag to pan · scroll to zoom · drag a node · click to inspect
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="h-[560px] w-full cursor-grab touch-none active:cursor-grabbing"
        onWheel={onWheel}
        onPointerDown={onPointerDownBg}
        onPointerMove={onPointerMove}
        onPointerUp={endInteraction}
        onPointerLeave={endInteraction}
        onClick={() => setSelected(null)}
      >
        <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
          {links.map((l, i) => {
            const s = l.source as SimNode;
            const t = l.target as SimNode;
            if (!s || !t || s.x == null || t.x == null) return null;
            const active = hover && (s.id === hover || t.id === hover);
            return (
              <line
                key={i}
                x1={s.x}
                y1={s.y}
                x2={t.x}
                y2={t.y}
                stroke={active ? "#334155" : "#1b2130"}
                strokeWidth={active ? 1.5 : 1}
                strokeOpacity={hover && !active ? 0.25 : 1}
              />
            );
          })}
          {nodes.map((n) => {
            if (n.x == null || n.y == null) return null;
            const style = TYPE_STYLE[n.type] ?? FALLBACK;
            const verdict = n.memoryId ? verdicts?.[n.memoryId] : undefined;
            const ring = verdict ? (verdict.passed ? PASS : BLOCK) : null;
            const dimmed = hover && hover !== n.id && !hoverNeighbors?.has(n.id);
            const showLabel =
              ["Memory", "AgentSession", "Repo", "EntityType", "Rule"].includes(n.type) || hover === n.id || selected?.id === n.id;
            return (
              <g
                key={n.id}
                transform={`translate(${n.x},${n.y})`}
                opacity={dimmed ? 0.25 : 1}
                className="cursor-pointer"
                onPointerDown={(e) => onNodePointerDown(e, n)}
                onClick={(e) => onNodeClick(e, n)}
                onMouseEnter={() => setHover(n.id)}
                onMouseLeave={() => setHover((h) => (h === n.id ? null : h))}
              >
                {ring && <circle r={style.r + 3.5} fill="none" stroke={ring} strokeWidth={2} strokeOpacity={0.95} />}
                {selected?.id === n.id && <circle r={style.r + 6} fill="none" stroke="#38bdf8" strokeWidth={1.5} strokeOpacity={0.8} />}
                <circle r={style.r} fill={style.fill} fillOpacity={0.9} stroke="#08090c" strokeWidth={1.5} />
                {showLabel && (
                  <text x={style.r + 4} y={3.5} className="fill-slate-300 font-sans" fontSize={10} style={{ pointerEvents: "none" }}>
                    {n.label.length > 30 ? n.label.slice(0, 28) + "…" : n.label}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* inline node inspector (non-Memory nodes; Memory nodes open the rich drawer) */}
      {selected && (
        <div className="absolute bottom-14 left-3 z-10 max-w-xs rounded-lg border border-ink-700 bg-ink-900/95 p-3 text-xs shadow-xl backdrop-blur">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: (TYPE_STYLE[selected.type] ?? FALLBACK).fill }} />
            <span className="font-medium text-slate-200">{(TYPE_STYLE[selected.type] ?? FALLBACK).label}</span>
          </div>
          <p className="mt-1.5 leading-relaxed text-slate-300">{selected.label}</p>
          <p className="mt-1 font-mono text-[10px] text-slate-600">{selected.id.slice(0, 40)}</p>
        </div>
      )}

      {/* legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1.5 border-t border-ink-800 px-4 py-2.5">
        {present.map((t) => {
          const s = TYPE_STYLE[t] ?? FALLBACK;
          return (
            <span key={t} className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.fill }} />
              {s.label}
            </span>
          );
        })}
        {verdicts && Object.keys(verdicts).length > 0 && (
          <>
            <span className="mx-1 h-3.5 w-px self-center bg-ink-700" />
            <span className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <span className="h-2.5 w-2.5 rounded-full ring-2" style={{ background: "transparent", boxShadow: `0 0 0 2px ${PASS}` }} /> approved
            </span>
            <span className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: "transparent", boxShadow: `0 0 0 2px ${BLOCK}` }} /> blocked
            </span>
          </>
        )}
      </div>
    </div>
  );
}
