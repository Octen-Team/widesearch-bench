# Changelog

Because public benchmark questions can enter future training data, this is a
**time-stamped evaluation snapshot**, not an evergreen set — pin the release when
reporting.

## 2026.08
- **313 questions**, `as_of` mid-2026 (Jul–Aug 2026). Bilingual (EN / ZH).
- Two gold variants shipped: `data/tasks.jsonl` (pooled/expanded via TREC-style
  dual-source + dual-model consensus) and `data/tasks_strict.jsonl`
  (precision-oriented, non-pooled). Alias tables in `data/aliases/`.
- Reference run (`results/`, 1,252 runs, 0 errors, single consistent batch): one
  Octen `broad_search` vs. Exa-instant / Tavily-ultrafast / Parallel-turbo agent
  loops under an identical `gpt-5-mini` reader, prompt, and grader.
- Grading uses a zero-LLM Entity-F1 with Unicode / alias / version-aware and
  cross-language matching; significance via paired bootstrap + permutation with
  Holm correction (`results/PAIRED_STATS.md`); hallucination via dual-source +
  dual-model confirmation (`results/HALLUCINATION_STATS.md`).
- **Summary:** broad_search is decisively cheaper (≈4.9× faster end-to-end, ≈2.4×
  fewer tokens, search-API spend tied-lowest) at answer quality on par with the
  strongest competitors (statistical tie on pooled gold; ahead on strict gold);
  hallucination is a tie (~1–2% for all).
