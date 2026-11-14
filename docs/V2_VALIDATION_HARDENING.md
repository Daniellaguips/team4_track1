# V2 validation hardening

Branch `v2/validation-hardening-collision-spec`, forked from the V1 preservation point.

## 1. Preservation point

| Item | Value |
|---|---|
| V1 commit | `327ecb61ede179e0e0f27ffc27bcc0b908a84794` (`main` = `origin/main` at start; working tree clean, nothing uncommitted) |
| Local tag | `v1-preservation-point` → `327ecb6` (annotated, not pushed) |
| Development branch | `v2/validation-hardening-collision-spec` |
| Submission ZIP | `track1_submission/TeamName_Track1.zip`, 3,584,863 bytes, SHA-256 `e0416ad52320419c49d70f3de2ee627ecaffd9ce20c1698a19d97e6bea8c1318`, `unzip -t` reports no errors. Not modified. |
| Ledger | `track1_freestyle/ledger.json`, SHA-256 `3f4906b7…184e`. Not modified. |
| Gap report | `docs/TRACK1_GAP_EXPLORATION_EN.md` does not exist in this checkout; nothing was read from it. |

Not modified on this branch: the five packages in `track1_freestyle/generated_tasks/`, `demo_tasks/`,
`runs/`, `dev_runs/`, `dev_tasks/`, `evidence/`, `ledger.json`, `pipeline_run.json`, and everything
under `track1_submission/`. The task templates `factory/templates/{grade.py,parser.py,test.sh}` are
also unchanged, so the verifier inside the shipped packages is byte-identical to what future
packages would get. Verify with:

```bash
git diff --stat v1-preservation-point -- track1_freestyle/generated_tasks track1_freestyle/demo_tasks \
  track1_freestyle/runs track1_freestyle/dev_runs track1_freestyle/dev_tasks track1_freestyle/evidence \
  track1_freestyle/ledger.json track1_freestyle/pipeline_run.json track1_freestyle/factory/templates \
  track1_submission
# expected: no output
```

New evidence lives only in `track1_freestyle/evidence_v2/`.

## 2. What the existing evidence does and does not show

- **Gold = 1.0** (historical, Podman + Harbor 0.25.0 on the original host): the reference patch makes
  every listed F2P test pass without breaking the listed P2P tests. It shows the reference solution
  is valid *against these tests*, nothing more.
- **Nop = 0.0 and mutation kills** (historical): the feature tests fail on the untouched base, and
  each listed wrong implementation fails at least one feature test. These are properties of the
  tests.
- **Neither shows difficulty.** Gold and nop/mutation results say nothing about how hard a task is
  for a model. That needs a benchmark (below).
- Nothing in section 2 was re-run on this branch. Re-classifying the *saved* outputs with the new
  gates (section 5) reads historical files offline; it is not a re-execution.

### 2a. Benchmark and Docker evidence, by provenance

An earlier draft of this document said "no model benchmark has run". That was true of the
evidence on this branch when it was written, but it is now outdated. The evidence falls into
three tiers.

**Historical (unchanged, kept as-is).** The V1 records on this branch were written when no
benchmark had been run. The V1 README marks the benchmark as blocked (no API key on the original
host), and V1 validation ran on rootless Podman because Docker was unavailable. Those files are
not edited; they are accurate records of that point in time.

**Reported by a teammate, not independently verified.**
[PR #2](https://github.com/tianluoboding/team4_track1/pull/2) is open and not merged (head
`team4-submission-ready` @ `934bf44c89623548e02ede57f74333be0aed4025`). It reports:

| Reported item | Value (from `track1_submission/team4_Track1/bench/benchmark_results_openrouter.json`) |
|---|---|
| Agent / model | `terminus-2` / `openrouter/anthropic/claude-haiku-5.5` |
| Harness | Harbor 0.26.0, engine `docker`, k = 3 |
| Result | resolve@3 = 3/3 on all five V1 tasks; 15 of 15 rollouts reward 1.0; reported total cost $0.17 |
| Docker validation | `evidence/docker/selfcheck_docker.txt`: oracle 1.0, nop 0.0, full P2P on all five tasks, `ALL SOUND` |

