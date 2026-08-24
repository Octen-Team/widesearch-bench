"""`widesearch doctor` — one-shot preflight so a local run needs zero
round-trips: env check for every key the published arms need, one live probe
per search engine (Octen search + broad_search, Exa, Tavily, Parallel), and a
reader completion + JSON-mode probe.

Every check prints PASS/FAIL with an actionable next step; exit code 0 only
when the harness is fully runnable.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

CHECKS: list[tuple[str, bool, str]] = []  # (name, ok, note)


def _rec(name: str, ok: bool, note: str = "") -> None:
    CHECKS.append((name, ok, note))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {note}" if note else ""))


def _env(name: str, required: bool = True) -> bool:
    ok = bool(os.environ.get(name))
    _rec(f"env {name}", ok or not required,
         "set" if ok else ("REQUIRED — export it" if required else "optional, unset"))
    return ok


async def _check_octen() -> None:
    from .octen_client import OctenClient
    octen = OctenClient()
    try:
        try:
            hits = await octen.search("web search api", count=3)
            _rec("octen search", len(hits) > 0,
                 f"{len(hits)} hits; sample fields: "
                 f"{sorted(list(hits[0].raw.keys()))[:8] if hits else 'n/a'}")
            _rec("octen search snippets", bool(hits and hits[0].snippet),
                 "highlight/snippet extraction works" if hits and hits[0].snippet
                 else "hits lack snippets — check highlight param support")
        except Exception as e:  # noqa: BLE001
            _rec("octen search", False, f"{type(e).__name__}: {str(e)[:160]}")
            return
        try:
            bhits = await octen.broad_search("compare llm search api pricing latency", max_queries=4, count=2)
            labeled = sum(1 for h in bhits if h.sub_query)
            _rec("octen broad_search", len(bhits) > 0, f"{len(bhits)} hits")
            _rec("broad sub_query labels", labeled > 0,
                 f"{labeled}/{len(bhits)} labeled — marginal-coverage curve available"
                 if labeled else "no sub-query labels found in response; octen-broad-search still "
                 "runs, but per-sub-query attribution will be empty")
        except Exception as e:  # noqa: BLE001
            _rec("octen broad_search", False, f"{type(e).__name__}: {str(e)[:160]}")
    finally:
        await octen.aclose()


def _check_openrouter() -> None:
    import httpx
    key = os.environ.get("OPENROUTER_API_KEY", "")
    base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    try:
        r = httpx.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"},
                      timeout=30.0)
        r.raise_for_status()
        ids = [m.get("id", "") for m in r.json().get("data", [])]
        _rec("openrouter /models", True, f"{len(ids)} models visible")
    except Exception as e:  # noqa: BLE001
        _rec("openrouter /models", False, f"{type(e).__name__}: {str(e)[:160]}")
        return

    configured = os.environ.get("WIDESEARCH_READER_MODEL", "")
    if configured.startswith("openrouter/"):
        slug = configured.removeprefix("openrouter/")
        _rec("configured slug exists", slug in ids,
             slug if slug in ids else f"'{slug}' not in OpenRouter model list")
        chosen = slug if slug in ids else None
    else:
        # reader is not an OpenRouter model (e.g. openai:*); skip the completion probe
        chosen = None
    if not chosen:
        return

    # tiny completion + JSON contract probe through the real wrapper
    try:
        from .llm import make_llm
        llm = make_llm(f"openrouter/{chosen}", max_tokens=200)
        out = llm.complete_json(
            "Return ONLY JSON, no prose, no fences.",
            'Return exactly {"ok": true}')
        _rec("openrouter completion + JSON", out.get("ok") is True,
             f"usage={llm.last_usage or 'not reported'}")
    except Exception as e:  # noqa: BLE001
        _rec("openrouter completion + JSON", False, f"{type(e).__name__}: {str(e)[:160]}")


async def _check_competitors() -> None:
    """One cheap search per competitor tier, so a missing or wrong key surfaces
    here instead of 313 questions into a run. These are the exact adapters the
    published `*-agent` arms use (arm name minus the `-agent` suffix)."""
    from .competitors import ADAPTERS
    for name, env in (("exa-instant", "EXA_API_KEY"),
                      ("tavily-ultrafast", "TAVILY_API_KEY"),
                      ("parallel-turbo", "PARALLEL_API_KEY")):
        if not os.environ.get(env):
            continue
        try:
            hits = await ADAPTERS[name]("web search api for llm agents", count=3)
            _rec(f"{name} search", len(hits) > 0, f"{len(hits)} hits")
        except Exception as e:  # noqa: BLE001
            _rec(f"{name} search", False, f"{type(e).__name__}: {str(e)[:160]}")


def _check_openai_reader() -> None:
    """Probe the reader through the real wrapper when it is an openai:* model."""
    configured = os.environ.get("WIDESEARCH_READER_MODEL", "")
    if not configured.startswith("openai:"):
        return
    try:
        from .llm import make_llm
        llm = make_llm(configured, max_tokens=200)
        out = llm.complete_json("Return ONLY JSON, no prose, no fences.",
                                'Return exactly {"ok": true}')
        _rec("openai reader + JSON", out.get("ok") is True,
             f"{configured}; usage={llm.last_usage or 'not reported'}")
    except Exception as e:  # noqa: BLE001
        _rec("openai reader + JSON", False, f"{type(e).__name__}: {str(e)[:160]}")


def doctor() -> int:
    print("widesearch doctor\n-- env --")
    # required for the four published arms + the reader
    have_octen = _env("OCTEN_API_KEY")
    _env("EXA_API_KEY")
    _env("TAVILY_API_KEY")
    _env("PARALLEL_API_KEY")
    _env("OPENAI_API_KEY")
    _env("WIDESEARCH_READER_MODEL")
    # alternative reader routing / unused arm
    have_or = _env("OPENROUTER_API_KEY", required=False)
    _env("BRAVE_API_KEY", required=False)

    if have_octen:
        print("-- octen --")
        asyncio.run(_check_octen())
    print("-- competitor engines --")
    asyncio.run(_check_competitors())
    print("-- reader --")
    _check_openai_reader()
    if have_or:
        _check_openrouter()

    failed = [c for c in CHECKS if not c[1]]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("Fix the FAIL items above, then rerun `widesearch doctor`.")
    else:
        print("All green — reproduce the published run with:\n"
              "  widesearch run data/tasks.jsonl --out my-run --repeats 1")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(doctor())
