# Add `click.Duration`, a human-readable duration parameter type

## Motivation

CLI tools often take timeouts and intervals such as `--timeout 1h30m` or `--every 90s`. Click has no built-in type for this, so each application rewrites a fragile parser, often with float arithmetic and inconsistent errors. Add an opt-in `ParamType` named `Duration`. It converts human-written durations into an exact `int` number of seconds, or a `datetime.timedelta`. Existing types and behavior must not change.

## Public interface

- `click.Duration(*, min=None, max=None, min_open=False, max_open=False, as_timedelta=False)`. All arguments are keyword-only.
- `click.types.Duration` is the same class. It is also exported as `click.Duration` from `click/__init__.py`.
- `Duration.name == "duration"`.
- `Duration.convert(value, param, ctx)` and `Duration.__call__(value, param=None, ctx=None)`. `None` is handled by the inherited `__call__`, which returns `None` without calling `convert`.
- `Duration.to_info_dict()`.
- `repr(Duration()) == "DURATION"`.

`Duration` is defined in `click/types.py` and subclasses `ParamType`. Its converted value type is `int` or `timedelta`.

## Rules

**R1. String grammar.**
- After `str.strip()` on both ends, a string input must be non-empty and at most 256 characters.
- It must consist of one or more terms.
- A term is a number immediately followed by exactly one unit letter, with no whitespace between them.
- A number is one or more ASCII digits `[0-9]`, optionally followed by `.` and one or more ASCII digits.
- Terms may be joined with nothing, or with any run of spaces and tabs.
- Units are case-sensitive: `w`=604800, `d`=86400, `h`=3600, `m`=60, `s`=1 seconds.
- Leading zeros are allowed and zero-valued terms are allowed (`'0s'` is 0, `'007s'` is 7, `'0h0m'` is 0).
- Anything else is invalid: signs, `'.5h'`, `'1.h'`, `'1 h'`, `'1H'`, `'5y'`, `'90'` (bare number), `'1h,30m'`, Unicode digits such as `'\u0663h'`, and newlines or other whitespace inside the string.
- Output: a parsed list of `(number, unit)` terms, which feeds R3 onward.
- Error: `click.BadParameter` with message exactly `"{value!r} is not a valid duration."`, where `{value!r}` is the repr of the ORIGINAL unstripped input string.
- Precedence: grammar is checked first, before duplicate/order (R3), overflow (R6), whole-number (R5) and bounds (R7). An over-length (>256 chars) or empty string fails here.
- Bounds: the maximum length is 256 characters measured after strip. Exactly 256 is accepted if otherwise valid.
- State: none.

**R2. Non-string inputs.**
- An `int` that is not a `bool` is taken as a count of seconds.
- A `datetime.timedelta` is taken as its exact length.
- Both skip grammar and order checks (R1, R3) and go straight to R6, R5 and R7.
- Negative ints, negative timedeltas, bools, floats, bytes and any other type are invalid.
- The value `None` is handled by the inherited `__call__` (returns `None` without calling `convert`).
- Output: as R4/R5. For example `Duration()(90) == 90` and `Duration(as_timedelta=True)(90) == timedelta(seconds=90)`.
- Errors: invalid types or negative values raise `click.BadParameter` `"{value!r} is not a valid duration."`
- Precedence: the type/negativity check happens first. A valid timedelta with a non-zero microsecond part in int mode then hits the R5 whole-seconds error, not R1.
- Bounds: 0 is valid.
- State: none.

**R3. Unit order and duplicates.**
- Terms must appear in strictly descending unit size: `w`, `d`, `h`, `m`, `s`.
- Scan terms left to right. The first failing term decides the error.
- If the term's unit already appeared in any earlier term, fail with the duplicate error.
- Otherwise, if the term's unit is larger than the unit of the immediately preceding term, fail with the order error.
- So `'1h30m'` and `'2w 3d 4h 5m 6s'` are valid; `'1m1h'` is an order error; `'1h1h'` and `'1h30m1h'` are duplicate errors; `'1m1h1h'` is an order error (the first failing term is the first `h`).
- Input: a string that already passed R1.
- Errors:
  - Duplicate: `click.BadParameter` `"{value!r} repeats the unit {unit!r}."` (e.g. `"'1h1h' repeats the unit 'h'."`).
  - Order: `click.BadParameter` `"{value!r} has units out of order; use largest to smallest."`
