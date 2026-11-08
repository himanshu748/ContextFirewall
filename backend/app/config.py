"""Single source of truth for the chat-LLM settings.

Both Cognee (graph extraction, ``cognee_runtime/bootstrap.py``) and the firewall's
direct chat client (``cognee_runtime/llm.py``) resolve model, endpoint and API key
through here, so pointing ``LLM_ENDPOINT`` at e.g. a local Ollama server moves both.
Env vars are read on every call (no caching) so tests and late ``.env`` loads work.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Pin the HF router provider (":novita"): the bare model auto-routes and can 403.
DEFAULT_LLM_MODEL = "openai/Qwen/Qwen2.5-72B-Instruct:novita"
DEFAULT_LLM_ENDPOINT = "https://router.huggingface.co/v1"


@dataclass(frozen=True)
class LLMSettings:
    model: str  # as configured, incl. the litellm "openai/" prefix (Cognee form)
    endpoint: str  # base URL, no trailing slash
    api_key: str
    chat_endpoint: str  # full chat-completions URL (direct client)

    @property
    def chat_model(self) -> str:
        """Bare model id for OpenAI-compatible servers (``openai/`` prefix stripped)."""
        return self.model.removeprefix("openai/")


def resolve_llm_settings() -> LLMSettings:
    endpoint = (os.getenv("LLM_ENDPOINT") or DEFAULT_LLM_ENDPOINT).rstrip("/")
    return LLMSettings(
        model=os.getenv("LLM_MODEL") or DEFAULT_LLM_MODEL,
        endpoint=endpoint,
        api_key=os.getenv("LLM_API_KEY") or os.getenv("HUGGINGFACE_API_KEY") or "",
        # LLM_CHAT_ENDPOINT stays an explicit full-URL override.
        chat_endpoint=os.getenv("LLM_CHAT_ENDPOINT") or f"{endpoint}/chat/completions",
    )
