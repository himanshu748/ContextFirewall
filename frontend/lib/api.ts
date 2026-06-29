import type {
  AuditResponse,
  ForgetResponse,
  GraphResponse,
  HealthResponse,
  ImproveResponse,
  PackResponse,
  RulesResponse,
  SessionSummary,
  TimelineResponse,
} from "./types";

// Set NEXT_PUBLIC_API_URL to the deployed Hugging Face Space URL in production.
export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<HealthResponse>("/health"),
  audit: (query: string, top_k = 12) =>
    req<AuditResponse>("/audit", { method: "POST", body: JSON.stringify({ query, top_k }) }),
  pack: (query: string, top_k = 12) =>
    req<PackResponse>("/pack", { method: "POST", body: JSON.stringify({ query, top_k }) }),
  forget: (memory_id: string, reason?: string) =>
    req<ForgetResponse>("/forget", { method: "POST", body: JSON.stringify({ memory_id, reason }) }),
  improve: () => req<ImproveResponse>("/improve", { method: "POST" }),
  rules: (query?: string) =>
    req<RulesResponse>(`/rules${query ? `?query=${encodeURIComponent(query)}` : ""}`),
  graph: (limit = 400) => req<GraphResponse>(`/graph?limit=${limit}`),
  sessions: () => req<SessionSummary[]>("/sessions"),
  timeline: (sessionId: string) =>
    req<TimelineResponse>(`/sessions/${encodeURIComponent(sessionId)}/timeline`),
  demoSeed: () => req<{ message: string }>("/demo/seed", { method: "POST" }),
  demoQueries: () => req<{ queries: string[] }>("/demo/queries"),
};