I read these files read-only through the GitHub API at that head SHA (no fetch, pull or merge) and
copied them to `track1_freestyle/evidence_v2/external/pr2/` with their source paths and sha256. I
did not rerun the benchmark or the Docker self-check. The PR contains the summary JSON only. It has
no per-rollout `trajectory/<iid>/<model>/rollout_N/` directories, no `result.json` with
`agent_info.model_info` and no per-rollout `reward.json`, so neither the individual rollouts nor the
exact model identity can be checked from the PR contents. The model was routed through OpenRouter.
Whether that matches the guide's required model id (`anthropic/claude-haiku-5-5`) should be
confirmed from the rollout `result.json` files if they exist.

**Independently verified on this branch.** One fact links the report to these tasks. All 60 files
of the five packages in PR #2 (`track1_submission/team4_Track1/generated_tasks/`) have the same git
blob hashes as the local `track1_freestyle/generated_tasks/`
(`evidence_v2/external/pr2/generated_tasks_blob_compare.txt`). The reported benchmark is therefore
about exactly the V1 packages preserved here. This branch does not change those packages or their
`grade.py`/`parser.py`, so the hardened factory gates cannot change the reported rewards. Nothing
else in the table above is verified by me.

**Implication if the report holds.** Under the benchmark guide's labels, resolve@3 = 3/3 is
"trivial". The V1 tasks are mechanically sound but easy for the benchmark model. This is a
difficulty finding, and it does not contradict the validity findings in this document: valid tests
and easy tasks are independent properties.

## 3. Defects confirmed in V1 (cited at `v1-preservation-point`)

### D1. Nop gate ignored its own completeness check — confirmed

`factory/gates.py:224-225`: `collected = all(n in st for n in f2p)` was computed and reported as
`f2p_all_reported`, but `ok` was only `reward == 0.0 and f2p_passed == 0 and p2p_passed == p2p_total`.
Because `grade.py` counts *passes*, any F2P outcome other than PASSED looks like "the feature is
absent". Regression tests show that V1 accepted, as a valid nop:

- an expected F2P id that never ran (missing record);
- a feature test file that is absent altogether;
- a feature test module that fails at collection with `ImportError`;
- a setup `ERROR` (missing fixture).

The factory README claimed nop required "*every* F2P reported FAILED (not missing/collection
error)". The code did not enforce that. A note now points to this document.

### D2. Full-suite exit status masked by `tail` — confirmed

`factory/pipeline.py:107-110` ran `… && python -m pytest … tests 2>&1 | tail -3`. The exit status of
a pipeline is the status of `tail`, so pytest's status was lost. `full_suite_gate` then searched the
last three lines for `(\d+) failed`. Regression tests (run under `/bin/sh` and `/bin/dash`) show V1
accepted:

- a collection error (`1 error` / `Interrupted` contains no "failed");
- zero tests selected (`no tests ran` / `N deselected`, pytest exit 5);
- pytest killed by `SIGKILL` mid-run (no summary line at all).

Patch-application failures *were* propagated (the `&&` chain short-circuits before the pipe), but
only as a bare non-zero status that did not say which step failed. Only the last 3 lines were kept,
so historical full-suite runs cannot be re-classified.

### D3. Mutants counted as killed by broken code — confirmed

`factory/gates.py:231`: `killed = reward is not None and f2p_passed < f2p_total`. A mutant that
fails to import (a syntax error in a module the tests import) makes every test file ERROR at
collection, so `f2p_passed` is 0 and V1 counted a kill. The same applies when the broken module is
imported lazily inside each test: pytest then reports call-phase `FAILED` with `SyntaxError`, which
V1 could not tell apart from a behavioural rejection. A mutant patch that does not apply gave
`reward = None` and was correctly *not* killed.

### D4. Parser totals and duplicate records trusted implicitly — hardening, no V1 false accept found

