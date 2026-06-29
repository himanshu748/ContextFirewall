"""Probe Hugging Face inference reachability + which models answer.

Stdlib only (urllib) so it runs on any Python. Reads HUGGINGFACE_API_KEY from env
(injected via RunWithCredentials). Tests the OpenAI-compatible router for chat and
embeddings so we know exactly how to configure Cognee's litellm provider.
"""
import os
import sys
import json
import urllib.request
import urllib.error

HF_KEY = os.environ.get("HUGGINGFACE_API_KEY")
if not HF_KEY:
    print("NO HUGGINGFACE_API_KEY in env")
    sys.exit(1)
print("HF key present, length:", len(HF_KEY))


def post(url, payload, key, timeout=60):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:600]
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
chat_models = [
    "meta-llama/Llama-3.3-70B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
]
print("\n=== CHAT (router /v1/chat/completions) ===")
working_chat = []
for m in chat_models:
    status, body = post(
        CHAT_URL,
        {
            "model": m,
            "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
            "max_tokens": 10,
        },
        HF_KEY,
    )
    snippet = body
    ok = False
    if status == 200:
        try:
            j = json.loads(body)
            snippet = j["choices"][0]["message"]["content"]
            ok = True
        except Exception as ex:  # noqa: BLE001
            snippet = f"parse-error {ex}: {body[:200]}"
    print(f"[{status}] {m} -> {str(snippet)[:140]}")
    if ok:
        working_chat.append(m)
print("WORKING_CHAT_MODELS:", working_chat)

print("\n=== EMBEDDINGS (router /v1/embeddings) ===")
emb_models = ["BAAI/bge-small-en-v1.5", "sentence-transformers/all-MiniLM-L6-v2", "intfloat/multilingual-e5-large"]
working_emb = []
for m in emb_models:
    status, body = post(
        "https://router.huggingface.co/v1/embeddings",
        {"model": m, "input": "hello world"},
        HF_KEY,
    )
    dims = ""
    ok = False
    if status == 200:
        try:
            j = json.loads(body)
            vec = j["data"][0]["embedding"]
            dims = f"dims={len(vec)}"
            ok = True
        except Exception as ex:  # noqa: BLE001
            dims = f"parse-error {ex}: {body[:150]}"
    print(f"[{status}] {m} -> {dims or str(body)[:140]}")
    if ok:
        working_emb.append((m, dims))
print("WORKING_EMBED_MODELS:", working_emb)
