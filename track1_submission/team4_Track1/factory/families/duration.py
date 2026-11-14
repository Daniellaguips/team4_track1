"""Blueprint: a new value-conversion ParamType, ``click.Duration`` (types.py + package export).

Knobs change the grammar the solver must implement, so different knob vectors produce
behaviourally different specs, golds, tests and mutants:
  units        "dhms" | "wdhms"            which unit letters exist
  order        "descending" | "any"        component ordering rule
  bare_number  "seconds" | "reject"        meaning of a digits-only value
"""
from __future__ import annotations

from ..model import Draft, Edit, Mutant

FAMILY = "duration"
KNOBS = {
    "units": ["dhms", "wdhms"],
    "order": ["descending", "any"],
    "bare_number": ["seconds", "reject"],
}
AXES = {
    "capability": "value conversion / input grammar (new ParamType)",
    "module": "click.types (+ package export)",
    "behavior_shape": "string grammar -> datetime.timedelta, inclusive bounds",
    "integration": "ParamType.fail error path, metavar/help, to_info_dict, defaults",
}

UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
UNIT_NAMES = {"w": "weeks (7 days)", "d": "days", "h": "hours", "m": "minutes", "s": "seconds"}


def build(knobs: dict) -> Draft:
    units = knobs["units"]
    desc = knobs["order"] == "descending"
    bare_secs = knobs["bare_number"] == "seconds"
    unit_map = ", ".join(f'"{u}": {UNIT_SECONDS[u]}' for u in units)

    order_rule = (
        "Components must appear in strictly decreasing unit size (for example `1h30m` is valid, "
        "`30m1h` is invalid). Consequently each unit can appear at most once."
        if desc else
        "Components may appear in any order (`30m1h` is valid and equals `1h30m`), but each unit "
        "may appear at most once (`1h1h` and `1h30m2h` are invalid)."
    )
    bare_rule = (
        "A value consisting only of digits (no unit letter at all), such as `90`, means that many "
        "seconds."
        if bare_secs else
        "A value consisting only of digits (no unit letter at all), such as `90`, is invalid: every "
        "component must carry a unit letter."
    )
    unit_lines = "\n".join(f"   - `{u}` — {UNIT_NAMES[u]} ({UNIT_SECONDS[u]} seconds)" for u in units)
    big = units[0]
    instruction = f"""# Add a `Duration` parameter type to Click

Click ships value types such as `click.IntRange` and `click.DateTime`, but nothing for
human-friendly time spans like `--timeout 1h30m`. Add a new parameter type, `Duration`, that
converts such strings to `datetime.timedelta`.

## Public interface

```python
click.Duration(min: datetime.timedelta | None = None, max: datetime.timedelta | None = None)
```

- Define the class in `click/types.py` as a subclass of `click.ParamType`, and export it from the
  package so that both `click.Duration` and `click.types.Duration` refer to it.
- `Duration().name` is `"duration"`, so the default metavar shown in help is `DURATION`
  (e.g. `--timeout DURATION`).
- `convert(value, param, ctx)` returns a `datetime.timedelta`.

## Requirements

**R1 — Grammar.** After stripping leading and trailing whitespace, a valid value is one or more
*components* written back to back with no separators. A component is one or more ASCII digits
(`0`–`9`, leading zeros allowed) immediately followed by exactly one lowercase unit letter.
The available unit letters are exactly:
{unit_lines}

Anything else is invalid, including: the empty string, whitespace inside the value (`1h 30m`),
signs (`-5m`), decimal points (`1.5h`), upper-case units (`1H`), unknown letters (`1x`), a unit
without digits (`h`) and digits after the last unit (`1h30`).

**R2 — Component order.** {order_rule}

**R3 — Digits only.** {bare_rule}

**R4 — Value.** The result is the sum of all components, as a `timedelta` with whole seconds.
`0s` is valid and yields `timedelta(0)`.

**R5 — Non-string input.** A value that is already a `datetime.timedelta` is used as is (it is not
re-parsed). Any other non-string value is converted with `str()` and then parsed by the rules
above (so an `int` default such as `90` follows rule R3).

**R6 — Bounds.** `min` and `max` are inclusive limits; either may be `None` (no limit). They apply
to every converted value, including `timedelta` values from R5. When the value is shorter than
`min`, fail with the message `{{n}} seconds is below the minimum of {{lo}} seconds.`; when it is
longer than `max`, fail with `{{n}} seconds is above the maximum of {{hi}} seconds.` Here `{{n}}`,
`{{lo}}` and `{{hi}}` are the whole number of seconds of the value and of the limit, written as
plain integers (for example `30 seconds is below the minimum of 60 seconds.`).

**R7 — Invalid input message.** When a value is not valid by R1–R3, fail with the message
`'<text>' is not a valid duration.` where `<text>` is the original string value (or the `str()`
of a non-string value) before stripping, quoted exactly as Python's `repr()` of that string
quotes it. For example the input `1h1h` produces `'1h1h' is not a valid duration.`

**R8 — Error reporting.** All failures go through the standard `ParamType.fail` mechanism
(raising `click.BadParameter`), so on the command line they render like other invalid values,
e.g. `Error: Invalid value for '--timeout': '1h1h' is not a valid duration.` with exit code 2.

**R9 — Introspection.** `to_info_dict()` returns the usual `param_type` and `name` entries plus
`"min"` and `"max"`, each the limit's whole number of seconds as an `int`, or `None` when unset.
For example `click.Duration(max=timedelta(hours=1)).to_info_dict()` is
`{{"param_type": "Duration", "name": "duration", "min": None, "max": 3600}}`.

Existing types and behaviour must not change.
"""

    order_check = (
        "            if seen and UNIT_ORDER.index(unit) <= UNIT_ORDER.index(seen[-1]):\n"
        "                return None\n"
        if desc else
        "            if unit in seen:\n"
        "                return None\n"
    )
    bare_branch = (
        "        if text.isascii() and text.isdigit():\n"
        "            return int(text)\n"
        if bare_secs else
        "        if text.isascii() and text.isdigit():\n"
        "            return None\n"
    )
    gold_class = f'''

class DurationInfoDict(ParamTypeInfoDict):
    min: int | None
    max: int | None


class Duration(ParamType[timedelta]):
    """Converts strings such as ``1h30m`` into :class:`datetime.timedelta`.

    Components are ``<digits><unit>`` with units ``{units}``.

    :param min: Inclusive lower bound, or ``None``.
    :param max: Inclusive upper bound, or ``None``.

    .. versionadded:: 8.6
    """

    name = "duration"

    UNIT_SECONDS = {{{unit_map}}}

    def __init__(
        self, min: timedelta | None = None, max: timedelta | None = None
    ) -> None:
        self.min = min
        self.max = max

    def to_info_dict(self) -> DurationInfoDict:
        return {{
            "min": None if self.min is None else int(self.min.total_seconds()),
            "max": None if self.max is None else int(self.max.total_seconds()),
            **super().to_info_dict(),
        }}

    def _parse(self, text: str) -> int | None:
        UNIT_ORDER = list(self.UNIT_SECONDS)
        text = text.strip()
        if not text:
            return None
{bare_branch}        total = 0
        seen: list[str] = []
        pos = 0
        while pos < len(text):
            start = pos
            while pos < len(text) and text[pos] in "0123456789":
                pos += 1
            if pos == start or pos >= len(text):
                return None
            unit = text[pos]
            if unit not in self.UNIT_SECONDS:
                return None
{order_check}            seen.append(unit)
            total += int(text[start:pos]) * self.UNIT_SECONDS[unit]
            pos += 1
        return total

    def convert(
        self, value: t.Any, param: Parameter | None, ctx: Context | None
    ) -> timedelta:
        if isinstance(value, timedelta):
            rv = value
        else:
            text = value if isinstance(value, str) else str(value)
            seconds = self._parse(text)
            if seconds is None:
                self.fail(
                    _("{{value!r}} is not a valid duration.").format(value=text),
                    param,
                    ctx,
                )
            rv = timedelta(seconds=seconds)

        n = int(rv.total_seconds())
        if self.min is not None and rv < self.min:
            self.fail(
                _("{{n}} seconds is below the minimum of {{lo}} seconds.").format(
                    n=n, lo=int(self.min.total_seconds())
                ),
                param,
                ctx,
            )
        if self.max is not None and rv > self.max:
            self.fail(
                _("{{n}} seconds is above the maximum of {{hi}} seconds.").format(
                    n=n, hi=int(self.max.total_seconds())
                ),
                param,
                ctx,
            )
        return rv

    def __repr__(self) -> str:
        return "Duration"
'''
    gold = [
        Edit("src/click/types.py", "from datetime import datetime\n", "from datetime import timedelta\n"),
        Edit("src/click/types.py", '    def __repr__(self) -> str:\n        return "DateTime"\n', gold_class),
        Edit("src/click/__init__.py", "from .types import DateTime as DateTime\n",
             "from .types import Duration as Duration\n"),
    ]

    # ---------------- feature tests ----------------
    ex_all = "".join(f"1{u}" for u in units)
    ex_all_secs = sum(UNIT_SECONDS[u] for u in units)
    rev = "30m1h"
    tests = f'''from datetime import timedelta

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
    assert f"Error: Invalid value for '--timeout': {{text!r}} is not a valid duration." in r.output
    return r


def test_exported_and_basic_conversion():
    """[R1][R4] exported under click and click.types; converts to timedelta."""
    assert click.Duration is click.types.Duration
    assert issubclass(click.Duration, click.ParamType)
    assert click.Duration().convert("2m", None, None) == timedelta(minutes=2)
    assert click.Duration().name == "duration"


def test_components_sum_on_command_line():
    """[R1][R4]"""
    assert _run(["--timeout", "1h30m"]).output == "5400\\n"
    assert _run(["--timeout", "{ex_all}"]).output == "{ex_all_secs}\\n"
    assert _run(["--timeout", "0s"]).output == "0\\n"
    assert _run(["--timeout", "007m"]).output == "420\\n"


def test_surrounding_whitespace_is_stripped():
    """[R1]"""
    assert _run(["--timeout", "  2m  "]).output == "120\\n"


def test_invalid_grammar():
    """[R1][R7][R8]"""
    for text in ["", "1h 30m", "-5m", "1.5h", "1H", "1x", "h", "1h30", "{big}"]:
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
{"    _bad(['--timeout', '" + rev + "'], '" + rev + "')" if desc else "    assert _run(['--timeout', '" + rev + "']).output == '5400\\n'"}
    assert _run(["--timeout", "1d1s"]).output == "86401\\n"


def test_digits_only():
    """[R3]"""
{"    assert _run(['--timeout', '90']).output == '90\\n'" if bare_secs else "    _bad(['--timeout', '90'], '90')"}


def test_int_default_follows_digits_rule():
    """[R3][R5]"""
    @click.command()
    @click.option("--timeout", type=click.Duration(), default=90)
    def cli(timeout):
        click.echo(int(timeout.total_seconds()))

    r = CliRunner().invoke(cli, [])
{"    assert r.output == '90\\n'" if bare_secs else "    assert r.exit_code == 2\n    assert \"'90' is not a valid duration.\" in r.output"}


def test_timedelta_passthrough():
    """[R5]"""
    td = timedelta(minutes=5, microseconds=0)
    assert click.Duration().convert(td, None, None) is td


def test_bounds_inclusive():
    """[R6]"""
    kw = dict(min=timedelta(minutes=1), max=timedelta(hours=1))
    assert _run(["--timeout", "1m"], **kw).output == "60\\n"
    assert _run(["--timeout", "1h"], **kw).output == "3600\\n"


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
    assert click.Duration(max=timedelta(hours=1)).to_info_dict() == {{
        "param_type": "Duration", "name": "duration", "min": None, "max": 3600,
    }}
    assert click.Duration(min=timedelta(seconds=5)).to_info_dict()["min"] == 5
'''
    # The "{big}" grammar case: a unit letter alone is invalid in every knob setting.

    mutants = [
        Mutant("bounds_exclusive", "treats min/max as exclusive limits",
               (Edit("src/click/types.py", "if self.min is not None and rv < self.min:",
                     "if self.min is not None and rv <= self.min:", "replace"),
                Edit("src/click/types.py", "if self.max is not None and rv > self.max:",
                     "if self.max is not None and rv >= self.max:", "replace"))),
        Mutant("no_strip", "does not strip surrounding whitespace",
               (Edit("src/click/types.py", "        text = text.strip()\n", "", "replace"),)),
        Mutant("message_uses_stripped_text", "reports the stripped text in the error",
               (Edit("src/click/types.py", "            text = value if isinstance(value, str) else str(value)\n",
                     "            text = (value if isinstance(value, str) else str(value)).strip()\n", "replace"),)),
        Mutant("passthrough_skips_bounds", "returns timedelta input before checking bounds",
               (Edit("src/click/types.py", "        if isinstance(value, timedelta):\n            rv = value\n",
                     "        if isinstance(value, timedelta):\n            return value\n", "replace"),)),
        Mutant("bare_number_flipped", "inverts the digits-only rule",
               (Edit("src/click/types.py", "        if text.isascii() and text.isdigit():\n            return "
                     + ("int(text)\n" if bare_secs else "None\n"),
                     "        if text.isascii() and text.isdigit():\n            return "
                     + ("None\n" if bare_secs else "int(text)\n"), "replace"),)),
        Mutant("order_rule_wrong", "uses the other ordering rule",
               (Edit("src/click/types.py", order_check,
                     ("            if unit in seen:\n                return None\n" if desc else
                      "            if seen and UNIT_ORDER.index(unit) <= UNIT_ORDER.index(seen[-1]):\n"
                      "                return None\n"), "replace"),)),
        Mutant("upper_case_units", "accepts upper-case unit letters",
               (Edit("src/click/types.py", "            unit = text[pos]\n",
                     "            unit = text[pos].lower()\n", "replace"),)),
        Mutant("info_dict_timedelta", "reports raw timedelta limits in to_info_dict",
               (Edit("src/click/types.py",
                     '"max": None if self.max is None else int(self.max.total_seconds()),',
                     '"max": self.max,', "replace"),)),
    ]
    return Draft(
        family=FAMILY,
        slug="duration-param-type",
        title="Add a Duration parameter type",
        knobs=dict(knobs),
        instruction=instruction,
        gold_edits=gold,
        test_files={"tests/test_duration_type.py": tests},
        focus_symbols=["src/click/types.py::DateTime.convert",
                       "src/click/types.py::_NumberRangeBase.convert",
                       "src/click/types.py::ParamType.to_info_dict",
                       "src/click/types.py::ParamType.fail"],
        mutants=mutants,
        novelty_probes=[r"class Duration\b", r"timedelta"],
        novelty_queries=["Duration type", "timedelta", "duration param"],
        axes=AXES,
    )
