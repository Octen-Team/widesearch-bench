# Datasheet — WideSearch-Bench

Following Gebru et al., *Datasheets for Datasets*. Numbers verified against
`data/tasks.jsonl` and `data/DATASET_STATS.md`.

## Motivation
Isolate **how retrieval width is delivered** for multi-entity questions — one
server-side broad-search call vs. a client-side multi-turn agent loop — under a
controlled setup (fixed answering model, prompt, grader, and number of real
searches). Existing benchmarks grade a final answer and conflate *how much*
searching happened with *how* it was orchestrated; this set separates them.

## Composition
- **313 T1 enumeration questions.** Each has an objective, closed answer set
  (the entities satisfying a conjunction of constraints). No single-answer
  questions — breadth by construction.
- **Language:** 227 English (72.5%) / 86 Chinese (27.5%); no other languages.
- **Gold-set size:** mean 6.2, median 5, range 2–23.
- **Domains (keyword-bucketed):** space/aerospace ~20%, biomed/pharma ~17%,
  AI-ML/compute ~13%, sports leagues ~10%, cloud/infra ~8%, media ~5%,
  security ~3%, fintech ~3%, open-source foundations ~2%, ~19% uncategorized.
- **Two gold variants:** `tasks.jsonl` (pooled/expanded) and
  `tasks_strict.jsonl` (precision-oriented, non-pooled). Alias tables in
  `aliases/` (Unicode, corporate-suffix, brand↔network, and zh↔en equivalences).

## Collection & annotation
Model-drafted across ~20 domains → mechanical *fake-fanout* filter (auto-reject
anything a single page answers, ≥80% coverage) → per-constraint evidence-grounded
gold with the final AND enforced in code → three-way audit: two independent
Google sources (SerpApi 87.8% / BrightData 88.8% adjudicable precision), a
cross-vendor model panel (GPT-5 + Claude Sonnet 5), and a human spot-check on a sample.
Completeness corrected at eval time by TREC-style pooling
(`../results/pooling_verdicts.jsonl`). Not hand-authored; not harvested from
production traffic.

## Recommended uses
Comparing width-delivery mechanisms / search backends on multi-entity retrieval
under matched conditions; studying cost–quality trade-offs; mechanical Entity-F1
evaluation. Report both pooled and strict gold.

## Limitations / not recommended for
- **Selection scope:** the set is enumeration answerable from the open web with
  a handful of queries; not a random sample of production traffic. Gold is
  independently verified by two Google sources (SerpApi + BrightData); pooled and
  strict gold are both shipped. Quality is reported as *parity* (a statistical
  tie), not superiority.
- **Pooling bias:** expanded gold credits entities the evaluated systems found; a
  brand-new system should re-pool. (Strict gold shipped for this reason.)
- **Temporal snapshot:** `as_of` mid-2026; answers drift — see version policy.
- **Single answering model** (`gpt-5-mini`), one run per (task, arm).
- Not a random sample of real queries; skews toward open-web-answerable
  enumeration.

## Maintenance & versioning
Time-stamped snapshot dataset. Changes tracked in
`../../CHANGELOG.md`. Because public questions may enter future training data,
treat this as a **time-stamped evaluation snapshot**, not an evergreen set;
re-verify or re-pool before comparing new systems.
