# V2 collision task: generation and validation report

Task: **`pallets__click-command-collection-providers-55a649`**, in
`track1_freestyle/generated_tasks_v2/`. V1's `generated_tasks/`, `runs/`, `ledger.json` and
`pipeline_run.json` were not touched. V2 output lives in `generated_tasks_v2/`, `runs_v2/`,
`ledger_v2.json` and `pipeline_run_v2.json`.

Status: **valid by every factory gate and by the organizer self-check. Not benchmarked**
(blocked; see `docs/BENCHMARK_STATUS.md`). Nothing here shows the task is hard.

## Generation mechanism (stated plainly)

- This is a **manually authored sixth blueprint** (`factory/families/collisions.py`), not
  autonomous feature discovery. The feature was chosen by the investigation and settled in
  `docs/COMMAND_COLLISION_DECISIONS.md`.
- **LLM use.** The blueprint code (instruction text, anchored gold edits, feature tests,
  compatibility tests, mutants) was written in a Cursor agent session with an LLM coding assistant
  (Claude). **Generation itself makes no model call** (`model_calls: 0`, $0); the pipeline is
  deterministic.
- **Reused components.** The V1 pipeline, the V2-hardened gates, the V1 templates (`grade.py`,
  `parser.py`, `test.sh`, `Dockerfile.tmpl`), coverage-based P2P curation, and the novelty,
  fairness and isolation gates.
- **New factory parts** (commits `77d7c5c`, `8d54758`): authored-compatibility test category,
  `declared_p2p`, the `test_categories` gate, P2P-aware mutation verdicts, and an explicit-only
  family registry.
- The package was produced only by `python -m factory generate`. The shipped directory is
  byte-identical to the pipeline's accepted attempt (`diff -r` against
  `runs_v2/20261114T150004_v2_collisions/.../attempt_1/package/...`), and
  `human_edits_after_generation` is `[]`.

## Generation history (both runs kept)

| Run | Code | Result | Failing gates | What was repaired in the generator |
|---|---|---|---|---|
| `runs_v2/20261114T145647_v2_collisions` | `77d7c5c` | **rejected** | `fairness_lint`, `full_suite_under_gold` | (1) A test passed `reverse=`, a keyword the spec does not name; rewritten without it. (2) The gold imported `dataclasses` into `click.core`, which broke upstream `tests/test_imports.py::test_light_imports`. Coverage curation had not selected that test; only the full-suite gate caught it. The record is now a `typing.NamedTuple` (no new import); the test is added as a declared upstream P2P; a mutant (`heavier_import`) checks that it is enforced |
| `runs_v2/20261114T150004_v2_collisions` | `8d54758` | **accepted** | none | — |

