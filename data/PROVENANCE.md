# Configuration and measurements

## Dataset and outputs

Reference candidates come from commit `15ce66043e17d4801df23db5dc391baba8d4d65b`; recorded answers and measurements come from `b5db3b9fcfc66caa28dcc342bdd415eaa50ea166`. [Identity decisions](identity_decisions.json) apply separately to each reference set. Source domains are included; per-entity source excerpts and pooling adjudications are not available in this release. Scores measure agreement with these reference answers.

## Evaluation configuration

The recorded run uses `openai:gpt-5-mini` with low reasoning effort, one attempt per question/configuration, and concurrency five. Octen uses broad_search plus a JSON reader; the other configurations use SEARCH/ANSWER agent loops. Each is configured for up to eight subqueries/search actions and five retained results per search. Excerpts retain vendor-specific lengths.

The recorded Octen client could retry successful responses containing fewer than two query groups. HTTP-attempt counts were not recorded. The current client accepts those responses and retries transport/status failures only. Current completion limits are 2,000 tokens for the reader and 1,200 per agent turn; the recorded implementation reused the first client created on a worker thread, so mixed-configuration jobs could inherit that client's default limit.

## Metrics

Entity-F1, precision and recall average all 313 task attempts per configuration. Terminal errors score zero. The other table columns average completed runs; denominators are in [summary.json](../results/summary.json). API calls count logical retrieval invocations, not HTTP attempts. Searches count recorded broad-search subqueries or issued agent search actions. Source domains count distinct domains among retrieved URLs per run, regardless of whether they support a correct answer. Downstream tokens exclude provider-internal work; historical JSON-retry usage may be incomplete. Unavailable measurements are `null`.

The same stored answers are scored against pooled and strict references. Paired bootstrap intervals and sign-flip tests use 10,000 samples and seed 20260810; Holm correction covers all six pairs separately for each reference set. These comparisons describe the tested configurations on this dataset.
