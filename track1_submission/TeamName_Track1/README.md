# Track 1 — AI Task Factory: `pallets/click` blueprint factory

A reusable pipeline that turns `pallets/click` at a pinned commit into Harbor 0.25 feature tasks,
validates each one through nine gates, and records full provenance. This submission contains the
pipeline, the 5 generated packages, their validation evidence, a freshly generated demo task, and a
benchmark runner whose execution was **blocked** (no organizer model key on this host).

| | |
|---|---|
| Repository | `pallets/click` (BSD-3-Clause), https://github.com/pallets/click |
| Base | tag `8.5.1` = `cf19179e8e2fd54c601378cec9e0d21bb12b6fb1` (upstream `main` checked at `e38188e9e205005d5af5f9e59df51904c984586a`) |
| Environment | `python:3.12-bookworm`, pytest 9.0.2 (+ pluggy 1.6.0, iniconfig 2.3.0, packaging 26.0, pygments 2.20.0); base suite: 2434 passed, 0 failed |
| Harbor | 0.25.0 (pinned in `requirements.txt`) |
| Generator model | none — deterministic blueprints, 0 model calls, $0 |

## Status at a glance

| Item | Status |
|---|---|
| Pipeline (generate → curate → package → 9 gates → provenance) | implemented, run |
| 5 packages, first-pass yield of the frozen pipeline | 5/5 accepted, 1 attempt each (`runs/20261114T115550_batch5/`) |
| Organizer `check_structure.py` | 5/5 pass (`evidence/check_structure.txt`) |
| Organizer `selfcheck.sh`, real Harbor 0.25.0 | 5/5 oracle 1.0, nop 0.0, P2P full — `ALL SOUND` (`evidence/selfcheck.txt`) |
| Fresh task demo | generated and validated (`demo_tasks/`, `evidence/demo_*`) |
| Benchmark (terminus-2, `anthropic/claude-haiku-5-5`, k=3) | **blocked: no `ANTHROPIC_API_KEY`**; runner implemented, not executed; **difficulty unproven** |

## Submission layout

```
generated_tasks/            the 5 Harbor packages (the deliverable)
pipeline_run.json           telemetry, one row per package
factory/ bench/ infra/      pipeline, benchmark runner, rootless-podman helpers
vendor/                     verbatim organizer files + sha256
ledger.json                 knob vectors already generated (batch + dev)
evidence/                   check_structure / selfcheck logs, dev_history.json, clean_repro/, demo_*
archives/runs.tar.gz        runs/ (batch, demo), dev_runs/, demo_tasks/, Harbor selfcheck trial dirs
```
Run directories and the demo task are archived because they contain package copies (`task.toml`)
that `validate_submission.py` would otherwise count as extra tasks. `tar xzf archives/runs.tar.gz`
restores them in place.

**Clean reproduction:** a fresh `git clone` + fresh venv + empty `T1_WORK` regenerated the batch
(`--n 5 --seed 2026`): 5/5 accepted first pass in 258 s, `diff -r` against `generated_tasks/`
identical (`evidence/clean_repro/`). The container image cache was shared, so the image build
itself was not re-done in that run.

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Harbor 0.25.0; pipeline is stdlib-only
# Docker host: nothing else. Engine for the factory's own gates: T1_ENGINE=docker
export T1_ENGINE=docker            # default is podman
export T1_WORK=/tmp/t1_factory_work
```

This host could not reach the Docker daemon socket (`permission denied`, no sudo), so everything was
run with **rootless Podman** via `infra/env.sh` (local tmpfs storage, user-level API socket for
docker-compose, short-name registry config) and the shim `infra/bin/harbor`, which only appends
`-e podman` to `harbor run` so the organizer `selfcheck.sh` runs unmodified. On a Docker host skip
`infra/` entirely.

```bash
source infra/env.sh                # only on hosts like this one
```

## Generate tasks

```bash
.venv/bin/python -m factory plan --n 5 --seed 2026                      # show what would be generated
.venv/bin/python -m factory generate --n 5 --seed 2026 --out generated_tasks --runs runs --label batch5
# a FRESH task: the ledger lists every knob vector already generated; the planner skips them
.venv/bin/python -m factory generate --n 1 --seed 7 --ledger ledger.json --out demo_tasks --runs runs --label demo_fresh
# one specific variant
.venv/bin/python -m factory generate --family duration \
    --knobs '{"units":"wdhms","order":"descending","bare_number":"reject"}' --out my_tasks
