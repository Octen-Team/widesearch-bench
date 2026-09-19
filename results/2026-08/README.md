# 2026-08 — archived release

This is the release published on 2026-08-10, kept exactly as it went out. The
files record what the four configurations actually answered that day, and the
numbers are the ones that were reported. **Nothing here is re-scored or
restated.** Corrections live in the next release, not in this one.

Two things to know before you cite or re-run it.

## The grades here were not produced by the harness's own scorer

`results/2026-08/grades_expanded.jsonl` and `grades_strict.jsonl` were written by
`tools/regrade.py` as it stood in August. That version counted a gold entity as
found if *any* prediction matched it, so a single prediction could be credited
against several gold entities. The live harness (`grading.grade_t1`) instead uses
`match_sets`, a greedy 1:1 assignment.

The two disagree on **21.2% of rows**, and the permissive one scores higher. So
re-running `widesearch run` over `data/2026-08/` will *not* reproduce the table
in `RESULTS.md` — the difference is the scorer, not your setup. `regrade.py` was
fixed in the 2026-09 cycle and now goes through the same path as the harness.

For the same reason, `detail.missed` / `detail.extra` in these files were carried
over from an earlier grading pass rather than recomputed, so on some rows the
detail block does not add up to the precision and recall stored beside it.

## The entity matcher has since been fixed, and the fix is not neutral

Three defects were found in `normalize.py` after this release:

- `A / B` names were not split into sub-forms, so the corporate-suffix stripper
  only ever fired on the trailing name.
- Token containment was rejected below a 0.5 token-count ratio, so a gold entity
  never matched a prediction that named it more fully
  (`Apollo 11` vs `Apollo 11 Passive Seismic Experiment (PSE)`).
- A single-token guard blocked bare model codes (`M3` vs gold `Apple M3`), and
  alias coverage was 2.2% of gold entities.

All three penalise verbose answers, and the agent arms answer with fuller entity
names more often than the one-shot reader does — so the defect was asymmetric
between the configurations being compared. Treat the *gaps* in `RESULTS.md`
accordingly.

## What is unaffected

Latency, downstream tokens, API calls, retrieved URLs and
`detail.answer_entities` are observations, not derived scores. They are
unaffected by any of the above.
