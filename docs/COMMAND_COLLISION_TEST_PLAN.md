# Test plan: `CommandCollection` provider diagnostics

Covers `docs/COMMAND_COLLISION_SPEC_DRAFT.md` (requirements R1–R11). **Plan only: no test file, gold
patch or package has been written.** Nothing here claims the task is hard for a model; that needs a
benchmark.

## 1. Fixture conventions (for whoever writes the tests)

- Import only `click` (and `pytest`) at module level. Reach new names inside test functions
  (`click.CommandProvider`, `cli.get_command_providers`). At the unmodified base every feature test
  must then **fail in its own call** with `AttributeError`, not ERROR at collection. The hardened nop
  gate rejects collection errors.
- Build groups inline: `a, b = click.Group("a"), click.Group("b")`, commands via
  `click.Command(name)` or decorators, `ctx = click.Context(cli)`. No files, network, or environment.
- Compare commands by identity (`is`), never by name or help text, when R4/R5 are being tested.
- Every assertion must be derivable from the spec text: no unstated ordering or reprs. Do not assert
  `repr(CommandProvider)`; the spec does not define it.

## 2. Requirement-to-test matrix

"F2P" = must fail at base and pass with a correct implementation. "BASE-PASS" = new test, but it
already passes at base because it pins existing behaviour (see section 4 for how to grade these).
"P2P" = existing upstream test.

| Requirement ID | Scenario | Expected observable behavior | F2P / P2P | Plausible mutant |
|---|---|---|---|---|
| R1 | `click.CommandProvider(name="x", group=g, source_index=None, command=c)`; read attributes; assign `p.name = "y"` | attributes as given; assignment raises `AttributeError`; two records with equal fields are `==` | F2P | M14 mutable record |
| R2 | two sources both provide `deploy` (distinct objects) | 2 providers; `source_index` `[0, 1]`; `group` `[a, b]`; `command` identities match | F2P | M3 reversed sources, M4 winner only, M12 1-based index |
| R2 | collection-local `deploy` plus both sources | 3 providers; first has `source_index is None` and `group is cli` | F2P | M1 local omitted, M2 local last |
| R2 | name provided by nothing | `[]` | F2P | M15 returns `None` |
| R2 | two calls; mutate the first result (`.clear()`) | second call unaffected | F2P | M16 returns a shared cached list |
| R2 / R10 | a source overrides `get_command` (lazy) and has an empty `commands` dict | lazy command is reported for that source | F2P | M10 reads `source.commands` |
| R3 | for each name in several layouts (local/source/none), compare with `cli.get_command` | `providers[0].command is cli.get_command(ctx, n)`, or `[]` ⇔ `None` | F2P | M2, M3 |
| R4 | same object registered in sources 0 and 1 | 2 providers, both `command is shared` | F2P | M5 de-dup by identity |
| R4 | the same `Group` object listed twice in `sources` | 2 providers, `source_index` 0 and 1 | F2P | M5 |
| R5 | distinct `deploy` in a and b, unique `status`, `logs` | `list(collisions) == ["deploy"]`; value equals `get_command_providers(ctx, "deploy")` | F2P | M7 name-count only |
| R5 | same object in two sources | name **not** in collisions | F2P | M6 provider-count ≥ 2 |
| R5 | source with listed-but-unresolvable `ghost` plus another source with real `ghost` | not a collision (only 1 provider) | F2P | M7 counts listed names |
| R5 | no duplicates anywhere | `{}` | F2P (fails at base on the missing method) | M15 |
| R5 | collection subclass overriding `list_commands` to return a custom order of two colliding names | dict key order follows that override | F2P | M17 sorts keys itself |
| R6 | hidden command in source 0 shadows visible one in source 1 | both reported; first `command.hidden is True` | F2P | M8 filters hidden |
| R6 | two hidden distinct commands with same name | reported as a collision | F2P | M8 |
| R7 | `Context(cli, token_normalize_func=str.lower)`, source has `deploy`, query `"DEPLOY"` | `[]` | F2P | M13 normalises |
| R8 | `chain=True`; winning provider is a `Group` | `get_command_providers` returns normally (and `get_command` still raises `RuntimeError`) | F2P | M11 calls `self.get_command`/chain check |
| R8 | source `get_command` raises `LookupError("boom")` | the same exception propagates from `get_command_providers` | F2P | M18 swallows errors |
| R8 | call both methods under `warnings.simplefilter("error")` | no warning | F2P | M19 warns on collision |
| R9 | call, then `add_source(b)`, call again | second call includes b | F2P | M9 caches at first call |
| R9 | call, then `cli.sources.append(b)` | reflected | F2P | M9, M20 snapshots `sources` in `__init__` |
| R9 | call, then `a.add_command(new)` | reflected | F2P | M9 |
| R10 | a source that is itself a `CommandCollection` with its own sources | one provider for that nested collection; its sources are not listed separately | F2P | M21 flattens nested collections |
| R11 | `get_command` precedence: local > sources in order | unchanged | BASE-PASS | M22 changes `get_command` |
| R11 | `list_commands` sorted and de-duplicated | unchanged | BASE-PASS | M23 `list_commands` returns duplicates |
| R11 | `--help` with hidden winner omits the name; completion likewise | unchanged | BASE-PASS | M22 |
| R11 | after calling the diagnostics, `get_command`/`list_commands`/help output are unchanged | unchanged | **F2P** (calls the new method, so it fails at base) | M24 diagnostics mutate state |

