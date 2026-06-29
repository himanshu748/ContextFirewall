"""Custom Cognee embedding engine backed by the Hugging Face inference router.

Why this exists: cognee 1.2.2 ships embedding engines for fastembed (local ONNX),
ollama, openai_compatible (/v1/embeddings), and litellm. None of those reach the
HF router's feature-extraction endpoint, which is the embeddings path that works
with our HF key:

    POST https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction
    body: {"inputs": ["text", ...]}  ->  [[float, ...], ...]

Using the API for embeddings (instead of local fastembed) keeps the process light
— no onnxruntime/model in RAM — which matters in the 4 GB sandbox and on a stateless
HF Space. This class implements cognee's EmbeddingEngine protocol
(embed_text / get_vector_size / get_batch_size) and is injected via bootstrap.
"""
from __future__ import annotations

import asyncio
from typing import List

import httpx
import numpy as np

from cognee.infrastructure.llm.tokenizer.TikToken import TikTokenTokenizer

DEFAULT_ENDPOINT_TMPL = (
    "https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"
)
_RETRY_STATUS = {429, 500, 502, 503, 504, 524}


class HFRouterEmbeddingEngine:
    """Embeds text via the Hugging Face router feature-extraction endpoint."""

    def __init__(
        self,
        model: str = "BAAI/bge-small-en-v1.5",
        dimensions: int = 384,
        api_key: str | None = None,
        endpoint: str | None = None,
        batch_size: int = 16,
        max_completion_tokens: int = 512,
        timeout: float = 60.0,
        max_retries: int = 5,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self.api_key = api_key or ""
        self.endpoint = endpoint or DEFAULT_ENDPOINT_TMPL.format(model=model)
        self.batch_size = batch_size
        self.max_completion_tokens = max_completion_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.tokenizer = self.get_tokenizer()

    # --- cognee EmbeddingEngine protocol ---
    def get_vector_size(self) -> int:
        return self.dimensions

    def get_batch_size(self) -> int:
        return self.batch_size

    def get_tokenizer(self):
        return TikTokenTokenizer(model="gpt-4o", max_completion_tokens=self.max_completion_tokens)

    async def embed_text(self, text: List[str]) -> List[List[float]]:
        if isinstance(text, str):
            text = [text]
        if not text:
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"inputs": text, "options": {"wait_for_model": True}}

        last_err = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    resp = await client.post(self.endpoint, headers=headers, json=payload)
                    if resp.status_code == 200:
                        return self._parse(resp.json(), len(text))
                    if resp.status_code in _RETRY_STATUS:
                        last_err = f"HTTP {resp.status_code}: {resp.text[:160]}"
                        await asyncio.sleep(min(2**attempt, 16))
                        continue
                    raise RuntimeError(
                        f"HF embedding error {resp.status_code}: {resp.text[:200]}"
                    )
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_err = repr(exc)
                    await asyncio.sleep(min(2**attempt, 16))
        raise RuntimeError(f"HF embedding failed after {self.max_retries} retries: {last_err}")

    def _parse(self, data, n_inputs: int) -> List[List[float]]:
        """Normalize HF feature-extraction output to one fixed-size vector per input.

        Possible shapes:
          - [float, ...]                      single pooled vector (1 input, unwrapped)
          - [[float, ...], ...]               one pooled vector per input
          - [[[float, ...], ...], ...]        token-level per input -> mean-pool tokens
        """
        # Single unwrapped vector for a 1-element input.
        if n_inputs == 1 and data and isinstance(data[0], (int, float)):
            return [self._coerce(data)]
        return [self._coerce(item) for item in data]

    def _coerce(self, vec) -> List[float]:
        arr = np.asarray(vec, dtype=float)
        if arr.ndim == 2:  # token-level embeddings -> mean pool
            arr = arr.mean(axis=0)
        return arr.astype(float).tolist()
