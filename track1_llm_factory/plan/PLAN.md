# Track 1 plan — v6.2 (contradiction-free merge). Target ≥ 8.5/10 from Fable 5.2 AND Codex frontier.

Ratings: v3 6.5 (Codex) · v4 7.1 (Fable) / 7.7 (Codex) · v5 7.9 (Fable) · Codex frontier's clean
replacement 8.7. v6 = v5.1 + every Codex 13:04 delta. Upload by **3:15 PM** (deadline 3:30).

## 0. Gate 0 — founder decision; secrets
Build starts only when Daniella says "build". Keys are **environment-only, never persisted**:
Daniella runs `./run.sh` in her own terminal; it asks for each key with hidden input (`read -s`)
and exports it only into that process. No key file anywhere; nothing in repo, ZIP, logs, argv,
Dockerfiles or task.toml.

## 1. Fixed settings (decided now, never changed after a rollout → stable task checksums)
`network_mode = "public"`, agent `timeout_sec = 900`, verifier 900, click 8.5.1 @ cf19179e,
image digest recorded. **Harbor: kit docs target 0.25.x; we use local 0.26.0** because the
reference package already passes selfcheck on it (oracle 1.0 / nop 0.0); recorded in README.
Model ids confirmed by a 1-token call at T+0.

## 2. Pipeline — `factory.generate --card <card> --seed <n>`
Deterministic code owns all Harbor plumbing (reference ByteSize package = template only, never
submitted, never benchmarked). temperature 0, prompts hashed, grounding cached. Every candidate
is snapshotted before validation; every repair is a new attempt.

| # | Stage | Pass condition |
|---|---|---|
| 1 | Pick (code) | card × seed → the card's pre-verified blueprint (§4). |
| 2 | Design → **frozen contract** (Sonnet 5.5) | 10–12 rules R1..Rn, ≥3 stated cross-rule interactions, exact error strings, ≥2 traps from the catalog. Each rule = contract row: input domain, output, exception type+message, precedence/order, bounds, state-reset. The contract is frozen after this stage. |
| 3 | Novelty (code) | git grep/log on upstream main + extension denylist. Hit → reject candidate. |
| 4 | Spec + gold (Sonnet) | instruction.md states every contract row + examples. Gold applies; **targeted smoke** (touched-module tests) green. |
| 5 | Tests, blind (Sonnet) | From instruction.md only; each test named test_r<N>_*. |
| 6 | Fairness | (a) code: test↔rule coverage both ways; (b) code: expected-output/exception literals appear verbatim in instruction.md (input fixtures exempt); (c) LLM blind judge (instruction + tests only): a test that **exceeds the frozen contract → repair the test**; the **spec is repaired only when it omitted text the contract already approved** — within the repair cap; an **unresolved contradiction or unstated dependency rejects the candidate** [Codex v6.1]. |
| 7 | Soundness (docker) | F2P = fail at base & pass at gold, ≥12; **nop reward exactly 0.0** and P2P green (asserted by our checker); oracle 1.0. ≤2 targeted repairs (named test ids + diagnostic). |
| 8 | Mutation (code) | **≥1 clean semantic corruption** of the actual gold (applies, imports, P2P green, ≥1 F2P fails). Mirrors the judges' gate. Model-written wrong impls = diagnostics. |
| 9 | Freeze (code) | **Full suite once** at base and gold; check_structure + Harbor selfcheck; checksum recorded. |
| 10 | Telemetry | calls.jsonl: model id/version, prompt hash, raw request/response, seed, base commit, uv.lock hash, Docker digest, tool versions, task checksum. pipeline_run.json: per task + `first_pass_valid / attempted` (failures included); $ and tokens per valid task. `--replay` rebuilds byte-identically; fresh reruns are comparable, not identical (stated). |

No same-model probe/harden loop: tasks are never selected or reshaped using Haiku results, so the
reported resolve@3 is unbiased. Hardness comes from the design (rule count, interactions, traps).

