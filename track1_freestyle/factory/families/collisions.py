"""Blueprint: provider diagnostics for ``click.CommandCollection`` (command-name collisions).

A manually authored sixth blueprint (V2). The design is fixed by docs/COMMAND_COLLISION_DECISIONS.md;
it has a single knob value because the decision record settled every open choice. Generation is
deterministic (no model call); see ORIGIN for how the blueprint itself was written.

Knobs:
  scope  "diagnostics"   read-only inspection; lookup, help, completion and chain checks unchanged
"""
from __future__ import annotations

from ..model import Draft, Edit, Mutant

FAMILY = "collisions"
KNOBS = {"scope": ["diagnostics"]}
AXES = {
    "capability": "introspection of command lookup across merged groups",
    "module": "click.core.CommandCollection (+ new click.CommandProvider record, click/__init__ export)",
    "behavior_shape": "ordered provider enumeration + identity-based collision report",
    "integration": "Group.get_command/list_commands overrides, add_source, nested collections, hidden "
                   "commands, chain-mode check, help/completion left unchanged",
    "novelty_note": "upstream Click (base and main e38188e9) has no provider listing or collision report "
                    "for CommandCollection; related ideas exist elsewhere (stevedore conflict_resolver, "
                    "argparse duplicate subparser error, cloup section duplicates) but not as a Click API. "
                    "See docs/COMMAND_COLLISION_INVESTIGATION.md.",
}
ORIGIN = {
    "kind": "manually authored sixth blueprint (not autonomous feature discovery)",
    "design": "docs/COMMAND_COLLISION_INVESTIGATION.md -> COMMAND_COLLISION_SPEC_DRAFT.md -> "
              "COMMAND_COLLISION_DECISIONS.md, directed by the team member running the V2 assignment",
    "authoring": "blueprint code (instruction, gold edits, tests, mutants) written in a Cursor agent session "
                 "with an LLM coding assistant (Claude); reviewed against base source and run through the "
                 "factory gates",
    "generation_time_model_calls": 0,
    "reused_components": "V1 pipeline, gates (V2-hardened), templates (grade.py, parser.py, test.sh, "
                         "Dockerfile), coverage-based P2P curation, novelty/fairness/isolation gates",
}

INSTRUCTION = """# Command provider diagnostics for `click.CommandCollection`

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
"""

RECORD = '''@dataclasses.dataclass(frozen=True)
class CommandProvider:
    """A place where a :class:`CommandCollection` finds a command for a
    name, as reported by :meth:`CommandCollection.get_command_providers`.

    :param group: The group whose lookup returned the command: the
        collection itself for its own commands, otherwise the source.
    :param source_index: ``None`` for the collection's own commands,
        otherwise the position of the source in
        :attr:`CommandCollection.sources`.
    :param command: The command the lookup returned.

    .. versionadded:: 8.6
    """

    group: Group
    source_index: int | None
    command: Command


'''

METHODS = '''
    def get_command_providers(
        self, ctx: Context, cmd_name: str
    ) -> list[CommandProvider]:
        """Return every provider of ``cmd_name`` in lookup order: the
        collection's own command first, then each source in order. The
        first provider is the one :meth:`get_command` uses, the others
        are shadowed. Nothing is cached and lookup is not changed.

        .. versionadded:: 8.6
        """
        rv: list[CommandProvider] = []
        cmd = super().get_command(ctx, cmd_name)

        if cmd is not None:
            rv.append(CommandProvider(group=self, source_index=None, command=cmd))

        for index, source in enumerate(self.sources):
            cmd = source.get_command(ctx, cmd_name)

            if cmd is not None:
                rv.append(CommandProvider(group=source, source_index=index, command=cmd))

        return rv

    def get_command_collisions(
        self, ctx: Context
    ) -> dict[str, list[CommandProvider]]:
        """Return the names from :meth:`list_commands` that more than one
        distinct command object provides, mapped to their providers.

        .. versionadded:: 8.6
        """
        rv: dict[str, list[CommandProvider]] = {}

        for name in self.list_commands(ctx):
            providers = self.get_command_providers(ctx, name)

            if len({id(p.command) for p in providers}) > 1:
                rv[name] = providers

        return rv
'''

