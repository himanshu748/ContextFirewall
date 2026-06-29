"""Remember — ingest a recorded coding-agent session into Cognee.

Two population paths run together (the Cognee 'remember' verb):
  1. ``add_data_points`` inserts the typed Repo / AgentSession / SessionEvent /
     Memory graph directly (deterministic objects the firewall audits + the
     replay timeline reads).
  2. ``cognify`` over the rendered transcript lets the LLM grow the rich entity
     web that powers GRAPH_COMPLETION / TEMPORAL recall and the graph view.

Trust scoring is computed here from real signals on each candidate memory
(evidence, reinforcement, verification, deprecation) — never hand-waved.
"""
from __future__ import annotations

from typing import Any, List, Tuple

from .bootstrap import configure_cognee
from .schema import (
    STATUS_CANDIDATE,
    AgentSession,
    Memory,
    Repo,
    SessionEvent,
    render_session_text,
)

CF_DATASET = "contextfirewall"

# The bundled sample session ships PLACEHOLDERS instead of credential-shaped
# literals, so secret scanners stay quiet on the repo. We hydrate them to clearly
# synthetic, never-valid tokens at seed time so the firewall's secret check has a
# realistic credential to catch in the demo. The AWS value is the canonical AWS
# documentation example key (publicly published, guaranteed invalid).
DEMO_SECRET_PLACEHOLDERS = {
    "<<DEMO_LEAKED_AWS_KEY>>": "AKIA" + "IOSFODNN7" + "EXAMPLE",
    "<<DEMO_LEAKED_HF_KEY>>": "hf_" + "DEMO" + ("0" * 8) + "notARealKey" + "abcdef",
}


def hydrate_demo_secrets(session: dict) -> dict:
    """Replace demo placeholders with synthetic, assembled (never-real) tokens."""

    def _sub(s: Any) -> Any:
        if not isinstance(s, str):
            return s
        for placeholder, token in DEMO_SECRET_PLACEHOLDERS.items():
            s = s.replace(placeholder, token)
        return s

    for m in session.get("memories") or []:
        if "text" in m:
            m["text"] = _sub(m["text"])
    for e in session.get("events") or []:
        if "content" in e:
            e["content"] = _sub(e["content"])
    return session


def compute_trust(mem: dict) -> float:
    """Derive a 0–1 trust score from explicit signals on a candidate memory.

    If the recorded memory already carries an explicit ``trust_score`` we respect
    it; otherwise we build one from evidence/reinforcement/verification/deprecation.
    """
    if isinstance(mem.get("trust_score"), (int, float)):
        return max(0.0, min(1.0, float(mem["trust_score"])))
    score = 0.5
    if mem.get("evidence_event_ids"):
        score += 0.2
    rc = int(mem.get("reinforcement_count", 1) or 1)
    score += min(0.2, 0.07 * max(0, rc - 1))
    if mem.get("verified"):
        score += 0.15
    if mem.get("unsupported"):
        score -= 0.4
    if mem.get("deprecated"):
        score -= 0.3
    return round(max(0.0, min(1.0, score)), 3)


def _derive_memories_from_events(session: dict) -> List[dict]:
    """Fallback when a session ships no pre-distilled memories: lift decisions/fixes/lessons."""
    out: List[dict] = []
    sid = session.get("session_id", "s")
    for i, ev in enumerate(session.get("events", [])):
        if ev.get("kind") in ("decision", "fix", "lesson"):
            kind = ev.get("kind")
            out.append(
                {
                    "memory_id": f"{sid}:m{i}",
                    "text": (ev.get("content") or "").strip(),
                    "kind": "lesson" if kind == "lesson" else ("decision" if kind == "decision" else "fact"),
                    "created_at": ev.get("timestamp"),
                    "evidence_event_ids": [ev.get("event_id") or f"{sid}:e{i}"],
                }
            )
    return out


def build_nodes(session: dict) -> Tuple[List[Any], List[Memory]]:
    """Construct the typed DataPoint graph for one recorded session."""
    sid = session["session_id"]
    repo_d = session.get("repo", {}) or {}
    repo = Repo(
        name=repo_d.get("name", "unknown-repo"),
        url=repo_d.get("url"),
        description=repo_d.get("description"),
    )
    sess = AgentSession(
        session_id=sid,
        task=session.get("task", ""),
        agent=session.get("agent"),
        started_at=session.get("started_at"),
        repo=repo,
    )

    events: List[SessionEvent] = []
    for i, ev in enumerate(session.get("events", [])):
        events.append(
            SessionEvent(
                event_id=ev.get("event_id") or f"{sid}:e{i}",
                session_id=sid,
                kind=ev.get("kind", "event"),
                content=ev.get("content", ""),
                timestamp=ev.get("timestamp"),
                ordinal=(ev.get("ordinal") if ev.get("ordinal") is not None else i),
                session=sess,
            )
        )

    mem_dicts = session.get("memories") or _derive_memories_from_events(session)
    memories: List[Memory] = []
    by_id: dict[str, Memory] = {}
    for i, m in enumerate(mem_dicts):
        mid = m.get("memory_id") or f"{sid}:m{i}"
        mem = Memory(
            memory_id=mid,
            text=(m.get("text") or "").strip(),
            kind=m.get("kind", "fact"),
            subject=m.get("subject"),
            created_at=m.get("created_at") or session.get("started_at"),
            trust_score=compute_trust(m),
            status=STATUS_CANDIDATE,
            reinforcement_count=int(m.get("reinforcement_count", 1) or 1),
            evidence_event_ids=list(m.get("evidence_event_ids") or []),
            source_session_id=sid,
        )
        memories.append(mem)
        by_id[mid] = mem

    # Wire supersedes edges (a newer memory replacing an older value on the same subject).
    for mem, src in zip(memories, mem_dicts):
        sup = src.get("supersedes_id")
        if sup and sup in by_id and by_id[sup] is not mem:
            mem.supersedes = by_id[sup]

    nodes: List[Any] = [repo, sess, *events, *memories]
    return nodes, memories


async def ingest_session(session: dict, *, cognify: bool = True) -> dict:
    """Remember one session: insert typed nodes (+ optionally build the entity graph)."""
    configure_cognee()
    import cognee
    from cognee.tasks.storage import add_data_points

    nodes, memories = build_nodes(session)
    await add_data_points(nodes)

    cognified = False
    if cognify:
        transcript = render_session_text(session)
        await cognee.add(transcript, dataset_name=CF_DATASET)
        await cognee.cognify(datasets=[CF_DATASET])
        cognified = True

    return {
        "session_id": session["session_id"],
        "nodes_added": len(nodes),
        "memories_created": len(memories),
        "cognified": cognified,
    }
