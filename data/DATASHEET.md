# Datasheet — WideSearch-Bench

## Purpose

Compare recorded outcomes of web-search configurations on multi-entity enumeration questions. Backend, excerpt length, prompt protocol and stopping behavior vary; this is not an experiment isolating a single orchestration mechanism.

## Composition

<!-- BEGIN GENERATED -->
- Questions: 313
- Pooled entities: 1828; strict entities: 1577
- Pooled set sizes: mean 5.8, median 5, range 2–23
<!-- END GENERATED -->

Questions are in English and Chinese, with `as_of` 2026-09-18. [DATASET_STATS.md](DATASET_STATS.md) is generated from the task file. Set-size labels describe the current number of reference entities.

## Collection and annotation

The inherited dataset was model-drafted and described as having undergone multi-source annotation and candidate pooling. The current release does not contain the source excerpts, individual adjudications or filter outputs needed to verify those descriptions. It makes no quantified gold-precision, completeness, independent-verification or single-page-exclusion claim. See [PROVENANCE.md](PROVENANCE.md).

Pooled and strict variants are retained. Identity corrections were reviewed at each question's requested granularity and recorded in [identity_decisions.json](identity_decisions.json). They repair name identity and do not establish factual eligibility. No members from the pooled variant were added to strict during this correction.

## Uses and limitations

Use as reference responses for harness development and exploratory comparison. Report both gold variants, failures, metric denominators, model settings and commit. Qualifying real-world facts require fresh evidence before treating these answers as an authoritative benchmark.

Candidate pooling, unknown completeness, selected domains, one model, one repeat and time drift limit generalization. A non-significant test does not establish equivalence. Text budgets differ because vendor excerpts retain their own default lengths.

## Maintenance

Pin [the release and commit](../CHANGELOG.md). Re-verify eligibility and retain source-level adjudications when updating gold. Reviewed identity merges must not be inferred automatically from permissive scoring matches.