CORE = "src/click/core.py"
GOLD = [
    Edit(CORE, "import collections.abc as cabc\nimport enum\n",
         "import collections.abc as cabc\nimport dataclasses\nimport enum\n", "replace"),
    Edit(CORE, "class CommandCollection(Group):\n", RECORD, "before"),
    Edit(CORE, "            rv.update(source.list_commands(ctx))\n\n        return sorted(rv)\n", METHODS),
    Edit("src/click/__init__.py", "from .core import CommandCollection as CommandCollection\n",
         "from .core import CommandProvider as CommandProvider\n"),
]

_LOCAL = "        if cmd is not None:\n            rv.append(CommandProvider(group=self, source_index=None, command=cmd))\n"
_SOURCE_LOOKUP = "            cmd = source.get_command(ctx, cmd_name)\n"
_SOURCE_APPEND = "            if cmd is not None:\n                rv.append(CommandProvider(group=source, source_index=index, command=cmd))\n"
_RETURN = "        return rv\n\n    def get_command_collisions("


def _m(name, description, *edits):
    return Mutant(name, description, tuple(Edit(CORE, a, t, "replace") for a, t in edits))


MUTANTS = [
    _m("local_omitted", "ignores the collection's own commands", (_LOCAL, "")),
    _m("local_after_sources", "reports the collection's own command after the sources",
       ("        cmd = super().get_command(ctx, cmd_name)\n\n" + _LOCAL,
        "        local = super().get_command(ctx, cmd_name)\n"),
       (_RETURN, "        if local is not None:\n"
                 "            rv.append(CommandProvider(group=self, source_index=None, command=local))\n\n"
        + _RETURN)),
    _m("sources_reversed", "walks the sources from last to first",
       ("        for index, source in enumerate(self.sources):\n            cmd = source",
        "        for index, source in reversed(list(enumerate(self.sources))):\n            cmd = source")),
    _m("active_provider_only", "returns only the provider that get_command would use",
       (_RETURN, _RETURN.replace("return rv\n", "return rv[:1]\n"))),
    _m("merges_same_object", "drops a provider whose command object was already reported",
       (_SOURCE_APPEND, _SOURCE_APPEND.replace("if cmd is not None:",
                                               "if cmd is not None and all(p.command is not cmd for p in rv):"))),
    _m("collision_by_provider_count", "treats any name with two providers as a collision, even the same object",
       ("            if len({id(p.command) for p in providers}) > 1:\n", "            if len(providers) > 1:\n")),
    _m("collision_by_listing_groups", "counts the groups whose list_commands mention the name",
       ("            if len({id(p.command) for p in providers}) > 1:\n",
        "            if sum(name in g.list_commands(ctx) for g in [self, *self.sources]) > 1:\n")),
    _m("hidden_filtered", "leaves hidden commands out of the report",
       (_RETURN, _RETURN.replace("return rv\n", "return [p for p in rv if not p.command.hidden]\n"))),
    _m("cached_per_name", "memoises the provider list per name on the collection",
       ("        rv: list[CommandProvider] = []\n        cmd = super()",
        "        cache = self.__dict__.setdefault(\"_provider_cache\", {})\n\n"
        "        if cmd_name in cache:\n            return cache[cmd_name]\n\n"
        "        rv: list[CommandProvider] = []\n        cache[cmd_name] = rv\n        cmd = super()")),
    _m("reads_commands_mapping", "reads source.commands instead of calling source.get_command",
       (_SOURCE_LOOKUP, "            cmd = source.commands.get(cmd_name)\n")),
    _m("applies_chain_check", "runs the chain-mode nested-group check like get_command",
       (_SOURCE_APPEND, _SOURCE_APPEND.replace(
           "            if cmd is not None:\n",
           "            if cmd is not None:\n                if self.chain:\n"
           "                    _check_nested_chain(self, cmd_name, cmd)\n\n"))),
    _m("one_based_index", "numbers sources from 1", ("source_index=index,", "source_index=index + 1,")),
    _m("swallows_source_errors", "skips a source whose get_command raises",
       (_SOURCE_LOOKUP, "            try:\n                cmd = source.get_command(ctx, cmd_name)\n"
                        "            except Exception:\n                continue\n")),
    _m("warns_on_collision", "emits a UserWarning for every collision",
       ("                rv[name] = providers\n",
        "                import warnings\n\n"
        "                warnings.warn(f\"command {name!r} has several providers\", stacklevel=2)\n"
        "                rv[name] = providers\n")),
    _m("sorts_collision_names", "sorts collision names instead of following list_commands",
       ("        for name in self.list_commands(ctx):\n            providers",
        "        for name in sorted(self.list_commands(ctx)):\n            providers")),
    _m("expands_nested_collections", "reports the sources of a nested CommandCollection instead of the collection",
       (_SOURCE_LOOKUP, "            if isinstance(source, CommandCollection):\n"
                        "                rv.extend(source.get_command_providers(ctx, cmd_name))\n"
                        "                continue\n\n" + _SOURCE_LOOKUP)),
    _m("mutable_record", "CommandProvider is a plain mutable dataclass",
       ("@dataclasses.dataclass(frozen=True)\nclass CommandProvider:", "@dataclasses.dataclass\nclass CommandProvider:")),
    _m("none_when_empty", "returns None instead of an empty list",
       (_RETURN, _RETURN.replace("return rv\n", "return rv or None  # type: ignore[return-value]\n"))),
    # Compatibility (R10) mutants: correct diagnostics, but an existing behaviour is changed on the way.
    _m("list_commands_keeps_duplicates", "rewrites CommandCollection.list_commands and keeps duplicate names",
       ("        rv: set[str] = set(super().list_commands(ctx))\n\n        for source in self.sources:\n"
        "            rv.update(source.list_commands(ctx))\n",
        "        rv: list[str] = list(super().list_commands(ctx))\n\n        for source in self.sources:\n"
        "            rv.extend(source.list_commands(ctx))\n")),
    _m("chain_check_dropped", "drops the chain-mode check from CommandCollection.get_command",
       ("                if self.chain:\n                    _check_nested_chain(self, cmd_name, rv)\n\n", "")),
]

