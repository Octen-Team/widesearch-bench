# Paired significance (ΔF1 vs Octen broad_search) — bootstrap CI + permutation p + Holm

### results/grades_expanded.jsonl
| Comparison | n | ΔF1 | 95% CI | p | p (Holm) | verdict |
|---|---|---|---|---|---|---|
| vs. Exa-instant | 313 | +0.028 | [-0.006, +0.060] | 0.0994 | 0.1988 | n.s. |
| vs. Parallel-turbo | 313 | +0.015 | [-0.014, +0.045] | 0.3079 | 0.3079 | n.s. |
| vs. Tavily-ultrafast | 313 | +0.044 | [+0.012, +0.075] | 0.0094 | 0.0282 | **sig** |

### results/grades_strict.jsonl
| Comparison | n | ΔF1 | 95% CI | p | p (Holm) | verdict |
|---|---|---|---|---|---|---|
| vs. Exa-instant | 313 | +0.055 | [+0.020, +0.089] | 0.0012 | 0.0024 | **sig** |
| vs. Parallel-turbo | 313 | +0.042 | [+0.011, +0.072] | 0.0065 | 0.0065 | **sig** |
| vs. Tavily-ultrafast | 313 | +0.065 | [+0.033, +0.097] | 0.0001 | 0.0003 | **sig** |
