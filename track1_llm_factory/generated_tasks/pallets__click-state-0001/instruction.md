# Invocation ledger: an opt-in, invocation-scoped event log shared by every `Context` in a run

## Motivation

A Click run builds a tree of `Context` objects (groups, subcommands, chained commands, `ctx.invoke`/`ctx.forward` sub-contexts). There is currently no single place to see what happened across that tree, in order. This feature adds an opt-in **ledger**: one ordered list of `(event, name)` tuples shared by every context of a run. Built-in code paths record `'parse'`, `'invoke'`, `'call'`, `'forward'`, `'result'` and `'deprecated'` events through a public `Context.record()` hook. `CliRunner.invoke` exposes the ledger as `Result.ledger`, and a new eager `@click.ledger_option` can turn recording on mid-run and print the ledger to stderr when the root context closes. The ledger is disabled by default. When it is disabled, nothing about existing behavior changes.

## Public interface

- `click.Context(..., ledger: bool | list | None = None)`
- `click.Context.ledger`: read-only property returning `tuple[tuple[str, str | None], ...]`
- `click.Context.ledger_enabled`: read-only property returning `bool`
- `click.Context.record(event: str, name: str | None = None) -> None`
- `click.ledger_option(*param_decls, **kwargs)`: new decorator implemented in `decorators.py` and exported from `click/__init__.py`
- `click.testing.CliRunner(..., ledger: bool = False)`
- `click.testing.CliRunner.invoke(..., ledger: bool | None = None)`
- `click.testing.Result.ledger`: tuple of `(event, name)` tuples

## Rules

**R1.** `Context.__init__` accepts a new keyword `ledger` (default `None`). The whole context tree shares ONE state: an entries list plus an enabled flag. The state is passed from parent to child by reference, like `meta`.

- Validation comes first. Anything other than a `bool`, a `list` or `None` (so `1`, `'x'` and `()` are invalid) raises `TypeError("'ledger' must be a bool, a list or None.")`.
- Root context (parent is `None`):
  - A list is adopted BY IDENTITY (not copied) and enables recording.
  - `True` creates a new empty list and enables recording.
  - `False`/`None` creates a new empty list and leaves recording disabled.
- Non-root context:
  - `True` or any list enables the tree's shared state. The list is NOT adopted; entries keep going to the tree's existing list.
  - `False`/`None` changes nothing, so a child can never disable recording.
- Enabling on any context enables it for every context of the tree, ancestors and siblings included.
- Contexts created by `ctx.invoke(Command)`, `_make_sub_context`, `make_context(parent=...)` and chained or nested groups all share the state.
- Passing `ledger` through `Command.context_settings` works with the existing rule that explicit `make_context` extras win over `context_settings`.
- Precedence at a root context: explicit `make_context`/`main` extras beat `Command.context_settings`, and `context_settings` beats the default (disabled). At a non-root context a truthy value can only turn recording on, never off.
- Bounds: `bool` is accepted, int `0`/`1` is not. An empty list at the root is adopted and enables recording.
- State lives on the tree (root-created, shared by reference). No module-level or class-level state may exist. The shared state is stored on the context as `_ledger_state`.

**R2.** `Context.ledger_enabled` returns the tree's enabled flag. `Context.ledger` returns a tuple snapshot of the shared entries: a new tuple on every access, and the empty tuple when nothing was recorded. `Context.record(event, name=None)` is the only way internal code appends.

- It first validates its arguments, in this order, always, even when recording is disabled:
  - `TypeError(f"Ledger event must be a non-empty string, got {event!r}.")` when `event` is not a `str` or is `''`.
  - Else `TypeError(f"Ledger name must be a string or None, got {name!r}.")` when `name` is neither `str` nor `None`.
- It then returns `None` without appending if recording is disabled or `self.resilient_parsing` is `True`.
- Otherwise it appends the tuple `(event, name)` to the shared entries.
- Every built-in event listed in R3-R8 MUST be recorded by calling `ctx.record(...)` on the context named in that rule, never by touching the list directly. A user `context_class` that overrides `record` (and may call `super`) then observes every built-in event recorded on its own context, in order.
- Precedence: a validation error beats the disabled/resilient no-op. The resilient check applies to the context `record` is called on, not to the tree: `resilient_parsing` is not inherited by child contexts.
- Bounds: event names outside the built-in set are allowed (user events). An empty-string name is a valid name.
- Appends are visible immediately through `ledger` on every context of the tree.

