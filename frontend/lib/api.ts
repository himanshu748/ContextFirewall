import type {
  AuditResponse,
  ForgetResponse,
  GraphResponse,
  HealthResponse,
  ImproveResponse,
  IngestResponse,
  PackResponse,
  RulesResponse,
  SessionSummary,
  TimelineResponse,
} from "./types";
import { getActiveApiKey } from "./activeKey";

// Set NEXT_PUBLIC_API_URL to the deployed Hugging Face Space URL in production.
export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  body: string;

  constructor(status: number, body: string) {
    super(`${status} ${body || "request failed"}`.trim());
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function buildHeaders(init?: RequestInit, method = "GET"): HeadersInit {
  const headers = new Headers(init?.headers || {});
  if (method !== "GET" && method !== "HEAD") {
    headers.set("Content-Type", "application/json");
  }
  // The signed-in user's API key authenticates and scopes every call (reads to
  // their namespace + demo, writes to their namespace). Anonymous = demo only.
  const key = getActiveApiKey();
  if (key) {
    headers.set("Authorization", `Bearer ${key}`);
  }
  return headers;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildHeaders(init, method),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let message = body || res.statusText;
    try {
      const parsed = JSON.parse(body);
      if (typeof parsed === "string") message = parsed;
      else if (parsed && typeof parsed === "object") {
        message = String((parsed as any).detail || (parsed as any).message || body || res.statusText);
      }
    } catch {
      // keep raw body text
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<HealthResponse>("/health"),
  audit: (query: string, top_k = 12) =>
    req<AuditResponse>("/audit", { method: "POST", body: JSON.stringify({ query, top_k }) }),
  pack: (query: string, top_k = 12) =>
    req<PackResponse>("/pack", { method: "POST", body: JSON.stringify({ query, top_k }) }),
  ingest: (session: unknown, cognify = false) =>
    req<IngestResponse>("/ingest", { method: "POST", body: JSON.stringify({ session, cognify }) }),
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
