# Changelog

Because public benchmark questions can enter future training data, this is a
**time-stamped evaluation snapshot**, not an evergreen set — pin the release when
reporting.

## 2026.09

First public release.

- **313 multi-entity T1 questions**, `as_of` 2026-09-18, bilingual (EN / ZH).
  Every question is verified to require retrieval width by a mechanical
  fake-fanout filter.
- Two gold variants: `data/tasks.jsonl` (pooled, TREC-style dual-source +
  dual-model consensus, 2,003 entities) and `data/tasks_strict.jsonl`
  (precision-oriented, non-pooled). Alias tables in `data/aliases/`.
- Reference run (`results/`, 1,252 runs, 0 errors): one Octen `broad_search` vs.
  Exa-instant / Tavily-ultrafast / Parallel-turbo agent loops under an identical
  `gpt-5-mini` reader, grounding prompt, grader, and search budget (8 searches
  x 5 results). No snippet truncation in any arm: each vendor's excerpt is
  passed through at its default length, and each arm's answering model receives
  all of the evidence that arm retrieved.
- Grading is a zero-LLM Entity-F1 with Unicode / alias / version-aware and
  cross-language matching; significance via paired bootstrap + permutation with
  Holm correction (`results/PAIRED_STATS.md`).
- **Summary:** broad_search reaches the highest Entity-F1 (0.5688) and recall
  (0.6138) of the four. Against Parallel (0.5154) and Exa (0.5284) the gap is
  significant after Holm correction; against Tavily (0.5542) it is not — those
  two are a statistical tie on quality. Cost is not close: 1 API call instead of
  6.0-6.7, 20.8K tokens instead of 70-87K, 10.2s instead of 32-36s.