FEATURE_TESTS = '''import warnings

import pytest

import click
from click.testing import CliRunner


def _with(group, *commands):
    for command in commands:
        group.add_command(command)
    return group


def test_provider_record():
    """R1: keyword construction, attributes, equality by value, immutability."""
    g, c = click.Group("g"), click.Command("c")
    p = click.CommandProvider(group=g, source_index=1, command=c)
    assert p.group is g and p.source_index == 1 and p.command is c
    assert p == click.CommandProvider(group=g, source_index=1, command=c)
    assert p != click.CommandProvider(group=g, source_index=0, command=c)
    assert p != click.CommandProvider(group=g, source_index=1, command=click.Command("c"))
    for attr, value in (("group", click.Group("h")), ("source_index", 2), ("command", click.Command("d"))):
        with pytest.raises(AttributeError):
            setattr(p, attr, value)
    assert p.group is g and p.source_index == 1 and p.command is c


def test_sources_reported_in_order():
    """R2: one record per source that provides the name, in sources order."""
    da, db = click.Command("deploy"), click.Command("deploy")
    a, b = _with(click.Group("a"), da), _with(click.Group("b"), db)
    cli = click.CommandCollection("cli", sources=[a, b])
    providers = cli.get_command_providers(click.Context(cli), "deploy")
    assert all(isinstance(p, click.CommandProvider) for p in providers)
    assert [(p.group, p.source_index) for p in providers] == [(a, 0), (b, 1)]
    assert providers[0].command is da and providers[1].command is db


def test_own_command_comes_first():
    """R2: the collection's own command is reported first, with source_index None."""
    own, da, db = click.Command("deploy"), click.Command("deploy"), click.Command("deploy")
    a, b = _with(click.Group("a"), da), _with(click.Group("b"), db)
    cli = click.CommandCollection("cli", sources=[a, b])
    cli.add_command(own)
    got = [(p.group, p.source_index, p.command) for p in cli.get_command_providers(click.Context(cli), "deploy")]
    assert got == [(cli, None, own), (a, 0, da), (b, 1, db)]


def test_unprovided_and_exact_names():
    """R2: nothing provides the name -> []; names are not normalized."""
    a = _with(click.Group("a"), click.Command("deploy"))
    cli = click.CommandCollection("cli", sources=[a])
    ctx = click.Context(cli, token_normalize_func=str.lower)
    assert cli.get_command_providers(ctx, "missing") == []
    assert cli.get_command_providers(ctx, "DEPLOY") == []
    assert [p.group for p in cli.get_command_providers(ctx, "deploy")] == [a]


def test_first_provider_is_what_get_command_returns():
    """R3"""
    a = _with(click.Group("a"), click.Command("x"))
    b = _with(click.Group("b"), click.Command("x"), click.Command("y"))
    cli = click.CommandCollection("cli", sources=[a, b])
    cli.add_command(click.Command("y"))
    ctx = click.Context(cli)
    for name in ("x", "y", "z"):
        providers = cli.get_command_providers(ctx, name)
        found = cli.get_command(ctx, name)
        if providers:
            assert providers[0].command is found
        else:
            assert found is None
    assert len(cli.get_command_providers(ctx, "y")) == 2


def test_repeated_registrations_are_not_merged():
    """R4: same object in two sources, same group listed twice."""
    shared = click.Command("sync")
    a, b = _with(click.Group("a"), shared), _with(click.Group("b"), shared)
    cli = click.CommandCollection("cli", sources=[a, b, a])
    providers = cli.get_command_providers(click.Context(cli), "sync")
    assert [(p.group, p.source_index) for p in providers] == [(a, 0), (b, 1), (a, 2)]
    assert all(p.command is shared for p in providers)


def test_collisions_need_distinct_objects():
    """R5: only names with two distinct command objects are collisions."""
    shared = click.Command("sync")
    a = _with(click.Group("a"), click.Command("deploy"), shared, click.Command("status"))
    b = _with(click.Group("b"), click.Command("deploy"), shared, click.Command("logs"))
    cli = click.CommandCollection("cli", sources=[a, b])
    ctx = click.Context(cli)
    collisions = cli.get_command_collisions(ctx)
    assert isinstance(collisions, dict)
    assert list(collisions) == ["deploy"]
    assert collisions["deploy"] == cli.get_command_providers(ctx, "deploy")


def test_listed_but_unresolvable_names_are_not_collisions():
    """R5: a name listed by a source whose get_command returns None."""
    class ListsGhost(click.Group):
        def list_commands(self, ctx):
            return ["ghost"]

        def get_command(self, ctx, name):
            return None

    lister = ListsGhost("lister")
    real = _with(click.Group("real"), click.Command("ghost"))
    cli = click.CommandCollection("cli", sources=[lister, real])
    ctx = click.Context(cli)
    assert cli.get_command_collisions(ctx) == {}
    assert [(p.group, p.source_index) for p in cli.get_command_providers(ctx, "ghost")] == [(real, 1)]


def test_collisions_follow_list_commands_order():
    """R5: keys come in the order of the collection's list_commands."""
    class Reversed(click.CommandCollection):
        def list_commands(self, ctx):
            return sorted(super().list_commands(ctx), reverse=True)

    a = _with(click.Group("a"), click.Command("alpha"), click.Command("beta"))
    b = _with(click.Group("b"), click.Command("alpha"), click.Command("beta"))
    cli = Reversed("cli", sources=[a, b])
    assert list(cli.get_command_collisions(click.Context(cli))) == ["beta", "alpha"]


def test_no_collisions():
    """R5: no duplicated names, or no sources at all."""
    a = _with(click.Group("a"), click.Command("deploy"))
    b = _with(click.Group("b"), click.Command("status"))
    cli = click.CommandCollection("cli", sources=[a, b])
    assert cli.get_command_collisions(click.Context(cli)) == {}
    empty = click.CommandCollection("empty")
    assert empty.get_command_collisions(click.Context(empty)) == {}
    assert empty.get_command_providers(click.Context(empty), "deploy") == []


def test_hidden_commands_are_reported():
    """R6"""
    hidden, visible = click.Command("deploy", hidden=True), click.Command("deploy")
    a, b = _with(click.Group("a"), hidden), _with(click.Group("b"), visible)
    cli = click.CommandCollection("cli", sources=[a, b])
    ctx = click.Context(cli)
    assert [p.command for p in cli.get_command_providers(ctx, "deploy")] == [hidden, visible]
    assert list(cli.get_command_collisions(ctx)) == ["deploy"]


def test_results_are_independent_snapshots():
    """R7: new objects per call, not shared, not updated later."""
    a = _with(click.Group("a"), click.Command("deploy"))
    cli = click.CommandCollection("cli", sources=[a])
    ctx = click.Context(cli)
    first = cli.get_command_providers(ctx, "deploy")
    assert first is not cli.get_command_providers(ctx, "deploy")
    first.clear()
    assert len(cli.get_command_providers(ctx, "deploy")) == 1
    snapshot = cli.get_command_providers(ctx, "deploy")
    cli.add_source(_with(click.Group("b"), click.Command("deploy")))
    assert len(snapshot) == 1
    assert len(cli.get_command_providers(ctx, "deploy")) == 2
    collisions = cli.get_command_collisions(ctx)
    collisions.clear()
    assert list(cli.get_command_collisions(ctx)) == ["deploy"]


def test_changes_after_a_call_are_reflected():
    """R7: add_source, sources.append and add_command after an earlier call."""
    a = _with(click.Group("a"), click.Command("deploy"))
    cli = click.CommandCollection("cli", sources=[a])
    ctx = click.Context(cli)
    assert cli.get_command_collisions(ctx) == {}
    assert cli.get_command_providers(ctx, "status") == []
    b = _with(click.Group("b"), click.Command("deploy"))
    cli.add_source(b)
    assert list(cli.get_command_collisions(ctx)) == ["deploy"]
    c = _with(click.Group("c"), click.Command("status"))
    cli.sources.append(c)
    assert [(p.group, p.source_index) for p in cli.get_command_providers(ctx, "status")] == [(c, 2)]
    a.add_command(click.Command("status"))
    cli.add_command(click.Command("status"))
    got = [(p.group, p.source_index) for p in cli.get_command_providers(ctx, "status")]
    assert got == [(cli, None), (a, 0), (c, 2)]


def test_sources_with_custom_lookup():
    """R8: a lazily loading source is consulted through its own get_command."""
    class Lazy(click.Group):
        def __init__(self, name, loaded):
            super().__init__(name)
            self.loaded = loaded

        def list_commands(self, ctx):
            return sorted(self.loaded)

        def get_command(self, ctx, name):
            return self.loaded.get(name)

    lazy_deploy, deploy = click.Command("deploy"), click.Command("deploy")
    lazy = Lazy("lazy", {"deploy": lazy_deploy})
    assert lazy.commands == {}
    a = _with(click.Group("a"), deploy)
    cli = click.CommandCollection("cli", sources=[lazy, a])
    ctx = click.Context(cli)
    got = [(p.group, p.source_index, p.command) for p in cli.get_command_providers(ctx, "deploy")]
    assert got == [(lazy, 0, lazy_deploy), (a, 1, deploy)]
    assert list(cli.get_command_collisions(ctx)) == ["deploy"]


def test_nested_collection_is_one_provider():
    """R8"""
    dx, dy = click.Command("deploy"), click.Command("deploy")
    x, y = _with(click.Group("x"), dx), _with(click.Group("y"), dy)
    inner = click.CommandCollection("inner", sources=[x, y])
    outer = click.CommandCollection("outer", sources=[inner])
    ctx = click.Context(outer)
    got = [(p.group, p.source_index, p.command) for p in outer.get_command_providers(ctx, "deploy")]
    assert got == [(inner, 0, dx)]
    assert outer.get_command_collisions(ctx) == {}
    assert list(inner.get_command_collisions(click.Context(inner))) == ["deploy"]


def test_chain_mode_groups_are_reported():
    """R9: no chain-mode check in the diagnostics."""
    tools = click.Group("tools")
    a = _with(click.Group("a"), tools)
    cli = click.CommandCollection("cli", sources=[a], chain=True)
    ctx = click.Context(cli)
    assert [(p.group, p.command) for p in cli.get_command_providers(ctx, "tools")] == [(a, tools)]
    assert cli.get_command_collisions(ctx) == {}


def test_errors_propagate():
    """R9: exceptions from source lookups and listings propagate, also during resilient parsing."""
    class BrokenLookup(click.Group):
        def get_command(self, ctx, name):
            raise LookupError("lookup broke")

    class BrokenListing(click.Group):
        def list_commands(self, ctx):
            raise LookupError("listing broke")

    cli = click.CommandCollection("cli", sources=[click.Group("ok"), BrokenLookup("bad")])
    other = click.CommandCollection("other", sources=[BrokenListing("bad")])
    for resilient in (False, True):
        with pytest.raises(LookupError, match="lookup broke"):
            cli.get_command_providers(click.Context(cli, resilient_parsing=resilient), "deploy")
        with pytest.raises(LookupError, match="listing broke"):
            other.get_command_collisions(click.Context(other, resilient_parsing=resilient))


def test_no_warnings_and_nothing_changes():
    """R9 R10: calling the diagnostics warns about nothing and changes nothing."""
    a = _with(click.Group("a"), click.Command("deploy", hidden=True), click.Command("status"))
    b = _with(click.Group("b"), click.Command("deploy"))
    cli = click.CommandCollection("cli", sources=[a, b])
    ctx = click.Context(cli)

    def state():
        return (cli.list_commands(ctx), cli.get_command(ctx, "deploy"), list(cli.sources),
                dict(cli.commands), dict(a.commands), CliRunner().invoke(cli, ["--help"]).output)

    before = state()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cli.get_command_providers(ctx, "deploy")
        cli.get_command_collisions(ctx)
    assert state() == before
'''

