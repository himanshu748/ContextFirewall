"""Cognee runtime bootstrap for ContextFirewall.

Single source of truth for configuring the Cognee SDK. Config is read from the
environment (loaded from ``backend/.env`` in dev; real env vars on the Hugging
Face Space in prod) and applied via ``cognee.config`` setters BEFORE any
add/cognify/search/memify/forget call.

Profiles (selected purely by which env vars are present — identical code path):

* **dev (default):** local file stores under ``CF_DATA_DIR`` (sqlite relational,
  lancedb vector, cognee's default graph). Chat via the Hugging Face router
  (``custom`` provider). Embeddings via local ``fastembed`` (no embeddings API).
* **prod:** set ``GRAPH_DATABASE_PROVIDER=neo4j`` + ``DB_PROVIDER=postgres`` +
  ``VECTOR_DB_PROVIDER=pgvector`` and the matching connection vars to externalize
  durable storage to Supabase + Neo4j Aura. The HF Space has no DB-wire firewall,
  so these connections work there (they cannot be exercised from the build
  sandbox — see project notes).

The build sandbox firewall blocks Postgres/Bolt wire protocols, so the prod
store branch is written here but is verified on the actual Space deploy.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# .../backend/app/cognee_runtime/bootstrap.py -> parents[2] == .../backend
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_DIR / ".env"


@lru_cache(maxsize=1)
def configure_cognee() -> dict[str, Any]:
    """Idempotently configure the Cognee SDK for the active profile.

    Returns a secret-free dict describing the resolved configuration (safe to log
    or return from a health endpoint).
    """
    load_dotenv(ENV_PATH, override=False)

    # --- keep cognee's stores inside the project (dev) / a writable mount (prod) ---
    data_dir = Path(os.getenv("CF_DATA_DIR", str(BACKEND_DIR / ".cf_data"))).resolve()
    system_root = data_dir / "system"
    data_root = data_dir / "data"
    system_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)

    # --- posture: single-tenant tool, no auth gate, no session cache by default ---
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
    os.environ.setdefault("CACHING", "false")
    # Skip cognee's 30s embedding pre-flight: our HF-router engine has its own retry
    # path for cold model loads, and the pre-flight false-fails on a cold start.
    os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")

    import cognee

    cognee.config.system_root_directory(str(system_root))
    cognee.config.data_root_directory(str(data_root))

    # --- LLM: chat / graph extraction (cognify) ---
    llm_provider = os.getenv("LLM_PROVIDER", "custom")
    llm_model = os.getenv("LLM_MODEL", "openai/Qwen/Qwen2.5-72B-Instruct")
    llm_endpoint = os.getenv("LLM_ENDPOINT", "https://router.huggingface.co/v1")
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("HUGGINGFACE_API_KEY") or ""
    cognee.config.set_llm_config(
        {
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_endpoint": llm_endpoint,
            "llm_api_key": llm_api_key,
        }
    )
    # HF router providers reject response_format=json_object (instructor's default
    # "json_mode"); markdown-JSON works with any OpenAI-compatible chat endpoint.
    # Default the custom/HF provider to markdown_json_mode.
    instructor_mode = os.getenv("LLM_INSTRUCTOR_MODE") or (
        "markdown_json_mode" if llm_provider == "custom" else ""
    )
    if instructor_mode:
        cognee.config.set_llm_config({"llm_instructor_mode": instructor_mode})

    # --- Embeddings ---
    # Default: "hf_router" -> call HF's feature-extraction API (no local model in RAM;
    # light enough for the 4 GB sandbox and a stateless Space). cognee has no native
    # adapter for that endpoint, so we inject a custom EmbeddingEngine by replacing the
    # factory `create_embedding_engine` (which get_embedding_engine() resolves from its
    # module globals at call time, so every caller is routed to our engine). Other
    # providers (fastembed, openai, openai_compatible, ollama) fall through to cognee.
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "hf_router")
    embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    embedding_dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))
    cognee.config.set_embedding_config(
        {
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "embedding_dimensions": embedding_dimensions,
        }
    )
    if embedding_provider == "hf_router":
        from .hf_embeddings import HFRouterEmbeddingEngine
        import cognee.infrastructure.databases.vector.embeddings.get_embedding_engine as _gee

        _hf_engine = HFRouterEmbeddingEngine(
            model=embedding_model,
            dimensions=embedding_dimensions,
            api_key=os.getenv("EMBEDDING_API_KEY") or llm_api_key,
            endpoint=os.getenv("EMBEDDING_ENDPOINT") or None,
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "16")),
        )
        _gee.create_embedding_engine = lambda *a, **k: _hf_engine

    # --- Graph store (prod: neo4j; dev: cognee default unless overridden) ---
    graph_provider = os.getenv("GRAPH_DATABASE_PROVIDER")
    if graph_provider:
        cognee.config.set_graph_database_provider(graph_provider)
        if graph_provider == "neo4j":
            cognee.config.set_graph_db_config(
                {
                    "graph_database_provider": "neo4j",
                    "graph_database_url": os.getenv("GRAPH_DATABASE_URL", ""),
                    "graph_database_username": os.getenv("GRAPH_DATABASE_USERNAME", "neo4j"),
                    "graph_database_password": os.getenv("GRAPH_DATABASE_PASSWORD", ""),
                }
            )

    # --- Relational store (prod: postgres / Supabase; dev: sqlite default) ---
    db_provider = os.getenv("DB_PROVIDER")
    if db_provider == "postgres":
        cognee.config.set_relational_db_config(
            {
                "db_provider": "postgres",
                "db_host": os.getenv("DB_HOST", ""),
                "db_port": os.getenv("DB_PORT", "5432"),
                "db_name": os.getenv("DB_NAME", "postgres"),
                "db_username": os.getenv("DB_USERNAME", ""),
                "db_password": os.getenv("DB_PASSWORD", ""),
            }
        )

    # --- Vector store (prod: pgvector on Supabase; dev: lancedb default) ---
    vector_provider = os.getenv("VECTOR_DB_PROVIDER")
    if vector_provider:
        cognee.config.set_vector_db_provider(vector_provider)

    return {
        "profile": "prod" if (db_provider or graph_provider == "neo4j") else "dev",
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_endpoint": llm_endpoint,
        "llm_api_key_set": bool(llm_api_key),
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dimensions": embedding_dimensions,
        "graph_provider": graph_provider or "cognee-default",
        "relational_provider": db_provider or "sqlite-default",
        "vector_provider": vector_provider or "lancedb-default",
        "data_dir": str(data_dir),
    }
