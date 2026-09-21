"""Offline tests for provider routing and OpenRouter payload construction."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-real")

from widesearch_bench.llm import OpenRouterLLM, make_llm, parse_json


def test_routing():
    llm = make_llm("openrouter/meta-llama/llama-3-70b")
    assert isinstance(llm, OpenRouterLLM)
    assert llm.model == "meta-llama/llama-3-70b"   # prefix stripped
    assert llm.temperature == 1.0               # OpenRouter default


def test_payload_stateless_single_turn():
    # the reasoning cap is opt-in via env; clear it so the assertion below
    # tests the payload shape rather than the developer's shell
    os.environ.pop("WIDESEARCH_REASONING_MAX_TOKENS", None)
    llm = make_llm("openrouter/meta-llama/llama-3-70b")
    p = llm._payload("SYS", "USER", max_tokens=500)
    assert p["model"] == "meta-llama/llama-3-70b"
    assert p["max_tokens"] == 500 and p["top_p"] == 1.0
    assert len(p["messages"]) == 2              # statelessness invariant
    assert p["messages"][0]["role"] == "system"
    assert "reasoning" not in str(p)            # never echo thinking back


def test_temperature_env_override():
    os.environ["WIDESEARCH_TEMPERATURE"] = "0.2"
    try:
        llm = make_llm("openrouter/meta-llama/llama-3-70b")
        assert llm.temperature == 0.2
    finally:
        del os.environ["WIDESEARCH_TEMPERATURE"]


def test_parse_json_tolerance():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure, here is it: {"a": 1}') == {"a": 1}
    assert parse_json('["x", "y"]') == ["x", "y"]


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"PASS {n}")
    print("all routing tests passed")


def test_json_retry_usage_includes_both_completions():
    from widesearch_bench.llm import _BaseLLM
    class Fake(_BaseLLM):
        calls = 0
        def complete(self, *args):
            self.calls += 1
            self.last_usage = {'prompt_tokens':10, 'completion_tokens':5}
            return 'invalid' if self.calls == 1 else '{"ok":true}'
    llm = Fake()
    assert llm.complete_json('s','u') == {'ok':True}
    assert llm.last_usage == {'prompt_tokens':20, 'completion_tokens':10}


def test_thread_client_cache_respects_model_and_budget(monkeypatch):
    from widesearch_bench import llm
    monkeypatch.setattr(llm._tls, 'clients', {}, raising=False)
    monkeypatch.setattr(llm, 'make_llm', lambda model, budget: (model,budget))
    assert llm._worker_llm('model-a',1200) == ('model-a',1200)
    assert llm._worker_llm('model-b',2000) == ('model-b',2000)
    assert llm._worker_llm('model-a',2000) == ('model-a',2000)
