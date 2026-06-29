"""End-to-end smoke test: prove Cognee runs live on Hugging Face inference.

Runs the real lifecycle against a tiny dataset:
  add -> cognify (HF chat extraction) -> search (GRAPH_COMPLETION + CHUNKS).
No mocking. Requires backend/.env with a working HF key.

Run:
    cd backend && set -a && . ./.env && set +a && PYTHONPATH=. .venv/bin/python scripts/smoke_cognee.py
"""
import asyncio
import time

from app.cognee_runtime.bootstrap import configure_cognee

SAMPLE = (
    "ContextFirewall records AI coding-agent sessions into a knowledge graph. "
    "On 2026-06-20 the production deploy command was 'make deploy-v1'. "
    "On 2026-06-28 the deploy command changed to 'make deploy-v2', and v1 was "
    "marked deprecated and unsafe to run. "
    "The integration test suite requires a Postgres database listening on port 5432."
)


async def main() -> None:
    profile = configure_cognee()
    print("=== COGNEE PROFILE ===")
    for k, v in profile.items():
        print(f"  {k}: {v}")

    import cognee
    from cognee import SearchType

    print("\n=== reset (prune) for a clean smoke ===")
    try:
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(graph=True, vector=True, metadata=True)
        print("  pruned")
    except Exception as e:  # noqa: BLE001
        print("  prune warning:", repr(e))

    print("\n=== add ===")
    await cognee.add(SAMPLE, dataset_name="cf_smoke")
    print("  added 1 document to dataset 'cf_smoke'")

    print("\n=== cognify (calls HF chat model — may take 30-120s) ===")
    t0 = time.time()
    await cognee.cognify(datasets=["cf_smoke"])
    print(f"  cognify OK in {time.time() - t0:.1f}s")

    print("\n=== search: GRAPH_COMPLETION ===")
    t0 = time.time()
    answer = await cognee.search(
        query_text="What is the current deploy command, and which one is deprecated?",
        query_type=SearchType.GRAPH_COMPLETION,
    )
    print(f"  ({time.time() - t0:.1f}s) ANSWER:", answer)

    print("\n=== search: CHUNKS (retrieval only, no LLM) ===")
    chunks = await cognee.search(query_text="deploy command", query_type=SearchType.CHUNKS)
    print("  CHUNKS:", str(chunks)[:600])

    print("\nSMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
