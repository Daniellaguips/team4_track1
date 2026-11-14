"""Blueprint: option-level mutual exclusion, ``click.Option(conflicts_with=...)``.

Cross-parameter validation that depends on *where* each value came from (ParameterSource).
Knobs:
  sources  "commandline" | "explicit"   which sources make a parameter "provided"
  report   "first" | "all"              first conflicting pair vs. every pair in one error
"""
from __future__ import annotations

from ..model import Draft, Edit, Mutant

FAMILY = "conflicts"
KNOBS = {"sources": ["commandline", "explicit"], "report": ["first", "all"]}
AXES = {
    "capability": "cross-parameter constraint validation",
    "module": "click.core.Option.__init__ + Command.parse_args",
    "behavior_shape": "post-processing check over parameter-source state, pair detection/dedup",
    "integration": "ParameterSource (command line/env/default/default_map), get_error_hint, "
                   "resilient parsing, callback ordering",
}


def build(knobs: dict) -> Draft:
    explicit = knobs["sources"] == "explicit"
    report_all = knobs["report"] == "all"
    src_rule = (
        "`ParameterSource.COMMANDLINE` **or** `ParameterSource.ENVIRONMENT`" if explicit
        else "`ParameterSource.COMMANDLINE` (a value taken from an environment variable does **not** count)"
    )
    msg_rule = (
        "Collect **every** conflicting pair (R4 order) and raise one `click.UsageError` with the message "
        "`Conflicting options: <pairs>.` where each pair is written `<A> and <B>` and pairs are joined "
        "with `\"; \"`. Example output line: `Error: Conflicting options: '--a' and '--b'; '--a' and '--c'.`"
        if report_all else
        "Raise `click.UsageError` for the **first** conflicting pair only (R4 order) with the message "
        "`Option <A> cannot be used together with <B>.` Example output line: "
        "`Error: Option '--json' cannot be used together with '--yaml'.`"
    )
    instruction = f"""# Mutually exclusive options: `conflicts_with`

Add a way to declare that two parameters of a command must not be given together, e.g. an
output switch `--json` that conflicts with `--yaml`.

## Public interface

- New keyword argument `conflicts_with` on `click.Option.__init__` (and therefore on
  `@click.option(...)`): a sequence of parameter **names** (the Python identifier, i.e.
  `Parameter.name`, such as `"yaml"` for `--yaml`) of other parameters of the same command.
  Default `None`.
- It is stored as the attribute `Option.conflicts_with`, always a `tuple` of strings: `None`
  becomes `()`, a list becomes a tuple, and a single plain string such as `"yaml"` is treated as
  one name, `("yaml",)`.
- `Option.to_info_dict()` output does **not** change (no new key).

## Requirements

**R1 — Provided.** A parameter counts as *provided* when `ctx.get_parameter_source(name)` is
{src_rule}. Values coming from defaults, `default_map` or an interactive prompt never count.
A flag given explicitly on the command line counts even when its value is false (`--no-json`).

**R2 — When.** The check runs while the command parses its arguments, after **all** of the
command's parameters have been processed (so the order of options on the command line does not
matter) and before the command callback is invoked. It is skipped when `ctx.resilient_parsing`
is true.

**R3 — Symmetry.** Declaring the conflict on one side is enough: `--json` with
`conflicts_with=["yaml"]` also forbids `--yaml --json`. Names that do not match any parameter
of the command, and a parameter naming itself, are ignored.

**R4 — Pair order.** Walk the command's parameters in `Command.get_params(ctx)` order; for each
option walk its `conflicts_with` names in the given order. A pair `(declaring option, named
parameter)` conflicts when both are provided. The same two parameters are reported at most
once, in the order they were first found (if `--a` names `b` and `--b` names `a`, only
`<A> and <B>` is reported).

**R5 — Error.** {msg_rule} `<A>`/`<B>` are each parameter's `get_error_hint(ctx)`
(for an option without `show_envvar`: every declared option string in single quotes joined by
`" / "`, e.g. `'-j' / '--json'`). The error is raised with the command's context, so the
normal usage error output is printed (starting with `Usage: cli [OPTIONS]` for a command named `cli`) and the exit code is 2.
"""
    sources_expr = ("{ParameterSource.COMMANDLINE, ParameterSource.ENVIRONMENT}" if explicit
                    else "{ParameterSource.COMMANDLINE}")
    if report_all:
        raise_block = '''        raise UsageError(
            _("Conflicting options: {pairs}.").format(
                pairs="; ".join(
                    f"{a.get_error_hint(ctx)} and {b.get_error_hint(ctx)}" for a, b in pairs
                )
            ),
            ctx,
        )
'''
    else:
        raise_block = '''        a, b = pairs[0]
        raise UsageError(
            _("Option {a} cannot be used together with {b}.").format(
                a=a.get_error_hint(ctx), b=b.get_error_hint(ctx)
            ),
            ctx,
        )
'''
    method = f'''    def _check_conflicts(self, ctx: Context) -> None:
        """Fail if two parameters declared as conflicting were both provided."""
        explicit = {sources_expr}
        params = self.get_params(ctx)
        by_name: dict[str, Parameter] = {{}}
        for p in params:
            if p.name is not None:
                by_name.setdefault(p.name, p)

        def provided(p: Parameter) -> bool:
            return p.name is not None and ctx.get_parameter_source(p.name) in explicit

        pairs: list[tuple[Parameter, Parameter]] = []
        seen: set[frozenset[str]] = set()
        for p in params:
            for other_name in getattr(p, "conflicts_with", ()):
                other = by_name.get(other_name)
                if other is None or other is p:
                    continue
                key = frozenset((t.cast(str, p.name), t.cast(str, other.name)))
                if key in seen:
                    continue
                if provided(p) and provided(other):
                    seen.add(key)
                    pairs.append((p, other))
        if not pairs:
            return
{raise_block}
'''
    gold = [
        Edit("src/click/core.py",
             "        show_envvar: bool = False,\n        deprecated: bool | str = False,\n        **attrs: t.Any,\n",
             "        show_envvar: bool = False,\n        deprecated: bool | str = False,\n"
             "        conflicts_with: cabc.Sequence[str] | None = None,\n        **attrs: t.Any,\n", "replace"),
        Edit("src/click/core.py", "        self.show_envvar = show_envvar\n",
             "        if isinstance(conflicts_with, str):\n"
             "            conflicts_with = (conflicts_with,)\n"
             "        self.conflicts_with: tuple[str, ...] = tuple(conflicts_with or ())\n"),
        Edit("src/click/core.py", "                ctx.params[name] = None\n\n        if args and not ctx.allow_extra_args",
             "                ctx.params[name] = None\n\n        if not ctx.resilient_parsing:\n"
             "            self._check_conflicts(ctx)\n\n        if args and not ctx.allow_extra_args", "replace"),
        Edit("src/click/core.py",
             '    def invoke(self, ctx: Context) -> t.Any:\n        """Given a context, this invokes the attached callback',
             method, "before"),
    ]

    def err(a, b):
        return (f"Option {a} cannot be used together with {b}." if not report_all
                else f"Conflicting options: {a} and {b}.")

    env_assert = (
        f'''    assert r.exit_code == 2
    assert "{err("'--json'", "'--yaml'")}" in r.output'''
        if explicit else
        '''    assert r.exit_code == 0, r.output
    assert r.output == "ok\\n"'''
    )
    multi = ("Option '--a' cannot be used together with '--b'." if not report_all else
             "Conflicting options: '--a' and '--b'; '--a' and '--c'; '--b' and '--c'.")
    tests = f'''import click
from click.core import ParameterSource
from click.testing import CliRunner


def _cli(calls=None, **kw):
    @click.command()
    @click.option("--json", "json_", is_flag=True, conflicts_with=["yaml"], **kw)
    @click.option("--yaml", is_flag=True, envvar="APP_YAML")
    def cli(json_, yaml):
        if calls is not None:
            calls.append(1)
        click.echo("ok")

    return cli


def _run(cli, args, **kw):
    return CliRunner().invoke(cli, args, **kw)


def test_attribute_normalization():
    """[R3 interface] conflicts_with stored as a tuple."""
    assert click.Option(["--a"]).conflicts_with == ()
    assert click.Option(["--a"], conflicts_with=["b", "c"]).conflicts_with == ("b", "c")
    assert click.Option(["--a"], conflicts_with="yaml").conflicts_with == ("yaml",)


def test_info_dict_unchanged():
    """[R5 interface] to_info_dict has no new key."""
    assert "conflicts_with" not in click.Option(["--a"], conflicts_with=["b"]).to_info_dict()


def test_one_side_alone_is_fine():
    """[R1]"""
    cli = _cli()
    assert _run(cli, ["--json"]).output == "ok\\n"
    assert _run(cli, ["--yaml"]).output == "ok\\n"
    assert _run(cli, []).output == "ok\\n"


def test_both_on_command_line_fails():
    """[R1][R5]"""
    calls = []
    r = _run(_cli(calls), ["--json", "--yaml"])
    assert r.exit_code == 2
    assert "Error: {err("'--json'", "'--yaml'")}" in r.output
    assert "Usage: cli [OPTIONS]" in r.output
    assert calls == []


def test_order_on_command_line_irrelevant_and_symmetric():
    """[R2][R3][R4]"""
    r = _run(_cli(), ["--yaml", "--json"])
    assert r.exit_code == 2
    assert "{err("'--json'", "'--yaml'")}" in r.output


def test_defaults_and_default_map_do_not_count():
    """[R1]"""
    @click.command(context_settings={{"default_map": {{"yaml": True}}}})
    @click.option("--json", "json_", is_flag=True, default=True, conflicts_with=["yaml"])
    @click.option("--yaml", is_flag=True)
    @click.pass_context
    def cli(ctx, json_, yaml):
        seen.append((json_, yaml, ctx.get_parameter_source("yaml")))

    seen = []
    r = _run(cli, ["--json"])
    assert r.exit_code == 0, r.output
    assert seen == [(True, True, ParameterSource.DEFAULT_MAP)]
    assert _run(cli, ["--yaml"]).exit_code == 0


def test_environment_source():
    """[R1]"""
    r = _run(_cli(), ["--json"], env={{"APP_YAML": "1"}})
{env_assert}


def test_explicit_false_flag_counts():
    """[R1]"""
    @click.command()
    @click.option("--color/--no-color", default=None, conflicts_with=["plain"])
    @click.option("--plain", is_flag=True)
    def cli(color, plain):
        click.echo("ok")

    r = _run(cli, ["--no-color", "--plain"])
    assert r.exit_code == 2
    assert "{err("'--color'", "'--plain'")}" in r.output


def test_error_hint_lists_all_option_strings():
    """[R5]"""
    @click.command()
    @click.option("-j", "--json", "json_", is_flag=True, conflicts_with=("yaml",))
    @click.option("-y", "--yaml", is_flag=True)
    def cli(json_, yaml):
        pass

    r = _run(cli, ["-y", "-j"])
    assert r.exit_code == 2
    assert "{err("'-j' / '--json'", "'-y' / '--yaml'")}" in r.output


def test_multiple_pairs_order_and_dedup():
    """[R4][R5]"""
    @click.command()
    @click.option("--a", is_flag=True, conflicts_with=["b", "c"])
    @click.option("--b", is_flag=True, conflicts_with=["a", "c"])
    @click.option("--c", is_flag=True)
    def cli(a, b, c):
        pass

    r = _run(cli, ["--c", "--b", "--a"])
    assert r.exit_code == 2
    assert "Error: {multi}" in r.output


def test_unknown_and_self_names_ignored():
    """[R3]"""
    @click.command()
    @click.option("--a", is_flag=True, conflicts_with=["nope", "a"])
    def cli(a):
        click.echo("ok")

    assert _run(cli, ["--a"]).output == "ok\\n"


def test_skipped_during_resilient_parsing():
    """[R2]"""
    cli = _cli()
    ctx = cli.make_context("cli", ["--json", "--yaml"], resilient_parsing=True)
    assert ctx.get_parameter_source("yaml") is ParameterSource.COMMANDLINE
'''
    other_src = ("{ParameterSource.COMMANDLINE}" if explicit
                 else "{ParameterSource.COMMANDLINE, ParameterSource.ENVIRONMENT}")
    mutants = [
        Mutant("source_rule_flipped", "uses the other set of counting sources",
               (Edit("src/click/core.py", f"        explicit = {sources_expr}\n", f"        explicit = {other_src}\n",
                     "replace"),)),
        Mutant("defaults_count", "treats any non-None source (incl. defaults) as provided",
               (Edit("src/click/core.py", "ctx.get_parameter_source(p.name) in explicit",
                     "ctx.get_parameter_source(p.name) is not None", "replace"),)),
        Mutant("string_split_into_chars", "turns a plain string into a tuple of characters",
               (Edit("src/click/core.py", "        if isinstance(conflicts_with, str):\n"
                     "            conflicts_with = (conflicts_with,)\n", "", "replace"),)),
        (Mutant("no_dedup", "reports both directions of the same pair",
                (Edit("src/click/core.py", "                if key in seen:\n                    continue\n", "",
                      "replace"),)) if report_all else
         Mutant("reports_last_pair", "reports the last conflicting pair instead of the first",
                (Edit("src/click/core.py", "        a, b = pairs[0]\n", "        a, b = pairs[-1]\n", "replace"),))),
        Mutant("pair_order_swapped", "reports the named parameter before the declaring one",
               (Edit("src/click/core.py", "                    pairs.append((p, other))\n",
                     "                    pairs.append((other, p))\n", "replace"),)),
        Mutant("checked_during_resilient", "runs the check during resilient parsing",
               (Edit("src/click/core.py", "        if not ctx.resilient_parsing:\n            self._check_conflicts(ctx)\n",
                     "        self._check_conflicts(ctx)\n", "replace"),)),
        Mutant("self_reference_not_ignored", "does not ignore a parameter naming itself",
               (Edit("src/click/core.py", "                if other is None or other is p:\n",
                     "                if other is None:\n", "replace"),)),
    ]
    return Draft(
        family=FAMILY, slug="option-conflicts-with", title="Mutually exclusive options",
        knobs=dict(knobs), instruction=instruction, gold_edits=gold,
        test_files={"tests/test_option_conflicts.py": tests},
        focus_symbols=["src/click/core.py::Command.parse_args", "src/click/core.py::Option.__init__",
                       "src/click/core.py::Parameter.handle_parse_result",
                       "src/click/core.py::Option.get_error_hint"],
        mutants=mutants,
        novelty_probes=[r"conflicts_with|mutually_exclusive|cannot be used together"],
        novelty_queries=["mutually exclusive", "conflicts_with", "exclusive options"],
        axes=AXES,
    )
