import warnings

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
            return list(reversed(super().list_commands(ctx)))

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
