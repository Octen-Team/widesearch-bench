# WideSearch-Bench

A reference dataset and harness for multi-entity web questions. This release compares four search configurations under a maximum budget of eight searches and five retained results per search, using `openai:gpt-5-mini`.

The configurations use different search backends, excerpt defaults and answering protocols. Agent loops can stop early. Evidence volume and actual search counts therefore differ; the experiment does not isolate orchestration as the only cause of quality, latency or token differences.

## Reference results

<!-- BEGIN GENERATED -->
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
<!-- END GENERATED -->

![Reference results](figures/widesearch_results.png)

See [all pairwise comparisons](results/PAIRED_STATS.md), [individual answers](results/cases.jsonl), and [recorded failures](results/FAILURES.md). The figure uses alphabetical configuration order and equal visual emphasis. No-significance results are not equivalence claims.

## Data and provenance

- [Pooled gold](data/tasks.jsonl) and [strict gold](data/tasks_strict.jsonl) share the same questions and `as_of` date, 2026-09-18. Report both variants.
- [Datasheet](data/DATASHEET.md) and [statistics](data/DATASET_STATS.md) describe the release.
- [Reviewed identity decisions](data/identity_decisions.json) separate distinct products, languages and award categories while merging documented surface forms. A fuzzy scoring match cannot authorize a merge.
- **Evidence limitation:** the current snapshot lacks per-entity source excerpts and pooling adjudication records. It is not independently auditable as a verified, exhaustive ground truth. [Provenance](data/PROVENANCE.md) describes what is and is not available. Results are conditional on these reference answers.

## Configuration

| Aspect | Setting |
|---|---|
| Answering model | `openai:gpt-5-mini`, reasoning effort `low` |
| Octen | One broad-search invocation, at most 8 subqueries × 5 results |
| Exa / Parallel / Tavily | Model-driven agent, at most 8 search actions × 5 retained results |
| Excerpts | Vendor defaults; no client-side snippet text truncation by default |
| Answering | Shared grounding rules; JSON reader for broad-search versus SEARCH/ANSWER agent protocol |
| Current completion limits | Reader: 2,000; agent: 1,200 per turn. Historical thread-cache and retry limitations are described in provenance. |
| Scoring | Same alias-aware Entity-F1 matcher for every configuration |
| Repeats | One attempted run per task and configuration |
| Concurrency | Five runs per configuration |

Unbounded excerpt passthrough is not a matched text budget. Different excerpt lengths affect context usage and token totals. Token counts exclude provider-internal computation and are not dollar costs. Request counts distinguish logical orchestration/search actions from HTTP attempts including retries.

## Reproduce

Python 3.10 or newer:

```sh
pip install -e '.[analysis]'
cp .env.example .env
# Fill in the search-provider keys and OPENAI_API_KEY, then:
set -a; source .env; set +a
widesearch doctor
widesearch run data/tasks.jsonl --out my-run \
  --arms exa-instant-agent,octen-broad-search,parallel-turbo-agent,tavily-ultrafast-agent \
  --repeats 1 --concurrency 5
```

Live reproduction incurs provider charges. Dates, indexes, models and vendor defaults can change; a rerun is a new observation. Use a separate output directory. `--dump-raw` saves retrieved snippets locally for every configuration; review and redact external content before sharing it.

The shipped responses can be re-scored without network access:

```sh
python tools/regrade.py --grades results/grades.jsonl \
  --gold data/tasks.jsonl --out /tmp/pooled.jsonl
python tools/regrade.py --grades results/grades.jsonl \
  --gold data/tasks_strict.jsonl --out /tmp/strict.jsonl
python tools/paired_stats.py /tmp/pooled.jsonl
python tools/paired_stats.py /tmp/strict.jsonl
python tools/release_report.py --check
```

Regenerate publication artifacts from the stored responses and current gold:

```sh
python tools/release_report.py
python tools/dataset_stats.py
python tools/make_figure.py
```

## Limitations

Gold completeness and eligibility need source-level verification before using this dataset to support vendor rankings. Candidate pooling can favor systems whose answers contributed candidates; construction records are insufficient to quantify that effect. The strict variant is a sensitivity check, not proof of independence. There is no reproducible evidence here for the earlier claimed single-page exclusion audit.

The published snapshot has missing HTTP-attempt counts, competitor query traces and retrieval-error diagnostics. These are marked unknown; current instrumentation cannot reconstruct historical events. Only recorded terminal failures can be counted. Failed usage is unavailable, and historical retry completions may be missing from downstream token counts. Cost summaries exclude failed runs and state their denominators. Quality includes every attempted run, with recorded failures scored zero. The historical Octen client could retry successful narrow responses; that policy has been removed for future runs, but its historical impact is unknown. See [provenance](data/PROVENANCE.md) for retry and completion-budget differences.

A single model, one repeat and this selected question set do not establish general performance, equivalence, or an isolated causal effect. Statistical tests describe variation across this dataset, conditional on its gold and recorded outputs.

## Citation and license

MIT; see [LICENSE](LICENSE). Cite the repository and pin both the release and commit, because this dated dataset and its scoring can change:

```bibtex
@misc{widesearchbench2026,
  title = {WideSearch-Bench: Multi-entity Web Search Configurations},
  author = {Octen},
  year = {2026},
  version = {2026.09},
  howpublished = {\url{https://github.com/Octen-Team/widesearch-bench}}
}
```
