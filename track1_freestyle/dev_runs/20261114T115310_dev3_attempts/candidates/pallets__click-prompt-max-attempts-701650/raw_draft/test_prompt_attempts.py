import pytest

import click
from click.testing import CliRunner


def _int_cli(**kw):
    @click.command()
    @click.option("--value", type=int, prompt=True, **kw)
    def cli(value):
        click.echo(f"got {value}")

    return cli


def _run(cli, text):
    return CliRunner().invoke(cli, [], input=text)


def test_validation():
    """[R1]"""
    for bad in (0, -1, True, False, "3", 1.5):
        with pytest.raises(ValueError):
            click.prompt("x", max_attempts=bad)
        with pytest.raises(ValueError):
            click.confirm("x", max_attempts=bad)
        with pytest.raises(ValueError):
            click.Option(["--v"], prompt=True, prompt_max_attempts=bad)


def test_option_attribute():
    """[R1] attribute default None."""
    assert click.Option(["--v"], prompt=True).prompt_max_attempts is None
    assert click.Option(["--v"], prompt=True, prompt_max_attempts=2).prompt_max_attempts == 2


def test_success_within_budget():
    """[R2][R4]"""
    r = _run(_int_cli(prompt_max_attempts=3), "a\nb\n7\n")
    assert r.exit_code == 0, r.output
    assert r.output.endswith("got 7\n")
    assert r.output.count("Error: 'a' is not a valid integer.") == 1
    assert r.output.count("Error: 'b' is not a valid integer.") == 1


def test_gives_up_after_budget():
    """[R2][R4]"""
    r = _run(_int_cli(prompt_max_attempts=3), "a\nb\nc\n9\n")
    assert r.exit_code == 1, r.output
    assert r.output.rstrip().endswith("Aborted!")
    assert r.output.count("Value: ") == 3
    assert "Error: 'c' is not a valid integer." in r.output
    assert "got 9" not in r.output


def test_single_attempt():
    """[R4]"""
    r = _run(_int_cli(prompt_max_attempts=1), "x\n2\n")
    assert r.exit_code == 1, r.output
    assert r.output.rstrip().endswith("Aborted!")
    assert r.output.count("Value: ") == 1


def test_unlimited_by_default():
    """[R5]"""
    r = _run(_int_cli(), "a\n" * 8 + "4\n")
    assert r.exit_code == 0
    assert r.output.endswith("got 4\n")


def test_confirmation_mismatch_counts():
    """[R2]"""
    @click.command()
    @click.option("--pin", prompt=True, confirmation_prompt=True, prompt_max_attempts=2)
    def cli(pin):
        click.echo(f"pin {pin}")

    r = _run(cli, "1\n2\n3\n4\n5\n5\n")
    assert r.exit_code == 1, r.output
    assert r.output.rstrip().endswith("Aborted!")
    assert r.output.count("Error: The two entered values do not match.") == 2


def test_empty_answer_without_default():
    """[R2]"""
    r = _run(_int_cli(prompt_max_attempts=2), "\n\n\n5\n")
    assert r.exit_code == 1, r.output
    assert r.output.rstrip().endswith("Aborted!")
    assert r.output.count("Value: ") == 2


def test_empty_answer_with_default_is_not_a_failure():
    """[R2]"""
    r = _run(_int_cli(default=3, prompt_max_attempts=1), "\n")
    assert r.exit_code == 0, r.output
    assert r.output.endswith("got 3\n")


def test_confirm_function():
    """[R3][R4]"""
    @click.command()
    @click.argument("n", type=int)
    def cli(n):
        click.echo(f"answer {click.confirm('Sure', max_attempts=n)}")

    r = CliRunner().invoke(cli, ["2"], input="maybe\nnah\ny\n")
    assert r.exit_code == 1, r.output
    assert r.output.rstrip().endswith("Aborted!")
    assert r.output.count("Error: invalid input") == 2
    r = CliRunner().invoke(cli, ["3"], input="maybe\nnah\ny\n")
    assert r.exit_code == 0
    assert r.output.endswith("answer True\n")


def test_prompt_function_in_command():
    """[R2][R4]"""
    @click.command()
    def cli():
        click.echo(f"n={click.prompt('Number', type=int, max_attempts=2)}")

    r = CliRunner().invoke(cli, [], input="x\n6\n")
    assert r.exit_code == 0
    assert r.output.endswith("n=6\n")
    r = CliRunner().invoke(cli, [], input="x\ny\n6\n")
    assert r.exit_code == 1, r.output
    assert r.output.rstrip().endswith("Aborted!")


def test_boolean_flag_prompt_uses_budget():
    """[R3][R4] boolean flags prompt through confirm."""
    @click.command()
    @click.option("--force/--no-force", prompt=True, prompt_max_attempts=1)
    def cli(force):
        click.echo(f"force={force}")

    r = _run(cli, "what\ny\n")
    assert r.exit_code == 1, r.output
    assert r.output.rstrip().endswith("Aborted!")
    assert r.output.count("Error: invalid input") == 1
    r = _run(cli, "y\n")
    assert r.output.endswith("force=True\n")
