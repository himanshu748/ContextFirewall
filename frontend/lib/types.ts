// API contract — mirrors backend/app/models.py

export type CheckName = "staleness" | "contradiction" | "secret" | "evidence";

export interface CheckResult {
  check: CheckName;
  passed: boolean;
  reason: string;
  severity: "info" | "warn" | "block";
}

export interface MemoryVerdict {
  memory_id: string;
  text: string;
  kind: string;
  subject: string | null;
  created_at: string | null;
  trust_score: number;
  status: string;
  source_session_id: string | null;
  passed: boolean;
  checks: CheckResult[];
  block_reason: string | null;
  block_check: CheckName | null;
}

export interface AuditResponse {
  query: string;
  candidates: MemoryVerdict[];
  passed_count: number;
  blocked_count: number;
}

export interface ExcludedMemory {
  memory_id: string;
  reason: string;
  check: CheckName;
}

export interface PackResponse {
  query: string;
  pack_markdown: string;
  included: string[];
  excluded: ExcludedMemory[];
  recall_answer: string | null;
}

export interface HealthResponse {
  status: string;
  profile: Record<string, unknown>;
  counts: Record<string, number>;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  props: Record<string, unknown>;
}
export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}
export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface TimelineEvent {
  event_id: string;
  kind: string;
  content: string;
  timestamp: string | null;
  ordinal: number;
}
export interface SessionSummary {
  session_id: string;
  task: string;
  agent: string | null;
  started_at: string | null;
  repo: Record<string, unknown>;
  event_count: number;
}
export interface TimelineResponse {
  session: SessionSummary;
  events: TimelineEvent[];
}

export interface ForgetResponse {
  memory_id: string;
  status: string;
  message: string;
}
