# Results

Pooled references:

| Configuration | F1 | Precision | Recall | API calls | Searches | Tokens | E2E (s) | Source domains |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Exa-instant | 0.4835 | 0.4726 | 0.5484 | 6.05 | 6.05 | 88,031 | 32.47 | 15.34 |
| Octen broad_search | 0.5428 | 0.5709 | 0.5849 | 1.00 | 7.98 | 20,911 | 10.20 | 22.73 |
| Parallel-turbo | 0.4632 | 0.4620 | 0.5204 | 6.46 | 6.46 | 70,511 | 34.39 | 13.21 |
| Tavily-ultrafast | 0.4920 | 0.5039 | 0.5316 | 6.72 | 6.72 | 83,552 | 35.63 | 17.26 |

<details>
<summary>Strict reference scores</summary>

| Configuration | F1 | Precision | Recall |
|---|---:|---:|---:|
| Exa-instant | 0.4542 | 0.4218 | 0.5507 |
| Octen broad_search | 0.5342 | 0.5352 | 0.6124 |
| Parallel-turbo | 0.4361 | 0.4130 | 0.5250 |
| Tavily-ultrafast | 0.4655 | 0.4537 | 0.5336 |

</details>

On this dataset, Octen broad_search has the highest mean Entity-F1 against both reference sets and the lowest recorded mean latency and downstream-token usage.

Quality metrics average all 313 tasks; other columns average completed runs. API calls count logical retrieval invocations; searches count recorded subqueries/search actions. Tokens are recorded downstream LLM usage; source domains count distinct retrieved domains per run.

[All pairwise comparisons](PAIRED_STATS.md) · [Configuration and measurements](../data/PROVENANCE.md)
