"""Blueprint: unique-prefix subcommand abbreviations on ``click.Group`` (command dispatch).

Knobs:
  hidden     "excluded" | "included"     do hidden commands take part in prefix matching
  ambiguity  "alphabetical" | "shortest"  order of candidates in the ambiguity error
"""
from __future__ import annotations

from ..model import Draft, Edit, Mutant

FAMILY = "abbrev"
KNOBS = {"hidden": ["excluded", "included"], "ambiguity": ["alphabetical", "shortest"]}
AXES = {
    "capability": "command dispatch / name resolution",
    "module": "click.core.Group.resolve_command (+ CommandCollection, chain mode)",
    "behavior_shape": "lookup precedence chain with ambiguity error",
    "integration": "token_normalize_func, list_commands/get_command, chain mode, sub-context naming",
    "novelty_note": "upstream docs/extending-click.md and examples/aliases show a user-land "
                    "AliasedGroup recipe (subclass overriding get_command); Click itself ships no "
                    "abbreviation option. This task's built-in opt-in, precedence, normalization, "
                    "hidden-command, resilient-parsing and ambiguity-order rules are not in that recipe.",
}


def _order(names, mode):
    return sorted(names) if mode == "alphabetical" else sorted(names, key=lambda n: (len(n), n))


def build(knobs: dict) -> Draft:
    hid_in = knobs["hidden"] == "included"
    mode = knobs["ambiguity"]
    hidden_rule = (
        "Hidden commands (`hidden=True`) take part in prefix matching exactly like visible ones."
        if hid_in else
        "Hidden commands (`hidden=True`) never take part in prefix matching; they can still be "
        "invoked by their exact name."
    )
    order_rule = (
        "sorted alphabetically" if mode == "alphabetical" else
        "sorted by name length, shortest first; names of equal length are sorted alphabetically"
    )
    st = ", ".join(_order(["start", "status", "stop"], mode))
    instruction = f"""# Unique-prefix command abbreviations for `click.Group`

Users of large command-line tools like typing `tool stat` instead of `tool status`. Add opt-in
support to `click.Group` for invoking a subcommand by any unambiguous prefix of its name.

## Public interface

- New keyword argument `allow_abbreviations: bool = False` on `click.Group.__init__`, stored as
  the attribute `allow_abbreviations`. Because `click.group()` and `Group.group()` forward keyword
  arguments to the class, `@click.group(allow_abbreviations=True)` must work too, and so must
  subclasses such as `click.CommandCollection` (which forwards its keyword arguments to `Group`).
- The behaviour lives in `Group.resolve_command(ctx, args)`, which keeps its signature and return
  shape `(command_name, command, remaining_args)`.

## Requirements

**R1 — Off by default.** With `allow_abbreviations=False` nothing changes: an unknown name such as
`st` fails exactly as today (`Error: No such command 'st'.`, exit code 2).

**R2 — Lookup order.** For the first remaining argument (the *token*), resolution is:
1. the existing exact lookup with `get_command(ctx, token)`;
2. the existing retry with `ctx.token_normalize_func(token)` when a normalize function is set
   (from now on *token* means this normalized value);
3. only if both fail and `allow_abbreviations` is true: prefix matching (R3–R6).
An exact name therefore always wins, even if it is also a prefix of other names (with commands
`run` and `runner`, `run` invokes `run` and `runn` invokes `runner`).

**R3 — Candidates.** Iterate over `self.list_commands(ctx)` (not the `commands` mapping, so groups
that compute their commands dynamically — e.g. `click.CommandCollection(sources=[a, b])` — work) and fetch each command
with `self.get_command(ctx, name)`; names for which `get_command` returns `None` are skipped. A
name is a candidate when it starts with the token. When `ctx.token_normalize_func` is set, the
name is passed through that function before the comparison (the command is still the one
registered under the original name). {hidden_rule} An empty token never matches anything.

**R4 — Exactly one candidate.** It is resolved: the returned command name is the candidate's
*registered* name, not the typed prefix. Consequently `ctx.invoked_subcommand` holds the full
name and the sub-command's context is created with the full name, so for example
`cli stat --help` prints a usage line starting with `Usage: cli status`.

**R5 — Several candidates.** Raise `click.UsageError` (with the group's context, so the usage line is
shown, e.g. `Usage: cli [OPTIONS] COMMAND [ARGS]...`) with the message `Ambiguous command '<token>'. Could be: <names>.` where `<token>` is the
token after normalization and `<names>` are the candidates' registered names {order_rule},
joined with `", "`. For commands `start`, `status`, `stop` and the token `st`, the output contains
`Error: Ambiguous command 'st'. Could be: {st}.` and the exit code is 2. During resilient parsing
(`ctx.resilient_parsing`, used by shell completion) no error is raised; the token is treated as
unknown instead.

**R6 — No candidate.** Behaviour is unchanged: `Error: No such command '<token>'.`, exit code 2.

**R7 — Chained groups.** In `chain=True` groups every subcommand token is resolved by the same rules,
so `cli bui te` runs `build` then `test` when those are unique prefixes.

Help output, shell completion and every other existing behaviour must stay unchanged.
"""
    hidden_skip = "" if hid_in else "            if cmd.hidden:\n                continue\n"
    sort_expr = ("sorted(n for n, _ in matches)" if mode == "alphabetical"
                 else "sorted((n for n, _ in matches), key=lambda n: (len(n), n))")
    helper = f'''
    def _resolve_abbreviation(
        self, ctx: Context, token: str
    ) -> tuple[str, Command | None]:
        """Resolve ``token`` as a unique prefix of a command name."""
        normalize = ctx.token_normalize_func
        matches: list[tuple[str, Command]] = []
        for name in self.list_commands(ctx):
            key = normalize(name) if normalize is not None else name
            if not key.startswith(token):
                continue
            cmd = self.get_command(ctx, name)
            if cmd is None:
                continue
{hidden_skip}            matches.append((name, cmd))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1 and not ctx.resilient_parsing:
            names = {sort_expr}
            raise UsageError(
                _("Ambiguous command {{name!r}}. Could be: {{names}}.").format(
                    name=token, names=", ".join(names)
                ),
                ctx,
            )
        return token, None

    def resolve_command('''
    gold = [
        Edit("src/click/core.py",
             "        result_callback: t.Callable[..., t.Any] | None = None,\n        **kwargs: t.Any,\n",
             "        result_callback: t.Callable[..., t.Any] | None = None,\n"
             "        allow_abbreviations: bool = False,\n        **kwargs: t.Any,\n", "replace"),
        Edit("src/click/core.py", "        self.chain = chain\n",
             "        #: Resolve unambiguous prefixes of subcommand names.\n"
             "        self.allow_abbreviations = allow_abbreviations\n"),
        Edit("src/click/core.py", "\n    def resolve_command(", helper, "replace"),
        Edit("src/click/core.py",
             "            cmd = self.get_command(ctx, cmd_name)\n\n        # If we don't find the command",
             "            cmd = self.get_command(ctx, cmd_name)\n\n"
             "        if cmd is None and self.allow_abbreviations and cmd_name:\n"
             "            cmd_name, cmd = self._resolve_abbreviation(ctx, cmd_name)\n\n"
             "        # If we don't find the command", "replace"),
    ]
    se = ", ".join(_order(["secret", "serve"], mode))
    hidden_test = (
        f'''    r = _run(g, ["se"])
    assert r.exit_code == 2
    assert "Error: Ambiguous command 'se'. Could be: {se}." in r.output'''
        if hid_in else
        '''    assert _run(g, ["se"]).output == "serve\\n"'''
    )
    sta = ", ".join(_order(["start", "status"], mode))
    tests = f'''import click
from click.testing import CliRunner


def _group(**kw):
    @click.group(**kw)
    @click.pass_context
    def cli(ctx):
        pass

    for name in ("start", "status", "stop", "run", "runner"):
        def make(n):
            @cli.command(n)
            def _c():
                click.echo(n)
        make(name)
    return cli


def _run(cli, args):
    return CliRunner().invoke(cli, args)


def test_attribute_default_and_off_by_default():
    """[R1] attribute stored, default False, no abbreviation when off."""
    assert click.Group().allow_abbreviations is False
    assert click.Group(allow_abbreviations=True).allow_abbreviations is True
    cli = _group()
    assert cli.allow_abbreviations is False
    r = _run(cli, ["sto"])
    assert r.exit_code == 2
    assert "Error: No such command 'sto'." in r.output


def test_unique_prefix_invokes_command():
    """[R3][R4]"""
    cli = _group(allow_abbreviations=True)
    assert _run(cli, ["sto"]).output == "stop\\n"
    assert _run(cli, ["star"]).output == "start\\n"
    assert _run(cli, ["statu"]).output == "status\\n"


def test_exact_name_wins():
    """[R2]"""
    cli = _group(allow_abbreviations=True)
    assert _run(cli, ["run"]).output == "run\\n"
    assert _run(cli, ["runn"]).output == "runner\\n"


def test_ambiguous_prefix_error():
    """[R5]"""
    r = _run(_group(allow_abbreviations=True), ["st"])
    assert r.exit_code == 2
    assert "Error: Ambiguous command 'st'. Could be: {st}." in r.output
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in r.output


def test_ambiguous_two_candidates():
    """[R5]"""
    r = _run(_group(allow_abbreviations=True), ["sta"])
    assert r.exit_code == 2
    assert "Error: Ambiguous command 'sta'. Could be: {sta}." in r.output


def test_no_candidate_and_empty_token():
    """[R3][R6]"""
    cli = _group(allow_abbreviations=True)
    r = _run(cli, ["xyz"])
    assert r.exit_code == 2
    assert "Error: No such command 'xyz'." in r.output
    r = _run(cli, [""])
    assert r.exit_code == 2
    assert "Error: No such command ''." in r.output


def test_full_name_is_used_for_subcontext():
    """[R4]"""
    seen = []

    @click.group(allow_abbreviations=True)
    @click.pass_context
    def cli(ctx):
        seen.append(ctx.invoked_subcommand)

    @cli.command()
    def status():
        pass

    @cli.command()
    def stop():
        pass

    r = _run(cli, ["stat", "--help"])
    assert r.exit_code == 0
    assert r.output.startswith("Usage: cli status")
    _run(cli, ["stat"])
    assert seen[-1] == "status"


def test_hidden_commands():
    """[R3] hidden handling; exact name always works."""
    @click.group(allow_abbreviations=True)
    def g():
        pass

    @g.command(hidden=True)
    def secret():
        click.echo("secret")

    @g.command()
    def serve():
        click.echo("serve")

{hidden_test}
    assert _run(g, ["secret"]).output == "secret\\n"


def test_chain_mode():
    """[R7]"""
    @click.group(chain=True, allow_abbreviations=True)
    def cli():
        pass

    for n in ("build", "bundle", "test"):
        def make(n):
            @cli.command(n)
            def _c():
                click.echo(n)
        make(n)

    r = _run(cli, ["bui", "te"])
    assert r.exit_code == 0, r.output
    assert r.output == "build\\ntest\\n"
    r = _run(cli, ["b"])
    assert r.exit_code == 2
    assert "Error: Ambiguous command 'b'. Could be: build, bundle." in r.output


def test_normalized_names_and_token():
    """[R2][R3][R5] names are normalized for comparison; registered name is invoked."""
    @click.group(allow_abbreviations=True,
                 context_settings={{"token_normalize_func": lambda s: s.replace("_", "-").lower()}})
    def cli():
        pass

    @cli.command("list_users")
    def lu():
        click.echo("users")

    @cli.command("list_groups")
    def lg():
        click.echo("groups")

    assert _run(cli, ["LIST-U"]).output == "users\\n"
    r = _run(cli, ["LIST"])
    assert r.exit_code == 2
    assert "Error: Ambiguous command 'list'. Could be: " in r.output


def test_command_collection_uses_list_commands():
    """[R3] candidates come from list_commands/get_command."""
    a = click.Group("a")
    b = click.Group("b")

    @a.command()
    def deploy():
        click.echo("deploy")

    @b.command()
    def destroy():
        click.echo("destroy")

    cli = click.CommandCollection(sources=[a, b], allow_abbreviations=True)
    assert _run(cli, ["dep"]).output == "deploy\\n"
    assert _run(cli, ["des"]).output == "destroy\\n"


def test_resilient_parsing_does_not_raise():
    """[R5] resilient parsing treats an ambiguous token as unknown."""
    cli = _group(allow_abbreviations=True)
    ctx = cli.make_context("cli", ["st"], resilient_parsing=True)
    name, cmd, rest = cli.resolve_command(ctx, ["st"])
    assert cmd is None and name is None and rest == []
    ctx = cli.make_context("cli", ["sto"], resilient_parsing=True)
    assert cli.resolve_command(ctx, ["sto"])[0] == "stop"
'''
    other_sort = ("sorted((n for n, _ in matches), key=lambda n: (len(n), n))" if mode == "alphabetical"
                  else "sorted(n for n, _ in matches)")
    mutants = [
        Mutant("uses_commands_mapping", "iterates self.commands instead of list_commands()",
               (Edit("src/click/core.py", "        for name in self.list_commands(ctx):\n            key = normalize",
                     "        for name in sorted(self.commands):\n            key = normalize", "replace"),)),
        Mutant("hidden_rule_flipped", "applies the opposite hidden-command rule",
               ((Edit("src/click/core.py", "            matches.append((name, cmd))\n",
                      "            if cmd.hidden:\n                continue\n            matches.append((name, cmd))\n",
                      "replace"),) if hid_in else
                (Edit("src/click/core.py", "            if cmd.hidden:\n                continue\n            matches",
                      "            matches", "replace"),))),
        Mutant("candidate_order_flipped", "orders ambiguity candidates by the other rule",
               (Edit("src/click/core.py", "            names = " + sort_expr, "            names = " + other_sort,
                     "replace"),)),
        Mutant("returns_typed_prefix", "returns the typed prefix as the command name",
               (Edit("src/click/core.py", "        if len(matches) == 1:\n            return matches[0]\n",
                     "        if len(matches) == 1:\n            return token, matches[0][1]\n", "replace"),)),
        Mutant("names_not_normalized", "compares raw names against the normalized token",
               (Edit("src/click/core.py", "            key = normalize(name) if normalize is not None else name\n",
                     "            key = name\n", "replace"),)),
        Mutant("empty_token_matches", "lets an empty token match",
               (Edit("src/click/core.py", "        if cmd is None and self.allow_abbreviations and cmd_name:\n",
                     "        if cmd is None and self.allow_abbreviations:\n", "replace"),)),
        Mutant("raises_when_resilient", "raises the ambiguity error during resilient parsing",
               (Edit("src/click/core.py", "        if len(matches) > 1 and not ctx.resilient_parsing:\n",
                     "        if len(matches) > 1:\n", "replace"),)),
        Mutant("first_match_wins", "picks the first candidate instead of reporting ambiguity",
               (Edit("src/click/core.py", "        if len(matches) == 1:\n            return matches[0]\n",
                     "        if len(matches) >= 1:\n            return matches[0]\n", "replace"),)),
    ]
    return Draft(
        family=FAMILY, slug="group-command-abbreviations", title="Unique-prefix command abbreviations",
        knobs=dict(knobs), instruction=instruction, gold_edits=gold,
        test_files={"tests/test_command_abbreviations.py": tests},
        focus_symbols=["src/click/core.py::Group.resolve_command", "src/click/core.py::Group.invoke",
                       "src/click/core.py::CommandCollection.list_commands", "src/click/core.py::Group.__init__"],
        mutants=mutants,
        novelty_probes=[r"allow_abbreviations|_resolve_abbreviation|Ambiguous command"],
        novelty_queries=["abbreviation", "command prefix", "ambiguous command"],
        axes=AXES,
    )