## 3. Hardness evidence — official k=3 only
Each frozen task: terminus-2 + anthropic/claude-haiku-5-5, k=3, launched as it freezes. **Max 3
containers at once** until capacity is proven (then up to 6). Last launch by 2:35 (900 s timeout).
All k or none; verify the real model in result.json and the checksum; rerun infra failures,
timeouts count. Report every rollout.
**Redesign path [Fable v6]:** if a task's official k=3 returns 2/3 or 3/3 before 2:10, regenerate
that card once as a NEW task (seed+1, 2–3 added cross-rule interactions) and benchmark it with a
fresh k=3. **The original task is automatically retired; the seed+1 replacement is submitted if
valid, regardless of its own k=3** (no post-hoc selection); if the replacement fails validation, the
original is kept [Fable v6.2]; both results disclosed, all rollouts of
the submitted task kept [Codex v6.1]. (Fresh task + fresh rollouts → no reuse of probed evidence; benchmark guide: 3/3 = "redesign
harder".)

## 4. Cards — 5 capability axes, one pre-verified blueprint each (+ backup)
| Card | Axis | Blueprint | Backup |
|---|---|---|---|
| types | value parsing + exact arithmetic | `click.Duration` (`1h30m`→seconds; unit order, duplicates, overflow, bounds) | Ratio/percent with exact fractions |
| argv | argv rewriting, recursion, file I/O | `@response-file` expansion (quoting, comments, nesting limit, cycle error) | unique-prefix long-option abbreviation |
| testing | stateful harness bookkeeping | `Result.env_changes` (env diff across invoke, isolation) | `Result.files_created` |
| help | output layout contract | `examples=` section rendering (alignment, wrapping, ordering) | — |
| completion | candidate filtering + ranking | subsequence matching mode with ranking + tie rules | — |
Dropped as not novel (verified upstream): case-insensitive Choice completion, help `col_max` cap,
ByteSize clone. Write-up: variation matrix (modules × behavior class × state × I/O) + rule-text
near-duplicate check.

## 5. Regression
Before gold generation, pin named upstream node ids per card covering each changed public behavior
and adjacent compatibility path, one-line rationale each (P2P table in README). Same set at base and
gold; full suite once at freeze. Never drop a test after seeing results.

## 6. Efficiency
Per card: ≤3 generation calls + ≤2 targeted repairs; token ceilings logged; targeted smoke during
generation, full suite once at freeze; **$4 hard cap per card**. No reference-task benchmark.
Budget ≈ $20 generation + ≈ $25 benchmarks of $100.

## 7. Schedule, owners, checkpoints (go ≈ 1:10 PM)
| Time | Claude | Codex |
|---|---|---|
| 1:10–1:25 | unit tests (parse/apply/coverage/literal checks); offline replay fixture through generate | checker: nop==0.0, mutation, P2P pinning; verify() green on reference |
| 1:25–1:40 | `types` card live | benchmark runner ready |
| **1:40** | **Checkpoint A: first valid task** (else fix pipeline before more cards) | launch its k=3 |
| 1:40–2:15 | `testing`, `argv`, then `help`, `completion` (≤3 containers at once) | freeze + launch k=3 as each passes |
| **2:15** | **Checkpoint B: ≥3 valid** | |
| **2:30** | **Hard freeze.** <5 valid → submit what is valid, honestly; never skip validation | last k=3 launch by 2:35 |
| 2:30–2:55 | README (all sections), variation write-up, P2P table, limitations, contributions | benchmarks finish; trajectory/ layout; checksum audit |
| 2:55–3:10 | validate_submission.py: **0 errors, 0 unexplained warnings**; ZIP; re-validate from a clean checkout | independent ZIP check |
| 3:10–3:15 | **upload**; 3:15–3:30 buffer + demo rehearsal | |

## 8. Demo (10 min)
Start a fresh live `generate` of a proven card at minute 0 (image pre-built); narrate the pipeline
on a submitted run meanwhile (gates, mutation rejection, selfcheck table, pipeline_run.json, a Haiku
failure trajectory, variation matrix, limitations); end on the live run's result. Fallback:
`--replay` of a submitted run.

## 9. Known limits
Plan text cannot prove hardness — only measured resolve@3 can. Temperature 0 is not full
determinism (hence replay). Harbor 0.26 vs kit-documented 0.25.x (recorded above).

---
CO-SIGNED: claude (v6.2) + codex (v6.2, CHAT 13:12) · Ratings: Codex frontier 8.7/10 · Fable 5.2 8.0/10 (signs as build plan; says 8.5 needs measured results)
