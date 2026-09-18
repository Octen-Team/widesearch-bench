# Alias tables

Entity aliases used by the zero-LLM grader (`widesearch_bench/normalize.py`).
Matching also applies, mechanically: NFKC + casefold + punctuation fold,
corporate-suffix strip, parenthetical/appositive sub-form extraction,
order-insensitive token-multiset equality, and version-aware token guards.

- `gold_aliases.jsonl` — per gold entity: `{task_id, canonical, aliases}`.
  Includes bilingual (zh↔en) aliases for cross-language answers and
  network↔brand equivalences (e.g. GCC: `NAPS ↔ QPay ↔ Himyan`,
  `OmanNet ↔ Oman national payment card`).
