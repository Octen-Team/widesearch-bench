# Alias tables

Entity aliases used by the zero-LLM grader (`widesearch_bench/normalize.py`).
Matching also applies, mechanically: NFKC + casefold + punctuation fold,
corporate-suffix strip, parenthetical sub-forms, guarded prediction descriptions,
and order-insensitive token-multiset equality. Arbitrary containment does not
establish identity; model qualifiers and programming-language symbols matter.

- `gold_aliases.jsonl` — per gold entity: `{task_id, canonical, aliases}`.
  Generated from pooled `data/tasks.jsonl` by `tools/release_report.py`.
- Current scoring reads aliases directly from the selected task file, so strict
  scoring does not import pooled entities from this convenience export.
- Identity edits and additions are documented in `data/identity_decisions.json`.
  Inherited aliases have the source-verification limits in `data/PROVENANCE.md`.
