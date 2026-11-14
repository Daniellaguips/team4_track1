# Codex plan review — 12:38 PM

## Scores

- **Reliability/yield (20): 5/10.** Gates and bounded repair are sound, but five cards depend on ~1,000 untested lines, unavailable API access, and an already-missed first milestone.
- **Fairness (15): 7/10.** Rule IDs plus mechanical coverage and a spec/test audit are strong, though the audit and renderer are not yet proven.
- **Hardness (20): 5/10.** Mutation checks help, but “10 rules/30 tests” rewards bulk, not model difficulty, and benchmarking starts too late to steer selection.
- **Variation (20): 8/10.** The five capability shapes are substantively different; delivered variation will be lower if only one or two survive.
- **Regression (10): 7/10.** Curated module-to-P2P mapping is rubric-aligned, but the map/checker are unfinished.
- **Reproducibility (5): 8/10.** Canonical telemetry, hashes, seed, and offline replay are excellent if implemented and demonstrated.
- **Efficiency (10): 4/10.** Seven parallel cards, two LLM stages, audits, and two repairs lack a token/cost ceiling and risk spending heavily before validation.
- **Feasibility: 2/10.** About 72 minutes remain; build is paused, no key is available, and no end-to-end factory run exists.

## Top improvements by expected points per minute

1. **Schedule:** replace the stale timetable with a 15-minute reauthorization/auth gate: prove one reference-seed generate→check→summary run; if it fails, switch immediately to minimum-submission mode.
2. **Cut lines:** make the target **two valid generated tasks + one backup**, not five plus two; one valid task outranks five partial packages on the validity tie-break.
3. **Benchmark:** launch k=3 on the first frozen valid task immediately; benchmark a second only after submission validation passes. Never wait for the batch.
4. **Architecture §2/§6:** replace fixed “≥10 rules/≥30 tests” with 6–10 interacting rules and the smallest biting test set; keep mutation, oracle, nop, and curated P2P unchanged.
5. **Demo:** replace live fresh generation with deterministic offline replay of the submitted run, then show its saved raw response, validation summary, mutation failure, and benchmark evidence.

## Cut / minimum credible submission

Cut spare seeds, cards 3–5, concurrent generation, second repair, multi-task benchmarking, and live generation. Do not cut the runnable CLI, one raw unedited Harbor package, pipeline summary, oracle/nop/base/mutation/selfcheck evidence, curated P2P, telemetry, replay, README limitations, or `validate_submission.py`.

Minimum credible: one pipeline invocation emits one parseable, self-contained package and summary; that raw output passes every gate and replays identically. If authorization/key arrives promptly, add a second capability-distinct package and k=3 evidence for the harder task.
