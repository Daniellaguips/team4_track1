# Decision record: `CommandCollection` provider diagnostics

Status: **settled for implementation as blueprint family `collisions`** (2026-11-14). It supersedes
the open items (U1–U7) of `docs/COMMAND_COLLISION_SPEC_DRAFT.md`. The final requirement text
is the generated task's `instruction.md`. `docs/COMMAND_COLLISION_TEST_PLAN.md` maps it to tests.

Base: pallets/click `cf19179e8e2fd54c601378cec9e0d21bb12b6fb1` (8.5.1). Code references are to
`src/click/core.py` at that commit.

## Novelty recheck (before deciding)

| Check (2026-11-14) | Result |
|---|---|
| Upstream `main` | still `e38188e9e205005d5af5f9e59df51904c984586a`, no commits since the earlier investigation. `git grep` for `get_command_providers`, `get_command_collisions`, `CommandProvider` and `collision` in `src/` and `tests/` finds no command-lookup diagnostics. The only hits are the parameter-name warning that already exists at base, plus help-option "shadowed" tests |
| pallets/click issues and PRs (GitHub search: `CommandCollection`, `collision`, `shadow command`, `duplicate command name`, sorted by update) | nothing new since the investigation; no open or merged proposal for provider listing |
| Extensions (PyPI latest) | cloup 4.0.0, click-extra 10.2.0, click-repl 0.4.1, rich-click 1.9.9, Typer 0.29.1, click-plugins 1.1.1.2, stevedore 5.10.0: the same versions that were source-grepped before. No re-read was needed |
| Team-internal | PR #2 `track1_llm_factory` (head `8394b349`): no command-lookup design (see investigation) |

No drop-in equivalent blocks the candidate. The novelty limits stated in the investigation still
apply: the ecosystem-wide search is incomplete, and the concept (duplicate-name detection) is a
known pattern being ported to `CommandCollection`.

## Decisions

