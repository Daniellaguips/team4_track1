# Unique-prefix command abbreviations for `click.Group`

Users of large command-line tools like typing `tool stat` instead of `tool status`. Add opt-in
support to `click.Group` for invoking a subcommand by any unambiguous prefix of its name.

## Public interface

- New keyword argument `allow_abbreviations: bool = False` on `click.Group.__init__`, stored as
  the attribute `allow_abbreviations`. Because `click.group()` and `Group.group()` forward keyword
  arguments to the class, `@click.group(allow_abbreviations=True)` must work too, and so must
  subclasses such as `click.CommandCollection` (which forwards its keyword arguments to `Group`).
- The behaviour lives in `Group.resolve_command(ctx, args)`, which keeps its signature and return
  shape `(command_name, command, remaining_args)`.

## Requirements

**R1 — Off by default.** With `allow_abbreviations=False` nothing changes: an unknown name such as
`st` fails exactly as today (`Error: No such command 'st'.`, exit code 2).

**R2 — Lookup order.** For the first remaining argument (the *token*), resolution is:
1. the existing exact lookup with `get_command(ctx, token)`;
2. the existing retry with `ctx.token_normalize_func(token)` when a normalize function is set
   (from now on *token* means this normalized value);
3. only if both fail and `allow_abbreviations` is true: prefix matching (R3–R6).
An exact name therefore always wins, even if it is also a prefix of other names (with commands
`run` and `runner`, `run` invokes `run` and `runn` invokes `runner`).

**R3 — Candidates.** Iterate over `self.list_commands(ctx)` (not the `commands` mapping, so groups
that compute their commands dynamically — e.g. `click.CommandCollection(sources=[a, b])` — work) and fetch each command
with `self.get_command(ctx, name)`; names for which `get_command` returns `None` are skipped. A
name is a candidate when it starts with the token. When `ctx.token_normalize_func` is set, the
name is passed through that function before the comparison (the command is still the one
registered under the original name). Hidden commands (`hidden=True`) never take part in prefix matching; they can still be invoked by their exact name. An empty token never matches anything.

**R4 — Exactly one candidate.** It is resolved: the returned command name is the candidate's
*registered* name, not the typed prefix. Consequently `ctx.invoked_subcommand` holds the full
name and the sub-command's context is created with the full name, so for example
`cli stat --help` prints a usage line starting with `Usage: cli status`.

**R5 — Several candidates.** Raise `click.UsageError` (with the group's context, so the usage line is
shown, e.g. `Usage: cli [OPTIONS] COMMAND [ARGS]...`) with the message `Ambiguous command '<token>'. Could be: <names>.` where `<token>` is the
token after normalization and `<names>` are the candidates' registered names sorted alphabetically,
joined with `", "`. For commands `start`, `status`, `stop` and the token `st`, the output contains
`Error: Ambiguous command 'st'. Could be: start, status, stop.` and the exit code is 2. During resilient parsing
(`ctx.resilient_parsing`, used by shell completion) no error is raised; the token is treated as
unknown instead.

**R6 — No candidate.** Behaviour is unchanged: `Error: No such command '<token>'.`, exit code 2.

**R7 — Chained groups.** In `chain=True` groups every subcommand token is resolved by the same rules,
so `cli bui te` runs `build` then `test` when those are unique prefixes.

Help output, shell completion and every other existing behaviour must stay unchanged.