**R3.** `'parse'` event. `Command.parse_args` calls `ctx.record('parse', ctx.info_name)` as its very last step, after the "unexpected extra arguments" check, once per call.

- `Group.parse_args` is NOT changed to record (it already delegates to `super().parse_args`), so a group records exactly one `'parse'` per `parse_args` call.
- A parse that raises (usage error, `NoArgsIsHelpError`, missing parameter, unexpected extra args) records no `'parse'` for that context.
- A user subclass that overrides `parse_args` and calls `super()` gets the event from `super`.
- Parameters processed earlier in the same `parse_args` (eager callbacks, deprecation notices) therefore appear BEFORE the context's `'parse'` entry.
- The entry is `('parse', info_name)`, and `info_name` may be `None`.
- It is skipped in resilient parsing (R2). An eager `--ledger` option (R9) turns recording on during this very parse, so this context's own `'parse'` IS recorded.
- A group whose `resolve_command` re-runs `parse_args` for an option-like unknown token ends in a `NoSuchCommand`/usage error and records nothing extra on the failing path.
- Each context records for itself on the shared list; children parsed later append after the parent.

**R4.** `'invoke'` event. `Command.invoke(ctx)` calls `ctx.record('invoke', ctx.info_name)` as its first statement, before the deprecated-command notice and before the callback. It is recorded once per `Command.invoke` call.

- Because `Group.invoke` calls `super().invoke(ctx)` for the group's own callback, a group records `'invoke'` only on the paths where that call happens: a subcommand is given, or `invoke_without_command` with no subcommand. With no subcommand and `invoke_without_command=False` ("Missing command.") nothing is recorded.
- Resulting orders:
  - Non-chain `g sub`: parse g, invoke g, parse sub, invoke sub.
  - Chain `g a b`: parse g, invoke g, parse a, parse b, invoke a, invoke b (all chained subcommands are parsed before any of them is invoked).
  - Nested non-chain groups: parse root, invoke root, parse inner, invoke inner, parse leaf, invoke leaf.
- `ctx.invoke(callback)` with a plain function never goes through `Command.invoke`, so it adds no `'invoke'` (R5).
- Callback-less commands still record `'invoke'`.
- Order is the global append order across the shared list, not per-context.

**R5.** `'call'` event. `Context.invoke(callback, ...)` records ONLY when `callback` is a `Command`.

- After the existing "The given command does not have a callback that can be invoked." `TypeError` check, and just before the callback runs, it calls `self.record('call', other_cmd.name)`. `self` is the calling context, and the name may be `None`.
- Calling a plain function through `ctx.invoke` records nothing. In particular the internal `ctx.invoke(self.callback, **ctx.params)` made by `Command.invoke` and the `ctx.invoke(self._result_callback, ...)` made by `Group.invoke` are plain-function calls and record no `'call'`.
- A Command invoked this way bypasses its own `parse_args` and `Command.invoke`, so it adds no `'parse'`, no `'invoke'` and no deprecated-command event (R8); only `'call'`.
- Its sub-context shares the tree's ledger, so events recorded inside the callback land after the `'call'` entry.
- The existing `TypeError` for a callback-less command is unchanged and nothing is recorded for it.
- It records one `'call'` per call, including repeated or recursive calls, at any nesting depth (R1).
- `forward()` produces a `'forward'` entry immediately followed by this `'call'` entry (R6).

**R6.** `'forward'` event. `Context.forward(cmd, ...)` calls `self.record('forward', cmd.name)` after its existing "Callback is not a command." `TypeError` check and before delegating to `self.invoke`.

- Since `invoke` then records `'call'` (R5), forwarding to a Command yields exactly `('forward', name)` then `('call', name)`. The argument-defaulting work records nothing.
- `TypeError('Callback is not a command.')` is unchanged, and nothing is recorded when it is raised.
- `'forward'` is recorded before R5's entry. A missing-callback `TypeError` raised inside `invoke` leaves the `'forward'` entry in place with no `'call'`.
- Forwarding from within a forwarded callback records a second forward/call pair after the first call entry.
- It is recorded on `self`, so a custom `context_class` `record` override on the forwarding context sees `'forward'` and `'call'`.

