"""Competitor search adapters — Exa / Tavily / Brave / Parallel.

Each returns a list[SearchHit] with the same shape as OctenClient.search, so a
competitor cross-arm study can swap the single-search retrieval layer per provider
while keeping reader/prompt/grading fixed. Endpoints/fields verified against
official docs 2026-07-24.

Perplexity is an answer engine (returns a synthesized answer, not a ranked hit
list), so it is NOT a drop-in retrieval arm — it belongs in a separate
full-pipeline comparison, noted but not implemented here.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from .octen_client import SearchHit

_TIMEOUT = 45.0


async def exa_search(query: str, count: int = 10) -> list[SearchHit]:
    key = os.environ["EXA_API_KEY"]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://api.exa.ai/search",
                         headers={"x-api-key": key, "Content-Type": "application/json"},
                         json={"query": query[:500], "numResults": max(1, min(count, 100)),
                               "contents": {"highlights": True}})
        r.raise_for_status()
        data = r.json()
    out = []
    for h in data.get("results", []):
        hl = h.get("highlights") or []
        snip = " ".join(hl) if isinstance(hl, list) else (h.get("text") or "")
        out.append(SearchHit(url=h.get("url", ""), title=h.get("title", ""),
                             snippet=snip or (h.get("text") or "")[:2000],
                             published=h.get("publishedDate"), raw=h))
    return [h for h in out if h.url]


async def tavily_search(query: str, count: int = 10) -> list[SearchHit]:
    key = os.environ["TAVILY_API_KEY"]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://api.tavily.com/search",
                         headers={"Authorization": f"Bearer {key}",
                                  "Content-Type": "application/json"},
                         json={"query": query[:400], "max_results": max(1, min(count, 20)),
                               "search_depth": "advanced"})
        r.raise_for_status()
        data = r.json()
    out = [SearchHit(url=h.get("url", ""), title=h.get("title", ""),
                     snippet=h.get("content", ""), raw=h)
           for h in data.get("results", [])]
    return [h for h in out if h.url]


async def brave_search(query: str, count: int = 10) -> list[SearchHit]:
    key = os.environ["BRAVE_API_KEY"]
    # Brave's `q` caps at ~400 chars AND ~50 words; long enumeration questions
    # 422 otherwise. Truncate to the limit (a Brave limitation, noted in report).
    q = " ".join(query.split()[:50])[:390]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.get("https://api.search.brave.com/res/v1/web/search",
                        headers={"X-Subscription-Token": key,
                                 "Accept": "application/json"},
                        params={"q": q, "count": max(1, min(count, 20)),
                                "extra_snippets": "true"})
        r.raise_for_status()
        data = r.json()
    out = []
    for h in (data.get("web", {}) or {}).get("results", []):
        extra = h.get("extra_snippets") or []
        snip = h.get("description", "")
        if extra:
            snip = snip + " " + " ".join(extra)
        out.append(SearchHit(url=h.get("url", ""), title=h.get("title", ""),
                             snippet=snip, raw=h))
    return [h for h in out if h.url]


async def exa_instant_search(query: str, count: int = 10) -> list[SearchHit]:
    """Exa 'instant' tier (type=instant, highlights) — per Octen search-eval repo."""
    key = os.environ["EXA_API_KEY"]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://api.exa.ai/search",
                         headers={"x-api-key": key, "Content-Type": "application/json"},
                         json={"query": query[:500], "numResults": max(1, min(count, 100)),
                               "type": "instant",
                               "contents": {"highlights": True}})
        r.raise_for_status()
        data = r.json()
    lat = data.get("searchTime")
    out = [SearchHit(url=h.get("url", ""), title=h.get("title") or "",
                     snippet=(" … ".join(h.get("highlights") or []) or h.get("text") or ""),
                     published=h.get("publishedDate"), reported_latency_ms=lat, raw=h)
           for h in data.get("results", [])]
    return [h for h in out if h.url]


async def tavily_ultrafast_search(query: str, count: int = 10) -> list[SearchHit]:
    """Tavily 'ultra-fast' search depth — per Octen search-eval repo."""
    key = os.environ["TAVILY_API_KEY"]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://api.tavily.com/search",
                         json={"api_key": key, "query": query[:400],
                               "max_results": min(max(count * 2, count + 5), 20),
                               "search_depth": "ultra-fast"})
        r.raise_for_status()
        data = r.json()
    rt = data.get("response_time")
    lat = float(rt) * 1000 if isinstance(rt, (int, float)) else None
    out = [SearchHit(url=h.get("url", ""), title=h.get("title", ""),
                     snippet=(h.get("content") or ""),
                     published=h.get("published_date"), reported_latency_ms=lat, raw=h)
           for h in data.get("results", [])[:count]]
    return [h for h in out if h.url]


async def parallel_turbo_search(query: str, count: int = 10) -> list[SearchHit]:
    """Parallel 'turbo' mode — per Octen search-eval repo."""
    key = os.environ["PARALLEL_API_KEY"]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post("https://api.parallel.ai/v1/search",
                         headers={"x-api-key": key, "Content-Type": "application/json"},
                         json={"objective": query[:400], "search_queries": [query[:400]],
                               "mode": "turbo",
                               "advanced_settings": {"max_results": max(1, min(count, 40))}})
        r.raise_for_status()
        data = r.json()
    out = [SearchHit(url=h.get("url", ""), title=h.get("title") or "",
                     snippet=(" … ".join(h.get("excerpts") or [])),
                     published=h.get("publish_date"), raw=h)
           for h in data.get("results", [])[:count]]
    return [h for h in out if h.url]


ADAPTERS = {"exa": exa_search, "tavily": tavily_search, "brave": brave_search,
            "exa-instant": exa_instant_search, "tavily-ultrafast": tavily_ultrafast_search,
            "parallel-turbo": parallel_turbo_search}


async def smoke(query: str = "commercial web search API for LLM agents") -> dict:
    import asyncio
    results = {}
    for name, fn in ADAPTERS.items():
        try:
            hits = await fn(query, count=5)
            results[name] = {
                "hits": len(hits),
                "has_snippet": bool(hits and hits[0].snippet),
                "sample_url": hits[0].url if hits else None,
            }
        except Exception as e:  # noqa: BLE001
            results[name] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
    return results
