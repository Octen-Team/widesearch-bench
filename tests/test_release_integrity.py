"""Regression coverage for entity identity and benchmark observability."""
import asyncio
from dataclasses import asdict
from unittest.mock import patch

from widesearch_bench.grading import grade
from widesearch_bench.normalize import entity_match
from widesearch_bench.octen_client import SearchHit
from widesearch_bench.runner import run_one_concurrent
from widesearch_bench.schema import Task, TaskType, GoldEntity, ArmRun


def task():
    return Task('audit', TaskType.T1_ENUM, 'q', gold_entities=[GoldEntity('Entity')],
                as_of='2026-09-18', min_gold_domains=0)


def test_distinct_product_variants_and_languages():
    for a, b in [('C', 'C++'), ('C#', 'C++'), ('Apple M3', 'Apple M3 Pro'),
                 ('Apple M3 Pro', 'Apple M3 Max'), ('GLM-4.5', 'GLM-4.5-Air'),
                 ('Node.js Foundation', 'JS Foundation')]:
        assert not entity_match(a, GoldEntity(b)), (a, b)
        assert not entity_match(b, GoldEntity(a)), (b, a)


def test_dedup_requires_identity_decision_not_containment():
    from tools.dedup_gold import group
    golds = [{'canonical': n, 'aliases': []} for n in ['C', 'C++', 'Apple M3', 'Apple M3 Pro']]
    assert group(golds) == [[0], [1], [2], [3]]


class ConcurrentClient:
    def __init__(self):
        self.n_requests = 0
        self.ready = asyncio.Event()

    async def broad_search(self, query, **kwargs):
        # Exercise the production HTTP accounting hook once it is available.
        from widesearch_bench import octen_client
        if hasattr(octen_client, 'record_request'):
            octen_client.record_request()
        self.n_requests += 1
        if self.n_requests == 2:
            self.ready.set()
        await self.ready.wait()
        return [SearchHit(url='https://example.com', snippet='Entity', sub_query=query)]


def test_concurrent_request_counts_are_isolated_and_persisted():
    async def exercise():
        client = ConcurrentClient()
        with patch('widesearch_bench.runner._read_sync', return_value=(
                {'entities': ['Entity']}, 'Entity', {'prompt_tokens': 1})):
            runs = await asyncio.gather(*[
                run_one_concurrent(client, None, task(), 'octen-broad-search', i)
                for i in range(2)])
        assert all(r.error is None for r, _ in runs), [r.error for r, _ in runs]
        assert [r.http_requests for r, _ in runs] == [1, 1]
        assert [asdict(grade(task(), r, ev))['http_requests'] for r, ev in runs] == [1, 1]
    asyncio.run(exercise())


def test_reader_failure_keeps_elapsed_time_and_marks_usage_unknown():
    class Client:
        n_requests = 0
        async def broad_search(self, query, **kwargs):
            await asyncio.sleep(0.01)
            return [SearchHit(url='https://example.com', snippet='Entity', sub_query=query)]
    async def exercise():
        with patch('widesearch_bench.runner._read_sync', side_effect=ValueError('bad JSON')):
            run, _ = await run_one_concurrent(Client(), None, task(), 'octen-broad-search', 0)
        assert run.error and "bad JSON" in run.error
        assert run.e2e_time_s >= 0.01
        assert run.downstream_tokens is None
    asyncio.run(exercise())


def test_agent_queries_survive_grading():
    from widesearch_bench.agent import agent_loop
    async def exercise():
        replies = iter(['SEARCH: precise query', 'ANSWER: {"entities": ["Entity"]}'])
        async def complete(*args): return next(replies), {'prompt_tokens': 3}
        async def search(*args): return [SearchHit(url='https://example.com', snippet='Entity')]
        result = await agent_loop(search, complete, 'q')
        assert result['subqueries'] == ['precise query']
    asyncio.run(exercise())


def test_identity_qualifier_after_parenthetical_is_preserved():
    gold = GoldEntity('Matter 1.4', ['Matter (Connectivity Standards Alliance) Core Specification version 1.4'])
    assert not entity_match('Matter', gold)


def test_live_report_keeps_failed_quality_and_excludes_failed_costs():
    from widesearch_bench.runner import build_report
    from widesearch_bench.grading import Grade
    good = Grade('one', 'example', 0, f1=1.0, downstream_tokens=100)
    failed = Grade('two', 'example', 0, downstream_tokens=None, detail={'error':'failure'})
    r = build_report([], [good, failed], ['example'])['arms']['example']
    assert r['f1_mean'] == 0.5
    assert r['n_tasks'] == 2
    assert r['n_failures'] == 1
    assert r['downstream_tokens_mean'] == 100


