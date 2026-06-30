# ContextFirewall backend — Hugging Face Space (Docker SDK).
# Deployed with the backend/ directory as the Space root.
FROM python:3.12-slim

# Build tooling + git (some cognee deps build from source on first install).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl && rm -rf /var/lib/apt/lists/*

# HF Spaces run as uid 1000; create a matching user with a writable home.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /home/user/app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user:user . .

# Local Cognee stores live here (dev profile / fallback). When the managed-store
# env vars (DB_PROVIDER=postgres, VECTOR_DB_PROVIDER=pgvector,
# GRAPH_DATABASE_PROVIDER=neo4j + connection secrets) are set as Space secrets,
# the same code externalizes storage and this dir holds only transient state.
ENV CF_DATA_DIR=/home/user/app/.cf_data

EXPOSE 7860
# --proxy-headers + trusted forwarded IPs so uvicorn honors the Space proxy's
# X-Forwarded-Proto (https). Without it, the /mcp -> /mcp/ redirect Location is
# emitted as http://, the MCP client follows to http, the Space 301s it back to
# https as a GET, the POST body is lost, and the MCP handshake hangs.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips=*"]
