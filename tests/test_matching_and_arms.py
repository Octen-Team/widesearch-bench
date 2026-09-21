"""Matcher and arm tests — client-side per-sub-query cap + round-robin interleave;
T4: time-pushdown switch and cross-arm consistency."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from widesearch_bench.arms import arm_a1, arm_a2, arm_a3, time_bounds
from widesearch_bench.octen_client import OctenClient, SearchHit
from widesearch_bench.reader import _interleave_by_subquery, _render_snippets
from widesearch_bench.schema import Task, TaskType


def _fake_broad_response(n_subs: int, per_sub: int) -> dict:
    return {"code": 0, "data": {"search_results": [
        {"query": f"sub-{s}", "results": [
            {"url": f"https://ex.com/{s}/{i}", "title": f"t{s}-{i}",
             "highlight": f"h{s}-{i}"}
            for i in range(per_sub)]}
        for s in range(n_subs)]}}


def test_broad_search_client_cap():
    """Server returning 10/sub-query must be capped to the requested 3."""
    oc = OctenClient(api_key="test-key")

    async def fake_post(path, payload):
        # contract shape: per-sub-query options under search_options
        assert payload["search_options"]["count"] == 3
        assert "count" not in payload
        return _fake_broad_response(n_subs=4, per_sub=10)

    oc._post = fake_post
    hits = asyncio.run(oc.broad_search("q", max_queries=4, count=3))
    asyncio.run(oc.aclose())
    per = {}
    for h in hits:
        per[h.sub_query] = per.get(h.sub_query, 0) + 1
    assert per == {f"sub-{s}": 3 for s in range(4)}, per
    # in-group ranking preserved: top-3 of each group survive
    assert [h.url for h in hits if h.sub_query == "sub-0"] == [
        f"https://ex.com/0/{i}" for i in range(3)]


def _mk_hits(n_subs: int, per_sub: int) -> list[SearchHit]:
    return [SearchHit(url=f"https://ex.com/{s}/{i}", title=f"t{s}-{i}",
                      snippet=f"snippet {s}-{i}", sub_query=f"sub-{s}")
            for s in range(n_subs) for i in range(per_sub)]


def test_interleave_round_robin_8_groups():
    hits = _mk_hits(8, 3)  # grouped sequentially on input
    out = _interleave_by_subquery(hits)
    assert len(out) == len(hits)
    assert sorted(h.url for h in out) == sorted(h.url for h in hits)
    # first 8 = rank-0 of each group in first-appearance order, then rank-1...
    expect = [f"https://ex.com/{s}/{i}" for i in range(3) for s in range(8)]
    assert [h.url for h in out] == expect
    # unlabeled (single-group, e.g. octen-search) input keeps order verbatim
    plain = [SearchHit(url=f"https://ex.com/{i}", snippet="x") for i in range(5)]
    assert [h.url for h in _interleave_by_subquery(plain)] == [h.url for h in plain]


def test_interleave_truncation_covers_all_groups():
    """When the render window truncates, every sub-query must still surface."""
    hits = _mk_hits(8, 3)
    block = len("[0] https://ex.com/0/0\nt0-0\nsnippet 0-0\n") + 1
    budget = block * 10  # room for ~10 of 24 blocks
    rendered_no_ilv = _render_snippets(hits, max_chars=budget)
    rendered_ilv = _render_snippets(_interleave_by_subquery(hits), max_chars=budget)
    covered_no_ilv = {s for s in range(8) if f"/{s}/" in rendered_no_ilv}
    covered_ilv = {s for s in range(8) if f"/{s}/" in rendered_ilv}
    assert covered_no_ilv != set(range(8)), "premise: plain order drops tail groups"
    assert covered_ilv == set(range(8)), covered_ilv


# ------------------------------------------------------------------ T5

def test_version_aware_entity_match():
    from widesearch_bench.normalize import entity_match
    from widesearch_bench.schema import GoldEntity
    k2 = GoldEntity("Kimi K2", ["Kimi-K2", "Kimi K2 Instruct", "moonshotai/Kimi-K2"])
    glm = GoldEntity("GLM-4.5", ["GLM 4.5", "zai GLM-4.5"])
    qwen = GoldEntity("Qwen3-235B", ["Qwen 3 235B", "Qwen3 235B-A22B"])
    # must BLOCK: version-style token right after the gold phrase
    assert not entity_match("Kimi K2.5", k2)
    assert not entity_match("Kimi K2.6", k2)
    assert not entity_match("GLM-4.7", glm)
    assert not entity_match("Qwen 3.5", qwen)
    # must ALLOW: explicit alias / non-version suffix
    assert entity_match("Kimi K2 Instruct", k2)     # alias verbatim
    assert entity_match("GLM-4.5 series", glm)      # suffix is not a version token
    assert entity_match("kimi k2", k2)              # plain canonical still fine
    assert entity_match("Kimi K2 (Moonshot)", k2)   # legacy containment intact


# ------------------------------------------------------------------ T4

def test_time_bounds():
    assert time_bounds(None) == (None, None)
    assert time_bounds("2025") == ("2025-01-01T00:00:00Z", "2026-01-01T00:00:00Z")


def test_time_scope_validation():
    base = dict(id="x", type=TaskType.T4_CONTROL, question="q?",
                gold_answer="a", as_of="2026-01-01")
    assert Task(**base, time_scope="2025").validate() == []
    assert any("time_scope" in e for e in Task(**base, time_scope="H1-2025").validate())


class _CaptureOcten:
    """Fake retrieval layer recording the time kwargs of every call."""
    def __init__(self):
        self.calls = []  # (method, start_time, end_time)

    async def search(self, query, count=5, start_time=None, end_time=None, **kw):
        self.calls.append(("search", start_time, end_time))
        return [SearchHit(url=f"https://ex.com/{len(self.calls)}", snippet="s")]

    async def broad_search(self, query, max_queries=8, count=3,
                           start_time=None, end_time=None, **kw):
        self.calls.append(("broad_search", start_time, end_time))
        return [SearchHit(url="https://ex.com/b", snippet="s", sub_query="sq")]

    async def parallel_search(self, queries, count=3,
                              start_time=None, end_time=None, **kw):
        self.calls.append(("parallel_search", start_time, end_time))
        return {q: [SearchHit(url=f"https://ex.com/{q}", snippet="s", sub_query=q)]
                for q in queries}


class _FakeLLM:
    last_usage: dict = {}
    def complete_json(self, system, user, max_tokens=None):
        return [f"sub query {i}" for i in range(8)]


def test_time_pushdown_consistent_across_arms():
    """Hard requirement: with time_scope set, every arm's retrieval calls carry
    the identical window; with it unset, none do."""
    for scope, want in [("2025", ("2025-01-01T00:00:00Z", "2026-01-01T00:00:00Z")),
                        (None, (None, None))]:
        oc = _CaptureOcten()
        asyncio.run(arm_a1(oc, "q", time_scope=scope))
        asyncio.run(arm_a2(oc, "q", time_scope=scope))
        asyncio.run(arm_a3(oc, _FakeLLM(), "q", time_scope=scope))
        assert len(oc.calls) == 3
        assert {(st, et) for _, st, et in oc.calls} == {want}, (scope, oc.calls)


# ------------------------------------------------------------------ T6

def test_grade_detail_always_has_answer_entities():
    from widesearch_bench.grading import grade
    from widesearch_bench.schema import ArmRun, GoldEntity
    task = Task(id="t", type=TaskType.T1_ENUM, question="q?",
                gold_entities=[GoldEntity("Exa")], as_of="2026-01-01",
                min_gold_domains=0)
    ok_run = ArmRun(task_id="t", arm="octen-broad-search", repeat=0, answer_entities=["Exa", "Nope"])
    assert grade(task, ok_run, "exa nope").detail["answer_entities"] == ["Exa", "Nope"]
    err_run = ArmRun(task_id="t", arm="octen-broad-search", repeat=0, error="Boom: x")
    d = grade(task, err_run).detail
    assert d["answer_entities"] == [] and "error" in d


def test_dump_raw_fields(tmp_dir="/tmp/widesearch_test_raw"):
    import json, shutil
    from pathlib import Path as P
    from widesearch_bench.runner import _dump_raw
    shutil.rmtree(tmp_dir, ignore_errors=True)
    hits = [SearchHit(url="https://ex.com/1", title="t1", snippet="s1",
                      published="2025-05-01T00:00:00Z", sub_query="sq1")]
    _dump_raw(P(tmp_dir), "task-x", "octen-broad-search", 0, hits)
    rows = [json.loads(l) for l in (P(tmp_dir) / "task-x__octen-broad-search__0.jsonl").read_text().splitlines()]
    assert rows == [{"task_id": "task-x", "sub_query": "sq1", "url": "https://ex.com/1",
                     "title": "t1", "snippet": "s1",
                     "published": "2025-05-01T00:00:00Z", "crawled": None}]
    shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"PASS {n}")
    print("matching and arm tests passed")