**R7.** `'result'` event. In `Group.invoke`, the inner `_process_result` calls `ctx.record('result', ctx.info_name)` immediately before invoking the result callback, only when `self._result_callback is not None`.

- It happens on every path that calls `_process_result` (subcommand, chain, `invoke_without_command`).
- With `chain=True` it is recorded once, after all chained `'invoke'` entries.
- Chained result callbacks registered through repeated `@group.result_callback()` produce a single `'result'` entry (one `_process_result` call).
- In nested groups the inner group's `'result'` precedes the outer group's.
- A group without a result callback records nothing.
- It is not recorded when the group fails before reaching `_process_result`.
- The `'result'` entry always follows the `'invoke'` entries of everything the group dispatched to.
- It is recorded on the group's own context, so `context_class` overrides on that group see it.

**R8.** `'deprecated'` event. Whenever click prints a deprecation notice it records the event on the relevant context immediately before echoing.

- For a deprecated command (`Command.invoke`) the entry is `('deprecated', self.name)`, recorded after that command's `'invoke'` entry and before the callback.
- For a deprecated parameter (`Parameter.handle_parse_result`, only when the notice is actually printed, i.e. value given and source < `DEFAULT_MAP`) the entry is `('deprecated', self.human_readable_name)`, recorded on `ctx` before the echo.
- The name is the same string the printed message shows.
- The notice text printed to stderr is byte-identical to before.
- Recording is subject to R2: while the context is `resilient_parsing` the notice is still printed but nothing is recorded.
- Parameter notices occur during `parse_args`, so they precede that context's `'parse'` entry (R3).
- A deprecated parameter used 2 times (`multiple=True`) is processed once, so one entry.
- A parameter whose value comes from default or `default_map` records nothing.
- Tracking per-run deprecations is simply filtering `ledger` for `'deprecated'`.

**R9.** New decorator `click.ledger_option(*param_decls, **kwargs)`, in `decorators.py`, exported from `click/__init__.py` as `ledger_option`, modeled on `version_option`.

- The default declaration is `'--ledger'`.
- It builds an option with `kwargs.setdefault` for `is_flag=True`, `expose_value=False`, `is_eager=True` and `help='Print the invocation ledger to stderr when the run ends.'`.
- Any `callback` in kwargs is replaced by the built-in callback.
- The built-in callback does nothing when the value is falsy or `ctx.resilient_parsing` is `True`. Otherwise it enables recording on ctx's tree (as R1 non-root `True`) and registers, via `ctx.find_root().call_on_close(...)`, a function that on root close writes one line per entry currently in the shared ledger, in order, to stderr using `click.echo(err=True)`.
- The line is `f"{event}: {name}"`, or just `event` when name is `None`.
- No local variable named `ledger` is exposed to the command callback.
- Each activation registers its own printer (using the option on both a group and its subcommand prints the ledger twice).
- Only events recorded after the option's callback runs exist. If `--ledger` is on a subcommand and recording was not already enabled, the root's `'parse'`/`'invoke'` and the group's events are NOT in the ledger, but the subcommand's own `'parse'`, and everything after, are.
- It only turns recording on. If recording is already enabled by R1 or R10, events are not duplicated.
- The printer reads the ledger at close time, so events recorded between option processing and root close are included. `ctx.exit()` closes the root before raising `Exit` and therefore also prints.
- Because it is eager, it runs before non-eager options of the same command, so those options' deprecated notices are recorded. It works with chain groups and nested groups.
- Example stderr lines: `parse: cli`, `invoke: cli`, `parse: sub`, `invoke: sub`.

**R10.** `testing.py`: `CliRunner.__init__` gains `ledger: bool = False` (stored as `self.ledger`). `CliRunner.invoke` gains the named parameter `ledger: bool | None = None`, placed before `**extra`, so `ledger` is no longer forwarded in `**extra`.