COMPAT_TESTS = '''"""Existing CommandCollection behaviour that must not change (pass before and after the feature)."""
import warnings

import pytest

import click
from click.testing import CliRunner


def _echo(name, text, hidden=False):
    @click.command(name, hidden=hidden)
    def cmd():
        click.echo(text)

    return cmd


def _with(group, *commands):
    for command in commands:
        group.add_command(command)
    return group


def test_lookup_precedence_is_unchanged():
    """R10: own commands first, then sources in order, first match wins."""
    a = _with(click.Group("a"), _echo("deploy", "from a"))
    b = _with(click.Group("b"), _echo("deploy", "from b"), _echo("status", "status from b"))
    cli = click.CommandCollection("cli", sources=[a, b])
    runner = CliRunner()
    assert runner.invoke(cli, ["deploy"]).output == "from a\\n"
    assert runner.invoke(cli, ["status"]).output == "status from b\\n"
    cli.add_command(_echo("deploy", "own"))
    assert runner.invoke(cli, ["deploy"]).output == "own\\n"


def test_list_commands_is_sorted_without_duplicates():
    """R10"""
    a = _with(click.Group("a"), _echo("zeta", "z"), _echo("alpha", "a"))
    b = _with(click.Group("b"), _echo("alpha", "a"), _echo("mid", "m"))
    cli = click.CommandCollection("cli", sources=[a, b])
    cli.add_command(_echo("beta", "b"))
    assert cli.list_commands(click.Context(cli)) == ["alpha", "beta", "mid", "zeta"]


def test_chain_mode_still_rejects_a_group_from_a_source():
    """R10"""
    a = _with(click.Group("a"), click.Group("tools"))
    cli = click.CommandCollection("cli", sources=[a], chain=True)
    with pytest.raises(RuntimeError):
        cli.get_command(click.Context(cli), "tools")


def test_hidden_winner_still_hides_the_name_in_help():
    """R10"""
    a = _with(click.Group("a"), _echo("deploy", "hidden", hidden=True))
    b = _with(click.Group("b"), _echo("deploy", "visible"), _echo("status", "s"))
    cli = click.CommandCollection("cli", sources=[a, b])
    out = CliRunner().invoke(cli, ["--help"]).output
    assert "status" in out and "deploy" not in out


def test_completion_is_unchanged():
    """R10: completion offers visible winners only."""
    a = _with(click.Group("a"), _echo("deploy", "hidden", hidden=True))
    b = _with(click.Group("b"), _echo("deploy", "visible"), _echo("status", "s"))
    cli = click.CommandCollection("cli", sources=[a, b])
    ctx = cli.make_context("cli", [], resilient_parsing=True)
    assert [item.value for item in cli.shell_complete(ctx, "")] == ["status"]


def test_duplicate_names_raise_no_warnings():
    """R10"""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        a = _with(click.Group("a"), _echo("deploy", "from a"))
        b = _with(click.Group("b"), _echo("deploy", "from b"))
        cli = click.CommandCollection("cli", sources=[a, b])
        result = CliRunner().invoke(cli, ["deploy"])
    assert result.exit_code == 0 and result.output == "from a\\n"
'''


def build(knobs: dict) -> Draft:
    if knobs != {"scope": "diagnostics"}:
        raise ValueError(f"unsupported knobs {knobs}")
    return Draft(
        family=FAMILY, slug="command-collection-providers", title="CommandCollection provider diagnostics",
        knobs=dict(knobs), instruction=INSTRUCTION, gold_edits=GOLD,
        test_files={"tests/test_command_collection_providers.py": FEATURE_TESTS},
        compat_test_files={"tests/test_command_collection_compat.py": COMPAT_TESTS},
        focus_symbols=["src/click/core.py::CommandCollection.get_command",
                       "src/click/core.py::CommandCollection.list_commands",
                       "src/click/core.py::Group.get_command", "src/click/core.py::Group.list_commands",
                       "src/click/core.py::Group.format_commands", "src/click/core.py::Group.resolve_command",
                       "src/click/core.py::_complete_visible_commands", "src/click/core.py::_check_nested_chain"],
        mutants=MUTANTS,
        novelty_probes=[r"get_command_providers|get_command_collisions|class CommandProvider"],
        novelty_queries=["CommandCollection collision", "command providers", "shadowed command"],
        axes=AXES,
    )