- Precedence: when a single term is both a duplicate and out of order, the duplicate error wins over the order error. Both run after R1 and before R6.
- State: the "seen units" set is per call, never shared between calls or instances.

**R4. Exact arithmetic.**
- Each term's value is multiplied by its unit seconds and the terms are summed using exact rational/integer arithmetic.
- Floats must not be used anywhere, including in the intermediate value.
- Examples: `'1.5h'` is exactly 5400 s, `'0.1h0.2m'` is exactly 372 s, `'1.1m'` is exactly 66 s, `'0.5s'` is exactly one half second, `'0.000001s'` is exactly one microsecond.
- The same exact total is used for the later checks R6, R5 and R7.
- Output: exact total seconds as a rational (not exposed directly).
- Errors: none.
- Precedence: runs after R3, before R6/R5/R7.
- Bounds: decimal digits in a term are unlimited, within the 256-character cap of R1.
- State: none.

**R5. Output modes and whole-unit rule.**
- With `as_timedelta=False` (the default) the result is a plain Python `int` (type exactly `int`) number of seconds, and the exact total must be a whole number of seconds.
- With `as_timedelta=True` the result is a `datetime.timedelta`, and the exact total must be a whole number of microseconds.
- Nothing is rounded, truncated or floored.
- Examples: `'1.5h'` gives 5400 in int mode; `'0.5s'` fails in int mode; `'0.5s'` gives `timedelta(microseconds=500000)` in timedelta mode; `'0.0000005s'` fails in both modes.
- Errors:
  - int mode: `click.BadParameter` `"{value!r} is not a whole number of seconds."`
  - timedelta mode: `click.BadParameter` `"{value!r} is not a whole number of microseconds."`
- Precedence: runs after the overflow check R6 and before the bounds check R7. So in int mode `'59.5s'` with `min=60` reports the whole-seconds error, while in timedelta mode it reports the range error.
- State: none.

**R6. Overflow cap.**
- Independently of any `max`, the exact total must not exceed 315360000 seconds (3650 days).
- Exactly 315360000 is accepted (`'3650d'` is ok, `'3651d'` is not).
- The cap applies to strings, ints and timedeltas.
- Error: `click.BadParameter` `"{value!r} is too large; the maximum is 315360000 seconds."`
- Precedence: checked after R1/R3/R4 and before R5 and R7. If the total is too large, neither the whole-number error nor the range error is reported. For example `'3651d'` with `max=10` reports "too large".
- Bounds: the cap is inclusive. A total > 315360000 fails; a total == 315360000 passes.
- State: none.

**R7. Min/max bounds.**
- `min` and `max` are integer seconds, whatever the output mode.
- The comparison uses the exact total (R4), not the converted output.
- `min` is inclusive unless `min_open=True`, and `max` is inclusive unless `max_open=True`.
- A value outside the range fails. When no bound is set, this check is skipped.
- The failure message embeds a range description:
  - only min: `'x>=60'` (or `'x>60'` when `min_open`);
  - only max: `'x<=3600'` (or `'x<3600'` when `max_open`);
  - both: `'60<=x<=3600'` with `<` replacing `<=` on each open side, e.g. `'60<x<3600'`.
- Error: `click.BadParameter` `"{value!r} is out of range: expected {range}."`, e.g. `"'30s' is out of range: expected 60<=x<=3600."` (`{value!r}` is the repr of the original input, which may be an int or timedelta.)
- Precedence: last of the value checks, after R6 and R5. `min_open`/`max_open` without a corresponding `min`/`max` have no effect.
- Bounds: inclusive by default. `Duration(min=60)('1m') == 60` and `Duration(min=60, min_open=True)('1m')` fails; `Duration(max=3600)('1h') == 3600` and `Duration(max=3600, max_open=True)('1h')` fails.

**R8. Constructor validation**, checked eagerly in `__init__` in this order:
1. `min` and `max` must each be `None` or an `int` that is not a `bool` and is >= 0. Otherwise raise `ValueError("min and max must be non-negative integers.")`.
2. `min` must not exceed `max` when both are given. Otherwise raise `ValueError("min must not be greater than max.")`.
3. If `min == max` and (`min_open` or `max_open`), the range is empty. Raise `ValueError("the range is empty.")`.

