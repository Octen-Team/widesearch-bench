"""The fan-out arm's decomposition-call tokens must count toward downstream_tokens."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from widesearch_bench.octen_client import SearchHit
from widesearch_bench.runner import run_one
from widesearch_bench.schema import GoldEntity, Task, TaskType


class _FakeOcten:
    async def search(self, query, count=5, **kw):
        return [SearchHit(url="https://a.com", title="t", snippet="Exa")]

    async def broad_search(self, query, **kw):
        return [SearchHit(url="https://a.com", title="t", snippet="Exa", sub_query="s")]

    async def parallel_search(self, queries, **kw):
        return {q: [SearchHit(url=f"https://a.com/{q}", title="t", snippet="Exa",
                              sub_query=q)] for q in queries}


class _SharedLLM:
    """Same object serves subquery + reader calls (as in run_bench)."""
    def __init__(self):
        self.calls = 0
        self.last_usage = {}

    def complete_json(self, system, user, max_tokens=None):
        self.calls += 1
        if "sub-queries" in system or "sub" in system.lower() and self.calls == 1:
            self.last_usage = {"prompt_tokens": 100, "completion_tokens": 50}
            return [f"q{i}" for i in range(8)]
        self.last_usage = {"prompt_tokens": 200, "completion_tokens": 30}
        return {"entities": ["Exa"]}


def _task():
    return Task(id="t", type=TaskType.T1_ENUM, question="q?",
                gold_entities=[GoldEntity("Exa")], as_of="2026-01-01",
                min_gold_domains=0)


def test_a3_subquery_tokens_counted():
    llm = _SharedLLM()
    run, _ = asyncio.run(run_one(_FakeOcten(), llm, llm, _task(), "octen-fanout", 0))
    assert run.error is None, run.error
    # reader (200+30) + decomposition (100+50)
    assert run.downstream_tokens == 380, run.downstream_tokens


def test_a1_unaffected():
    llm = _SharedLLM()
    llm.calls = 1  # skip subquery branch behavior; only reader runs
    run, _ = asyncio.run(run_one(_FakeOcten(), llm, llm, _task(), "octen-search", 0))
    assert run.downstream_tokens == 230, run.downstream_tokens


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"PASS {n}")
    print("p1 runner tests passed")
