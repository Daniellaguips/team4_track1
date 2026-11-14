# Command provider diagnostics for `click.CommandCollection`

`click.CommandCollection` merges the commands of several groups (its `sources`) into one command
line. When two groups register the same command name, the first one found wins and the others are
silently shadowed, and there is no public way to see which group provides a name or which names
are provided more than once. Add read-only diagnostics for this. **Lookup, dispatch, help, shell
completion and every other existing behaviour must stay exactly as they are.**

## Terms

- The collection's **own commands** are those registered on the collection itself (with
  `add_command` or `@collection.command`), i.e. what the plain `click.Group.get_command(collection,
  ctx, name)` returns.
- A **provider** of a name is one place where looking that name up returns a command: the
  collection's own commands, or one position in `collection.sources`, looked up with that source
  group's own `get_command(ctx, name)` method.

## Public interface

- `click.CommandProvider`, a new public record type (defined in `click.core`, exported from
  `click`).
- `CommandCollection.get_command_providers(ctx, cmd_name) -> list[CommandProvider]`
- `CommandCollection.get_command_collisions(ctx) -> dict[str, list[CommandProvider]]`

## Requirements

**R1 — `click.CommandProvider`.** It has exactly the attributes `group`, `source_index` and
`command`, and can be constructed with them as keyword arguments,
`CommandProvider(group=..., source_index=..., command=...)`. `group` is the group whose lookup
returned the command (the collection itself for its own commands, otherwise the source group);
`source_index` is `None` for the collection's own commands, otherwise the 0-based position of that
source in `collection.sources`; `command` is the command object the lookup returned. Records are
immutable: assigning to any attribute raises `AttributeError`. Two records are equal when all
three attributes are equal (groups and commands compare as Click objects normally do, i.e. by
identity).

**R2 — `get_command_providers(ctx, cmd_name)`.** Returns a new list with one record per provider
of `cmd_name`, in lookup order: first the collection's own command (if any), then each source in
`sources` order whose `get_command(ctx, cmd_name)` returns a command. Lookups that return `None`
add nothing; if nothing provides the name the result is `[]`. The name is used exactly as given,
as `get_command` does: no `token_normalize_func`, no prefix matching. `ctx` is passed unchanged to
every lookup.

**R3 — Consistent with lookup.** For any name, when the providers list is non-empty, its first
record's `command` is the object `collection.get_command(ctx, name)` returns; when it is empty,
`get_command` returns `None`. The first record is the active provider; later ones are shadowed.

**R4 — No merging.** Every provider gets its own record, even when the same command object is
reached more than once: the same object registered in two sources, or the same group listed twice
in `sources` (those records differ only in `source_index`).

**R5 — `get_command_collisions(ctx)`.** Returns a new dict. Its keys are the names returned by
`collection.list_commands(ctx)`, in that order, keeping only names whose providers (R2) include at
least two **distinct** command objects (compared with `is`). Each value equals
`get_command_providers(ctx, name)`. A name whose providers all return the same object is not a
collision; a listed name that no provider resolves is not a collision; names that `list_commands`
does not return are not examined. No collisions gives `{}`.

**R6 — Hidden commands.** Commands with `hidden=True` are reported like any other, both as
providers and in collisions.

**R7 — Snapshots, no caching.** Every call reflects `sources` and all registrations at the time of
that call: a source added with `add_source` or appended to `collection.sources`, and commands
added to the collection or to a source after an earlier call, all show up in the next call.
Nothing is cached. Returned lists and dicts are new objects owned by the caller; changing them does
not affect later calls, and they are not updated when sources change afterwards.

**R8 — Custom and nested groups.** Sources are consulted only through their own `get_command`
(and, through the collection's `list_commands`, their own `list_commands`), so groups that
override these methods, for example to load commands lazily, take part exactly as they do in
normal lookup. A source that is itself a `CommandCollection` is a single provider; its own sources
are not expanded.

**R9 — No side effects.** The two methods do not modify `sources`, any group's registered
commands or the context, and emit no warnings. They do not perform the chain-mode check that
`get_command` applies to a group found in a source: with `chain=True` they report such a group
normally even though `get_command` raises `RuntimeError` for it. Exceptions raised by a source's
`get_command` or `list_commands`, or by the collection's `list_commands`, propagate unchanged. The
behaviour is the same whatever `ctx.resilient_parsing` is.

**R10 — Compatibility.** Existing behaviour does not change, whether or not the new methods are
called: `get_command` (own commands first, then sources in order, first match wins, chain-mode
check on a group found in a source), `list_commands` (sorted, without duplicates), `add_source`,
help output (a hidden command that wins a name still hides that name), shell completion and
invocation. No new warnings or errors are raised when defining, registering, looking up or
invoking commands.

## Example

```python
a, b = click.Group("a"), click.Group("b")
deploy_a, deploy_b = click.Command("deploy"), click.Command("deploy")
a.add_command(deploy_a)
b.add_command(deploy_b)
cli = click.CommandCollection("cli", sources=[a, b])
ctx = click.Context(cli)

cli.get_command_providers(ctx, "deploy")
# [CommandProvider(group=a, source_index=0, command=deploy_a),
#  CommandProvider(group=b, source_index=1, command=deploy_b)]
cli.get_command(ctx, "deploy") is deploy_a   # True, unchanged
list(cli.get_command_collisions(ctx))        # ['deploy']
cli.get_command_providers(ctx, "missing")    # []
```
