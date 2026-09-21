# Results

| Configuration | Pooled F1 | Strict F1 | Precision | Recall | E2E s | Recorded LLM tokens |
|---|---:|---:|---:|---:|---:|---:|
| Exa-instant | 0.4835 | 0.4542 | 0.4726 | 0.5484 | 32.47 | 88,031 |
| Octen broad_search | 0.5428 | 0.5342 | 0.5709 | 0.5849 | 10.20 | 20,911 |
| Parallel-turbo | 0.4632 | 0.4361 | 0.4620 | 0.5204 | 34.39 | 70,511 |
| Tavily-ultrafast | 0.4920 | 0.4655 | 0.5039 | 0.5316 | 35.63 | 83,552 |

On this dataset, Octen broad_search has the highest mean Entity-F1 against both reference sets and the lowest recorded mean latency and downstream-token usage.

F1 averages all 313 tasks; latency and token means use completed runs. Precision and recall use pooled references.

[All pairwise comparisons](PAIRED_STATS.md) · [Configuration and measurements](../data/PROVENANCE.md)
