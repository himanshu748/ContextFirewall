from __future__ import annotations

import asyncio

import pytest

from app.config import DEFAULT_LLM_ENDPOINT, DEFAULT_LLM_MODEL, resolve_llm_settings

_VARS = ("LLM_MODEL", "LLM_ENDPOINT", "LLM_CHAT_ENDPOINT", "LLM_API_KEY", "HUGGINGFACE_API_KEY")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for v in _VARS:
        monkeypatch.delenv(v, raising=False)


def test_defaults():
    s = resolve_llm_settings()
    assert s.model == DEFAULT_LLM_MODEL
    assert s.model.endswith(":novita")
    assert s.chat_model == "Qwen/Qwen2.5-72B-Instruct:novita"
    assert s.endpoint == DEFAULT_LLM_ENDPOINT
    assert s.chat_endpoint == "https://router.huggingface.co/v1/chat/completions"
    assert s.api_key == ""


def test_endpoint_override_drives_chat_url(monkeypatch):
    monkeypatch.setenv("LLM_ENDPOINT", "http://localhost:11434/v1/")
    s = resolve_llm_settings()
    assert s.endpoint == "http://localhost:11434/v1"
    assert s.chat_endpoint == "http://localhost:11434/v1/chat/completions"


def test_chat_endpoint_explicit_override_wins(monkeypatch):
    monkeypatch.setenv("LLM_ENDPOINT", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_CHAT_ENDPOINT", "http://other/chat")
    s = resolve_llm_settings()
    assert s.endpoint == "http://localhost:11434/v1"
    assert s.chat_endpoint == "http://other/chat"


def test_model_override_and_prefix_strip(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "openai/llama3.1:8b")
    s = resolve_llm_settings()
    assert s.model == "openai/llama3.1:8b"
    assert s.chat_model == "llama3.1:8b"
    monkeypatch.setenv("LLM_MODEL", "llama3.1:8b")
    assert resolve_llm_settings().chat_model == "llama3.1:8b"


def test_api_key_precedence(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "hf")
    assert resolve_llm_settings().api_key == "hf"
    monkeypatch.setenv("LLM_API_KEY", "llm")
    assert resolve_llm_settings().api_key == "llm"


def test_chat_client_uses_shared_settings(monkeypatch):
    from app.cognee_runtime import llm

    monkeypatch.setenv("LLM_ENDPOINT", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "openai/llama3.1:8b")
    monkeypatch.setenv("LLM_API_KEY", "k")
    seen = {}

    class R:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class C:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): ...
        async def post(self, url, headers, json):
            seen.update(url=url, model=json["model"])
            return R()

    monkeypatch.setattr(llm.httpx, "AsyncClient", C)
    assert asyncio.run(llm.chat([{"role": "user", "content": "x"}])) == "ok"
    assert seen == {"url": "http://localhost:11434/v1/chat/completions", "model": "llama3.1:8b"}
