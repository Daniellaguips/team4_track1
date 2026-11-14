"""Blueprint: bounded retries for interactive prompts (termui.prompt / confirm + Option prompts).

Knobs:
  empty      "counts" | "free"            an empty answer without default is a failed attempt?
  exhausted  "abort" | "usage_error"      what happens when the attempts run out
"""
from __future__ import annotations

from ..model import Draft, Edit, Mutant

FAMILY = "attempts"
KNOBS = {"empty": ["counts", "free"], "exhausted": ["abort", "usage_error"]}
AXES = {
    "capability": "interactive input state machine (retry budget)",
    "module": "click.termui.prompt/confirm + click.core.Option.prompt_for_value",
    "behavior_shape": "loop with failure counter across conversion / confirmation / empty paths",
    "integration": "Option prompt plumbing (typed values, boolean flags, confirmation_prompt), "
                   "Abort/UsageError exit codes",
}


def build(knobs: dict) -> Draft:
    empty_counts = knobs["empty"] == "counts"
    abort = knobs["exhausted"] == "abort"
    empty_rule = (
        "an empty answer when the prompt has no default (today it is silently asked again; it "
        "still is, but it now counts as a failed attempt; no message is printed for it)"
        if empty_counts else
        "— **not** an empty answer: an empty answer when there is no default is silently asked "
        "again exactly as today and does not count"
    )
    give_up = (
        "raise `click.Abort()` (inside a command this prints `Aborted!` and exits with code 1)"
        if abort else
        "raise `click.UsageError` with the message `Gave up after <n> invalid attempts.` where "
        "`<n>` is `max_attempts` (inside a command this prints e.g. "
        "`Error: Gave up after 3 invalid attempts.` and exits with code 2)"
    )
    instruction = f"""# Bounded retries for prompts

`click.prompt`, `click.confirm` and options with `prompt=...` ask again forever when the answer
is invalid, which hangs scripted or piped sessions. Add an optional retry budget.

## Public interface

- `click.prompt(..., max_attempts: int | None = None)` — new keyword argument (also add it to
  the two `typing.overload` signatures of `prompt`).
- `click.confirm(..., max_attempts: int | None = None)` — new keyword argument.
- `click.Option(..., prompt_max_attempts: int | None = None)` (thus also
  `@click.option(..., prompt_max_attempts=...)`), stored as the attribute
  `Option.prompt_max_attempts`. When the option prompts, it passes this value as `max_attempts`
  to `prompt` — or to `confirm` for boolean-flag options, which prompt with a yes/no question.

## Requirements

**R1 — Validation.** `None` means unlimited (today's behaviour). Otherwise the value must be an
`int` greater than or equal to 1; `bool` values are rejected. Anything else raises `ValueError`:
for `prompt`/`confirm` immediately when called, before anything is printed or read; for
`Option` in its constructor.

**R2 — Failed attempts of `prompt`.** A *failed attempt* is: a value whose conversion fails
(the `Error: ...` line is printed exactly as today, e.g. `Error: 'a' is not a valid integer.` for
the answer `a` to an integer prompt); a confirmation that does not match when
`confirmation_prompt` is used (`Error: The two entered values do not match.` printed as today);
{empty_rule}. An empty answer when a default exists is not a failure (the default is used).

**R3 — Failed attempts of `confirm`.** Every answer that prints `Error: invalid input` today is a
failed attempt.

**R4 — Giving up.** When the number of failed attempts reaches `max_attempts`, stop asking and
{give_up}. The message for the last failed attempt is printed before giving up, and no further
input is read. A valid answer given before the budget is used up is returned normally, so with
`max_attempts=3` two bad answers followed by a good one succeed.

**R5 — Unchanged behaviour.** Aborting with Ctrl-C/EOF still raises `click.Abort`; with
`max_attempts=None` (the default) everything behaves exactly as before.
"""
    count_empty = "            failed()\n" if empty_counts else ""
    if abort:
        give_up_body = "    raise Abort()\n"
    else:
        give_up_body = ('    raise UsageError(_("Gave up after {n} invalid attempts.").format(n=limit))\n')
    helpers = f'''def _check_max_attempts(value: int | None, name: str = "max_attempts") -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{{name}} must be a positive integer or None.")


def _give_up(limit: int) -> t.NoReturn:
{give_up_body}

def _attempt_counter(max_attempts: int | None) -> t.Callable[[], None]:
    failures = 0

    def failed() -> None:
        nonlocal failures
        failures += 1
        if max_attempts is not None and failures >= max_attempts:
            _give_up(max_attempts)

    return failed


'''
    T = "src/click/termui.py"
    C = "src/click/core.py"
    gold = [
        Edit(T, "    show_choices: bool = True,\n) -> str: ...",
             "    show_choices: bool = True,\n    max_attempts: int | None = None,\n) -> str: ...", "replace"),
        Edit(T, "    show_choices: bool = True,\n) -> V: ...",
             "    show_choices: bool = True,\n    max_attempts: int | None = None,\n) -> V: ...", "replace"),
        Edit(T, '    show_choices: bool = True,\n) -> V:\n    """Prompts',
             '    show_choices: bool = True,\n    max_attempts: int | None = None,\n) -> V:\n    """Prompts', "replace"),
        Edit(T, "    def prompt_func(text: str) -> str:\n",
             "    _check_max_attempts(max_attempts)\n    failed = _attempt_counter(max_attempts)\n\n", "before"),
        Edit(T, '                value = t.cast("str", default)\n                break\n', count_empty),
        Edit(T, '            echo(_("Error: {message}").format(message=message), err=err)\n            continue\n',
             '            echo(_("Error: {message}").format(message=message), err=err)\n'
             '            failed()\n            continue\n', "replace"),
        Edit(T, '        echo(_("Error: The two entered values do not match."), err=err)\n',
             "        failed()\n"),
        Edit(T, "    show_default: bool = True,\n    err: bool = False,\n) -> bool:",
             "    show_default: bool = True,\n    err: bool = False,\n    max_attempts: int | None = None,\n) -> bool:",
             "replace"),
        Edit(T, '    prompt = _build_prompt(\n        text,\n        prompt_suffix,\n        show_default,\n        "y/n"',
             "    _check_max_attempts(max_attempts)\n    failed = _attempt_counter(max_attempts)\n", "before"),
        Edit(T, '            echo(_("Error: invalid input"), err=err)\n            continue\n',
             '            echo(_("Error: invalid input"), err=err)\n            failed()\n            continue\n',
             "replace"),
        Edit(T, "\ndef confirm(\n", "\n" + helpers + "def confirm(\n", "replace"),
        Edit(C, "        prompt_required: bool = True,\n        hide_input: bool = False,\n",
             "        prompt_required: bool = True,\n        hide_input: bool = False,\n"
             "        prompt_max_attempts: int | None = None,\n", "replace"),
        Edit(C, "        self.prompt_required = prompt_required\n",
             "        if prompt_max_attempts is not None and (\n"
             "            isinstance(prompt_max_attempts, bool)\n"
             "            or not isinstance(prompt_max_attempts, int)\n"
             "            or prompt_max_attempts < 1\n"
             "        ):\n"
             "            raise ValueError(\n"
             '                "prompt_max_attempts must be a positive integer or None."\n'
             "            )\n"
             "        self.prompt_max_attempts = prompt_max_attempts\n"),
        Edit(C, "            return confirm(self.prompt, default)\n",
             "            return confirm(\n                self.prompt, default, max_attempts=self.prompt_max_attempts\n            )\n",
             "replace"),
        Edit(C, "            value_proc=lambda x: self.process_value(ctx, x),\n            **prompt_kwargs,\n",
             "            value_proc=lambda x: self.process_value(ctx, x),\n"
             "            max_attempts=self.prompt_max_attempts,\n            **prompt_kwargs,\n", "replace"),
    ]

    def gave_up(n):
        if abort:
            return ('    assert r.exit_code == 1, r.output\n'
                    '    assert r.output.rstrip().endswith("Aborted!")')
        return ('    assert r.exit_code == 2, r.output\n'
                f'    assert "Error: Gave up after {n} invalid attempts." in r.output')

    empty_test = (
        f'''    r = _run(_int_cli(prompt_max_attempts=2), "\\n\\n\\n5\\n")
{gave_up(2)}
    assert r.output.count("Value: ") == 2'''
        if empty_counts else
        '''    r = _run(_int_cli(prompt_max_attempts=2), "\\n\\n\\n5\\n")
    assert r.exit_code == 0, r.output
    assert r.output.endswith("got 5\\n")
    assert r.output.count("Value: ") == 4'''
    )
    tests = f'''import pytest

import click
from click.testing import CliRunner


def _int_cli(**kw):
    @click.command()
    @click.option("--value", type=int, prompt=True, **kw)
    def cli(value):
        click.echo(f"got {{value}}")

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
    r = _run(_int_cli(prompt_max_attempts=3), "a\\nb\\n7\\n")
    assert r.exit_code == 0, r.output
    assert r.output.endswith("got 7\\n")
    assert r.output.count("Error: 'a' is not a valid integer.") == 1
    assert r.output.count("Error: 'b' is not a valid integer.") == 1


def test_gives_up_after_budget():
    """[R2][R4]"""
    r = _run(_int_cli(prompt_max_attempts=3), "a\\nb\\nc\\n9\\n")
{gave_up(3)}
    assert r.output.count("Value: ") == 3
    assert "Error: 'c' is not a valid integer." in r.output
    assert "got 9" not in r.output


def test_single_attempt():
    """[R4]"""
    r = _run(_int_cli(prompt_max_attempts=1), "x\\n2\\n")
{gave_up(1)}
    assert r.output.count("Value: ") == 1


def test_unlimited_by_default():
    """[R5]"""
    r = _run(_int_cli(prompt_max_attempts=None), "a\\n" * 8 + "4\\n")
    assert r.exit_code == 0
    assert r.output.endswith("got 4\\n")


def test_confirmation_mismatch_counts():
    """[R2]"""
    @click.command()
    @click.option("--pin", prompt=True, confirmation_prompt=True, prompt_max_attempts=2)
    def cli(pin):
        click.echo(f"pin {{pin}}")

    r = _run(cli, "1\\n2\\n3\\n4\\n5\\n5\\n")
{gave_up(2)}
    assert r.output.count("Error: The two entered values do not match.") == 2


def test_empty_answer_without_default():
    """[R2]"""
{empty_test}


def test_empty_answer_with_default_is_not_a_failure():
    """[R2]"""
    r = _run(_int_cli(default=3, prompt_max_attempts=1), "\\n")
    assert r.exit_code == 0, r.output
    assert r.output.endswith("got 3\\n")


def test_confirm_function():
    """[R3][R4]"""
    @click.command()
    @click.argument("n", type=int)
    def cli(n):
        click.echo(f"answer {{click.confirm('Sure', max_attempts=n)}}")

    r = CliRunner().invoke(cli, ["2"], input="maybe\\nnah\\ny\\n")
{gave_up(2)}
    assert r.output.count("Error: invalid input") == 2
    r = CliRunner().invoke(cli, ["3"], input="maybe\\nnah\\ny\\n")
    assert r.exit_code == 0
    assert r.output.endswith("answer True\\n")


def test_prompt_function_in_command():
    """[R2][R4]"""
    @click.command()
    def cli():
        click.echo(f"n={{click.prompt('Number', type=int, max_attempts=2)}}")

    r = CliRunner().invoke(cli, [], input="x\\n6\\n")
    assert r.exit_code == 0
    assert r.output.endswith("n=6\\n")
    r = CliRunner().invoke(cli, [], input="x\\ny\\n6\\n")
{gave_up(2)}


def test_boolean_flag_prompt_uses_budget():
    """[R3][R4] boolean flags prompt through confirm."""
    @click.command()
    @click.option("--force/--no-force", prompt=True, prompt_max_attempts=1)
    def cli(force):
        click.echo(f"force={{force}}")

    r = _run(cli, "what\\ny\\n")
{gave_up(1)}
    assert r.output.count("Error: invalid input") == 1
    r = _run(cli, "y\\n")
    assert r.output.endswith("force=True\\n")
'''
    mutants = [
        Mutant("off_by_one", "allows one extra attempt",
               (Edit(T, "        if max_attempts is not None and failures >= max_attempts:\n",
                     "        if max_attempts is not None and failures > max_attempts:\n", "replace"),)),
        Mutant("mismatch_not_counted", "does not count confirmation mismatches",
               (Edit(T, '        echo(_("Error: The two entered values do not match."), err=err)\n        failed()\n',
                     '        echo(_("Error: The two entered values do not match."), err=err)\n', "replace"),)),
        Mutant("empty_rule_flipped", "uses the opposite empty-answer rule",
               ((Edit(T, '                value = t.cast("str", default)\n                break\n            failed()\n',
                      '                value = t.cast("str", default)\n                break\n', "replace"),)
                if empty_counts else
                (Edit(T, '                value = t.cast("str", default)\n                break\n',
                      '                value = t.cast("str", default)\n                break\n            failed()\n',
                      "replace"),))),
        Mutant("wrong_exhaustion_exception", "raises the other exception type when giving up",
               (Edit(T, "def _give_up(limit: int) -> t.NoReturn:\n" + give_up_body,
                     "def _give_up(limit: int) -> t.NoReturn:\n" +
                     ('    raise UsageError(_("Gave up after {n} invalid attempts.").format(n=limit))\n'
                      if abort else "    raise Abort()\n"), "replace"),)),
        Mutant("bool_accepted", "accepts True as a budget",
               (Edit(T, "    if isinstance(value, bool) or not isinstance(value, int) or value < 1:\n",
                     "    if not isinstance(value, int) or value < 1:\n", "replace"),)),
        Mutant("flag_prompt_not_forwarded", "boolean-flag prompts ignore the budget",
               (Edit(C, "                self.prompt, default, max_attempts=self.prompt_max_attempts\n",
                     "                self.prompt, default\n", "replace"),)),
        Mutant("message_suppressed_on_last", "gives up before printing the last error",
               (Edit(T, '            echo(_("Error: {message}").format(message=message), err=err)\n'
                     '            failed()\n',
                     '            failed()\n            echo(_("Error: {message}").format(message=message), err=err)\n',
                     "replace"),)),
        Mutant("confirm_not_counted", "confirm() ignores its budget",
               (Edit(T, '            echo(_("Error: invalid input"), err=err)\n            failed()\n',
                     '            echo(_("Error: invalid input"), err=err)\n', "replace"),)),
    ]
    return Draft(
        family=FAMILY, slug="prompt-max-attempts", title="Bounded retries for prompts",
        knobs=dict(knobs), instruction=instruction, gold_edits=gold,
        test_files={"tests/test_prompt_attempts.py": tests},
        focus_symbols=["src/click/termui.py::prompt", "src/click/termui.py::confirm",
                       "src/click/core.py::Option.prompt_for_value", "src/click/core.py::Option.__init__"],
        mutants=mutants,
        novelty_probes=[r"max_attempts|prompt_max_attempts|invalid attempts"],
        novelty_queries=["max_attempts", "prompt retries", "prompt attempts"],
        axes=AXES,
    )
