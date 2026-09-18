# Hallucination — per-arm rates + paired significance (n=313)

**Definition:** an answer entity that (a) does not match gold AND (b) is independently
**confirmed wrong** by dual-source (SerpApi + BrightData) + dual-model (GPT-5 + Claude
Sonnet 5) consensus (`dual_verdicts.jsonl`). Rate = confirmed-wrong / total answer entities.
This is a **lower bound**: only pooled entities were adjudicated; fresh-run entities never
pooled are not counted (would require new retrieval, not run).

| Arm | confirmed-wrong / total | rate |
|---|---|---|
| Octen — one broad_search | 16 / 1500 | **1.1%** |
| Exa-instant — agent | 24 / 1543 | 1.6% |
| Parallel-turbo — agent | 27 / 1604 | 1.7% |
| Tavily-ultrafast — agent | 27 / 1356 | 2.0% |

Range 1.1%–2.0%. Octen broad is numerically lowest but **within noise**.

## Paired test vs. Octen broad_search (per-task rate, bootstrap CI + sign-flip permutation p)

| Comparison | ΔRate | 95% CI | p |
|---|---|---|---|
| vs. Parallel-turbo | −0.4 pp | [−0.9, +0.1] | 0.125 |
| vs. Exa-instant | −0.2 pp | [−0.8, +0.3] | 0.125 |
| vs. Tavily-ultrafast | −0.2 pp | [−0.8, +0.4] | 0.250 |

**No pairwise difference is significant** (all p ≥ 0.125; Holm-corrected all n.s.). Under
strict dual-source + dual-model confirmation, true fabrication is ~1–2% for every
configuration with no detectable difference. (A looser single-source, evidence-grounded
proxy over-counts *correct-but-ungrounded* entities and is therefore not used here.)
