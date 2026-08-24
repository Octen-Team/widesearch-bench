"""A REAL multi-turn search agent (ReAct-style loop).

Unlike the fan-out arm (one-shot decompose then parallel search), here the model
drives the search itself, round by round: it issues one query, reads the
results, then decides its NEXT query or stops and answers. The running
transcript (all prior queries + results) is fed back each round, so token cost
GROWS per round — this is exactly the "intermediate token of letting the model
loop the search tool" that fan-out under-counts.

Metrics captured: total LLM tokens across ALL rounds (agent_tokens), number of
search calls issued, and the final answer for F1/hallucination grading.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Awaitable, Callable

from .octen_client import SearchHit

AGENT_SYS = """\
You are a web-search research agent answering an ENUMERATION question. Work in a
loop. Each turn output EXACTLY ONE action:
  SEARCH: <a focused query>        (to gather more evidence)
  ANSWER: {"entities": ["...", ...]}   (when your searches support the answer)
Use MULTIPLE searches with different angles to cover the set before answering.
You have at most __MAXROUNDS__ searches; when in doubt, search more.

STRICT GROUNDING RULES (identical to the non-agent arms, for fair comparison):
- Use ONLY the evidence returned by YOUR searches. Do NOT use prior knowledge.
- If an entity is not supported by your search results, OMIT it. An incomplete
  honest answer scores better than a padded one."""


def _render(hits: list[SearchHit], k: int = 5) -> str:
    return "\n".join(f"- {h.title} | {h.snippet[:200]}" for h in hits[:k]) or "(no results)"


async def agent_loop(search_fn: Callable[[str, int], Awaitable[list[SearchHit]]],
                     complete_threaded: Callable[[str, str], Awaitable[tuple[str, dict]]],
                     question: str, max_rounds: int = 8, per_search: int = 5) -> dict:
    """search_fn(query, k) -> hits (async). complete_threaded(system, user) ->
    (text, usage) runs the sync LLM off-thread. Returns dict with entities,
    agent_tokens, n_searches, evidence."""
    sys = AGENT_SYS.replace("__MAXROUNDS__", str(max_rounds))
    transcript = f"QUESTION: {question}\n"
    total_tokens = 0
    n_searches = 0
    search_time = 0.0
    evidence_parts: list[str] = []
    urls: list[str] = []
    entities: list[str] = []

    for _ in range(max_rounds + 2):  # a couple extra turns to allow a final answer
        text, usage = await complete_threaded(sys, transcript + "\nYour next action:")
        total_tokens += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        m_ans = re.search(r"ANSWER:\s*(\{.*)", text, re.S)
        m_srch = re.search(r"SEARCH:\s*(.+)", text)
        if m_ans:
            try:
                j = json.loads(re.search(r"\{.*\}", m_ans.group(1), re.S).group(0))
                entities = [str(e) for e in j.get("entities", [])]
            except Exception:  # noqa: BLE001
                entities = []
            break
        if m_srch and n_searches < max_rounds:
            query = m_srch.group(1).strip().strip('"')
            _s = time.time()
            try:
                hits = await search_fn(query, per_search)
            except Exception:  # noqa: BLE001
                hits = []
            wall = time.time() - _s
            # search time = provider-reported latency; fall back to wall-clock
            # if the provider doesn't report it (e.g. Parallel).
            rep = hits[0].reported_latency_ms if hits and hits[0].reported_latency_ms is not None else None
            search_time += (rep / 1000.0) if rep is not None else wall
            n_searches += 1
            urls.extend(h.url for h in hits if h.url)
            evidence_parts.append(_render(hits))
            transcript += f"\nSEARCH: {query}\nRESULTS:\n{_render(hits)}\n"
        else:
            # no valid action, or search budget exhausted -> force an answer next
            transcript += "\n(You have used all searches. Output ANSWER now.)\n"
            if n_searches >= max_rounds:
                # one more turn to extract the answer
                text, usage = await complete_threaded(
                    sys, transcript + '\nOutput ONLY: ANSWER: {"entities": [...]}')
                total_tokens += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                m = re.search(r"\{.*\}", text, re.S)
                if m:
                    try:
                        entities = [str(e) for e in json.loads(m.group(0)).get("entities", [])]
                    except Exception:  # noqa: BLE001
                        pass
                break
    return {"entities": entities, "agent_tokens": total_tokens,
            "n_searches": n_searches, "search_time": round(search_time, 3),
            "urls": urls, "evidence": "\n".join(evidence_parts)}
