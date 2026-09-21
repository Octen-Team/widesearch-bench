# Provenance and audit limits

## Available records

- Question text, date, reference entities and aliases in both task files.
- Inherited `gold_source_domains` metadata. These domains are leads, not evidence tying an entity to every question constraint.
- Stored answer entities, scores and partial run measurements in `results/grades.jsonl`.
- Explicit entity-identity corrections in `identity_decisions.json`. The candidate names were recovered from the pre-deduplication snapshot at commit `15ce66043e17d4801df23db5dc391baba8d4d65b`; observed answers and run measurements are from commit `b5db3b9fcfc66caa28dcc342bdd415eaa50ea166`.

Identity decisions were applied separately to the pooled and strict candidate sets. Correcting identity does not certify the entity's eligibility, release date, regulatory status or completeness of a set. Ambiguous family names that do not identify the requested category, version or service were excluded with an explicit reason. No source adjudications were created by this repair.

## Missing records

The current snapshot lacks per-entity retrieved source passages, dated source URLs, individual pooling judgments and reproducible filtering outputs. Older pooling verdicts belonged to a different gold snapshot; they have not been relabeled as verification of this release. Consequently, the release does not assert the earlier quantitative verification rates or that every question demonstrably requires multiple pages.

Current-source retrieval and adjudication are required before those assurances can be restored. A future evidence record should include task/entity identifiers, each constraint, dated source URLs and supporting excerpts, the decision and its rationale, and model/human provenance. Apply the same protocol to candidates from every evaluated configuration.

## Run measurements

Historical HTTP attempt counts are `null`, including hidden retries. Missing competitor subqueries and retrieval error lists are also `null`; an empty list must not be substituted for unavailable records. Published logical call counts are not HTTP request totals or verified billed-unit counts.

Recorded terminal errors remain in the data and score zero under the all-attempt quality policy. Their elapsed time is recovered from the stored failure duration; downstream usage is `null` because partial charged work was not preserved. Cost means use successful attempts only, with denominators in `results/summary.json`. Even successful historical token records may omit retry completions, so they are labeled recorded usage rather than complete billing totals. Hallucination rates are `null`: rescoring without the original evidence cannot recompute grounding.

The updated harness records task-local HTTP attempts, agent subqueries and retrieval failures on future runs. This instrumentation does not retroactively fill gaps in the reference snapshot. The stored answers have been re-scored after identity and matcher corrections; no live or selective reruns were performed for this repair.

The historical Octen client could also retry successful broad-search responses with fewer than two observed query groups. That content-dependent retry policy has been removed: future runs accept such responses and retry only transport/status failures. Historical HTTP counts are unavailable, so its impact on the recorded outputs cannot be quantified. The reference snapshot should not be described as having equal actual retrieval budgets.

The updated LLM wrapper adds both completions' reported usage when JSON parsing triggers a retry, and caches clients by model and completion budget. The historical cache used the first client created on a worker thread; mixed-configuration jobs could therefore inherit that thread's default completion budget. Current defaults are 2,000 completion tokens for the reader and 1,200 per agent turn. This is a configuration difference, not a matched total token budget.
