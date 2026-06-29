"""Minimal async chat client for the Hugging Face inference router.

The firewall's contradiction and evidence checks need a small, dependable
structured-LLM call. Rather than reach into cognee's internal LLM client, we call
the HF router's OpenAI-compatible chat endpoint directly (same key/model as the
cognee LLM config) and degrade gracefully: if the model is unreachable, the
caller falls back to deterministic logic and the verdict is labelled accordingly.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, List, Optional

import httpx

DEFAULT_CHAT_ENDPOINT = "https://router.huggingface.co/v1/chat/completions"
_RETRY_STATUS = {429, 500, 502, 503, 504, 524}
_JSON_RE = re.compile(r"\{.*\}", re.S)


class LLMUnavailable(RuntimeError):
    """Raised when the chat model cannot be reached (callers fall back)."""


def _model_name() -> str:
    # cognee uses an "openai/" litellm routing prefix; the raw router wants the bare id.
    model = os.getenv("LLM_MODEL", "openai/Qwen/Qwen2.5-72B-Instruct")
    return model.split("openai/", 1)[1] if model.startswith("openai/") else model


def _api_key() -> str:
    return os.getenv("LLM_API_KEY") or os.getenv("HUGGINGFACE_API_KEY") or ""


async def chat(
    messages: List[dict],
    *,
    max_tokens: int = 512,
    temperature: float = 0.0,
    timeout: float = 60.0,
    max_retries: int = 4,
) -> str:
    key = _api_key()
    if not key:
        raise LLMUnavailable("no HF/LLM API key in environment")
    endpoint = os.getenv("LLM_CHAT_ENDPOINT") or DEFAULT_CHAT_ENDPOINT
    payload = {
        "model": _model_name(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    last_err: Any = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_retries):
            try:
                r = await client.post(endpoint, headers=headers, json=payload)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"]
                if r.status_code in _RETRY_STATUS:
                    last_err = f"HTTP {r.status_code}"
                    await asyncio.sleep(min(2**attempt, 8))
                    continue
                raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:160]}")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_err = repr(exc)
                await asyncio.sleep(min(2**attempt, 8))
    raise LLMUnavailable(f"chat failed after {max_retries} retries: {last_err}")


async def chat_json(
    messages: List[dict],
    *,
    default: Optional[dict] = None,
    **kwargs: Any,
) -> dict:
    """Call chat() and parse a JSON object from the reply. Returns ``default`` on any failure."""
    fallback = default if default is not None else {}
    try:
        text = await chat(messages, **kwargs)
    except LLMUnavailable:
        return dict(fallback)
    text = text.strip()
    # strip ```json fences if present
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    match = _JSON_RE.search(text)
    if not match:
        return dict(fallback)
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else dict(fallback)
    except json.JSONDecodeError:
        return dict(fallback)


async def llm_available() -> bool:
    try:
        await chat([{"role": "user", "content": "Reply with: OK"}], max_tokens=5)
        return True
    except LLMUnavailable:
        return False