def test_prediction_descriptions_preserve_identity_qualifiers():
    assert entity_match('SpaceX — Falcon 1 reached orbit in 2008', GoldEntity('SpaceX'))
    assert entity_match('San Diego FC — MLS — inaugural season 2025', GoldEntity('San Diego FC'))
    for pred, gold in [('Apple A19 — Pro', 'Apple A19'),
                       ('YouTube — TV', 'YouTube'),
                       ('Nobel Prize', 'Nobel Prize in Physics')]:
        assert not entity_match(pred, GoldEntity(gold))


def test_http_retry_accounting_accepts_successful_narrow_response():
    import httpx
    from unittest.mock import AsyncMock
    from widesearch_bench.octen_client import OctenClient
    async def exercise():
        attempts = []
        def respond(request):
            attempts.append(request)
            if len(attempts) == 1:
                return httpx.Response(429, json={})
            return httpx.Response(200, json={'data': {'results': [
                {'url': 'https://example.com', 'highlight': 'Entity'}]}})
        client = OctenClient(api_key='test-key')
        await client._client.aclose()
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            with patch('widesearch_bench.octen_client.asyncio.sleep', new=AsyncMock()), \
                 patch('widesearch_bench.runner._read_sync', return_value=(
                     {'entities':['Entity']}, 'Entity', {'prompt_tokens':1})):
                run, ev = await run_one_concurrent(client, None, task(), 'octen-broad-search', 0)
            assert run.error is None
            assert len(attempts) == 2  # 429 retry only; do not reselect 200 responses
            assert grade(task(), run, ev).http_requests == 2
            assert run.api_calls == 1
        finally:
            await client.aclose()
    asyncio.run(exercise())


def test_agent_run_persists_queries_and_raw_evidence(tmp_path):
    from widesearch_bench.agent import agent_loop
    async def exercise():
        replies = iter(['SEARCH: precise query', 'ANSWER: {"entities": ["Entity"]}'])
        async def complete(*args): return next(replies), {'prompt_tokens':3}
        async def search(*args): return [SearchHit(url='https://example.com', snippet='Entity')]
        result = await agent_loop(search, complete, 'q')
        with patch('widesearch_bench.agent.agent_loop', return_value=result):
            run, evidence = await run_one_concurrent(None, None, task(), 'exa-instant-agent', 0,
                                                     raw_dir=tmp_path)
        assert run.error is None
        assert grade(task(), run, evidence).detail['subqueries'] == ['precise query']
        import json
        raw = json.loads((tmp_path/'audit__exa-instant-agent__0.jsonl').read_text())
        assert raw['sub_query'] == 'precise query'
        assert raw['snippet'] == 'Entity'
    asyncio.run(exercise())


def test_released_gold_keeps_identities_distinct_and_aliases_shared():
    from pathlib import Path
    from widesearch_bench.schema import load_tasks
    from widesearch_bench.normalize import match_sets
    root = Path(__file__).resolve().parents[1]
    for filename in ['tasks.jsonl', 'tasks_strict.jsonl']:
        tasks = {t.id:t for t in load_tasks(root/'data'/filename)}
        languages = tasks['ws-0253'].gold_entities
        c = next(g for g in languages if g.canonical == 'C')
        cpp = next(g for g in languages if g.canonical == 'C++')
        assert len(match_sets(['C', 'C++'], [c, cpp])[0]) == 2
        chips = tasks['ws-0166'].gold_entities
        for g in chips:
            if g.canonical.startswith('Apple '):
                assert entity_match(g.canonical[6:], g), g.canonical
        for tid in ['ws-0037','ws-0167','ws-0235','ws-0286','ws-0294','ws-0189']:
            golds = tasks[tid].gold_entities
            for i, a in enumerate(golds):
                for b in golds[i+1:]:
                    assert not entity_match(a.canonical,b), (tid,a.canonical,b.canonical)
                    assert not entity_match(b.canonical,a), (tid,b.canonical,a.canonical)


def test_released_names_and_multilingual_explanations():
    from pathlib import Path
    from widesearch_bench.schema import load_tasks
    tasks = {t.id:t for t in load_tasks(Path(__file__).resolve().parents[1]/'data/tasks.jsonl')}
    for tid, pred in [
        ('ws-0258','reSET-O'), ('ws-0243','LandSpace'),
        ('ws-0300','Thinking Machines Lab'), ('ws-0014','Freevee (standalone Freevee app)'),
        ('ws-0050','中国银联 (China UnionPay) — 已获中国人民银行核发的银行卡清算业务许可证 (见中国人民银行公告，2019)'),
        ('ws-0066','Charlotte FC (MLS) — inaugural/expansion season 2022'),
        ('ws-0066','Angel City FC (NWSL) — inaugural/expansion season 2022')]:
        assert any(entity_match(pred,g) for g in tasks[tid].gold_entities), (tid,pred)
