# WideSearch-Bench

**A benchmark that isolates *how retrieval width is delivered* for multi-entity questions — one server-side broad-search call vs. a model-driven multi-turn agent loop — holding the answering model, prompt, grading, and number of real searches fixed.**

> **Headline (n=313, rigor-audited):** For multi-entity enumeration, a single `broad_search` delivers **answer quality on par with the strongest agent-loop competitors** while being **≈4.9× faster end-to-end, using ≈2.4× fewer tokens**, at a **search-API cost tied for cheapest (~7× below Exa/Tavily)**. The decisive, unambiguous advantage is **cost**, not quality.

---

## Results (n=313, same `gpt-5-mini` reader for every configuration; single consistent full run)

| Configuration | Entity-F1 | Real queries | End-to-end (s) | Tokens | Search $/1k q † |
|---|---|---|---|---|---|
| **Octen — one broad_search** | **0.548** | 8.0 | **8.4** | **8,043** | 8.0 |
| Parallel-turbo — agent loop | 0.533 | 7.8 | 41.1 | 19,327 | **7.8** |
| Exa-instant — agent loop | 0.521 | 7.7 | 40.5 | 19,679 | 54.1 |
| Tavily-ultrafast — agent loop | 0.505 | 7.9 | 46.1 | 20,088 | 62.8 |

**Paired significance (F1, bootstrap 95% CI, vs broad_search):** n.s. vs Parallel (Δ=+0.015) and Exa (Δ=+0.028); significant over Tavily (Δ=+0.044, Holm). broad_search's mean F1 leads all four, but is statistically tied with the two strongest competitors.

† **Search-API cost per 1k questions** = real queries × each provider's current per-search price: Octen **$1/1k** ([docs](https://docs.octen.ai/overview/pricing), 80% off from $5; broad_search billed per sub-query), Exa-instant $7/1k, Tavily basic $8/1k (1 credit × $0.008), Parallel turbo $1/1k. Octen broad ($8/1k) ties Parallel-turbo ($7.8) and is ~7× cheaper than Exa/Tavily. **Tokens** are total downstream LLM consumption (broad_search uses ≈2.4× fewer than the agent loops).

On the **strict / non-pooled** gold the ordering is unchanged. **Bottom line: quality parity with the top competitors, at a fraction of the cost.**

1,252 runs, **0 errors**, single consistent full run. Hallucination (dual-source + dual-model *confirmed-wrong*) is 1–2% for every configuration (Octen 1.1%, Exa 1.6%, Parallel 1.7%, Tavily 2.0%) with **no significant difference**.

![Results](figures/widesearch_results.png)

---

## What this benchmark is

- **313 multi-entity T1 enumeration questions** (English + Chinese), each with an objective, closed answer set.
- Each question is **verified to require retrieval width** by a mechanical *fake-fanout* filter (no single page covers the answer).
- Graded by a **zero-LLM mechanical Entity-F1** (Unicode/alias/version-aware matching) — no judge model in the scoring loop.
- Four configurations vary **only the width-delivery mechanism**; the answering model (`gpt-5-mini`), grounding prompt, grading, and real-search budget (≈8) are held fixed.

## Files

| Path | What |
|---|---|
| `data/tasks.jsonl` | **Primary eval set** (313 tasks, pooled/expanded gold) |
| `data/tasks_strict.jsonl` | Same tasks, **strict precision gold** (no pooled additions) — use to avoid pooling bias |
| `results/grades_expanded.jsonl` | **Per-run traces + scores** on the pooled gold (4 arms × 313) — the reported numbers |
| `results/RESULTS.md` | **Canonical results** (table, significance, cost) |
| `results/pooling_verdicts.jsonl` | Dual-source + dual-model pooling verdicts |
| `results/cases.jsonl` | Per-case: question · gold · every arm's answer + score |

## Repository layout

```
data/       tasks.jsonl  tasks_strict.jsonl  aliases/
            DATASHEET.md  DATASET_STATS.md
results/    grades_expanded.jsonl  grades_strict.jsonl
            cases.jsonl  pooling_verdicts.jsonl
            RESULTS.md  PAIRED_STATS.md  HALLUCINATION_STATS.md
figures/    widesearch_results.{png,svg}        ← canonical figure source
tools/      make_figure.py  make_cases.py  paired_stats.py
            regrade.py  dataset_stats.py
tests/      harness unit tests (pytest)
widesearch_bench/   the harness (search clients, agent loop, reader, grader)
.env.example        template for the five required API keys
```

`grades_expanded.jsonl` and `grades_strict.jsonl` are the same 1,252 runs scored
against the pooled and the strict gold respectively; every reported number comes
from one of the two. `cases.jsonl` is the per-question view of the same runs
(regenerate with `python tools/make_cases.py`).

**Naming convention.** Machine-read artifacts are `lower_snake.jsonl`; human-read reports are `SCREAMING_SNAKE.md`. Gold variants use a suffix (`_strict`). Arm identifiers use hyphens (`octen-broad-search`).

## Reproduce

**1. Install.** Python ≥ 3.10.

```bash
pip install -e .            # harness + CLI
pip install -e ".[analysis]"  # adds numpy/matplotlib for tools/
```

**2. Keys.** Copy `.env.example` to `.env` and fill in five keys — one per
retrieval arm plus the reader:

