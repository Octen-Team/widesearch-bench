# Results

Pooled references:

| Configuration | F1 | Precision | Recall | API calls | Searches | Tokens | E2E (s) | Source domains |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Octen broad_search | 0.5428 | 0.5709 | 0.5849 | 1.00 | 7.98 | 20,911 | 10.20 | 22.73 |
| Tavily-ultrafast | 0.4920 | 0.5039 | 0.5316 | 6.72 | 6.72 | 83,552 | 35.63 | 17.26 |
| Exa-instant | 0.4835 | 0.4726 | 0.5484 | 6.05 | 6.05 | 88,031 | 32.47 | 15.34 |
| Parallel-turbo | 0.4632 | 0.4620 | 0.5204 | 6.46 | 6.46 | 70,511 | 34.39 | 13.21 |

<details>
<summary>Strict reference scores</summary>

| Configuration | F1 | Precision | Recall |
|---|---:|---:|---:|
| Octen broad_search | 0.5342 | 0.5352 | 0.6124 |
| Tavily-ultrafast | 0.4655 | 0.4537 | 0.5336 |
| Exa-instant | 0.4542 | 0.4218 | 0.5507 |
| Parallel-turbo | 0.4361 | 0.4130 | 0.5250 |

</details>

On these 313 questions, Octen broad_search ranks first in pooled F1, precision and recall, with higher F1 than all 3 agent configurations (Holm-adjusted p < 0.01); compared with Octen, the agent configurations use 6.1–6.7× as many logical API calls and 3.4–4.2× as many recorded downstream tokens, and take 3.2–3.5× as long end to end.

Quality metrics average all 313 tasks; other columns average completed runs. API calls count logical retrieval invocations; searches count recorded subqueries/search actions. Tokens are recorded downstream LLM usage; source domains count distinct retrieved domains per run.

[All pairwise comparisons](PAIRED_STATS.md) · [Configuration and measurements](../data/PROVENANCE.md)
