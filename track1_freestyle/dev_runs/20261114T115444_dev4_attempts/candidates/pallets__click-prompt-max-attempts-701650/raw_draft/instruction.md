# Bounded retries for prompts

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
an empty answer when the prompt has no default (today it is silently asked again; it still is, but it now counts as a failed attempt; no message is printed for it). An empty answer when a default exists is not a failure (the default is used).

**R3 — Failed attempts of `confirm`.** Every answer that prints `Error: invalid input` today is a
failed attempt.

**R4 — Giving up.** When the number of failed attempts reaches `max_attempts`, stop asking and
raise `click.Abort()` (inside a command this prints `Aborted!` and exits with code 1). The message for the last failed attempt is printed before giving up, and no further
input is read. A valid answer given before the budget is used up is returned normally, so with
`max_attempts=3` two bad answers followed by a good one succeed.

**R5 — Unchanged behaviour.** Aborting with Ctrl-C/EOF still raises `click.Abort`; with
`max_attempts=None` (the default) everything behaves exactly as before.
