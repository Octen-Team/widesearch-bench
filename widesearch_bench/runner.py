"""Runner: execute tasks x arms x repeats, grade, aggregate, report.

Latency measured around the retrieval phase only (reader latency is fixed
across arms by design, so retrieval latency is the arm-attributable cost).
Downstream tokens approximated as len(evidence)/4 + reader output budget —
replace with true usage counts when the LLM wrapper exposes them.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path

from .arms import ARMS, arm_a3, a3_decompose, rrf_fuse, time_bounds, arm_competitor

COMPETITOR_ARMS = {"exa", "tavily", "brave",
                   "exa-instant", "tavily-ultrafast", "parallel-turbo"}
from .grading import Grade, grade
from .llm import LLM, _worker_llm
from .octen_client import OctenClient
from .reader import read_answer
from .schema import ArmRun, Task, TaskType, load_tasks
from .stats import paired_compare, stratify


def _read_sync(model, task, hits):
    """Reader call on a worker thread (own LLM); usage captured in-thread to
    avoid cross-job races on last_usage."""
    llm = _worker_llm(model, 2000)
    parsed, evidence = read_answer(llm, task, hits)
    return parsed, evidence, dict(getattr(llm, "last_usage", {}) or {})


def _decompose_sync(model, question, n_sub):
    llm = _worker_llm(model, 2000)
    subs = a3_decompose(llm, question, n_sub)
    return subs, dict(getattr(llm, "last_usage", {}) or {})


async def run_one_concurrent(octen, model, task, arm, repeat,
                             time_pushdown=True, raw_dir=None):
    """Concurrency-safe run: sync LLM calls (reader, octen-fanout decompose) offloaded to
    threads so many runs overlap. latency_s is NOT reliable here (concurrent
    contention) — read arm latency from a sequential run instead."""
    run = ArmRun(task_id=task.id, arm=arm, repeat=repeat)
    ts = task.time_scope if time_pushdown else None
    t0 = time.time()
    subq_tokens = 0
    try:
        if arm == "octen-fanout":
            subs, u = await asyncio.to_thread(_decompose_sync, model, task.question, 8)
            subq_tokens = u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)
            st, et = time_bounds(ts)
            per = await octen.parallel_search(subs, count=3, start_time=st, end_time=et)
            hits, calls = rrf_fuse(list(per.values())), len(subs)
            run.n_queries = len(subs)
        elif arm.endswith("-agent"):
            # REAL multi-turn search agent (ReAct loop) on <engine>. The
            # model drives the search round by round; all LLM rounds' tokens are
            # the true "let the model loop" cost. Produces its own answer (no
            # separate reader).
            from .agent import agent_loop
            from .competitors import ADAPTERS
            base = arm[:-6]
            st, et = time_bounds(ts)
            if base == "octen":
                async def _search(q, k):
                    return await octen.search(q, count=k, start_time=st, end_time=et)
            else:
                _search = ADAPTERS[base]

            async def _complete(system, user):
                def _c():
                    llm = _worker_llm(model, 1200)
                    txt = llm.complete(system, user)
                    return txt, dict(getattr(llm, "last_usage", {}) or {})
                return await asyncio.to_thread(_c)

            res = await agent_loop(_search, _complete, task.question, max_rounds=8)
            run.api_calls = res["n_searches"]
            run.n_queries = res["n_searches"]
            run.downstream_tokens = res["agent_tokens"]
            run.search_time_s = res.get("search_time", 0.0)
            run.e2e_time_s = round(time.time() - t0, 3)
            run.latency_s = run.e2e_time_s
            run.retrieved_urls = res.get("urls", [])
            run.answer_entities = res["entities"]
            return run, res["evidence"]
        elif arm in COMPETITOR_ARMS:
            hits, calls, _s = await arm_competitor(arm, task.question, time_scope=ts)
        else:
            hits, calls, _s = await ARMS[arm](octen, task.question, time_scope=ts)
        # real searches: broad_search fans out to len(_s) sub-queries under 1 API call
        run.n_queries = len(_s) if isinstance(_s, list) else calls
        wall_search = round(time.time() - t0, 3)
        # search time = provider-reported server-side latency (fallback to wall-clock)
        rep = next((h.reported_latency_ms for h in hits if h.reported_latency_ms is not None), None)
        run.search_time_s = round(rep / 1000.0, 3) if rep is not None else wall_search
        run.latency_s = wall_search
        run.api_calls = calls
        run.retrieved_urls = [h.url for h in hits]
        if raw_dir is not None:
            _dump_raw(raw_dir, task.id, arm, repeat, hits)
        parsed, evidence, usage = await asyncio.to_thread(_read_sync, model, task, hits)
        run.e2e_time_s = round(time.time() - t0, 3)  # search + reader
        run.downstream_tokens = ((usage.get("prompt_tokens", 0)
                                  + usage.get("completion_tokens", 0))
                                 or (len(evidence) // 4 + 2000)) + subq_tokens
        if task.type == TaskType.T1_ENUM:
            run.answer_entities = [str(e) for e in parsed.get("entities", [])]
        elif task.type == TaskType.T2_MATRIX:
            run.answer_matrix = parsed.get("matrix", {})
        else:
            run.answer_text = str(parsed.get("answer", ""))
        return run, evidence
    except Exception as e:  # noqa: BLE001
        run.latency_s = round(time.time() - t0, 3)
        run.error = f"{type(e).__name__}: {e}"
        return run, ""


def _dump_raw(raw_dir: Path, task_id: str, arm: str, repeat: int, hits) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    with (raw_dir / f"{task_id}__{arm}__{repeat}.jsonl").open("w", encoding="utf-8") as f:
        for h in hits:
            f.write(json.dumps({
                "task_id": task_id, "sub_query": h.sub_query, "url": h.url,
                "title": h.title, "snippet": h.snippet,
                "published": h.published, "crawled": h.crawled,
            }, ensure_ascii=False) + "\n")


async def run_one(octen: OctenClient, reader_llm: LLM, subq_llm: LLM,
                  task: Task, arm: str, repeat: int,
                  time_pushdown: bool = True,
                  raw_dir: Path | None = None) -> tuple[ArmRun, str]:
    run = ArmRun(task_id=task.id, arm=arm, repeat=repeat)
    # identical for every arm — arm fairness is a hard requirement
    ts = task.time_scope if time_pushdown else None
    t0 = time.time()
    subq_tokens = 0
    try:
        if arm.endswith("-agent") or arm.endswith("-fan") or arm in COMPETITOR_ARMS:
            # agent/competitor arms only run on the concurrent path (which has
            # full handling); guard the sequential path so it never KeyErrors.
            raise RuntimeError(f"arm '{arm}' requires --concurrency > 1")
        if arm == "octen-fanout":
            hits, calls, _subs = await arm_a3(octen, subq_llm, task.question,
                                              time_scope=ts)
            # capture NOW — subq_llm may be the same object as reader_llm,
            # whose next call overwrites last_usage. Design contract: octen-fanout's
            # decomposition tokens count toward downstream cost (not api_calls).
            u = getattr(subq_llm, "last_usage", {}) or {}
            subq_tokens = u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)
        else:
            hits, calls, _subs = await ARMS[arm](octen, task.question,
                                                 time_scope=ts)
        run.latency_s = round(time.time() - t0, 3)
        run.api_calls = calls
        run.retrieved_urls = [h.url for h in hits]
        if raw_dir is not None:  # dumped pre-reader so a reader crash keeps the evidence
            _dump_raw(raw_dir, task.id, arm, repeat, hits)

        parsed, evidence = read_answer(reader_llm, task, hits)
        usage = getattr(reader_llm, "last_usage", {}) or {}
        run.downstream_tokens = ((
            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        ) or (len(evidence) // 4 + 2000)) + subq_tokens
        if task.type == TaskType.T1_ENUM:
            run.answer_entities = [str(e) for e in parsed.get("entities", [])]
        elif task.type == TaskType.T2_MATRIX:
            run.answer_matrix = parsed.get("matrix", {})
        else:
            run.answer_text = str(parsed.get("answer", ""))
        return run, evidence
    except Exception as e:  # noqa: BLE001 — record, don't crash the batch
        run.latency_s = round(time.time() - t0, 3)
        run.error = f"{type(e).__name__}: {e}"
        return run, ""


async def run_bench(
    tasks_path: str, out_dir: str,
    arms: list[str] = ("octen-search", "octen-broad-search", "octen-fanout"),
    repeats: int = 3,
    reader_model: str | None = None,
    time_pushdown: bool = True,
    dump_raw: bool = False,
    concurrency: int = 1,
) -> dict:
    tasks = [t for t in load_tasks(tasks_path) if t.type != TaskType.T3_SURVEY]
    errs = [e for t in tasks for e in t.validate()]
    if errs:
        raise ValueError("task validation failed:\n" + "\n".join(errs))

    octen = OctenClient()
    import os
    reader_llm = LLM(model=reader_model or os.environ.get("WIDESEARCH_READER_MODEL"))
    subq_llm = reader_llm  # octen-fanout decomposition uses the same fixed model

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = (out / "raw") if dump_raw else None
    grades: list[Grade] = []
    gpath = out / "grades.jsonl"
    gpath.write_text("", encoding="utf-8")  # incremental checkpoint (kill-safe)

    def _persist(g: Grade) -> None:
        grades.append(g)
        with gpath.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(g), ensure_ascii=False) + "\n")

    try:
        if concurrency > 1:
            model = reader_model or os.environ.get("WIDESEARCH_READER_MODEL")
            # PER-ARM concurrency: each search engine/arm gets its own cap, so N
            # arms run at up to concurrency*N total (each engine independently
            # throttled to `concurrency`).
            sems = {a: asyncio.Semaphore(concurrency) for a in arms}
            lock = asyncio.Lock()
            jobs = [(t, a, r) for t in tasks for a in arms for r in range(repeats)]

            async def _worker(job):
                task, arm, rep = job
                async with sems[arm]:
                    run, ev = await run_one_concurrent(
                        octen, model, task, arm, rep,
                        time_pushdown=time_pushdown, raw_dir=raw_dir)
                g = grade(task, run, ev)
                async with lock:
                    _persist(g)

            await asyncio.gather(*(_worker(j) for j in jobs))
        else:
            for task in tasks:
                for arm in arms:
                    for rep in range(repeats):
                        run, evidence = await run_one(
                            octen, reader_llm, subq_llm, task, arm, rep,
                            time_pushdown=time_pushdown, raw_dir=raw_dir)
                        _persist(grade(task, run, evidence))
    finally:
        await octen.aclose()

    report = build_report(tasks, grades, arms)
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_report(tasks: list[Task], grades: list[Grade], arms: list[str]) -> dict:
    def per_task(arm: str, metric: str) -> dict[str, float]:
        acc: dict[str, list[float]] = {}
        for g in grades:
            if g.arm == arm and "error" not in g.detail:
                acc.setdefault(g.task_id, []).append(getattr(g, metric))
        return {t: sum(v) / len(v) for t, v in acc.items() if v}

    quality_metric = "f1"  # T1/T2 both expose f1; T4 uses accuracy separately
    size_labels = {
        t.id: (t.set_size.value if hasattr(t.set_size, "value") else (t.set_size or "?"))
        for t in tasks}
    drift_labels = {t.id: t.term_drift for t in tasks}

    report: dict = {"arms": {}, "comparisons": [], "strata": {}}
    for arm in arms:
        q = per_task(arm, quality_metric)
        report["arms"][arm] = {
            "f1_mean": round(sum(q.values()) / len(q), 4) if q else 0.0,
            "api_calls_mean": _mean(per_task(arm, "api_calls")),
            "latency_s_mean": _mean(per_task(arm, "latency_s")),
            "downstream_tokens_mean": _mean(per_task(arm, "downstream_tokens")),
            "hallucinated_rate_mean": _mean(per_task(arm, "hallucinated_rate")),
            "source_diversity_mean": _mean(per_task(arm, "source_diversity")),
            "n_tasks": len(q),
        }
        report["strata"][arm] = {
            "f1_by_set_size": stratify(q, size_labels),
            "f1_by_term_drift": stratify(q, drift_labels),
        }
    for a, b in [("octen-search", "octen-broad-search"), ("octen-broad-search", "octen-fanout"), ("octen-search", "octen-fanout")]:
        if a in arms and b in arms:
            report["comparisons"].append(asdict(paired_compare(
                per_task(a, quality_metric), per_task(b, quality_metric),
                quality_metric, a, b)))
    # headline efficiency: coverage-per-call / per-second
    for arm in arms:
        s = report["arms"][arm]
        s["f1_per_call"] = round(s["f1_mean"] / s["api_calls_mean"], 4) if s["api_calls_mean"] else 0.0
        s["f1_per_second"] = round(s["f1_mean"] / s["latency_s_mean"], 4) if s["latency_s_mean"] else 0.0
    return report


def _mean(d: dict[str, float]) -> float:
    return round(sum(d.values()) / len(d), 4) if d else 0.0
