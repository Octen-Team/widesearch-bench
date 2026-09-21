# Reference results

313 questions; 1252 attempted runs; **5 recorded failures**.

Quality includes every attempt. Cost means below use successful attempts only; they are not full-run totals.

| Configuration | Attempts / successful | Pooled F1 | Strict F1 | Precision | Recall | Logical searches/calls | E2E s | Recorded LLM tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Exa-instant | 313 / 311 | 0.4835 | 0.4542 | 0.4726 | 0.5484 | 6.05 | 32.47 | 88,031 |
| Octen broad_search | 313 / 312 | 0.5428 | 0.5342 | 0.5709 | 0.5849 | 1.00 | 10.20 | 20,911 |
| Parallel-turbo | 313 / 311 | 0.4632 | 0.4361 | 0.4620 | 0.5204 | 6.46 | 34.39 | 70,511 |
| Tavily-ultrafast | 313 / 313 | 0.4920 | 0.4655 | 0.5039 | 0.5316 | 6.72 | 35.63 | 83,552 |

Logical calls exclude hidden HTTP retries: broad_search is one orchestration invocation; agents count search actions. Actual HTTP attempts were not recorded for this snapshot.
Token counts cover downstream LLM usage, not provider-internal work. Retry completions may be incompletely represented in historical usage.
These are observations from the tested configurations, not an isolated causal estimate of orchestration or a vendor-wide ranking.

See [paired comparisons](PAIRED_STATS.md) and [provenance](../data/PROVENANCE.md).
