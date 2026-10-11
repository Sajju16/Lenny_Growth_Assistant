import httpx
import time
import json
import sys

def run_benchmark(run_num=1):
    url = "http://127.0.0.1:8000/api/chat/stream"
    payload = {
        "message": "How should an early-stage startup improve retention, and should we focus on early user experience or resurrection campaigns?",
        "model": "qwen2.5:1.5b",
        "use_rag": True,
    }

    ps_before = httpx.get("http://127.0.0.1:11434/api/ps").json()
    models_before = [m["name"] for m in ps_before.get("models", [])]

    print(f"\n--- Run #{run_num} ---")
    print("Ollama models loaded before:", models_before)

    t0 = time.perf_counter()
    t_connected = None
    t_first_token = None
    t_first_meta = None
    token_count = 0
    full_text = ""
    done_data = None
    token_times = []

    with httpx.Client(timeout=180.0) as client:
        with client.stream("POST", url, json=payload) as resp:
            t_connected = time.perf_counter() - t0
            for line in resp.iter_lines():
                if not line:
                    continue
                now = time.perf_counter() - t0
                if line.startswith("data:"):
                    try:
                        d = json.loads(line[5:].strip())
                        if "citations" in d and t_first_meta is None and "delta" not in d:
                            t_first_meta = now
                        elif "delta" in d:
                            if t_first_token is None:
                                t_first_token = now
                            token_count += 1
                            full_text += d["delta"]
                            token_times.append(now)
                        elif "response" in d:
                            done_data = d
                    except Exception as e:
                        pass

    t_total = time.perf_counter() - t0
    ps_after = httpx.get("http://127.0.0.1:11434/api/ps").json()
    models_after = [m["name"] for m in ps_after.get("models", [])]

    gen_time = (token_times[-1] - t_first_token) if (token_times and t_first_token) else 0.0
    tps = (token_count / gen_time) if gen_time > 0 else 0.0

    print(f"Time to connect: {t_connected:.3f}s")
    print(f"Time to first metadata event: {t_first_meta:.3f}s")
    print(f"Time to first token (TTFT): {t_first_token:.3f}s")
    print(f"Total stream duration: {t_total:.3f}s")
    print(f"Token generation duration: {gen_time:.3f}s")
    print(f"Tokens received: {token_count} (actual TPS: {tps:.2f} tokens/s)")
    print(f"Word count: {len(full_text.split())} words")
    print("Backend timing metadata:", done_data.get("timing") if done_data else None)
    print("Backend eval metadata:", done_data.get("metadata") if done_data else None)
    citations = done_data.get("citations", []) if done_data else []
    print(f"Verified citations ({len(citations)}): {[c.get('guest') for c in citations]}")
    print("Ollama models loaded after:", models_after)
    return {
        "run": run_num,
        "ttft": t_first_token,
        "total": t_total,
        "tokens": token_count,
        "tps": tps,
        "words": len(full_text.split()),
        "citations": [c.get("guest") for c in citations],
    }

if __name__ == "__main__":
    run_benchmark(1)
