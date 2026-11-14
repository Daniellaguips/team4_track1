# Add a `Duration` parameter type to Click

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
   - `w` — weeks (7 days) (604800 seconds)
   - `d` — days (86400 seconds)
   - `h` — hours (3600 seconds)
   - `m` — minutes (60 seconds)
   - `s` — seconds (1 seconds)

Anything else is invalid, including: the empty string, whitespace inside the value (`1h 30m`),
signs (`-5m`), decimal points (`1.5h`), upper-case units (`1H`), unknown letters (`1x`), a unit
without digits (`h`) and digits after the last unit (`1h30`).

**R2 — Component order.** Components may appear in any order (`30m1h` is valid and equals `1h30m`), but each unit may appear at most once (`1h1h` and `1h30m2h` are invalid).

**R3 — Digits only.** A value consisting only of digits (no unit letter at all), such as `90`, means that many seconds.

**R4 — Value.** The result is the sum of all components, as a `timedelta` with whole seconds.
`0s` is valid and yields `timedelta(0)`.

**R5 — Non-string input.** A value that is already a `datetime.timedelta` is used as is (it is not
re-parsed). Any other non-string value is converted with `str()` and then parsed by the rules
above (so an `int` default such as `90` follows rule R3).

**R6 — Bounds.** `min` and `max` are inclusive limits; either may be `None` (no limit). They apply
to every converted value, including `timedelta` values from R5. When the value is shorter than
`min`, fail with the message `{n} seconds is below the minimum of {lo} seconds.`; when it is
longer than `max`, fail with `{n} seconds is above the maximum of {hi} seconds.` Here `{n}`,
`{lo}` and `{hi}` are the whole number of seconds of the value and of the limit, written as
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
`{"param_type": "Duration", "name": "duration", "min": None, "max": 3600}`.

Existing types and behaviour must not change.
