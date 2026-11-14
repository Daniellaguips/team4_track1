# Specification draft: `CommandCollection` provider diagnostics

Status: **draft for team review. Not implemented, not packaged, not benchmarked.** It targets
pallets/click at `cf19179e8e2fd54c601378cec9e0d21bb12b6fb1` (8.5.1). Background and novelty evidence:
`docs/COMMAND_COLLISION_INVESTIGATION.md`. Open decisions are listed in section 6. The draft is meant
to be implementable from this text and the repository alone; it refers to no hidden tests or
reference solution.

## 1. Scope decision

**Chosen: diagnostics only.** Add read-only inspection that reports every provider of a command
name and every name provided by more than one distinct command. Lookup behaviour does not change.

**Not chosen (now): diagnostics plus an opt-in collision policy** (for example `on_collision="error"`
or `"warn"`). Reasons:

- A policy changes `get_command`. `get_command` drives help rendering, shell completion,
  `to_info_dict`, chain checks and invocation, so a policy forces several more decisions: whether
  `--help` raises on an ambiguous name, whether completion may raise during resilient parsing,
  whether the error happens at construction, `add_source`, or lookup, and whether
  identical-object duplicates trip it. Each of those is a fairness risk for a generated task, and
  none of them is needed to fix the missing capability (you cannot see who provides a name).
- A policy is easy to layer on afterwards in user code or in a later task once diagnostics exist.
  The reverse is not true.
- The brief warns against adding interactions to make a task longer. Diagnostics already carry the
  substantive edge cases: precedence, identity, hidden winners, dynamic sources, custom groups and
  chain side effects.

## 2. Terminology

- **Collection**: a `click.CommandCollection` instance.
- **Local lookup**: the collection's own registrations, i.e. what `click.Group.get_command(collection, ctx, name)`
  returns (the `commands` mapping filled by `add_command` / `@collection.command`).
- **Source lookup**: `source.get_command(ctx, name)` for each element of `collection.sources`, in list
  order, using the source's own (possibly overridden) method.
- **Provider**: one place where a lookup for a name returns a command: the local lookup, or one
  position in `sources`.

## 3. Public interface

### R1 — `click.CommandProvider`

A new public, immutable record type, importable as `click.CommandProvider` (defined in
`click.core`), with exactly these attributes:

| Attribute | Type | Meaning |
|---|---|---|
| `name` | `str` | the command name that was looked up, exactly as passed in |
| `group` | `click.Group` | the group that returned the command: the collection itself for the local lookup, otherwise the source object |
| `source_index` | `int \| None` | `None` for the local lookup; otherwise the 0-based index of that source in `collection.sources` at the time of the call |
| `command` | `click.Command` | the object the lookup returned |

- It can be constructed with keywords: `CommandProvider(name=…, group=…, source_index=…, command=…)`.
- Assigning to any attribute raises `AttributeError` (a frozen dataclass's `FrozenInstanceError`
  satisfies this).
- Two records are equal when all four attributes are equal. `group` and `command` compare as
  Click objects normally do (by identity, unless a user subclass defines equality).

### R2 — `CommandCollection.get_command_providers(ctx, cmd_name)`

```python
def get_command_providers(self, ctx: Context, cmd_name: str) -> list[CommandProvider]
```

Returns a **new list** of every provider that resolves `cmd_name`, in **lookup order**:

1. the local lookup, if it returns a command (`source_index=None`, `group=self`);
2. then each source in `self.sources` order whose `get_command(ctx, cmd_name)` returns a command
   (`source_index=i`, `group=self.sources[i]`).

Lookups that return `None` contribute nothing. The result is `[]` when nothing resolves the name.
`ctx` is passed unchanged to every lookup.

### R3 — consistency with `get_command`

For any collection, context and name:

- if `get_command_providers(ctx, n)` is non-empty, its first element's `command` is the object
  `get_command(ctx, n)` returns (whenever `get_command` returns without raising);
- if it is empty, `get_command(ctx, n)` returns `None`.

The first element is the **active** provider. All later elements are **shadowed**.

### R4 — repeated registrations are not merged

Each provider produces its own record, even when the same command object is reached more than
once: the same object registered locally and in a source, in two sources, or the same `Group`
object listed twice in `sources`. In the last case the records differ only in `source_index`. No
de-duplication by name, group or command.

### R5 — `CommandCollection.get_command_collisions(ctx)`

```python
def get_command_collisions(self, ctx: Context) -> dict[str, list[CommandProvider]]
```

Returns a new dict. Its keys are the names returned by `self.list_commands(ctx)`, in that order,
kept only when the providers for that name (R2) contain **at least two distinct command objects**
(compared with `is`). Each value is exactly `self.get_command_providers(ctx, name)`.

- A name whose providers all return the *same object* is **not** a collision (R4 still lists every
  provider when queried directly).
- A name listed by `list_commands` that no provider resolves (`get_command` returns `None`) is not a
  collision.
- A name that some custom `get_command` resolves but no `list_commands` reports is not examined.
  Collisions are computed only over listed names.
- An empty dict means no collisions.