.venv/bin/python -m factory telemetry --runs runs/*_batch5 --tasks generated_tasks --out pipeline_run.json
```

Each candidate leaves `runs/<run>/candidates/<iid>/` with `raw_draft/` (first-pass spec + tests),
`attempt_N/` (package, `gates.json`, gold/nop/mutant grader runs with logs, `novelty.json`,
`p2p_rationale.json`) and `record.json` (knobs, code version, attempts, repairs, verdict).

## Structure check and Harbor oracle/nop

```bash
K="path/to/Track 1 - Coding/harness"          # or vendor/harness (verbatim copy)
python3 "$K/check_structure.py" generated_tasks/*
SELFCHECK_OUT=./sc bash "$K/selfcheck.sh" generated_tasks/*
python3 "$K/validate_submission.py" TeamName_Track1.zip
```

## Benchmark

```bash
export ANTHROPIC_API_KEY=...        # organizer key, environment only
BENCH_BUDGET_USD=60 HARBOR_ENV=podman .venv/bin/python bench/run_benchmark.py generated_tasks/*
```
`bench/run_benchmark.py` runs `harbor run -a terminus-2 -m anthropic/claude-haiku-5-5 -k 3` per task
(each rollout is a fresh Harbor trial), computes resolve@3 = resolved graded rollouts / graded
rollouts (resolved = reward 1.0, not pass@k), excludes and re-runs infrastructure failures
(reward null, environment/API/rate-limit/truncation errors; agent timeouts count as misses), keeps
every rollout, writes `trajectory/<iid>/claude-haiku-5-5/rollout_N/` and stops at the budget. On
this host it recorded `bench/benchmark_status.json: blocked` and exited 3. **No resolve@k number in
this submission is real; none is reported.** It was also never run end to end, so a first real run
may surface integration problems (e.g. terminus-2 setup in the task image).

## The five tasks

| Task | Capability / module | Knobs of this instance | F2P | P2P | Mutants killed |
|---|---|---|---:|---:|---:|
| `duration-param-type-9f8a40` | new `click.Duration` ParamType (`types.py`) | units `wdhms`, any order, digits = seconds | 16 | 37 | 8/8 |
| `group-command-abbreviations-583fa0` | prefix dispatch in `Group.resolve_command` | hidden included, alphabetical ambiguity list | 12 | 21 | 8/8 |
| `help-command-sections-56c8e3` | help sections in `Group.format_commands` | alphabetical sections, default section last | 10 | 37 | 6/6 |
| `option-conflicts-with-921c06` | `Option(conflicts_with=)` checked in `Command.parse_args` | env counts as provided, report all pairs | 12 | 48 | 7/7 |
| `prompt-max-attempts-ac2a26` | retry budget in `termui.prompt/confirm` + `Option` | empty answers free, give up with `UsageError` | 12 | 39 | 8/8 |

See `VARIATION_WRITEUP.md` for the variation strategy.

## Gates (per candidate, `gates.json`)

1. **structure** — organizer `check_structure.check()` + `base_commit`/`docker_image` checks (static).
2. **base_health** — full existing suite in the task image at base: 2434 passed / 0 failed (container).
3. **grounding** — every gold edit is anchored on text occurring exactly once at base; gold modifies
   existing `src/click` files; touched/focus symbols exist (static).
4. **novelty** — feature probes absent from `src/` at base and at upstream `main`, `git log -G`
   over base..main, GitHub PR search (results in `novelty.json`) (network).
5. **fairness_lint** — every test cites requirement IDs, every requirement is tested, every
   asserted message is assembled from spec text + test-supplied values, every public name/keyword
   used is in the spec (static; plus manual reading of all specs).
6. **isolation** — spec names no tests/harness files and quotes ≤2 gold lines; Dockerfile copies
   nothing; the image has no `/solution`, `/tests`, feature test files, upstream history (static + container).
7. **gold** — package grader with gold applied: reward 1.0, F2P n/n, P2P m/m (container).
8. **nop** — base: reward 0.0, *every* F2P reported FAILED (not missing/collection error), P2P m/m (container).
9. **mutation** — 6–8 plausible wrong implementations per task; each must fail ≥1 F2P (container).
   Extra: entire existing suite + feature tests under gold (0 failures).

Gates 7–9 run the package's own `tests/test.sh` in the image built from its own Dockerfile; the
organizer `selfcheck.sh` then repeats 7–8 through real Harbor.

Regression (P2P) curation: once per base, the suite runs under coverage with per-test contexts; for
every function enclosing a gold hunk plus the blueprint's declared focus symbols, the 12 tests that
execute most of its lines are kept (cap 90, only base-green, ids without spaces). Rationale per test
in `p2p_rationale.json`.

## Reliability, provenance and human intervention

- **Frozen-pipeline batch:** 5/5 first-pass valid, 0 repairs, 0 human edits after generation.
- **Development history before the freeze** (`evidence/dev_history.json`, raw in `dev_runs/`):
  9 candidates, 4 accepted. Failures found and fixed **in the pipeline/blueprints** (never by
  editing a package): fairness lint too literal; two feature tests that already passed at base;
  one equivalent mutant; one ambiguous mutant anchor. The batch's knob vectors were not among the
  vectors exercised during development.
- One demo generation was started with a knob vector that had been used during development; it was
  aborted and deleted, the ledger was extended with dev vectors, and the demo was re-run.
- Hand-written (pre-designed): the five blueprints (spec templates, gold templates, tests, mutants,
  knob spaces), the Dockerfile template. Generated by the pipeline: concrete specs/golds/tests for a
  knob vector, all diffs, P2P sets, run scripts, packages, gate evidence.
- Reused verbatim from the organizer kit: `tests/grade.py`, `tests/parser.py`, `tests/test.sh`
  (example task) and `vendor/harness/` (hashes in `vendor/REUSED_SHA256.txt`).

## Cost and time

No model was called: 0 tokens, $0 of the OpenRouter and Anthropic allocations. Per-task wall time
in `pipeline_run.json` (41–66 s, excluding the shared one-time image build ≈20 s and coverage
index ≈35 s). Build window used: ≈11:16–12:20 local for the pipeline, tasks and validation.

## Limitations

- **No benchmark** → hardness is not demonstrated. Specs are deliberately rule-dense, but a model of
  claude-haiku-5-5's class may well solve some of them.
- No LLM generation: new *capabilities* require a human to write a blueprint; the factory produces
  new *variants* (20 knob vectors) automatically. The demo task differs from a batch task in one
  rule (default-section position).
- Novelty is checked against `src/`, upstream `main` and GitHub PR search; upstream docs contain a
  user-land `AliasedGroup` recipe related to the abbreviation task (recorded in its axes note).
- The fairness lint is heuristic; it was backed by reading every generated spec once.
- `CommandCollection.list_commands` got no P2P test from coverage curation.
- Validated with rootless Podman (Harbor `-e podman`), not Docker. The Dockerfile unpacks
  `tmux`/`less` .debs without maintainer scripts so it also builds without subuid mappings.
- `network_mode = "public"` (benchmark agents need egress per the guide); answers are not reachable
  over the network since the features do not exist upstream.

## Material conflicts noted

- The assignment .docx ("Additional submission details") mentions *resolve@5 / five rollouts*;
  `benchmark_guide.md`, `harbor_quickstart.md` and the brief all say k=3 → k=3 used.
- `harbor_task_interface.md` says the grader resets test paths with `git checkout`; the example
  `grade.py` deletes them instead. Feature tests are always new files, so both behave identically.

## Team

Single contributor (AI coding agent operating on the user's workspace); no other members.
