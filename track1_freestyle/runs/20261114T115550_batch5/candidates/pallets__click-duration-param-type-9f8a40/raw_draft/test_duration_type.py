from datetime import timedelta

import pytest

import click
from click.testing import CliRunner


def _cli(**kw):
    @click.command()
    @click.option("--timeout", type=click.Duration(**kw))
    def cli(timeout):
        click.echo("none" if timeout is None else int(timeout.total_seconds()))

    return cli


def _run(args, **kw):
    return CliRunner().invoke(_cli(**kw), args)


def _bad(args, text, **kw):
    r = _run(args, **kw)
    assert r.exit_code == 2, r.output
    assert f"Error: Invalid value for '--timeout': {text!r} is not a valid duration." in r.output
    return r


def test_exported_and_basic_conversion():
    """[R1][R4] exported under click and click.types; converts to timedelta."""
    assert click.Duration is click.types.Duration
    assert issubclass(click.Duration, click.ParamType)
    assert click.Duration().convert("2m", None, None) == timedelta(minutes=2)
    assert click.Duration().name == "duration"


def test_components_sum_on_command_line():
    """[R1][R4]"""
    assert _run(["--timeout", "1h30m"]).output == "5400\n"
    assert _run(["--timeout", "1w1d1h1m1s"]).output == "694861\n"
    assert _run(["--timeout", "0s"]).output == "0\n"
    assert _run(["--timeout", "007m"]).output == "420\n"


def test_surrounding_whitespace_is_stripped():
    """[R1]"""
    assert _run(["--timeout", "  2m  "]).output == "120\n"


def test_invalid_grammar():
    """[R1][R7][R8]"""
    for text in ["", "1h 30m", "-5m", "1.5h", "1H", "1x", "h", "1h30", "w"]:
        _bad(["--timeout", text], text)


def test_invalid_message_uses_unstripped_text():
    """[R7]"""
    _bad(["--timeout", " 1q "], " 1q ")


def test_repeated_unit_is_invalid():
    """[R2]"""
    _bad(["--timeout", "1h1h"], "1h1h")
    _bad(["--timeout", "1h30m2h"], "1h30m2h")


def test_component_order():
    """[R2]"""
    assert _run(['--timeout', '30m1h']).output == '5400\n'
    assert _run(["--timeout", "1d1s"]).output == "86401\n"


def test_digits_only():
    """[R3]"""
    assert _run(['--timeout', '90']).output == '90\n'


def test_int_default_follows_digits_rule():
    """[R3][R5]"""
    @click.command()
    @click.option("--timeout", type=click.Duration(), default=90)
    def cli(timeout):
        click.echo(int(timeout.total_seconds()))

    r = CliRunner().invoke(cli, [])
    assert r.output == '90\n'


def test_timedelta_passthrough():
    """[R5]"""
    td = timedelta(minutes=5, microseconds=0)
    assert click.Duration().convert(td, None, None) is td


def test_bounds_inclusive():
    """[R6]"""
    kw = dict(min=timedelta(minutes=1), max=timedelta(hours=1))
    assert _run(["--timeout", "1m"], **kw).output == "60\n"
    assert _run(["--timeout", "1h"], **kw).output == "3600\n"


def test_below_minimum_message():
    """[R6][R8]"""
    r = _run(["--timeout", "30s"], min=timedelta(minutes=1))
    assert r.exit_code == 2
    assert "Error: Invalid value for '--timeout': 30 seconds is below the minimum of 60 seconds." in r.output


def test_above_maximum_message():
    """[R6][R8]"""
    r = _run(["--timeout", "1h1s"], max=timedelta(hours=1))
    assert r.exit_code == 2
    assert "Error: Invalid value for '--timeout': 3601 seconds is above the maximum of 3600 seconds." in r.output


def test_bounds_apply_to_timedelta_values():
    """[R5][R6]"""
    with pytest.raises(click.BadParameter) as ei:
        click.Duration(max=timedelta(hours=1)).convert(timedelta(hours=2), None, None)
    assert "7200 seconds is above the maximum of 3600 seconds." in str(ei.value)


def test_help_metavar():
    """[R8 interface: metavar]"""
    r = _run(["--help"])
    assert "--timeout DURATION" in r.output


def test_info_dict():
    """[R9]"""
    assert click.Duration(max=timedelta(hours=1)).to_info_dict() == {
        "param_type": "Duration", "name": "duration", "min": None, "max": 3600,
    }
    assert click.Duration(min=timedelta(seconds=5)).to_info_dict()["min"] == 5
