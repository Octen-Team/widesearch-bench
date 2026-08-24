# WideSearch-Bench — Final results (fresh full run, n=313)

> **Canonical results.** Benchmark `data/tasks.jsonl` (313) · per-run traces `results/grades_expanded.jsonl` (1,252 runs, **0 errors**) · single answering model `openai:gpt-5-mini` (OpenAI direct, reasoning effort=low) · one consistent batch (same day, same harness, same matcher). Four configurations (no control arm).

## Core results

| Search provider | F1 | Real queries | Search time (s) | End-to-end (s) | Tokens | Search $/1k q † |
|---|---|---|---|---|---|---|
| **Octen — one broad_search** | **0.548** | 8.0 | 1.94 | **8.4** | **8,043** | 8.0 |
| Parallel-turbo + agent-loop | 0.533 | 7.8 | 7.59 | 41.1 | 19,327 | 7.8 |
| Exa-instant + agent-loop | 0.521 | 7.7 | 2.33 | 40.5 | 19,679 | 54.1 |
| Tavily-ultrafast + agent-loop | 0.505 | 7.9 | 1.77 | 46.1 | 20,088 | 62.8 |

† Search-API cost = real queries × current per-search price: Octen $1/1k (broad_search billed per sub-query) · Exa-instant $7/1k · Tavily basic $8/1k · Parallel turbo $1/1k. Tokens are total downstream LLM consumption.

## Paired significance (F1, bootstrap 95% CI, n=313, vs Octen broad_search)

| Comparison | ΔF1 | 95% CI | Verdict |
|---|---|---|---|
| vs Parallel-turbo | +0.015 | [−0.014, 0.045] | n.s. |
| vs Exa-instant | +0.028 | [−0.006, 0.060] | n.s. |
| vs Tavily-ultrafast | +0.044 | [0.012, 0.075] | **significant** (Holm 0.028) |

## Conclusions

- **Quality: on par with the strongest competitors (pooled gold).** broad_search's mean (0.548) leads all four, but on the **pooled/expanded gold** it is a statistical **tie** with Parallel (0.533) and Exa (0.521), significant only over Tavily (0.505). On the **strict, non-pooled gold** (`data/tasks_strict.jsonl`) broad_search is significant against all three (strict F1: 0.545 / 0.503 / 0.490 / 0.480; Δ +0.042 / +0.055 / +0.065, Holm p ≤ 0.007) — pooling adds "correct-but-unlisted" entities that agents surface more of, which narrows the gap. We report parity on the pooled gold and treat strict as the optimistic bound. **We do not claim higher quality.**
- **Cost: decisive and unambiguous.** End-to-end **≈4.9× faster** (8.4s vs 41–46s) · tokens **≈2.4× fewer** (8.0k vs ~19–20k) · search-API spend tied with Parallel-turbo and **≈7× below** Exa/Tavily. Real search width is comparable (≈8 for all).

**In one line:** on multi-entity retrieval, one broad_search reaches answer quality on par with the strongest agent-loop competitors at ~1/5 the latency, ~1/2.4 the tokens, and the lowest search-API tier. The value proposition is *same quality, cheaper, faster*.

## Data-quality notes

- **broad_search anti-degenerate guard works:** only 2 tasks show nq≤1, and both are genuinely narrow queries (an antitrust-lawsuit question and a CISA/FBI joint-advisory malware question — broad_search legitimately fans out to a single sub-query on these). The earlier 75 transient nq=1 failures are resolved.
- Empty answers per arm: 11–18, symmetric (legitimate "found nothing" outcomes from the agent/reader).
- Gold: `data/tasks.jsonl` (pooled/expanded) and `data/tasks_strict.jsonl` (strict, non-pooled — for pooling-bias checks).