Requirements without their own F2P row: none. R11's pure "nothing changed" rows are BASE-PASS on
purpose. They are **not** forced into F2P to inflate the count.

### Minimal positive / negative pairs

- Positive: distinct `deploy` in a and b → `"deploy" in collisions`.
  Negative: the same object in a and b → `"deploy" not in collisions`.
- Positive: hidden earlier, visible later → 2 providers.
  Negative: same layout, query a name nobody provides → `[]`.
- Positive: `add_source` after a call → reflected.
  Negative: no mutation → two calls return equal lists.

### Boundary cases

Empty `sources`; collection with only local commands; `sources=[]` then `add_source`; a source that
`list_commands` reports but cannot resolve; the same group twice; nested collection; `chain=True`;
a name that differs only by case under `token_normalize_func`.

## 3. Mutants (realistic wrong implementations)

| ID | Mutant | Detected by |
|---|---|---|
| M1 | local lookup omitted | R2 local row |
| M2 | local provider appended after sources | R2 local row, R3 |
| M3 | sources iterated in reverse | R2, R3 |
| M4 | returns only the active provider | R2 two-source row |
| M5 | de-duplicates providers by command identity | R4 rows |
| M6 | collision = "≥ 2 providers" | R5 same-object row |
| M7 | collision = "listed by ≥ 2 groups' `list_commands`" | R5 ghost row |
| M8 | skips hidden commands | R6 rows |
| M9 | memoises results per name / per collection | R9 rows |
| M10 | reads `source.commands` instead of `source.get_command` | R2/R10 lazy row |
| M11 | obtains the active command via `self.get_command` (triggers chain check) | R8 chain row |
| M12 | 1-based `source_index`, or local reported as index 0 | R2 rows |
| M13 | applies `ctx.token_normalize_func` | R7 row |
| M14 | plain mutable class for `CommandProvider` | R1 row |
| M15 | returns `None` instead of `[]` / `{}` | R2 empty row, R5 empty row |
| M16 | returns an internal list | R2 mutation row |
| M17 | sorts collision keys instead of following `list_commands` | R5 override-order row |
| M18 | catches exceptions from sources | R8 exception row |
| M19 | emits `UserWarning` on collisions | R8 warnings row |
| M20 | copies `sources` at construction | R9 append row |
| M21 | recursively expands nested collections | R10 nested row |
| M22–M24 | change existing lookup/help, or mutate state when called | R11 rows (M22/M23 only by BASE-PASS tests or P2P, see section 4) |

Each mutant should be a small, compiling patch against the gold. The hardened mutation gate counts
it as killed only if a collected F2P test *fails behaviourally*. A mutant that does not import
counts as invalid, not killed.

## 4. Grading compatibility tests — factory gap

The current factory (`pipeline.f2p_ids`) makes **every** `test_*` function in the test patch an
F2P id. The nop gate requires every F2P to **fail** at base. A BASE-PASS compatibility test would
therefore make nop fail. There are three options; the team must choose (spec U7):