- `parser.py` de-duplicates by `(name, status)`, so one test can legitimately appear twice with
  different statuses (for example PASSED for the call and ERROR for teardown). `grade.py` and
  `container.grade` keep whichever record comes last. With pytest's `-rA` ordering ERROR is printed
  after PASSED, so V1 happened to score such a test as not passing. That outcome depends on
  report ordering, not on an explicit rule.
- `grade.py` builds its totals from `set(fail_to_pass.json)`, so duplicate ids in an expected list
  disappear silently. No gate compared the grader's totals with the expected lists.
- Gold acceptance had no concrete false-accept case. It is now routed through the same classifier
  so these properties are checked explicitly.

## 4. Fixes

| File | Change |
|---|---|
| `factory/container.py` | `grade()` keeps raw parser `records`, the verifier exit (`TEST_SH_EXIT`), a named patch-application failure (`T1_STAGE_FAIL=apply_patch`) and the verifier's full pytest log. `read_result()` loads a saved run from disk so historical runs can be re-classified offline. Adds `full_suite_script()`, a POSIX-sh script (no bash, no `pipefail`, no pipes) that writes the complete pytest output to a file, captures `$?` immediately, prints `T1_PYTEST_EXIT=<rc>` and a 3-line tail, and exits with pytest's status. `cd`, gold-apply and tests-apply failures exit 90/91/92 and print `T1_STAGE_FAIL=<step>`. |
| `factory/gates.py` | New `pytest_summary()`, `classify_run()`, `failure_exceptions()`, `mutant_verdict()`. `gold_gate`, `nop_gate` and `mutation_gate` now take the expected F2P **and** P2P lists. `full_suite_gate(p, log)` reads the saved log. |
| `factory/pipeline.py` | Passes `f2p, p2p` to the gates. The full suite runs `container.full_suite_script()` with a writable `/out` mount (`attempt_N/full_suite/pytest.log` + `container.log`). |
| `track1_freestyle/README.md` | Short V2 note under the gate list (V1 text left as written). |

The shipped task verifier (`grade.py`, `parser.py`, `test.sh`) is unchanged. All changes are on the
factory's acceptance side.

### Acceptance rules now enforced

`classify_run(r, f2p, p2p)` records a **problem** (the run cannot be read as a verdict) for any of:

| Check | Why |
|---|---|
| duplicate ids inside the expected F2P or P2P list; an id in both; empty F2P | `grade.py` would silently collapse them |
| `T1_STAGE_FAIL` present, `reward` null, verifier exit ≠ 0 | build/apply/setup failure, not a test result |
| no parser records | nothing was graded |
| a test reported more than once with the same status | corrupt or concatenated output |
| a file-level `ERROR` record (`tests/x.py`, no `::`) | collection/import error |
| no pytest summary line in the verifier log | crash, kill, or pytest never ran |
| summary reports `no tests ran`, any `error`, or contains `INTERNALERROR` / `Interrupted` / `ERROR collecting` | infrastructure-level failure |
| PASSED/FAILED record counts ≠ pytest's own `passed+xpassed` / `failed` | the parser dropped or invented results (SKIPPED/XFAIL records are not compared because the parser does not capture grouped skip lines) |
| `reward`, `f2p_passed/total`, `p2p_passed/total` ≠ values recomputed from the records and the expected lists using the documented reward rule | do not trust parser-provided totals |

Each expected test is assigned exactly one status: `PASSED`, `FAILED`, `ERROR`, `SKIPPED`, `MISSING`,
or `INCONSISTENT(A+B)` when it has records with several statuses.

| Gate | Accept iff |
|---|---|
| gold | no problems, reward 1.0, every F2P `PASSED`, every P2P `PASSED` |
| nop | no problems, reward 0.0, every F2P `FAILED` (call phase; not `MISSING`/`ERROR`/`SKIPPED`/`INCONSISTENT`), every P2P `PASSED` |
| mutant `killed` | no problems; every expected test is `PASSED` or `FAILED`; and at least one F2P `FAILED` whose FAILURES block raises nothing in {`SyntaxError`, `IndentationError`, `TabError`, `ImportError`, `ModuleNotFoundError`} |
| mutant `invalid` | any problem, any expected test not PASSED/FAILED, or the only F2P failures are import/syntax errors |
| mutant `survived` | valid run, every F2P passes |
| mutation gate | at least one mutant, and every mutant `killed` |
| full suite | no `T1_STAGE_FAIL`, `T1_PYTEST_EXIT=0`, container exit 0, summary line present, ≥1 passed, 0 failed, 0 errors, no crash markers |

