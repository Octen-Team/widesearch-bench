# WideSearch-Bench

**A benchmark that isolates *how retrieval width is delivered* for multi-entity questions — one server-side broad-search call vs. a model-driven multi-turn agent loop — holding the answering model, prompt, grading, evidence budget, and number of real searches fixed.**

> **Headline (n=313):** On multi-entity enumeration, a single `broad_search` call
> reaches the highest Entity-F1 and the highest recall of the four configurations
> — significantly ahead of two of the three agent loops, statistically tied with
> the third — while issuing **1 API call instead of 6.0–6.7**, using **3.4–4.2×
> fewer tokens**, and finishing **3.2–3.5× faster**.

---

## Results (n=313, same `gpt-5-mini` reader, same 8-search budget, no snippet truncation in any arm)

| Configuration | Entity-F1 | Recall | Precision | API calls | Real queries | End-to-end (s) | Tokens |
|---|---|---|---|---|---|---|---|
| **Octen — one broad_search** | **0.5688** | **0.6138** | 0.5981 | **1.0** | 8.0 | **10.2** | **20,844** |
| Tavily-ultrafast — agent loop | 0.5542 | 0.5948 | 0.5733 | 6.7 | 6.7 | 35.6 | 83,552 |
| Exa-instant — agent loop | 0.5284 | 0.5993 | 0.5171 | 6.0 | 6.0 | 32.3 | 87,469 |
| Parallel-turbo — agent loop | 0.5154 | 0.5794 | 0.5140 | 6.4 | 6.4 | 34.2 | 70,060 |

**Paired significance (ΔF1 vs broad_search, bootstrap 95% CI, Holm-corrected):**
Parallel +0.053 `[+0.026, +0.081]` p=0.0006 and Exa +0.040 `[+0.014, +0.067]`
p=0.008 are **significant**; Tavily +0.015 `[-0.011, +0.040]` p=0.248 is **not** —
broad_search and the Tavily agent loop are a statistical tie on quality. Full
tables in `results/PAIRED_STATS.md`.

The cost gaps are not close, and they are structural rather than statistical:
1 API call against 6.0–6.7, 20.8K tokens against 70–87K, 10.2s against 32–36s.

1,252 runs, **0 errors**.

![Results](figures/widesearch_results.png)

---

## What this benchmark is

- **313 multi-entity T1 enumeration questions** (English + Chinese), each with an objective, closed answer set.
- Each question is **verified to require retrieval width** by a mechanical *fake-fanout* filter (no single page covers the answer).
- Graded by a **zero-LLM mechanical Entity-F1** (Unicode/alias/version-aware matching) — no judge model in the scoring loop.
- Four configurations vary **only the width-delivery mechanism**; the answering model (`gpt-5-mini`), grounding prompt, grading, and search budget (8 searches × 5 results) are held fixed.
- **No snippet truncation anywhere.** Every arm passes through whatever its vendor returns at that vendor's default excerpt setting, and every arm's answering model receives all of the evidence its arm retrieved.

## Files

| Path | What |
|---|---|
| `data/tasks.jsonl` | **Primary eval set** — 313 tasks, pooled gold (2,003 entities) |
| `data/tasks_strict.jsonl` | Same tasks, **strict gold** (no pooled additions) |
| `data/aliases/` | Entity aliases and normalization rules |
| `data/DATASHEET.md` | Motivation, composition, collection, uses, limitations |
| `results/grades.jsonl` | **Per-run traces + scores** (4 arms × 313) — the reported numbers |
| `results/PAIRED_STATS.md` | Paired significance tables |
| `results/cases.jsonl` | Per-question: gold · every arm's answer + score |

## Repository layout

```
data/       tasks.jsonl  tasks_strict.jsonl  aliases/
            DATASHEET.md  DATASET_STATS.md
results/    grades.jsonl  cases.jsonl  PAIRED_STATS.md
figures/    widesearch_results.{png,svg}
tools/      make_figure.py  make_cases.py  paired_stats.py
            regrade.py  dataset_stats.py
tests/      harness unit tests (pytest)
widesearch_bench/   the harness (search clients, agent loop, reader, grader)
.env.example        template for the five required API keys
```

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
python tools/paired_stats.py results/grades.jsonl

python tools/regrade.py --grades results/grades.jsonl \
  --gold data/tasks.jsonl --out /tmp/regraded.jsonl
# -> octen-broad-search 0.5688 · tavily-ultrafast-agent 0.5542
#    exa-instant-agent 0.5284 · parallel-turbo-agent 0.5154
```

**Reproduction cost (full 313 × 4 run).** Search-API spend ≈ **$41 total** across the four vendors (per-1k rate × 313 questions: Octen ~$2.5, Parallel ~$2.4, Exa ~$17, Tavily ~$20 — dominated by Exa/Tavily; the two `$1/1k` arms cost ~$2.5 each). Plus `gpt-5-mini` tokens: ≈ **82M tokens** total (~21K/q broad, ~70–87K/q agents × 313). The agent arms dominate: with snippets passed through at full length, each round re-sends a longer transcript. Needs API keys for Octen, Exa, Tavily, Parallel, and OpenAI. Wall-clock ≈ 35 min at `--concurrency 5`.

---

## Limitations & honest disclosures

We would rather you trust the solid parts than oversell. Read this before citing.

1. **Gold quality & independence.** Gold is precision-oriented and independently verified against **two Google-backed sources (SerpApi 87.8% / BrightData 88.8% adjudicable precision) that are independent of every evaluated system**; completeness is corrected by TREC-style pooling and we ship a strict non-pooled gold. broad_search is ahead of two agent loops and tied with the third, so the quality claim is "highest, significantly ahead of two of three" — not a sweep. The robust finding is the cost gap: latency, tokens and call count are physical facts, independent of the gold.
2. **Pooling bias.** The expanded gold pools correct-but-unlisted entities surfaced during gold construction (dual-source SerpApi+BrightData × dual-model GPT-5+Claude-Sonnet-5 consensus). A system evaluated later may find correct entities that were never pooled and be under-credited. We ship **both** the pooled gold and a **strict non-pooled gold**; new entrants should re-pool.
3. **Temporal snapshot.** Questions are `as_of` 2026-09-18. Answers drift over time; this is a dated snapshot, not an evergreen set. Pin the release when reporting.
4. **Mechanical, alias-aware grading.** Entity-F1 uses Unicode/casefold/punctuation normalization, corporate-suffix stripping, curated alias tables (including cross-language and brand↔network equivalences), parenthetical/appositive sub-forms, and a version-aware guard (so "Kimi K2.5" ≠ "Kimi K2"). This avoids the format-driven false negatives a naïve string match would produce; every arm is scored by the identical function.
5. **Single reader model, single repeat.** Results use `gpt-5-mini` (reasoning effort=low), one run per (task, arm). The *mechanism* effect (cost) is structural; absolute F1 and per-task variance will shift with model choice and repeats.
6. **A few hard items.** 2 tasks (0.6%) are all-zero — every arm misses them. They contribute equally to all arms and do not bias the comparison.

## Methodology in depth

See `results/PAIRED_STATS.md` for the full significance tables, and `results/cases.jsonl` for what every arm answered on each question.

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
  version      = {2026.09},
  howpublished = {\url{https://github.com/Octen-Team/widesearch-bench}}
}
```
