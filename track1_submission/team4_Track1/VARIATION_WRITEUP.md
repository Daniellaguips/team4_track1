# Variation strategy

## What the factory is (and is not)

The factory is a **blueprint compiler + validator** for `pallets/click` at tag `8.5.1`
(`cf19179e8e2fd54c601378cec9e0d21bb12b6fb1`). No LLM is used anywhere (no organizer key was available
on this host, see README "Limitations"). Variation comes from two pre-designed layers:

1. **Five capability blueprints** (`factory/families/*.py`), each hand-designed around a *different
   extension point* of Click and a *different behavioural shape*. These are the creative part and
   they are pre-written by a human (disclosed).
2. **Behavioural knobs inside each blueprint.** Every blueprint is a function `build(knobs) -> Draft`;
   each knob changes a *rule* the solver must implement, and the spec text, gold implementation,
   feature tests and mutants are all derived from the same knob values. 5 blueprints x 4 knob vectors
   = 20 distinct concrete tasks today.

The pipeline (not a human) then grounds every edit in the real code (anchors must exist exactly once
at base), materialises gold and test patches with git, curates the regression set from per-test
coverage, packages for Harbor and runs all gates. The planner (`factory/planner.py`) decides what to
generate: a batch first spans different blueprints (capability axis), then a seeded RNG picks a knob
vector per blueprint, skipping vectors already recorded in a ledger so a re-run produces fresh
behaviour rather than duplicates.

## Axes the five tasks move along

| Blueprint | Capability | Click module / extension point | Behavioural shape |
|---|---|---|---|
| `duration` | value conversion | `types.py` new `ParamType` + package export | string grammar -> `timedelta`, bounds |
| `abbrev` | command dispatch | `Group.resolve_command`, `CommandCollection`, chain mode | precedence chain + ambiguity error |
| `conflicts` | cross-parameter validation | `Option.__init__`, `Command.parse_args`, `ParameterSource` | post-processing check over value provenance |
| `attempts` | interactive I/O | `termui.prompt/confirm`, `Option.prompt_for_value` | retry state machine with failure counter |
| `sections` | help rendering | `Command.__init__`, `Group.format_commands`, `HelpFormatter` | partition + ordering + shared width budget |

They share no public symbol, touch different functions (see each task's `p2p_rationale.json`), and
fail in different ways: grammar edge cases, lookup precedence, provenance bookkeeping, loop
accounting, layout arithmetic.

## Knobs (rule changes, not renames)

- `duration`: unit set (`dhms` / `wdhms`), component order (strictly descending / any order without
  repeats), digits-only meaning (seconds / invalid).
- `abbrev`: hidden commands take part in prefix matching or not; ambiguity candidates alphabetical or
  shortest-first.
- `conflicts`: which `ParameterSource`s count as "provided" (command line only / also environment);
  report first conflicting pair or all pairs (with de-duplication).
- `attempts`: whether an empty answer without default is a failed attempt; give up with `Abort`
  (exit 1) or `UsageError` (exit 2).
- `sections`: named-section order (first seen / alphabetical); default section first or last.

Each knob flips at least one feature test's expected value and has a matching mutant ("implements the
other rule"), so a solver that memorised one variant fails the other.

## Why this is variation and not rewording

- Different blueprints exercise different modules and require different reasoning; their gold
  patches touch disjoint functions.
- Different knob vectors of one blueprint produce different oracles: the same input (`30m1h`,
  `cli se`, `--json` with `APP_YAML=1`, an empty prompt answer, section order) has a different
  correct output.
- Identity rides on behaviour: no task is produced by renaming an identifier.

## Fairness mechanics shared by all blueprints

Every feature test cites the requirement IDs (`R1`...) it checks; the fairness lint fails a candidate
if a test cites no requirement, if a requirement is untested, if an asserted message cannot be
assembled from spec text plus values the test itself supplies, or if a test uses a public name or
keyword the spec never mentions. Mutants (6-8 per task) model plausible wrong implementations of
spec rules (off-by-one, wrong precedence, the other knob's rule, skipped de-duplication, ...).