## 4. Behaviour rules

### R6 — hidden commands
Hidden commands (`hidden=True`) are reported like any other, in providers and in collisions. The
diagnostics do not filter on `hidden`. For example, a hidden local or earlier-source command that
shadows a visible later one appears as the active provider, followed by the visible one.

### R7 — exact names
`cmd_name` is used as given: no `token_normalize_func`, no prefix or alias matching beyond what each
group's own `get_command` does.

### R8 — no side effects
The two methods:

- do not modify `sources`, any group's `commands`, or `ctx`;
- do not emit warnings;
- do not perform the chain-mode nested-group check. They return normally even when `chain=True`
  and a provider's command is a `Group`, although `get_command` raises `RuntimeError` in that
  situation;
- let exceptions raised by a source's `get_command` or `list_commands`, or by the collection's
  `list_commands`, propagate unchanged at call time.

### R9 — dynamic sources, no caching
Results reflect `sources` and registrations **at the time of each call**. A source added with
`add_source`, appended directly to `sources`, or a command added to a source or to the collection
after an earlier call is reflected in the next call. Nothing is computed at construction or cached
between calls.

### R10 — custom source groups
Sources are consulted only through their own `get_command` and `list_commands`, so overridden or
lazy-loading groups participate exactly as they do in normal lookup. A source that is itself a
`CommandCollection` is treated as one provider. Its own sources are not expanded.

### R11 — backward compatibility
With or without the new methods being called, the existing behaviour of `CommandCollection` stays
exactly as at the base commit. That covers `get_command` (local first, then sources, first match
wins, chain check on the winner), `list_commands` (sorted, de-duplicated), `add_source`, the
constructor, help output, shell completion, `to_info_dict` and invocation. No new warnings or errors
are raised at definition, registration, lookup or invocation time.

## 5. Interactions (stated so they need no guessing)

| Area | Behaviour |
|---|---|
| Help (`--help`, `format_commands`) | unchanged; it does not use the diagnostics. A hidden winner still hides the visible shadowed command (investigation, case 5) |
| Shell completion | unchanged |
| Resilient parsing | the methods behave the same whatever `ctx.resilient_parsing` is |
| Chain mode | see R8; `get_command` unchanged |
| `NoSuchCommand` suggestions | unchanged (still collection-local only) |
| Failure timing | only at call time of the new methods, and only by propagating exceptions from user code (R8) |

## 6. Out of scope

- Any collision policy (error, warn, prefer-last) and any change to lookup precedence.
- Showing shadowed commands in help, completion or `to_info_dict`.
- Making `NoSuchCommand` suggest source commands.
- Warnings for `Group.add_command` overwriting an existing name in one group.
- Recursively flattening nested collections.
- Reflecting a *user subclass's* override of the collection's own `get_command`. The local lookup is
  defined as `Group.get_command(self, …)`.
- Validating argument types (non-`str` names, non-`Context` contexts).
- Documentation pages beyond docstrings; changelog wording.

## 7. Unresolved decisions

| ID | Decision | Draft position | Why it is open |
|---|---|---|---|
| U1 | Diagnostics only vs. diagnostics plus opt-in policy | diagnostics only (section 1) | Team may want a larger task; needs a separate spec if so |
| U2 | Names `get_command_providers`, `get_command_collisions`, `CommandProvider` | as drafted | No upstream naming precedent; must appear verbatim in any instruction |
| U3 | Same object via several providers counts as a collision? | no (R5) | Some users may want "registered twice" flagged; R4 keeps it visible either way |
| U4 | Include unlisted-but-resolvable names in collisions? | no (R5) | Cannot be enumerated in general |
| U5 | Record type: frozen dataclass vs `NamedTuple` | either, as long as R1 holds | A `NamedTuple` also compares equal to plain tuples and unpacks; tests must not depend on that |
| U6 | Upstream realism | proceed as a benchmark task, not an upstream proposal | Maintainer scepticism in [#2590](https://github.com/pallets/click/issues/2590) |
| U7 | How baseline-passing compatibility tests are graded | needs factory support (test plan, section 4) | The current factory makes every new test an F2P, and nop requires all of them to fail |

## 8. Minimal examples

```python
import click

a, b = click.Group("a"), click.Group("b")

@a.command("deploy")
def deploy_a(): ...

@b.command("deploy")
def deploy_b(): ...

cli = click.CommandCollection("cli", sources=[a, b])
ctx = click.Context(cli)

cli.get_command_providers(ctx, "deploy")
# [CommandProvider(name='deploy', group=a, source_index=0, command=deploy_a),
#  CommandProvider(name='deploy', group=b, source_index=1, command=deploy_b)]
cli.get_command(ctx, "deploy") is deploy_a          # unchanged, True
list(cli.get_command_collisions(ctx))               # ['deploy']
cli.get_command_providers(ctx, "missing")           # []

shared = click.Command("sync")
a.add_command(shared); b.add_command(shared)
len(cli.get_command_providers(ctx, "sync"))         # 2 (R4)
"sync" in cli.get_command_collisions(ctx)           # False (same object, R5)
```
