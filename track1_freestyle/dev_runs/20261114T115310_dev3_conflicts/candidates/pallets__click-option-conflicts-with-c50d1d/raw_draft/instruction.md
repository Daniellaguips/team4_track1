# Mutually exclusive options: `conflicts_with`

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
`ParameterSource.COMMANDLINE` (a value taken from an environment variable does **not** count). Values coming from defaults, `default_map` or an interactive prompt never count.
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

**R5 — Error.** Raise `click.UsageError` for the **first** conflicting pair only (R4 order) with the message `Option <A> cannot be used together with <B>.` Example output line: `Error: Option '--json' cannot be used together with '--yaml'.` `<A>`/`<B>` are each parameter's `get_error_hint(ctx)`
(for an option without `show_envvar`: every declared option string in single quotes joined by
`" / "`, e.g. `'-j' / '--json'`). The error is raised with the command's context, so the
normal usage error output is printed (starting with `Usage: cli [OPTIONS]` for a command named `cli`) and the exit code is 2.
