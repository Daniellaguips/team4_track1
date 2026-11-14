"""Blueprint: grouping subcommands into named sections in a group's help page (rendering).

Knobs:
  order    "first_seen" | "alphabetical"   order of the named sections
  default  "first" | "last"                position of the default "Commands" section
"""
from __future__ import annotations

from ..model import Draft, Edit, Mutant

FAMILY = "sections"
KNOBS = {"order": ["first_seen", "alphabetical"], "default": ["first", "last"]}
AXES = {
    "capability": "help-page rendering / output layout",
    "module": "click.core.Command.__init__ + Group.format_commands (HelpFormatter)",
    "behavior_shape": "partition + ordering of rendered rows with shared width budget",
    "integration": "HelpFormatter.section/write_dl, hidden commands, short-help truncation, "
                   "list_commands order",
}

OLD_BLOCK = """        # allow for 3 times the default spacing
        if len(commands):
            limit = formatter.width - 6 - max(len(cmd[0]) for cmd in commands)

            rows = []
            for subcommand, cmd in commands:
                help = cmd.get_short_help_str(limit)
                rows.append((subcommand, help))

            if rows:
                with formatter.section(_("Commands")):
                    formatter.write_dl(rows)
"""


def build(knobs: dict) -> Draft:
    alpha = knobs["order"] == "alphabetical"
    dfirst = knobs["default"] == "first"
    order_rule = ("sorted alphabetically by section name (plain string comparison)" if alpha else
                  "in the order in which each section name is first encountered while walking the "
                  "visible commands in `list_commands(ctx)` order")
    pos_rule = "before all named sections" if dfirst else "after all named sections"
    instruction = f"""# Help sections for subcommands

A group with many subcommands prints them all under one `Commands:` heading. Allow commands to
declare a help section so the group's help page lists them under separate headings.

## Public interface

- New keyword argument `help_section: str | None = None` on `click.Command.__init__`, stored as
  the attribute `Command.help_section`. It is therefore accepted by `@click.command(...)`,
  `@group.command(...)`, `@group.group(...)` and `click.Group(...)`.
- `Command.to_info_dict()` output does **not** change.
- The rendering lives in `Group.format_commands(ctx, formatter)`.

## Requirements

**R1 — Which commands.** As today, the listed commands are those returned by
`self.list_commands(ctx)` for which `get_command` returns a command that is not hidden, in that
order.

**R2 — Default section.** Commands whose `help_section` is `None` or exactly `"Commands"` are
listed in the default section with the heading `Commands` (the same heading as today).

**R3 — Named sections.** Every other `help_section` value is a section heading of its own, used
verbatim (case-sensitive; `"Admin"` and `"admin"` are different sections). Inside a section,
commands keep the R1 order.

**R4 — Section order.** The default section is placed {pos_rule}. Named sections are ordered
{order_rule}. Sections without any listed command (e.g. only hidden commands) are not printed.

**R5 — Rendering.** Each section is written exactly like today's commands section — with
`formatter.section(<heading>)` followed by `formatter.write_dl(rows)` where a row is
`(command name, short help)` — so the output for a section looks like:

```
Admin:
  purge-cache  Drop caches.
```

Because each section is a separate `write_dl` call, the description column is aligned
independently within each section. The short-help length limit stays one value computed over
**all** listed commands, as today: `formatter.width - 6 - <length of the longest listed command
name>`, passed to `cmd.get_short_help_str(limit)`.

**R6 — Compatibility.** When no listed command has a named section, the help output is identical
to the current output.
"""
    order_expr = "sorted(named)" if alpha else "named"
    layout = "[None, *ordered]" if dfirst else "[*ordered, None]"
    new_block = f"""        # allow for 3 times the default spacing
        if len(commands):
            limit = formatter.width - 6 - max(len(cmd[0]) for cmd in commands)

            sections: dict[str | None, list[tuple[str, str]]] = {{}}
            for subcommand, cmd in commands:
                section = getattr(cmd, "help_section", None)
                if section == "Commands":
                    section = None
                help = cmd.get_short_help_str(limit)
                sections.setdefault(section, []).append((subcommand, help))

            named = [name for name in sections if name is not None]
            ordered = {order_expr}
            for section in {layout}:
                rows = sections.get(section)
                if not rows:
                    continue
                heading = _("Commands") if section is None else section
                with formatter.section(heading):
                    formatter.write_dl(rows)
"""
    C = "src/click/core.py"
    gold = [
        Edit(C, "        deprecated: bool | str = False,\n    ) -> None:\n        #: the name the command thinks it has.",
             "        deprecated: bool | str = False,\n        help_section: str | None = None,\n    ) -> None:\n"
             "        #: the name the command thinks it has.", "replace"),
        Edit(C, "        self.hidden = hidden\n        self.deprecated = deprecated\n",
             "        #: Heading under which a parent group lists this command.\n"
             "        self.help_section = help_section\n"),
        Edit(C, OLD_BLOCK, new_block, "replace"),
    ]

    def expected_order(named_first_seen):
        named = sorted(named_first_seen) if alpha else list(named_first_seen)
        return (["Commands"] + named) if dfirst else (named + ["Commands"])

    order1 = expected_order(["Users", "Data"])
    tests = f'''import click
from click.testing import CliRunner


def _cli():
    @click.group()
    def cli():
        pass

    @cli.command(help="Create a repo.")
    def init():
        pass

    @cli.command(help="Drop caches.", help_section="Users")
    def purge_cache():
        pass

    @cli.command(help="Export data.", help_section="Data")
    def export():
        pass

    @cli.command(help="Sync it.")
    def sync():
        pass

    @cli.command(help="Add a user.", help_section="Users")
    def adduser():
        pass

    @cli.command(help="Secret.", help_section="Ops", hidden=True)
    def zap():
        pass

    return cli


def _help(cli):
    r = CliRunner().invoke(cli, ["--help"])
    assert r.exit_code == 0, r.output
    return r.output


def _headings(out):
    return [l[:-1] for l in out.splitlines() if l and not l.startswith(" ") and l.endswith(":")
            and l != "Options:"]


def test_attribute():
    """[R2 interface] help_section stored on Command, default None."""
    assert click.Command("x").help_section is None
    assert click.Command("x", help_section="Admin").help_section == "Admin"
    assert click.Group("g", help_section="Admin").help_section == "Admin"
    assert "help_section" not in click.Command("x", help_section="A").to_info_dict(
        click.Context(click.Command("x")))


def test_sections_and_order():
    """[R1][R2][R3][R4]"""
    assert _headings(_help(_cli())) == {order1!r}


def test_rows_per_section_aligned_independently():
    """[R3][R5]"""
    out = _help(_cli())
    assert "Commands:\\n  init  Create a repo.\\n  sync  Sync it.\\n" in out
    assert "Users:\\n  adduser      Add a user.\\n  purge-cache  Drop caches.\\n" in out
    assert "Data:\\n  export  Export data.\\n" in out


def test_hidden_only_section_omitted():
    """[R1][R4]"""
    out = _help(_cli())
    assert "Ops" not in out
    assert "zap" not in out


def test_explicit_commands_section_merges_with_default():
    """[R2]"""
    @click.group()
    def cli():
        pass

    @cli.command(help="One.", help_section="Commands")
    def one():
        pass

    @cli.command(help="Two.")
    def two():
        pass

    out = _help(cli)
    assert _headings(out) == ["Commands"]
    assert "Commands:\\n  one  One.\\n  two  Two.\\n" in out


def test_case_sensitive_names():
    """[R3][R4]"""
    @click.group()
    def cli():
        pass

    @cli.command(help_section="Admin")
    def b():
        pass

    @cli.command(help_section="admin")
    def a():
        pass

    assert _headings(_help(cli)) == {(sorted(["admin", "Admin"]) if alpha else ["admin", "Admin"])!r}


def test_only_named_sections():
    """[R4] no default section when every command is in a named section."""
    @click.group()
    def cli():
        pass

    @cli.command(help_section="Zeta")
    def a():
        pass

    @cli.command(help_section="Alpha")
    def b():
        pass

    assert _headings(_help(cli)) == {(sorted(["Zeta", "Alpha"]) if alpha else ["Zeta", "Alpha"])!r}


def test_short_help_limit_uses_all_commands():
    """[R5]"""
    long_help = "This sentence is definitely much longer than thirty two characters in total."

    @click.group(context_settings={{"terminal_width": 60}})
    def cli():
        pass

    @cli.command(help=long_help)
    def a():
        pass

    @cli.command("very-long-command-name", help="Short.", help_section="Admin")
    def v():
        pass

    out = _help(cli)
    expected = cli.commands["a"].get_short_help_str(60 - 6 - len("very-long-command-name"))
    assert expected.endswith("...")
    assert f"Commands:\\n  a  {{expected}}\\n" in out


def test_no_sections_output_unchanged():
    """[R6]"""
    @click.group()
    def cli():
        pass

    @cli.command(help="Hello.")
    def hello():
        pass

    @cli.command(help="World.")
    def world():
        pass

    out = _help(cli)
    assert out.endswith("Commands:\\n  hello  Hello.\\n  world  World.\\n")
    assert cli.commands["hello"].help_section is None


def test_subgroup_section():
    """[R3] groups can be placed in sections too."""
    @click.group()
    def cli():
        pass

    @cli.group(help="Manage users.", help_section="Admin")
    def users():
        pass

    @cli.command(help="Run.")
    def run():
        pass

    out = _help(cli)
    assert "Admin:\\n  users  Manage users.\\n" in out
'''
    mutants = [
        Mutant("global_alignment", "renders all sections with one shared column width",
               (Edit(C, "                with formatter.section(heading):\n                    formatter.write_dl(rows)\n",
                     "                width = max(len(n) for r in sections.values() for n, _ in r)\n"
                     "                with formatter.section(heading):\n"
                     "                    formatter.write_dl([(n.ljust(width), h) for n, h in rows])\n",
                     "replace"),)),
        Mutant("order_flipped", "orders named sections by the other rule",
               (Edit(C, f"            ordered = {order_expr}\n",
                     "            ordered = " + ("named" if alpha else "sorted(named)") + "\n", "replace"),)),
        Mutant("default_position_flipped", "puts the default section on the other side",
               (Edit(C, f"            for section in {layout}:\n",
                     "            for section in " + ("[*ordered, None]" if dfirst else "[None, *ordered]") + ":\n",
                     "replace"),)),
        Mutant("explicit_commands_separate", "treats help_section='Commands' as a separate section",
               (Edit(C, '                if section == "Commands":\n                    section = None\n', "",
                     "replace"),)),
        Mutant("per_section_limit", "computes the short-help limit per section",
               (Edit(C, "                help = cmd.get_short_help_str(limit)\n                sections.setdefault",
                     "                help = cmd.get_short_help_str(\n"
                     "                    formatter.width - 6 - max(len(n) for n, c in commands\n"
                     "                    if getattr(c, 'help_section', None) == getattr(cmd, 'help_section', None))\n"
                     "                )\n                sections.setdefault", "replace"),)),
        Mutant("case_insensitive", "merges sections case-insensitively",
               (Edit(C, '                section = getattr(cmd, "help_section", None)\n',
                     '                section = getattr(cmd, "help_section", None)\n'
                     "                section = section.title() if section else section\n", "replace"),)),
    ]
    return Draft(
        family=FAMILY, slug="help-command-sections", title="Help sections for subcommands",
        knobs=dict(knobs), instruction=instruction, gold_edits=gold,
        test_files={"tests/test_help_sections.py": tests},
        focus_symbols=["src/click/core.py::Group.format_commands", "src/click/core.py::Command.__init__",
                       "src/click/formatting.py::HelpFormatter.write_dl",
                       "src/click/core.py::Command.get_short_help_str"],
        mutants=mutants,
        novelty_probes=[r"help_section|command_section|section_name"],
        novelty_queries=["help section", "command sections", "group commands help"],
        axes=AXES,
    )