| Variable | Used by |
|---|---|
| `OCTEN_API_KEY` | `octen-broad-search` |
| `EXA_API_KEY` | `exa-instant-agent` |
| `TAVILY_API_KEY` | `tavily-ultrafast-agent` |
| `PARALLEL_API_KEY` | `parallel-turbo-agent` |
| `OPENAI_API_KEY` | the answering model |
| `WIDESEARCH_READER_MODEL` | set to `openai:gpt-5-mini` |

**3. Preflight.** `widesearch doctor` checks every key and makes one live call per
engine, so a bad key fails in seconds rather than 313 questions into a run.

```bash
set -a; source .env; set +a
widesearch doctor
```

**4. Run.**

```bash
widesearch run data/tasks.jsonl --out my-run \
  --arms octen-broad-search,exa-instant-agent,tavily-ultrafast-agent,parallel-turbo-agent \
  --repeats 1 --concurrency 5
```

Those are the defaults, so `widesearch run data/tasks.jsonl --out my-run` is
equivalent. `--concurrency` must stay above 1: the three agent arms only run on
the concurrent path, and the published latencies were measured at 5, so they
include the same contention.

**Verify against the published numbers without re-running.** `paired_stats.py`
recomputes the significance tables from the shipped scores; `regrade.py` goes
further and re-scores every run from the raw answers and the gold, so it trusts
nothing but the matcher:

```bash
python tools/paired_stats.py results/grades_expanded.jsonl   # pooled gold
python tools/paired_stats.py results/grades_strict.jsonl     # strict gold

python tools/regrade.py --grades results/grades_expanded.jsonl \
  --gold data/tasks.jsonl --out /tmp/regraded.jsonl
# -> octen-broad-search 0.5485 · parallel-turbo-agent 0.5333
#    exa-instant-agent  0.5210 · tavily-ultrafast-agent 0.5049
```

**Reproduction cost (full 313 × 4 run).** Search-API spend ≈ **$41 total** across the four vendors (per-1k rate × 313 questions: Octen ~$2.5, Parallel ~$2.4, Exa ~$17, Tavily ~$20 — dominated by Exa/Tavily; the two `$1/1k` arms cost ~$2.5 each). Plus `gpt-5-mini` tokens: ≈ **17M tokens** total (~8K/q broad, ~19–20K/q agents × 313), i.e. low-single-digit dollars at list price. Needs API keys for Octen, Exa, Tavily, Parallel, and OpenAI. Wall-clock ≈ 50 min at `--concurrency 5`.

---

## Limitations & honest disclosures

We would rather you trust the solid parts than oversell. Read this before citing.

1. **Gold quality & independence.** Gold is precision-oriented and independently verified against **two Google-backed sources (SerpApi 87.8% / BrightData 88.8% adjudicable precision) that are independent of every evaluated system**; completeness is corrected by TREC-style pooling and we ship a strict non-pooled gold. We report quality as **parity** because the paired test shows a statistical tie with the strongest competitors — not a claim of superiority. The robust finding is the cost gap (latency and tokens are physical facts, independent of the gold).
2. **Pooling bias.** The expanded gold pools correct-but-unlisted entities found by the evaluated systems (dual-source SerpApi+BrightData × dual-model GPT-5+Claude-Sonnet-5 consensus). A brand-new system evaluated later may find correct entities that were never pooled and be under-credited. We ship **both** the pooled gold and a **strict non-pooled gold**; new entrants should re-pool.
3. **Temporal snapshot.** Questions are `as_of` 2026-07/08. Answers drift over time; this is a dated snapshot, not an evergreen set. Version pinned.
4. **Mechanical, alias-aware grading.** Entity-F1 uses Unicode/casefold/punctuation normalization, corporate-suffix stripping, curated alias tables (including cross-language and brand↔network equivalences), parenthetical/appositive sub-forms, and a version-aware guard (so "Kimi K2.5" ≠ "Kimi K2"). This avoids the format-driven false negatives a naïve string match would produce; every arm is scored by the identical function.
5. **Single reader model, single repeat.** Results use `gpt-5-mini` (reasoning effort=low), one run per (task, arm). The *mechanism* effect (cost) is structural; absolute F1 and per-task variance will shift with model choice and repeats.
6. **A few hard items.** 11 tasks (3.5%) are all-zero on the pooled gold — every arm misses them (12, or 3.8%, on the strict gold). They contribute equally to all arms and do not bias the comparison. A separate 11 tasks (3.5%, `as_of` 2026-08-10) were added in a later batch; their gold was verified to the same dual-source + dual-model standard as the rest.

## Methodology in depth

See `results/RESULTS.md` (results, significance, cost), `results/PAIRED_STATS.md` (full significance tables).

## License, datasheet & changelog

- **License:** MIT (`LICENSE`).
- **Datasheet:** `data/DATASHEET.md` (motivation, composition, collection, uses, limitations).
- **Version policy & changelog:** `CHANGELOG.md` — this is a time-stamped evaluation snapshot (`as_of` mid-2026); pin the release, re-verify before comparing new systems.

## Citation

If you use WideSearch-Bench, please cite it and pin the version:

```bibtex
@misc{widesearchbench2026,
  title        = {WideSearch-Bench: Isolating How Retrieval Width Is Delivered},
  author       = {Octen},
  year         = {2026},
  version      = {2026.08},
  howpublished = {\url{https://github.com/Octen-Team/widesearch-bench}}
}
```
