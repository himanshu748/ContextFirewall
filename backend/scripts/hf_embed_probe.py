import os
import json
import urllib.request
import urllib.error
HF = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
print("hf key set:", bool(HF))
import litellm
litellm.drop_params = True
try:
    litellm.suppress_debug_info = True
except Exception:
    pass

print("\n--- litellm huggingface provider ---")
for m in [
    "huggingface/BAAI/bge-small-en-v1.5",
    "huggingface/sentence-transformers/all-MiniLM-L6-v2",
    "huggingface/intfloat/multilingual-e5-small",
]:
    try:
        r = litellm.embedding(model=m, input=["hello world"], api_key=HF)
        print(f"[OK] {m} dims={len(r['data'][0]['embedding'])}")
    except Exception as e:
        print(f"[ERR] {m} -> {type(e).__name__}: {str(e)[:180]}")

def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {HF}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

print("\n--- raw feature-extraction endpoints ---")
for path in [
    "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5/pipeline/feature-extraction",
    "https://api-inference.huggingface.co/models/BAAI/bge-small-en-v1.5",
]:
    s, b = post(path, {"inputs": "hello world"})
    out = b if isinstance(b, str) else str(b)
    if s == 200 and out.startswith("["):
        try:
            v = json.loads(out)
            dim = len(v) if isinstance(v[0], float) else len(v[0])
            out = f"OK vector dims~{dim}"
        except Exception:
            pass
    print(f"[{s}] {path} -> {out[:120]}")
