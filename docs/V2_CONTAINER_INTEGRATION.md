# Container integration report (executed 2026-11-14)

All runs below were **executed** on this branch under Docker. They used isolated copies; the
formal V1 packages were never modified. Afterwards, the isolated copy used for the organizer
check was compared with `track1_freestyle/generated_tasks/pallets__click-duration-param-type-9f8a40`
using `diff -r`: no differences.

Earlier sessions recorded "Docker daemon not running"; that blocker is historical. Docker Desktop
was started as a normal user application (no sudo, no service changes).

## Environment

| Item | Value |
|---|---|
| Host | macOS (darwin 24.1.0), Docker Desktop, engine 29.9.2 |
| Factory image | `localhost/t1-click-env:63288ad38b2a` (built from `factory/templates/Dockerfile.tmpl` in 44 s; `python:3.12-bookworm`, pytest 9.0.2) |
| Host Python | 3.13.5 (`/tmp/t1v2/venv313`); the factory needs ≥ 3.12 |
| Harbor | 0.25.0 (pinned in `requirements.txt`; scratch venv `/tmp/t1v2/harborvenv`) |
| Code | commit `8d54758684cc5d610f67445682e5de6b776d3e96` (factory integration run) |

## Part A — factory integration checks (`validation_tests/container_integration.py`)

These run the **factory's own gates** (`factory/gates.py`, `factory/container.py`), not the
organizer's harness. Command:

```bash
cd track1_freestyle
T1_ENGINE=docker T1_WORK=/tmp/t1v2/work /tmp/t1v2/venv313/bin/python \
  validation_tests/container_integration.py pallets__click-duration-param-type-9f8a40 bounds_exclusive
# exit 0; all cases as expected
```

Evidence: `track1_freestyle/evidence_v2/integration/20261114T150236_pallets__click-duration-param-type-9f8a40/`
(`summary.json`, `cases.json`, `mutation_gate.json`, `stdout.log`, and a directory per graded
run containing `applied.diff`, `container.log` and `verifier/` (`stdout.log`, `output.json`,
`grading_details.json`)).

Cases marked **fixture** are deliberate corruptions built from the isolated copy under `T1_WORK`.
They are labelled `test_fixture: true` in `cases.json`.

| Case | Fixture? | Expected | Hardened result | V1 logic on the same run | Recorded evidence |
|---|---|---|---|---|---|
| gold on the unmodified copy | no | accept | **accept** | accept | reward 1.0, 16/16 F2P, 37/37 P2P |
| nop (baseline) | no | accept | **accept** | accept | reward 0.0, every F2P `FAILED` in its own call, P2P 37/37 |
| expected F2P id that does not exist | yes | reject | **reject** | *accept* | `not_failed: {…::test_t1_fixture_does_not_exist: MISSING}` |
| feature test file fails to collect (module-level `SyntaxError`), nop | yes | reject | **reject** | *accept* | `collection/import errors: ['tests/test_duration_type.py']`; `pytest reported 1 error(s)` |
| same fixture, gold | yes | reject | **reject** | reject | same problems |
| behavioural mutant `bounds_exclusive` (historical) | no | killed | **killed** | killed | `killed_by.f2p: [test_bounds_inclusive]` |
| mutant = gold + `SyntaxError` in `src/click/types.py` | yes | invalid | **invalid** | *killed* | `parser produced no test records`; `no pytest summary line` |
| mutant whose patch does not apply | yes | invalid | **invalid** | survived | container exit **91**, `T1_STAGE_FAIL=apply_patch` |
| full suite, gold + feature tests | no | accept | **accept** | — | exit **0**; complete log (36 lines, ends with `2450 passed, 24 skipped, 31000 deselected, 1 xfailed`) |
| full suite, one feature assertion forced to fail | yes | reject | **reject** | — | pytest exit **1** → container exit **1**; complete log (102 lines, FAILURES section + summary) |
| full suite, feature file collection error | yes | reject | **reject** | — | pytest exit **2** → container exit **2**; complete log (ERRORS section + summary) |
| full suite, gold patch does not apply | yes | reject | **reject** | — | container exit **91**, `T1_STAGE_FAIL=apply_gold`, pytest never ran |
| full suite, test patch does not apply | yes | reject | **reject** | — | container exit **92**, `T1_STAGE_FAIL=apply_tests` |
| **V1 full-suite command**, failing-test fixture | yes | — | — | reject (tail text contained "failed") | container exit **0**: the status was masked by `| tail -3` |
| **V1 full-suite command**, collection-error fixture | yes | — | — | ***accept*** | container exit **0**; tail shows `1 error`, which V1 did not check |

"31000 deselected" is upstream's own `addopts = "-m 'not stress'"`; it is the same at base.

What this establishes in the real task image:

- Invalid execution (missing test, collection error, syntax error, patch failure) is **rejected**.
  It is never counted as "feature absent" (nop) or as a mutation kill.
- Patch failures and pytest failures propagate their **actual exit status** (0, 1, 2, 91, 92)
  through the POSIX-sh full-suite script, and the full pytest log is saved, not only a tail.
- Two V1 defects, previously shown only in unit tests, also occur in the container: the V1 nop gate
  accepts a missing test or a collection error, and the V1 full-suite command accepts a run whose
  feature tests never collected.

## Part B — organizer harness (separate from the factory gates)

`check_structure.py` and Harbor `selfcheck.sh` from `organizer/Track1-Coding/harness/`
(unmodified) were run on an isolated copy at `/tmp/t1v2/sc_copy/`. Evidence:
`track1_freestyle/evidence_v2/integration/organizer_selfcheck_duration/` (`check_structure.txt`,
`selfcheck.txt`, the Harbor trial directories under `sc/`, and `find_shim.sh`).

```bash
python3.13 organizer/Track1-Coding/harness/check_structure.py /tmp/t1v2/sc_copy/pallets__click-duration-param-type-9f8a40
# ✓ pallets__click-duration-param-type-9f8a40   exit=0
PATH=/tmp/t1v2/shim:/tmp/t1v2/harborvenv/bin:$PATH SELFCHECK_OUT=<evidence>/sc \
  bash organizer/Track1-Coding/harness/selfcheck.sh /tmp/t1v2/sc_copy/pallets__click-duration-param-type-9f8a40
#   oracle  reward=1.0   F2P=16/16 P2P=37/37
#   nop     reward=0.0   F2P=0/16 P2P=37/37
#   ✓ mechanically sound      ALL SOUND      selfcheck exit=0
```

Host notes (no organizer file was edited):

- The default `python3` on this host is 3.8.6 and has no `tomllib`, so `check_structure.py`
  exited 1 with `ModuleNotFoundError`. It was re-run with Python 3.13 (recorded in
  `check_structure.txt`).
- `selfcheck.sh` reads results with GNU `find -printf`, which macOS `find` lacks. A shim
  (`find_shim.sh`, placed first on `PATH`) emulates only the exact
  `find DIR -name PAT -printf '%T@ %p\n'` call and passes every other call to `/usr/bin/find`.
- Harbor recorded `task_checksum` `bbc4130f709c0b2e9b566f08f7c70b457c068e3e39c366b4d808997d1a7c7f73`
  for this V1 package.

## What was not checked

- Only one V1 task went through the full fixture set. The other four V1 tasks were not re-run
  here; PR #2 reports a Docker self-check for all five (not verified by me).
- Rootless Podman was not re-tested on this host.
- No model/agent run (benchmark blocked; see `docs/BENCHMARK_STATUS.md`).
