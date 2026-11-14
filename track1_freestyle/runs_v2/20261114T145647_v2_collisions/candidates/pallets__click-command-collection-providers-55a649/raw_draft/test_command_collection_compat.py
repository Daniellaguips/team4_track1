"""Existing CommandCollection behaviour that must not change (pass before and after the feature)."""
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
    assert runner.invoke(cli, ["deploy"]).output == "from a\n"
    assert runner.invoke(cli, ["status"]).output == "status from b\n"
    cli.add_command(_echo("deploy", "own"))
    assert runner.invoke(cli, ["deploy"]).output == "own\n"


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
    assert result.exit_code == 0 and result.output == "from a\n"