The nop rule deliberately allows `ImportError`/`AttributeError` *inside a test function*. A test that
imports the not-yet-existing feature is the normal way a feature test fails at base. It must not
fail at collection, though, because that is indistinguishable from a broken test module.

## 5. Checks executed on this branch

All run locally on macOS (arm64), no containers. Logs are in `track1_freestyle/evidence_v2/logs/`.

| Check | Result | Log |
|---|---|---|
| Regression tests, Python 3.11.13, `/bin/sh` (bash 3.2 in POSIX mode) | 44 passed | `validation_tests_sh.log` |
| Same, `T1_TEST_SH=/bin/dash` | 44 passed | `validation_tests_dash.log` |
| Same, Python 3.13.5 + dash | 44 passed | `validation_tests_py313_dash.log` |
| Full factory import (`factory.pipeline`, all 5 families) on Python 3.13.5 | ok (on 3.11 `families/duration.py` fails to import: it uses 3.12+ f-string syntax; pre-existing, not changed) | — |
| Offline re-classification of every saved gold/nop/mutant run (V1 batch, demo, dev runs) | see below | `replay_historical.json` |

Re-classification of saved runs (historical files, new logic; nothing re-executed):

- **All 5 V1 tasks and the demo task:** gold, nop and mutation still accepted; every mutant `killed`;
  no problems. The parser-vs-pytest-summary count check holds on every saved run.
- **Dev candidates:** the new verdicts match the historical `gates.json` in every case where a
  historical verdict exists. Rejected dev candidates stay rejected for the same reasons: one F2P
  passing at nop, or mutant `no_dedup` surviving. One dev attempt
  (`dev_runs/20261114T114902_dev2_attempts`) has no historical mutation entry to compare against.
- Full-suite runs cannot be re-classified (V1 kept only 3 lines).

The regression tests are in `track1_freestyle/validation_tests/`:

- `test_validation_gates.py` — **synthetic fixtures**. Real pytest 9.0.2 runs small made-up
  modules (not click). The output is graded by the real template `grade.py` + `parser.py` and loaded
  with `container.read_result`. Each defect test also asserts what V1's logic (copied verbatim into
  the test file) decided, so the defect is demonstrated rather than asserted. This is **not Harbor
  evidence**.
- `test_historical_replay.py` — real saved V1 outputs, re-classified offline.

Coverage of the required scenarios:

| Required scenario | Test(s) |
|---|---|
| Correct Gold / Nop | `test_gold_correct_is_accepted`, `test_nop_correct_is_accepted`, `test_v1_saved_runs_still_accepted[*]` |
| Missing F2P records | `test_nop_rejects_missing_f2p_record`, `test_nop_rejects_absent_feature_test_file` |
| Collection / import errors | `test_nop_rejects_collection_import_error`, `test_nop_rejects_setup_error` |
| Incorrect / inconsistent totals | `test_tampered_grader_totals_are_rejected`, `test_duplicate_expected_ids_are_rejected`, `test_overlapping_f2p_p2p_is_rejected`, `test_parser_dropping_records_is_detected`, `test_repeated_identical_records_are_rejected`, `test_pass_plus_teardown_error_is_inconsistent` |
| P2P regression | `test_nop_rejects_p2p_regression` |
| Full-suite failure hidden behind successful output processing | `test_full_suite_failure_hidden_by_tail_is_caught[collection_error\|zero_tests\|crash]`, `test_full_suite_test_failure`, `test_full_suite_patch_failure_is_propagated[gold\|tests]`, `test_full_suite_unwritable_log_is_propagated` |
| Successful full suite | `test_full_suite_success` |
| Mutant behavioural failure vs invalid execution | `test_mutant_behavioural_failure_is_killed`, `test_mutant_lazy_import_behavioural_failure_is_killed`, `test_mutant_syntax_error_at_import_is_invalid`, `test_mutant_lazy_import_syntax_error_is_invalid`, `test_mutant_that_did_not_apply_is_invalid`, `test_mutant_survivor_is_reported`, `test_mutation_gate_needs_every_mutant_killed` |
| No verdict without grading | `test_missing_grading_result_and_bad_verifier_exit`, `test_patch_apply_failure_is_reported` |

