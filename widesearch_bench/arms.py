"""Retrieval configurations consumed by the runner.

octen-search: single octen search (count=10)
octen-broad-search: octen broad_search single call (max_queries=8)
octen-fanout: client-side fan-out: LLM writes 8 sub-queries ->
    8 concurrent searches -> RRF fusion

Backend, excerpt length, time-filter support and agent answering protocol can
vary. Equal maximum result counts do not imply equal evidence or actual work.

Each arm returns (hits, api_calls, subqueries_used). Latency is measured by
the runner around the whole retrieval phase.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from .llm import LLM
from .octen_client import OctenClient, SearchHit

RRF_K = 60


def time_bounds(time_scope: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """task.time_scope ("2025") -> ISO published-time window pushed down to
    retrieval. Applied identically to all arms — arm fairness is a hard
    requirement. None -> no filter."""
    if not time_scope:
        return None, None
    y = int(time_scope)
    return f"{y}-01-01T00:00:00Z", f"{y + 1}-01-01T00:00:00Z"


def rrf_fuse(ranked_lists: list[list[SearchHit]], top_n: int = 24) -> list[SearchHit]:
    scores: dict[str, float] = {}
    best: dict[str, SearchHit] = {}
    for lst in ranked_lists:
        for rank, hit in enumerate(lst):
            key = hit.url.rstrip("/").lower()
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            best.setdefault(key, hit)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [best[k] for k, _ in ordered[:top_n]]


SUBQUERY_SYSTEM = """\
You decompose a wide research question into exactly {n} diverse web search
sub-queries (3-8 words each). Cover distinct angles/entities; avoid rephrasing
the same angle twice; keep the original language of the question.
Return ONLY a JSON array of {n} strings."""


async def arm_a1(octen: OctenClient, question: str,
                 time_scope: Optional[str] = None) -> tuple[list[SearchHit], int, list[str]]:
    st, et = time_bounds(time_scope)
    hits = await octen.search(question, count=10, start_time=st, end_time=et)
    return hits, 1, [question]


async def arm_competitor(provider: str, question: str,
                         time_scope: Optional[str] = None) -> tuple[list[SearchHit], int, list[str]]:
    """Competitor octen-search arm: a single search on Exa/Tavily/Brave (count=10), same
    reader/grading downstream — directly comparable to Octen octen-search. Time filtering
    is not pushed down (adapters don't uniformly support it); time_scope is
    ignored here and this is noted in the competitor report."""
    from .competitors import ADAPTERS
    hits = await ADAPTERS[provider](question, count=10)
    return hits, 1, [question]


async def arm_a2(octen: OctenClient, question: str,
                 max_queries: int = 8,
                 time_scope: Optional[str] = None) -> tuple[list[SearchHit], int, list[str]]:
    st, et = time_bounds(time_scope)
    # Match the default maximum hits per search. Providers can return fewer
    # hits, and agents can stop early, so observed evidence volumes vary.
    per = int(os.environ.get("OCTEN_BROAD_COUNT", "5"))
    hits = await octen.broad_search(question, max_queries=max_queries, count=per,
                                    start_time=st, end_time=et)
    subs = sorted({h.sub_query for h in hits if h.sub_query})
    return hits, 1, subs or [question]


def a3_decompose(llm: LLM, question: str, n_sub: int = 8) -> list[str]:
    """Sync LLM sub-query decomposition (extracted so the concurrent runner can
    offload it to a thread)."""
    subs: list[Any] = llm.complete_json(
        SUBQUERY_SYSTEM.format(n=n_sub), f"QUESTION:\n{question}")
    return [str(s) for s in subs][:n_sub] or [question]


async def arm_a3(octen: OctenClient, llm: LLM, question: str,
                 n_sub: int = 8,
                 time_scope: Optional[str] = None) -> tuple[list[SearchHit], int, list[str]]:
    subs = a3_decompose(llm, question, n_sub)
    st, et = time_bounds(time_scope)
    per = await octen.parallel_search(subs, count=3, start_time=st, end_time=et)
    fused = rrf_fuse(list(per.values()))
    # api_calls: n_sub searches + 1 LLM decomposition call (counted separately
    # by the runner in downstream_tokens; retrieval calls only here)
    return fused, len(subs), subs


ARMS = {"octen-search": arm_a1, "octen-broad-search": arm_a2, "octen-fanout": arm_a3}