| # | Topic | Decision | Reason from code or realistic use |
|---|---|---|---|
| D1 | Scope | **Diagnostics only.** No collision policy, no new constructor argument, no change to lookup | Defaults given for this milestone. A policy would change `get_command`, which help, completion, chain checks and invocation all depend on |
| D2 | Public API | `click.CommandProvider` (record), `CommandCollection.get_command_providers(ctx, cmd_name) -> list[CommandProvider]`, `CommandCollection.get_command_collisions(ctx) -> dict[str, list[CommandProvider]]` | Names follow Click's `get_command` / `list_commands` vocabulary. No upstream naming precedent exists, so the instruction states them verbatim |
| D3 | Record fields | **`group`, `source_index`, `command`**, nothing else. The draft's `name` field is **dropped** | Minimal scope: the caller passed the name to `get_command_providers`, and the collisions dict is keyed by it. `group` + `source_index` identify the provider; `command` is what it returned. `command.name` is not a substitute for the lookup name (`add_command(cmd, name=...)`), but the record does not need either |
| D4 | Record semantics | Immutable (assigning an attribute raises `AttributeError`); constructible by keyword; equal when all three fields are equal (`group`/`command` compare as Click objects do, i.e. by identity). The gold uses a frozen dataclass | Tests check only these properties, not `repr`, tuple behaviour or hashing, so a `NamedTuple` would also be correct |
| D5 | Provider identity and ordering | The collection's own registrations first (`source_index=None`, `group` is the collection), then `sources` in list order (`source_index` = 0-based position at call time) | This is exactly the order `CommandCollection.get_command` searches (core.py:2173-2188), so the first record is the command `get_command` returns |
| D6 | Collection-local lookup | "Own registrations" = what `click.Group.get_command(collection, ctx, name)` returns (the `commands` mapping filled by `add_command`) | The base class's own lookup. A user subclass overriding the *collection's* `get_command` is not consulted for local commands; that is stated as out of scope |
| D7 | Hidden commands | Reported like any other; no filtering | Hidden commands still resolve in `get_command` and can shadow visible ones in dispatch and help (investigation case 5). Hiding them would make the diagnostics miss exactly the confusing case |
| D8 | Same object via several providers | One record per provider, **no de-duplication** | Shows every place a name is registered |
| D9 | Same group listed twice in `sources` | Two records differing only in `source_index` | Falls out of D8; `add_source` does not refuse duplicates |
| D10 | What is a collision | A name from `list_commands(ctx)` whose providers include **at least two distinct command objects** (`is`). Identical objects alone are not a collision | Defaults given for this milestone. Re-registering one object cannot change behaviour, whichever provider wins |
| D11 | Which names are examined | Exactly the names returned by `self.list_commands(ctx)`, in that order. A listed name that nothing resolves is skipped; a name that resolves but is not listed is not examined | Unlisted names cannot be enumerated in general. Following `list_commands` respects subclasses that override it (for example, to order help) |
| D12 | Dynamic sources | Each call reads `self.sources` and every registration at call time: `add_source`, `sources.append` and `add_command` after an earlier call are all reflected | `add_source` is a public API, and `self.sources` is a plain public list |
| D13 | Snapshots and caching | Each call returns a **new** list or dict. Nothing is cached, and earlier results do not change when sources change later | Avoids stale diagnostics and shared mutable state |
| D14 | Custom group hooks | Sources are consulted only through their own `get_command` (and, via the collection's `list_commands`, their own `list_commands`) | Lazy-loading groups (`get_command` override with an empty `commands` mapping) are the documented way to build large CLIs |
| D15 | Nested collections | A source that is itself a `CommandCollection` is **one** provider. Its own sources are not expanded | Matches how `get_command` treats it. Flattening would report groups that the outer lookup never consults directly |
| D16 | Cycles | **Not specified, not tested.** A collection that (directly or indirectly) lists itself as a source already recurses without end in `get_command` at base | No realistic configuration needs it; specifying it would add a rule purely for difficulty |
| D17 | Chain mode | The diagnostics **do not** run the chain-mode nested-group check, and return normally where `get_command` would raise `RuntimeError` | The check guards invocation (core.py:2183-2184). Diagnostics do not invoke, and that misconfiguration is precisely something a user would want to inspect |
| D18 | Errors | Exceptions raised by a source's `get_command`/`list_commands` (or the collection's `list_commands`) propagate unchanged. No warnings are emitted | Swallowing user errors would hide broken lazy loaders |
| D19 | Resilient parsing | No special case: results and error propagation are the same whatever `ctx.resilient_parsing` is | Lookup at base does not consult the flag. Shell completion contexts are resilient, so a completion helper may call the diagnostics |
| D20 | Name matching | Names are used exactly as given (no `token_normalize_func`, no prefix matching), like `get_command` | `get_command` does not normalise; normalisation happens in `resolve_command` |
| D21 | Compatibility | Existing behaviour is unchanged: `get_command` precedence and chain check, sorted de-duplicated `list_commands`, help (a hidden winner still hides the name), completion, invocation, no new warnings | Defaults given for this milestone |

## Dropped from the draft

- The `name` record field (D3).
- A dedicated case-normalisation test. D20 is stated in the instruction and covered by one
  assertion, but no rule was added beyond "same as `get_command`".
- Cycle behaviour (D16).

## Test categories (implemented in the factory)

- **F2P** (`tests/test_command_collection_providers.py`): every test calls the new API, so each
  one fails at base with `AttributeError` inside its own call.
- **Authored compatibility** (`tests/test_command_collection_compat.py`): new tests that pin
  D21 and pass at base and under gold. They go into `pass_to_pass.json` because the grading
  contract defines P2P as "PASS both at base and with the gold", so a solution that breaks them
  scores 0. They are labelled `authored_compatibility` in `tests/p2p_provenance.json` and reported
  separately from upstream regression tests. They are never described as pre-existing upstream tests.
- **Upstream P2P**: pre-existing tests chosen by the factory's coverage curation, listed as
  `upstream_regression` in the same provenance file.