## 6. Not executed: container integration

Docker CLI 29.9.2 is installed, but the Docker daemon was not running. Docker Desktop was launched once
(user-level `open -a Docker`, no sudo). It exited without starting a daemon; it may need first-run
interaction in its GUI. Podman and Harbor are not installed. **No container or Harbor check was run
on this branch.** Specifically unverified:

- `container.grade()` and `full_suite_script()` inside the real `python:3.12-bookworm` task image;
- the new `/out` bind mount under Docker Desktop or rootless Podman;
- a full `python -m factory generate` run with the hardened gates.

PR #2 reports a Docker run of the organizer `selfcheck.sh` on the five V1 packages (section 2a). If
that report holds, it confirms that the V1 packages work under Docker. It does not exercise this
branch's code: `selfcheck.sh` runs Harbor with each package's own `grade.py`, not the factory gates
in `factory/gates.py`/`container.py`. The three items above therefore remain unverified. The
daemon was rechecked at the end of this session and was still not reachable.

Commands, once an engine works (writes only to `evidence_v2/integration/<timestamp>_<task>/` and a
scratch copy under `$T1_WORK`):

```bash
cd track1_freestyle
python3.13 -m venv /tmp/t1venv   # any Python >= 3.12 (families/duration.py needs 3.12+ syntax)
T1_ENGINE=docker /tmp/t1venv/bin/python validation_tests/container_integration.py \
    pallets__click-duration-param-type-9f8a40 bounds_exclusive
# expected summary: gold, nop, mutation, full_suite_under_gold all true

# Organizer self-check on an isolated copy (does not touch generated_tasks/):
mkdir -p /tmp/t1_selfcheck && cp -R generated_tasks/pallets__click-duration-param-type-9f8a40 /tmp/t1_selfcheck/
SELFCHECK_OUT=evidence_v2/integration/harbor_selfcheck \
    ../organizer/Track1-Coding/harness/selfcheck.sh /tmp/t1_selfcheck/pallets__click-duration-param-type-9f8a40
```

## 7. What these checks cannot establish

- **Difficulty.** Nothing on this branch measures model performance. The only difficulty evidence
  is the benchmark reported in PR #2 (resolve@3 = 3/3 on all five V1 tasks; section 2a), which I
  have not independently verified.
- **That a nop FAILED means "feature absent".** The gate guarantees each F2P was collected and
  failed in its own call, while the P2P set (same click import, same harness) is green. The gold run
  shows the same tests pass once the gold patch is applied. Together these are strong
  circumstantial evidence, not proof: a test could fail at base for an unrelated reason that the
  gold patch also happens to fix. Failure reasons in the `-rA` summary are truncated (`- Attr...`),
  so they are not used for gating.
- **Semantic mutant quality.** A "killed" mutant was rejected by an assertion or exception in a
  feature test. Whether that mutant is a *realistic* wrong implementation is a human judgement. The
  import/syntax exclusion is a fixed list of exception types, not a semantic analysis.
- **Fairness.** Whether the spec states everything the tests check is judged by the existing
  static lint plus human reading. The validation gates do not cover it.
- **Novelty.** The novelty gate greps upstream `src/` and searches GitHub PR titles. It cannot show
  the capability is absent from the wider ecosystem (third-party extensions, forks, unindexed code).
- **Stability.** Each gate runs once; flakiness is not measured.
- **Shell portability beyond dash/bash.** Verified with bash 3.2 (POSIX mode) and dash. In
  production `container.run` still invokes the script with `bash -c` (the image ships bash). The
  script itself uses no bash features, so it also runs under the image's `/bin/sh` (dash on Debian
  bookworm), but that image was not run here.
