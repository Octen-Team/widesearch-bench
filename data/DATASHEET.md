# Dataset

WideSearch-Bench contains multi-entity enumeration questions in English and Chinese, dated 2026-09-18.

<!-- BEGIN GENERATED -->
- Questions: 313
- Pooled entities: 1828; strict entities: 1577
- Pooled set sizes: mean 5.8, median 5, range 2–23
<!-- END GENERATED -->

## Reference sets

- `tasks.jsonl`: pooled reference answers.
- `tasks_strict.jsonl`: strict reference answers for the same questions.

Each task contains the question, reference entities and aliases, date, language, set size and source-domain metadata. Both variants use the same entity-identity policy; pooled-only entities are not added to strict. [Identity decisions](identity_decisions.json) record merges, exclusions and shared aliases.

## Scoring

Every configuration uses the same mechanical Entity-F1 scorer. Distinct model variants, services and award categories remain separate. Scores are reported against both reference sets; all pairwise comparisons use Holm correction.

See [dataset statistics](DATASET_STATS.md), [configuration and measurement details](PROVENANCE.md), and [results](../results/RESULTS.md).
