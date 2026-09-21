# Paired Entity-F1 comparisons

Bootstrap 95% intervals and two-sided sign-flip permutation tests; 10,000 samples, seed 20260810. Holm correction covers all six arm pairs separately within each gold variant. No significant difference does not establish equivalence.

## Pooled gold

| A − B | n | ΔF1 | 95% bootstrap CI | permutation p | Holm p |
|---|---:|---:|---|---:|---:|
| Exa-instant − Octen broad_search | 313 | -0.0592 | [-0.0878, -0.0300] | 0.0001 | 0.0006 |
| Exa-instant − Parallel-turbo | 313 | +0.0204 | [-0.0055, +0.0464] | 0.1270 | 0.2540 |
| Exa-instant − Tavily-ultrafast | 313 | -0.0085 | [-0.0330, +0.0155] | 0.4877 | 0.4877 |
| Octen broad_search − Parallel-turbo | 313 | +0.0796 | [+0.0504, +0.1096] | 0.0001 | 0.0006 |
| Octen broad_search − Tavily-ultrafast | 313 | +0.0508 | [+0.0220, +0.0797] | 0.0008 | 0.0032 |
| Parallel-turbo − Tavily-ultrafast | 313 | -0.0288 | [-0.0570, -0.0007] | 0.0454 | 0.1362 |

## Strict gold

| A − B | n | ΔF1 | 95% bootstrap CI | permutation p | Holm p |
|---|---:|---:|---|---:|---:|
| Exa-instant − Octen broad_search | 313 | -0.0800 | [-0.1078, -0.0513] | 0.0001 | 0.0006 |
| Exa-instant − Parallel-turbo | 313 | +0.0181 | [-0.0075, +0.0444] | 0.1753 | 0.3506 |
| Exa-instant − Tavily-ultrafast | 313 | -0.0113 | [-0.0356, +0.0125] | 0.3533 | 0.3533 |
| Octen broad_search − Parallel-turbo | 313 | +0.0980 | [+0.0686, +0.1272] | 0.0001 | 0.0006 |
| Octen broad_search − Tavily-ultrafast | 313 | +0.0687 | [+0.0395, +0.0968] | 0.0001 | 0.0006 |
| Parallel-turbo − Tavily-ultrafast | 313 | -0.0294 | [-0.0582, -0.0009] | 0.0455 | 0.1365 |
