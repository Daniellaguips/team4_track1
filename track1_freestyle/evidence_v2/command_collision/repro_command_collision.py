"""Reproduce current CommandCollection name-resolution behaviour (no feature code involved).

Run against a click checkout:
  PYTHONPATH=<click>/src python repro_command_collision.py
Each case prints observable facts only; nothing here is a proposed API.
"""
from __future__ import annotations

import click
from click.shell_completion import ShellComplete
from click.testing import CliRunner


def make(name, label, hidden=False):
    @click.command(name, hidden=hidden, help=f"{label} {name}")
    def _cmd():
        click.echo(f"{label}:{name}")
    return _cmd


def groups():
    a, b = click.Group("a"), click.Group("b")
    a.add_command(make("deploy", "A"))
    a.add_command(make("status", "A"))
    b.add_command(make("deploy", "B"))
    b.add_command(make("logs", "B"))
    return a, b


def lookup(col, name):
    ctx = click.Context(col)
    cmd = col.get_command(ctx, name)
    return None if cmd is None else cmd.help


def run(col, *args):
    r = CliRunner().invoke(col, list(args))
    return r.exit_code, r.output.strip()


def case(title, **facts):
    print(f"## {title}")
    for k, v in facts.items():
        print(f"   {k}: {v!r}")


print(f"click imported from {click.__file__}")

a, b = groups()
col = click.CommandCollection("cli", sources=[a, b])
ctx = click.Context(col)
case("1 first source wins; list_commands de-duplicates",
     get_command_deploy=lookup(col, "deploy"),
     invoke_deploy=run(col, "deploy"),
     list_commands=col.list_commands(ctx),
     providers_visible_via_public_api="none (get_command returns one object, list_commands names only)")

a, b = groups()
case("2 source order decides the winner",
     sources_ab=lookup(click.CommandCollection(sources=[a, b]), "deploy"),
     sources_ba=lookup(click.CommandCollection(sources=[b, a]), "deploy"))

a, b = groups()
col = click.CommandCollection("cli", sources=[a, b])
col.add_command(make("deploy", "LOCAL"))
case("3 collection-local command shadows every source", get_command_deploy=lookup(col, "deploy"))

a, b = groups()
shared = make("sync", "SHARED")
a.add_command(shared)
b.add_command(shared)
col = click.CommandCollection("cli", sources=[a, b])
c = click.Context(col)
case("4 same object registered in two sources",
     resolved_is_shared=col.get_command(c, "sync") is shared,
     listed_once=col.list_commands(c).count("sync") == 1)

a, b = groups()
a.add_command(make("logs", "A-HIDDEN", hidden=True))
col = click.CommandCollection("cli", sources=[a, b])
code, out = run(col, "--help")
case("5 hidden command in an earlier source shadows a visible later one",
     get_command_logs=lookup(col, "logs"),
     logs_in_help=any(line.strip().startswith("logs") for line in out.splitlines()),
     invoke_logs=run(col, "logs"))
comp = ShellComplete(col, {}, "cli", "_CLI_COMPLETE")
case("5b completion for 'l' (hidden winner suppresses the visible alternative)",
     completions=[i.value for i in comp.get_completions([], "l")])

a, b = groups()
col = click.CommandCollection("cli", sources=[a])
before = lookup(col, "logs")
col.add_source(b)
case("6 add_source changes resolution immediately (no caching)",
     before=before, after=lookup(col, "logs"))

a, b = groups()
lst = [a]
col = click.CommandCollection("cli", sources=lst)
lst.append(b)
empty: list = []
col2 = click.CommandCollection("cli", sources=empty)
empty.append(a)
case("6b the sources list is aliased unless it is empty",
     non_empty_list_aliased=col.sources is lst, sees_later_append=lookup(col, "logs"),
     empty_list_aliased=col2.sources is empty, sees_append_to_empty=lookup(col2, "deploy"))


class LazyGroup(click.Group):
    def list_commands(self, ctx):
        return ["deploy", "ghost"]

    def get_command(self, ctx, name):
        return make("deploy", "LAZY") if name == "deploy" else None


a, b = groups()
col = click.CommandCollection("cli", sources=[LazyGroup("lazy"), a])
c = click.Context(col)
case("7 custom source overrides are consulted; listed-but-unresolvable names",
     get_command_deploy=lookup(col, "deploy"),
     list_commands=col.list_commands(c),
     ghost_resolves=lookup(col, "ghost"),
     ghost_in_help="ghost" in run(col, "--help")[1])

a, b = groups()
sub = click.Group("deploy", help="GROUP deploy")
b2 = click.Group("b2")
b2.add_command(sub)
col = click.CommandCollection("cli", sources=[a, b2], chain=True)
col_rev = click.CommandCollection("cli", sources=[b2, a], chain=True)
try:
    rev = lookup(col_rev, "deploy")
except RuntimeError as e:
    rev = f"RuntimeError: {e}"
case("8 chain mode: nested-group check only applies to the winning command",
     shadowed_group_ok=lookup(col, "deploy"), group_wins=rev)

a, b = groups()
col = click.CommandCollection("cli", sources=[a, b])
case("9 unknown command: suggestions only consider collection-local commands",
     invoke_deplo=run(col, "deplo"))

a, b = groups()
col = click.CommandCollection("cli", sources=[a, b])
info = col.to_info_dict(click.Context(col))
case("10 to_info_dict reports one entry per name",
     commands={k: v["help"] for k, v in info["commands"].items()})
