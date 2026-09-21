"""Async client for the three Octen retrieval primitives.

Conventions (confirmed against live API):
  - auth header: `x-api-key`
  - search results at `data.results[]`
  - ranked snippet in `highlight` field
  - `count` in [1, 100]

Endpoint paths are env-configurable (OCTEN_BASE_URL etc.) so the same code
runs against alternate base-URL deployments without edits.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

import httpx
from dataclasses import dataclass, field


@dataclass
class SearchHit:
    url: str
    title: str = ""
    snippet: str = ""
    published: Optional[str] = None
    crawled: Optional[str] = None
    sub_query: Optional[str] = None
    reported_latency_ms: Optional[float] = None  # provider-reported server-side latency
    raw: dict[str, Any] = field(default_factory=dict)

DEFAULT_BASE = os.environ.get("OCTEN_BASE_URL", "https://api.octen.ai")
# live paths verified 2026-07-21 (the former /v1/* defaults 404)
PATH_SEARCH = os.environ.get("OCTEN_PATH_SEARCH", "/search")
PATH_BROAD = os.environ.get("OCTEN_PATH_BROAD", "/broad-search")
PATH_EXTRACT = os.environ.get("OCTEN_PATH_EXTRACT", "/extract")



RETRYABLE = {429, 500, 502, 503, 504}


def _highlight_tokens(explicit: Optional[int] = None) -> int:
    """Per-snippet highlight budget, uniform across ALL retrieval primitives
    so the window budget stays comparable across arms. Explicit argument >
    env WIDESEARCH_HIGHLIGHT_TOKENS > 512."""
    if explicit is not None:
        return explicit
    return int(os.environ.get("WIDESEARCH_HIGHLIGHT_TOKENS", "512"))


class OctenClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE,
        timeout: float = 45.0,
        max_retries: int = 3,
        max_concurrency: int = 12,
    ) -> None:
        self.api_key = api_key or os.environ["OCTEN_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.n_requests = 0
        self._sem = asyncio.Semaphore(max_concurrency)
        self._client = httpx.AsyncClient(
            timeout=timeout, headers={"x-api-key": self.api_key}
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ http
    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        last: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            async with self._sem:
                # Counted per attempt, not per call. api_calls reports the
                # billed unit (one broad_search = 1); a retry is invisible
                # there, so report what actually went over the wire too.
                self.n_requests += 1
                try:
                    resp = await self._client.post(url, json=payload)
                except httpx.TransportError as e:  # network flake -> retry
                    last = e
                    await asyncio.sleep(min(2**attempt, 8))
                    continue
            if resp.status_code in RETRYABLE:
                last = RuntimeError(f"{resp.status_code} from {path}")
                await asyncio.sleep(min(2**attempt, 8))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"octen request failed after retries: {last}")

    # --------------------------------------------------------------- parsing
    _URL_KEYS = ("url", "link", "href")
    _SNIPPET_KEYS = ("highlight", "snippet", "summary", "content", "text")

    @classmethod
    def _looks_like_hit(cls, d: Any) -> bool:
        return isinstance(d, dict) and any(k in d and isinstance(d[k], str) for k in cls._URL_KEYS)

    @classmethod
    def _to_hit(cls, r: dict, sub_query: Optional[str] = None) -> SearchHit:
        url = next((r[k] for k in cls._URL_KEYS if isinstance(r.get(k), str)), "")
        snippet = ""
        for k in cls._SNIPPET_KEYS:
            v = r.get(k)
            if isinstance(v, str) and v:
                snippet = v
                break
            if isinstance(v, list) and v:  # highlight may be a list of strings/objects
                snippet = " ".join(x if isinstance(x, str) else str(x.get("text", "")) for x in v)
                break
        return SearchHit(
            url=url, title=r.get("title", ""), snippet=snippet,
            # live API field names are time_published/time_last_crawled;
            # keep the older keys as fallbacks for alternate deployments
            published=r.get("time_published") or r.get("published") or r.get("published_at"),
            crawled=r.get("time_last_crawled") or r.get("crawled") or r.get("last_crawled"),
            sub_query=sub_query, raw=r,
        )

    @classmethod
    def _parse_hits(cls, data: Any, sub_query: Optional[str] = None) -> list[SearchHit]:
        """Adaptive: recursively locate hit-lists anywhere in the response and
        carry sub-query labels found on enclosing group objects. Eliminates
        schema guessing — tolerates data.results[], results[], data.groups[]
        [{sub_query, results}], or any nesting of those."""
        hits: list[SearchHit] = []

        def walk(node: Any, label: Optional[str]) -> None:
            if isinstance(node, list):
                if node and all(cls._looks_like_hit(x) for x in node):
                    hits.extend(cls._to_hit(x, label) for x in node)
                else:
                    for x in node:
                        walk(x, label)
            elif isinstance(node, dict):
                new_label = label
                for lk in ("sub_query", "subquery", "query"):
                    if isinstance(node.get(lk), str) and not cls._looks_like_hit(node):
                        new_label = node[lk]
                        break
                for v in node.values():
                    walk(v, new_label)

        walk(data, sub_query)
        # de-dup while preserving order (a URL may appear under multiple keys)
        seen, out = set(), []
        for h in hits:
            k = (h.url, h.sub_query)
            if h.url and k not in seen:
                seen.add(k)
                out.append(h)
        return out

    # ----------------------------------------------------------------- tools
    async def search(
        self,
        query: str,
        count: int = 5,
        include_domains: Optional[list[str]] = None,
        include_text: Optional[list[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        time_basis: str = "published",
        highlight_tokens: Optional[int] = None,
    ) -> list[SearchHit]:
        # NOTE: no `time_range` here — per docs it is a RELATIVE window enum
        # (day|week|month|year); the old code passed "2025" and got a proper
        # 400. Absolute windows use start_time/end_time (ISO 8601) + time_basis,
        # which also take precedence over time_range if both are given.
        payload: dict[str, Any] = {
            "query": query[:500],
            "count": max(1, min(count, 100)),
            "highlight": {"enable": True, "max_tokens": _highlight_tokens(highlight_tokens)},
        }
        if include_domains:
            payload["include_domains"] = include_domains
        if include_text:
            payload["include_text"] = include_text[:5]
        if start_time or end_time:
            payload["time_basis"] = time_basis
            if start_time:
                payload["start_time"] = start_time
            if end_time:
                payload["end_time"] = end_time
        data = await self._post(PATH_SEARCH, payload)
        hits = self._parse_hits(data)
        lat = (data.get("meta") or {}).get("latency")
        for h in hits:
            h.reported_latency_ms = lat
        return hits

    async def broad_search(
        self,
        query: str,
        max_queries: int = 8,
        count: int = 3,
        include_domains: Optional[list[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        time_basis: str = "published",
    ) -> list[SearchHit]:
        """Server-side multi-angle fan-out. Use when the ANGLES are unknown.

        When the entity list IS known, prefer `parallel_search` below —
        client-side decomposition keeps sub-queries exact instead of guessed.
        """
        # Per-sub-query options MUST live under search_options — the API
        # silently ignores unknown top-level fields (probed: top-level count/
        # per_query_count/max_results/top_k all no-ops; search_options.count
        # takes effect exactly, per-sub-query semantics).
        n = max(1, min(count, 100))
        opts: dict[str, Any] = {
            "count": n,
            "highlight": {"enable": True, "max_tokens": _highlight_tokens()},
        }
        if include_domains:
            opts["include_domains"] = include_domains
        if start_time or end_time:
            opts["time_basis"] = time_basis
            if start_time:
                opts["start_time"] = start_time
            if end_time:
                opts["end_time"] = end_time
        payload: dict[str, Any] = {
            "query": query[:500],
            "max_queries": max(1, min(max_queries, 30)),
            "search_options": opts,
        }
        # Anti-degenerate guard: under batch concurrency the API occasionally
        # returns HTTP 200 with an empty/partial body (0 hits, or hits with no
        # per-sub-query grouping), which silently collapses a wide fan-out to a
        # single "query" downstream and disproportionately handicaps octen-broad-search. Retry
        # a few times until we get a genuine multi-sub-query response; only then
        # accept a <2 result (some narrow queries legitimately fan out to 1).
        data = await self._post(PATH_BROAD, payload)
        hits = self._parse_hits(data)
        if max_queries >= 2:
            for _ in range(3):
                if hits and len({h.sub_query for h in hits if h.sub_query}) >= 2:
                    break
                await asyncio.sleep(1.0)
                data = await self._post(PATH_BROAD, payload)
                hits = self._parse_hits(data)
        # Belt-and-braces: the server once ignored the count contract entirely
        # (see search_options note above); never hand more than `count` hits
        # per sub-query downstream even if it drifts again.
        taken: dict[Optional[str], int] = {}
        capped: list[SearchHit] = []
        for h in hits:
            if taken.get(h.sub_query, 0) < n:
                taken[h.sub_query] = taken.get(h.sub_query, 0) + 1
                capped.append(h)
        lat = (data.get("meta") or {}).get("latency")
        for h in capped:
            h.reported_latency_ms = lat
        return capped

    async def parallel_search(
        self,
        queries: list[str],
        count: int = 3,
        include_domains: Optional[list[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        time_basis: str = "published",
    ) -> dict[str, list[SearchHit]]:
        """Client-side fan-out: exact sub-queries, one per known entity.

        This is the VERIFY-hop workhorse. Unlike broad_search we control the
        decomposition, so 'Organised Crime Index 2023 {country}' stays exact
        for every country instead of being re-guessed server-side.
        """
        async def one(q: str) -> tuple[str, list[SearchHit]]:
            hits = await self.search(
                q, count=count, include_domains=include_domains,
                start_time=start_time, end_time=end_time, time_basis=time_basis)
            for h in hits:
                h.sub_query = q
            return q, hits

        pairs = await asyncio.gather(*(one(q) for q in queries))
        return dict(pairs)

    async def extract(
        self,
        urls: list[str],
        full_content: bool = True,
        query: Optional[str] = None,
        fmt: str = "text",
        max_age_seconds: int = 86400,
    ) -> list[dict[str, Any]]:
        """Evidence-grade fetch.

        full_content=True is the default for verification because highlight
        mode ranks prose above numbers on data-panel pages — the exact
        failure observed on score-card sites. Pass query only for prose pages
        where a ranked excerpt is genuinely sufficient.
        """
        payload: dict[str, Any] = {
            "urls": urls[:20],
            "format": fmt,
            "max_age_seconds": max_age_seconds,
        }
        if not full_content and query:
            payload["query"] = query[:500]
        data = await self._post(PATH_EXTRACT, payload)
        return (data.get("data") or {}).get("results", []) or data.get("results", [])
