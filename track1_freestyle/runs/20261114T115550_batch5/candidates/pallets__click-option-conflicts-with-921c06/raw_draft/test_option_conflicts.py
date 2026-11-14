import click
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
    assert _run(cli, ["--json"]).output == "ok\n"
    assert _run(cli, ["--yaml"]).output == "ok\n"
    assert _run(cli, []).output == "ok\n"


def test_both_on_command_line_fails():
    """[R1][R5]"""
    calls = []
    r = _run(_cli(calls), ["--json", "--yaml"])
    assert r.exit_code == 2
    assert "Error: Conflicting options: '--json' and '--yaml'." in r.output
    assert "Usage: cli [OPTIONS]" in r.output
    assert calls == []


def test_order_on_command_line_irrelevant_and_symmetric():
    """[R2][R3][R4]"""
    r = _run(_cli(), ["--yaml", "--json"])
    assert r.exit_code == 2
    assert "Conflicting options: '--json' and '--yaml'." in r.output


def test_defaults_and_default_map_do_not_count():
    """[R1]"""
    @click.command(context_settings={"default_map": {"yaml": True}})
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
    r = _run(_cli(), ["--json"], env={"APP_YAML": "1"})
    assert r.exit_code == 2
    assert "Conflicting options: '--json' and '--yaml'." in r.output


def test_explicit_false_flag_counts():
    """[R1]"""
    @click.command()
    @click.option("--color/--no-color", default=None, conflicts_with=["plain"])
    @click.option("--plain", is_flag=True)
    def cli(color, plain):
        click.echo("ok")

    r = _run(cli, ["--no-color", "--plain"])
    assert r.exit_code == 2
    assert "Conflicting options: '--color' and '--plain'." in r.output


def test_error_hint_lists_all_option_strings():
    """[R5]"""
    @click.command()
    @click.option("-j", "--json", "json_", is_flag=True, conflicts_with=("yaml",))
    @click.option("-y", "--yaml", is_flag=True)
    def cli(json_, yaml):
        pass

    r = _run(cli, ["-y", "-j"])
    assert r.exit_code == 2
    assert "Conflicting options: '-j' / '--json' and '-y' / '--yaml'." in r.output


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
    assert "Error: Conflicting options: '--a' and '--b'; '--a' and '--c'; '--b' and '--c'." in r.output


def test_unknown_and_self_names_ignored():
    """[R3]"""
    @click.command()
    @click.option("--a", is_flag=True, conflicts_with=["nope", "a"])
    def cli(a):
        click.echo("ok")

    assert _run(cli, ["--a"]).output == "ok\n"


def test_skipped_during_resilient_parsing():
    """[R2]"""
    cli = _cli()
    ctx = cli.make_context("cli", ["--json", "--yaml"], resilient_parsing=True)
    assert ctx.get_parameter_source("yaml") is ParameterSource.COMMANDLINE
