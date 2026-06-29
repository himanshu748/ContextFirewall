"""End-to-end engine validation on REAL Cognee + Hugging Face inference.

Ingests the real ContextFirewall onboarding session, then runs recall -> the four
audit checks -> trusted context pack, and asserts the firewall blocks exactly the
memories it should (stale host decision, contradicted OOM claim, leaked key,
unsupported Cloud-tier claim) and passes the good ones.

Run (reads backend/.env):
    cd backend && PYTHONPATH=. .venv/bin/python scripts/dev_integration.py
"""
import asyncio
import json
import time
from pathlib import Path

from app.cognee_runtime.bootstrap import configure_cognee
from app.cognee_runtime.ingest import hydrate_demo_secrets, ingest_session
from app.firewall.audit import audit_memories
from app.firewall.pack import build_pack

SESSION = Path(__file__).resolve().parents[1] / "data" / "sessions" / "contextfirewall_onboarding.json"

EXPECT_BLOCKED = {
    "onb:m_host_old": "staleness",
    "onb:m_137_oom": "contradiction",
    "onb:m_secret": "secret",
    "onb:m_cloud_free": "evidence",
}
EXPECT_PASSED = {"onb:m_host_new", "onb:m_137_real", "onb:m_pg", "onb:m_dco", "onb:m_emb", "onb:m_patch"}

QUERY = (
    "Onboarding: how do I deploy the ContextFirewall backend, run the Cognee smoke on "
    "Hugging Face, set up embeddings and the test database, what caused exit 137, "
    "Cognee Cloud, and the contribution rules?"
)


async def main() -> None:
    profile = configure_cognee()
    print("=== PROFILE ===", {k: profile[k] for k in ("profile", "llm_model", "embedding_provider", "embedding_dimensions")})

    import cognee

    print("\n=== reset ===")
    try:
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(graph=True, vector=True, metadata=True)
        print("  pruned")
    except Exception as e:  # noqa: BLE001
        print("  prune warning:", repr(e))

    print("\n=== ingest (remember) ===")
    session = hydrate_demo_secrets(json.loads(SESSION.read_text()))
    t0 = time.time()
    res = await ingest_session(session, cognify=True)
    print(f"  {res} in {time.time() - t0:.1f}s")

    print("\n=== audit (recall + 4 checks) ===")
    t0 = time.time()
    audit = await audit_memories(QUERY, top_k=12)
    print(f"  recalled {len(audit['candidates'])} candidates in {time.time() - t0:.1f}s; "
          f"passed={audit['passed_count']} blocked={audit['blocked_count']}\n")
    verdict_by_id = {}
    for v in audit["candidates"]:
        verdict_by_id[v["memory_id"]] = v
        mark = "PASS" if v["passed"] else f"BLOCK[{v['block_check']}]"
        print(f"  {mark:18} {v['memory_id']:18} trust={v['trust_score']:.2f}  {v['text'][:70]}")
        if not v["passed"]:
            print(f"      ↳ {v['block_reason']}")

    print("\n=== trusted context pack ===")
    pack = await build_pack(QUERY, top_k=12)
    print(pack["pack_markdown"])
    print("\n  --- ungoverned baseline (GRAPH_COMPLETION) ---")
    print("  ", (pack["recall_answer"] or "")[:400])

    # --- self-check ---
    print("\n=== SELF-CHECK ===")
    problems = []
    for mid, expected_check in EXPECT_BLOCKED.items():
        v = verdict_by_id.get(mid)
        if v is None:
            problems.append(f"{mid}: not recalled")
        elif v["passed"]:
            problems.append(f"{mid}: expected BLOCK[{expected_check}] but PASSED")
        elif v["block_check"] != expected_check:
            problems.append(f"{mid}: blocked by {v['block_check']}, expected {expected_check}")
    for mid in EXPECT_PASSED:
        v = verdict_by_id.get(mid)
        if v is None:
            problems.append(f"{mid}: not recalled")
        elif not v["passed"]:
            problems.append(f"{mid}: expected PASS but BLOCK[{v['block_check']}] — {v['block_reason']}")
    if problems:
        print("  MISMATCHES:")
        for p in problems:
            print("   -", p)
        print("\nINTEGRATION_FAIL")
    else:
        print("  all expected verdicts correct")
        print("\nINTEGRATION_OK")


if __name__ == "__main__":
    asyncio.run(main())
