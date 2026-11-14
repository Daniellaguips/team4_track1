"""OpenRouter chat-completions wrapper with telemetry. Key from env OPENROUTER_API_KEY only.
Every call is logged to runs/<iid>/calls.jsonl (prompt, raw response, usage, model, finish)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.environ.get("FACTORY_MODEL", "anthropic/claude-sonnet-5.5")
MAX_TOKENS = int(os.environ.get("FACTORY_MAX_TOKENS", "32000"))
URL = "https://openrouter.ai/api/v1/chat/completions"


def _key() -> str:
    k = os.environ.get("OPENROUTER_API_KEY")
    if not k:
        raise SystemExit("OPENROUTER_API_KEY not set (environment only)")
    return k


class Telemetry:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        self.calls = self.n_input = self.n_output = self.n_cache = self.attempts = 0
        self.cost = 0.0
        self.t0 = time.time()

    def summary(self, iid: str) -> dict:
        return {
            "instance_id": iid,
            "model": MODEL,
            "wall_seconds": round(time.time() - self.t0),
            "model_calls": self.calls,
            "attempts": self.attempts,
            "n_input_tokens": self.n_input,
            "n_output_tokens": self.n_output,
            "n_cache_tokens": self.n_cache,
            "cost_usd": round(self.cost, 4),
        }


def _post(body: dict) -> dict:
    data = json.dumps(body).encode()
    for attempt in range(5):
        req = urllib.request.Request(URL, data=data, headers={
            "Authorization": f"Bearer {_key()}", "Content-Type": "application/json",
            "X-Title": "click-task-factory"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(2 ** attempt * 3)
                continue
            raise RuntimeError(f"OpenRouter HTTP {e.code}: {e.read()[:300]!r}") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt < 4:
                time.sleep(2 ** attempt * 3)
                continue
            raise
    raise RuntimeError("unreachable")


def call(tel: Telemetry, stage: str, system_cached: str, user: str, model: str | None = None) -> str:
    model = model or MODEL
    body = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "usage": {"include": True},
        "messages": [
            {"role": "system", "content": [
                {"type": "text", "text": system_cached, "cache_control": {"type": "ephemeral"}}]},
            {"role": "user", "content": user},
        ],
    }
    t = time.time()
    resp = _post(body)
    choice = resp["choices"][0]
    text = choice["message"].get("content") or ""
    u = resp.get("usage", {})
    cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
    tel.calls += 1
    tel.n_input += u.get("prompt_tokens", 0)
    tel.n_output += u.get("completion_tokens", 0)
    tel.n_cache += cached
    tel.cost += float(u.get("cost", 0) or 0)
    rec = {
        "stage": stage, "model": resp.get("model", model), "requested_model": model,
        "finish_reason": choice.get("finish_reason"), "usage": u,
        "seconds": round(time.time() - t, 1),
        "prompt_sha256": hashlib.sha256((system_cached + user).encode()).hexdigest()[:16],
        "user_prompt": user, "response": text,
    }
    with open(tel.run_dir / "calls.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    if choice.get("finish_reason") == "length":
        raise RuntimeError(f"{stage}: response truncated at max_tokens")
    return text


def extract_json(text: str) -> dict:
    blocks = re.findall(r"```json\s*(.*?)```", text, re.S)
    raw = blocks[-1] if blocks else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)