- `None` means use `self.ledger`. Otherwise the explicit bool wins.
- When the effective value is truthy, `invoke` creates a NEW empty list for that call and calls `cli.main(args=..., prog_name=..., ledger=<that list>, **extra)`. The root Context adopts it by identity (R1) and wins over `context_settings`.
- When falsy, no `ledger` is passed to `main`.
- `Result` gains the keyword argument `ledger` (default `()`, appended after `exc_info` so positional construction is unchanged) and the attribute `Result.ledger`: the tuple of entries from that call's list, captured in the `finally` block. Entries recorded before an exception, a `SystemExit` or a usage error are therefore still present.
- When the effective ledger is falsy, `Result.ledger == ()`.
- No type validation on the runner side; truthiness is used.
- Per-call `ledger=` beats the runner default. The runner-provided list beats `cli.context_settings['ledger']`.
- A command using `@ledger_option` under runner `ledger=False` still gets entries printed to stderr, but `Result.ledger` stays `()`.
- `catch_exceptions=False` re-raises, but the list was already filled.
- A fresh list is used per `invoke` call, never reused across calls and never stored on the runner.

**R11.** Reset/isolation: ledger state exists only on Context trees.

- Two successive `CliRunner.invoke` calls on the same runner and same command object yield independent ledgers (the second `Result.ledger` never contains entries from the first).
- Two successive `cli.make_context(...)` calls produce independent roots.
- A child context built with `parent=ctx` always shares ctx's state, even if a custom `context_class` subclass overrides `__init__` and forwards `parent`/`ledger` through.
- Reusing ONE Context object for two separate invocations is not reset (entries accumulate). `Context.close()` does not clear entries.
- `Result.ledger` is an immutable snapshot taken at the end of `invoke`; later events on the same Context do not alter it.
- Reset is achieved by the fresh list per call (R10). Adoption by identity (R1) makes `Result.ledger` see later appends.
- No module-level or class-level list/flag; threads are out of scope.

**R12.** Backward compatibility: with recording disabled (the default) every existing behavior is byte-identical. This covers:

- stdout/stderr text (help output, errors, deprecation notices), exit codes and return values;
- `ctx.params`, parameter sources and callback ordering;
- the `to_info_dict` structures (no `'ledger'` key is added to `Context.to_info_dict` or `Command.to_info_dict`);
- warnings emitted (no new warnings, since pytest runs with `filterwarnings=error`);
- `Result` positional constructor arguments and `repr`;
- the set of module-level imports of every click module (no new top-level imports; use function-local imports where needed).

Further constraints:

- Events recorded before a failure stay in the ledger (no rollback). For example, a subcommand parse error after the group ran leaves `('parse', g)`, `('invoke', g)` and no `'parse'` for the failing subcommand.
- R12 beats any implementation choice that would alter output when the ledger is disabled. Enabling recording must also not change any user-visible output other than via R9's explicit stderr printing.
- `ledger_enabled` `False` means `record` still validates arguments (R2) but appends nothing.
- Recording never mutates `ctx.params`, `ctx.args`, `ctx.meta` or `ctx.obj`.

## Examples

| Scenario | Result |
|---|---|
| `Context(cmd, ledger=1)` | `TypeError: 'ledger' must be a bool, a list or None.` |
| `lst = []; Context(cmd, ledger=lst)` | root adopts `lst` by identity; `ctx.ledger_enabled is True` |
| `Context(cmd)` then `ctx.record('x', 'y')` | returns `None`, `ctx.ledger == ()` (disabled) |
| `ctx.record('', None)` / `ctx.record('x', 5)` | `TypeError: Ledger event must be a non-empty string, got ''.` / `TypeError: Ledger name must be a string or None, got 5.` |
| `CliRunner(ledger=True).invoke(g, ['sub'])` | `Result.ledger == (('parse','g'),('invoke','g'),('parse','sub'),('invoke','sub'))` |
| Chain group `g a b` | `parse g, invoke g, parse a, parse b, invoke a, invoke b` (plus `result g` if a result callback exists) |
| `ctx.forward(other)` inside a command | `('forward','other'), ('call','other')` |
| `ctx.invoke(plain_function)` | nothing recorded |
| `--ledger` on the root command `cli` with subcommand `sub` | stderr: `parse: cli`, `invoke: cli`, `parse: sub`, `invoke: sub` |
| `--ledger` only on subcommand `sub`, recording not already enabled | stderr: `parse: sub`, `invoke: sub` |
| Deprecated option `--old` given | `('deprecated', 'old')` appears before that command's `('parse', ...)` |