1. **Recommended:** extend the factory so a test patch can mark tests as "new pass-to-pass". They go
   into `pass_to_pass.json` and must pass at base, under gold, and under every mutant that is not
   meant to break them. This is a small change in `pipeline.f2p_ids`/`package.write` plus the gates.
   No V1 package is affected.
2. Omit BASE-PASS tests and rely on upstream P2P. This is weak here, because upstream has **no**
   `CommandCollection` tests (investigation, section 2).
3. Fold compatibility assertions into F2P tests after a call to the new API. Acceptable only for
   the M24 row, where it is the actual requirement. Using it for M22/M23 would turn existing
   behaviour into F2P artificially.

## 5. Upstream P2P selection

Coverage-based curation keyed on the touched symbol `CommandCollection.*` would select nothing,
because no upstream test executes it. Declare these focus symbols instead: `Group.get_command`,
`Group.list_commands`, `Group.format_commands`, `Group.resolve_command`,
`_complete_visible_commands`, `_check_nested_chain`. Then let curation rank tests by coverage. The
expected candidates, all of which pass at base (local macOS run,
`evidence_v2/command_collision/p2p_candidates_at_base.log`, not the task image), are:

| Test | Why |
|---|---|
| `tests/test_commands.py::test_group_add_command_name`, `::test_aliased_command_canonical_name` (custom `get_command`), `::test_invoked_subcommand`, `::test_unknown_command`, `::test_suggest_possible_commands[*]` | group lookup, custom lookup overrides, `NoSuchCommand` |
| `tests/test_chain.py::test_basic_chaining`, `::test_chaining_help[*]` | chain-mode lookup and help |
| `tests/test_shell_completion.py::test_group`, `::test_chained`, `::test_hidden` | completion over `list_commands`/`get_command`, hidden filtering |
| `tests/test_basic.py::test_basic_group`, `::test_group_commands_dict`, `::test_group_from_list`, `::test_hidden_command`, `::test_hidden_group` | registration and hidden commands in help |
| `tests/test_info_dict.py::test_command[Group]`, `[Nested Group]` | `to_info_dict` walks `list_commands`/`get_command` |

Exclude `tests/test_chain.py::test_group_chaining`: it is `xfail` at base, so it is not a valid P2P.

## 6. Checks against harness and environment failures

These are enforced by the hardened gates (`docs/V2_VALIDATION_HARDENING.md`). They must be re-run in
the task image, which this branch has not done.

- **Nop:** every F2P id is reported once with status FAILED (expected cause `AttributeError` on
  `get_command_providers`/`get_command_collisions`/`CommandProvider`). There are no collection
  errors, no `MISSING`, every P2P passes, and the recomputed totals equal the grader's.
- **Gold:** every F2P and P2P passes, and there are no pytest errors (setup/teardown included).
- **Mutants:** each one applies cleanly (`T1_STAGE_FAIL` absent), imports, and is rejected by at
  least one F2P assertion; import/syntax failures count as invalid.
- **Full suite under gold:** `T1_PYTEST_EXIT=0`, complete log saved, at least one test passed, 0
  failed, 0 errors.
- **Determinism:** the tests use only in-memory groups. Run the F2P file twice under gold and
  compare statuses. That is a manual check; the factory has no flakiness gate.
- **Fairness lint:** each test docstring cites its R-id. The spec names every public symbol the
  tests touch (`CommandProvider`, `get_command_providers`, `get_command_collisions`, `source_index`,
  `group`, `command`, `name`).

## 7. Implementation challenges (no difficulty claim)

These are places where a reasonable implementation can go wrong. Whether a model actually does is
unknown until benchmarked.

- Local lookup must use the base `Group` lookup. Calling `self.get_command` would return the winner
  from any source and also triggers the chain check (M2/M11).
- Identity versus equality: "collision" depends on distinct objects, while R4 forbids
  de-duplication (M5/M6).
- Listed names versus resolvable names: `list_commands` can report names that `get_command` cannot
  resolve (M7).
- The constructor's `sources or []` aliasing means "reflect `sources` at call time" is the only rule
  that behaves the same for empty and non-empty lists (M20).
- Exceptions from user groups must propagate. There is a temptation to "be robust" (M18).