The blueprint yield is 1 accepted out of 2 pipeline runs. The second run's `first_pass_valid:
true` refers to that run only. `pipeline_run_v2.json` lists both rows; `ledger_v2.json` records the
knob vector once per run.

Resources: 66.0 s and 68.1 s wall time per candidate (warm image; the first run also built the
coverage index), 0 model calls, 0 tokens, $0.

## Package contents

| Part | File(s) | Content |
|---|---|---|
| Requirements | `instruction.md` (866 words) | R1–R10 as decided; public names stated verbatim; example |
| Reference patch | `solution/patch.diff` | `src/click/core.py` (`CommandProvider` NamedTuple, two methods) and `src/click/__init__.py` (export) |
| Feature tests (F2P) | `tests/test_command_collection_providers.py` via `test_patch.diff` | 18 tests |
| Upstream regression (P2P) | `pass_to_pass.json`, provenance `upstream_regression` | 31 pre-existing tests: 30 from coverage curation on 8 focus symbols, plus 1 declared (`test_imports.py::test_light_imports`) |
| Authored compatibility (P2P) | `tests/test_command_collection_compat.py`, provenance `authored_compatibility` | 6 new tests pinning R10; pass at base and under gold |
| Provenance | `tests/p2p_provenance.json` | splits `pass_to_pass.json` into the two categories (grade.py ignores it) |
| Mutants | `runs_v2/.../attempt_1/mutants.json` | 21 (below) |
| Environment and metadata | `environment/Dockerfile`, `task.toml` | V1 template, pinned base `cf19179e`, `network_mode = "public"` |
| Provenance and resources | `runs_v2/.../record.json`, `p2p_rationale.json`, `novelty.json`, `gates.json`, `pipeline_run_v2.json` | knobs, code version, blueprint origin, per-gate details, timings |

## Validation results (accepted run)

| Check | Kind | Result |
|---|---|---|
| Structure (vendored `check_structure.py` + base/image fields) | static | pass, 0 errors, 0 warnings |
| Test categories | static | pass: F2P 18, upstream P2P 31, authored P2P 6; F2P only from the feature file, authored only from the compatibility file, upstream ids pre-existing and `PASSED` at base |
| Base health (full suite at base in image) | container | 2434 passed, 0 failed |
| Grounding | static | modifies existing `src/click/core.py`, `src/click/__init__.py`; anchors resolve exactly once |
| Novelty | network | no probe hit at base or `main` `e38188e9`; GitHub PR search ran without errors; 0 merged hits |
| Fairness lint | static | 0 problems; every R1–R10 exercised |
| Isolation | static + container | 0 problems (no test names/paths in spec; image has no `/tests`, `/solution` or test files; one-commit `/app`) |
| Gold | container | reward 1.0; 18/18 F2P `PASSED`; 37/37 P2P `PASSED`; no problems |
| Nop | container | reward 0.0; 18/18 F2P `FAILED` in their own calls (`AttributeError`, no collection errors); 37/37 P2P `PASSED` (incl. the 6 authored); no problems |
| Mutation | container | 21/21 killed (table below); 0 invalid, 0 survived |
| Full suite under gold | container | pytest exit 0: 2458 passed, 24 skipped, 1 xfailed, 0 failed, 0 errors |
| Organizer `check_structure.py` | organizer | ✓ (`evidence_v2/collision_task/check_structure.txt`) |
| Organizer `selfcheck.sh` (Harbor 0.25.0, Docker) | organizer | oracle 1.0, F2P 18/18, P2P 37/37; nop 0.0, F2P 0/18, P2P 37/37; `ALL SOUND` (`evidence_v2/collision_task/selfcheck.txt`) |
| Determinism | container | gold and nop each graded twice more: identical per-test statuses (`determinism.json`) |

Harbor `task_checksum` of the frozen package: `76aa9a95bc79a4c4300bb677af3d592443465112fa019aceac08ca6544573d55`.
File manifest with sha256: `evidence_v2/collision_task/package_manifest.json`.

### Mutants

| Mutant | Caught by |
|---|---|
| `local_omitted`, `local_after_sources`, `sources_reversed`, `active_provider_only`, `merges_same_object`, `collision_by_provider_count`, `collision_by_listing_groups`, `hidden_filtered`, `cached_per_name`, `reads_commands_mapping`, `applies_chain_check`, `one_based_index`, `swallows_source_errors`, `warns_on_collision`, `sorts_collision_names`, `expands_nested_collections`, `mutable_record`, `none_when_empty` | F2P (1–11 feature tests each) |
| `list_commands_keeps_duplicates`, `chain_check_dropped` (correct diagnostics; existing behaviour changed) | **authored compatibility P2P only**: reward 0 |
| `heavier_import` (correct diagnostics; `import click` loads `dataclasses`) | **declared upstream P2P only** (`test_light_imports`): reward 0 |

The last three rows show that a solution violating a compatibility requirement cannot get a full
reward. Under the V1 mutation logic, which counted only F2P failures, these three would have been
reported as "survived".

## Reproduce

```bash
cd track1_freestyle
python3.13 -m venv /tmp/venv && /tmp/venv/bin/pip install pytest   # factory itself is stdlib-only
export T1_ENGINE=docker T1_WORK=/tmp/t1_work
/tmp/venv/bin/python -m factory generate --family collisions --knobs '{"scope":"diagnostics"}' \
  --out generated_tasks_v2 --runs runs_v2 --ledger ledger_v2.json --label v2_collisions
/tmp/venv/bin/python -m factory telemetry --runs runs_v2/<run> --tasks generated_tasks_v2 --out pipeline_run_v2.json
python3.13 ../organizer/Track1-Coding/harness/check_structure.py generated_tasks_v2/pallets__click-command-collection-providers-55a649
SELFCHECK_OUT=./sc bash ../organizer/Track1-Coding/harness/selfcheck.sh generated_tasks_v2/pallets__click-command-collection-providers-55a649
# macOS only: prepend a GNU-find-compatible shim to PATH (evidence_v2/integration/organizer_selfcheck_duration/find_shim.sh)
```

Regenerating into a fresh directory should give byte-identical package files at commit
`8d54758`; that was not re-run separately here.

## Risks

- **Difficulty is unknown.** It is likely comparable to the V1 tasks, which Haiku reportedly
  solved 3/3. The 18 feature tests are rule-by-rule and the gold is about 40 lines; a careful agent
  that reads the instruction may well solve it. Benchmark before relying on it.
- **Authored tests graded as P2P.** The organizer interface defines P2P mechanically ("PASS both at
  base and with the gold"), but its prose calls P2P "existing tests". The provenance file keeps the
  6 authored tests distinguishable; organizers may still judge regression coverage on the 31
  upstream tests only.
- **Novelty** is limited to upstream Click and a fixed set of extensions; the concept itself is a
  known pattern (see the investigation).
