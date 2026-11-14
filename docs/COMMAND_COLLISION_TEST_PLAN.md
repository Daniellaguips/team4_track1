# Test plan and requirement-to-test matrix: `CommandCollection` provider diagnostics

Status: **final for task version `pallets__click-command-collection-providers-55a649`**
(blueprint `factory/families/collisions.py`, commit `8d54758`). Requirements R1–R10 are the
task's `instruction.md`, settled in `docs/COMMAND_COLLISION_DECISIONS.md`. This replaces the
earlier plan-only version (draft R1–R11; the mapping is at the end). Validation results:
`docs/COLLISION_TASK_REPORT.md`. Nothing here claims the task is hard.

## 1. Test categories

| Category | File / source | Count | Must at base | Must under gold | Graded as |
|---|---|---|---|---|---|
| F2P (feature) | `tests/test_command_collection_providers.py` (new) | 18 | FAIL, each in its own call | PASS | `fail_to_pass.json` |
| Authored compatibility | `tests/test_command_collection_compat.py` (new) | 6 | PASS | PASS | `pass_to_pass.json`, provenance `authored_compatibility` |
| Upstream regression | pre-existing upstream tests | 31 (30 curated by coverage on 8 focus symbols, 1 declared) | PASS | PASS | `pass_to_pass.json`, provenance `upstream_regression` |

Conventions that keep the categories honest:

- F2P tests import only `warnings`, `pytest` and `click` at module level and reach the new API
  inside each test, so at base every one fails with `AttributeError` in its own call (verified:
  18/18), never as a collection error.
- Baseline-passing tests are never put in F2P. The nop gate would reject them
  (`test_baseline_passing_test_cannot_be_forced_into_f2p`).
- Authored tests are never described as upstream tests; `gates.test_categories` checks the
  partition, and upstream ids must be in no file the test patch creates and must be `PASSED` in
  the base suite run.
- Every test docstring cites its R ids (fairness lint).

## 2. Requirement-to-test matrix

| Req | Scenario | Test | Category | Mutants it catches |
|---|---|---|---|---|
| R1 | keyword construction, the three attributes, equality by value, assignment raises `AttributeError` | `test_provider_record` | F2P | `mutable_record` |
| R2 | two sources provide `deploy`: records `(a,0)`, `(b,1)` with the right commands | `test_sources_reported_in_order` | F2P | `sources_reversed`, `active_provider_only`, `one_based_index` |
| R2 | own command + two sources: `(cli,None)` first | `test_own_command_comes_first` | F2P | `local_omitted`, `local_after_sources`, `sources_reversed`, `one_based_index` |
| R2 | nothing provides the name → `[]`; `"DEPLOY"` not normalised | `test_unprovided_and_exact_names` | F2P | `none_when_empty` |
| R3 | first provider is what `get_command` returns, or `[]` ⇔ `None` (three layouts) | `test_first_provider_is_what_get_command_returns` | F2P | `local_omitted`, `local_after_sources`, `sources_reversed`, `active_provider_only` |
| R4 | same object in two sources; same group listed twice | `test_repeated_registrations_are_not_merged` | F2P | `merges_same_object`, `active_provider_only`, `one_based_index` |
| R5 | distinct `deploy` collides, shared `sync` does not; value equals providers | `test_collisions_need_distinct_objects` | F2P | `collision_by_provider_count`, `collision_by_listing_groups`, `warns_on_collision` |
| R5 | listed-but-unresolvable `ghost` is not a collision | `test_listed_but_unresolvable_names_are_not_collisions` | F2P | `collision_by_listing_groups` |
| R5 | keys follow an overridden `list_commands` order | `test_collisions_follow_list_commands_order` | F2P | `sorts_collision_names` |
| R5 | no duplicates, or no sources → `{}` / `[]` | `test_no_collisions` | F2P | `collision_by_listing_groups`, `none_when_empty` |
| R6 | hidden earlier command reported, and the name collides | `test_hidden_commands_are_reported` | F2P | `hidden_filtered` |
| R7 | new objects per call, caller mutation has no effect, earlier results not updated | `test_results_are_independent_snapshots` | F2P | `cached_per_name` |
| R7 | `add_source`, `sources.append`, `add_command` after a call are reflected | `test_changes_after_a_call_are_reflected` | F2P | `cached_per_name`, `local_omitted`, `none_when_empty` |
| R8 | lazily loading source with empty `commands` is consulted via `get_command` | `test_sources_with_custom_lookup` | F2P | `reads_commands_mapping` |
| R8 | nested collection is one provider; not expanded | `test_nested_collection_is_one_provider` | F2P | `expands_nested_collections`, `reads_commands_mapping` |
| R9 | `chain=True`, a group from a source is reported (no `RuntimeError`) | `test_chain_mode_groups_are_reported` | F2P | `applies_chain_check` |
| R9 | lookup/listing exceptions propagate, with and without `resilient_parsing` | `test_errors_propagate` | F2P | `swallows_source_errors`, `cached_per_name`, `reads_commands_mapping` |
| R9, R10 | calling the diagnostics emits no warning and changes no state or help output | `test_no_warnings_and_nothing_changes` | F2P (calls the new API) | `warns_on_collision` |
| R10 | invocation precedence: own, then sources in order | `test_lookup_precedence_is_unchanged` | authored compat | — |
| R10 | `list_commands` sorted without duplicates | `test_list_commands_is_sorted_without_duplicates` | authored compat | `list_commands_keeps_duplicates` |
| R10 | chain mode still raises `RuntimeError` in `get_command` | `test_chain_mode_still_rejects_a_group_from_a_source` | authored compat | `chain_check_dropped` |
| R10 | a hidden winner still hides the name in `--help` | `test_hidden_winner_still_hides_the_name_in_help` | authored compat | — |
| R10 | completion offers visible winners only | `test_completion_is_unchanged` | authored compat | — |
| R10 | duplicate names raise no warning at definition or invocation | `test_duplicate_names_raise_no_warnings` | authored compat | — |
| R10 | "the existing test suite must keep passing" | 31 upstream P2P (e.g. `test_chain.py::test_basic_chaining`, `test_shell_completion.py::test_hidden`, `test_imports.py::test_light_imports`) and the full-suite gate | upstream P2P | `heavier_import` |

The mutant column lists the mutants each test is meant to catch, and every pairing was confirmed
in the pipeline run. It is not exhaustive: many tests also catch other mutants. The complete
record is the per-mutant `killed_by` in `runs_v2/20261114T150004_v2_collisions/.../gates.json`.

## 3. Checks against harness and environment failures

Enforced by the hardened gates and executed for this task in the task image:

- **Nop:** every F2P reported once as `FAILED` (all `AttributeError`), no collection errors, no
  `MISSING`, every P2P `PASSED`, and the grader's totals match a recomputation from raw records.
- **Gold:** every F2P and P2P `PASSED`, no pytest errors.
- **Mutants:** each applies and imports; killed only by a behavioural failure of an F2P or P2P test;
  import/syntax failures would count as invalid.
- **Full suite under gold:** pytest exit 0 with a complete saved log (this gate caught the first
  candidate's import regression).
- **Determinism:** gold and nop graded twice more with identical per-test statuses.

## 4. Mapping from the draft (for readers of the earlier version)

Draft R1 → R1 (`name` field dropped, D3); draft R2+R7 → R2; R3 → R3; R4 → R4; R5 → R5; R6 → R6;
R9 → R7; R10 → R8; R8 → R9; R11 → R10. Draft "BASE-PASS" rows are the authored compatibility
category; the factory gap described in the draft's section 4 is closed (option 1, with provenance).
