"""LLM wrapper with two providers, selected by model-string prefix:

  "openrouter/<vendor>/<model>"  -> OpenRouter (OpenAI-compatible), e.g.
                                    openrouter/<vendor>/<model>
  anything else                  -> Anthropic SDK (base_url overridable via
                                    ANTHROPIC_BASE_URL override)

Invariants shared by both paths:
- STATELESS single-turn calls only (one system + one user message). Any
  reasoning/thinking content in responses is read-only and never echoed back —
  this sidesteps preserved-thinking-history instability in reasoning models entirely.
- Real usage tokens captured per call into `last_usage` when the provider
  reports them (OpenRouter does; runner prefers this over estimates).
- JSON contract enforced by prompt + tolerant parsing (parse_json), with one
  retry on parse failure appended by complete_json.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Optional

DEFAULT_MODEL = os.environ.get("WIDESEARCH_MODEL", "claude-sonnet-4-6")
OPENROUTER_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1") + "/chat/completions"
RETRYABLE = {429, 500, 502, 503, 504}


def parse_json(text: str) -> Any:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    m = re.search(r"[\[{]", text)
    if m:
        text = text[m.start():]
    return json.loads(text)


class _BaseLLM:
    last_usage: dict[str, int]

    def complete(self, system: str, user: str, max_tokens: Optional[int] = None) -> str:
        raise NotImplementedError

    def complete_json(self, system: str, user: str,
                      max_tokens: Optional[int] = None) -> Any:
        text = self.complete(system, user, max_tokens)
        try:
            return parse_json(text)
        except (json.JSONDecodeError, ValueError) as e:
            first_usage = dict(self.last_usage)
            retry_user = (f"{user}\n\nYour previous output failed JSON parsing "
                          f"({str(e)[:200]}). Return ONLY the JSON, no prose, no fences.")
            text = self.complete(system, retry_user, max_tokens)
            self.last_usage = {k: first_usage.get(k, 0) + self.last_usage.get(k, 0)
                               for k in first_usage.keys() | self.last_usage.keys()}
            return parse_json(text)


class AnthropicLLM(_BaseLLM):
    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 2000) -> None:
        import anthropic
        kwargs: dict[str, Any] = {}
        if os.environ.get("ANTHROPIC_BASE_URL"):
            kwargs["base_url"] = os.environ["ANTHROPIC_BASE_URL"]
        self.client = anthropic.Anthropic(**kwargs)
        self.model = model
        self.max_tokens = max_tokens
        self.last_usage = {}

    def complete(self, system: str, user: str, max_tokens: Optional[int] = None) -> str:
        msg = self.client.messages.create(
            model=self.model, max_tokens=max_tokens or self.max_tokens,
            system=system, messages=[{"role": "user", "content": user}])
        u = getattr(msg, "usage", None)
        self.last_usage = ({"prompt_tokens": u.input_tokens,
                            "completion_tokens": u.output_tokens} if u else {})
        return "".join(b.text for b in msg.content if b.type == "text")


class OpenRouterLLM(_BaseLLM):
    """OpenAI-compatible chat completions against OpenRouter.

    httpx-based (no openai SDK dependency). Defaults: temperature=1.0,
    top_p=1.0 (OpenRouter default), overridable via WIDESEARCH_TEMPERATURE.
    Retries on 429/5xx with exponential backoff.
    """

    def __init__(self, model: str, max_tokens: int = 2000,
                 max_retries: int = 4) -> None:
        import httpx
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.temperature = float(os.environ.get("WIDESEARCH_TEMPERATURE", "1.0"))
        headers = {
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        }
        if os.environ.get("OPENROUTER_REFERER"):
            headers["HTTP-Referer"] = os.environ["OPENROUTER_REFERER"]
        if os.environ.get("OPENROUTER_TITLE"):
            headers["X-Title"] = os.environ["OPENROUTER_TITLE"]
        self._client = httpx.Client(timeout=180.0, headers=headers)
        self.last_usage = {}

    def _payload(self, system: str, user: str, max_tokens: Optional[int]) -> dict:
        budget = max_tokens or self.max_tokens
        payload = {
            "model": self.model,
            "max_tokens": budget,
            "temperature": self.temperature,
            "top_p": 1.0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        # Reasoning models can spend the entire completion budget on
        # reasoning and return empty content — the JSON-parse retry can never
        # recover from that. WIDESEARCH_REASONING_MAX_TOKENS caps the reasoning
        # budget so the answer always has room; unset/0 keeps the payload as-is.
        cap = int(os.environ.get("WIDESEARCH_REASONING_MAX_TOKENS", "0"))
        if cap > 0:
            payload["reasoning"] = {"max_tokens": cap}
        return payload

    def complete(self, system: str, user: str, max_tokens: Optional[int] = None) -> str:
        payload = self._payload(system, user, max_tokens)
        last_err: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            resp = self._client.post(OPENROUTER_URL, json=payload)
            if resp.status_code in RETRYABLE:
                last_err = f"HTTP {resp.status_code}"
                time.sleep(min(2 ** attempt, 15))
                continue
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:  # OpenRouter can return 200 with an error body
                last_err = str(data["error"])[:200]
                time.sleep(min(2 ** attempt, 15))
                continue
            u = data.get("usage") or {}
            self.last_usage = {"prompt_tokens": u.get("prompt_tokens", 0),
                               "completion_tokens": u.get("completion_tokens", 0)}
            msg = data["choices"][0]["message"]
            # reasoning fields are read-only; return content only
            return msg.get("content") or ""
        raise RuntimeError(f"OpenRouter failed after retries: {last_err}")


import threading as _threading
from concurrent.futures import ThreadPoolExecutor as _TPE

_tls = _threading.local()


def _worker_llm(model: Optional[str], max_tokens: int) -> "_BaseLLM":
    """One LLM client per worker thread (httpx.Client isn't meant to be shared
    across threads for concurrent requests)."""
    clients = getattr(_tls, "clients", None)
    if clients is None:
        clients = _tls.clients = {}
    key = (model or os.environ.get("WIDESEARCH_MODEL", DEFAULT_MODEL), max_tokens)
    if key not in clients:
        clients[key] = make_llm(*key)
    return clients[key]


def concurrent_map(fn, items: list, model: Optional[str] = None,
                   max_tokens: int = 2000, workers: int = 16) -> list:
    """Run fn(worker_llm, item) across a thread pool. Order preserved; failures
    become None. Used to parallelize LLM-bound batch stages instead of
    the ~12s/call sequential path."""
    results: list = [None] * len(items)

    def run(i_item):
        i, item = i_item
        llm = _worker_llm(model, max_tokens)
        try:
            return i, fn(llm, item)
        except Exception:  # noqa: BLE001
            return i, None

    with _TPE(max_workers=workers) as ex:
        for i, r in ex.map(run, list(enumerate(items))):
            results[i] = r
    return results


class OpenAILLM(_BaseLLM):
    """OpenAI official API (api.openai.com). Handles reasoning-model contract:
    max_completion_tokens (not max_tokens), reasoning_effort, no temperature.
    """

    def __init__(self, model: str, max_tokens: int = 2000, max_retries: int = 4) -> None:
        import httpx
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.effort = os.environ.get("WIDESEARCH_OPENAI_EFFORT", "low")
        self._client = httpx.Client(
            timeout=180.0,
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                     "Content-Type": "application/json"})
        self.last_usage = {}

    def complete(self, system: str, user: str, max_tokens: Optional[int] = None) -> str:
        payload = {
            "model": self.model,
            "max_completion_tokens": max_tokens or self.max_tokens,
            "reasoning_effort": self.effort,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        last = None
        for attempt in range(self.max_retries + 1):
            resp = self._client.post("https://api.openai.com/v1/chat/completions", json=payload)
            if resp.status_code in RETRYABLE:
                last = f"HTTP {resp.status_code}"
                time.sleep(min(2 ** attempt, 15))
                continue
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                last = str(data["error"])[:200]
                time.sleep(min(2 ** attempt, 15))
                continue
            u = data.get("usage") or {}
            self.last_usage = {"prompt_tokens": u.get("prompt_tokens", 0),
                               "completion_tokens": u.get("completion_tokens", 0)}
            return data["choices"][0]["message"].get("content") or ""
        raise RuntimeError(f"OpenAI failed after retries: {last}")


def make_llm(model: Optional[str] = None, max_tokens: int = 2000) -> _BaseLLM:
    model = model or os.environ.get("WIDESEARCH_MODEL", DEFAULT_MODEL)
    if model.startswith("openai:"):
        return OpenAILLM(model.removeprefix("openai:"), max_tokens)
    if model.startswith("openrouter/"):
        return OpenRouterLLM(model.removeprefix("openrouter/"), max_tokens)
    return AnthropicLLM(model, max_tokens)


# Back-compat alias: existing call sites construct LLM(model=...)
def LLM(model: Optional[str] = None, max_tokens: int = 2000) -> _BaseLLM:  # noqa: N802
    return make_llm(model, max_tokens)