- All constructor arguments are keyword-only. Positional arguments raise the normal `TypeError`.
- The checks run in the listed order, so `min=5, max=1.5` reports (1) and not (2).
- `min == max` with both ends closed is valid (a single accepted value).
- Instances are immutable in practice. Attributes `min`, `max`, `min_open`, `max_open` and `as_timedelta` are stored under those names.

**R9. Error plumbing and use in commands.**
- Errors are raised through `ParamType.fail`, so they are `click.BadParameter` with the exact message strings above.
- Within a command, the standard "Invalid value for ...: <message>" wrapping applies.
- The type works with `ctx=None` and `param=None` (prompt use), and with defaults. For example `@click.option('--t', type=click.Duration(), default='1h30m')` yields 5400 when omitted, and an int default 90 yields 90.
- `BadParameter` is raised only for invalid values; `ValueError` only from the constructor (R8).
- Value-check order overall: R1/R2 type check, R3, R6, R5, R7. The first failure is the one reported.

**R10. Metadata.**
- The class attribute `name` is `'duration'`.
- `to_info_dict()` returns a dict with exactly the keys `param_type` (`'Duration'`), `name` (`'duration'`), `as_timedelta` (bool), `min` (int|None), `max` (int|None), `min_open` (bool) and `max_open` (bool).
- `repr(Duration(...))` is always `'DURATION'`, regardless of settings.
- `is_composite` stays `False` and `arity` stays 1.
- With no custom metavar the help metavar is `'DURATION'`.

**R11. Packaging and statelessness.**
- `Duration` is defined in `click/types.py`, subclasses `ParamType`, and is re-exported as `click.Duration` in `click/__init__.py`.
- Importing click must not import any module outside the import allowlist at module level. `re` and `datetime` are allowed, but `fractions`, `decimal` and `math` are not. Exact arithmetic must therefore use integers, or import lazily inside a method.
- No warnings are emitted, because the project's tests run with `filterwarnings=error`.
- One instance can be called repeatedly and from many commands with no cross-call effects. A failed conversion never changes the result of the next one, and compiled patterns never use shared match state.
- No per-call data is kept on the instance. Calling the same instance with `'1h1h'` (error) and then `'1h'` returns 3600.

## Examples

| Call | Result |
|---|---|
| `Duration()('1h30m')` | `5400` |
| `Duration()('  2w 3d 4h 5m 6s ')` | `1483506` (int) |
| `Duration()('1.1m')` | `66` |
| `Duration()('0.1h0.2m')` | `372` |
| `Duration()('0s')` | `0` |
| `Duration()('3650d')` | `315360000` |
| `Duration()('3651d')` | BadParameter `'3651d' is too large; the maximum is 315360000 seconds.` |
| `Duration(as_timedelta=True)('0.5s')` | `timedelta(microseconds=500000)` |
| `Duration()('0.5s')` | BadParameter `'0.5s' is not a whole number of seconds.` |
| `Duration(as_timedelta=True)('0.0000005s')` | BadParameter `'0.0000005s' is not a whole number of microseconds.` |
| `Duration()('1m1h')` | BadParameter `'1m1h' has units out of order; use largest to smallest.` |
| `Duration()('1h30m1h')` | BadParameter `'1h30m1h' repeats the unit 'h'.` |
| `Duration()('1 h')` | BadParameter `'1 h' is not a valid duration.` |
| `Duration()(True)` | BadParameter `True is not a valid duration.` |
| `Duration(min=60, max=3600)('30s')` | BadParameter `'30s' is out of range: expected 60<=x<=3600.` |
| `Duration(min=60, min_open=True)('1m')` | BadParameter `'1m' is out of range: expected x>60.` |
| `Duration(min=60)('59.5s')` | BadParameter `'59.5s' is not a whole number of seconds.` |
| `Duration(min=60, as_timedelta=True)('59.5s')` | BadParameter `'59.5s' is out of range: expected x>=60.` |
| `Duration(min=3, max=3, max_open=True)` | `ValueError: the range is empty.` |
| `repr(Duration(min=1))` | `'DURATION'` |
